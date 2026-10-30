# Milestone 4 adversarial review: claims ledger

- **Reviewed:** the uncommitted working tree on top of `8c3221b` (milestone 4, "Drivers"), 2026-10-29.
- **Protocol:** `evidence-gated-validation`, Tier 2. Default verdict for every claim: broken.
- **Mode, stated honestly: single-context sequential fallback.** Channel A (ADR 0005 at `8c3221b` and now, ADR 0003 §c,
  the data model, `04-drivers.md`) was read first; the probe designs were then frozen in
  [`probes/m4/00-preregistration.md`](probes/m4/00-preregistration.md). The same context ran Channel B, so agreement
  is **dual-confirmed (fallback mode)**, not independent. Deviations from the pre-registration: `p01b` (fail-open
  check) and `p12b` were added; `p11`'s "tests.json H5 primary" case was dropped (tests.json has no H5-H7 rows, the
  case was a no-op).
- **Environment:** [`probes/m4/env-pin.txt`](probes/m4/env-pin.txt) (Python 3.12.13, numpy 2.5.4, scipy 1.18.1,
  pandas 3.1.0, statsmodels 0.15.0).
- **Isolation.** Probes read the stage cache (`cache/stage/74bed6f4b1281810/`) and committed files. No CLI that writes
  was run; G1 for H5-H7 was re-run by calling `run.run_g1_drivers` with output to scratch; `p01b` called `run.main()`
  with `stage_dir` and `DERIVED` redirected to scratch. Every mutant ran on a scratch copy. `p99_integrity.sh`: see §4.
- **No dolt, no sec.gov, no token.** No probe prints a VIX value or a per-event VIX-adjusted value.
- Probes: [`probes/m4/`](probes/m4/); verbatim outputs in `probes/m4/out/`.

## 1. Verdicts

