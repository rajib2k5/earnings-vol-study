# Milestone 2 adversarial review: claims ledger

- **Reviewed:** the uncommitted working tree on top of `0409627` (milestone 2, "IV measures"), on 2026-10-29.
- **Protocol:** `evidence-gated-validation`, Tier 2 for every numeric claim. Default verdict for every claim: broken.
- **Mode, stated honestly.** Channel A (method and documents) ran as a separate sub-agent. It saw the claims and the
  code, never a probe output: [`probes/m2/channel-a.md`](probes/m2/channel-a.md). Channel B (runtime) ran in this
  context.
  - The claims and the probe designs were frozen first, in [`probes/m2/00-preregistration.md`](probes/m2/00-preregistration.md).
  - Channel A's report arrived while `p02` was running. So `p03`–`p16` were implemented knowing A's verdicts, and
    `p17` is a follow-up that was **not** pre-registered: it tests A's hypotheses.
  - Agreement between the two channels is therefore **dual-confirmed (fallback mode)**, never "independently proven".
- **Environment:** [`probes/m2/env-pin.txt`](probes/m2/env-pin.txt) (Python 3.12, numpy 2.5.4, scipy 1.18.1,
  pandas 3.1.0, pyarrow 26.0.0, exchange-calendars 4.13.2).
- **Isolation.** Every probe that mutates, rebuilds or stages runs on a scratch copy of the repository with a scratch
  `VOL_DATA_DIR`. Afterwards I checked that the working tree was unchanged:
  - `git diff --stat` is the same as at the start;
  - the `md5sum` of `data/derived/*.parquet` is unchanged;
  - no new folder appeared under `cache/stage/`.
- **No dolt, no sec.gov.** No probe runs `dolt`, and no request went to sec.gov.
- **How to re-run.** Every probe sits in `probes/m2/`. Its verbatim output is in `probes/m2/out/<probe>.txt`, with the
  scratch paths replaced by `<scratch>`.

## 1. Verdicts

The Gate column follows the skill's convergence table.

