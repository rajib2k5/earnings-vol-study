# Milestone 4: what drives the crush, and implied against realised moves

- **Status:** built; adversarially reviewed ([ledger](../validation/m4-ledger.md)) and fixed (§9; a delta review of
  the fixes has not run); pending the owner's review. **The timing labels are provisional**: 20 of the 473 required press-release look-ups are done, and every other event keeps the calendar's
  label until SEC EDGAR runs. Every result on this page, in `results.parquet` and in the app depends on those labels.
- **Date:** 2026-10-29
- **Scope:** the regressor columns of `event_measures` that milestone 3 left null; OLS with two-way clustered
  inference (`stats/regression.py`); the crush regression of H5 and H6 and the implied-against-realised test of H7
  (`stats/drivers.py`); **gate G1 for H5–H7, run before any H5–H7 result**; Holm over the declared family H1–H7
  (fixed after review, §9 R1); the milestone-3 open item on the crush's ρ̂̄ = 0.30; contract 0.5.0 with `drivers.json` and `implied_vs_realised.json` and two app
  pages; the notebook `04_drivers`.
- **Source of truth:** [ADR 0005](../adr/0005-statistical-test-suite.md) §3–§5 (the regressions, H5–H7, gate G1,
  the reference-distribution check), [ADR 0003](../adr/0003-iv-measures.md) §c "Units" (H7's regressor),
  [ADR 0004](../adr/0004-baseline-and-event-windows.md), the [data model](../architecture/data-model.md) (§3.11 the
  regressor columns, §3.13 `results`, §4 the contract) and the code. Where a document left a choice open, §2 records
  the choice; the owner can override each one.
- **Where this fits:** [LEARNING_LOG.md](../../LEARNING_LOG.md) is the index. New concept notes:
  [regression with two-way clustered errors](../concepts/13-regression-with-two-way-clustered-errors.md),
  [implied against realised moves](../concepts/14-implied-against-realised-moves.md),
  [a common factor in single-stock IV](../concepts/15-a-common-factor-in-single-stock-iv.md).

---

## 1. What we built and why

Milestone 3 measured the crush (−0.199 log points) and tested its mean. Milestone 4 asks what makes a crush larger
or smaller, and whether the move the options priced matches the move the stock made. ADR 0005 declared three more
hypotheses for that, before any data was seen:

- **H5**: β of |SURP| (the earnings surprise in price units) is 0 in the crush regression;
- **H6**: β of the prior volatility level, ln σ_d at day −1, is 0 in the same regression;
- **H7**: in r₀² = a + b (E + σ_d²/252) + u, a = 0 and b = 1 (the implied variance is unbiased for the realised one).

What was built:

1. **The regressor columns** of `event_measures` (`panel/regressors.py`): `price_ref`, `surprise_scaled`,
   `abs_surprise_scaled_w`, `sue_hist`, `sue_hist_n`, `vix_regime` (committed) and `realized_ret_0_yf`, `ln_mcap_yf`
   (Yahoo, class R, local). Every earlier table is byte-identical; `event_measures` changed in these eight columns only.
2. **OLS with one-way and two-way cluster-robust inference** (`stats/regression.py`), pure numpy like
   `stats/clustering.py`, checked against a hand-worked 4-event case and against statsmodels with `use_t=True`.
3. **The driver models** (`stats/drivers.py`): the primary crush regression of H5 and H6, its mean-adjusted twin,
   H7's regression and Wald test, the share of moves beyond the implied |move|, and eight exploratory variants that
   ADR 0005 §3 names.
4. **Gate G1 for H5–H7** (`stats/g1_drivers.py`, wired in `stats/run.py`): 2,000 seeded null replications per design
   at the real design, before the results run. **All three primaries failed** (§6.1): their statistics are liberal
   at this design. ADR 0005 declared G1's size designs for H1–H4 only, so the failed check is printed beside H5–H7's
   rows and they stay in the declared Holm family with their real p-values (§9 R1: the first build dropped them, an
   undeclared choice). No substitute statistic was promoted.
5. **`results`** (927 rows): 62 regression rows, Holm over the declared family H1–H7, H2's season-cut row
   recomputed with that family, 5 descriptive rows `holm_post_gate` with the Holm p over the family without the
   hypotheses whose G1 check failed (H1–H4, and H2's season cut; a sensitivity, not binding), and G1's H5–H7 rates
   and H7 calibration. The run refuses a G1 report without a verdict for every hypothesis it writes rows for (§9 R2).
6. **The ρ̂̄ investigation** (`stats/common_factor.py`, `research/prototypes/rhobar_crush.py`): the crush baselines'
   ρ̂̄ = 0.30 is one common date component, linearly unrelated to Δln VIX, spread over most dates; no stale snapshot
   is involved (§6.6, softened after review). H1's primary is unchanged.
7. **Contract 0.5.0**: `drivers.json` and `implied_vs_realised.json`; the app's Drivers page (coefficients with their
   intervals, gate G1 for H5–H7, Holm and its post-gate sensitivity) and Implied vs realised page (a scatter of the implied |move| against the
   realised one). Built by a delegated agent, checked here by `npm run verify` (§6.10).
8. **The notebook** `notebooks/04_drivers.ipynb`, generated by `tools/build_notebooks.py`.

---

## 2. Why this design: the decisions table

Choices the ADRs and the data model leave open, and the ones this milestone added. The owner can override each.

| # | Choice | Alternatives | Why | Cost |
|---|---|---|---|---|
| 1 | `price_ref` at **event_iv's pre session** (day −1 in `daily`; the nearest observed in `coarse`) | the calendar day −1 | The same session as E, σ_d and SLOPE; every eligible daily event has pre = day −1 | A coarse event's price can be from day −2 |
| 2 | \|SURP\| winsorised over **every event of the same `events.sample` with a `surprise_scaled`**, excluded events included, numpy's linear quantiles | the eligible events only | The data model says "the events with the same `events.sample`"; the cut points do not then depend on eligibility | none measured |
| 3 | SUE_hist: the previous quarters are the **earlier events of the security with a `surprise_scaled`**, by effective day 0; sd with ddof 1; an sd of 0 gives null; `sue_hist_n` null when `sue_hist` is | count orphan quarters too | Only a priced surprise can be compared with one | 339 of the 347 primary events get one |
| 4 | `vix_regime`: terciles **within each `events.sample`**, over its events with a VIX close at day −1; a value on a cut point goes to the lower bin; `none` gets null | terciles over all samples | "VIX tercile at day −1 over the sample" | daily: 127 low / 118 mid / 121 high |
| 5 | SIZE = ln(market cap on the rank date) + ln(close(day −1) / last close), **split-adjusted Yahoo closes** | download Yahoo's share-count history | Local raw files only (the brief prefers them); the only cap the project holds is the rank date's | Assumes the rank date's share count: buybacks and issues are ignored (not measured) |
| 6 | `realized_ret_0_yf`: Yahoo close-to-close from pre to post with the post-day dividend added back | without the dividend | A cross-check of `realized_ret_0` | Local only (class R) |
| 7 | H5/H6's event set: **H1's set with every regressor present** (347); H7's: H1's set with r₀, E and σ_d (336), **E of any sign** | all daily events with the inputs | One primary sample for H1–H7 (the funnel's last step); ADR 0005 §3 keeps E ≤ 0 | 6 short-baseline events are out of H7 although it needs no baseline |
| 8 | Statistic names **`twoway_date_t` / `cluster_date_t`** for coefficients and **`twoway_date_wald` / `cluster_date_wald`** for H7 | the data model's `ols_coef` and `wald` | G1's verdicts and the withholding rule key on (hypothesis, statistic); the names say the covariance | The data model and the invariant changed (§3.3) |
| 9 | H7's rows have **`adjustment = "none"`** (a new enum value) | `mean` | r₀ and E are not adjusted for the market | The enum grew |
| 10 | CR1 in **each** dimension with statsmodels' factor G/(G−1)·(N−1)/(N−K), the intersection with its own | one factor for V | statsmodels' `cov_cluster_2groups` does this; the oracle and statsmodels agree to 1e−12 | none |
| 11 | A coefficient whose two-way variance is ≤ 0 uses max(V_A, V_B); a Wald block that is not positive definite uses the one-way block with the larger trace; both flagged | an eigenvalue clip | `clustering.twoway`'s rule, extended | Never triggered here |
| 12 | The **mean-adjusted twin** of H5/H6 is a robustness row, **sized by G1** (key `twoway_date_t:mean_adj`) | not sized (milestone 3 did not size H1's twin) | A robustness row ADR 0005 §4 may have to withhold; measured, not assumed | It was oversized and is withheld (§6.3) |
| 13 | G1's H5/H6 DGP: the cm30 calibration with **each firm's scale pinned to its real one** (`sig_firm`) and the **real regressors held fixed** | random firm scales | ln σ_d(−1) is a firm-level regressor; heteroskedasticity must follow the real firms. The random-scale version is reported too | One more design |
| 14 | G1's H7 DGP: r = √(x·m_f)·w, Student-t w with a same-date share, so **E[r² \| x] = x exactly**, calibrated scale-free (ν, ρ, τ) | resample real moves | The null must hold exactly; the calibration must not read the tested level of r² | ν from a sample kurtosis is noisy |
| 15 | Power read **from the null replications** (b_j + β moves exactly; r² scaled by b) | separate power runs | Exact for OLS; no extra simulation | none |
| 16 | H5–H7 on **their own seed blocks** (2000+), after H1–H4 | rerun H1–H4 with new seeds | H1–H4's rates must not move: they are identical to milestone 3's (§6.1) | none |
| 17 | Exploratory regression rows: BH within **(regression, sample)**; H5–H7's primaries are in Holm's family, not in it (§9 R1; the first build put them in) | one family with the event tests | Milestone 3's q-values do not move | Two families per sample |
| 18 | \|dispersion surprise\| and the signed surprise **winsorised inside their model** (1%/99%) | raw | One outlier with high − low ≈ 0 would dominate a z-score | none |
| 19 | The VIX model exports the **\|SURP\| × tercile slopes** | export nothing | They are slope differences, not regime means (data model §2.1 forbids dummy coefficients) | A reading of §2.1 |
| 20 | The exceed share is a **two-way t of 1[\|r₀\| > implied] against 0.425** | a binomial test | Same-date and same-firm dependence, as everywhere else | none |
| 21 | Holm runs over the **declared family H1–H7** with H5–H7's real p-values; their failed G1 size check is printed beside their rows, not used to drop them. The family without every failed G1 primary (H1–H4) is kept as **descriptive rows** (`holm_post_gate`) | Holm over the post-gate family H1–H4 as binding (the first build's choice, refuted at review) | ADR 0005 declared G1's size designs for the intercept-only H1–H4 and called a regression's reference-check failure "not a reason to drop a hypothesis"; a gate added after milestone 0 can only lower H1–H4's Holm p (§9 R1) | Two Holm numbers per hypothesis to read; a rejection of H5–H7 would rest on a liberal statistic (none is rejected) |
| 22 | No regression on `mixed` (33 events, one season) | fit it | A model needs 10 events beyond its columns (`drivers.MIN_DF`) | none |
| 23 | The ρ̂̄ investigation lives in **pure functions** (`stats/common_factor.py`, tested) and a kept prototype; it changes no test | change H1's statistic | The brief: investigate, do not change H1's primary | none |
| 24 | **A regression size check, added at milestone 4** (G1 for H5–H7): run before the results, reported beside each row, not binding on Holm's family (`results.SIZE_GATED` = H1–H4) | no size check for regressions (milestone 0's plan) | ADR 0005 §3 had flagged the regressions as "not separately simulated"; the check shows their statistics are liberal (§6.1) | **The owner may choose the post-gate family instead** (`SIZE_GATED` = all seven): H1 2.3e−22, H2 0.0234, G = 7 0.0469 |

---

## 3. Code walkthrough by `file:line`

### 3.1 The regressor columns (panel layer)

- [`panel/regressors.py:57`](../../src/earnings_vol/panel/regressors.py#L57) `price_ref()`,
  [`:79`](../../src/earnings_vol/panel/regressors.py#L79) `surprise_scaled()`,
  [`:89`](../../src/earnings_vol/panel/regressors.py#L89) `winsorise()`,
  [`:99`](../../src/earnings_vol/panel/regressors.py#L99) `sue_hist()`,
  [`:118`](../../src/earnings_vol/panel/regressors.py#L118) `vix_regime()`,
  [`:135`](../../src/earnings_vol/panel/regressors.py#L135) `yahoo_return()`,
  [`:147`](../../src/earnings_vol/panel/regressors.py#L147) `ln_mcap()`,
  [`:160`](../../src/earnings_vol/panel/regressors.py#L160) `regressor_table()`.
- [`panel/window.py:352`](../../src/earnings_vol/panel/window.py#L352) `measures_table()` takes the table (`regs`);
  [`panel/run.py:84`](../../src/earnings_vol/panel/run.py#L84) `yahoo_inputs()` reads the local Yahoo files and the
  rank date's caps; [`:51`](../../src/earnings_vol/panel/run.py#L51) the call.

### 3.2 The regressions and the driver models

- [`stats/regression.py:34`](../../src/earnings_vol/stats/regression.py#L34) `zscore()`,
  [`:40`](../../src/earnings_vol/stats/regression.py#L40) `dummies()`, [`:55`](../../src/earnings_vol/stats/regression.py#L55)
  `fit()`, [`:68`](../../src/earnings_vol/stats/regression.py#L68) `cluster_cov()`,
  [`:79`](../../src/earnings_vol/stats/regression.py#L79) `covariance()` (two-way: V_A + V_B − V_AB),
  [`:91`](../../src/earnings_vol/stats/regression.py#L91) `coef_test()`, [`:107`](../../src/earnings_vol/stats/regression.py#L107)
  `wald_test()`.
- [`stats/drivers.py:92`](../../src/earnings_vol/stats/drivers.py#L92) `PRIMARY`, [`:93`](../../src/earnings_vol/stats/drivers.py#L93)
  `TWIN`, [`:94`](../../src/earnings_vol/stats/drivers.py#L94) `EXPLORATORY`; [`:113`](../../src/earnings_vol/stats/drivers.py#L113)
  `model_inputs()` (complete cases, winsorise inside, z-score, FE dummies); [`:145`](../../src/earnings_vol/stats/drivers.py#L145)
  `h7_inputs()` and [`:165`](../../src/earnings_vol/stats/drivers.py#L165) `implied_variance()` (the /252);
  [`:176`](../../src/earnings_vol/stats/drivers.py#L176) `shift_null()` (b tested against 1);
  [`:200`](../../src/earnings_vol/stats/drivers.py#L200) `crush_rows()`, [`:240`](../../src/earnings_vol/stats/drivers.py#L240)
  `h7_rows()`, [`:266`](../../src/earnings_vol/stats/drivers.py#L266) `exceed_rows()`,
  [`:282`](../../src/earnings_vol/stats/drivers.py#L282) `driver_rows()`.

### 3.3 Gate G1 for H5–H7, the wiring, Holm

- [`stats/g1_drivers.py:84`](../../src/earnings_vol/stats/g1_drivers.py#L84) `std_t()`, [`:96`](../../src/earnings_vol/stats/g1_drivers.py#L96)
  `h7_generate()`, [`:108`](../../src/earnings_vol/stats/g1_drivers.py#L108) `calibrate_h7()`,
  [`:137`](../../src/earnings_vol/stats/g1_drivers.py#L137) `evaluate_h56()` (with the twin and the power shortcut),
  [`:160`](../../src/earnings_vol/stats/g1_drivers.py#L160) `evaluate_h7()`, [`:177`](../../src/earnings_vol/stats/g1_drivers.py#L177)
  `replicate()`, [`:205`](../../src/earnings_vol/stats/g1_drivers.py#L205) `sig_firm()`,
  [`:223`](../../src/earnings_vol/stats/g1_drivers.py#L223) `designs()`, [`:236`](../../src/earnings_vol/stats/g1_drivers.py#L236)
  `merge()`; [`stats/g1.py:144`](../../src/earnings_vol/stats/g1.py#L144) the pinned scale in `generate()`.
- The wiring, pure: [`stats/run.py:93`](../../src/earnings_vol/stats/run.py#L93) `primary_sets()`,
  [`:190`](../../src/earnings_vol/stats/run.py#L190) `driver_design()`, [`:210`](../../src/earnings_vol/stats/run.py#L210)
  `driver_tasks()`, [`:236`](../../src/earnings_vol/stats/run.py#L236) `driver_report()`; around them
  [`:257`](../../src/earnings_vol/stats/run.py#L257) `run_g1_drivers()` and [`:332`](../../src/earnings_vol/stats/run.py#L332)
  the merge into G1's report; [`:335`](../../src/earnings_vol/stats/run.py#L335) `result_rows()` (the verdict check at
  [`:345`](../../src/earnings_vol/stats/run.py#L345), the binding family at [`:348`](../../src/earnings_vol/stats/run.py#L348), driver rows at
  [`:352`](../../src/earnings_vol/stats/run.py#L352), before Holm; the post-gate sensitivity at [`:358`](../../src/earnings_vol/stats/run.py#L358)).
- [`stats/results.py:200`](../../src/earnings_vol/stats/results.py#L200) `primary_rows()` (event tests and
  regressions), [`:55`](../../src/earnings_vol/stats/results.py#L55) `SIZE_GATED`, [`:205`](../../src/earnings_vol/stats/results.py#L205) `require_verdicts()`,
  [`:219`](../../src/earnings_vol/stats/results.py#L219) `binding_family()`, [`:227`](../../src/earnings_vol/stats/results.py#L227) `post_gate_family()`,
  [`:233`](../../src/earnings_vol/stats/results.py#L233) `apply_holm()`, [`:245`](../../src/earnings_vol/stats/results.py#L245) `holm_post_gate_rows()`,
  [`:268`](../../src/earnings_vol/stats/results.py#L268) `season_cut_rows()`, [`:309`](../../src/earnings_vol/stats/results.py#L309)
  `apply_bh()`, [`:321`](../../src/earnings_vol/stats/results.py#L321) `g1_rows()` (H7's calibration).
- [`invariants.py:40`](../../src/earnings_vol/invariants.py#L40): the Wald statistics; [`:59`](../../src/earnings_vol/invariants.py#L59)
  their df rule from the cluster counts; [`:70`](../../src/earnings_vol/invariants.py#L70) no t rule on a Wald row;
  [`:81`](../../src/earnings_vol/invariants.py#L81) the F rule.

### 3.4 The common factor, the export, the app

- [`stats/common_factor.py:26`](../../src/earnings_vol/stats/common_factor.py#L26) `date_contributions()`,
  [`:35`](../../src/earnings_vol/stats/common_factor.py#L35) `rhobar()`, [`:41`](../../src/earnings_vol/stats/common_factor.py#L41)
  `loo_factor()`, [`:63`](../../src/earnings_vol/stats/common_factor.py#L63) `residualise()`;
  `research/prototypes/rhobar_crush.py` prints the measurements.
- [`export/driver_views.py:73`](../../src/earnings_vol/export/driver_views.py#L73) `g1_summary()`,
  [`:123`](../../src/earnings_vol/export/driver_views.py#L123) `term_note()`, [`:156`](../../src/earnings_vol/export/driver_views.py#L156)
  `drivers_data()`, [`:238`](../../src/earnings_vol/export/driver_views.py#L238) `implied_vs_realised_data()`;
  [`export/event_views.py:165`](../../src/earnings_vol/export/event_views.py#L165) `holm_family()` (the family as the run built it),
  [`:179`](../../src/earnings_vol/export/event_views.py#L179) `post_gate()`, [`:190`](../../src/earnings_vol/export/event_views.py#L190) `holm_caveat()`,
  [`:262`](../../src/earnings_vol/export/event_views.py#L262) `tested` over both families.
- The app (delegated agent; checked here by `npm run verify`): `app/src/lib/drivers.ts`, `impliedRealised.ts`,
  `chartLayout.ts` (pure scaling), `DriversPage.tsx`, `ImpliedRealisedPage.tsx`; `contract.ts` at 0.5.0.

---

## 4. Data flow

```
 stage: events, eps, event_iv, iv_daily, chain_expiry, market_daily (VIX, local); raw/yfinance (local)
        │ panel/run.py: ... -> regressors.regressor_table -> measures_table
        ▼
 event_measures (+ price_ref, surprise_scaled, abs_surprise_scaled_w, sue_hist(_n), vix_regime; _yf local)
        │ stats/run.py --g1: H1-H4 as at milestone 3 (same seeds, same rates), then
        │                    driver_design -> g1_drivers designs: calibrated (pinned scales + H7 calibration),
        │                    calibrated_random_scale, D0, D2, D4, D4+firm_fx0.03, D2+common_ar0.5, 4 H7 stress
        │                    designs; 2,000 replications each -> driver_report -> merge
        ▼
 stage/g1_report.json   gate: H1-H4 pass; H5, H6, H7 FAIL (before any H5-H7 result)
        │ stats/run.py result_rows: require_verdicts (every hypothesis with rows has one) -> binding
        │                family H1-H7 (only H1-H4's gate can drop one) -> event tests -> driver_rows
        │                (mis-sized robustness withheld) -> Holm (H1-H7) -> season cut -> BH (exploratory
        │                rows, per family and sample) -> paths -> G1 rows -> holm_post_gate (sensitivity)
        ▼
 results (927 rows; the invariant runs on the write)
        │ tools/export_app_data.py
        ▼
 app/public/data: drivers.json, implied_vs_realised.json (new), tests.json (Holm and G1 now name H5-H7), meta 0.5.0
```

---

## 5. Pitfalls and guards

| # | Pitfall | Guard | Test |
|---|---|---|---|
| 1 | The EPS history is not split-adjusted (NVDA 6.12 → 0.68), so a split-adjusted price scales the surprise wrongly | `price_ref` = forward × df at day −1, as-of | `test_price_ref_is_forward_times_df_of_the_front_expiry_at_the_pre_session` |
| 2 | σ_d² added to E without /252 (252× too big) | [`drivers.py:167`](../../src/earnings_vol/stats/drivers.py#L167) | `test_h7_regressor_is_in_w_units` (0.0011195), the notebook test |
| 3 | statsmodels' default `use_t=False` (normal and χ² p-values) | pure numpy t and F; the invariant | `test_statsmodels_with_use_t_agrees_on_the_hand_worked_case`, `test_wald_rows_of_h7` |
| 4 | df from max(G) or from N − K | [`regression.py:79`](../../src/earnings_vol/stats/regression.py#L79) | `test_two_way_covariance_hand_worked`, `test_statsmodels_agrees_on_a_larger_unbalanced_design` |
| 5 | A failed H5–H7 size check used to drop them from Holm (undeclared, it can only lower H1–H4's Holm p), or a substitute promoted | `results.binding_family`: only `SIZE_GATED` (H1–H4) leave on a failed gate; `crush_rows`, `h7_rows` take the family | `test_a_failed_driver_size_check_keeps_h5_h7_in_the_binding_family`, `test_the_committed_gate_decides_the_roles` |
| 6 | Holm or the season cut still seeing H5–H7 at p = 1 | `primary_rows()` over both families | `test_result_rows_holm_runs_over_h1_to_h7_with_the_real_h5_h7`, `test_the_season_cut_holm_counts_a_small_h5_p` |
| 7 | G1's H5–H7 run moving H1–H4's seeds | `driver_tasks` on block 2000+ | `test_driver_tasks_use_fresh_seed_blocks`; §6.1 (H1–H4 rates byte-identical) |
| 8 | G1 calibrating H7 on the level of r² (the tested b) | `calibrate_h7` rescales to mean square 1 | `test_calibrate_h7_round_trip_and_scale_free` |
| 9 | Pinning firm scales shifts the generator's stream | the draw is still made | `test_generate_pins_the_firm_scale_without_moving_the_stream` |
| 10 | The twin of a mis-sized primary shown as a test | G1 sizes it (`TWIN_KEY`); `crush_rows` withholds it | `test_crush_rows_roles_statistics_and_withholding`, `test_drivers_data_after_a_failed_gate` |
| 11 | Wiring that no test reads (milestone 3's lesson) | `driver_design`, `driver_tasks`, `driver_report`, `merge`, `result_rows` are pure | `tests/test_g1_drivers.py`, `tests/test_drivers.py` on the synthetic Frame |
| 12 | A pandas-3 missing string (NaN) written into JSON | `driver_views._s` | `test_drivers_data_after_a_failed_gate` (the envelope refuses NaN) |
| 13 | A G1 report without a verdict for a hypothesis read as a pass (the review's fail-open finding) | `results.require_verdicts` before any row; `in_family[h]` read strictly | `test_result_rows_refuses_a_report_without_a_verdict` (5 cases), the `KeyError` cases of `test_crush_rows_roles_statistics_and_withholding` and `test_h7_rows_test_a_zero_and_b_one_with_every_event` |
| 14 | The post-gate family mistaken for the binding one | `holm_post_gate` rows are `family = descriptive`, no p-value, no `p_holm` | `test_holm_post_gate_is_a_sensitivity_over_the_family_without_the_failed_primaries` |

---

## Before you read §6: predict

1. A bigger earnings surprise: a bigger or a smaller crush? By how much per standard deviation of |SURP|?
2. Does a high ordinary IV before the news make the log crush bigger or smaller?
3. Is the two-way clustered t of a regression coefficient as well behaved at this design as the two-way t of a mean
   was at milestone 3?
4. Do the options over- or under-price the earnings-day move, on average?
5. The crush baselines' ρ̂̄ is 0.30 after the VIX adjustment. Is that one bad date, or something everywhere?

---

## 6. Measured results

All on 2026-10-29, on this machine, at the pinned commits (earnings `fjrb6h5le9h1qiif2j4pl6cpaas7pnee`, options
`msfqpodh24viv7prdqdan8517rkjp861`), params hash `74bed6f4b1281810…` (the milestone-4 `drivers` section of
`params.yaml` is new). **Timing labels provisional** (20 of 473 look-ups). Commands in the appendix.

### 6.1 Gate G1 for H5–H7 (first, before any H5–H7 result)

`uv run --frozen python -m earnings_vol.stats.run --g1` (20 workers): 465 s for H1–H4 and their re-measure, then
27 s for H5–H7. **H1–H4's numbers are identical to milestone 3's** (the rates of all 33 designs, both calibrations, the
10,000-replication re-measure and the power curves, compared key by key in the two `g1_report.json` files: no
difference), because H5–H7 use their own seed blocks.
Design: H5/H6 on the 347 events of the primary crush regression (172 day-0 dates, 50 companies); H7 on 336 events
(167 dates, 50 companies), no regressor floored. 2,000 replications per design; the exact binomial 99% band is
[3.80%, 6.30%].

**The binding, calibrated design: every H5–H7 primary fails.**

| Hypothesis | Primary statistic | Rejection rate at 5% | ≤ 6.30%? | One-way date (robustness) | Mean-adjusted twin (robustness) |
|---|---|---:|---|---:|---:|
| H5 \|SURP\| | `twoway_date_t` | **9.55%** | **fail** | 18.45% | 9.65% |
| H6 ln σ_d(−1) | `twoway_date_t` | **8.10%** | **fail** | 20.10% | 8.35% |
| H7 a = 0, b = 1 | `twoway_date_wald` | **16.15%** | **fail** | 17.00% | – |

So H5's, H6's and H7's primary statistics are **liberal at this design**: a rejection by them would not be trusted.
*Corrected after review (§9 R1):* the first build read ADR 0005 §5 as moving them out of the confirmatory family
and ran Holm on H1–H4. §5's size designs were declared for H1–H4 only, so H5–H7 stay in the declared Holm family
with their real p-values and this size printed beside each row (§6.2). No other statistic is promoted. Every
robustness row above is also above the bar (none within a point of it, so no re-measure ran) and its p-value is
withheld (ADR 0005 §4).

**The other designs (reported, not pass/fail)**, primary statistic, H5 / H6:

| Design | calibrated, random firm scales | D0 iid | D2 | D4 | D4 + company effects 0.03 | D2 + common AR 0.5 |
|---|---:|---:|---:|---:|---:|---:|
| two-way t | 8.20 / 8.05 | 8.70 / 7.45 | 8.80 / 6.55 | 7.25 / 6.30 | 8.00 / 7.55 | 7.50 / 6.90 |

H7's stress designs (two-way Wald): normal moves with no dependence 12.30%, t(4.5) tails 20.50%, same-date
correlation 0.3 16.40%, firm sd 0.5 20.25%.

**Why it fails: the statistic, not the simulation.** `research/prototypes/g1_regression_size.py` (output kept beside
it) uses the simplest nulls on the real design matrices: y iid N(0, 1) for H5/H6, and moves that are exactly normal
with variance x for H7. Rejection rates at 5%:

| | two-way | one-way date | one-way firm | HC1 |
|---|---:|---:|---:|---:|
| H5 / H6, primary X (sector and season FE) | 7.60 / 6.50 | 5.95 / 5.00 | 7.30 / 6.20 | 5.90 / 5.20 |
| H5 / H6, no fixed effects | 7.20 / 5.95 | 5.55 / 5.10 | 6.80 / 6.25 | 5.35 / 5.20 |
| H7 Wald, normal moves | 11.80 | 10.95 | 11.75 | 11.22 |

|SURP| is very skewed (2.46 after z-scoring) and persistent within a company, so its score is carried by a few
companies: the firm dimension with 50 clusters is where the size goes (7.30% with firm clusters alone, 5.95% with date
clusters alone). The real crush adds heavy-tailed day-0 jumps and company effects (9.55%). H7 regresses a squared,
skewed move on a skewed regressor (x: skewness 1.72, max/median 7.6): every sandwich estimator under-states the
variance at N = 336, even HC1 with no clustering (11.22%). ADR 0005 §3 had warned that the two-way regression
inference was "not separately simulated"; G1's reference-distribution check (df and p on t_{min(G)−1} and F) passes
for every row, so the failure is size, not a wrong reference distribution. The review re-measured the iid case on
8,000 replications with its own code (ledger claim 2): H5 7.85%, H6 6.50%, H7 12.95%, each above that count's bar of
5.64%, so H6's failure is the statistic's too.

**H7's calibration** (`g1_calibration_h7:*` rows): standardised moves r₀/√x have kurtosis 5.62 → ν = 6.29; the
same-date product is −0.056 (clamped to 0); the company dispersion of mean (r₀²/x) is 0 by the method of moments.

**Power under the calibrated design** (two-way t; rejection rate at a true β, log points of crush per sd of the
regressor; read from the null replications): H5 26.7% at 0.01, 63.9% at 0.02, 90.0% at 0.03, 100% at 0.05 (80% at
0.026); H6 14.8%, 33.0%, 60.5%, 94.0% (80% at 0.042). H7 at b = 0.6, 0.8, 1.2, 1.4: 96.10%, 61.55%, 16.10%, 51.85%
(at b = 1.2 below its own size, 16.15%: the test barely sees b > 1). These powers are for oversized tests.

### 6.2 The family and Holm

`uv run --frozen python -m earnings_vol.stats.run`: 927 rows (event_test 45, regression 62, descriptive 131,
validation 689); the reference-distribution invariant ran on the write. *Fixed after review (§9 R1):* Holm runs over
the declared family H1–H7.

| | Statistic (G1 size at 5%) | p | **p_holm (declared family H1–H7, binding)** | Post-gate family H1–H4 (descriptive sensitivity) |
|---|---|---:|---:|---:|
| H1 CRUSH | `twoway_date_t` (4.60%) | 5.8e−23 | **4.1e−22** | 2.3e−22 |
| H2 RUNUP | `rad_season_p`, G = 8 (0.40%) | 0.0078 | **0.0469**; G = 7: **0.0781**, not rejected | 0.0234; G = 7: 0.0469 |
| H3 PERSIST_10 | `twoway_season_t` (0.50%) | 0.743 | **1** | 1 |
| H4 ΔSIGMA_D | `twoway_date_t` (4.60%) | 0.782 | **1** | 1 |
| H5 \|SURP\| | `twoway_date_t` (**9.55%**, size check failed) | 0.0102 | **0.0511**, not rejected | – (left out) |
| H6 ln σ_d(−1) | `twoway_date_t` (**8.10%**, size check failed) | 0.895 | **1** | – |
| H7 a = 0, b = 1 | `twoway_date_wald` (**16.15%**, size check failed) | 0.275 | **1** | – |

- **H1–H4's binding Holm p are milestone 3's** (4.1e−22, 0.0469, 1, 1): H5's p (0.0102) ranks after H2's (0.0078), so
  H1's multiplier (7) and H2's (6) do not move.
- **H2's G = 7 counterfactual is 0.0781, not rejected.** With the October 2026 tail merged into July the cut's p is the
  floor 2/2⁷ = 0.0156; it ranks third, after H5's 0.0102, so Holm gives max(6 × 0.0102, 5 × 0.0156) = 0.0781
  (milestone 3: 0.0938 with H5–H7 at p = 1). Its row and its note in `tests.json` say so. H2's rejection still
  depends on G alone.
- **None of H5–H7 is rejected.** H5's Holm p is 0.0511; its statistic rejects 9.55% under the null at this design, so
  even a rejection would not have been trusted.
- **The post-gate sensitivity** (`results` rows `holm_post_gate`, descriptive): over H1–H4 alone, H1 2.3e−22, H2 0.0234
  and the G = 7 cut 0.0469, which would be "rejected". That is what the first build reported as binding. It is not:
  dropping H5–H7 was a choice made after milestone 0, and it could only lower H1–H4's Holm p (§9 R1). The owner may
  choose it (decisions table row 24).

### 6.3 H5 and H6: the crush regression (daily, market-adjusted, n = 347)

CRUSH on z(|SURP|), z(ln σ_d(−1)), z(SLOPE), z(SIZE), with sector and season fixed effects; R² 0.427; two-way by
172 day-0 dates and 50 companies, t on 49 df. Coefficients are log points of crush per sd of the regressor; the crush
itself is negative (−0.199 on average), so **a positive coefficient means a smaller fall**.

| Row | Role | Estimate | se | t | p | Note |
|---|---|---:|---:|---:|---:|---|
| H5 \|SURP\|, two-way | primary (G1 size 9.55%: liberal) | **+0.0132** | 0.0050 | 2.67 | 0.0102 | Holm p 0.0511; 95% CI [0.0033, 0.0232] |
| H5, one-way date | robustness | +0.0132 | 0.0040 | 3.32 | withheld | G1 size 18.45% |
| H5, mean-adjusted twin | robustness | +0.0121 | 0.0045 | 2.67 | withheld | G1 size 9.65% |
| H6 ln σ_d(−1), two-way | primary (G1 size 8.10%: liberal) | **−0.0014** | 0.0108 | −0.13 | 0.895 | Holm p 1; 95% CI [−0.0230, 0.0202] |
| H6, one-way date | robustness | −0.0014 | 0.0079 | −0.18 | withheld | G1 size 20.10% |
| H6, mean-adjusted twin | robustness | −0.0042 | 0.0107 | −0.39 | withheld | G1 size 8.35% |
| SLOPE | exploratory (never sized by G1) | −0.0317 | 0.0070 | −4.52 | 3.9e−5 | q 0.0006 |
| SIZE | exploratory (never sized by G1) | +0.0129 | 0.0067 | 1.92 | 0.060 | q 0.18 |

How to read it:

- **H5.** One sd more surprise goes with a crush 0.013 log points smaller (the IV keeps more of its level after a
  bigger surprise). The p of 0.0102 comes from a statistic that rejects 9.55% of the time under the null at this
  design, so it is weaker evidence than it looks, and its Holm p over the declared family is 0.0511: not rejected.
  The sign agrees across the twin and the date-clustered row.
  With |SURP| replaced by |SUE_hist| or the |dispersion surprise| it is near 0 (§6.5).
- **H6.** No measurable effect of the prior ordinary volatility level (CI ±0.022).
- **SLOPE** is the strongest driver: one sd steeper term structure at day −1 (a larger event share of the 30-day
  variance) goes with a crush 0.032 larger. That is expected and partly mechanical (ADR 0005 §3: SLOPE proxies E/σ_d²).
  Its p and q come from the same two-way t that G1 measured as liberal for H5's and H6's coefficients (9.55% and
  8.10% under the calibrated null; 7.60% and 6.50% with iid outcomes). **G1 never sized SLOPE's own coefficient**, so
  q 0.0006 is an indication, not a test at 5%.

### 6.4 H7: implied against realised moves (n = 336)

r₀² = a + b (E + σ_d²/252) + u, two-way by 167 dates and 50 companies:

| Row | Estimate | se | Test | p |
|---|---:|---:|---|---:|
| **Wald a = 0, b = 1** (primary, G1 size 16.15%: liberal) | | | F(2, 49) = 1.33 | 0.275; Holm p 1 |
| Wald, one-way date (robustness) | | | F(2, 166) = 0.94 | withheld (G1 17.00%) |
| b | 0.767 | 0.150 | t vs 1: −1.55 | 0.128; CI [0.465, 1.069] |
| a | 0.00083 | 0.00080 | t vs 0: 1.03 | 0.307 |
| share \|r₀\| > implied \|move\| (E > 0, n = 332) | 0.401 | 0.024 | t vs 0.425: −1.01 | 0.319 |
| E at day −2 instead (n = 331): Wald; b | 0.922 (b) | 0.129 | F = 0.20 | 0.822 |

R² 0.151. The realised squared move is about three quarters of the implied variance (b 0.77), but the interval
includes 1, and the share of moves beyond the implied |move| (40.1%) is close to the 42.5% that fair pricing of a
normal move gives (not 50%; concept note 14). The median ratio |r₀| / implied |move| is 0.816. Four events have E ≤ 0
and stay in the regression. With E read at day −2, b is 0.92: the day −1 quotes (wide on AMC announcement days, ADR
0003 §c) may inflate E a little. H7 is not rejected (Holm p 1). The Wald test is badly oversized at this design, so
a rejection would not have been trusted either; the coefficient and share rows are exploratory and come from the
same kind of two-way statistic.

### 6.5 Exploratory rows

39 daily and 4 coarse exploratory regression tests, BH within each sample (H5–H7's primaries are in Holm's family,
not here: §9 R1 took them out of the daily BH family, so every daily q moved a little). q ≤ 0.05: SLOPE in every
crush model (daily q 0.0006–0.011, coarse q 2.6e−6), SLOPE on ΔSIGMA_D (+0.081, t 8.15, q 7.0e−9: with E split from
σ_d at day −1, a steep slope moves both pieces, likely mechanical), |SURP| with ln cm30 as the prior level (+0.0139,
q 0.032), SIZE in the VIX model (+0.018, q 0.018).

| Variant (daily, crush, two-way t) | the surprise term | prior level | slope | size |
|---|---:|---:|---:|---:|
| ln cm30(−1) as the prior level (mechanically linked) | +0.0139 (q 0.032) | −0.0077 | −0.0315 | +0.0119 |
| \|SUE_hist\| (n 339) | +0.0021 (q 0.75) | +0.0022 | −0.0295 | +0.0119 |
| \|dispersion surprise\| (n 344) | +0.0029 (q 0.77) | +0.0011 | −0.0306 | +0.0130 |
| signed surprise added: \|SURP\| / SURP | +0.0065 / +0.0073 | −0.0011 | −0.0314 | +0.0128 |
| firm FE in place of sector FE | +0.0076 (q 0.59) | −0.0309 (q 0.072) | −0.0222 | +0.0507 |
| VIX terciles in place of seasons; \|SURP\| × mid / × high | +0.0144; +0.0029 / −0.0010 | +0.0084 | −0.0327 | +0.0183 |
| ΔSIGMA_D as the outcome (n 262) | +0.0111 | −0.0435 | +0.0813 | −0.0054 |
| coarse sample (n 110, 81 dates, 40 companies) | −0.0061 | −0.0197 | −0.0848 | +0.0186 |

The surprise effect does not survive a different surprise measure, or firm fixed effects; the slope effect survives
everything. **Every p-value and q-value here comes from the same two-way t** (or F) that G1 measured as liberal at
this design for H5's and H6's coefficients (9.55% and 8.10% under its calibrated null; the iid prototype gives 7.60%
and 6.50%). None of these coefficients, SLOPE's included, was sized by G1 itself.

### 6.6 The crush's ρ̂̄ = 0.30: where it comes from

`research/prototypes/rhobar_crush.py` (output kept beside it), on H1's 347 events and their standardised clean
baseline changes (the input of `kpp_t`):

- **ρ̂̄ = 0.3006** reproduced (`eventtests.pynnonen_rhobar` agrees).
- **Not one date.** 489 dates have two or more events (20.1 on average); 75.9% of them have a positive cross-product.
  The top 10 dates (4.7% of the pairs) hold 39.2% of the cross-product; without them ρ̂̄ is still 0.192.
- **Not a stale snapshot.** On each of the 10 top dates (2025-11-24, 2026-06-05, 2024-12-19, 2026-03-09, 2026-03-10,
  2024-12-18, 2026-06-08, 2025-03-10, 2025-03-14, 2025-06-23; mean standardised change −2.27 to +1.71, a Cboe-derived
  aggregate named in DATA.md) every firm's snapshot is from that session with status `ok`, and no ln cm30 change is
  exactly 0.
- **One common date component.** Taking out a leave-one-firm-out mean of the other firms' z on the same date, with a
  loading per firm (median 0.89, 0.48 to 1.25), leaves ρ̂̄ = −0.028. A sector factor alone leaves 0.030, mostly
  because it carries the market-wide part (G1's calibration: 0.294 across sectors, 0.360 within); the sector factor
  after the all-firm one leaves −0.025.
- **VIX's part.** The raw changes have ρ̂̄ 0.374; the VIX adjustment (β per company, median 0.31) takes it to 0.301.
  β = 1 for every company makes it worse (0.658). The date mean of the adjusted z has correlation −0.016 with the
  change of ln VIX (361 dates with ≥ 10 events; raw: +0.681).

**What these numbers can and cannot distinguish** (softened after review, §9 R6):

- *They show* one common date component in the VIX-adjusted changes, spread over most dates: not one bad date, not a
  stale snapshot, and taken out by an all-firm leave-one-out mean.
- *They cannot show its structure.* The review simulated one pure common date factor (ρ 0.3) plus noise in the real
  data's gaps: after the same leave-one-firm-out step ρ̂̄ is −0.032, after the sector step 0.032 to 0.038; independent
  z give about 0 (ledger claim 7, `p07`). So −0.028 and 0.030 are what a single common factor gives. They do not show
  a sector structure, and they cannot separate a "single-stock IV factor" from several.
- *They cannot show that β is correct for VIX.* β is each company's least-squares slope of these same changes on
  Δ ln VIX, so the residual is (nearly) uncorrelated with Δ ln VIX by construction, and the date means inherit that:
  −0.016 is close to automatic. It says the common component is **linearly unrelated to Δ ln VIX**. It cannot rule
  out VIX entering in another form (non-linear, at another lag, with a β that changes over time) or a market variable
  other than VIX.

So ADR 0005's warning line (above about 0.2 suggests a failed VIX adjustment or a data error) found no data error and
no single bad date. Whether it found a failed VIX adjustment depends on what "failed" means: the linear VIX
adjustment removes what is linearly related to Δ ln VIX, and the changes still share one common date component.
H1's primary (two-way date × firm) is robust to any same-date dependence; the KP-type rows, which model it, stay
withheld for the crush. Using an equal-weighted single-stock IV index as a second market factor would be a change to
ADR 0004's market model, an owner decision (§8).

### 6.7 The regressor columns

Filled for all 1,353 events where their inputs exist: `price_ref` 1,200, `surprise_scaled` and
`abs_surprise_scaled_w` 1,198, `sue_hist` 998, `vix_regime` 1,259; local `ln_mcap_yf` 1,307 and `realized_ret_0_yf`
1,170. On the 347 primary events: every column but `sue_hist` (339). **Cross-check:** Yahoo's close-to-close return
against `realized_ret_0` (option forwards) on 336 primary events: median absolute difference 16.9 bp, 95th
percentile 216.1 bp, correlation 0.9924.

### 6.8 The ADRs' checks touched here

| Check | Measured | Verdict |
|---|---|---|
| ADR 0005: two-way SEs no larger than one-way, every H1–H7 row | H5 0.0050 vs 0.0040; H6 0.0108 vs 0.0079; H7 F 1.33 vs 0.94 | two-way larger: company persistence matters for the drivers |
| ADR 0005: ρ̂̄ above about 0.2 for the crush | 0.301; one common date component, linearly unrelated to Δ ln VIX; not a data error or one date (§6.6) | traced, not fully explained |
| ADR 0005 §3: E and SLOPE not both in the model (collinear) | SLOPE only; E enters H7 alone | as declared |

### 6.9 What is committed, and what stays local

| Output | Where | Why |
|---|---|---|
| `event_measures` with `price_ref`, `surprise_scaled`, `abs_surprise_scaled_w`, `sue_hist`, `sue_hist_n` (class F) and `vix_regime` (class F, a three-level label of VIX) | `data/derived/` (207,582 B), CC BY-SA 4.0, `vix_regime` under Cboe's terms | the app and the regressions read them |
| `realized_ret_0_yf`, `ln_mcap_yf` | local stage only | per-event Yahoo values no view needs |
| `results` with the regression rows (45,833 B): the market-adjusted coefficients (class S), the SIZE coefficients (from Yahoo market caps), the VIX-tercile model's slopes | `data/derived/`, under the owner's decision of 2026-10-29 | aggregates the docs and the app show; notices updated |
| `drivers.json` (59,914 B), `implied_vs_realised.json` (160,568 B: 336 per-event rows of implied and realised moves, class F, DoltHub-derived: r₀ is the option-forward return, not Yahoo's) | `app/public/data/` | the two new views; named in DATA.md and `data/derived/LICENSE` since §9 R5 |
| Per-date means of the standardised VIX-adjusted changes on the 10 top dates, and their mean pair products (§6.6, `rhobar_crush.out.txt`) | this page and `research/prototypes/` | Cboe-derived aggregates under the owner's decision of 2026-10-29, named in DATA.md and `data/derived/LICENSE` since §9 R5 |
| G1's per-firm scales (`sig_firm`) | used in memory by the gate run; not written | per-company aggregates of VIX-adjusted scales; their sd across the 50 companies (0.1344) equals the calibration's `sig_disp` |

### 6.10 The gates

All on 2026-10-29 in the working tree, after the review fixes (§9); quoted verbatim in the delivery report. The
first build's results are in the ledger's references (615 Python tests, 1,804 app tests, 69 of 69 own mutants).

| What | Command | Result |
|---|---|---|
| Python tests | `uv run --frozen pytest -q -p no:cacheprovider` | `626 passed, 53 warnings in 68.84s (0:01:08)` (11 more than before the review: the R1–R3 tests, one of them over 5 cases) |
| App gate | `cd app && npm run verify` | `eslint .` clean; `Test Files  44 passed (44)`, `Tests  1891 passed (1891)`; `All files | 99.78 | 99.42 | 99.39 | 99.88` (statements, branches, functions, lines); `✓ built in 3.41s` |
| Notebooks | `uv run --frozen python tools/build_notebooks.py --check` | `OK: 5 notebooks in /home/…/notebooks are in sync with src/` |
| Data files | `uv run --frozen python tools/licensing/check_data_files.py` (and on a scratch copy with every file staged) | `clean: no raw vendor file and no oversized data file` |
| Diagrams | `uv run --frozen --group diagrams python tools/diagrams/build.py docs/architecture/specs --out docs/architecture/out --check` | `ok: 5 spec(s) up to date in docs/architecture/out` (the specs did not change, so the Mermaid render was not re-run) |
| Export | `uv run --frozen python tools/export_app_data.py` | nine `Wrote …/app/public/data/<kind>.json` lines (meta, sample_funnel, iv_measures, tests, event_paths, terrain, heatmap, drivers, implied_vs_realised) |
| Review probe `p01b` (fail-open) | `uv run --frozen --no-sync python docs/validation/probes/m4/p01b_fail_open.py <scratch>` | `(b) result_rows without the H5-H7 gate: refused: ValueError gate G1's report has no verdict for H5, H6, H7: …` (before: 865 rows written) |
| Review probe `p08` (mutants) | a copy re-anchored to the fixed code (M07, M12, M13, M14 moved; M18 disambiguated; M19 retired with `holm_declared_rows`; N01–N17 added for the R1/R2 code), full suite per mutant, five scratch copies | first pass 39 of 40 killed (N05, the post-gate cut taking the binding cut's Holm p, survived: the synthetic cut p was 1 in both families); its test was sharpened and the second pass killed N05 and N17: **41 of 41**, every restore `sha256 ok=True` |
| Data mutants (R1) | a script on a scratch copy's `results.parquet` | `SUMMARY data killed 3 of 3` (H5's primary marked exploratory; the cut's p_holm set to 0.046875; the post-gate cut set to 0.078125) |
| Review probe `p11` (parsers) | a copy with the three expectations R1 changed (§9 R4) | `MISSES 0`; falsifier `MISSES 26`, rc 1. The original stops at its `all_declared` case (`TypeError`: the key is gone) |
| Review probe `p12` (numbers) | a copy reading H5/H6 as primary and the six q-values, row and test counts R1 moved, plus the Holm numbers | `MATCH 68 of 68`. The original stops at its first H5 lookup (`role = exploratory`: 0 rows) |
| Own number check | every number in this page, README, ADR 0005, the milestone-3 page, concept notes 12–15, the data model, DATA.md and the LICENSE regenerated from `results` and the stage reports | `SUMMARY 201 of 201 numbers found where cited`, `NEGATIVE 0 stale phrases` |

---

## 7. Concepts used, and explain it back

- **OLS with one-way and two-way clustered errors, the small-sample factor, t and F on min(G) − 1, z-scored
  regressors, fixed effects, why leverage breaks the size** — [concept note 13](../concepts/13-regression-with-two-way-clustered-errors.md).
- **E + σ_d²/252, the 42.5% benchmark, why a regression of r² is fragile** —
  [concept note 14](../concepts/14-implied-against-realised-moves.md).
- **Pynnönen's ρ̂̄, a leave-one-out factor, what VIX does and does not remove** —
  [concept note 15](../concepts/15-a-common-factor-in-single-stock-iv.md).
- **Gate G1 for a regression, which hypotheses a failed gate can move out (H1–H4 only), the declared family** — concept note
  [12](../concepts/12-holm-and-the-size-gate.md) and note 13.

Explain it back (interview questions):

1. Why does a two-way clustered variance subtract the intersection term, and what is that term when every company
   reports at most once a day?
2. H5's two-way t gives p = 0.0102. Why is that not evidence at the 1% level here, and what did gate G1 measure?
3. Why does the gate's H7 simulation make E[r² | x] = x hold exactly, and why does the calibration rescale r₀/√x
   before reading its kurtosis?
4. The power at β is read from the null replications without simulating again. Why is that exact for OLS?
5. H5–H7 failed their size check. Why do they stay in Holm's family, and why would dropping them have lowered
   H1–H4's Holm p (H2's G = 7 counterfactual from 0.0781 to 0.0469)?
6. ρ̂̄ is 0.30 after the VIX adjustment and about 0 after a leave-one-out IV factor. What can that say about VIX as
   the market factor for single-stock IV, what can it not say (why is the −0.016 correlation with Δ ln VIX nearly
   automatic?), and why does H1's primary not care?
7. Why must the surprise be divided by the as-of option forward, not a Yahoo close?

---

## 8. What's next, and what is not done

- **Reviewed and fixed, no delta review yet.** The adversarial review ([ledger](../validation/m4-ledger.md)) and the
  fixes (§9) have run; a delta review of the fixes has not.
- **H5–H7 are tested with liberal statistics.** They are in the binding Holm family, but their statistics reject
  8–16% under the null at this design, so a rejection by them would not be trusted (none occurred). Every
  exploratory regression p and q has the same weakness. A statistic that passes G1 at this design would be a new ADR
  decision: CR2
  (Bell-McCaffrey) with Imbens-Kolesár degrees of freedom, or a wild cluster bootstrap by company, each to be gated
  before use. Their p-values are now on record, so a later confirmatory use would be compromised for this sample; a
  fresh sample (more seasons, or the coarse era once its timing is settled) would be clean.
- **The common date component** (§6.6): whether ADR 0004's market model should add an equal-weighted single-stock IV
  factor next to VIX is an owner decision; it would change every market-adjusted number. Whether the component is
  a factor of its own or VIX entering in another form is not measured.
- **Which Holm family binds** is the owner's call (decisions table row 24): the declared H1–H7 (now) or the post-gate
  H1–H4 (the sensitivity rows).
- **SIZE assumes the rank date's share count** (decision 5); a share-count history from Yahoo would remove it.
- **G1's H7 calibration** reads ν from one sample kurtosis (5.62); the stress designs bracket it (normal 12.30%,
  t(4.5) 20.50%) and every one fails.
- Not built: the market-conditions variant's VIX-tercile *dummy* coefficients (never exported, §2.1), firm-clustered
  ramp regressions (none declared), `crush_two_session`, the Cboe VX\* cross-check, the coarse/mixed scale correction.
- **Provenance:** the JSON files name `source_commit` 8c3221b and `results.code_commit` ends in `-dirty`, because this
  work is uncommitted; re-export after the milestone commit.
- **The timing look-ups** (453 to go) wait for SEC EDGAR; every number here is provisional until they are done.

---

## 9. Fixes after review

The adversarial review ([ledger](../validation/m4-ledger.md), 2026-10-29) refuted one claim as worded (claim 3) and
found five others partial (claims 1, 8, 9, 11, and the reading of claim 7). Each fix below gives the claim, what was
wrong, the change, and before → after. The gate outputs are in §6.10; no delta review has run.

### R1 (major): the declared Holm family binds

- *Claim* (§1, §2 row 21, §6.2): dropping H5–H7 from Holm after their failed G1 size check is what ADR 0005 §5
  declared in advance.
- *What was wrong:* ADR 0005 at `8c3221b` says G1's size designs "cover only the intercept-only H1–H4", and that for
  the regressions a failed reference-distribution check "is a code bug … not a reason to drop a hypothesis". Sizing
  H5–H7, and dropping them on a failed size check, was a choice made at milestone 4, missing from the decisions table.
  A failed gate can only remove hypotheses, so it could only lower H1–H4's Holm p. It moved H2's G = 7 counterfactual
  from 0.0781 (not rejected) to 0.0469 ("still rejected"), and the README, the `tests.json` note and §6.2 printed only
  the new value.
- *Change:* `results.binding_family` (only `results.SIZE_GATED` = H1–H4 leave the family on a failed gate);
  `results.holm_post_gate_rows` replaces `holm_declared_rows`, so the post-gate family is the descriptive sensitivity;
  `drivers.crush_rows` and `h7_rows` give H5–H7 the role primary while they are in the binding family; BH runs over
  exploratory rows only. The export prints each H5–H7 primary's G1 size with a note that the statistic is liberal on
  this design, so a rejection by it would not be trusted; `drivers.json` `holm.post_gate` replaces `all_declared`.
  ADR 0005 §5 has a dated note; the decisions table rows 17 and 21 are rewritten and row 24 is new (the owner may
  choose the post-gate family instead). README, the milestone-3 page (header and §6.2), concept notes 12–14, the data
  model, notebooks 03 and 04, `stats/run.py`'s header and the app's Drivers, Results and Implied vs realised pages
  follow.
- *Before → after:* binding family H1–H4 → H1–H7. p_holm: H1 2.3e−22 → 4.1e−22; H2 0.0234 → 0.0469; H2's G = 7
  counterfactual 0.0469 "rejected" → **0.0781, not rejected**; H5 – → 0.0511, H6 – → 1, H7 – → 1 (none rejected).
  H5–H7's role exploratory → primary. `results` 929 → 927 rows (7 `holm_all_declared` → 5 `holm_post_gate`). The
  daily exploratory regression family 42 → 39 tests, so every daily q moved a little: SLOPE 0.0007 → 0.0006, |SURP|
  with ln cm30 0.034 → 0.032, SIZE in the VIX model 0.019 → 0.018, SLOPE on ΔSIGMA_D 7.6e−9 → 7.0e−9. Every
  sentence that called the G = 7 counterfactual rejected is deleted.

### R2: a missing G1 verdict counted as a pass

- *Claim* (§1 item 4, `stats/run.py`'s header): G1 decides H5–H7's roles, and the results run cannot use a report
  without it.
- *What was wrong:* `drivers.py` (crush and H7 roles) and `run.py` (the family) read the gate with
  `gate.get(h, True)`. The review's `p01b` handed `result_rows` the real report with every H5–H7 entry removed (what a
  milestone-3 report looks like): it wrote 865 rows with H5–H7 primary, Holm over seven and no one-way row withheld.
  `main()` refused only a missing file or another params hash.
- *Change:* `results.require_verdicts` runs first in `result_rows` and raises `ValueError` unless every hypothesis
  that gets rows (H1–H7) has a boolean verdict in `gate` and its calibrated rates (which decide the withheld rows);
  `crush_rows` and `h7_rows` read family membership strictly (`in_family[h]`, `KeyError` when missing); a row for a
  hypothesis outside the checked set also raises. The docs now say the run *raises before computing a row*, which is
  what the code does. Tests: `test_result_rows_refuses_a_report_without_a_verdict` (5 cases) and the `KeyError` cases
  in `test_crush_rows_roles_statistics_and_withholding` and `test_h7_rows_test_a_zero_and_b_one_with_every_event`;
  mutants N01, N02, N07 and N08 of §6.10.
- *Before → after:* `p01b` (b): "produced 865 rows (no refusal)" → "refused: ValueError gate G1's report has no
  verdict for H5, H6, H7".

### R3: four mutants survived the full suite

- *Claim* (§6.10, appendix): "killed 69 of 69".
- *What was wrong:* the review's own 25 mutants, each run against the full suite, left M05 (the mean-adjusted twin
  regressing the market-adjusted crush: its rows would silently equal the primary's), M25 (|SURP| winsorised over all
  samples: 29 of 1,198 values move, 8 of the 347 primary), M03 (the Wald fallback branch: the old fallback test never
  called the 2 × 2 Wald) and M09 (the ρ correction's sign: the τ = 0.3 round trip's ±0.03 could not see a 2% effect)
  alive. M18 survived as equivalent here (every family member had a primary row).
- *Change:* `test_the_twin_regresses_the_mean_adjusted_crush`,
  `test_regressor_table_winsorises_abs_surprise_within_each_sample` (two samples whose quantiles differ),
  `test_a_non_positive_definite_wald_block_falls_back_to_the_larger_trace_one_way_block` (12 made-up events whose
  two-way block has a negative eigenvalue: F 65.07 from the date block, about 1.6e5 from the smaller one),
  `test_calibrate_h7_reads_the_same_rho_whatever_the_firm_dispersion` (the same date shocks at τ 0 and τ 0.8: ρ̂ 0.300
  and 0.293; the mutant reads about 0.22), and `test_holm_counts_a_family_member_without_a_primary_row_as_p_one`, which
  makes M18 testable instead of equivalent. The module headers and the appendix count the mutants bullet for bullet.
- *Before → after:* the review's harness: 20 of 25 killed, M18 equivalent → **41 of 41 killed** (a copy of the harness
  re-anchored to the fixed code, with 17 mutants of the fix code; N05 needed a sharper test first, §6.10).

### R4: the app's parsers accepted 9 inconsistent payloads

- *Claim* (§3.4, §6.10): the parsers reject malformed and inconsistent payloads.
- *What was wrong:* the review's `p11` found 9 accepted: a primary with a null p and no `g1_size` (drivers and
  tests), H5 in both `family` and `left_family`, G1 `pass: true` above the band, `p_holm` on an exploratory row, H7
  primary with `g1_pass: false`, benchmark 0.5, a one-way Wald p after G1 failed it, a duplicate `event_id`.
- *Change:* cross-field rules D1–D8 in `drivers.ts`, I1–I5 in `impliedRealised.ts`, T1–T3 in `results.ts`, each with
  a test seen to fail on its mutant (80 app mutants, all killed, every restore SHA-256 checked; a delegated agent,
  checked here by `npm run verify` and the probe). A Wald primary has no interval by contract, so D1 asks a Wald
  primary for its p and Holm p only. `implied_vs_realised.json` gained `g1_bar`, `g1_rate_one_way` and
  `g1_pass_one_way`, so the one-way rule can be checked. R1 changed the contract in three places, so a copy of the
  probe (in the session's scratch folder; the read-only original is untouched) changes three expectations: H5 in
  both lists is planted through `left_family` (H5 is now in `family`); `all_declared` is gone, so `post_gate.p_holm`
  is planted instead; "H7 primary with `g1_pass: false`" is now the committed state and must be accepted, and the
  inconsistency it stood for is planted as "primary with `p_holm` null".
- *Before → after:* `MISSES 9` → `MISSES 0` (falsifier: 26 misses, rc 1).

### R5: two data notices were missing

- *What was wrong:* `app/public/data/implied_vs_realised.json` (336 per-event rows) was named in neither DATA.md nor
  `data/derived/LICENSE`; the per-date means of the standardised VIX-adjusted changes on the 10 dates named in §6.6 and
  `rhobar_crush.out.txt` were not in DATA.md's Cboe list.
- *Change:* both are named in DATA.md (the DoltHub row and the `VIXCLS` row) and in `data/derived/LICENSE`, as covered
  by the owner's decision of 2026-10-29 (ADR 0001 §7). The JSON's realised move r₀ is the option-forward return
  (`event_measures.realized_ret_0`, DoltHub, CC BY-SA), not Yahoo's: checked, it equals the committed column to 5e−6,
  the export's rounding. Yahoo's return (`realized_ret_0_yf`) stays local.
- *Before → after:* not named → named, with what each holds and under which terms.

### R6: §6.6 read more into ρ̂̄ than the numbers carry

- *What was wrong:* "β is right for VIX, and what is left is orthogonal to VIX" (§6.6; ADR 0004's note said the
  same). One pure common date factor simulated in the real data's gaps gives the same −0.032 (leave-one-out) and 0.032
  to 0.038 (sector) (review `p07`), and the −0.016 correlation with Δ ln VIX is nearly automatic because β is the
  least-squares slope on Δ ln VIX.
- *Change:* §6.6 lists what the numbers can and cannot distinguish. ADR 0004's note, ADR 0005's status note, concept
  note 15, the milestone-3 page and §1, §6.8, §8 here say "one common date component, linearly unrelated to Δ ln VIX".
- *Before → after:* "a common single-stock IV factor that VIX does not capture … β is right for VIX" → "one common date
  component, linearly unrelated to Δ ln VIX; its structure, and whether VIX enters in another form, are not
  identified".

### R7: exploratory p and q come from a liberal statistic

- *What was wrong:* every exploratory regression p and q, the README headline's SLOPE q included, comes from the
  two-way t that G1 measured as liberal on this design, and the docs did not say so where those numbers appear.
  SLOPE's coefficient itself was never sized by G1.
- *Change:* README, §6.3, §6.5, concept note 13, notebook 04 and the Drivers page's caveat say so, with the measured
  sizes (9.55% and 8.10% for H5's and H6's coefficients under G1's calibrated null; 7.60% and 6.50% with iid outcomes)
  and the fact that no other coefficient, SLOPE's included, was sized.
- *Before → after:* "BH q 0.0007" with no warning → "BH q 0.0006, from the same liberal two-way t; G1 never sized the
  slope's coefficient".

---

## Appendix: what I ran

```
uv run --frozen python -m earnings_vol.events.run                 # new params hash; every committed table byte-identical
uv run --frozen python -m earnings_vol.measures.run --only snapshots
uv run --frozen python -m earnings_vol.measures.run --only iv
uv run --frozen python -m earnings_vol.panel.run                  # event_measures: the eight regressor columns
uv run --frozen python -m earnings_vol.stats.run --g1             # gate G1 first: H1-H4 (465 s), then H5-H7 (27 s)
uv run --frozen python -m earnings_vol.stats.run                  # results
uv run --frozen python tools/export_app_data.py
uv run --no-sync --frozen python research/prototypes/rhobar_crush.py > research/prototypes/rhobar_crush.out.txt
uv run --no-sync --frozen python research/prototypes/g1_regression_size.py > research/prototypes/g1_regression_size.out.txt
uv run --frozen python tools/build_notebooks.py && uv run --frozen python tools/build_notebooks.py --check
uv run --frozen --group diagrams python tools/diagrams/build.py docs/architecture/specs --out docs/architecture/out
# fixes after review (§9): no G1 re-run (the report already holds every H1-H7 verdict)
uv run --frozen python -m earnings_vol.stats.run                  # results: 927 rows, Holm over H1-H7
uv run --frozen python tools/export_app_data.py
uv run --frozen python tools/build_notebooks.py && uv run --frozen python tools/build_notebooks.py --check
```

G1 ran twice: the first run sized H5–H7's primaries and one-way rows but not the twin; the twin was added to G1 and
the gate re-run (same seeds, same rates for everything the first run measured) before the results run. No H5–H7
result was computed before the second gate.

**Mutation checks.** Each new or extended test module lists, in its header, the mutants it was seen to kill. A script
in the session's scratch folder applied each to a scratch copy of the repository, ran the module, restored the file
and checked its SHA-256. Four mutants survived the first pass (the season cut seeing H5–H7 at p = 1, the
all-declared Holm without the failed rows, ρ's pair count, the power shortcut's se); each got a sharper test and was
then killed. After the review (§9 R3) the review's own harness, re-anchored and extended to the fix code, ran the
full suite per mutant: 41 of 41 killed (last column below), and three data mutants of `results.parquet`, 3 of 3.

| Module | Tests | Mutants (header bullets) | Killed this round (review harness ids) |
|---|---:|---:|---|
| `tests/test_regression.py` (new) | 9 | 11 | M01, M02, M03 |
| `tests/test_regressors.py` (new) | 9 | 13 | M21–M25 |
| `tests/test_drivers.py` (new) | 13 | 26 | M02, M04–M07, M12, M14, M18, M20, N01–N08, N16, N17 |
| `tests/test_g1_drivers.py` (new) | 13 | 16 | M08–M11, M15–M17 |
| `tests/test_common_factor.py` (new) | 4 | 6 | – |
| `tests/test_driver_views.py` (new) | 7 | 15 | M07, M12–M14, M17, N03, N04, N06, N09–N16; the `g1_summary` rate/replications pairing (added before the commit) |
| `tests/test_invariants.py` (extended) | +1 | +3 | – |
| `tests/test_g1.py` (2 tests on the committed results, R1) | 0 | +3 data | data r1a–r1c |
| `tests/test_notebooks_sync.py` (notebook 04) | +1 | the H7 /252 mutant | M01, M21; data r1b |
| `tests/test_event_views.py` (fixture gains H3's exploratory row) | 0 | 0 | N12 |
| `tests/test_stats_wiring.py` (synthetic report gains H5–H7 verdicts) | 0 | 0 | M12 |
| **Total** | **57 new** | **90 code + 3 data** | 41 of 41, plus 1 |

The app's new test files list their own mutants (116 tried, all killed, every restore SHA-256 checked, by the
delegated agent).
