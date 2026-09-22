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

`.github/workflows/update.yml` keeps the site in step with eprint on two tracks:

- **every hour** (`:17`), a probe: two requests — `/days/2` for what was revised, and
  the first page of the year listing for what was just published — and then only the
  paper pages that actually moved. An hour in which eprint did not move writes no file,
  and the run stops before the rebuild, the commit and the deploy. A quiet hour
  therefore costs two requests, so asking this often is cheap for the archive.
- **every day** at 04:43 UTC (12:43 Singapore time), the full year listing, as a safety
  net: `/days` only reaches back two days, so this is what catches anything the probes
  missed while CI was down. This run always rebuilds and deploys.

That daily slot is not trusted on its own, because GitHub's scheduler drops whole hours
of runs on a free public repository (this one has seen a scheduled run arrive 5½ hours
late, and hourly slots vanish entirely). Two other things therefore reach for the full
listing without it: the probe itself, whenever the year's total says its view is
incomplete, and the age of `data/2026.json` — any run, whichever cron woke it, scans in
full once the file is more than a day old, which also covers a missing file on a fresh
clone.

A run that has work to do (and every push to `main` or manual run) then rebuilds
`site/index.html`, commits the refreshed `data/2026.json` back to the repository, and
deploys `site/` to GitHub Pages. `--max 300` caps the paper pages of a single run, so a
backlog is worked off over several runs instead of hammering the archive.

The committed JSON is what makes this cheap: the expensive first pass over a whole year
is done once, locally, and CI only ever fetches the delta. You can also trigger a run by
hand from the Actions tab (`Run workflow`).

A few things to know:

- eprint offers nothing to push *at* a machine: no webhook. What it offers a reader is
  RSS/Atom, OAI-PMH, and IACR's email alerts (which do reach subscribers on every
  update). An email could be relayed into a `repository_dispatch` to cut the lag from
  under an hour to a few minutes, but that means a mail-to-webhook hop that fails
  silently, so this repository polls `/days` instead.
- GitHub's cron is not punctual, and on a free public repository it is not even
  dependable: runs arrive tens of minutes to hours late, and individual slots are
  dropped. Hourly is what is asked for, not what is delivered — expect the site to
  be a few hours behind at times. Reliable cadence would need an outside trigger
  (a cron service calling `workflow_dispatch`, or a local scheduler), which is
  deliberately not set up here.
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