| # | Claim | Verdict | Channel B (runtime): what was run, what it printed | Channel A (docs/method) | Gate |
|---|---|---|---|---|---|
| 1 | Black-76 on mids inverts correctly, deep ITM/OTM, near-zero time value, bid = 0, crossed | **SURVIVES** | `p01`: `black76` against a textbook pricer (`scipy.stats.norm`) on k ∈ [−3, 3], w ∈ [1e-8, 4]: max error/F 0; parity residual 3.4e-15. Round trip on the OTM side, 290 points: worst relative error 9.3e-10 (at w = 1e-7). Prices at or beyond Black(w = 4) or Black(1e-8) give `None`. A synthetic chain with one OTM quote set to bid = 0, crossed, locked or NaN gives the same `w_atm` as the chain without that strike. Falsifier (d1 with +w): `falsifier_rc=1` | A2–A5 CONFIRMED: monotone in w, so the root test is exact; brentq tolerances are legal; ndtr is the normal CDF. A1 (Black 1976 text) UNVERIFIABLE: the paper was unreachable, but the analytic check passes | Accepted (fallback mode). Leaf A1 is documentary only |
| 2a | The 4 smallest \|C − P\|, **ties to the lower strike** | **REFUTED** | `p02b`: a decimal tie whose floats differ (0.005 against 0.004999999999999999) goes to the **higher** strike. `p02`, all 180,055 forwards: 109 rows pick a different 4th strike than the exact cents rule, and 89 forwards differ (max 0.43%). `p03`: IV changes by a median of 0.04 and a maximum of **2.99 vol points** (PLTR 2025-06-27, expiry 2025-07-25: 63.59% against 60.61%). `p17`: 1 daily event's day −1/0 measures read such a row. Mutant R1 (ties to the higher strike) **survives** every test | B2: Cboe breaks ties to the lowest strike; the ADR says the same (`0003:120-121`) | **Rejected**: both channels say the code does not do what the ADR states (`forward.py:51` sorts float gaps) |
| 2b | Stored `forward` = an independent recomputation from raw quotes | **SURVIVES** | `p02`: all 181,597 atoms recomputed from `option_chain` with no import of the measures code. Forward max \|diff\| **0** (same float tie rule). Status 181,597/181,597 agree | B1 CONFIRMED (Cboe Math Methodology §3(a)(ii)); median of 4 is a project choice with no source | Accepted |
| 3a | ATM w interpolated linearly in k between the nearest valid k_lo ≤ 0 < k_hi, 1.5-sd rule | **SURVIVES** | `p02`: 177,455 `bracket_linear` rows. Max relative difference in `w_atm` 1.5e-13; bracket strikes identical in every row | ADR 0003 §0 step 4; I#2 documented | Accepted |
| 3b | The quadratic fallback (293) is sound | **REFUTED as "sound"** (implementation exact; method weak) | `p02`: the 293 match my re-implementation to 1.8e-13. But **166 of 293 fit strikes on one side of k = 0 only** (pure extrapolation), and 178 of 293 fit exactly 4 points (1 residual degree of freedom). `p03` hold-out on 3,135 real `bracket_linear` expiries: hiding every k ≤ 0 strike sends 2,605 to the quadratic, with an IV error against the known bracket answer of median **+0.155**, p95 \|·\| 1.57, max 7.26 vol points, 10.8% above 1 point. Hiding only the lower bracket strike (3,055 stay linear) gives median \|·\| 0.13, p95 0.80. Caveat: real one-sided rows have a nearer strike (median \|k\| 0.0031), so the hold-out is harsher than production. Mutants C4 (call-site weights), R5 (window) and R7 (w_ref) **all survive** | I#1: the ADR says "inverse spread"; the code uses inverse **relative** spread (`chain.py:208`), undocumented | **Rejected** on soundness; minor: 8 of 366 daily events read a quadratic atom at day −1/0 (`p17`) |
| 4 | τ = XNYS sessions in (t, as_of(expiry)], half sessions = 1 | **SURVIVES** | `p04`: all 181,597 rows against `exchange_calendars` directly: 0 mismatches. The session table equals XNYS (24 early closes); 28,713 rows span an early close, each counted 1. `tau_cal_days`: 0 mismatches. Falsifier (+1): 181,597 mismatches, `falsifier_rc=1`. The 0.5 sensitivity is not built (stated) | F1, F2 CONFIRMED (XNYS early closes are sessions; `between` counts 1) | Accepted |
| 5 | `front_fixed`: T1\* = first expiry with τ ≥ 5 at day 0 | **SURVIVES** | `p04`: 1,170 events with pre and post; T1\* mismatches 0, IV mismatches 0. 727 listed at post; 442 not listed, of which 4 interpolated (never extrapolated). Mutant R2 (τ ≥ 4) killed. Notes: T1\* is not stored for the 30 events without a post session (`event_iv.py:187`); 26 events skip a shorter, listed, non-ok expiry (documented "among ok expiries") | I#3, I#4: "pre" not "day −1"; "ok" only. Both documented | Accepted |
| 6 | `cm30_iv` never blends a clean expiry with a spanning one | **SURVIVES** for interpolation and extrapolation; literally false for `two_component` | `p04`: every `ok` session recomputed: cm30 and blind 0 mismatches; 0 interp/extrap rows use both classes. Stored lo/hi classes: interp/extrap and flat_sigma single-class; **`two_component` (913) is clean lo / spanning hi by design** (ADR 0003 §b step 3). Mutant C1 killed | C1, C2 CONFIRMED (Cboe interpolates σ²T linearly in time). C3: the 10-session cap is a project choice | Accepted, with the `two_component` qualification |
| 7 | Spans ⇔ as_of(expiration) ≥ day 0, AMC on expiry day, Friday expiries | **SURVIVES** as implemented; the AMC-on-expiry-day premise is **UNRESOLVED** | `p04`: 0 mismatches on 181,597 rows against my own anchors. **No expiration in the data is a non-session**, so `as_of` never changes anything. 1,164 rows expire on a BMO day 0 and span. `p17`: 27 usable rows (7 events) expire on an AMC announcement date and are classed clean; 11 iv_daily rows use one as `cm30_exp_hi` in a clean interpolation, 2 as the clean leg of `two_component`, 0 in an E pair. Mutant C2 killed | E3a CONFIRMED. E3b REFUTED as an absolute: the exercise cut-off is 5:30 p.m. ET (FINRA 2360), and Cboe BZX declines to list such expiries because of post-close earnings volatility. E3c: `as_of` cannot change spans | BMO and Friday rows accepted. AMC on expiry day: the method is contested by A, and B measures a bounded effect (13 rows). Escalate as minor |
| 8 | E from the right pair; E ≤ 0 flagged, kept out of √E stats; the `sigma_d` fallback sound | **SURVIVES** (the fallback is untested) | `p04`: E, σ_d and `implied_move_status` recomputed on 57,749 sessions: 0 mismatches. 0 equal-τ pairs (`termstructure.py:149` has no guard). 0 pairs whose T2 spans the event after next. `p10`: the view's √E histogram uses the 344 with E > 0; √(mean E) over all 348, signed, = 7.58% (reproduced). `p17`: **207 of 19,573 E pairs skip a shorter non-ok spanning expiry** (undocumented). Mutant R4 (σ_d from the two *longest* clean) **survives** every test | D1 CONFIRMED against D-J (2004), §4.1.1. D3: D-J also need T2 before the next announcement (0 violations in B). D4: D-J zero out negative E; the ADR keeps it signed (documented) | Accepted. The fallback is untested |
| 9 | AAPL oracle E = 0.00088284, √E = 2.9713%, from the same inputs; the test is not circular | **SURVIVES** | `p09`: an own pricer, exact-cents forward, own bisection and XNYS sessions, on `worked.py`'s quotes only (read with `ast`). Result: F 271.4213 / 272.0582 / 270.5490 / 270.9454; **E = 0.00088284, √E = 2.9713%**, σ_d 0.2442, total 2.6697%, realised −0.3112%, front crush −0.1787. Falsifier (all strikes): E = 0.00069327, `falsifier_rc=1`. The test asserts literals and reads only quotes from `worked.py`. Its helper `price76` is independent (`scipy.stats.norm`, pinned to 7.965567) | The oracle values are from ADR 0003 §c | Accepted |
| 10 | Funnel 1,353/1,320/366/356/354/348; `iv_usable` and the baseline change right; terciles; 285 missing for the stated reasons | **SURVIVES**, with one finding: **the baseline change is inert** | `p10`, with no funnel code imported: [1353, 1320, 366, 356, 354, 348]. `iv_usable` drops ABBV:2025-01-31 and LIN:2025-02-06. Terciles: 9/9 rows equal the JSON. Falsifier (baseline counted by snapshot only, the milestone-1 rule): **also 348, with the same 6 drops** (`falsifier_rc=1` = "mutant gives 348"). So 350 → 348 comes entirely from the new step; the cm30 rule is guarded only by unit-test event G. `p10b`: 285 = coarse 228 (88 no common forward, 140 an end without a snapshot), none 36 (28 after the data end), daily 14, mixed 7. Mixed includes 1 `duplicate_row` (BRK.B:2024-11-01), which the doc does not mention | ADR 0004 §1 rule 2 requires the cm30 | Accepted. The baseline rule's effect on real data is nil |
| 11 | P4, P5, P6, the leak | **SURVIVES** for the headline numbers; **two figures in the walkthrough are wrong** | `p10`: AAPL n = 6, median 4.76%; MSFT n = 7, median 5.45%. P5: 4/348 = 0.0115. Leak (sessions 22–60): n 33,801, mean +0.225, p95 1.37, 75.8% equal; 1–21 sessions: −0.219 (n 19,045). On proper ADR 0004 clean baselines: +0.286. `p11`: P6 n 53,083, mean −0.163, median −0.113, below 72.5%; session clock +0.701. **Clock explanation holds:** vendor − ours(cal) is uncorrelated with τ_cal·252/(τ·365) (corr +0.025), while vendor − ours(session) correlates −0.818; the vendor's implied T·365/τ_cal has median 1.0074. Errors: (i) "whole primary sample: median 6.45%" is the median over the **344** with E > 0; over 348 (E ≤ 0 as 0) it is 6.27%. (ii) "\|r₀\| / implied above 1 for **38.2% (332)**" is 133/348; of 332 it is **40.1%** (`p11c`) | The ADR rejects E > 0-only averages | Accepted. The two wording/number errors are in `02-iv-measures.md:214, 261` |
| 12 | Byte-identical rebuild; `chain_expiry` local, 17 MB | **SURVIVES** | `p12`: fresh scratch `VOL_DATA_DIR` (copied extracts and raw files), the 9 derived files deleted, then events → snapshots → iv. Result: "byte-identical: 9 files". Stage `chain_expiry`, `iv_daily` and `event_iv` are identical to the local stage. `chain_expiry` is 16,965,282 B and not in the index. (IV stage wall 152 s here, against 50.7 s claimed: machine load) | — (runtime-only claim) | Accepted (B only, by the nature of the claim) |
| 13 | Contract 0.3.0 consistent; the app only draws; coverage | **SURVIVES**; provenance caveat | 0.3.0 appears in `contract.py:27`, `contract.ts:21`, `app/DATA.md:6`, data-model §4 and all three JSON files. `npm run verify` on a scratch copy: 29 files, **675 tests passed**, coverage 99.48 / 98.6 / 98.45 / 99.72, build OK. The pages compute only bar heights and widths. Caveat: every JSON says `source_commit`/`code_commit` **0409627**, the milestone-1 commit, which does not contain the code that produced these numbers | — | Accepted |
| 14 | Tests meaningful; 5 of 47 mutants; no re-implementation | **PARTLY REFUTED** | `p14` on a scratch copy, every file restored and SHA-256 checked. Claimed mutants: C1, C2, C3 and C5 KILLED. **C4 "quadratic unweighted" SURVIVES when planted where the atom chooses its weights** (`1/rel` → ones, or → `rel`). It is killed only inside `_wls_quadratic_intercept`. The test `test_quadratic_fit_is_weighted_by_inverse_spread` tests the helper, not the atom. Own mutants: R2, R3, R6 killed; **R1 (tie direction), R4 (σ_d fallback pair), R5 (quadratic window), R7 (w_ref) survive**. No test re-implements code under test as its own oracle. One mild circularity: the second half of `test_synthetic_truth_is_recovered` builds its inputs with `chain.tau_sessions` | — | Rejected for the claim that the tests pin the fallback, tie and weight rules |
| 15a | DATA.md states each source's terms accurately | **REFUTED** | `p15`/reads: `data/derived/LICENSE:3-4` says "Everything in this folder" is CC BY-SA, and `:29-30` says no Yahoo data is in the repository. **`timing_check.parquet` (Yahoo-derived `gap_verdict_yf`) is now in that folder.** `meta.json` (About page) says Yahoo data is "never committed" with `committed: false` (`tools/export_app_data.py:78-83, 102-103`). `sample_funnel.json` exports a Yahoo-derived share. DATA.md's Yahoo row gives no restriction | G1 CONFIRMED (DoltHub CC BY-SA at the pinned commits). G2–G5: the one-liners are accurate but omit restrictions (Yahoo no redistribution; Cboe no distribution or verification use). **Escalate** | **Rejected**: notices contradict each other |
| 15b | `check_data_files.py` reads the index, catches renamed copies, cannot be bypassed by folder or extension | **REFUTED** (holds only for exact local copies) | `p15` on a scratch copy's index. **Caught:** an exact AAPL Yahoo file as `docs/notes.txt` (T1) and exact DTB3 as `Raw/DTB3.CSV` (T7). **Passed:** the same with no vendor folder, as in CI (T2, T7b); gzip (T3); +1 byte (T4); **a whole raw `option_chain` month re-serialised, 72,465 rows, 383 KB (T5)**; the stage `market_daily` with the class-R VIX column (T6). No git hook exists. The 4 new M2 data files are untracked, so today's "every test run" check has not seen them (staged with `git add -A` they pass, T0b) | H: reads `git ls-files -s -z`; the docstring (`:19-21`) itself admits CI and edited copies | **Rejected** |
| 15c | No committed file is bulk raw or over the limits | **SURVIVES** | `p15` T0b, everything staged: clean. Largest blob `iv_daily.parquet` 4,721,282 B | — | Accepted |
| 16 | Layering allow-list holds for the new modules | **SURVIVES** | `p16`: imports of the 9 new or changed middle modules (own AST walk) are stdlib/numpy/pandas/scipy or the same or left layers. `test_layering.py` passes 47 and fails when `pyarrow` is planted in `iv_view`, an export import in `termstructure`, or `to_parquet` in `report` | — | Accepted |

