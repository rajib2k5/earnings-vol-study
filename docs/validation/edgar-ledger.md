# SEC EDGAR timing: fetch, time zone, wiring, outcomes, and the re-run

- **Date:** 2026-11-09. **Scope:** ADR 0002 §3, source 1 (the Item 2.02 8-K acceptance time), for the 453 events that
  the default rule still needed looked up after the first 20 press releases (milestone 1). Phase 1 (§1–§9) stopped
  before the downstream pipeline was re-run. Phase 2 (§10, the same day) switched EDGAR on, re-ran the pipeline and
  updated the docs.
- **What changed:** `src/earnings_vol/ingest/edgar.py` (extra pages, cache-only reader, strict UTC parser, EDGAR's
  closed days, `several_8k`, predecessor CIKs, the fetch command), `src/earnings_vol/events/timing.py`
  (`resolve_edgar`), `src/earnings_vol/events/events.py` (`build_events(..., edgar=)`),
  `src/earnings_vol/events/run.py` (a second pass when `params.timing.edgar` is true, the EDGAR report),
  `data/manual/edgar_predecessor_ciks.csv` (new), `tests/test_edgar_timing.py` (new), `tests/test_ingest_sources.py`
  (fixture gains `filingDate`; the holiday test follows the measured closures).
- **Not changed in phase 1, on purpose:** `params.yaml`. `timing.edgar` was absent, so it read as false and the params
  hash and the stage directory stayed where they were while other work read them. Phase 2 set `timing.edgar: true`
  (§10).
- **Isolation.** The contact string for the User-Agent was set only inline in the commands that made requests to
  `data.sec.gov`. It is in no file, log, test or output: the cache files and `fetch_log.json` hold EDGAR's JSON and
  counts only, and a search for the contact address over the repository and the data folder found 0 hits (§8). The
  events layer reads EDGAR from the local cache through `read_cached`, which makes no request and needs no User-Agent.
  Mutants ran on a temporary copy of the tree (`p04`). Phase-1 tables were written only to
  `$VOL_DATA_DIR/earnings-vol-study/cache/edgar-phase1/`.
- **Probes:** [`probes/edgar/`](probes/edgar/); verbatim outputs in `probes/edgar/out/`. `p01` time zone, `p02` phase-1
  outcomes, `p03` fetch and coverage, `p04` mutants. Every probe reads `raw/edgar/` only and prints counts, dates and
  EDGAR times, never a price value.
- **Not claimed here.** These are measurements by the builder. No independent channel has re-run them; the
  pre-registered claims in [`edgar-egv/claims-ledger.md`](edgar-egv/claims-ledger.md) are for that.

## 1. What was fetched

| | |
|---|---|
| Requests | **186** to `data.sec.gov/submissions/`: 1 trial (AAPL), 183 in the fetch run (2026-11-09 19:16:22Z to 19:17:16Z, 3.4 a second; the client sleeps 0.1 s after each), 2 for XOM's predecessor CIK (19:17:57Z, 19:17:58Z). A second run of `python -m earnings_vol.ingest.edgar` made 0 (all cached). |
| Files | **186** JSON files in `raw/edgar/`: 51 submissions files (50 securities and 1 predecessor CIK) and 135 extra pages, **72,838,276 bytes**, plus `fetch_log.json` |
| Filings read | 390,105 (51 CIKs, merged, each accession once); 2,312 of them are 8-Ks with Item 2.02 |
| Reach | extra pages are read back to 2020-01-01 (`edgar.SINCE`), with a 7-day margin (below) |

Per security (`p03`; pages used / listed; first and last filing date of the merged filings; Item 2.02 8-Ks from 2020):

