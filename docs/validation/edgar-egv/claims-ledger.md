# SEC EDGAR timing: EGV claims ledger (pre-registered)

Frozen on 2026-11-09, before either channel ran. Neither channel may add, drop or reword a claim. Environment: the
same pin as `../vx-egv/env-pin.txt`. Every material claim starts **REJECTED**.

Scope: the claims about the EDGAR submissions API that the timing labels rest on. The counts of labels resolved and
changed are numbers, not EGV claims: they go to the verifier and the adversarial re-derivation (router rows 5 and 6).

| ID | Cat | Mat | Claim |
|---|---|---|---|
| E1 | API | material | `https://data.sec.gov/submissions/CIK##########.json` returns `filings.recent` with parallel arrays `form`, `items`, `accessionNumber` and `acceptanceDateTime`. |
| E2 | API | material | Filings older than those in `filings.recent` are listed in `filings.files`, each served at `https://data.sec.gov/submissions/<name>` with the same arrays. |
| E3 | Semantic | material | Each `acceptanceDateTime` value is a UTC instant, as its trailing `Z` says. |
| E4 | Semantic | material | `acceptanceDateTime` holds the time EDGAR accepted the filing, also when the filing is accepted after 17:30 Eastern and gets the next business day as its filing date. |
| E5 | Semantic | material | `items` lists a Form 8-K's item numbers as one comma-separated string, such as `2.02,9.01`. |
| E6 | Semantic | material | Item 2.02 of Form 8-K, "Results of Operations and Financial Condition", is the item under which a company furnishes its earnings release. |
| E7 | Semantic | material | EDGAR does not accept filings on Columbus Day and Veterans Day, two federal holidays on which NYSE is open. |
| E8 | Environmental | material | SEC's fair-access policy allows at most 10 requests per second and requires a User-Agent that declares a contact. |

Code under validation: `src/earnings_vol/ingest/edgar.py` and the timing wiring the builder adds (path given to each
channel when the build ends).
