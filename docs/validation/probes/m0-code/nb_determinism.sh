#!/usr/bin/env bash
# C3.1 / C3.2 probe. Usage: nb_determinism.sh <repo-copy>   (NEVER the real repo: it rewrites the notebook)
# Part 1: sha256 of build_notebooks.render() from separate processes with different
#         PYTHONHASHSEED, cwd, HOME, LANG, TZ. Must be one hash, equal to the file on disk.
# Part 2: byte-level drifts of the notebook file; --check must exit 1 for every one.
set -u
R="$1"; PY="$R/.venv/bin/python"
render_hash() {
  "$PY" -c 'import importlib.util,hashlib,sys
spec=importlib.util.spec_from_file_location("b", sys.argv[1]+"/tools/build_notebooks.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
print(hashlib.sha256(m.render().encode()).hexdigest())' "$R"
}
echo "== part 1: render() across processes"
for seed in 0 1 42 12345 random; do
  ( cd /; PYTHONHASHSEED=$seed HOME=/nonexistent LANG=C LC_ALL=C TZ=Pacific/Kiritimati render_hash ) | sed "s/^/seed=$seed: /"
done
( cd "$R"; PYTHONHASHSEED=7 LANG=de_DE.UTF-8 TZ=UTC render_hash ) | sed "s/^/seed=7 de_DE: /"
echo "on-disk: $(sha256sum "$R/notebooks/00_scaffold_tour.ipynb" | cut -c1-64)"
echo "== part 2: --check on byte drifts"
NB="$R/notebooks/00_scaffold_tour.ipynb"; cp "$NB" "$NB.orig"
chk() { (cd "$R" && "$PY" tools/build_notebooks.py --check >/dev/null 2>&1); echo "$1 -> check rc=$? (bytes $(stat -c %s "$NB"), sha $(sha256sum "$NB" | cut -c1-12))"; cp "$NB.orig" "$NB"; }
chk "unchanged"
printf ' ' >> "$NB"; chk "trailing space"
sed -i 's/$/\r/' "$NB"; chk "CRLF line endings"
"$PY" -c 'import sys;p=sys.argv[1];b=open(p,"rb").read();open(p,"wb").write(b.replace(b"\n",b"\r"))' "$NB"; chk "CR-only line endings"
"$PY" -c 'import sys;p=sys.argv[1];b=open(p,"rb").read();open(p,"wb").write(b"\xef\xbb\xbf"+b)' "$NB"; chk "UTF-8 BOM"
"$PY" -c 'import sys;p=sys.argv[1];b=open(p,"rb").read();open(p,"wb").write(b.rstrip(b"\n"))' "$NB"; chk "missing final newline"
rm "$NB"; chk "file deleted"
rm "$NB.orig"