| Security | Pages | Bytes | First filing | Last filing | 2.02 since 2020 | First 2.02 from 2020 |
|---|---|---:|---|---|---:|---|
| AAPL | 0/1 | 180,759 | 2015-10-05 | 2026-11-06 | 28 | 2020-01-28 |
| ABBV | 0/1 | 173,247 | 2017-05-09 | 2026-11-03 | 49 | 2020-02-07 |
| AMAT | 0/1 | 175,918 | 2013-03-07 | 2026-10-26 | 26 | 2020-02-12 |
| AMD | 0/2 | 178,501 | 2017-12-28 | 2026-11-04 | 29 | 2020-01-28 |
| AMGN | 0/2 | 173,838 | 2018-05-22 | 2026-11-04 | 28 | 2020-01-30 |
| AMZN | 1/2 | 524,972 | 2000-02-07 | 2026-11-05 | 28 | 2020-01-30 |
| ANET | 1/1 | 370,307 | 2014-01-31 | 2026-11-06 | 29 | 2020-01-02 |
| AVGO | 0/0 | 176,189 | 2018-02-06 | 2026-10-27 | 27 | 2020-03-12 |
| BAC | 14/21 | 6,880,095 | 2019-01-29 | 2026-11-09 | 29 | 2020-01-15 |
| BRK.B | 0/1 | 178,058 | 2017-02-14 | 2026-11-09 | 27 | 2020-02-25 |
| CAT | 0/3 | 183,353 | 2019-04-29 | 2026-11-04 | 29 | 2020-01-31 |
| COST | 0/1 | 175,853 | 2016-10-25 | 2026-10-27 | 27 | 2020-03-05 |
| CRWD | 1/1 | 227,525 | 2011-12-02 | 2026-11-06 | 28 | 2020-03-19 |
| CSCO | 1/2 | 514,157 | 2004-02-12 | 2026-10-29 | 27 | 2020-02-12 |
| CVX | 0/1 | 173,589 | 2019-05-01 | 2026-11-05 | 31 | 2020-01-31 |
| DELL | 1/1 | 345,183 | 2013-07-24 | 2026-10-26 | 27 | 2020-02-27 |
| GE | 0/2 | 181,851 | 2019-01-15 | 2026-11-05 | 30 | 2020-01-29 |
| GOOGL | 1/1 | 466,855 | 2015-10-02 | 2026-11-06 | 29 | 2020-02-03 |
| GS | 25/39 | 11,614,292 | 2019-10-30 | 2026-11-09 | 31 | 2020-01-15 |
| HD | 0/2 | 177,547 | 2018-02-26 | 2026-09-22 | 27 | 2020-02-25 |
| IBM | 1/4 | 524,682 | 2012-08-01 | 2026-11-09 | 31 | 2020-01-21 |
| INTC | 0/2 | 175,467 | 2019-03-25 | 2026-11-04 | 29 | 2020-01-23 |
| JNJ | 0/2 | 170,371 | 2018-08-02 | 2026-10-26 | 30 | 2020-01-22 |
| JPM | 47/71 | 23,677,088 | 2019-11-21 | 2026-11-09 | 28 | 2020-01-14 |
| KO | 0/2 | 175,056 | 2018-07-25 | 2026-11-09 | 28 | 2020-01-30 |
| LIN | 0/0 | 139,322 | 2017-06-01 | 2026-11-09 | 28 | 2020-02-13 |
| LLY | 1/2 | 525,865 | 2008-01-29 | 2026-11-04 | 33 | 2020-01-30 |
| LRCX | 0/1 | 182,595 | 2015-04-20 | 2026-11-09 | 28 | 2020-01-29 |
| MA | 0/1 | 176,119 | 2019-04-24 | 2026-11-03 | 28 | 2020-01-29 |
| META | 1/2 | 520,057 | 2017-06-23 | 2026-11-06 | 28 | 2020-01-29 |
| MRK | 0/2 | 174,458 | 2018-05-29 | 2026-11-04 | 29 | 2020-02-05 |
| MS | 31/46 | 16,901,790 | 2019-08-16 | 2026-11-09 | 28 | 2020-01-16 |
| MSFT | 1/2 | 542,382 | 2008-08-28 | 2026-11-05 | 28 | 2020-01-29 |
| MU | 0/1 | 181,572 | 2017-10-18 | 2026-11-05 | 27 | 2020-03-25 |
| NFLX | 1/3 | 523,677 | 2016-05-04 | 2026-11-05 | 28 | 2020-01-21 |
| NVDA | 1/1 | 439,168 | 1998-03-06 | 2026-11-06 | 28 | 2020-02-13 |
| ORCL | 0/1 | 174,650 | 2016-06-10 | 2026-11-04 | 28 | 2020-03-12 |
| PANW | 0/1 | 170,852 | 2019-11-04 | 2026-11-05 | 27 | 2020-02-24 |
| PG | 1/3 | 532,983 | 2015-02-19 | 2026-11-09 | 28 | 2020-01-23 |
| PLTR | 0/1 | 175,421 | 2008-03-05 | 2026-11-04 | 25 | 2020-11-12 |
| PM | 0/1 | 174,628 | 2017-11-02 | 2026-10-23 | 28 | 2020-02-06 |
| RTX | 0/1 | 165,642 | 2017-09-14 | 2026-11-03 | 28 | 2020-01-28 |
| TMO | 0/2 | 173,880 | 2019-09-10 | 2026-11-05 | 31 | 2020-01-30 |
| TSLA | 0/1 | 178,410 | 2018-06-14 | 2026-11-06 | 56 | 2020-01-03 |
| TXN | 0/2 | 176,874 | 2017-01-30 | 2026-10-30 | 28 | 2020-01-22 |
| UNH | 1/2 | 516,699 | 2010-08-13 | 2026-11-03 | 28 | 2020-01-15 |
| V | 0/1 | 175,332 | 2015-02-18 | 2026-11-05 | 28 | 2020-01-30 |
| WFC | 2/9 | 1,066,265 | 2018-12-04 | 2026-11-09 | 28 | 2020-01-14 |
| WMT | 1/2 | 518,185 | 2012-09-06 | 2026-11-06 | 27 | 2020-02-18 |
| XOM (CIK 0002115436) | 0/0 | 8,899 | **2026-07-01** | 2026-11-03 | 2 | 2026-07-31 |
| XOM predecessor (0000034088) | 1/2 | 527,798 | 2005-10-04 | 2026-10-27 | 26 | 2020-01-31 |

**Every security reaches back before 2020-01-01 except XOM's universe CIK**, which starts on 2026-07-01. Its
predecessor is read with it (decision D12). PLTR's first Item 2.02 8-K is 2020-11-12 because it listed on 2020-09-30.

**Structure, settled on the fetched files (`p03`).**

- An extra page holds the same parallel arrays as `recent`, at its top level (`accessionNumber`, `filingDate`,
  `acceptanceDateTime`, `form`, `items` and others). Over the 135 pages read: the array length equals the listed
  `filingCount` every time, and the first `filingDate` equals the listed `filingFrom` every time.
- The listed `filingTo` is **not** always the page's last `filingDate`: the difference ran from −6 to **+1** days. A
  page whose `filingTo` lies just before `since` can still hold a filing on `since`, so `pages_needed` uses a 7-day
  margin (`PAGE_MARGIN_DAYS`). With `since` = 2020-01-01 the margin adds no page today.
