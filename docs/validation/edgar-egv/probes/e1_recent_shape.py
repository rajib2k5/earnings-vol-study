"""E1: submissions JSON has filings.recent with parallel arrays form, items, accessionNumber, acceptanceDateTime.
Exit 0 = survives.  Raw check on every CIK##########.json in the cache + a read through the code (merge_filings).
Scope: the cache cannot show the HTTP URL itself (no network); indirect evidence only: the file name, the `cik`
field inside and the code-written serialisation (json.dumps(sort_keys=True)) all agree."""
import sys, os, glob, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _lib import *

need = ("form", "items", "accessionNumber", "acceptanceDateTime")
files = sorted(p for p in glob.glob(str(EDG / "CIK*.json")) if re.fullmatch(r"CIK\d{10}\.json", os.path.basename(p)))
fails = []
tot = 0
for p in files:
    txt = open(p, encoding="utf-8").read()
    d = json.loads(txt)
    rec = d["filings"]["recent"]
    miss = [k for k in need if k not in rec or not isinstance(rec[k], list)]
    lens = {len(rec[k]) for k in need if k in rec}
    name_cik = os.path.basename(p)[3:13]
    if miss or len(lens) != 1 or 0 in lens:
        fails.append((os.path.basename(p), "missing/ragged", miss, sorted(lens)))
    if str(d.get("cik", "")).zfill(10) != name_cik:
        fails.append((os.path.basename(p), "cik field != file name", d.get("cik")))
    if json.dumps(d, sort_keys=True) != txt:
        fails.append((os.path.basename(p), "not the code's serialisation"))
    tot += min(lens) if lens else 0
print(f"{len(files)} CIK main files; total recent rows {tot}")
print("first file keys of recent:", sorted(json.loads(open(files[0]).read())["filings"]["recent"])[:6], "...")
# read through the code: every CIK, every row has a parsable acceptanceDateTime and a str form/items
try:
    rows = all_8k_rows()
    bad = [r for r in rows if not isinstance(r[2], str) or not isinstance(r[3], str)]
    for r in rows:
        if r[2] == "8-K":
            edgar.parse_acceptance(r[4])
except Exception as ex:  # a field the code expects but the files lack is a refutation, not a probe crash
    print("code read failed:", repr(ex)); rows, bad = [], []; fails.append(("code read failed", repr(ex)))
print(f"rows read via edgar.merge_filings: {len(rows)}; non-str form/items: {len(bad)}")
if bad: fails.append(("code read gives non-str form/items", len(bad)))
if len(files) < 40 or len(rows) < 100000: fails.append(("coverage too small", len(files), len(rows)))
for f in fails: print("FAIL", f)
print("RESULT:", "SURVIVES" if not fails else "REFUTED")
sys.exit(0 if not fails else 1)