Also re-run: the Python suite on a scratch copy gives `439 passed, 48 warnings`.

## 2. Further defects nobody asked about, by severity

1. **Compliance (major; escalate).** The data notices contradict each other since `timing_check.parquet` was committed
   and the Yahoo-derived share was exported:
   - `data/derived/LICENSE:3-4, 29-30`;
   - `meta.json` `data_licence.attribution` and the Yahoo `committed: false` entry, which the About page shows;
   - `app/DATA.md:114, 127-129`.

   ADR 0001 §7 is inconsistent as well:
   - its allow-list (`0001:301-305`) omits `timing_check`, `event_iv` and `session_snapshot`;
   - its guard list (`0001:270`) still says no `_yf` column in `data/derived`.

   Channel A adds two terms the notices never state: Yahoo bars redistribution, and Cboe bars distributing its data
   or using it to verify other data. The second may conflict with the VX\* validation plan.
2. **Process (major).** The data-file gate can be passed by any transform of a raw file:
   - a re-serialised raw quote month (T5) passes, which is exactly the "raw `option_chain` rows" the owner banned;
   - in CI, rule 5 is skipped;
   - nothing runs at commit time.
3. **Forward tie-break (minor-moderate).** 109 forwards break an exact cents tie the wrong way (`forward.py:51`), up
   to 3 vol points on one atom. No test pins the tie rule.
