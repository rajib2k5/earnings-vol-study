#!/bin/bash
# usage: run_probe.sh <probe.py> <pycache-prefix-dir>
# Sandbox: clean env, no network (unshare --net), TZ=UTC, bytecode off and a fresh pycache prefix (stale-pyc trap), 300 s limit.
P="$1"; PFX="$2"; REPO=/home/rajib2k5/dev/earnings-vol-study
SCR=/tmp/claude-1000/-home-rajib2k5-dev/9fcceee1-9f95-4cb4-9f87-030ec5521894/scratchpad
mkdir -p "$PFX"
cd "$SCR" || exit 99
exec env -i PATH=/usr/bin:/bin HOME="$SCR" TMPDIR="$SCR" TZ=UTC LC_ALL=C PYTHONDONTWRITEBYTECODE=1 \
  timeout --kill-after=5 300 unshare --user --map-root-user --net -- \
  "$REPO/.venv/bin/python" -B -I -X pycache_prefix="$PFX" "$REPO/docs/validation/edgar-egv/probes/$P"