| # | Claim | Verdict | Channel B (what ran, what it printed) | Channel A |
|---|---|---|---|---|
| 1 | G1 for H5-H7 before any H5-H7 result, real design, every input re-estimated; the code refuses to write H5-H7 results without the G1 report | **PARTIAL** | `p01`: `run_g1_drivers` re-run at 2,000 reps: **52 of 52 H5-H7 rates identical** to `g1_report.json` (H5 9.55, H6 8.10, H7 16.15%), gate, H7 calibration, power, n 347/347/336 equal; falsifier (seed block +1) 50 of 52 differ, rc 1, and still fails all three (8.40/7.75/18.05%). M08 (outcome not re-estimated) is killed. No stage dir holds an earlier regression `results`; timestamps fit the story (g1_report 19:07, results 19:13). **But `p01b`:** `result_rows` with a report lacking H5-H7 writes 865 rows with **H5-H7 `role=primary`, Holm over seven, one-way rows not withheld**, no error. `main()` refuses only a missing file or another params hash (`run.py:370-374`) | The order cannot be proven from artifacts. `run.py` changed at 19:13:15, after the report; the current code reproduces it |
| 2 | The failures are the statistics': iid normal outcomes on the real design give H5 7.60%, H7 11.80% | **SURVIVES** | `p02`, own vectorised CR1 (not the package's), 8,000 reps: **H5 7.85% (se 0.30), H6 6.50% (0.28), H7 Wald 12.95% (0.38)**; the bar at 8,000 is 5.64%. Falsifier (no G/(G−1)) moves every rate. H7 is 1.15 points above the printed 11.80% (z about 1.8): noise, same conclusion | ADR 0005 §3 (`8c3221b`:719) had flagged regressions "not separately simulated" |
| 3 | Dropping H5-H7 from Holm is exactly what ADR 0005 §5 declared in advance; p_holm 2.3e−22, 0.0234, G = 7 0.0469; "all 7" rows descriptive and labelled | **REFUTED as worded** (numbers SURVIVE) | `p03`, own Holm: H1 2.32e−22, H2 0.0234375, cut 0.046875, all 7 all-declared rows equal (family descriptive, no p); falsifier m = 7 rc 1. **The same cut under the declared seven-hypothesis family with the real H5-H7 p's is 0.078125 (not rejected); milestone 3 printed 0.09375** | ADR 0005 at `8c3221b`:863-864: "The size designs cover only the intercept-only H1–H4"; :873-876: a reference-check failure is "not a reason to drop a hypothesis". Sizing regressions is a milestone-4 decision, missing from the decisions table, and it can only lower H1-H4's Holm p. It turned H2's G = 7 cut from "not rejected" to "rejected" (README, `tests.json` H2 note, §6.2 present only the new value) |
| 4 | regression.py = statsmodels `use_t=True` to 1e-12, Wald included | **SURVIVES** | `p04`, 300 random unbalanced designs (half with a firm at most once per date): df mismatches 0; max diff se 7.9e-14 (rel.), t 2.3e-12 (abs., large t), p 1.9e-14, CI 1.1e-13, F 1.1e-13 (rel.), F p 8.6e-15. Falsifier (intersection added): t diff 55, rc 1 | CGM formula as in ADR 0005 §3 |
| 5 | Regressors follow the data model, no look-ahead | **SURVIVES** | `p05`, own pandas recomputation from the stage tables: price_ref 1,200, surprise 1,198, \|SURP\|_w 1,198, sue_hist 998, sue_hist_n, ln_mcap_yf 1,307: **max diff 0** each; 0 earlier quarters dated on/after the event; pre = day −1 and post = day 0 for 182/182 AMC and 165/165 BMO; pre ≥ day 0 in 0 of 1,200; z sd 1, 8+8 dummies (first level dropped). Falsifier (current quarter in SUE history) rc 1 | Data model §3.11 rows 771-781 ✓; SIZE uses the 2026-10-29 share count (decision 5, disclosed) |
| 6 | H7 units, sessions, b 0.767 (0.46-1.07), F 1.33, p 0.275, exceed 0.401 vs 0.425 | **SURVIVES** | `p06`, own numpy: b 0.7670 se 0.1504 CI [0.4648, 1.0691]; F(2,49) 1.3253 p 0.2751 (block PD, no fallback); share 0.4006 se 0.0242 t −1.007 p 0.3191; 2(1−Φ(√(2/π))) = 0.42494; `implied_abs_move_total_m1`/(√(2/π)√(E+σ²/252)) = 1.000000 on all 332; worked example 0.0011195. Falsifier (no /252): b 0.032 | ADR 0003 §c:354-365, :486-491 ✓ |
| 7 | ρ̄ numbers | **SURVIVES** (numbers); interpretation over-read | Prototype re-run byte-identical. `p07`, own code: 0.3006, 489 dates, 0.759 positive, top-10 share 0.392, without them 0.1920, LOO −0.0282, sector 0.0301. **Mechanics:** one pure common date factor (ρ 0.3) in the real missingness gives −0.032 (LOO) and 0.032-0.038 (sector); iid z gives about 0 | −0.016 against Δ ln VIX is near-mechanical: β is the OLS slope of the same changes on Δ ln VIX. So §6.6 shows one common date component, not that "β is right" |
| 8 | Tests catch breakage, wiring included | **PARTIAL** | §2: **20 of 25 own mutants killed** by behavioural tests; **wiring 8 of 9** (the 9th, M18, is equivalent in this wiring). Real survivors: M05 (twin), M25 (\|SURP\| groups), M03 (Wald fallback); M09 equivalent on the real data but its test cannot see it | — |
| 9 | Data policy | **PARTIAL** | `check_data_files.py` on a staged scratch copy (133 paths): clean. `scan_real_rows.py`: the 3 pre-milestone lines only. No `*_cboe`/`*_yf` column committed; JSON has no VIX key; notebook 04 has 0 outputs. **But** `implied_vs_realised.json` (336 per-event rows) is not named in DATA.md or `data/derived/LICENSE`; the per-date means of standardised VIX-adjusted changes on 10 named dates (§6.6:382-383, `rhobar_crush.out.txt`) are not in DATA.md's Cboe list | DATA.md:17 lists `vix_regime` and the regression rows ✓ |
| 10 | Other tables byte-identical; H1-H4 G1 rows identical | **SURVIVES** | `p10`: 11 committed tables byte-identical to `8c3221b`; event_measures changed in 6 committed columns only, 0 class-R columns; all 786 milestone-3 rows present, only 3 `p_holm` differ (H1, H2, H2 cut); **527 H1-H4 G1 rows and 88 calibration rows identical** | — |
| 11 | App only draws; parsers reject malformed payloads, a withheld primary, a withheld row with CI | **PARTIAL** | grep of the new app files: extents (`Math.max/min`), round ticks, pixel scaling only. `p11`: committed files accepted; the two named cases and 17 malformed payloads rejected; **9 inconsistent payloads accepted:** primary with null p and no `g1_size` (drivers and tests), H5 in both `family` and `left_family`, G1 `pass: true` above the band, `p_holm` on an exploratory row, H7 `role: primary` with `g1_pass: false`, benchmark 0.5, a one-way Wald p after G1 failed it, duplicate `event_id`. Falsifier (accept-all) rc 1 | — |
| 12 | Every number in §6 and README equals the data | **SURVIVES** | `p12`: **58 of 58** (slope −0.032 / −0.0317, q 0.0007 included), row counts 929 = 45/62/133/689, 42 daily + 4 coarse tests; `p12b`: §6.7 counts, 16.9 / 216.1 bp, 0.9924, 127/118/121 | — |