- The blocks of one company follow each other closely: over the 135 boundaries between consecutive blocks, the days
  from one block's last filing to the next block's first are 1 to 8. The 8 days are GOOGL's (2023-08-21 to
  2023-08-29, between its one page and `recent`), a quiet week rather than a missing block.
- `items`: every 8-K filed from 2004-08-23 on has the form `n.nn[,n.nn…]` (7,130 of them), e.g. `2.02,9.01`. The 53
  8-Ks with the old item numbers (`5,7`, `12`, `9` …) were filed from 2000-02-07 to 2004-08-20, before the 2004 item
  renumbering, and none is read as Item 2.02.
- `acceptanceDateTime`: all 390,105 values have the form `YYYY-MM-DDTHH:MM:SS.000Z`.
- No accession is listed twice with different fields (`merge_filings` would stop the build).

## 2. The time zone of `acceptanceDateTime`

The code assumed UTC because of the trailing `Z`. Each filing was read both ways and compared with six independent
references (`p01`).

| Reference | Read as a UTC instant | Read as New York wall time |
|---|---|---|
| **A. The 20 press-release look-ups** (ground truth): 8-K date and BMO/AMC equal the release's | **20 of 20** (16 read by the rule, 4 in the Columbus Day 2024 window, whose times also agree) | 9 of 20; all 11 BMO releases land inside the session (`during_session`) |
| **B. Calendar labels**, 1,306 labelled events on a session D | agree **1,273**, contradict 4, during the session 1, holiday window 20, other date 3, no 8-K 5 | agree 665, contradict 3, **during the session 610**, holiday 20, other date 3, no 8-K 5 |
| **C. Price-gap diagnostic** on the 8-K's own label (counts only) | supports **722**, quiet 527, contradicts 18, during 1 | supports 449, quiet 208, contradicts 8, **during 603** |
| **D. EDGAR's filing date**, 8-Ks and 8-K/As from 2020: accepted before 17:30 New York time → same filing date; from 17:30 → next business day | before 17:30: **4,444 of 4,444** same date; from 17:30: **123 of 137** a later date | before 17:30: 1,572 same, 5 later; from 17:30: **2,932 of 3,004 the same date** |
| **E. EDGAR's hours** (06:00–22:00 New York time), all 390,105 filings | **312 outside (0.08%)** | 79,068 outside (20.27%) |
| **F. Daylight saving:** a company's median Item 2.02 time in EDT months minus EST months | median shift **+0 min**; 2 of 50 shift by 45 min or more (BRK.B and MS, whose release habits differ by quarter, not by an hour) | median shift **−60 min**; **50 of 50** shift by 45 min or more |

**Decision: `acceptanceDateTime` is a UTC instant.** The code was already converting from UTC; it now does so through
`edgar.parse_acceptance()`, which refuses any other format (a value without milliseconds, with six digits, or with an
offset), so a change in EDGAR's output cannot move a time by hours unnoticed. Tests:
`test_acceptance_time_is_a_utc_instant_across_daylight_saving` (one 16:30 release in EDT and in EST, and a 06:46 EDT
filing read as BMO) and `test_parse_acceptance_refuses_any_other_format`; mutants M5 and M6 (§7).

Row D also bears on the pre-registered claim E4: 8-Ks accepted after 17:30 keep their real acceptance time and most get
the next filing date. The 14 exceptions (accepted from 17:30, same filing date) are not explained here.

## 3. Item 2.02 8-Ks near the events