4. **Quadratic fallback (minor).**
   - 57% of its uses are one-sided extrapolation, with a measured upward bias.
   - Its weights differ from the ADR text: relative spread, not spread.
   - Its weights, window and w_ref are unpinned by tests.
5. **Wrong figures in the walkthrough (minor).**
   - `02-iv-measures.md:214`: 38.2% should be 40.1% (n = 332).
   - `:261`: the "whole sample" median is over E > 0 only, the selection ADR 0003 §c warns against.
6. **Provenance (minor).** The JSON `source_commit`/`code_commit` name `0409627` for numbers produced by uncommitted
   milestone-2 code.
7. **AMC-on-expiry-day expiries classed clean (minor).** 7 events, 13 iv_daily rows; contested by the exercise
   cut-off (row 7).
8. **Documentation inaccuracies (minor).**
   - ADR 0003 `:144` says "the lower end always holds". That is false for F > 1,253: 2,437 rows of AMZN, AVGO, GOOGL,
     LLY and NFLX. It is harmless, because `has_root` checks both ends.
   - `data-model.md:431`: `n_strikes_valid` counts strikes with a root, not "passing the quote filter".
   - `data-model.md:451` and the walkthrough: "`df` is a FRED value, so it stays local". This contradicts
     `data-model.md:196` (DTB3 may be committed), and `iv_daily` is computed with the same DF. The real reason is the
     size.
