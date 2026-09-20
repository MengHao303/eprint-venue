#!/usr/bin/env python3
"""Build the static site from the scraped JSON in data/."""
import base64
import datetime
import json
import os
import sys
import time

import venues
from classify import classify, STATUS_LABEL, STATUS_ORDER

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "site", "index.html")
TEMPLATE = os.path.join(ROOT, "template.html")
ASSETS = os.path.join(ROOT, "assets")

# eprint's own category codes, which drive its badge colours
CAT_CODES = {
    "Applications": "APPLICATIONS",
    "Attacks and cryptanalysis": "ATTACKS",
    "Cryptographic protocols": "PROTOCOLS",
    "Foundations": "FOUNDATIONS",
    "Implementation": "IMPLEMENTATION",
    "Public-key cryptography": "PUBLICKEY",
    "Secret-key cryptography": "SECRETKEY",
}


def data_uri(name, mime):
    with open(os.path.join(ASSETS, name), "rb") as f:
        return "data:%s;base64,%s" % (mime, base64.b64encode(f.read()).decode())


def stylesheet():
    """eprint's stylesheets, inlined, with its background image embedded."""
    with open(os.path.join(ASSETS, "bootstrap.min.css")) as f:
        boot = f.read()
    with open(os.path.join(ASSETS, "eprint.css")) as f:
        eprint = f.read()
    eprint = eprint.replace("url(/img/shades6.svg)",
                            "url(%s)" % data_uri("shades6.svg", "image/svg+xml"))
    return boot + "\n" + eprint


def load(years=None):
    files = sorted(f for f in os.listdir(DATA_DIR) if f.endswith(".json"))
    if years:
        files = [f for f in files if f[:-5] in years]
    papers, fetched = [], ""
    for fn in files:
        with open(os.path.join(DATA_DIR, fn)) as f:
            blob = json.load(f)
        fetched = max(fetched, blob.get("fetched", ""))
        papers.extend(blob["papers"])
    return papers, fetched


def pack(papers):
    cats, venue_names = [], []

    def idx(lst, v):
        try:
            return lst.index(v)
        except ValueError:
            lst.append(v)
            return len(lst) - 1

    rows = []
    for p in papers:
        c = classify(p.get("pubinfo", ""))
        rows.append([
            p["id"],
            p.get("title", ""),
            ", ".join(p.get("authors", [])),
            idx(cats, p.get("category", "")),
            p.get("pubinfo", ""),
            STATUS_ORDER.index(c["status"]),
            idx(venue_names, c["venue_key"]),
            c["revision"],
            p.get("doi", ""),
            "; ".join(p.get("keywords", [])),
            p.get("abstract", ""),
            p.get("received", ""),
            p.get("revised", "") or p.get("updated", ""),
        ])
    counts = {}
    for row in rows:
        counts[venue_names[row[6]]] = counts.get(venue_names[row[6]], 0) + 1
    offered = sorted(
        ((v, n) for v, n in counts.items()
         if v and v not in ("\u2014", "Unspecified")
         and (not venues.ALLOWED or v in venues.ALLOWED)
         and v not in venues.HIDDEN and n >= venues.MIN_PAPERS),
        key=lambda vn: (-vn[1], vn[0]))
    return {"cats": cats, "catCodes": [CAT_CODES.get(c, "uncategorized") for c in cats],
            "venues": venue_names, "filterVenues": offered,
            "statuses": [STATUS_LABEL[s] for s in STATUS_ORDER],
            "rows": rows}


SGT = datetime.timezone(datetime.timedelta(hours=8))  # Singapore, no DST


def singapore_time(stamp):
    """'2026-09-20T07:23:56Z' -> '2026-09-20 15:23 (Singapore)'."""
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"):
        try:
            utc = datetime.datetime.strptime(stamp, fmt).replace(
                tzinfo=datetime.timezone.utc)
        except ValueError:
            continue
        return utc.astimezone(SGT).strftime("%Y-%m-%d %H:%M (Singapore)")
    return stamp


def main(argv):
    years = [a for a in argv if a.isdigit()]
    papers, fetched = load(years or None)
    if not papers:
        sys.exit("No data in data/ — run scrape.py first.")
    data = pack(papers)
    with open(TEMPLATE) as f:
        html = f.read()
    yrs = sorted({p["id"].split("/")[0] for p in papers})
    span = yrs[0] if len(yrs) == 1 else f"{yrs[0]}–{yrs[-1]}"
    data["year"] = span
    html = (html
            .replace("__CSS__", stylesheet())
            .replace("__LOGO__", data_uri("iacrlogo_small.png", "image/png"))
            .replace("__SEARCHICON__", data_uri("search.svg", "image/svg+xml"))
            .replace("__ARROWUP__", data_uri("arrow-up-circle-outline.svg", "image/svg+xml"))
            .replace("__DATA__", json.dumps(data, ensure_ascii=False,
                                            separators=(",", ":")))
            .replace("__YEAR__", span)
            .replace("__YEARS__", span)
            .replace("__COUNT__", str(len(papers)))
            .replace("__FETCHED__",
                     singapore_time(fetched) if fetched
                     else datetime.datetime.now(SGT).strftime(
                         "%Y-%m-%d %H:%M (Singapore)")))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        f.write(html)
    print(f"Wrote {OUT} ({os.path.getsize(OUT) / 1e6:.1f} MB, "
          f"{len(papers)} papers)")


if __name__ == "__main__":
    main(sys.argv[1:])
