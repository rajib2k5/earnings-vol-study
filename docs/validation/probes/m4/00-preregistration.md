# Milestone 4 review: pre-registered probes (written before any probe ran)

Mode: single-context sequential fallback. Channel A (ADR 0005 at 8c3221b and in the working tree, ADR 0003 §c,
data model, the milestone page) was read before the probes were written; the probe commands below were fixed
before any of them ran. Default verdict: broken. Isolation: stage cache read-only; every write to scratch.

| Claim | Probe | Pass condition | Falsifier |
|---|---|---|---|
| 1 | `p01_g1_drivers.py`: (a) run `run_g1_drivers` at 2,000 reps with the package's code on the stage cache, compare every H5-H7 rate with `g1_report.json`; (b) `result_rows` with a report whose gate lacks H5-H7: does it refuse, or write H5-H7 as primary; (c) `main()` with no report | (a) every rate equal; (b) refuses; (c) refuses | (a) a planted seed shift changes rates; (b) n/a |
| 2 | `p02_size_iid.py`: own numpy two-way CR1 (not the package's), y iid N(0,1) on the real X of H5/H6, r ~ N(0, x) on the real x of H7, 4,000 reps | rates within 2 se of 7.60 / 11.80% and above 6.30% | own CR1 without G/(G-1): rate moves |
| 3 | `p03_holm.py`: Holm over H1-H4 and over H1-H7 from the committed p's; the G = 7 counterfactual; read ADR 0005 §5 at 8c3221b for H5-H7 | numbers equal; ADR text declares a size gate for H5-H7 | Holm with m = 7 differs |
| 4 | `p04_regression_vs_sm.py`: 300 random unbalanced designs, package vs statsmodels `use_t=True` (one-way, two-way, Wald a = 0, b = 1) | max abs diff <= 1e-10 in se, t, p, F, df | drop the intersection term: diff > 1e-3 |
| 5 | `p05_regressors.py`: own recomputation of price_ref, surprise, winsor, sue_hist, ln_mcap from the stage tables; session order of every input vs day 0; z-score/sector columns of the model | every value equal; no input dated on or after day 0 (prior IV, slope, price) | sue with the current quarter included: differs |
| 6 | `p06_h7.py`: own OLS + two-way + Wald on the committed rows' sample; pre/post sessions by timing; exceed share; worked example | equal to 1e-10; BMO pre = day -1, post = day 0; AMC the same with day 0 = next session | /252 dropped: b moves |
| 7 | `p07_rhobar.py`: own Pynnonen rho-bar, date shares, top-10 removal, LOO factor, sector factor, VIX correlation | equal to the printed 3 dp | n/a (aggregates) |
| 8 | `p08_mutants.py`: >= 12 own mutants on a scratch copy, each run against the full Python suite (-m "not dolt"), restore by SHA-256 | each killed by a behavioural test | — |
| 9 | `check_data_files.py`, `scan_real_rows.py` on a staged scratch copy; scan of JSON/parquet columns for VIX | clean; no VIX value | — |
| 10 | `p10_identity.py`: sha256 of every committed table vs `git show 8c3221b:`; event_measures column-by-column; H1-H4 G1 rows vs 8c3221b's results | identical except the 8 regressor columns and new rows | — |
| 11 | `p11_parsers.mjs` on an esbuild bundle of the 0.5.0 parsers: malformed drivers / implied payloads, a withheld primary, a withheld row with CI | every malformed payload rejected | accept-all parser |
| 12 | `p12_numbers.py`: >= 15 numbers of §6 and README vs results.parquet / JSON | equal at printed precision | — |