## 2. Claim 8: own mutants

Scratch copies (`rsync`, no `node_modules`/`.venv`), full suite `-m "not dolt"` per mutant (baseline 613 passed),
restore checked by SHA-256 (`ok=True` on all 25). Outputs: `out/p08_{a,b,c}.txt`.

| Mutant | File:line | Result |
|---|---|---|
| M01 CR1 factor without (N−1)/(N−K) | regression.py:75 | KILLED (hand-worked, statsmodels tests) |
| M02 two-way df from max(G) − 1 | regression.py:88 | KILLED |
| **M03 Wald fallback picks the smaller-trace block** | regression.py:116 | **SURVIVED** (branch untested; not triggered on real data) |
| M04 exceed share keeps E ≤ 0 | drivers.py:266 | KILLED |
| **M05 the mean-adjusted twin regresses the market-adjusted crush** | drivers.py:113 | **SURVIVED**: the twin rows (+0.0121 / −0.0042 in §6.3) would silently equal the primary |
| M06 shift_null ignores the null | drivers.py:174 | KILLED |
| M07 H7 role ignores the gate | drivers.py:246 | KILLED |
| M08 G1 H5/H6 outcome not re-estimated | g1_drivers.py:142 | KILLED |
| M09 calibrate_h7 ρ correction sign | g1_drivers.py:127 | SURVIVED; equivalent on the real data (τ = 0, ρ clamped at 0, `p08b`), but the round-trip test's ±0.03 cannot see ±2.3% at τ 0.3 |
| M10 H7 firm multiplier mean ≠ 1 | g1_drivers.py:104 | KILLED |
| M11 sig_firm centred on the event mean | g1_drivers.py:210 | KILLED |
| M12 Holm family ignores the gate | run.py:336 | KILLED |
| M13 driver rows get no mis-sized set | run.py:335 | KILLED |
| M14 all-declared sensitivity over the binding family | run.py:339 | KILLED |
| M15 driver_design: sig_firm zeroed | run.py:197 | KILLED |
| M16 driver_design: H7 x from E at day −2 | run.py:194 | KILLED |
| M17 driver_report gate twice as lenient | run.py:245 | KILLED |
| M18 Holm drops a member without a primary row | results.py:196 | SURVIVED; equivalent here (every family member has a primary row) |
| M19 all-declared sees primary rows only | results.py:212 | KILLED |
| M20 BH over both families together | results.py:273 | KILLED |
| M21 SUE history includes the current quarter | regressors.py:109 | KILLED |
| M22 VIX tercile ties go up | regressors.py:131 | KILLED |
| M23 SIZE scaled by the first close | regressors.py:154 | KILLED |
| M24 price_ref at the post session | regressors.py:68 | KILLED |
| **M25 \|SURP\| winsorised over all samples** | regressors.py:174 | **SURVIVED**: 29 of 1,198 values move, **8 of the 347 primary** (`p08b`); `test_winsorise_within_each_group` tests the helper, not the call |

## 3. Defects, by severity

