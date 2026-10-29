# Milestone 3 review: pre-registered claims and probes

Frozen 2026-10-29, before any probe ran and before Channel A started. Default verdict for every claim: **broken**.
Probes run on a scratch copy of the repository (or read-only on the stage cache); no probe writes to the working tree
except this folder. A probe whose output contradicts its pass condition refutes the claim; a probe that cannot fail is
PROBE_INVALID. No probe output or ledger line may quote a raw VIX value or a per-event VIX-adjusted value: probes
print only differences, counts, aggregates and pass/fail.

| # | Sub-claim | Probe (Channel B) | Pass condition | Falsifier |
|---|---|---|---|---|
| 1a | β_s = Σ dX dM / Σ dM² through the origin over clean one-session baseline changes, each (security, session) once | `p01_beta.py`: recompute β from the stage `event_window_obs` with own pandas code | max \|Δβ\| < 1e-12 | include every observed change (not only clean): mismatch |
| 1b | No session entering β lies in any same-security [−21, +10] zone | `p01_beta.py`: intersect β's sessions with every zone | 0 overlaps | — (count) |
| 1c | β uses no information from after the event it adjusts | `p01_beta.py`: per event, share of β's changes dated after its day 0 / after its day +10 | 0 events with later changes | — (count) |
| 1d | Twin consistency: crush_cboe + β·Δm = crush_mean_adj; aliv_cboe − aliv_mean_adj = −β(m − μᵐ) | `p01_beta.py` | max \|diff\| < 1e-12 | — |
| 2a | Day 0: BMO = announcement session, AMC = next session | `p02_windows.py` on events | 0 violations | swap BMO/AMC: violations |
| 2b | CRUSH = e at day 0 (daily: −1 → 0 exactly), RUNUP = ALIV(−1), PERSIST_h = ALIV(+h), only when the baseline passes | `p02_windows.py`: recompute from the stage window rows | max \|diff\| < 1e-12 | shift by one rel_day: mismatch |
| 2c | ΔSIGMA_D and EVAR match ADR 0004 §3 (same two expiries both days; E at −1) | read `measures/` code (A); recompute from `iv_daily` where possible (B) | definitions agree | — |
| 2d | Baseline counts: ≥ 20 sessions, ≥ 15 changes; a change spans ≤ 1 session in daily, ≤ 2 in mixed/coarse and only across `not_observed` sessions | `p02_windows.py`: own count from the window rows | 0 mismatches with `baseline_n_changes` and eligibility | allow span across zone sessions: mismatch |
| 3a | `twoway()` = CGM with G/(G−1) per term, df = min(G)−1 | `p03_cgm.py`: statsmodels OLS on a constant, 2-column groups, `use_t=True`, random unbalanced data | t, df, p equal to 1e-10 | add the intersection term: mismatch |
| 3b | H1 = −0.1991, se 0.0113, t −17.70, df 49 | `p03_cgm.py`: own two-way formula on the stage values | matches to rounding | — |
| 4a | `rademacher_p` enumerates 2^G vectors, floor 2/2^G; H2 p = 2/2⁸ | `p04_rad.py`: own enumeration on the stage values | same p; 256 vectors | sample 200 random vectors: p differs or fails the count |
| 4b | 8 merged RUNUP seasons, unbalanced (max > 1.5 min), so rad is primary by the ADR's rule | `p04_rad.py`: own season merge | 8, ratio > 1.5 | — |
| 4c | H2's Holm pass is not an artifact of the season cut | `p04_rad.py`: Oct-2026 tail merged into its neighbour (G = 7) and the H2 Holm p under the same rule | Holm p ≤ 0.05 also at G = 7 | — |
| 5a | G1 calibrated rates H1 4.60, H2 0.65, H3 0.55, H4 4.75% | `p05_g1.py`: re-run the calibrated design only (2,000 reps, same seeds), output to scratch | identical rates | — |
| 5b | The calibrated DGP reproduces the real moments | `p05_g1.py`: simulate the calibrated DGP, re-run `calibrate()` on simulated panels | each moment within ~2 sim sd of the real one | — |
| 5c | The AR correction does not make the gate easier | `p05_g1.py`: estimator reading at true φ = 1, 0.995, 0.982; G1 H2/H3 at φ = 1 and φ = 0.995 | reading at true φ ≥ 0.995 is above the real 0.982; H2/H3 within band at the plausible φ | — |
| 5d | κ (common noise) does not make the gate easier | `p05_g1.py`: calibrated design with κ = 0 and ρ_m re-fitted | H1–H4 within band | — |
| 6 | Holm over H1–H7 with p = 1 for untested is an upper bound; matches the ADR family | `p06_holm.py`: 10,000 random draws for H5–H7, compare to statsmodels | adjusted p(H1–H4) ≤ the p = 1 value always; equal to statsmodels | — |
| 7 | No VIX value or per-event VIX-adjusted value committed; `check_data_files.py` clean on a scratch index; tests made-up | `p07_policy.sh`: parquet schemas, JSON keys, grep docs/notebooks, scratch index, `scan_real_rows.py` | none found; clean | — |
| 8 | ≥ 6 own mutants killed | `p08_mutants.py` on a scratch copy | each mutant: ≥ 1 failing test | — |
| 9 | App computes no statistic; contract 0.4.0 parsers reject malformed data | read `app/src` (A); `p09_parsers.mjs` on an esbuild bundle of the parsers (B) | every malformed payload rejected | — |
| 10 | ≥ 10 numbers in the milestone doc §6 / README / DATA.md equal results.parquet / tests.json | `p10_numbers.py` | all equal to rounding | — |
| 11 | Oversizing caveat computed from the G1 rows; 24.1 / 26.1 / 15.7 / 15.8 / 69.0 / 38.8% | `p10_numbers.py` | equal to the G1 rows | — |
| 12 | ρ̄ = 0.313 is Pynnönen eq. 32 on standardised clean baseline changes; reported as open | `p12_rhobar.py`: own estimator; check same-firm double counting | 0.313 reproduced; no same-firm pairs | — |

Channel A (separate sub-agent, documents only): ADR 0004/0005 text against the code, and the primary papers for the
formulas (CGM 2011, Pynnönen 2022 eq. 32, Kendall 1954, Holm 1979, Corrado-Zivney 1992, Cowan 1992).
