# Milestone 1 delta review: claims ledger

PRE-REGISTRATION (written before any Channel B probe below was run; verdicts are appended in §3 after both channels).

- Reviewed: the uncommitted working tree on top of commit `3636e98`, restricted to the fixes listed in
  `m1-ledger.md` §6. Not a full re-review.
- Protocol: `evidence-gated-validation`, Tier 2 for every numeric claim. **Mode: single-context sequential fallback**
  (one reviewer context; a separate researcher sub-agent does the web look-ups for claim 8 and sees only the claimed
  values, not the code). Dual-confirmed results are "dual-confirmed (fallback mode)".
- Default verdict for every claim: **broken**, until both channels say otherwise.
- Environment pin: `probes/m1-delta/env-pin.txt` (Python 3.12.13, pandas 3.1.0, numpy 2.5.4, pyarrow 26.0.0,
  exchange_calendars 4.13.2, dolt 2.6.1, node 22.23.1, aarch64).
- Paths: `$REPO` is the repository root; `$VOL_DATA_DIR` defaults to `~/data/vol-projects`. No probe runs `dolt` in
  `$VOL_DATA_DIR/dolthub/*`; no request goes to sec.gov. Mutations run on a scratch copy of the tree only; the
  working tree is checksummed at start and end.
- Contamination note: the reviewer read `m1-ledger.md` §6, `events/eps.py`, `tests/test_eps.py`,
  `tests/test_events_eps_link.py`, `timing.can_enter_sample`, `events.check_sample_ranges`, `tests/test_layering.py`,
  `edgar.is_real_contact`, `dolt.stat_fingerprint`, `tests/test_dolt.py`, the CSV and `sample_funnel.json` while
  designing the probes below.

## 1. Claims and pre-registered probes

| ID | Claim (atomic) | Cat | Mat | Channel A (docs/source) | Channel B probe (pass condition / falsifier) |
|---|---|---|---|---|---|
| 1a | On the real data every linked period is the quarter its event reported | Alg | material | ADR 0002 §3, data model §3.8 | `pd01`: independent oracle from `eps_estimate`: the `Current Quarter` period end in the last weekly snapshot dated before the announcement is the quarter about to be reported. Compare with every committed link. Pass: 0 disagreements where the oracle is defined. Falsifier check: the same oracle on the pre-review rule (`window_start=10`) must show disagreements |
| 1b | A missing report gives an orphan and never moves a neighbouring quarter's event | Alg | material | `eps.py` header | `pd02`: synthetic shapes: slow reporter (lags 62–75) with the next report missing; a full slow chain; two calendar rows for one quarter; COST 53-week year (stored Sep 30 then Nov 30); a 52/53-week year ending Jan 1–3; BRK.B; PLTR pre-IPO. Falsifier: any period linked to another quarter's event |
| 1c | The assignment is one-to-one, order-keeping and of minimal total cost | Alg | material | `match_periods` docstring | `pd03`: 20,000 random instances vs a brute-force enumeration of all order-keeping one-to-one assignments with the same cost; plus 1-to-1 on the committed `eps`. Falsifier: a lower-cost assignment, a duplicated event, an order inversion |
| 1d | No real-data event sits in two periods' windows in a way that min-total-\|lag\| resolves to the wrong quarter | Alg | material | — | `pd01`/`pd04`: list every committed event that lies in ≥ 2 periods' windows and every security with a lag ≥ 60; cross-check them against the `pd01` oracle |
| 2a | 35 orphans of 1,359 (2.58%), 1,324 matched, 606 pre-calendar | Num | material | milestone 1 §6, ADR 0002 note 3 | `pd04`: recount from `eps.parquet`; rebuild `eps` in memory from the cache with `run.build` and compare field by field |
| 2b | Funnel 1,353 → 1,320 → 366 → 356 → 350; 6 short baselines; P3 359/366 | Num | material | milestone 1 §6 | `pd05`: re-run the first review's independent funnel (`probes/m1/p07`) on the new tables; recount from `events.parquet`; compare `sample_funnel.json`, the PR/FAQ and the milestone page |
| 2c | The committed tables equal a rebuild from the cache | Num | material | — | `pd04`: in-memory `run.build` vs committed `eps`/`events` parquet (sorted, field by field) |
| 3 | Scoping the invariant to `can_enter_sample` cannot hide an event that can be sampled | Sem | material | ADR 0002 §3 | `pd06`: over every date 2016–2027 × {BMO, AMC, NULL}: `sample_of(day0) != none ⇒ can_enter_sample`; diff the violations with and without the scope on the real build; check events within 3 days of each sample edge. Falsifier: a sampled not_checked event dropped by the scope |
| 4a | The params ranges partition 2020-04-01 .. 2026-10-26 | Num | material | ADR 0004 §5 | `pd07`: `check_sample_ranges` on params; every session in the span in exactly one range |
| 4b | `check_sample_ranges` stops a gap or an overlap wherever ranges are used | Sem | material | — | `pd07`: gap, overlap, reorder, swapped names; grep every consumer of `samples` for a path that skips the check |
| 5a | `test_layering` fails on I/O in a middle module | Sem | material | ADR 0001 §1 | `pd08`: on a scratch copy, insert each of ~12 I/O forms into `events/eps.py` (relative import of `store`, left import of `ingest.prices` + call, `np.load`, `pd.read_pickle`, `pd.read_html`, `importlib`, `__import__`, `io.FileIO`, `getattr(builtins, "open")`, …); run `test_layering`. Falsifier: the test passes with I/O present |
| 5b | `test_layering` cannot pass vacuously | Sem | material | — | `pd08`: point the walk at an empty/renamed package on the copy; expect failure |
| 6a | `is_real_contact` rejects reserved and malformed contacts | Sem | material | RFC 2606/6761/6762/8375/7686/9476 | `pd09`: battery of reserved special-use names and malformed local parts. Falsifier: one accepted |
| 6b | `is_real_contact` accepts real contacts | Sem | minor | — | `pd09`: ordinary real-world forms (trailing full stop, IDN, apostrophe, long TLD). Falsifier: one refused |
| 6c | Without the variable the EDGAR client makes zero requests | Sem | material | `ingest/edgar.py` | `pd09`: block `socket.connect`/`getaddrinfo`, call every public EDGAR entry point with the variable unset. Falsifier: a connect attempt |
| 7a | The shared-clone stat fingerprint catches a new file anywhere in the clone | Sem | material | `dolt.py:129` | `pd10`: new hidden file, nested file, empty dir, symlink, file in `.dolt/`. Falsifier: one unseen |
| 7b | The dolt test asserts the touched files | Sem | material | `tests/test_dolt.py:213` | `pd10`: run `-m dolt`; on a scratch copy replace `dolt.query`'s subprocess with a no-touch fake; expect the test to fail |
| 8a | basis and time are consistent in every CSV row; the parser refuses an inconsistent row | Sem | material | ADR 0002 §3 | `pd11`: per-row check; feed `timing.parse_checks` each inconsistent pair |
| 8b | The replaced URLs are IR or newswire pages for the right release | Sem | material | web (researcher) | N/A-by-construction on B (a document fact) |
| 8c | ORCL 2024-09-09 was released at 16:05 ET | Sem | material | web (researcher) | N/A-by-construction on B |
| 9 | No Yahoo, Cboe, FRED-VIX or other licensed vendor values in the tree | Env | material | ADR 0001 §7, data model §2.1 | `pd12`: run `scan_real_rows.py`; grep ADR 0002, ADR 0003, tests, notebooks, docs for one-decimal values and percentages that could be vendor values; check each hit's source |
| 10 | `uv run --frozen pytest -q` passes | Num | material | — | `pd13`: run it; report the line |

