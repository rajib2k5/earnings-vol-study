#!/usr/bin/env bash
# M0 delta review, claim 8b. Adapted from ../../m0-code/nb_determinism.sh (part 2).
# Usage: nb_drift_delta.sh <repo-COPY>    (NEVER the real repo: it rewrites the notebook)
# Every byte-level drift of the notebook file must make `build_notebooks.py --check`
# exit 1; the unchanged file must exit 0. The original file is restored after each case
# and its sha256 is compared at the end.
set -u
R="$1"; PY="$R/.venv/bin/python"
NB="$R/notebooks/00_scaffold_tour.ipynb"; cp "$NB" "$NB.orig"
H0=$(sha256sum "$NB" | cut -c1-64)
chk() {
  (cd "$R" && "$PY" tools/build_notebooks.py --check >/dev/null 2>&1); rc=$?
  if [ -e "$NB" ]; then info="bytes $(stat -c %s "$NB"), sha $(sha256sum "$NB" | cut -c1-12)"; else info="absent"; fi
  echo "$1 -> check rc=$rc ($info)"; cp "$NB.orig" "$NB"
}
edit() { "$PY" -c "import sys;p=sys.argv[1];b=open(p,'rb').read();$1;open(p,'wb').write(b)" "$NB"; }
chk "unchanged"
printf ' ' >> "$NB"; chk "trailing space"
edit 'b=b.replace(b"\n",b"\r\n")'; chk "CRLF line endings (all lines)"
edit 'b=b.replace(b"\n",b"\r")'; chk "CR-only line endings"
edit 'b=b.replace(b"\n",b"\r\n",1)'; chk "CRLF on the first line only"
edit 'b=b[:-1]+b"\r\n"'; chk "CRLF on the final newline only"
edit 'b=b"\xef\xbb\xbf"+b'; chk "UTF-8 BOM"
edit 'b=b.rstrip(b"\n")'; chk "missing final newline"
edit 'b=b+b"\n"'; chk "extra final newline"
edit 'b=b.replace(b"  ",b"\t",1)'; chk "one indent as tab"
rm "$NB"; chk "file deleted"
echo "== build then check in one process (writer and checker agree on bytes?)"
(cd "$R" && "$PY" tools/build_notebooks.py >/dev/null && "$PY" tools/build_notebooks.py --check >/dev/null 2>&1); echo "build+check rc=$?"
cp "$NB.orig" "$NB"; rm "$NB.orig"
H1=$(sha256sum "$NB" | cut -c1-64)
[ "$H0" = "$H1" ] && echo "restored: sha matches ($H0)" || echo "RESTORE FAILED: $H0 != $H1"
