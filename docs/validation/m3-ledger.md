# Milestone 3 adversarial review: claims ledger

- **Reviewed:** the uncommitted working tree on top of `fca9972` (milestone 3, "the event study"), on 2026-10-29.
- **Protocol:** `evidence-gated-validation`, Tier 2. Default verdict for every claim: broken.
- **Mode, stated honestly.** The claims and probe designs were frozen first in
  [`probes/m3/00-preregistration.md`](probes/m3/00-preregistration.md). Channel A (documents and papers, no execution)
  ran as a separate sub-agent: [`probes/m3/channel-a.md`](probes/m3/channel-a.md). Its report arrived before most
  Channel B probes ran, so B's verdict mapping was done knowing A's verdicts. Agreement is **dual-confirmed (fallback
  mode)**. `p01c` is a follow-up to A's finding A1 and was **not** pre-registered. `p06` ran 2,000 random draws, not the
  10,000 pre-registered (the machine was slow; an earlier 10,000-draw falsifier run gave the same verdict).
- **Environment:** [`probes/m3/env-pin.txt`](probes/m3/env-pin.txt) (Python 3.12.13, numpy 2.5.4, scipy 1.18.1,
  pandas 3.1.0, statsmodels 0.15.0, node 22.23.1).
- **Isolation.** Probes read the stage cache (`cache/stage/94065662cd46610c/`) and the committed files only. Every
  mutant ran on a scratch copy of the repository. No CLI that writes (`stats.run`, `panel.run`) was run; G1 was re-run
  by calling its functions with output to scratch. Afterwards: the SHA-256 of the 16 source files, of
  `data/derived/*.parquet`, `app/public/data/*.json` and every stage file are unchanged, and `git status --porcelain`
  differs from the start only by `docs/validation/m3-ledger.md` and `docs/validation/probes/m3/`.
- **No dolt, no sec.gov, no token.** No probe quotes a VIX value or a per-event VIX-adjusted value; every printed
  number is a difference, a count or an aggregate.
- **Re-run:** each probe sits in `probes/m3/`; its verbatim output is in `probes/m3/out/`.

## 1. Verdicts

