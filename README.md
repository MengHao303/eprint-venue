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
| `.github/workflows/update.yml` | Daily refresh + deploy to GitHub Pages |

## Usage

```sh
./update.sh              # refresh 2026 and rebuild the site
./update.sh 2024 2025 2026   # several years in one page
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

## Automatic updates

`.github/workflows/update.yml` runs every day at 04:43 UTC (12:43 Singapore time),
and on every push to `main`:

1. reads the year listing and re-fetches only the papers whose `Last updated` moved
   (`--max 300` caps one run, so a backlog is worked off over several days instead of
   hammering the archive);
2. rebuilds `site/index.html`;
3. commits the refreshed `data/2026.json` back to the repository;
4. deploys `site/` to GitHub Pages.

The committed JSON is what makes this cheap: the expensive first pass over a whole year
is done once, locally, and CI only ever fetches the delta. You can also trigger a run by
hand from the Actions tab (`Run workflow`).

Two things to know:

- GitHub disables scheduled workflows in repositories with no activity for 60 days. The
  daily data commit normally counts as activity, but if the schedule ever goes quiet,
  re-enable it from the Actions tab.
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