1. **Major (inference, reporting): an undeclared gate shrank Holm's family** (claim 3). ADR 0005 at `8c3221b`
   said G1's size designs cover H1-H4 only (:863-864) and that a regression's reference-check failure is "not a reason
   to drop a hypothesis" (:873-876). Sizing H5-H7 is a new milestone-4 choice. A failed gate can only remove
   hypotheses, so it can only lower H1-H4's Holm p. It moved H2's G = 7 cut from 0.0781 (declared H1-H7 family, real
   p's) to **0.0469, "still rejected"** (README, `tests.json` H2 note, §6.2). *Fix:* add a dated ADR 0005 §5 note and a
   decisions-table row: "regression size gate added at milestone 4". Print 0.0781 next to 0.0469 wherever the cut
   appears. Let the owner say which family binds.
2. **Moderate (code): a missing gate verdict counts as a pass.** `drivers.py:222`, `:246`, `run.py:336` use
   `gate.get(h, True)`. `p01b`: with H5-H7 missing from the report, the run writes H5-H7 as primary, runs Holm over
   seven and withholds nothing. *Fix:* `result_rows` raises unless every hypothesis with rows has a gate verdict.
3. **Moderate (tests):** M05 and M25 survive the full suite; M03's branch is untested; M09's tolerance is too loose.
   *Fix:* a twin test against OLS on `crush_mean_adj`; a `regressor_table` test with two samples whose quantiles
   differ; a Wald test with a non-PD two-way block; the ρ round trip at τ ≈ 0.8.
4. **Minor (parsers):** the 9 accepted inconsistencies of claim 11. *Fix:* cross-field rules (primary ⇒ p not null;
   `family ∩ left_family = ∅`; `pass == rate ≤ band`; `p_holm` only on primary; H7 primary ⇒ `g1_pass`; benchmark
   0.425; unique `event_id`).
5. **Minor (notices):** name `implied_vs_realised.json` in DATA.md; list §6.6's per-date VIX-adjusted means.
6. **Minor (interpretation):** §6.6 and ADR 0004's new note read the −0.016 and the LOO −0.03 as "β is right for
   VIX". Both are what OLS β and any one common date factor give (`p07`). Say "one common date component that is
   linearly unrelated to Δ ln VIX".
7. **Trivial:** `run.py:30-32` says Holm "now runs over H1-H7 with H5-H7's real p-values" (false). H6's iid rate
   (6.50%) is above the 8,000-rep bar too, so H6's failure is also the statistic's.
8. **Judgement:** every exploratory regression p and q (SLOPE q 0.0007 in the README headline) comes from the same
   two-way t that G1 found oversized; SLOPE's row was never sized.

## 4. Commands and integrity

From the repository root; `<s>` is `…/scratchpad/m4`.

```
uv run --frozen --no-sync python docs/validation/probes/m4/p01_g1_drivers.py <s>/p01_rerun.json   # 52 of 52 equal; --falsify rc 1
uv run --frozen --no-sync python docs/validation/probes/m4/p01b_fail_open.py <s>/p01b            # (a) refused; (b) 865 rows, H5-H7 primary
uv run --frozen --no-sync python docs/validation/probes/m4/p02_size_iid.py 8000                  # 7.85 / 6.50 / 12.95%; --falsify
uv run --frozen --no-sync python docs/validation/probes/m4/p03_holm.py                           # mismatches 0; --falsify rc 1
uv run --frozen --no-sync python docs/validation/probes/m4/p04_regression_vs_sm.py               # PASS; --falsify rc 1
uv run --frozen --no-sync python docs/validation/probes/m4/p05_regressors.py                     # mismatching columns 0; --falsify rc 1
uv run --frozen --no-sync python docs/validation/probes/m4/p06_h7.py                             # --falsify: b 0.032
uv run --no-sync --frozen python research/prototypes/rhobar_crush.py > <s>/rhobar_rerun.txt     # byte-identical
uv run --frozen --no-sync python docs/validation/probes/m4/p07_rhobar.py
.venv/bin/python docs/validation/probes/m4/p08_mutants.py <s>/repo{1,2,3} .venv/bin/python {0 8|9 16|17 24}   # 6/9, 8/8, 6/8
uv run --frozen --no-sync python docs/validation/probes/m4/p08b_survivor_effects.py
(cd <s>/repo && git add -A && PYTHONPATH=src <repo>/.venv/bin/python tools/licensing/check_data_files.py)   # clean
uv run --frozen --no-sync python docs/validation/probes/m4/p10_identity.py <s>/p10
app/node_modules/.bin/esbuild <s>/entry.ts --bundle --format=esm --platform=node --outfile=<s>/parsers.mjs
node docs/validation/probes/m4/p11_parsers.mjs <s>/parsers.mjs                                  # MISSES 9; --falsify rc 1
uv run --frozen --no-sync python docs/validation/probes/m4/p12_numbers.py                        # MATCH 58 of 58
bash docs/validation/probes/m4/p99_integrity.sh <s>
```

**Integrity** (`out/p99_integrity.txt`): `git status --porcelain` differs from the start only by
`docs/validation/m4-ledger.md` and `docs/validation/probes/m4/`. The SHA-256 of the 586 other tracked and untracked
files and of the 1,443 cache files are identical to the snapshots taken before the first probe. The set of cache
files is unchanged. All 25 scratch restores: `sha256 ok=True`.
