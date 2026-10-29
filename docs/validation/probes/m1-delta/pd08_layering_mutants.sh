#!/usr/bin/env bash
# pd08 (claims 5a, 5b): I/O forms appended to events/eps.py in a SCRATCH COPY of the
# tree; tests/test_layering.py is run after each. "SURVIVED" = the test still passes
# with I/O in a middle module. The copy is restored from a pristine eps.py each time.
#
# Usage: pd08_layering_mutants.sh <scratch_tree> <python>
set -u
T="$1"; PY="$2"
F="$T/src/earnings_vol/events/eps.py"
cp "$F" "$F.orig"
run() {
  local name="$1" code="$2"
  cp "$F.orig" "$F"
  printf '\n%s\n' "$code" >> "$F"
  out=$(cd "$T" && "$PY" -m pytest -q -p no:cacheprovider tests/test_layering.py 2>&1 | tail -1)
  if echo "$out" | grep -q failed; then v=KILLED; else v=SURVIVED; fi
  printf '%-9s %-46s | %s\n' "$v" "$name" "$out"
}
run "control: open(__file__)"            'x = open(__file__).read()'
run "control: import urllib.request"     'import urllib.request'
run "relative: from .. import store"     'from .. import store as _s
def _w(df, t, p): return _s.write_table(df, t, p, params_hash="x", dolt_commits={})'
run "relative: from ..ingest import dolt" 'from ..ingest import dolt as _d
def _q(): return _d.query(None, "SELECT 1")'
run "left import: ingest.prices.load"    'from earnings_vol.ingest import prices as _p
def _l(): return _p.load("SPY", None)'
run "left import: ingest.dolt.query"     'from earnings_vol.ingest import dolt as _d
def _q(): return _d.query(None, "SELECT 1")'
run "np.load"                            'def _l(): return np.load("x.npy")'
run "np.savetxt"                         'def _l(a): return np.savetxt("x.txt", a)'
run "pd.read_pickle"                     'def _l(): return pd.read_pickle("x.pkl")'
run "df.to_pickle"                       'def _l(df): return df.to_pickle("x.pkl")'
run "pd.read_html (network)"             'def _l(): return pd.read_html("https://example.com")'
run "pd.read_feather"                    'def _l(): return pd.read_feather("x.feather")'
run "importlib.import_module(os)"        'import importlib
_os = importlib.import_module("os")'
run "__import__(socket)"                 '_sock = __import__("socket")'
run "io.FileIO"                          'import io
def _l(): return io.FileIO("x")'
run "getattr(builtins, open)"            'import builtins
def _l(): return getattr(builtins, "op" + "en")("x")'
run "exec(import os)"                    'exec("import os")'
cp "$F.orig" "$F"; rm "$F.orig"
# 5b: vacuity — hide the middle packages from the walk.
mv "$T/src/earnings_vol/events" "$T/src/earnings_vol_events_hidden"
out=$(cd "$T" && "$PY" -m pytest -q -p no:cacheprovider tests/test_layering.py 2>&1 | tail -1)
echo "5b vacuity (events/ moved out of the package): $out"
mv "$T/src/earnings_vol_events_hidden" "$T/src/earnings_vol/events"
out=$(cd "$T" && "$PY" -m pytest -q -p no:cacheprovider tests/test_layering.py 2>&1 | tail -1)
echo "restored copy: $out"
