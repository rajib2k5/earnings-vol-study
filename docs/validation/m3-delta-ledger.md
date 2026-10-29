# Milestone 3 delta review: the fixes of §9, attacked

- **Reviewed:** the uncommitted working tree on top of `fca9972` after the fix round described in
  [`docs/milestones/03-event-study.md`](../milestones/03-event-study.md) §9, against the first review
  ([`m3-ledger.md`](m3-ledger.md)) and the fixer's scratch outputs. 2026-10-29. Default verdict for every claim: broken.
- **Isolation.** Probes read the stage cache (`cache/stage/94065662cd46610c/`) and the committed files. No CLI that writes
  was run. Every mutant ran on a scratch copy (`rsync`, no `node_modules`/`.venv`), each file restored and its SHA-256
  checked (`ok=True` on every line). `d99_integrity.sh` compares `git status --porcelain`, the SHA-256 of every tracked and
  untracked file, and the 33 stage files with snapshots taken before the first probe: see §4.
- **No dolt in `~/data/vol-projects/dolthub/*`, no sec.gov, no token.** No probe prints a VIX value or a per-event
  VIX-adjusted value; printed numbers are rates, counts, differences and aggregates already in the committed files.
- Probes: [`probes/m3-delta/`](probes/m3-delta/); verbatim outputs in `probes/m3-delta/out/`.

## 1. Verdicts

