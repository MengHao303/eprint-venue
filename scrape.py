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


LISTING_TOTAL = re.compile(r"\((\d+)\s+results\)")


def list_year(year, head_only=False):
    """Return ({paper_id: last_updated}, total) for a year.

    `total` is the count eprint prints above the listing ("All papers in 2026
    (2135 results)"), which is on every page, so `head_only` buys it — along
    with the 100 newest papers — for a single request.
    """
    ids, total, offset = {}, 0, 0
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
        if not total:
            m = LISTING_TOTAL.search(page)
            total = int(m.group(1)) if m else 0
        if head_only:
            break
        sys.stderr.write(f"\r  listing {year}: {len(ids)} papers")
        sys.stderr.flush()
        if f'href="/{year}/?offset={offset + 100}"' not in page:
            break
        offset += 100
    if not head_only:
        sys.stderr.write("\n")
    return ids, total


def list_recent(days):
    """Return {paper_id: last_updated} for every paper eprint added or revised
    in the last `days` days.

    One request to /days/N, instead of the ~20 pages of a year listing. The
    page spans all years, so the caller filters it down to the years it keeps.
    """
    page = get(f"{BASE}/days/{days}")
    ids = dict(LISTING_ENTRY.findall(page)) if page else {}
    print(f"{len(ids)} papers touched in the last {days} days")
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


def scrape_year(year, force=False, limit=0, ids=None):
    """Refresh data/<year>.json.

    `ids` is {paper_id: last_updated} for the year. By default it comes from
    the year listing, which is complete, so papers missing from it are dropped.
    A caller that passes a partial view instead (--recent) only adds and
    updates, and a run that finds nothing new leaves the file untouched.
    """
    path = os.path.join(DATA_DIR, f"{year}.json")
    cache = {}
    if os.path.exists(path) and not force:
        with open(path) as f:
            cache = {p["id"]: p for p in json.load(f)["papers"]}

    partial = ids is not None
    if partial:
        # /days/N reports revisions, but a paper that clears moderation days
        # after it was submitted enters the listing with its old "last updated"
        # date and never shows up there — so read the newest 100 as well, and
        # compare the year's printed total against what we would then hold. A
        # mismatch means something older moved in (or out), and only the full
        # listing can say what.
        head, total = list_year(year, head_only=True)
        ids = {**ids, **head}
        if total and len(set(cache) | set(ids)) != total:
            print(f"{year} lists {total} papers, we would have "
                  f"{len(set(cache) | set(ids))} — reading the full listing")
            partial = False
    if not partial:
        print(f"Listing {year} ...")
        ids, _ = list_year(year)
    todo = [pid for pid, upd in ids.items()
            if force or pid not in cache or cache[pid].get("updated") != upd]
    todo.sort(key=lambda p: int(p.split("/")[1]), reverse=True)
    capped = ""
    if limit and len(todo) > limit:
        todo = todo[:limit]
        capped = f" (capped at {limit} this run; rerun to continue)"
    if partial:
        print(f"{len(ids)} of them in {year}; {len(todo)} to fetch{capped}")
    else:
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
        keys = cache if partial else ids
        return [cache[pid] for pid in sorted(keys, key=lambda p: int(p.split("/")[1]),
                                             reverse=True) if pid in cache]

    if partial and not todo:
        print(f"Nothing new in {year}; left {path} as it is")
        return ordered()

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
    ap.add_argument("--recent", type=int, default=0, metavar="DAYS",
                    help="take the changed papers from /days/DAYS (a single "
                         "request) instead of scanning the year listing; "
                         "data files with nothing new are not rewritten")
    a = ap.parse_args()
    STATE["delay"] = a.delay
    years = a.years or ["2026"]
    recent = list_recent(a.recent) if a.recent else None
    for y in years:
        ids = None
        if recent is not None:
            ids = {pid: upd for pid, upd in recent.items()
                   if pid.startswith(f"{y}/")}
        scrape_year(int(y), a.force, a.limit, ids)
