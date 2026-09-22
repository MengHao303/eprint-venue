#!/bin/sh
# Incremental refresh: re-fetch only new or changed papers, then rebuild the site.
#   ./update.sh            # refresh 2026
#   ./update.sh 2025 2026  # refresh several years
#   RECENT=2 ./update.sh   # only what eprint touched in the last 2 days (1 request)
#   FORCE=1 ./update.sh    # ignore the cache and re-fetch everything
set -e
cd "$(dirname "$0")"
YEARS="${*:-2026}"
python3 scrape.py $YEARS ${FORCE:+--force} ${RECENT:+--recent $RECENT}
python3 build.py
echo "Open site/index.html"