9. **Undocumented choices (minor).**
   - 207 E pairs skip a non-ok spanning expiry.
   - T1\* is left null when post is missing (30 events).
   - `event_variance` has no equal-τ guard (0 cases today).

## 3. The single most important fix

Make the licence notices true before anything is pushed. Either:

- drop `timing_check.parquet` and the exported `share_gap_contradicts` from the commit; or
- rewrite `data/derived/LICENSE`, the `meta.json` attribution and `committed` flags, and `app/DATA.md`, so that they
  name the Yahoo-derived label and its terms, and have the owner confirm that Yahoo's terms allow it.

Today the repository publishes a statement ("no Yahoo data anywhere in this repository") that this milestone made
false.

**The one item to delete:** `data/derived/timing_check.parquet`, together with the committed `share_gap_contradicts`
that depends on it. It is the only committed third-party-restricted value. It feeds one share per tercile, from 20
look-ups, which ADR 0002 §3 says cannot show a trend yet. And it is what makes three licence notices false.

## 4. Not verified

- Black (1976), the 2019 RFS version of Dubinsky-Johannes, Merton (1973) and the OCC By-Laws were unreachable
  (Channel A, "What could not be reached").
- Whether Yahoo's and Cboe's terms permit the committed and planned uses is a legal question. It is left to the owner.
- The IV stage's 50.7 s timing was not reproduced. This machine took 152 s under parallel load, and the claim was not
  under attack.

## 5. Fixes applied

Applied 2026-10-29 by an implementer sub-agent, in the working tree on top of `0409627` (nothing committed). The
sections above are left as the review wrote them. Scratch scripts and their outputs live under
`$VOL_DATA_DIR/earnings-vol-study/cache/m2fix-scratch/`, outside the repository. The probes in `probes/m2/` were re-run
unchanged, never edited.

