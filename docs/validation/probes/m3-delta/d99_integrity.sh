#!/usr/bin/env bash
# d99: the working tree and the stage cache are as they were before the delta review, except for the two
# paths this review may write. Compares against snapshots taken at the start (scratch).
# Run: bash docs/validation/probes/m3-delta/d99_integrity.sh <scratch snapshot dir>
set -u
S="$1"
cd /home/rajib2k5/dev/earnings-vol-study
git status --porcelain > "$S/status_after.txt"
echo "git status lines added since the start (only m3-delta paths allowed):"
diff "$S/status_before.txt" "$S/status_after.txt" | grep '^[<>]' || echo "  (none)"
git ls-files -co --exclude-standard -z | xargs -0 sha256sum 2>/dev/null \
  | grep -v -e 'docs/validation/m3-delta-ledger.md' -e 'docs/validation/probes/m3-delta/' > "$S/hashes_after.txt"
echo "tracked + untracked file hashes vs start (m3-delta paths excluded):"
diff <(sort -k2 "$S/hashes_before.txt") <(sort -k2 "$S/hashes_after.txt") && echo "  identical ($(wc -l < "$S/hashes_after.txt") files)"
echo "stage cache hashes vs start:"
sha256sum -c --quiet "$S/stage_before.txt" && echo "  identical ($(wc -l < "$S/stage_before.txt") files)"