| # | Claim | Verdict | Evidence (what ran, what it printed) |
|---|---|---|---|
| 1 | `sig0` estimated by the package from real data, uses no test outcome, does not make the gate easier; H1 4.75→4.45% | **PARTIAL** | `d01 a`: package `sig0` = committed row (diff 0) = own recomputation (cm30 0.033558, σ_d 0.049115). `d01 b`: tested values permuted / negated / +1 / ×3 → Δsig0 **0** each (firm_fx, jump_k move, so the substitution took). `d01 c` (production seeds): calibrated 4.45/0.40/0.50/4.75%, same seeds with sig0 = 0.03: **4.75**/0.40/0.50/**5.15%** (the 4.75→4.45 is exactly the sig0 change). `d01 d` (10,000 fresh paired seeds): primary H1 −0.08 pp (se 0.06), H4 +0.08 pp (se 0.11), H3 +0.01, H2 0: **the primary gate is not easier**. **But every H1/H4 robustness rate falls**: H4 BMP 6.99→6.03, one-way 6.01→5.23, KP 4.79→4.10, KPP 4.83→4.09, sign 6.62→6.06, rank 15.08→13.80; at production seeds **H4 `bmp_t` 7.20% (withheld) → 6.00% (p reported)**. The withholding gate is easier, and §9 F6 credits "the σ_d series" for it |
| 2 | G1 gates H4 on its own ΔSIGMA_D statistic and σ_d calibration; 4.75% on that statistic | **PARTIAL** | Runtime: 4.75% reproduced through `replicate()`'s second series with the σ_d calibration (φ 0.868, n 0.969); the σ_d mask keeps 262 of 262 H4 events (`d01 e`); the simulated statistic is the real one in 254 of 262 events (`d11`, corr 0.986). **Untested:** `d02` W4 (H4 on the cm30 calibration), W5 (cm30 mask), W6 (σ_d calibration from cm30/CRUSH), **W7 (H4 evaluated on the cm30 series, i.e. the pre-fix bug)**: all survive the full suite, `548 passed`. Fidelity gap: `g1.estimate()` re-estimates β on the σ_d series (`g1.py:197`); production ΔSIGMA_D uses the cm30 β (`window.py:221`) |
| 3 | H3 at φ = 1: 5.86% over 10,000 (blocks 5.25–6.25%); 6.45% was one block; φ = 0.995: 1.65% | **PARTIAL** | `d08`: the fixer's four blocks reproduce exactly (5.95/6.25/5.80/6.05); the fifth (5.25%) has no recorded seeds (`phi_dep.py` was overwritten) and cannot be re-run. 10,000 fresh seeds: **φ = 1: 5.63% (se 0.23)**, φ = 0.995: **1.82%** (se 0.13); sig0 0.03 vs calibrated at φ = 1: **+0.000 pp** (paired). 6.45% is 1.6 block-sd above, so "one block" holds. **But "inside the 6.30% bar" is wrong:** ADR 0005 §5 sets the bar "for the replications used"; at 10,000 it is **5.57%** (`g1.binom_band(10000)` = (0.0445, 0.0557)). Both 5.86% and 5.63% are above it: at φ = 1 the primary is measurably liberal (z ≈ 2.9). Not binding (calibrated φ 0.985), but `03-event-study.md:259-261`, `:544-545` and ADR 0005:26-28 misstate it |
| 4 | β pools only passing baselines (`window.py:188`); H1 −0.1994; median 0.309; new test fails without the fix | **SURVIVES** | `window.py:188` passes `clean & base_ok[:, None]`. `d04`: own β over passing baselines, each (security, session) once: 50 securities, max \|Δβ\| **6.1e-16**, 11,759 changes, 0 of the 3,168 failing-event changes shared with a passing baseline, median 0.3095, H1 −0.1994 (t −17.73). Falsifier (every clean change): Δβ 0.138, `falsify_rc=1`. `d02` W9 (revert line 188): see §2. Trivial: the β maximum prints 0.524 in §6.5 and §9 F2; the data round to 0.525 |
| 5 | Exactly the G1-oversized rows withheld; no primary; app handles null; the withholding step is tested | **PARTIAL; "tested" REFUTED** | `d06`: withheld set = oversized set (9 = 9); estimate kept 9/9, se kept on the 4 that have one (sign, rank, Patell have none), CI null 9/9; **0 of 4 primaries** null; `tests.json` `g1_size` = G1 rate 9/9. `d10` (esbuild bundle in scratch): committed file accepted; `g1_size` beside a p rejected; but a **withheld primary** and a withheld row **with its CI** are accepted (`results.ts:192` checks p only). **`d02` W1 (`results.py:128` → `out.append(new)`) and W2 (`run.py:174` → `mis_sized = {}`): SURVIVED, `548 passed`.** `test_the_committed_rows_withhold_exactly_the_oversized_statistics` (`test_g1.py:251`) reads the committed parquet and never calls `event_test_rows`: it **does not fail** when the step is removed |
| 6 | M11 is an equivalent mutant | **SURVIVES** | Proof: for p ∈ [0, 1] the top rank gives fl(fl(m·p)/m) ≤ fl(m/m) = 1 (monotone rounding), so min(1, ·) = min(∞, ·) there and the loops coincide after. `d03`: 100,000 vectors (m 1–300, exact 1s, ties, ulps below 1, subnormals): **0 differ**; 2,000 doubles below 1 × m 1–400: top value > 1 in **0**; NaN/<0/>1 raise in both. It rests on the guard: without `_probabilities`, [0.2, 1.5] gives [0.4, 1.0] vs [0.4, 1.5] (the guard's own mutant is killed, `fixer_mutants_rerun.txt`) |
| 7 | H2 counterfactual (G 7: p 0.0156, Holm 0.0938) by the same code path, shown wherever H2's Holm p is | **SURVIVES** (wiring untested) | `results.py:213-228` reuses `merge_small_seasons` and `suite.ramp`. `d05`, own merge and own 2^G enumeration: G 8 sizes 50/46/49/50/48/45/49/19, all season means > 0, p 0.007812; cut 2026Q4→2026Q3: G 7, 68 vs 45 (unbalanced), p **0.015625**, own Holm **0.093750** = committed row. Shown: README:195, §6.2:327/340, `tests.json` H2 `note`, Results page notes caption (`ResultsPage.tsx:93-97`), notebook 03 cell 8 prints the cut row, concept note 12:35, ADR 0005:749. `d02` W3 (the call dropped from `run_results`, `run.py:178`): **SURVIVED** |
| 8 | p08 15/16; p10 103/103; fixer's 21 killed; 79 + 3 header mutants, 78 tests | **SURVIVES** | `p08` re-run (my scratch copy): **15 of 16 killed**, each by the test named for it; M11 survived (equivalent, claim 6). `p10` (fixer's adjusted copy): **103 of 103**, byte-identical to the fixer's output. Fixer's mutants re-run: **16 of 16** (14 Python + 2 data) killed by their named tests; the 5 app mutants were **not re-run** (vitest not run here). Headers: 79 code + 3 data bullets; eight modules **78 passed** (64 test functions, parametrised) |
| 9 | No new data-policy problem; notices list dm_sd, beta_median, β min/max | **PARTIAL** | `check_data_files.py` on a staged scratch copy: `clean`; `scan_real_rows.py`: the same 3 pre-milestone lines. No `*_cboe`/β/VIX column in `data/derived` (only the count `beta_n` and the all-null `vix_regime`); `event_paths.json` per-event values = `aliv_mean_adj` (max diff 5e-5), not `aliv_cboe` (`d12`). DATA.md:17 lists all three. **`data/derived/LICENSE` lists dm_sd and beta_median but not β min/max**, although ADR 0004's cost bullet cites it for them. **DATA.md:17 says "no other per-company one", but §6.5:402 publishes six named per-company firm-cluster terms of the VIX-adjusted RUNUP / PERSIST_10** (`d09`: \|doc − market-adjusted\| ≤ 0.003; mean-adjusted 0.04–0.14) |
| 10 | `pytest -q -p no:cacheprovider` → 550 passed | **SURVIVES** | `uv run --frozen pytest -q -p no:cacheprovider` in the working tree: **`550 passed, 49 warnings in 51.21s`**, rc 0 (`out/d13_pytest_gate.txt`). Green, but see §2: 8 of the 9 wiring mutants below leave it green |

## 2. The fix round's wiring: mutants on a scratch copy, full suite each (`d02`)

The fixer's own mutants (re-run: 16 of 16 killed) all target pure helpers (`oversized`, `withhold`, `season_cut_rows`,
`generate`, `calibrate`). Nothing tests the lines that connect them to the run. Each mutant below ran the whole suite
(`-m "not dolt"`, 548 tests), with no `-x`, so every failing test is listed.

| Mutant | File:line | Result |
|---|---|---|
| W1 `event_test_rows` never withholds | `results.py:128` | **SURVIVED** (548 passed) |
| W2 `run_results` passes no mis-sized rows | `run.py:174` | **SURVIVED** |
| W3 `run_results` drops the season-cut row | `run.py:178` | **SURVIVED** |
| W4 H4's calibrated design uses the cm30 calibration again | `run.py:133` | **SURVIVED** |
| W5 σ_d design uses the cm30 usable mask | `run.py:104` | **SURVIVED** |
| W6 σ_d calibration from the cm30 series and CRUSH | `run.py:110` | **SURVIVED** |
| W7 `replicate()` evaluates H4 on the first (cm30) series: the pre-fix bug F5 fixed | `g1.py:258` | **SURVIVED** |
| W8 the calibrated design runs at the stress scale 0.03 | `run.py:130` | **SURVIVED** |
| W9 β pool back to every clean change | `window.py:188` | KILLED (`test_beta_pools_only_baselines_that_pass_the_minimum`) |

So F5 (H4's own series), F6 (withholding) and F1's row in `results` can each revert silently on the next
`stats.run`; only the committed parquet, which the tests read, would still look right until it is rebuilt.

## 3. Defects, by severity

1. **Major (tests).** The fix round's wiring is untested: W1–W8 survive (§2). *Fix:* (a) a synthetic `inputs.Frame`
   test of `event_test_rows(..., mis_sized={("H1", "cluster_date_t"): 0.2})` asserting that row's p and CI are null
   and the others are not; (b) a test of `replicate()` with `second` where the second design has another usable mask
   or T, asserting H4's decisions come from it (W7); (c) move the run wiring (`designs_sd`, `des_sd`, `cal_sd`,
   `mis_sized`, the season-cut call) into a pure function and test it on a fixture.
2. **Moderate (reporting).** "5.86% at φ = 1 (10,000 replications): inside / under the 6.30% bar"
   (`03-event-study.md:259-261`, `:544-545`; ADR 0005:26-28) applies the 2,000-replication band to 10,000. ADR 0005 §5
   sets the bar "for the replications used": 5.57% at 10,000. Measured 5.63% (fresh) and 5.86% (fixer): above it.
   *Fix:* "at φ = 1 the primary is liberal (5.6–5.9% over 10,000, band top 5.57%); it does not bind because the
   calibrated φ is 0.985."
3. **Moderate (withholding, disclosure).** Calibrating sig0 lowers every H4 robustness rate by 0.6–1.3 points
   (10,000 paired) and moves H4 `bmp_t` from 7.20% (withheld) to 6.00% (reported); §9 F6 (`:557`) credits "the σ_d
   series". The two H4 rows at the edge are a coin flip of one 2,000-replication block: sign 6.45% (withheld) and BMP
   6.00% (kept) read **6.06% and 6.03%** on 10,000 fresh seeds. *Fix:* state sig0's role in F5/F6; decide rows within
   about 1 point of the bar on ≥ 10,000 replications with that count's band.
4. **Minor (calibration reads the tested mean; pre-existing, not in the delta).** `jump_k` uses var(A_i / s_i)
   around company means (`g1.py:416-419`); a common shift does not cancel when s_i varies within a company, so the H1
   mean enters it. `d07`: day-0 ratio **4.70 → 3.32** with CRUSH demeaned, jump 2.70 → 2.14; H1 primary 4.45 → 4.60%,
   H1 robustness rows +1–3 points, no verdict changes; σ_d unaffected (2.785 → 2.789). The §6.1 tables call 4.70 a
   measurement "on the real baselines". *Fix:* use (A_i − Ā)/s_i.
5. **Minor (licensing notices).** DATA.md:17 says "no other per-company one", yet §6.5:402 names six per-company
   firm-cluster terms of VIX-adjusted RUNUP / PERSIST_10 (`d09`). `data/derived/LICENSE` does not list β min/max,
   although ADR 0004's cost bullet cites it for them. *Fix:* list the §6.5 firm terms in DATA.md (or print them on
   the mean-adjusted values), and drop the LICENSE citation from ADR 0004 or add the line.
6. **Minor (parser).** `results.ts:192` accepts a primary row with a null p and a `g1_size`, and a withheld row that
   keeps its CI. *Fix:* reject `g1_size` on `role = primary`, and a non-null CI beside a non-null `g1_size`.
7. **Minor (fidelity).** G1 re-estimates β for H4 on the σ_d series (`g1.py:197`), while production adjusts
   ΔSIGMA_D with the cm30 β (`window.py:221`). Its effect on a date-clustered t is absorbed; on sign and rank it is not
   modelled. *Fix:* say so in §6.1, or pass the cm30 β estimate to H4's `estimate()`.
8. **Minor (reproducibility).** The fifth φ = 1 block (5.25%) has no recorded seeds; `phi_dep.py` was overwritten.
9. **Trivial.** β maximum 0.524 should read 0.525 (§6.5, §9 F2). The Results page prints `withheld (G1 size 0.2275)`
   (`ResultsPage.tsx:44`), a fraction beside a caveat in percent.

## 4. Commands and integrity

From the repository root; `<s>` is this session's scratch folder (`…/scratchpad/m3delta`).

```
rsync -a --exclude node_modules --exclude .venv --exclude .pytest_cache ./ <s>/repo/   # and <s>/repo2/ (git add -A)
.venv/bin/python docs/validation/probes/m3/p08_mutants.py <s>/repo .venv/bin/python        # SUMMARY killed 15 of 16
uv run --frozen --no-sync python docs/validation/probes/m3-delta/d01_sig0.py 10000         # claims 1, 2
.venv/bin/python docs/validation/probes/m3-delta/d02_wiring_mutants.py <s>/repo .venv/bin/python   # 1 of 9 killed
uv run --frozen --no-sync python docs/validation/probes/m3-delta/d03_m11.py                # 0 of 100,000 differ
uv run --frozen --no-sync python docs/validation/probes/m3-delta/d04_beta.py               # and --falsify (rc 1)
uv run --frozen --no-sync python docs/validation/probes/m3-delta/d05_h2_cut.py             # 0.015625 / 0.093750
uv run --frozen --no-sync python docs/validation/probes/m3-delta/d07_jump_leak.py
uv run --frozen --no-sync python docs/validation/probes/m3-delta/d08_h3_phi.py             # 5.63% / 1.82% / band 5.57%
uv run --frozen --no-sync python docs/validation/probes/m3-delta/p10_adjusted_copy.py      # SUMMARY 103 of 103
.venv/bin/python docs/validation/probes/m3-delta/fixer_mutants_py_only.py <s>/repo2 .venv/bin/python  # 16 of 16
app/node_modules/.bin/esbuild <s>/entry_results.ts --bundle --format=esm --platform=node --outfile=<s>/results_parser.mjs
node docs/validation/probes/m3-delta/d10_parser.mjs <s>/results_parser.mjs
(cd <s>/repo2 && PYTHONPATH=src <repo>/.venv/bin/python tools/licensing/check_data_files.py)   # clean
uv run --frozen pytest -q -p no:cacheprovider                                            # 550 passed
bash docs/validation/probes/m3-delta/d99_integrity.sh <s>
```

`d06`, `d09`, `d11` and `d12` first ran inline; they are saved as `.py` files and re-ran with output identical to
`out/`. `d12`'s exact-number scan
of the JSON files is not diagnostic (4-dp collisions with thousands of per-event values; the mean-adjusted control
collides too); the structural check above it is the evidence.

**Integrity** (`out/d99_integrity.txt`): `git status --porcelain` differs from the start only by
`docs/validation/m3-delta-ledger.md` and `docs/validation/probes/m3-delta/`; the SHA-256 of all 516 other tracked and
untracked files and of the 33 stage files are identical to the snapshots taken before the first probe. Every mutated
scratch file was restored with `sha256 ok=True`.
