"""E5: `items` of an 8-K is one comma-separated string such as '2.02,9.01'.  Exit 0 = survives.
Independent census of every cached 8-K row, then agreement of the code's Item 2.02 selection with the census."""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _lib import *

rows = [r for r in all_8k_rows() if r[2] == "8-K"]
# modern items are N.NN; pre-2004 8-Ks carry bare numbers ("5,7", "12"): both are comma-separated token lists
pat = re.compile(r"\d{1,2}(\.\d{2})?(,\d{1,2}(\.\d{2})?)*")
empty = sum(1 for r in rows if r[3] == "")
bad = [r[3] for r in rows if r[3] != "" and not pat.fullmatch(r[3])]
multi = [r[3] for r in rows if "," in r[3]]
other_sep = [r[3] for r in rows if re.search(r"[;|/ \t]", r[3])]
print(f"8-K rows {len(rows)}; empty items {empty}; items not matching comma-separated item numbers {len(bad)} {bad[:5]}")
print(f"rows with a comma {len(multi)}; rows with '2.02,9.01' exactly {sum(1 for m in multi if m == '2.02,9.01')}; rows with ; | / or space {len(other_sep)}")
census = collections.Counter(r[1] for r in rows if "2.02" in r[3].split(","))
code = collections.Counter()
for sid in SECS:
    pass
n_code = 0
seen = set()
for sid, v in SECS.items():
    doc, pages = edgar.read_cached(v["cik"], RAW, edgar.SINCE)
    for f in edgar.item_202_filings(doc, pages):
        if f["accession"] not in seen:
            seen.add(f["accession"])
print(f"8-K rows carrying item 2.02 (independent split on ','): {len(census)}; selected by edgar.item_202_filings: {len(seen)}; sets equal: {set(census) == seen}")
fails = []
if bad: fails.append("non-conforming items strings")
if other_sep: fails.append("other separators present")
if sum(1 for m in multi if m == "2.02,9.01") < 100: fails.append("no '2.02,9.01' evidence")
if set(census) != seen or len(seen) < 1000: fails.append("code selection != independent census")
print("RESULT:", "SURVIVES" if not fails else "REFUTED: " + "; ".join(fails))
sys.exit(0 if not fails else 1)