| # | Claim | Verdict | Channel B (what ran, what it printed) | Channel A | Gate |
|---|---|---|---|---|---|
| 1a | β = OLS through the origin over clean one-session baseline changes, each (security, session) once | **SURVIVES** | `p01`: own pandas β for 50 securities, max \|Δβ\| **7.8e-16**, β_n identical. Falsifier (every observed change): max \|Δβ\| 0.19, `falsifier_rc=1` | A1 formula ✓ | Accepted |
| 1a′ | β pools "all non-excluded events" as ADR 0004 defines them | **REFUTED (minor)** | `p01`: **3,168 of 14,927** β changes come from **632 events whose baseline fails 20/15**; 4,715 from coarse/mixed. `p01c`: β from passing baselines only moves per-company β by up to 0.14 (median 0.361 → 0.309) but the H1 mean only from −0.1991 to −0.1994 | A1: ADR 0004:85-86 says a failing event "gets no baseline"; code never applies `base_ok` to β (`window.py:180-182`) | Rejected as worded; immaterial for H1 |
| 1b | No event-window day enters β | **SURVIVES** | `p01`: 0 of 14,927 β changes touch another same-security [−21, +10] zone; 0 inside the event's own | ADR 0004 §1 | Accepted |
| 1c | β "uses no information from after the event it adjusts" | **REFUTED as stated** (by design) | `p01`: **1,209 of 1,259** events have β changes dated after their day +10; median 80% of a security's β changes are after the event's day 0 | ADR 0004:119-120 permits it: later baselines are "harmless here" | Not a code defect; the claim's wording is wrong |
| 1d | Mean-adjusted twin consistent | **SURVIVES** | `p01`: \|crush_cboe + βΔm − crush_mean_adj\| ≤ 2.2e-16 (353); \|aliv_cboe − aliv_mean_adj + β(m − μᵐ)\| ≤ 7.2e-16 (32,173 rows) | ✓ | Accepted |
| 2 | Day 0 and every window match ADR 0004/0005 | **SURVIVES**, three gaps | `p02`: BMO/AMC day 0 and day −1: 0 violations on 1,317 events. Own CRUSH/RUNUP/PERSIST_1/5/10 from the window rows: max diff 0, null patterns identical. Own baseline counts with the 1-/2-session span rule: 0 mismatches on 1,259 events (falsifier, span across any excluded session: 6 mismatches, `rc=1`). Own `eligible_crush`: 347 = 347. **718 of 845 coarse events still fail the minimum** with the 2-span rule | A2: ΔSIGMA_D = ½ ln of the same expiry pair's σ_d² on both days ✓ (`event_iv.py:166-216`). Gaps: EVAR falls back to −2 in `daily` (ADR says −1); coarse "flagged" not stored; `baseline_max_change_span` has **no ADR authority** (params note "default taken at milestone 3") | Accepted with the gaps listed |
| 3 | Two-way CGM, G/(G−1), df = min G − 1; H1 −0.1991, se 0.0113, t −17.70, df 49 | **SURVIVES** | `p03`: package vs statsmodels `use_t=True`, 200 random unbalanced sets: max \|Δt\| 6.2e-15, \|Δp\| 5.6e-16, Δdf 0. Own two-way on stage values: **n 347, G 172/50, −0.1991, se 0.0113, t −17.70, df 49, p 6.35e-23**. Falsifier (+V_AB): se 0.0139, t −14.33 | A3 ✓ (CGM WP eq. 2.15; (N−1)/(N−K) = 1 at K = 1). `max(V_A,V_B)` fallback is the WP's ad hoc rule, not the published eigenvalue fix | Accepted |
| 4a | Full 2^G enumeration, floor 2/2^G = 0.0078 | **SURVIVES** | `p04`: own enumeration, **256 vectors, p 0.007812** = floor; all 8 season means > 0. Falsifier (200 sampled vectors): count check fails, `rc=1` | A4 ✓ | Accepted |
| 4b | The pre-declared rule selects `rad_season_p` | **SURVIVES** | `p04`: merged RUNUP seasons 50/46/49/50/48/45/49/**19**; 50/19 = 2.63 > 1.5 | HEAD ADR 0005:279-282, 295-296 ✓ | Accepted |
| 4c | H2's Holm pass is not an artifact of the season cut | **REFUTED** | `p04`: merge the 19-event Oct-2026 tail into July (what HEAD ADR 0005 §2b predicted): G 7, still unbalanced (68/45), **rad p 0.0156, Holm 0.0938, not rejected**. As built (G 8): Holm 0.0469. The p is pinned to the floor whenever all season sums share a sign, so the Holm verdict is a function of G alone | A4: HEAD text "the October 2026 tail joins July's"; HEAD §4 "could then pass Holm only from the fifth step" | **Rejected** |
| 5a | G1 calibrated rates 4.60 / 0.65 / 0.55 / 4.75% | **SURVIVES** | `p05 a`: calibrated design re-run, 2,000 reps, builder's seeds: identical rates, max diff **0.0**; calibration params equal the report | A10: β, s_i, R̂, SA, ρ, seasons re-estimated per rep ✓ | Accepted |
| 5b | The calibrated DGP reproduces the real moments | **REFUTED for one moment** | `p05 b`, 20 simulated panels through `calibrate()`: within 1.7 sd for ρ₁, correlations, lag-1 cross, firm crush sd, day-0 ratio, sd ln s, cs-mean acf. **AR of levels: raw 0.724 vs 0.794 ± 0.018 (z −3.9); corrected 0.9815 vs 0.9988 ± 0.003 (z −5.7)** | A10: drift estimator differs from the ADR's ("slope of levels on time"); κ and the AR corrections have no ADR authority; **H4 is simulated on cm30, never σ_d** | Rejected as worded (disclosed in direction) |
| 5c/d | κ and the AR correction do not make the gate easier | **SURVIVES**, with a dependency | `p05 c`: the corrected estimator reads 1.000 at true φ ≥ 0.99, 0.9987 at 0.982, 0.987 at 0.95, so the real 0.9815 implies φ < 0.95: the design is the stricter side. `p05 d` (2,000 reps, new seeds): calibrated 5.35/0.75/0.45/5.15; **κ = 0 with ρ_m refit 5.30/0.70/0.45/5.35** (κ harmless); φ = 0.995: 5.60/1.50/1.80/5.25; **φ = 1: H3 6.45% (above 6.30)** | — | Accepted; H3's pass rests on mean reversion the data supports |
| 6 | Holm over H1–H7, H5–H7 at p = 1, is an upper bound and the ADR's family | **SURVIVES** | `p06`: 2,000 random H5–H7 draws: 0 cases where a real p raises H1–H4's adjusted p; 0 differences from statsmodels. Falsifier (m − rank − 1): all draws differ, `rc=1` | A5: formula ✓; p = 1 rule has no pre-milestone ADR text (silent), monotonicity derived | Accepted |
| 7 | No VIX value or per-event VIX-adjusted value committed; data gate clean; tests made-up | **PARTIAL** | `p07` on a scratch copy with all 132 changed files staged: `check_data_files.py` → clean. `scan_real_rows.py`: 3 flags, all in pre-milestone files (`0003-iv-measures.md:49`, `02-iv-measures.md:223,231`), none in M3 files or tests. No `*_cboe` column in `data/derived`; JSON per-event values are `aliv_mean_adj`; `vix_regime` all null; notebook 03 has no outputs. **But** committed `results.parquet` holds `g1_calibration:measured` rows **`dm_sd`** (sd of daily Δln VIX, a statistic of the VIX series itself) and **`beta_median`**; and `03-event-study.md:342` publishes the min and max per-company β (each one company's VIX-derived value) | A11: ADR 0001 §7's S bullet and ADR 0004:221-223 still cite the superseded strict rule and a disclosure test that is "not built" | Escalate (owner's licensing call) |
| 8 | The tests catch breakage | **REFUTED** | `p08`: **5 of 16** own mutants killed (§2); M10 would change H3's event set unseen | — | Rejected |
| 9 | The app only draws; 0.4.0 parsers reject malformed data | **SURVIVES** | `p09` (esbuild bundle in scratch): the 4 committed files parse; **18 of 18 malformed payloads rejected** (p 1.5, string estimate, unknown role, extra/missing key, ci_lo > ci_hi, band decreasing, pass not boolean, ragged arrays, duplicate series, n < 0) and a 0.3.0 envelope rejected. Falsifier: 18 accepted, `rc=1`. Grep of `app/src`: only colour scaling (max \|v\|), extents and pixel rounding are computed | — | Accepted |
| 10 | Every number in §6, README, DATA.md matches | **SURVIVES**, two misprints | `p10`: **71 of 73** doc numbers equal `results.parquet`/`tests.json`; README's H1–H4 table 12/12. Misses: H2 0.23135 printed 0.2314 (half-way rounding, fine); **path day −10 is 0.2355, printed "+0.236"** (double rounding). `p02`: **7 of 366** daily events fail the baseline minimum; §6.5 says 6 | — | Accepted with corrections |
| 11 | Oversizing caveat computed from G1; 24.1 / 26.1 / 15.7 / 15.8 / 69.0 / 38.8% | **SURVIVES** | `p10`: the caveat names exactly the 13 robustness rows above 6.30% (H1 7, H4 6), none missing; values equal the G1 rows (0.2410, 0.2605, 0.1570, 0.1575, 0.6895, 0.3875). Built at `event_views.py:115-121` | — | Accepted |
| 12 | ρ̄ = 0.313 per Pynnönen, reported open | **SURVIVES** | `p12`: own eq. 32 on 9,826 clean changes, 491 dates: **0.3128**; centred per event 0.3093; 0 (date, security) cells with two events; ν̄ρ̄ = 0.001933 = results `rbar`. Extra: dropping the 5% of dates with the largest \|mean z\| gives **0.197**; by year 0.33 / 0.24 / **0.47** (2026) | A6 ✓ algebraically; z uncentred (differs from the paper's mean-0 ranks, measured as 0.004) | Accepted |

## 2. Claim 8: own mutants (scratch copy, eight new test modules, each file restored and SHA-256 checked)

**Verdict: REFUTED. 5 of 16 own mutants killed** (`out/p08.txt`; every restore `sha256 ok=True`; the working tree was
never edited). The builder's listed mutants were not repeated.

| Mutant | File | Result | Real-data effect if it shipped |
|---|---|---|---|
| M01 CR1 residuals not demeaned | clustering.py:45 | KILLED (`test_oneway_cr1_hand_worked`) | — |
| M02 rad t\* variance not re-centred | clustering.py:124 | KILLED (`test_rademacher_…`) | — |
| M03 merge the last small season first | clustering.py:92 | survived | none today (one small season) |
| M04 sign test share ≤ 0 | eventtests.py:122 | survived | near-equivalent (no exact zeros) |
| M05 kp_ow sector fallback → all-pairs mean | eventtests.py:83 | **survived** | `test_kp_ow_rbar_is_clamped_at_zero_and_uses_the_sector_fallback` (tests/test_eventtests.py:45-62) builds a case whose own comment says the sector and all-pairs means are equal (−1/−1, then +1/+1), so it **cannot** see the fallback it is named after |
| M06 span weight read at the span's start | abnormal.py:145 | KILLED (`test_span_sum_equals_aliv`) | — |
| M07 Bartlett 1 − k/L | abnormal.py:197 | KILLED (`test_rhat_psd_…`) | — |
| M08 coarse change may span a `null_iv` session | window.py:145 | survived | `p08b`: 6 coarse/mixed change counts move, 0 eligibility flips |
| M09 coarse PERSIST tries h+1 before h−1 | window.py:162 | survived | coarse PERSIST values move (Tue/Thu targets) |
| M10 **daily** PERSIST may read ±1 | window.py:224 | **survived** | `p08b`: **9 more events would enter H3's primary set** (329 → 338), and 10/9 for PERSIST_1/_5 — no test pins the daily exact-target rule |
| M11 BH q not capped at 1 | multiple.py:41 | survived | q > 1 possible |
| M12 G1 uses the **true** β | g1.py:189 | **survived** | the "every input re-estimated" property of G1 is pinned by no test |
| M13 G1 AR without Kendall | g1.py:340 | **survived** | φ, the parameter H3's gate verdict turns on (§1 5c/d), is untested |
| M14 firm_fx without the sampling correction | g1.py:384 | survived | calibrated company effect untested |
| M15 DGP drops the day-0 jumps | g1.py:137 | survived | event-induced variance untested |
| M16 band at the 99% quantile | g1.py:237 | KILLED (`test_exact_binomial_band`) | — |

The G1 tests check the band, `stale_psi`, `detectable_shift`, three DGP moments and one smoke run; the calibration
mapping that decides the gate (φ, firm effect, jump) and the re-estimation inside `evaluate()` are not tested.
Count note: the eight modules hold **59** tests (`test_eventtests.py` has 9 test functions; §6.7 says 10).

## 3. Defects nobody asked about, by severity

1. **H2's confirmatory rejection is fragile (major, reporting).** `rad_season_p` sits on its floor 2/2^G, so the
   Holm verdict depends only on G. At G = 8 it passes (0.0469); with the tail merged as HEAD ADR 0005 §2b expected,
   it fails (0.0938). README's H1–H4 table and `03-event-study.md` §6.2 show "rejected" without that counterfactual.
   ADR 0005 §4's HEAD sentence "could then pass Holm only from the fifth step" is now false at G = 8 and is not
   corrected. *Fix:* print the G = 7 counterfactual next to H2 in README, §6.2 and `tests.json`. Correct ADR 0005 §4.
   Say plainly that the sign of the run-up is beyond doubt (all 8 season means > 0, two-way t 13.8), while the Holm
   pass is a property of the cluster count.
2. **Test vacuity in the panel's daily target rule and in G1's calibration (major, tests).** M10 changes the primary
   H3 event set with every test green. M12–M15 change the gate's inputs with every test green. M05's test cannot see
   what its name claims. *Fix:* add a daily case with +10 unusable and ±1 usable (expect `missing_target`). Add a G1
   test that plants a known β ≠ β_true and asserts the re-estimated one is used. Add a calibration round-trip test
   (simulate at known φ, firm_fx and jump_k; assert `calibrate()` recovers them within tolerance). Give the
   sector-fallback test unequal sector and all-pairs means.
3. **Licensing scope (escalate).** `results.parquet` carries `dm_sd` and `beta_median`. `03-event-study.md:342`
   publishes the min and max company β. These are VIX statistics beyond "aggregates of market-adjusted results".
   ADR 0004:221-223 and ADR 0001 §7's S bullet still cite the superseded rule (A11). *Fix:* drop `dm_sd` and
   `beta_median` from the committed rows (keep them in the local report), and drop the β range from §6.5. Or record
   the owner's explicit OK.
4. **β pool deviates from ADR 0004 (minor).** It includes 632 failing-baseline events. *Fix:* `window.py:180-182`
   should pass `clean & base_ok[:, None]`, or the ADR should say the minimum does not apply to β. Effect on H1:
   0.0003.
5. **G1 calibration gaps (minor, disclosed in part).** The AR moment is not reproduced (z −5.7). H4 is gated on the
   crush process, not σ_d. The drift estimator differs from the ADR's. *Fix:* state in §6.1 that H4's gate is crush
   evidence, and that H3's pass requires φ < ~0.995 (φ = 1: 6.45%).
6. **Provenance (minor, repeat of M2).** Every JSON says `source_commit` fca9972, and `results.code_commit` is
   `fca9972…-dirty`. Neither names code that contains milestone 3. *Fix:* re-export after the commit.
7. **Misprints (trivial).** Day −10 path "+0.236" should be +0.235 (0.2355). "6 of 366" should be 7 of 366. The
   test-count breakdown says 10 for `test_eventtests` (9).
8. **The oversized robustness rows (judgement).** In G1's calibrated design, H1/H4's one-way, BMP, KP, KPP, Patell
   (69%), sign and rank rows reject 13.7–69% under the null. ADR 0005 §4 says rows known to be mis-sized are dropped
   "so that no reader is misled". Keeping their p-values (down to 1e−66) behind a caveat contradicts that rule.

## 4. Commands

All from the repository root unless noted; `<scratch>` is the session scratch folder.

```
uv run --frozen --no-sync python docs/validation/probes/m3/p01_beta.py            # and --falsify
uv run --frozen --no-sync python docs/validation/probes/m3/p01c_beta_pool.py
uv run --frozen --no-sync python docs/validation/probes/m3/p02_windows.py         # and --falsify
uv run --frozen --no-sync python docs/validation/probes/m3/p03_cgm.py             # and --falsify
uv run --frozen --no-sync python docs/validation/probes/m3/p04_rad.py             # and --falsify
uv run --frozen --no-sync python docs/validation/probes/m3/p05_g1.py a <scratch>/p05a.json 2000   # also b 20, c 10, d 2000
uv run --frozen --no-sync python docs/validation/probes/m3/p06_holm.py            # and --falsify
rsync -a --exclude node_modules --exclude .venv ./ <scratch>/repo/ && (cd <scratch>/repo && git add -A)
(cd <scratch>/repo && PYTHONPATH=<scratch>/repo/src <repo>/.venv/bin/python tools/licensing/check_data_files.py)
(cd <scratch>/repo && PYTHONPATH=<scratch>/repo/src <repo>/.venv/bin/python tools/licensing/scan_real_rows.py)
.venv/bin/python docs/validation/probes/m3/p08_mutants.py <scratch>/repo .venv/bin/python
app/node_modules/.bin/esbuild <scratch>/entry.ts --bundle --format=esm --platform=node --outfile=<scratch>/parsers.mjs
node docs/validation/probes/m3/p09_parsers.mjs <scratch>/parsers.mjs              # and --falsify
uv run --frozen --no-sync python docs/validation/probes/m3/p10_numbers.py
uv run --frozen --no-sync python docs/validation/probes/m3/p12_rhobar.py
git status --porcelain; git diff | sha256sum; sha256sum -c (src, data/derived, app/public/data, stage)   # all unchanged
```