- **Coverage** (the ADR's milestone-1 criterion, at least 95% of events with an Item 2.02 8-K on D−1…D+1; `p02` §6):
  daily **361 of 368 (98.1%)**, mixed 47 of 48 (97.9%), coarse 845 of 868 (97.4%); the duplicate row is left out.
  **The criterion is met.** The 7 daily misses and the 1 mixed miss are all BRK.B, which releases on Saturdays, while
  EDGAR accepted nothing on a weekend (`p01` G). For 7 of the 8 the nearest Item 2.02 8-K is 2 to 5 days after D; for
  BRK.B 2025-02-28 it is 2025-02-24, 4 days before D, which points to a calendar date error (`p02` §4b).
- Over all 1,353 events: 1,310 have exactly one Item 2.02 8-K in the window, 1 has two (ABBV 2022-04-29, 07:45 and
  09:00, both BMO, outside the 453), 42 have none.
- From 2020, one 8-K/A carries Item 2.02 (PLTR, filed 2021-08-18). Amendments are not read (D11).

## 4. EDGAR's closed days

`p01` G lists the NYSE sessions from 2020-01-02 to 2026-11-06 on which none of the 51 CIKs had an acceptance (EDGAR
accepted nothing on a weekend either). Besides every Columbus Day and Veterans Day (the ADR's two), there are
**2020-12-24, 2021-06-18 (Juneteenth's first observance), 2021-12-31 (New Year's Day 2022 observed), 2024-12-24,
2025-12-24 and 2025-12-26**. `edgar_holidays()` now includes them: New Year's Eve by rule (when 1 January is a
Saturday) and the others as a measured list, `EDGAR_CLOSED_MEASURED`. `read_acceptance` also now looks up the holidays
of every year in the window, not only D's year (a window across 31 December). **None of the 453 events is affected**
by the added days: all 11 `edgar_holiday` outcomes are Columbus Day or Veterans Day windows. A future one-off closure
is not known in advance (§9).

## 5. Wiring decisions

ADR 0002 §3 is followed where it speaks. Where it is silent, the conservative option was taken: the event stays
unresolved (`not_checked`, calendar label) for a press-release look-up.

| # | Situation | Rule applied | Source |
|---|---|---|---|
| D1 | Which events EDGAR is consulted on | The 453 that the default rule still requires (`lookup_violations` of a first pass), plus the 20 press-release events for the record only. Coarse `not_checked` events that need no look-up are not consulted. | Task scope; the ADR does not say whether EDGAR replaces `not_checked` in `coarse` |
| D2 | An event with a press-release row | The release decides, as before; the matched 8-K is recorded in `edgar_accession` / `edgar_accepted_utc` | Task; ADR table row 3 |
| D3 | 8-K on D agrees with the calendar label | `confirmed`, `timing_source = edgar` | ADR table row 1 |
| D4 | NULL label, 8-K on D before the open or after the close | `inferred`, the 8-K's label | ADR table row 4 |
| D5 | 8-K on D contradicts the label | **unresolved** (`contradicts`): `corrected` needs a press release that agrees | ADR table row 2, source 2 |
| D6 | 8-K on D−1 or D+1 | **unresolved** (`other_date`), even where day 0 would be the same | ADR source 2 ("falls on a different date") |
| D7 | Accepted 09:30–close | **unresolved** (`during_session`), hand check | ADR source 1 |
| D8 | D−1, D or D+1 is an EDGAR closed day | **unresolved** (`edgar_holiday`); the press release decides | ADR source 1 |
| D9 | No Item 2.02 8-K in the window | **unresolved** (`no_8k`). Not `no_document`: that status means no press release *and* no 8-K, and no release was looked up | Data model `timing_status` |
| D10 | Two Item 2.02 8-Ks in the window that read differently | **unresolved** (`several_8k`), new. 0 of the 453 | Silent; conservative |
| D11 | An 8-K/A | Not read: it is filed after the release it amends | Silent; conservative |
| D12 | XOM's 2020–2026 8-Ks under an older CIK | Read CIK 0000034088 with the universe CIK, from `data/manual/edgar_predecessor_ciks.csv`, whose row gives the evidence: the new CIK's first filing is an 8-K12B (successor issuer) of 2026-07-01; the old one (EXXON MOBIL CORP) lists no ticker, filed a Form 25-NSE on 2026-07-02, and has Item 2.02 8-Ks every quarter to 2026-05-01 | Silent; evidence from EDGAR's own files |
| D13 | Job 1 under the EDGAR rule: the gap contradicts the 8-K's label | The 8-K's label stands; the event is listed for a press-release check (`edgar_pending_gap_checks`). The outside flag is counted as a trigger too, as under the default rule | ADR §3 job 1 names only the contradiction; the flag is the conservative reading |
| D14 | A non-session D with the 8-K accepted on D | `confirmed`, the calendar label kept (only the date is checked). 0 cases: EDGAR accepts nothing on weekends | ADR, "A non-session D" |
| D15 | Switching it on | `params.timing.edgar` (absent = false). The stage reads `raw/edgar/` only; fetching is a separate command, `python -m earnings_vol.ingest.edgar` | Keeps the events stage offline and the contact string out of pipeline runs |

## 6. Outcomes for the 453 (`p02`)

The two builds were made in memory: as committed, and with `timing.edgar` true (a params copy in
`cache/edgar-phase1/`). Tables written: `cache/edgar-phase1/{events_edgar.parquet, outcomes.csv, report.json}`.

| Outcome | coarse | daily | mixed | All |
|---|---:|---:|---:|---:|
| `confirmed` (EDGAR) | 24 | 351 | 30 | **405** |
| `inferred` (EDGAR) | 6 | 0 | 0 | **6** |
| unresolved: `no_8k` | 17 | 7 | 2 | 26 |
| unresolved: `edgar_holiday` | 0 | 10 | 1 | 11 |
| unresolved: `other_date` | 4 | 0 | 0 | 4 |
| unresolved: `contradicts` | 0 | 0 | 1 | 1 |
| unresolved: `during_session`, `several_8k` | 0 | 0 | 0 | 0 |
| **All** | 51 | 368 | 34 | **453** |

- **Resolved: 411** (405 `confirmed`, 6 `inferred`), by label **AMC 224, BMO 187**.
- **Unresolved: 42**, all left `not_checked` with the calendar label:
  - `no_8k` 26: BRK.B 23 (it releases on Saturdays; the nearest Item 2.02 8-K is 2 to 10 days after D for 20 of
    them, 4 days before D for 2021-08-13 and 2025-02-28, and none within 14 days for 2022-08-05), GS 2021-10-13 and 2022-10-21 and AMAT
    2021-02-10 (NULL-label rows; the nearest Item 2.02 8-Ks are 2021-10-15, 2022-10-18 and 2021-02-18, so the
    calendar date itself looks wrong);
  - `edgar_holiday` 11: GS, JNJ, JPM, WFC on 2025-10-14 and 2026-10-13, UNH 2026-10-13, HD 2024-11-12, CSCO
    2025-11-12. Every one of their 8-K times agrees with the calendar label;
  - `other_date` 4: META 2020-07-29 (8-K 2020-07-30 19:18, AMC), MS 2020-04-15, ORCL 2020-09-09 and WFC 2022-10-13
    (NULL labels; 8-Ks one day later). These look like calendar date errors;
  - `contradicts` 1: **TXN 2024-10-22**, calendar BMO, 8-K accepted 16:03 (AMC). If a press release confirms it, day 0
    moves from 2024-10-22 to 2024-10-23 (mixed sample).
- **Day 0 against the current calendar-based build:** **0 events move.** **6 get a day 0 they did not have**: the
  `inferred` NULL-label events IBM 2021-04-19, INTC 2021-04-22, ORCL 2020-06-16, 2020-12-10, 2021-12-09, 2023-03-09
  (all coarse, all AMC). `timing_not_checked` exclusions fall from 32 to 26; sample counts are unchanged (coarse 868,
  daily 368, mixed 49, none 68); the EPS table is identical in both builds. If the unresolved 8-K readings were later
  confirmed by press releases, TXN and META would move by one session and MS, ORCL and WFC would gain a day 0.
- **The 20 press-release look-ups:** EDGAR's time agrees with all 20 on date and label (16 read by the rule; BAC, GS,
  JNJ and UNH on 2024-10-15 fall in the Columbus Day window and would not have been read). Nothing was overwritten:
  each keeps its status and `timing_source = press_release`, and its accession is recorded. EDGAR alone would have
  flagged the three press-release findings: NFLX and GOOGL as `contradicts` (AMC against the calendar's BMO) and MS as
  `other_date` (2024-10-16 07:28 against the calendar's 10-17).
- **Job 1:** **37** EDGAR labels are questioned by the gap, all among the 453: 18 by a gap contradiction, 19 by the
  outside flag (disjoint); coarse 24, daily 11, mixed 2. Each needs a press-release check (listed in `p02` §7).
- **`timing.lookups_complete` cannot become true.** 42 events still violate the build invariant (null_label 23,
  daily_or_mixed_era 21, gap_trigger 3; coarse 21, daily 17, mixed 4), so setting it would stop the build. On top of
  that, the 37 job-1 checks and the ADR's 50-event accuracy audit of `confirmed` EDGAR labels against press releases
  have not been done.

## 7. Mutants (`p04`, on a temporary copy of the tree; PYTHONPATH pointed there)

Baseline of the two test files: 82 passed. Each mutant was applied alone, the named test(s) run, the file restored and
its SHA-256 compared with the original (all equal; the final files equal the repository's).

| # | Mutant | Test(s) | Result |
|---|---|---|---|
| M1 | `pages_needed` without the 7-day margin | `test_pages_needed_reaches_back_to_since_with_a_margin` | killed (1 failed) |
| M2 | `merge_filings` keeps the first copy without comparing | `test_merge_filings_keeps_each_accession_once_and_refuses_two_readings` | killed |
| M3 | `item_202_filings` reads `recent` only | `test_an_8k_only_in_an_extra_page_is_found` | killed |
| M4 | `read_cached` returns no pages | `test_fetch_all_caches_the_pages_and_read_cached_needs_no_network` | killed |
| M5 | `parse_acceptance` reads New York wall time | `test_acceptance_time_is_a_utc_instant_across_daylight_saving` | killed |
| M6 | `parse_acceptance` without its format check | `test_parse_acceptance_refuses_any_other_format` | killed (5 of 6) |
| M7 | `edgar_holidays` without the New Year's Eve rule | `test_edgar_holidays_include_new_years_eve_and_the_measured_closures` | killed |
| M8 | `read_acceptance` uses D's year's holidays only | `test_the_holiday_window_crosses_the_year` | killed |
| M9 | `read_acceptance` without `several_8k` | `test_two_8ks_in_the_window_that_read_differently_are_not_read` | killed |
| M10 | `resolve_edgar` confirms a contradiction | `test_resolve_edgar_status_table` | killed (1 of 11) |
| M11 | `resolve_edgar` without the other-date check | `test_resolve_edgar_status_table` | killed (2 of 11) |
| M12 | `cached_item_202` reads the first CIK only | `test_predecessor_ciks_are_read_with_the_current_one` | killed |
| M13 | `run.build` consults EDGAR for no event | `test_build_with_edgar_resolves_only_what_the_rule_allows` | killed |
| M14 | `run.edgar_scope` without the press-release events | `test_build_with_edgar_resolves_only_what_the_rule_allows` | killed |
| M15 | `fetch_universe` puts the User-Agent in its record | `test_the_fetch_record_never_holds_the_user_agent` | killed |
| M16 | `run.build` with EDGAR always on | `test_build_without_edgar_never_reads_it` | killed |
| M17 | `edgar_holidays` without the measured closures | `test_edgar_holidays` (ingest) and the new holiday test | killed (2 failed) |

**17 of 17 killed.** The tests use hand-written values only: made-up CIKs (41, 42), accession numbers, times and a
made-up contact on a placeholder domain.

## 8. Gates

- `uv run --frozen pytest -q`, last run 2026-11-09 15:25 local time: **713 passed, 7 failed**. The 7 are outside this
  change. All are in `tests/test_report_numbers.py`, and all report the same thing: "stale:
  docs/report/earnings-vol-report.md (run tools/report_numbers.py)". The parallel report work rewrote that file at
  15:25:41, a few seconds before the run. `tools/report_numbers.py` does not import `earnings_vol` or read EDGAR. An
  earlier run the same day gave 697 passed, 18 failed. Those 18 were also in the report and VX files that the same
  work was adding.
- The six test files for this change's area (`test_edgar_timing`, `test_ingest_sources`, `test_events_run`,
  `test_timing`, `test_events`, `test_layering`): **193 passed**.
- A search for the contact address over `~/dev/earnings-vol-study` and `~/data/vol-projects/earnings-vol-study`:
  0 hits.

## 9. Open, and least sure

1. **The ADR's milestone-1 EDGAR audit has not run**: 50 random `confirmed` EDGAR events checked against press
   releases. The 20 press-release look-ups agree with EDGAR's time 20 of 20, but they are not a random sample of
   `confirmed` events (GOOGL was chosen as a known error).
2. **`inferred` rests on the 8-K alone.** An 8-K filed hours after a BMO release would read AMC. The 20 look-ups put
   EDGAR within −18 to +13 minutes of the stated release time, and job 1 flags 0 of the 6 `inferred` events, but 6 is
   too few to measure that risk.
3. **Scope D1.** Coarse events that the default rule leaves `not_checked` were not given EDGAR labels. Applying EDGAR to
   them would remove the coarse sample's gap-triggered selection; whether to do so is an ADR decision for the owner.
4. **Job 1's trigger** includes the outside flag (D13). The ADR names only the contradiction under the EDGAR rule.
5. **Future EDGAR closures** (Christmas Eve orders, mournings) are not known in advance; `EDGAR_CLOSED_MEASURED` must be
   extended when the data are refreshed (`p01` G lists empty sessions).
6. ~~Docs still describe EDGAR as pending its contact string (ADR 0002 status, data model §2, milestone 1): phase 2.~~
   Done in phase 2 (§10.5).

## 10. Phase 2: EDGAR switched on, the pipeline re-run (2026-11-09)

### 10.1 The decision

**Owner decision, 2026-11-09: SEC EDGAR is the timing source.** `params.yaml` now holds `timing.edgar: true`, with the
decision in its comment; ADR 0002's status and its note "SEC EDGAR switched on" record it too. `timing.lookups_complete`
stays **false**: 42 required look-ups are open and the ADR's 50-event audit has not run. The params hash moved from
`74bed6f4b1281810` to `d23d18972bf0c8d4`, so every stage was rebuilt in a new stage directory; the old one is kept.

### 10.2 What was re-run, in order

| Step | Command (`uv run --frozen …`) | Result |
|---|---|---|
| Events | `python -m earnings_vol.events.run` | 5.8 s; the EDGAR report equals phase 1's (§6): 405 confirmed, 6 inferred, 42 open, 37 gap-questioned |
| Measures | `python -m earnings_vol.measures.run` | 91.8 s (snapshots, close, IV) |
| Panel | `python -m earnings_vol.panel.run` | 5.8 s |
| Gate G1 | `python -m earnings_vol.stats.run --g1` | 276.6 s in all (G1 265 s, drivers 11 s, 20 workers); 2,000 reps; the 10,000-rep re-measure of the rows near the bar (H4: `bmp_t`, `cluster_date_t`, `gen_sign_z`) ran again |
| Results | `python -m earnings_vol.stats.run` | 927 rows; Holm over the declared H1–H7 |
| App data | `python tools/export_app_data.py` | nine JSON files |
| VX\* | `python tools/vx_crosscheck.py` | 10 s; bar iv re-read on the new events |
| Numbers | `python tools/report_numbers.py` | 335 numbers; the look-up pins checked against the local stage report |
| Pictures | `--with playwright==1.64.1 python tools/screenshots.py --out <scratch>` | all 21 shot into a scratch folder; only `app-about.png` and `app-about-phone.png` copied to `docs/images/` (§10.6) |
| Report | `--group report --with playwright==1.64.1 python tools/build_report.py` | PDF 806,008 B, DOCX 376,208 B |
| Notebooks | `python tools/build_notebooks.py --check` | `OK: 5 notebooks … are in sync with src/` |

Before anything was overwritten, `data/derived/*`, `app/public/data/*` (with `tests.json` and `drivers.json`), the old
stage reports and the two About screenshots were copied to the session scratchpad (`pre-edgar/`). SHA-256 of the three
named files before the re-run: `results.parquet` `52cee5e731e2…`, `tests.json` `4635f866da25…`, `drivers.json`
`993d8ee8f9bd…`.

### 10.3 Before → after (`p05_before_after.py`, output in `probes/edgar/out/p05_before_after.txt`)

H1–H7, the primary row of each (verdict: rejected when the Holm p over H1–H7 is below 0.05):

| | Statistic | Estimate | SE | p | Holm p | Verdict |
|---|---|---|---|---|---|---|
| H1 crush | two-way (date) t | −0.199377 → −0.199377 | 0.0112433 → 0.0112433 | 5.8e−23 → 5.8e−23 | 4.06e−22 → 4.06e−22 | rejected → rejected |
| H2 run-up | randomisation p (season) | 0.231896 → 0.231896 | — | 0.007812 → 0.007812 | 0.04688 → 0.04688 | rejected → rejected |
| H3 persistence | two-way (season) t | 0.00802043 → 0.00802043 | 0.0233378 → 0.0233378 | 0.7428 → 0.7428 | 1 → 1 | not rejected → not rejected |
| H4 ordinary vol | two-way (date) t | 0.00310774 → 0.00310774 | 0.0111723 → 0.0111723 | 0.7821 → 0.7821 | 1 → 1 | not rejected → not rejected |
| H5 surprise | two-way (date) t | 0.0132357 → 0.0132357 | 0.00495392 → 0.00495392 | 0.01022 → 0.01022 | 0.05108 → 0.05108 | not rejected → not rejected |
| H6 prior vol | two-way (date) t | −0.00142782 → −0.00142782 | 0.0107539 → 0.0107539 | 0.8949 → 0.8949 | 1 → 1 | not rejected → not rejected |
| H7 implied vs realised | two-way (date) Wald | — | — | 0.2751 → 0.2751 | 1 → 1 | not rejected → not rejected |

| Number | Before | After |
|---|---|---|
| G1 rejection rate at 5% (band [0.038, 0.063]), H1 / H2 / H3 / H4 | 0.0460 / 0.0040 / 0.0050 / 0.0460, pass | the same |
| G1, H5 / H6 / H7 | 0.0955 / 0.0810 / 0.1615, fail | the same |
| G1 re-measure, 10,000 reps (H4 `bmp_t`, `cluster_date_t`, `gen_sign_z`) | 0.0534, 0.0498, 0.0568 | the same |
| Events by sample (daily / mixed / coarse / none) | 368 / 49 / 868 / 68 | the same |
| Primary sample (after the last funnel step) | 347 | 347 |
| Funnel "one row per release, and day 0 can be placed" | 1,320 | **1,326** |
| `timing_not_checked` exclusions | 32 | **26** |
| Day 0 | — | moved 0, lost 0, newly defined 6 (IBM 2021-04-19, INTC 2021-04-22, ORCL 2020-06-16, 2020-12-10, 2021-12-09, 2023-03-09; all `coarse`, all AMC) |
| Timing statuses (confirmed / corrected / date_corrected / inferred / not_checked) | 16 / 2 / 1 / 1 / 1,333 | **421** / 2 / 1 / **7** / **922** |
| `timing_source` (press_release / edgar / calendar / none) | 20 / 0 / 1,297 / 36 | 20 / **411** / **892** / **30** |
| Look-ups done (`sample_funnel.json`) | 20 | **431** |
| VX\* bar iv: n, ratio, event-bootstrap interval, verdict | 34, 0.9181, [0.8688, 0.9728], pass | the same |
| VX\* bar iv: its events' labels | not_checked 34 | **confirmed 32, not_checked 2** (GS 2025-10-14 and 2026-10-13, next to Columbus Day) |
| VX\* bars i, ii, iii, the alignment check, the longer-gap check | — | identical sections of `vx_crosscheck.json` |
| `results.parquet` rows with any change in estimate, SE, p, Holm p, q or n | — | **13 of 927, all exploratory regressions** (below) |

The 13 rows: the `coarse` driver model `crush_drivers` (5 rows: R², `abs_surprise`, `ln_sigma_d`, `slope`, `size`; the
largest change is in the fourth significant digit, `abs_surprise` −0.0060814 → −0.0060824); the `daily` model `crush_sue` (5 rows; `abs_sue` 0.00209 → 0.00166,
p 0.577 → 0.659; `slope` p 0.000273 → 0.000283); and three rows whose BH q moved only (`crush_disp` `abs_disp`,
`dsigma_d_drivers` `size`, `implied_realised_m2`). The cause: the 6 newly dated events are ineligible for every test
(short baseline, or no day −1 snapshot for IBM), but they enter the earnings-surprise history (`sue_hist` changed for 34
IBM, INTC and ORCL events), the `coarse` winsorisation of the surprise (22 events) and the VIX terciles (12 events).

### 10.4 Did any verdict change?

**No.** H1 and H2 are rejected under Holm over H1–H7 and H3–H7 are not, as before. Every G1 pass/fail flag is the same.
The VX\* bars are the same (bar i fails for GOOGL, IBM and the pooled sample; bar iii passes for all five; bar iv
passes). Why so little moved: in the `daily` and `mixed` samples EDGAR confirmed the calendar's label for every event
it read; where it did not (the TXN contradiction, the other-date and holiday cases), the event stays `not_checked`
with the calendar's label, so no day 0 moved. The 6 events that gained a day 0 are `coarse` and none is eligible for a
test.

### 10.5 Wording changed where it was false

"Provisional" stays, because `timing.lookups_complete` is still false. Changed where a sentence said EDGAR had not run,
or that every non-press-release event rests on the calendar:

- **Code text:** the caveats in `src/earnings_vol/export/{funnel,event_views,iv_view}.py` (into every app JSON); the
  header comments of `ingest/edgar.py` and `events/timing.py`; `tools/export_app_data.py` lists SEC EDGAR as a data
  source (the committed `edgar_accession` and `edgar_accepted_utc`), with a line in the attribution text
  (`tests/test_export_app_data.py` updated by hand).
- **The look-up pins** in `tools/report_numbers.py`: `LOOKUPS_REQUIRED` stays 473; new pins `LOOKUPS_OPEN_BY_REASON`
  (no 8-K 26, EDGAR holiday 11, other date 4, contradicts 1), `LOOKUPS_GAP_QUESTIONED` (37) and `LOOKUPS_AUDIT` (50),
  with their source (this ledger, §6, and the stage's `events_report.json`). The press-release and EDGAR counts (20,
  411) are read from the committed `events.parquet` and cross-checked against `lookups.n_done` (431). `--check`
  compares every pin with the local stage report (`lookup_violations.n`, `edgar.outcome`, `edgar.pending_gap_checks`)
  and fails if that report has no EDGAR run. Bar iv's label counts (32 documented, 2 calendar) are new numbers from
  `vx_crosscheck.json`, and the bar-iv prose claim now says most of its events rest on a document's label.
- **Docs:** ADR 0002 (status, "In one paragraph", the note "SEC EDGAR switched on"), the data model (the EDGAR source
  row, the class reasoning (the labels stay class F, because the look-up scope in `coarse` is still chosen by the gap
  trigger), `timing_source`, `edgar_accession`, `edgar_accepted_utc`, open decisions 6 and 7), milestone 1 (status,
  §6.4), milestone 5 (new §12, the bar-iv limit, the appendix), README (status, the fetch command, the milestone-1
  lesson, the tree), `DATA.md`, `data/derived/README.md`, and the report, README and PR/FAQ templates (the look-up
  counts with their reasons, the audit, the gap-questioned labels; the PR/FAQ's "no request has been made"; report §9
  question 6 now asks the owner about BRK.B's Saturday releases and about EDGAR in `coarse`).
- **Docs, second sweep** (every remaining "gated on the contact string" / "until SEC EDGAR runs" that was now false):
  the four diagram specs (`architecture`, `data_flow`, `erd`, `event_sequence`; rebuilt into `docs/architecture/out/`,
  `--check` ok, the Mermaid 12.2.0 render gate ok) and the copies and prose in `docs/architecture/README.md`; ADR 0001's
  layer table; ADR 0002's rule text (source 1, the default rule, the milestone-1 check, licensing, cost, the
  fallback trigger; the dated notes are history and were left); the ADR index; the status and "what is next" lines
  of milestones 3, 4 and 5 (a dated "Since 2026-11-09" sentence after the old one) and item 4 of milestone 1's
  summary; decision 2
  of milestone 5; the two provisional notices in `tools/build_notebooks.py` (notebooks 03 and 04 rebuilt); two
  hand-written paragraphs of `docs/prfaq.md` outside the rendered blocks. **Left as they were:** dated gate outputs
  and probe outputs, the milestone-1 table's "453 left after the 20", and `docs/validation/vx-preregistration.md`
  ("the SEC EDGAR look-ups have not run yet"), because a pre-registration is not edited after the fact.
- **Tests updated for the new data or params:** `tests/test_events_run.py` passes an empty EDGAR loader (the real
  params now ask for one); `tests/test_report_numbers.py` expects 473 / 431 / 42 and the new keys, plants an EDGAR
  stage report, and uses the new bar-iv claim.

### 10.6 Screenshots

`tools/screenshots.py` (the milestone-5 tool) re-took every picture into a scratch folder; only the About shots were
copied (`app-about.png`, `app-about-phone.png`: the VX\* row now says "run 2026-11-09", and SEC EDGAR is listed).
**Stale when written, replaced later the same day (2026-11-09):** `fig-funnel.png` (in the report) and `app-sample.png`
showed 1,320 events at "day 0 can be placed" (now 1,326); `app-results.png`, `app-drivers.png`, `app-implied.png`,
`app-paths.png`, `app-heatmap.png`, `app-3d.png` and `app-iv.png` showed the provisional notice with 20 look-ups done (now
431). All nine were re-taken with `tools/screenshots.py` (into a scratch folder first, then copied); the other pictures
draw numbers that did not change.

### 10.7 Mutants for the new checks (`p06_report_mutants.py`, on a scratch copy)

Baseline `tests/test_report_numbers.py`: 29 passed. Each mutant was applied alone, the named test run, the file restored
and its SHA-256 compared (all equal; the final files equal the repository's).

| # | Mutant in `tools/report_numbers.py` | Test | Result |
|---|---|---|---|
| R25 | `lookups.edgar` counted from `press_release` | `test_key_numbers_from_the_committed_data` | killed |
| R26 | the done = press releases + EDGAR cross-check compares done with itself | `…fail_the_check[look-ups by source]` | killed |
| R27 | the stage comparison of the open look-ups by reason skipped | `test_the_pinned_lookup_count_is_compared_with_a_local_stage_report` | killed |
| R28 | the stage comparison of the gap-questioned count skipped | the same | killed |
| R29 | the bar-iv label claim made always true | `…fail_the_check[VX timing]` | killed |
| R30 | the "no EDGAR run in the stage report" guard removed | the stage test | killed |

**6 of 6 killed.**

### 10.8 Gates and the contact check (after the last edit)

| Gate | Command | Printed |
|---|---|---|
| Python tests | `uv run --frozen pytest -q -p no:cacheprovider` | `723 passed, 61 warnings in 77.12s` |
| App | `cd app && npm run verify` (lint, then coverage, then build, joined by `&&`) | `Test Files  44 passed (44)`, `Tests  1894 passed (1894)`; `All files \| 99.78 \| 99.42 \| 99.39 \| 99.88`; `✓ built in 5.43s` |
| Numbers | `uv run --frozen python tools/report_numbers.py --check` | `ok: 4 file(s) match 335 numbers from the committed data; the PDF and DOCX were built from this Markdown; look-ups: 42 left + 431 done = 473; open by reason and 37 gap-questioned, as pinned (local events_report.json)` |
| Data files | `uv run --frozen python tools/licensing/check_data_files.py` | `clean: no raw vendor file and no oversized data file` |
| VX\* | `uv run --frozen python tools/vx_crosscheck.py --check` | `ok: data/derived/vx_crosscheck.json equals a fresh computation (13 s)` |
| Notebooks | `uv run --frozen python tools/build_notebooks.py --check` | `OK: 5 notebooks … are in sync with src/` |
| Diagrams | `… tools/diagrams/build.py docs/architecture/specs --out docs/architecture/out --check`, then `--verify-mermaid` | `ok: 5 spec(s) up to date`; `mermaid 12.2.0: 5 spec(s) checked: every title, label, … reads as the spec text` |
| Contact | a recursive `grep -rn` for the owner's e-mail address (not written here) over the repository and `$VOL_DATA_DIR/earnings-vol-study` | no output (0 hits) |

Nothing was committed (all git writes are on hold).