## 2. Channel A (documents and source), committed before any probe output

| ID | Primary source read | Finding |
|---|---|---|
| 1a | ADR 0002 §3 "Missing events are detected" (lines 619–641); `events/eps.py:72-137` | The code implements the ADR text exactly: window `[first of the stored month, stored end + 100]`; DP over (period i, event j) with link = \|lag\|, skip period = 101, skip event = 0; forward walk prefers link, then skip-event. Whether the links are right on the data is not decidable from documents: **UNVERIFIABLE** on A |
| 1b | same; ADR sentence "A whole chain never shifts by a quarter to gain a link, because every shifted link costs about 90 days more" | **REFUTED by arithmetic** for slow reporters: with period i's report at lag L and period i+1's report missing, own-quarter cost = L + 101, shifted cost = 101 + \|L − ~91\|. The shift wins whenever L > ~45.5 and the event lies in period i+1's window, i.e. L ≥ ~62 (the first of the next period-end month). The "about 90 days more" only holds for L ≲ 45. Whether a real firm reports that late is a data question (1d) |
| 1b' | ADR 0002 M1 note 3 (line 149) | The ADR itself records a **duplicate calendar row**: BRK.B Friday 2024-11-01 (no label) next to the real Saturday 2024-11-02 release. Min-total-\|lag\| gives the 2024-09-30 period the nearer row (lag 32 < 33): the duplicate, not the release. Predicted wrong link |
| 1c | `match_periods` | Standard order-keeping alignment DP; one-to-one by construction (i and j both advance on a link). **CONFIRMED** on A as source reading |
| 2 | ADR 0002 note 3, ADR 0002 line 750 ("more than about 3% of expected events, counting `orphan` only") | Claimed 35 / (35 + 1,324) = 2.575%. The denominator "expected events" is orphan + matched; pre_calendar excluded, ticker_conflict not mentioned |
| 3 | ADR 0002 §2 (day-0 rule) and §3 (invariant); `timing.can_enter_sample` | Candidates {D if a session, next(D)} cover every day 0 the §2 rule can give, and `sample_of` uses D when day 0 is null (NULL label on a session). **CONFIRMED** on A for the calendar date. Gap in principle: the scope is decided on the calendar's D, while a look-up can move the date (MS moved −1 day), so an event dated just past a sample edge can belong to a sample after correction |
| 4 | ADR 0004 §5; `events.check_sample_ranges`; `params.yaml samples` | Contiguity coarse→mixed→daily and non-empty ranges checked in `run.build`. Other consumers of `samples` not known from source reading |
| 5 | ADR 0001 §1; `tests/test_layering.py` | The I/O check is a denylist of module names and call names. Source reading shows three classes it cannot see: relative imports (`node.module` is `None` or does not start with `earnings_vol`), imports of the **ingest** layer (allowed to the left, and ingest does I/O), and I/O functions not in `IO_CALLS` (`np.load`, `pd.read_pickle`, `pd.read_html`, …). **REFUTED in principle** on A |
| 6 | `edgar.py:39-67`; RFC 2606, 6761, 6762; IANA special-use names registry (home.arpa RFC 8375, onion RFC 7686, alt RFC 9476) | Reserved set coded: test, example, invalid, localhost, local, example.com/.org/.net. Special-use names home.arpa, onion and alt are **not** in it |
| 7 | `dolt.py:129-142` | `rglob("*")` on the clone root; keys are relative paths, so a new path is a new key. **CONFIRMED** on A as source reading |
| 8a | `timing.py:39-50, 126-134`; data model line 183 | A time iff basis ∈ {time_stamp, announced_time}; the label must agree with a given time. Data model: an aggregator URL "is kept only where no company or newswire page was found" |
| 8b/8c | researcher sub-agent (web, no sec.gov), retrieved 2026-10-29; sees only the claimed values | see §3 |
| 9 | ADR 0001 §7; data model §2.1 | (read during B; scanner rules in `tools/licensing/scan_real_rows.py`) |

