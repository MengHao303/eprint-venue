#!/usr/bin/env python3
"""Fetch Cryptology ePrint Archive metadata, including the Publication info
field that the year listing pages omit.

Metadata only (no PDFs), polite rate limiting, and incremental: papers whose
"last updated" date is unchanged since the previous run are not re-fetched.
"""
import argparse
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

BASE = "https://eprint.iacr.org"
# Identify honestly; override with EPRINT_UA when running somewhere else.
UA = os.environ.get(
    "EPRINT_UA",
    "Claude-User (eprint publication-info viewer)")
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# The archive sits behind Cloudflare rate limiting, so one request at a time,
# spaced out, and back off hard whenever it answers 429.
STATE = {"delay": 1.0, "last": 0.0}


def get(url, retries=6):
    for attempt in range(retries):
        wait = STATE["delay"] - (time.time() - STATE["last"])
        if wait > 0:
            time.sleep(wait)
        STATE["last"] = time.time()
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code == 429:
                pause = int(e.headers.get("Retry-After") or 0) or 60 * (attempt + 1)
                STATE["delay"] = min(STATE["delay"] + 0.25, 5.0)
                sys.stderr.write(f"\n  rate limited; pausing {pause}s "
                                 f"(delay now {STATE['delay']:.2f}s)\n")
                time.sleep(pause)
                continue
            if attempt == retries - 1:
                raise
        except Exception:
            if attempt == retries - 1:
                raise
        time.sleep(2 * (attempt + 1))
    return None


def strip_tags(s):
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(s).strip()


def collapse(s):
    return re.sub(r"\s+", " ", s).strip()


LISTING_ENTRY = re.compile(
    r'<a href="/(\d{4}/\d+)">\1</a>.*?Last updated:&nbsp;\s*([\d-]+)', re.S)


def list_year(year):
    """Return {paper_id: last_updated} for every paper of a year."""
    ids, offset = {}, 0
    while True:
        url = f"{BASE}/{year}/" if offset == 0 else f"{BASE}/{year}/?offset={offset}"
        page = get(url)
        if not page:
            break
        found = LISTING_ENTRY.findall(page)
        if not found:
            break
        for pid, updated in found:
            ids[pid] = updated
        sys.stderr.write(f"\r  listing {year}: {len(ids)} papers")
        sys.stderr.flush()
        if f'href="/{year}/?offset={offset + 100}"' not in page:
            break
        offset += 100
    sys.stderr.write("\n")
    return ids


def parse_paper(pid, page):
    def meta_field(name):
        m = re.search(r"<dt>\s*%s\s*</dt>\s*(.*?)(?=<dt>|</dl>)" % name, page, re.S)
        return m.group(1) if m else ""

    title = ""
    m = re.search(r'<meta name="citation_title" content="([^"]*)"', page)
    if m:
        title = html.unescape(m.group(1))
    authors = [html.unescape(a) for a in
               re.findall(r'<meta name="citation_author" content="([^"]*)"', page)]

    abstract = ""
    m = re.search(r'<p style="white-space: pre-wrap;[^"]*">(.*?)</p>', page, re.S)
    if not m:
        m = re.search(r'class="paper-abstract"[^>]*>(.*?)</p>', page, re.S)
    if m:
        abstract = strip_tags(m.group(1))

    category = ""
    m = re.search(r'<small class="badge category category-[A-Z]+">([^<]*)</small>', page)
    if m:
        category = html.unescape(m.group(1))

    pubinfo_raw = meta_field("Publication info")
    pubinfo = collapse(strip_tags(pubinfo_raw))
    doi = ""
    m = re.search(r'href="(https?://(?:dx\.)?doi\.org/[^"]+)"', pubinfo_raw)
    if m:
        doi = html.unescape(m.group(1))

    keywords = [html.unescape(k) for k in
                re.findall(r'class="me-2 badge bg-secondary keyword">([^<]*)</a>',
                           meta_field("Keywords"))]

    history = []
    for d in re.findall(r"<dd>([\d-]{10}:[^<]*)</dd>", meta_field("History")):
        history.append(collapse(html.unescape(d)))

    received = revised = ""
    for h in history:
        if "received" in h:
            received = h.split(":")[0]
        elif not revised and ("revised" in h or "last of" in h or "approved" in h):
            revised = h.split(":")[0]

    return {
        "id": pid,
        "title": title,
        "authors": authors,
        "category": category,
        "pubinfo": pubinfo,
        "doi": doi,
        "keywords": keywords,
        "abstract": abstract,
        "received": received,
        "revised": revised,
        "history": history,
    }


def scrape_year(year, force=False, limit=0):
    path = os.path.join(DATA_DIR, f"{year}.json")
    cache = {}
    if os.path.exists(path) and not force:
        with open(path) as f:
            cache = {p["id"]: p for p in json.load(f)["papers"]}

    print(f"Listing {year} ...")
    ids = list_year(year)
    todo = [pid for pid, upd in ids.items()
            if force or pid not in cache or cache[pid].get("updated") != upd]
    todo.sort(key=lambda p: int(p.split("/")[1]), reverse=True)
    capped = ""
    if limit and len(todo) > limit:
        todo = todo[:limit]
        capped = f" (capped at {limit} this run; rerun to continue)"
    print(f"{len(ids)} papers in {year}; {len(todo)} to fetch "
          f"({len(ids) - len(todo)} cached){capped}")

    def save(papers):
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(path, "w") as f:
            json.dump({"year": year,
                       "fetched": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                       "count": len(papers),
                       "papers": papers}, f, ensure_ascii=False)

    def ordered():
        return [cache[pid] for pid in sorted(ids, key=lambda p: int(p.split("/")[1]),
                                             reverse=True) if pid in cache]

    for n, pid in enumerate(todo, 1):
        page = get(f"{BASE}/{pid}")
        if page:
            rec = parse_paper(pid, page)
            rec["updated"] = ids[pid]
            cache[pid] = rec
        sys.stderr.write(f"\r  fetched {n}/{len(todo)} ({pid})   ")
        sys.stderr.flush()
        if n % 50 == 0:  # checkpoint, so an interrupted run resumes cheaply
            save(ordered())
    if todo:
        sys.stderr.write("\n")

    papers = ordered()
    save(papers)
    print(f"Wrote {path} ({len(papers)} papers, "
          f"{os.path.getsize(path) / 1e6:.1f} MB)")
    return papers


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("years", nargs="*", default=["2026"])
    ap.add_argument("--force", action="store_true", help="ignore cache")
    ap.add_argument("--delay", type=float, default=1.0,
                    help="seconds between requests (default 1.0)")
    ap.add_argument("--max", type=int, default=0, dest="limit",
                    help="fetch at most this many paper pages per run "
                         "(0 = no limit); the rest are picked up next run")
    a = ap.parse_args()
    STATE["delay"] = a.delay
    for y in (a.years or ["2026"]):
        scrape_year(int(y), a.force, a.limit)