| Claim | Fix | Test (mutation result) |
|---|---|---|
| 15a | **Notices made true and consistent.** `timing_check.gap_verdict_yf` is kept. `data/derived/LICENSE` and `README.md` now say: CC BY-SA 4.0, except `gap_verdict_yf` and `security.in_universe`, which are Yahoo-derived and under Yahoo's terms. They also say that the IVs and moves use FRED `DTB3` as an input, with FRED's citation, and stay CC BY-SA, that no Cboe value is committed, and that the timing labels come from documents (class F). `tools/export_app_data.py`: FRED split into `FRED DTB3` (committed: true, public domain) and `FRED VIXCLS (Cboe VIX)` (false). Yahoo is committed: true, Cboe false. The attribution names the Yahoo labels and the FRED citation. Also updated: `app/DATA.md`; ADR 0001 §6 and §7 (the guard list, the class-R line, the suffix line, the allow-list of 9 committed tables, the app JSON line); data model §1.3, §2, §2.1 and a new §6 item 8 (Cboe's terms against VX\* validation, an owner question); root `DATA.md` (one line per source on what its terms restrict, "not checked" where uncited). `meta.ts` needed no change: its consistency rule still holds | `test_the_committed_flags_say_what_the_registry_lets_into_the_repository` replaces `test_cboe_and_yahoo_are_never_committed`; `app/src/test/publicData.test.ts` now asserts Cboe never, Yahoo committed, and every committed source named in the attribution |
| 15b | **Gate extended**, keeping the index reading and rule 5. Rule 6 is an allow-list: `data/derived/` holds only the registry's committed tables, each with exactly its committed columns (read from the staged blob), plus README, LICENSE and the calendar JSON. `app/public/data/` holds only `<kind>.json` for `contract.KINDS` (new), with a matching `kind` field. Rule 7 refuses archives (`.gz .zip .bz2 .xz .7z .tar .zst .tgz`) anywhere. Rules 1–3 and 7 now compare in lower case. The docstring lists what still passes | `test_refused_paths` (+19 cases, 31 in all: gzip and the other archives, an unregistered parquet, `market_daily`, `chain_expiry`, case variants), `test_a_re_serialised_table_or_a_local_table_is_refused_without_the_vendor_folder`, `test_a_gzip_copy_of_a_vendor_file_is_refused_with_or_without_the_vendor_folder`, `test_an_app_file_must_carry_its_own_kind`, `test_the_allow_lists_follow_the_registry_and_the_contract`. Mutants G1–G7 all killed |
| 2a | `forward_from_pairs` ranks the integer 2\|C − P\| in cents (`np.rint(200·\|C−P\|)`), so an exact tie goes to the lower strike. "Whole cents" is applied to the bid + ask sums: \|C − P\| itself sits on a half-cent grid, and rounding it to whole cents would invent ties (0.015 and 0.025 both give 2). All 16,348,450 bid/ask values in the 82 extracted months are whole cents | `test_forward_breaks_an_exact_cents_tie_to_the_lower_strike` (0.005 against 0.004999999999999999; F = 98.7475, not 100.0). F1 (float ranking) and F2 (the review's R1) killed |
| 3b | **Decision:** the quadratic runs only for a too-wide bracket, and only when its window holds a valid strike on each side of k = 0. With no bracket, or a one-sided window, the status is `no_atm`: the ATM w is never extrapolated. The window is drawn around the bracket's linear w (the nearest-strike path is gone). Weights stay 1/relative spread, and ADR 0003's text was fixed. Evidence, from a hold-out on all 177,388 `bracket_linear` τ ≥ 5 expiries of the old stage: one-sided fits p95 1.53, max 41.6 vol points (286,742 fits). On 2,812 too-wide brackets, the two-sided quadratic gives p95 1.15 and median −0.11; linear across the same brackets gives p95 1.16 and median +0.22. Of three weightings, 1/relative spread has the smallest median \|·\| (0.199, against 0.239 for 1/absolute spread and 0.215 unweighted) and max; its p95 ties the unweighted fit's (1.148 against 1.146). The review's probe `p03`, re-run on the fixed code against the old stage: one-sided 3,109 `none`, 26 bracket; wide 3,055 bracket (p95 0.80), 24 quadratic (p95 1.18, max 1.49), 56 none. Recorded in ADR 0003 §0 step 4 | `test_atom_quadratic_window_weights_and_reference_w` (a = 0.0043709131, from `numpy.polyfit` outside the code), `test_atom_never_extrapolates_from_one_side_of_the_money`. Q1 (one-sided window), Q2 (the pre-review ATM block), Q3 (weights = ones, the review's C4 at the call site), Q4 (weights = rel), Q5 (3 sd, R5), Q6 (nearest strike's w, R7): all killed |
| 7 | An expiry spans when `as_of(expiration)` ≥ `spans_from`, the first session on or after D (`tables.Anchor`, `tables.spans`): D itself for AMC and for unlabelled events, day 0 otherwise. `front_fixed` uses the same rule at post. The horizon test still counts to day 0 (documented). ADR 0003 §b, data model §3.5 and §3.6 | `test_an_expiry_on_an_amc_announcement_day_spans_the_event` (AMC, BMO, Saturday cases). A1 (`spans_from` = day 0) killed; A2 (`>`) killed. **A3 survives:** `front_fixed` with the old day-0 rule at post. It is equivalent in practice: when the rules disagree, interpolation in the class without extrapolation gives no value either way, unless two expirations share T1\*'s last session (milestone page appendix) |
| 8 | The fallback is pinned. ADR 0003 §c ("Which expiries") and data model §3.6 now say that T1 and T2 are the two shortest usable spanning expiries: a `no_atm`/`no_forward` one is skipped, because E needs each w and any two spanning expiries identify E. Re-measured: **235 of 19,601** E rows skip one (p17 (b); 207 of 19,573 before the fixes) | `test_sigma_d_without_e_comes_from_the_two_shortest_clean_expiries`. S1 (two longest, the review's R4) and S2 (first and last) killed |
| 14 | The worked example lists 5 mutants. All five re-run (W1–W5) and killed. The milestone page now counts 67 header mutants: 49 from the build and 18 from these fixes | — |

**Mutation run** (scratch copy of the repository, no bytecode, every file restored and SHA-256 checked): 25 mutants,
**24 killed, 1 survived (A3, above)**.

**Numbers that changed** (old → new). Rebuilt with `uv run --frozen python -m earnings_vol.events.run`, `… -m
earnings_vol.measures.run --only snapshots`, `… --only iv` and `uv run --frozen python tools/export_app_data.py`.
The params hash is unchanged (`8286751e4eaca31e`), so the stage was rebuilt in place, and the old stage was copied out
first for the comparison. The seven tables of the events and snapshot stages came out byte-identical. A second IV run
was byte-identical on 12 files.

- Forwards: 89 of 180,055 changed, by at most 0.5633 (0.43%). The IV of those 89 expiries changed by a median
  \|·\| of 0.052 and at most 2.99 vol points (PLTR 2025-06-27, expiry 2025-07-25: 63.59% → 60.61%). No row changed
  method or status through the forward.
- `chain_expiry`:
  - `ok` 177,748 → 177,582; `no_atm` 2,307 → 2,473; `quadratic` 293 → 127 (166 → `none`);
  - `straddle_gap` 36,105 → 36,104; `fwd_dispersion` 13,151 → 13,147;
  - `spans_next_event` changed in 157 rows (141 usable): 31 for 7 AMC events and 126 for 16 `timing_not_checked`
    events;
  - file 16,965,282 → 16,963,711 B.
- `iv_daily`:
  - front IV 57,638 → 57,633; `cm30_iv` 57,110 → 57,087; `cm30_blind_iv` 57,279 → 57,265; E 19,573 → 19,601;
  - methods: `interp_clean` 27,163 → 27,098, `interp_spanning` 16,298 → 16,328, `extrap_clean` 10,081 → 10,093,
    `extrap_spanning` 1,834 → 1,817, `two_component` 913 → 893, `flat_sigma` 821 → 858, `none` among `ok` sessions
    639 → 662;
  - `negative_forward_variance` 36 → 34; file 4,721,282 → 4,722,263 B.
- `event_iv`: with a 30-day crush 1,148 → 1,146; file 174,067 → 174,095 B.
- **Funnel:** `iv_usable` 354 → 353 (RTX:2025-04-22 dropped: its day-0 front expiry was a one-sided quadratic);
  primary **348 → 347**.
  - The baseline cm30 rule is still inert: the review's `p10 --mutant-snapshot-baseline` also gives 347, with the same
    six drops.
  - E ≤ 0: 4 of 347 (share 0.0115, unchanged).
  - Terciles: daily 2 crush −0.192 → −0.1937; daily 3 n_crush 118 → 117; coarse 2 n_crush 204 → 203 (other means in
    the 4th decimal).
- `iv_measures.json`:
  - √E: n 344 → 343; p10 3.27%, p25 4.47 → 4.46%, median 6.45%, p75 8.78 → 8.77%, p90 11.10 → 11.09%;
  - √(mean E) 7.58 → 7.51%;
  - crush: n 348 → 347, mean −0.2005 → −0.2009, median −0.1885 → −0.1888, p10 −0.3425 → −0.3427, p90 −0.0632 → −0.0634.
- Primary-sample figures (`p11c`):
  - dsigma median −0.0017 (261) → −0.0022 (262);
  - \|r₀\|/implied median 0.815 → 0.816, above 1 for 133 of 332 (40.1%; the page said 38.2%);
  - no front-fixed crush 84 of 348 → 83 of 347;
  - P4 whole sample: median 6.45% over the 343 with E > 0; 6.27 → 6.33% over all 347.
- P6 (`iv_report.json`, `p11`): n 53,083 → 53,135; the means and medians are unchanged at the stated rounding.
- Leak (`p10`): n 33,801 → 33,786, mean +0.225 → +0.227, p95 1.37, equal 75.8 → 75.7%; 1–21 sessions −0.219 → −0.217
  (n 19,045 → 19,038).
- `p17` (d): a daily event's day −1/0 measure reading a quadratic row: 8 → 1.

**Documents.** The milestone page:

- every number above and the gate lines;
- :214 → 133 of 332 = 40.1%;
- :261 → the denominators (343 with E > 0; 347 all);
- the inert baseline rule;
- the mutation counts per module header;
- every `file:line` (including `export_app_data.py:203` and `event_iv.py:132`);
- the `chain_expiry` "FRED" reason;
- the DTB3 wording: `r_cont` 3.83% from a raw 3.76%.

Elsewhere:

- ADR 0003: the review note, §0 steps 2–4, §b, §c and the :144 correction;
- data model :431 and :451, and a review note;
- `README.md` status and results (347);
- PR/FAQ 347;
- `LEARNING_LOG.md` :9, the milestone-2 Page cell and :51;
- `docs/architecture/README.md` :99, :184–185 and :698 (15 stored tables, 9 view files, contract 0.3.0; the 11 built
  tables re-checked against `erd.yaml`: 155 columns equal), and `architecture.yaml:84`;
- concept notes 06 and 07.

**Gates** (last runs):

- `uv run --frozen pytest -q -p no:cacheprovider`: `467 passed, 48 warnings in 72.38s (0:01:12)`;
- `cd app && npm run verify`: lint clean, `Test Files 29 passed (29)`, `Tests 675 passed (675)`, coverage
  99.48 / 98.6 / 98.45 / 99.72, `✓ built in 2.60s`;
- `uv run --frozen python tools/build_notebooks.py --check`: `OK: 3 notebooks … are in sync with src/`;
- `uv run --frozen python tools/licensing/check_data_files.py`: `clean: no raw vendor file and no oversized data
  file`. The same result with every file staged in a scratch index; the real index was not touched;
- diagrams: `ok: 5 spec(s) up to date in docs/architecture/out`, and the Mermaid 12.2.0 render gate passed on all 5
  specs;
- `scan_real_rows.py`: 2 lines flagged, both the requested raw DTB3 3.76% quote.

**Not done, or left to the owner.**

- `source_commit` / `code_commit` still name `0409627`, as asked: the owner re-exports after the commit.
- `app/CLAUDE.md` still says "no CBOE or Yahoo data … in `dist/`". The app now ships the Yahoo-derived
  `share_gap_contradicts`. That file is agent configuration, so it was not edited.
- Rule 6 does not cover `data/manual/`, so T4 (an edited vendor copy there) still passes.
- History and commit hooks are not checked.
- Whether Yahoo's terms allow the two committed labels, and whether CC BY-SA §3(b)(3) allows carving them out of the
  CC BY-SA folder, are legal questions for the owner. So is Cboe's verification clause (data model §6 item 8).
- VX\* validation is not built.