## 3. Verdicts (both channels compared)

Gate key as in `m1-ledger.md`. All outputs are in `probes/m1-delta/`. Mutations ran on a scratch copy of the tree;
every mutated file was restored and `cmp`-checked against the working tree.

| ID | Verdict | Evidence (command → output) |
|---|---|---|
| 1a | **SURVIVES on the bracketed events; REFUTED on one real event (BRK.B)** | `pd01`: oracle = `eps_estimate` Current-Quarter period end before vs after D. **1,290 bracketed events: 1,290 agree, 0 disagree** with the committed links. Falsifier: the same oracle on the pre-review rule finds **11 disagreements** (COST ×4, CSCO ×1, ORCL ×6), so it can fail. All 16 events that sit in two periods' windows (COST ×9, ORCL ×7) resolve to the oracle's period. Rebuild with the rule = committed links (`True`). **But** BRK.B 2024-09-30 is linked to `BRK.B:2024-11-01`, the Friday duplicate row with no label that ADR 0002 note 3 itself calls a duplicate, and not to `BRK.B:2024-11-02`, the real Saturday release (lag 32 < 33, so min-total-\|lag\| picks the duplicate; `pd02` S3 reproduces it). Effect in `events.parquet`: the duplicate carries `fiscal_period_end` and is excluded (`timing_not_checked`); the real release is in `mixed`, not excluded, with `fiscal_period_end = None`, so a sampled event has no EPS |
| 1b | **REFUTED (rule; not triggered by today's data)** | `pd02` (synthetic, `match_periods` called directly): **S1** a reporter with lag 66 and the Q2 report missing: Q1's report goes to the **Q2** period and **Q1 becomes the orphan**. **S2** the same reporter with **every report present**: the whole chain shifts by a quarter (12-31 orphan; 03-31←Q4, 06-30←Q1, 09-30←Q2; cost 177 against 263 unshifted). **S4** a Berkshire-shaped Q4 release on Sat 2025-03-01 (lag 60) with the Q1 row missing: the release goes to 2025-03-31 and 2024-12-31 is the orphan. The arithmetic (Channel A): the shift wins whenever the lag exceeds ~45 days and the event falls inside the next period's month, i.e. lag ≥ ~60. Today's data: max link lag 59 (BRK.B Q4), 0 links ≥ 60 (`pd01`), so no committed link is affected. COST 53-week, a year ending Jan 1, mid-month ends with a fast report and PLTR pre-IPO all link correctly (S5–S8). The ADR sentence "a whole chain never shifts … every shifted link costs about 90 days more" and the milestone page's "the first-of-the-month bound excludes it structurally" are false as general statements; they hold only while every lag is ≲ 45 days or the report stays out of the next period's month |
| 1c | **ACCEPTED (fallback mode)** | `pd02`: 20,000 random instances against a brute-force enumeration of all order-keeping one-to-one assignments with the same cost: `{'cost': 0, 'dup': 0, 'order': 0, 'window': 0}`. Falsifier: a greedy first-in-window matcher through the same checker: `cost: 5140`. `test_events_eps_link.py` test 1 (no event linked twice) passes on the committed table. Note: the 101 unlinked cost is unpinned (mutant M-e, 101 → 200, survives the whole suite, `pd05b`) |
| 2a | **ACCEPTED (fallback mode)** | `pd04`: in-memory `run.build` from the cache; `session`, `security`, `ticker_alias`, `events`, `eps` rebuilt **byte-identical** to `data/derived/`. `{'matched': 1324, 'orphan': 35, 'pre_calendar': 606}`, 1,965 rows, 0 ticker_conflict; `35 / (35 + 1324) = 2.5754%`. Orphans: 18 at 2021-12-31, COST 7, GS 3, AVGO 2, PLTR 2, 15 × 1, as the ADR says. `pd04b`: the sensitivity table of milestone 1 §6.5 reproduces row for row. Withdrawing the owner flag follows from ADR 0002's own threshold ("more than about 3%, counting orphan only") |
| 2b | **ACCEPTED (fallback mode)** | `pd05`: the first review's independent funnel (`probes/m1/p07`, ADR 0004 §1 written from the text) on the new tables: `[1353, 1320, 366, 356, 350]`; the 6 short baselines BRK.B:2025-05-03 (12, 11), COST:2025-05-29 (7, 6), COST:2026-05-28 (8, 7), GS:2025-04-14 (0, 0), MS:2025-07-16 (0, 0), PM:2026-04-22 (19, 18); **P3 359 / 366**, median 30, 50 securities. `pd05b`: a fresh export equals the committed `sample_funnel.json` and `meta.json` except `generated_at`. PR/FAQ line 73 says 350; ADR 0002 and the milestone page give 2.58%, 350, 359; every older number (348, 3.16%, 43, 1,316) still in the docs is marked as the pre-review value |
| 2c | **ACCEPTED (fallback mode)** | `pd04` byte-identity above |
| 3 | **ACCEPTED (fallback mode), one documented edge** | `pd06`: all 8,856 (date, label) cases 2019-06-01..2027-06-30 × {BMO, AMC, NULL}: sampled but outside `can_enter_sample` **0**; the scope is also not wider than needed (0). Falsifier: a scope on next(D) only hides 2 cases (2026-10-26 BMO/NULL). `pd04`: scoped 453 = build's `lookup_violations`; unscoped 482; the 29 dropped are all `sample = none` (22 labelled + 6 NULL after 2026-10-26, BRK.B:2020-02-28 NULL); **sampled not_checked events dropped: []**. Mutant M-b (scope removed) killed by 2 tests. Edge (Channel A): the scope is decided on the calendar's D; KO:2026-10-27 and V:2026-10-27 sit one day past the data end, and a look-up that moved one of them to 2026-10-26 BMO (MS moved by one day) would make it sampled. Not a defect while nothing is looked up after the data end |
| 4a | **ACCEPTED (fallback mode)** | `pd04`: every one of the 1,651 sessions in 2020-04-01..2026-10-26 lies in exactly one range; ORCL:2024-09-09 → day 0 2024-09-10, `coarse`, no exclusion |
| 4b | **SURVIVES for the function; the build's call is untested** | `pd06`: gap, overlap, empty, reordered, mixed→daily gap all refused with the stated message; a `daily` range past the data end is accepted (not part of the claim). `run.build` is the only place ranges become samples (`grep`). Mutant M-c (the `check_sample_ranges` call deleted from `run.build`) **survives the whole suite** (`pd05b`): the params test guards today's params, nothing guards the wiring |
| 5a | **REFUTED** | `pd08`: 2 controls killed (`open(__file__)`, `import urllib.request`); **all 15 other I/O forms survive `test_layering`**, among them the realistic ones: `from .. import store` + `write_table`, `from ..ingest import dolt` + `query`, `from earnings_vol.ingest import prices` + `prices.load` (a left-layer import that does file I/O), `np.load`, `np.savetxt`, `pd.read_pickle`, `df.to_pickle`, `pd.read_html` (network), `pd.read_feather`, `importlib.import_module("os")`, `__import__("socket")`, `io.FileIO`, `getattr(builtins, "open")`, `exec`. A relative right-layer import (`from ..measures import forward` in `events/eps.py`) also passes, so relative imports escape **both** checks |
| 5b | **ACCEPTED (fallback mode)** | `pd08`: with `events/` moved out of the package the test fails (`1 failed, 20 passed`); restored copy passes |
| 6a | **REFUTED (minor)** | `pd09`: accepted although reserved or malformed: `x@router.home.arpa` (RFC 8375), `x@…onion` (RFC 7686), `x@foo.alt` (RFC 9476), `x@corp.internal`; local parts `.x@`, `x..y@`, `x.@`, `%+-@`; a 64-character label; a domain over 253 characters. Controls `x@printer.local`, `x@example.com` refused |
| 6b | **REFUTED (minor, fails closed)** | `pd09`: refused although real: `contact first.last@gmail.com.` (a sentence ending in a full stop), a punycode TLD (`.xn--p1ai`), a Unicode local part. Ordinary forms (plain, `<…>`, apostrophe, long gTLD) accepted |
| 6c | **ACCEPTED (fallback mode)** | `pd09`: sockets, `getaddrinfo` and `requests.Session.request` blocked and counted; variable unset → `EdgarNotConfigured` twice and again with a cached file present; **0** attempts. Falsifier: with a contact set, the default `requests.get` path makes **1** (blocked) attempt |
| 7a | **ACCEPTED (fallback mode)** | `pd10`: a hidden file beside `.dolt`, a file in a new nested folder, an empty folder, a file in `.dolt/` and in `.dolt/noms`, a symlink: all **SEEN**. A dangling symlink makes `stat_fingerprint` raise `FileNotFoundError` (fails closed, not as `DoltWriteError`). A same-size overwrite with the mtime restored is unseen, by design of a stat fingerprint |
| 7b | **ACCEPTED (fallback mode)** | `pd10b`: unmutated `1 passed`; with `dolt.query` mutated to restore every mtime after the SELECT, `assert touched <= set(changed)` fails (`1 failed`) |
| 8a | **SURVIVES mechanically; provenance defects** | `pd11`: the committed CSV parses (20 rows); time present iff basis ∈ {time_stamp, announced_time} in every row; the parser refuses all 6 inconsistent mutants (time_stamp without a time, call_time / release_text with a time, announced_time without a time, a time contradicting the label, an unknown basis). But for 5 of the 9 `time_stamp` rows the time is not on the page the `url` names: NVDA, WFC, UNH (company pages with "no time stamp shown"; the time comes from an aggregator named only in the note) and **JPM and PM, whose time source is "read by the milestone-1 review", with no URL at all**. `source_kind` describes the URL, not where the time came from |
| 8b | **REFUTED for NFLX (1 of the 4 replaced URLs checked)** | Researcher (WebFetch/WebSearch, no sec.gov, 2026-10-29): **ORCL** PR Newswire page, the FY25 Q1 results release: right. **PM** pmi.com `newsId=28126` is the Q3 2024 results release dated October 22, 2024: right. **MS** businesswire.com URL returns HTTP 403; FinancialContent's Business Wire copy links back to the same release id `20241016758014` and is the Q3 2024 results release: right release, unreadable page. **NFLX** the URL is the 2024-09-13 **pre-announcement** "Netflix to Announce Third Quarter 2024 Financial Results", not the release; ir.netflix.net has no results press release (results are on its Quarterly Earnings page; the shareholder letter is dated October 17, 2024). The row is honest about this (`announced_time`), but the claim "pages for the right release" fails for it. NVDA, WFC, UNH not checked |
| 8c | **ACCEPTED on Channel A only (document fact)** | PR Newswire page shows "Sep 09, 2024, 16:05 ET"; "16:10" appears nowhere on it. Also: MS 2024-10-16 07:29 EDT (FinancialContent re-host of Business Wire only; official page 403); PM 06:59 EDT on StockTitan and Quantisnow re-hosts only (Business Wire 403) |
| 9 | **REFUTED** | `tools/licensing/scan_real_rows.py` → `clean: 0 lines flagged in 329 text file(s) … against 55 raw file(s)`. By hand plus `pd12b` (a scan that also reads one-decimal values, percentages, month-name dates and Python `date(Y, M, D)` literals): **`tests/test_measures.py:155` and `:158` hold `<a Cboe VIX close>` for `date(2025, 4, 17)`, which is FRED VIXCLS (Cboe) for 2025-04-17 exactly** (raw `VIXCLS.csv`: `2025-04-17,<a Cboe VIX close>`). The scanner misses it because its date patterns read only ISO and US dates, not `date(2025, 4, 17)`. The other 16 hits are coincidences (statistics, params, DTB3, which is US-government data). ADR 0002 and ADR 0003: no Yahoo, VIX or VX\* values; ADR 0002 Context item 2 keeps "≈ 270.41, within a few cents of the official close", a paraphrase rather than a value |
| 10 | **ACCEPTED** | `uv run --frozen pytest -q -p no:cacheprovider` → `305 passed, 36 warnings in 14.45s` (dolt tests included, none skipped) |

## 4. New defects (ranked)

1. **EPS links follow the nearest calendar row, not the release** (claim 1a): BRK.B's Q3 2024 EPS sits on the
   excluded duplicate `BRK.B:2024-11-01`; the sampled release `BRK.B:2024-11-02` (`mixed`) has none. Any duplicate row
   nearer to the period end will do the same.
2. **The min-total-|lag| rule shifts links for any lag ≥ ~60 days** (claim 1b): a complete chain shifts by a quarter
   (S2), and a missing report turns the previous quarter into the orphan (S1, S4). Not triggered today (max lag 59),
   but Berkshire's Q4 lags are 53–59 days and its releases fall on weekends: one release on 1 March with a missing Q1
   row reproduces S4. No test covers a lag ≥ 60, and the ADR and milestone page state the opposite.
3. **A Cboe VIX value in the tests** (`tests/test_measures.py:155,158`, <a Cboe VIX close> for 2025-04-17), and a licence scanner
   that cannot see Python `date(...)` literals, so it reported the tree clean.
4. **`test_layering` misses relative imports, left-layer I/O and most I/O functions** (claim 5a). Relative imports
   also escape the import-direction check.
5. **Press-release provenance**: 5 of 9 timed rows cannot be re-checked from their own URL (JPM and PM have no
   source URL for the time at all); JPM's URL is the call announcement and NFLX's the pre-announcement (data model
   line 183 asks for the release or its newswire copy).
6. **Untested wiring**: deleting the `check_sample_ranges` call from `run.build`, or changing the 101 unlinked cost,
   survives the whole suite (`pd05b`).
7. `is_real_contact`: special-use names and RFC-malformed addresses pass; a contact ending in a full stop is refused.

## 5. Bottom line

- **Most important fix:** the EPS match. Make it robust to the two shapes it gets wrong: (a) collapse or flag
  duplicate calendar rows of one release before matching (the BRK.B pair is in the data now), and (b) stop the
  pairing from trading a link to the next period when the lag is long: e.g. cap a link's lag at ~45 days *unless*
  the event lies before the next period's month, or cost a link by its distance from the security's median lag
  rather than raw |lag|. Add S1, S2 and S4 from `pd02` as tests, and correct the ADR and milestone sentences that
  say a chain cannot shift.
- **Delete:** the `<a Cboe VIX close>` VIXCLS value from `tests/test_measures.py` (replace with a made-up number), and teach
  `scan_real_rows.py` to read `date(Y, M, D)` literals.

## 6. Fixes applied

Applied 2026-10-29 on the same uncommitted tree; **not reviewed again**. Commands run from the repository root with
`uv run --frozen`. Every new test was mutation-checked on a scratch copy of the tree (never the working tree): the
code was broken, the named tests were seen to fail, and the bytes were restored (SHA-256 compared).

| # | Defect (§4) | What changed | Tests |
|---|---|---|---|
| 1a | Duplicate calendar row took the EPS link | `events.duplicate_rows`: rows of one security whose dates in use lie within `eps_match.duplicate_within_days` (14) are one release; the row with the strongest timing evidence (press release / EDGAR > calendar label > none) is kept; a tie stops the build. The others get `exclusion_reason = duplicate_row`, set first (in `build_events`), skipped by `build_eps`, given **no zone of their own** in other events' baselines (`export/funnel.py`), removed at the funnel's `timing_known` step; they stay in `events` and its prev/next chain. ADR 0002 §3 "Duplicate calendar rows", ADR 0004 §1, data model §3.7 | `test_events.py` (4 duplicate tests), `test_build_eps_never_links_a_duplicate_row`, `test_events_run.py`, `test_a_duplicate_row_blocks_no_session_and_leaves_at_timing_known`, `test_duplicate_rows_have_no_link_and_one_row_per_release_is_kept` (committed tables) |
| 1b | Long lags shift links (S1, S2, S4) | Window lower bound = first day of the period-end month **+ 14 days** (`params.yaml` `window_start: month_start+14`; `"month_start"` keeps meaning +0, an int a fixed lag). Chosen over "distance from the usual lag", which would depend on the links it decides. Over the 1,324 links the earliest report is 24 days after the first of its month (COST 2023-05-25), so 10 days of margin. A link can now reach the next period only from 74 days late (74–77 by month) | `test_s1_…`, `test_s2_…`, `test_s4_…`, `test_a_link_moves_to_the_next_period_only_from_74_days_late` (lags 73/74), bounds at 05-15/05-14, `test_the_rule_is_the_one_in_params` |
| 1c | False "never shifts" / "structurally" sentences | Replaced in ADR 0002 §3 (new "When a link can still move"), the milestone page §2/§6.5, `eps.py`'s header, the concept note and the data model §3.8 by the exact condition: next period only from 74 days late; then always if the next report is missing, and from 81–82 days if it is present 30 days after its period; a backward move never lowers the total without a duplicate row. Checked by `match_periods` itself: smallest moving lag 74–77 (next report missing) and 81–82 (present, lag 30) over every month of 2022–2024; 30,000 random chains with lags ≤ 73 and no duplicates: 0 wrong links; 30,000 with lags ≤ 100: 0 backward links | as above |
| 1d | Counts | Re-measured; **no published count changed**. Docs updated where the composition or a wrong statement changed (below) | — |
| 2 | Cboe VIX close in `tests/test_measures.py:155,158` | Replaced by a made-up 12.5. The scanner was not edited (instruction), so it still cannot read `date(Y, M, D)` literals; `pd12b` was re-run instead: 16 hits, all coincidences (DTB3, statistics, params), no VIX | `test_market_daily_carries_the_rate_but_never_vix` |
| 3 | `test_layering` deny-list | Allow-list for middle non-`run` modules: `PURE_STDLIB` (24 named modules), numpy, pandas, scipy, statsmodels, **exchange_calendars** (not in the brief: `events/calendar.py` needs it; it computes the XNYS rules in code), `params`, `schema`, middle modules of the own layer or to the left (not `run`). Relative imports resolved in both checks. Refused calls: `open`, `exec`, `eval`, `compile`, `__import__`, `getattr` and other dynamic access, numpy file functions, pandas `read_*`/`write_*` and the `to_*` writers, `__builtins__`. To pass it, `securities.build_ticker_alias` now takes the alias rows (from `events/run.py`), and `timing.parse_checks` reads the CSV without `io` (same 20 rows parsed, checked) | 47 tests; `pd08` re-run on a scratch copy: **all 17 forms KILLED**, vacuity check `1 failed`, restored copy `47 passed`; relative right-layer import: `2 failed` |
| 4 | Untested wiring (M-c, M-e) | `test_events_run.py`: `run.build` on a made-up one-company world (no cache, no network). **Decision: the unlinked cost stays derived, `lag_max + 1`, not a parameter**: it is the smallest cost that never gives a link up for nothing, and a larger one only pulls towards extra links; `test_an_unlinked_period_costs_lag_max_plus_one` pins it at 100/101/102 extra days | `test_build_stops_on_sample_ranges_with_a_gap`, `test_build_uses_the_window_parameter`, `test_build_marks_the_duplicate_row_and_links_the_release`, the cost test |
| 5 | EDGAR contact filter | Reserved: `home.arpa`, `.onion`, `.alt`, `.internal` added; local part may not start/end with a dot or contain `..`; label ≤ 63, domain ≤ 253. Fail-closed cases (trailing full stop, punycode TLD, Unicode) documented in the docstring and pinned as refused. `pd09` re-run: all required cases refused; still accepted: `%+-@realdomain.net` and the two non-RFC placeholders (out of scope) | 12 new refuse cases, 3 new accept cases (63-char label, 253-char domain) |
| 6 | Press-release provenance | NFLX `url` → the Q3 2024 letter to shareholders (dated 2024-10-17; Netflix issued no separate results release, its 2024 list has none between Sep 13 and Dec 9). JPM `url` → the earnings release PDF ("…net income of $12.9 billion ($4.37 per share)", read from the PDF). New column **`time_source`** (required with a time, only with one, `https://`): the `url` itself for ORCL, BAC, MU, PG; re-hosts showing date + time + EDT for NVDA (StockTitan), JPM, UNH, MS, PM (FinancialContent re-hosts of the Business Wire items) and WFC (Observer-Reporter re-host); for NFLX the pre-announcement (1:00 p.m. PT → 16:00 ET is our conversion). Business Wire and GlobeNewswire returned 403; done with WebSearch/WebFetch by a researcher sub-agent, no sec.gov, no personal data; the two PDFs were read by the implementer. JPM's 06:55 is the wire notice that results were out, not a time on the PDF | `parse_checks` tests (4 new refusals); `pd11` re-run: 20 rows parse, all 6 mutants refused |
| 7 | Verifier corrections | 2025-10 `option_chain` = **159,604** (parquet, its manifest and both `ingest_log.json` entries); 160,584's origin could not be traced (no ticker or date accounts for 980 rows); also corrected in data model §8. SKYD/VYLR: no `volatility_history` row at all at the pinned commit (queried on the private mirror), Yahoo caps present. The 50 companies' calendar ends 2026-12-01 (CRWD); the whole table 2026-12-04 (mirror query). Orphan partition and every `#L` link fixed (below). `LEARNING_LOG.md` L9 and L46 | — |
| 8 | Rebuild | `events.run`, `measures.run`, `export_app_data.py` (source_commit left `3636e98`), notebooks, sensitivity table; diagrams: specs unchanged, build `0 file(s) changed`, render gate passed | — |

**Measured after the fixes**

- `python -m earnings_vol.events.run` → `eps_match_status {matched: 1324, orphan: 35, pre_calendar: 606}`;
  `exclusion_reason {(none): 1259, duplicate_row: 1, outside_samples: 61, timing_not_checked: 32}`; look-up violations
  453 (unchanged: the duplicate still counts as a required look-up; a look-up of it would settle which row is the
  release). Diff against the pre-fix tables: `events` 2 rows (BRK.B:2024-11-01 `fiscal_period_end` 2024-09-30 → null,
  reason `timing_not_checked` → `duplicate_row`; BRK.B:2024-11-02 null → 2024-09-30), `eps` 1 row (BRK.B 2024-09-30:
  `BRK.B:2024-11-01`, lag 32 → `BRK.B:2024-11-02`, lag 33, consensus unchanged); `security`, `ticker_alias`, `session`,
  `session_snapshot` byte-identical; a second rebuild byte-identical. Six tables 277,479 bytes.
- Lags −6 to +59 (0 links ≥ 60, 7 negative, all COST). Orphans 35: 18 at 2021-12-31; COST 7, GS 2, AVGO 2, PLTR 2;
  ANET, MS, PG, WMT 1 each (2.58%).
- Funnel (`tools/export_app_data.py`): `1353 / 1320 / 366 / 356 / 350`, step 2 reason
  `duplicate_row|timing_ambiguous|timing_not_checked` (33 = 1 + 32); P3 **359 / 366**, median 30, 5th percentile 24,
  50 securities (a scratch call of `export.funnel.baseline_counts`). The JSON differs from before only in
  `params_hash`, the step-2 label and reason, and `generated_at`.
- `pd01` unmodified: committed links 1,290 / 1,290 agree; falsifier (window +10) 11 disagree; rebuild with
  `"month_start"` (+0) = committed: `True`; BRK.B:2024-11-02 now linked to the oracle's 2024-09-30. With `"month_start+14"`
  (scratch copy): the same, `True`.
- `pd02` unmodified (it pins `"month_start"`, +0): S1, S2, S3, S4 FAIL, S5–S8 OK, as before (the probe still detects
  the old window). With `"month_start+14"` (scratch copy): **S1, S2, S4 OK**, S5–S8 OK; S3 FAIL by construction
  (`match_periods` alone still takes the nearer of two rows; duplicates are removed upstream and tested there);
  brute force over 20,000 instances `{'cost': 0, 'dup': 0, 'order': 0, 'window': 0}`; greedy falsifier `cost: 3129`.
- First review's `probes/m1/p07` unmodified: `[1353, 1321, 366, 356, 350]`, P3 359 of 366, median 30, p5 24. Its
  step 2 is 1,321 because it predates `duplicate_row`; every later step and all six short baselines agree.
- `tools/eps_match_sensitivity.py`: every one-to-one row from −10 days to "first of the month + 21" gives 1,324 /
  35 / 606, max lag 59 (milestone 1 §6.5).
- Mutation checks (scratch copy): **30 of 30 killed**, M-e (`lag_max + 100`) and M-c (call deleted) among them, plus
  the window delay ±1, `unlinked = lag_max`, duplicate filter / branch / `<` / tie / ranking, the zone and step-2
  rules, three `time_source` rules, four reserved names, the dot rule, the 63/253/254 limits, four `test_layering`
  mutants, and `params` back to `month_start`. Also: in a copy of the committed `events.parquet` (schema kept), the
  duplicate flag removed from BRK.B:2024-11-01 → `1 failed`; and, to show the committed-table window assertion has
  teeth, its bound moved from +14 to +25 days in a scratch copy of the test → fails on COST 2023-05-25.
- `uv run --frozen pytest -q -p no:cacheprovider` → `370 passed, 36 warnings` (the 2 `dolt`-marked tests included;
  they query only the private mirror and a temporary repo).
- `cd app && npm run verify` → exit 0; lint clean; `Test Files  27 passed (27)`, `Tests  447 passed (447)`;
  statements 99.31%, branches 98.06%, functions 98.08%, lines 99.64%; built. Thresholds untouched.
- `uv run --frozen python tools/build_notebooks.py --check` → `OK: 2 notebooks … are in sync with src/`.
- `uv run --frozen python tools/licensing/scan_real_rows.py` → `clean: 0 lines flagged in 337 text file(s) of working
  tree against 55 raw file(s)`.
- Every `#L` link of milestone 1's page re-checked with a script: 49 links that name a function point at its `def`,
  the rest read by hand; the events.py, timing.py, eps.py, edgar.py and funnel.py references were moved to their
  current lines. The milestone-0 page's links were not touched (that page says its numbers move with the files).

**Left open:** the duplicate row still counts among the 453 required look-ups; GOOGL's URL is still its earnings-call
event page (`call_time`, out of this fix's scope); `scan_real_rows.py` still cannot read `date(Y, M, D)` literals;
`exchange_calendars` on the allow-list is a deviation from the brief, for the owner or reviewer to accept.
