#!/usr/bin/env bash
# p12: rebuild events -> snapshots -> iv in a scratch copy of the repository with a scratch
# VOL_DATA_DIR, and compare data/derived byte for byte with the working tree (claim 12).
# Usage: p12_rebuild.sh <repo working tree> <scratch dir> <python>
# Nothing is written to the working tree or to the real data folder: the repository is copied,
# the cache inputs (dolt extracts, universe.parquet, raw/) are copied into <scratch>/vdd.
set -euo pipefail
REPO=$1; SCR=$2; PY=$3
SRC_DATA=${VOL_DATA_DIR:-$HOME/data/vol-projects}/earnings-vol-study
rm -rf "$SCR/rebuild" && mkdir -p "$SCR/rebuild/vdd/earnings-vol-study/cache"
rsync -a --exclude app/node_modules --exclude .venv --exclude graphify-out --exclude .pytest_cache \
      --exclude docs/validation/probes/m2 "$REPO/" "$SCR/rebuild/repo/"
cp -a "$SRC_DATA/cache/dolt" "$SRC_DATA/cache/universe.parquet" "$SCR/rebuild/vdd/earnings-vol-study/cache/"
cp -a "$SRC_DATA/raw" "$SCR/rebuild/vdd/earnings-vol-study/"
cd "$SCR/rebuild/repo"
md5sum data/derived/*.parquet | sort -k2 > "$SCR/rebuild/before.md5"
rm -f data/derived/{events,eps,security,session,ticker_alias,timing_check,session_snapshot,iv_daily,event_iv}.parquet
export VOL_DATA_DIR="$SCR/rebuild/vdd" PYTHONPATH="$SCR/rebuild/repo/src"
"$PY" -m earnings_vol.events.run > "$SCR/rebuild/events.log" 2>&1
"$PY" -m earnings_vol.measures.run --only snapshots > "$SCR/rebuild/snap.log" 2>&1
T0=$SECONDS; "$PY" -m earnings_vol.measures.run --only iv > "$SCR/rebuild/iv.log" 2>&1; echo "iv wall $((SECONDS-T0)) s"
md5sum data/derived/*.parquet | sort -k2 > "$SCR/rebuild/after.md5"
echo "== before vs after (data/derived) =="; diff "$SCR/rebuild/before.md5" "$SCR/rebuild/after.md5" && echo "byte-identical: $(wc -l < "$SCR/rebuild/after.md5") files"
STAGE=$(ls -d "$SCR"/rebuild/vdd/earnings-vol-study/cache/stage/*/)
echo "== stage: $STAGE"; ls -l "$STAGE"chain_expiry.parquet
for t in chain_expiry iv_daily event_iv; do
  a=$(md5sum < "$STAGE$t.parquet"); b=$(md5sum < "$SRC_DATA/cache/stage/$(basename "$STAGE")/$t.parquet")
  echo "stage $t rebuilt vs local stage: $([ "$a" = "$b" ] && echo identical || echo DIFFERENT)"
done
tail -1 "$SCR/rebuild/iv.log"
