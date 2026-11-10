# SEC EDGAR timing: EGV verdict

`route: rows 2, 3, 5, 6 | primary: dual-channel EGV Mode 1 on E1–E8 (row 3), gates + hand mutants (row 2) | complement: verifier + adversarial on the look-up counts and the re-run results (rows 5–6, separate report) | not-run: EGV on the counts (Channel A N/A for a value) | stop: met for E1, E2, E6, E7, E8; not met for E3, E4, E5 (UNRESOLVED by construction)`

`mode: Mode 1, dual subagent.` Channel A (documents only): `channel-a.md`. Channel B (cached data and probes only, no network): `channel-b.md`, `probes/`. The ledger (`claims-ledger.md`, SHA-256 `df591fce…e790`) was frozen before either channel ran and was not edited.

| ID | Claim (short) | Mat | A | B | Gate |
|---|---|---|---|---|---|
| E1 | the submissions JSON has the four parallel arrays | mat | UNVERIFIABLE: the URL and a "columnar data array" are documented, the field names are not | CONFIRMED: 51 files, 120,329 `recent` rows; the URL half rests on file names and internal `cik` only | **split.** E1a, the URL (A CONFIRMED; B indirect). E1b, the field names (B CONFIRMED; A N/A, docs silent). **ACCEPTED**, the field names on one channel |
| E2 | older filings sit in `filings.files` pages with the same arrays | mat | UNVERIFIABLE in part: the list of extra files with date ranges is documented, the URL and contents are not | CONFIRMED: 135 cached pages, same keys as `recent`; 232 of 234 events before the `recent` block are found only through them | **split.** E2a, the list exists (A and B CONFIRMED). E2b, the URL and same arrays (B CONFIRMED; A N/A). **ACCEPTED** |
| E3 | `acceptanceDateTime` is a UTC instant | mat | UNVERIFIABLE: SEC states no zone for this field. Its one statement on acceptance times (the submission header) says "EST" | CONFIRMED: as UTC, 20 of 20 press releases agree, within about ±18 min where a time is stamped; as New York time, 9 of 20 and about 4 h off. `filingDate` 6,934 of 6,935 before the cut-off | **UNRESOLVED by construction.** No document states the zone, so only one evidence source exists. The empirical evidence is strong and from four independent references. Escalated to the owner. (Corrected: an earlier version said "four independent references"; Channel B used three — press releases, filing dates, calendar labels. The daylight-saving test is the builder's, `edgar-ledger.md` §2 row F, not a channel result) |
| E4 | the acceptance time is kept for filings after 17:30 | mat | UNVERIFIABLE: 17 CFR 232.13 documents the 17:30 cut-off and the next-day filing date, not this field | CONFIRMED with exceptions: 223 of 248 after-cut-off 8-Ks carry a later `filingDate`; 25 do not, unexplained | **UNRESOLVED by construction.** The code reads the acceptance time, not the filing date, so the 25 exceptions do not change a label |
| E5 | `items` is one comma-separated string such as `2.02,9.01` | mat | UNVERIFIABLE: no page documents the format | CONFIRMED: 7,183 8-K rows, no other separator; the code's Item 2.02 selection equals an independent count (2,312) | **UNRESOLVED by construction.** Low risk: the format is uniform in every cached row |
| E6 | Item 2.02 furnishes the earnings release | mat | CONFIRMED: Form 8-K (SEC 873, 02-25), Item 2.02 and General Instruction B.2 | CONFIRMED: 1,311 of 1,353 calendar events have one within ±1 day, against 0 of 1,353 at +45 days | **ACCEPTED** |
| E7 | EDGAR is closed on Columbus Day and Veterans Day | mat | CONFIRMED for 2026 (SEC EDGAR calendar) | CONFIRMED for 2020–2025: 0 acceptances on each such session, against a median of 180 | **ACCEPTED** (A covers 2026, B covers 2020–2025) |
| E8 | 10 requests a second; a contact in the User-Agent | mat | CONFIRMED for 10 a second and for declaring a User-Agent | client half CONFIRMED (at most 10 in any 1 s window; a User-Agent on every request); policy half UNVERIFIABLE (no network) | **split.** E8a, SEC's policy (A only). E8b, our client (B only). **ACCEPTED** |

Every load-bearing Channel B probe failed on its mutant (falsifier_rc = 1 for all ten), and the restored file's SHA-256
matched the original each time.

**For the owner:** E3 decides every EDGAR label. If the field were New York time, every after-close 8-K would read as
filed during the session. SEC documents no zone for it, so the UTC reading rests on the data alone. Channel B's three comparisons support it: the 20 hand-timed press
releases, the filing dates and the calendar labels. The builder's daylight-saving test (not a channel result) points
the same way. Channel A found no document that contradicts it; SEC's only statement on acceptance times, for the
submission header, says "EST".
