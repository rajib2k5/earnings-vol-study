#!/usr/bin/env bash
# p99: the working tree and the stage cache are as they were before this review, except the two paths it may write.
# Run: bash docs/validation/probes/m4/p99_integrity.sh <scratch snapshot dir with status0.txt sha0.txt cache0.txt>
set -u
S="$1"
cd /home/rajib2k5/dev/earnings-vol-study
git status --porcelain > "$S/status1.txt"
echo "git status lines changed since the start (only docs/validation/m4-ledger.md and probes/m4/ allowed):"
diff "$S/status0.txt" "$S/status1.txt" | grep '^[<>]' || echo "  (none)"
git ls-files -co --exclude-standard -z | xargs -0 sha256sum 2>/dev/null \
  | grep -v -e 'docs/validation/m4-ledger.md' -e 'docs/validation/probes/m4/' > "$S/sha1.txt"
echo "tracked + untracked file hashes vs start (m4 paths excluded):"
diff <(grep -v -e 'docs/validation/m4-ledger.md' -e 'docs/validation/probes/m4/' "$S/sha0.txt" | sort -k2) <(sort -k2 "$S/sha1.txt") \
  && echo "  identical ($(wc -l < "$S/sha1.txt") files)"
echo "stage cache hashes vs start:"
sha256sum -c --quiet "$S/cache0.txt" && echo "  identical ($(wc -l < "$S/cache0.txt") files)"
echo "files in the cache now vs start:"
diff <(awk '{print $2}' "$S/cache0.txt" | sort) <(find ~/data/vol-projects/earnings-vol-study/cache -type f | sort) && echo "  same set"
