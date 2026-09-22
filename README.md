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
| `classify.py` | Turns the free-text publication info into a status + venue |
| `venues.py` | Folds venue spellings onto one name (`CCS`, `ACM-CCS`, `ACM SIGSAC Conference on…` → `ACM CCS`) |
| `build.py` | Renders `data/*.json` + `template.html` into `site/index.html` |
| `template.html` | The page: layout, styles, client-side filtering |
| `update.sh` | Incremental refresh + rebuild in one command |
| `.github/workflows/update.yml` | Hourly refresh + deploy to GitHub Pages |

## Usage

```sh
./update.sh              # refresh 2026 and rebuild the site
./update.sh 2024 2025 2026   # several years in one page
RECENT=2 ./update.sh     # only what eprint touched in the last 2 days (1 request)
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

`--recent N` replaces step 1 with a single request to `eprint.iacr.org/days/N`, the
archive's own "papers updated in last N days" listing, which gives the same ids and
dates for everything that moved — across all years, so it is filtered to the years kept
in `data/`. It is a partial view of the year, so such a run only adds and updates
papers, never drops them, and a run that finds nothing new does not rewrite the file at
all. That last part is what lets CI tell an empty hour from a busy one.

## Automatic updates

`.github/workflows/update.yml` keeps the site in step with eprint on two tracks:

- **every hour** (`:17`), a probe: one request to `/days/2` names every paper the archive
  added or revised, and only those paper pages are fetched. An hour in which eprint did
  not move writes no file, and the run then stops before the rebuild, the commit and the
  deploy — so the site is normally at most an hour behind the archive, for about
  24 requests a day.
- **every day** at 04:43 UTC (12:43 Singapore time), the full year listing, as a safety
  net: `/days` only reaches back two days, so this is what catches anything the probes
  missed while CI was down. This run always rebuilds and deploys.

A run that has work to do (and every push to `main` or manual run) then rebuilds
`site/index.html`, commits the refreshed `data/2026.json` back to the repository, and
deploys `site/` to GitHub Pages. `--max 300` caps the paper pages of a single run, so a
backlog is worked off over several runs instead of hammering the archive.

The committed JSON is what makes this cheap: the expensive first pass over a whole year
is done once, locally, and CI only ever fetches the delta. You can also trigger a run by
hand from the Actions tab (`Run workflow`).

A few things to know:

- eprint offers no push notification — no webhook, and its "Subscribe" link is IACR
  *news* by email (currently disabled), not per-paper updates. Hourly polling of `/days`
  is as close to live as the archive allows; RSS/Atom and OAI-PMH are the other read-only
  options.
- GitHub's cron is not punctual: scheduled runs are commonly delayed by minutes to tens
  of minutes under load, and can be skipped. "Within the hour" is the promise, not "on
  the minute".
- GitHub disables scheduled workflows in repositories with no activity for 60 days. The
  data commits normally count as activity, but if the schedule ever goes quiet, re-enable
  it from the Actions tab.
- CI identifies itself through `EPRINT_UA`, which names this repository, so the archive's
  operators can see who is fetching and get in touch. If eprint.iacr.org ever rate-limits
  or blocks CI, the workflow fails loudly and the deployed site simply keeps the last
  good snapshot.

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
