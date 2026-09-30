# ePrint Venue View

<https://menghao303.github.io/eprint-venue/>

The [Cryptology ePrint Archive](https://eprint.iacr.org/) year listing shows the title,
authors, category and abstract of every paper — but not the **Publication info** field,
which says whether a paper is still a preprint or has been accepted at CRYPTO, TCHES,
CCS, a journal, and so on. You only see it after opening each paper.

This project mirrors that field onto the listing: one page with every paper of a year,
its publication info in the row, and filters for venue, publication status and category.

## Files

| File | Purpose |
| --- | --- |
| `scrape.py` | Fetches paper metadata from eprint.iacr.org into `data/<year>.json` |
| `data/feed.json` | The RSS feed as the last `--feed` run saw it, plus papers still to fetch |
| `classify.py` | Turns the free-text publication info into a status + venue |
| `venues.py` | Folds venue spellings onto one name (`CCS`, `ACM-CCS`, `ACM SIGSAC Conference on…` → `ACM CCS`) |
| `build.py` | Renders `data/*.json` + `template.html` into `site/index.html` |
| `template.html` | The page: layout, styles, client-side filtering |
| `update.sh` | Incremental refresh + rebuild in one command |
| `.github/workflows/update.yml` | Daily refresh + deploy to GitHub Pages (paused, see below) |

## Usage

```sh
./update.sh              # refresh 2026 and rebuild the site
./update.sh 2024 2025 2026   # several years in one page
RECENT=2 ./update.sh     # only what eprint touched in the last 2 days (1 request)
FEED=1 ./update.sh       # RSS + JSON API, as CI does (needs EPRINT_API_KEY)
FORCE=1 ./update.sh      # ignore the cache and re-fetch everything
open site/index.html     # self-contained, no server needed
```

`site/index.html` embeds its data, so it works offline and can be copied anywhere.

## How updating works

`scrape.py` is incremental. Each run:

1. reads the year listing pages (100 papers per request) to get every paper id and its
   `Last updated` date;
2. compares those dates against `data/<year>.json`;
3. fetches the paper page **only** for papers that are new or whose date has moved.

When a paper is accepted somewhere, the authors upload a revision, which moves the
`Last updated` date — so the changed publication info is picked up on the next run.
A routine refresh is therefore ~20 listing requests plus a handful of paper pages.
Run `FORCE=1 ./update.sh` occasionally (say monthly) to catch metadata edits that did
not bump the date.

`--recent N` replaces step 1 with two requests. The first is `eprint.iacr.org/days/N`,
the archive's own "papers updated in last N days" listing, which gives the same ids and
dates for everything revised — across all years, so it is filtered to the years kept in
`data/`.

That listing alone is not enough: a paper that clears moderation days after it was
submitted enters the year listing carrying its *old* `Last updated` date, so it never
appears under `/days` at all. (Seen in practice: 40 papers published in one morning,
dated three to four days earlier, none of them in `/days/2`.) The second request is
therefore the first page of the year listing, which carries the 100 newest papers and,
in its header, the year's total — `All papers in 2026 (2135 results)`. When that total
does not match what the run would end up holding, something older moved in or out, and
the run reads the full listing after all.

So a `--recent` run is a partial view that knows when it is incomplete: it only adds and
updates papers, it upgrades itself to a full scan when the count says it must, and when
nothing moved it does not rewrite the file at all. That last part is what lets CI tell
an empty hour from a busy one.

## Automatic updates

The archive's maintainer (Kevin McCurley) asked us, on 2026-09-30, to keep up through
the RSS feed and eprint's JSON API instead of scraping HTML, and gave us an API key.
That is `scrape.py --feed`, which CI runs **once a day** at 00:07 UTC (08:07 Singapore):

1. read `https://eprint.iacr.org/rss/rss.xml`, the last 100 papers eprint added or
   revised (all years, newest change first; about six days' worth);
2. compare it with the feed the previous run saw (`data/feed.json`). A revision lifts a
   paper to the top and untouched papers only slide down, so the papers above the
   untouched tail are exactly the ones that moved — including one revised twice;
3. fetch each moved paper of a kept year from `https://eprint.iacr.org/api/1.0/<id>`.

The API returns the publication type as structured fields (`pubtype`: `PREPRINT`,
`OTHER`, `CRYPTO`, `TCHES`, …; `revisiontype`: `SAME`/`MINOR`/`MAJOR`; a free-text
`note`; the venue `year`; a `DOI`). `scrape.py` spells them the way the paper page does
(`A major revision of an IACR publication in CRYPTO 2026`), so `classify.py` and the page
treat both sources alike; the raw fields are kept in each record's `pubtype`.

A few things to know:

- **Rate limit: 100 API requests a day.** A normal day is 10–20. A run stops at
  `--max 80` or at the first `429`, and leaves what it did not fetch in
  `data/feed.json` for the next run.
- **The key is a secret.** CI reads it from the repository secret `EPRINT_API_KEY`;
  locally, export it in your shell. Never commit it.
- If more than 100 papers changed between two runs (GitHub skipped several days), the
  feed no longer reaches back far enough and the run says so. A full listing scan run
  locally (`./update.sh`) catches up; that is the HTML path, so keep it rare.
- A day in which nothing moved writes no file, and the run stops before the rebuild,
  commit and deploy.
- GitHub's cron runs late and occasionally skips a day; the feed covers about six days,
  so a skipped day is caught up by the next run. GitHub also disables schedules in
  repositories with no activity for 60 days — re-enable from the Actions tab if needed.
- Requests carry `EPRINT_UA`, which points to this site, as the maintainer asked.

The HTML path (`./update.sh`, `RECENT=N`) is still there for a first pass over a new
year. Between 2026-09-27 and 2026-09-30 the schedule was off, after eprint's Cloudflare
answered the old HTML scraper with a 403.

## Fetching politely

The archive sits behind Cloudflare rate limiting. The scraper therefore:

- sends one request at a time with a delay (`--delay`, default 1s);
- backs off for 60s and widens the delay whenever the server answers `429`;
- checkpoints to `data/<year>.json` every 50 papers, so an interrupted run resumes
  where it stopped;
- fetches metadata pages only — never PDFs.

The first full year takes a while (a couple of thousand pages); every run after that is
incremental.

## Data

Metadata belongs to the IACR and the papers' authors, most of it under CC-BY. Every row
links back to the paper page and PDF on eprint.iacr.org.
