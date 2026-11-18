route: row 6 (a result that decides how the report shows the 2026 events) + row 2 (the check's code, under tests with hand mutants) | primary: the hash-frozen plan (preregistration.md), pushed before the run, with the code frozen in a second push before the run; one run | complement: Opus adversarial review of the plan's first draft (procedure only, synthetic data; §1.2) and a power and calibration simulation of the revised design (plan §12); after the run, a verifier (Sonnet) re-measures every figure and an Opus adversarial pass attacks the premise and the procedure | not-run: dual-channel EGV (no API-existence or library-semantics claim) | stop: §10's verdicts reached once, every figure re-measured once and attacked once

# The 2026 snapshot-timing check: ledger

Owner decision 2026-11-18 (report §9 Q9, option 3), relayed by the hub session. The plan is
[preregistration.md](preregistration.md); this file records what was frozen, when, and how it was checked.

## 1. The plan freeze

| Item | Value |
|---|---|
| plan | `docs/validation/snapshot-timing/preregistration.md` |
| plan SHA-256 | `0e7663232df05a328444c3228b1fb04a80b91040d9676a215fba02e479c0ff55` |
| timing map SHA-256 | `ed633f2bc8932e8f1ea9cb3ffde16ec23838e8a007ac7433478416785cdcb0c8` |
| commit | the commit that adds this ledger (its SHA is in §2, with the code freeze) |

The map's own `code_commit` reads `2b10b86…-dirty`: `tools/snapshot_timing_map.py` was not yet committed when it
wrote the map. It is committed with the map in this push; §2 records `--check` on a fresh clone of that commit,
which recomputes every class and compares.

### 1.1 Corrections made while the plan was written (before its push)

- **ln σ_d is a per-event series** (§4, §7). The first draft took X = ln `sigma_d_iv` of `iv_daily`. H4's ΔSIGMA_D
  holds E's expiry pair at day −1 fixed on both days (`measures/event_iv.py`), while `iv_daily` moves to the next
  event's pair after day 0, so its day-0 value is not H4's. I found this while writing the check, before any run,
  and the review found it too (§1.2, claim 2). The σ_d blocks now use the event's own pair, and block C must equal
  `dsigma_d_mean_adj` row by row. σ_d has no block O (no shift uses it): 7 blocks, not 8.
- **A plumbing mode** (§13 item 2): before the run, the tool may run on the real inputs only up to the blocks, with
  no fit, to check the sample sizes, the counts and the block-C equality.
- **The verdict's tests are the restricted wild cluster bootstrap** (§7, §10). The revised draft used the 90%
  unrestricted bootstrap-t interval. Its own first simulation (a scratchpad version of plan §12's script, 400 replications per configuration, 999
  draws). Its figures, and my re-runs of review claims 3 and 8 in §1.2, come from session scratchpad runs on code this
  commit replaces: they are recorded here, not reproducible from this commit showed that interval still under-covers: 86.0–90.0% at a nominal 90% and 90.75–94.25% at 95% across 6
  configurations, and P(SMALL) 0.09 for H1 with a true shift of 0.94 lines, against about 0.077 for an exactly
  calibrated test (a normal approximation with the simulated sd 0.0032). The verdict now uses one-sided tests with the null imposed at −L and +L. The unrestricted
  intervals stay as description. The second simulation (the committed script, 8 configurations, 400
  replications, 999 draws) measured the new tests: SMALL 5.8% (H1) and 6.5% (H4) with a true shift of exactly one
  line, and one-sided rejection at the true shift 2.8–7.0% at a nominal 5% (plan §12).

### 1.2 Adversarial review of the first draft (Opus, before the push)

Ten numbered claims; the default verdict was "this is broken". The reviewer read the first draft, the repo and the
local stage cache. It read no event measure split by class, and it modified no repo file. Its scripts are in the
session scratchpad (not committed). Verdicts: 1 survives, 4 partly correct, 5 refuted (the report's opening line says 5 and 4; its per-claim labels,
below, give 4 and 5). What I did with each:

| # | Claim of the first draft | Verdict | Checked by me | Action in the plan |
|---|---|---|---|---|
| 1 | The day classifier is adequate | SURVIVES: every company's slope of gap on −r from 2026-02-19 is 0.16–0.46 on off days, −0.01–0.06 on close days | not re-run (no action) | §3 cites it |
| 2 | §5's model is complete | REFUTED: H4's X was the wrong quantity; an intraday snapshot inflates E; eligibility depends on the class (5 of 98 against 4 of 250) | the H4 quantity: found independently while writing the code (§1.1) | §4, §7 per-event σ_d; §5 the E effect; §11 H7 flagged always; §14 eligibility |
| 3 | The neighbour identities hold | PARTLY: off days are busier VIX days (0.067 against 0.048, Welch p 0.020); day-0-off events are 25% Fridays against 15%; a half-repaid error hides half the shift | **reproduced** on new seeds: 0.0667 against 0.0483 | §7 adds Δln VIX (dm) and weekday dummies in P, A, C; §14 the half-repaid case |
| 4 | §8 catches a violation that matters | REFUTED: one-line violations rejected 16–31%; size 7.5–13.5% at a nominal 5% | consistent: in the revised design's first simulation the analytic F rejected 12.75–19.25% across the 6 configurations without a violation | §8 bootstrap p; §14 "failing it is strong evidence" removed |
| 5 | §9's formulas match the codebase | PARTLY: H1–H3 check out; H4 as claim 2 | no action beyond claim 2 | §9 s_e on the clean baseline |
| 6 | §6's ordering check | PARTLY: O2 fires 15.6% with no fault under an intraday reversal of the gap | not re-run: §6 became descriptive for the reasons in plan §6 | §6 descriptive, no FAULT |
| 7 | The power sketch and the rule | PARTLY: H1 P(SMALL) 0.83–0.86 (Gaussian), 0.51 (t3); H4 0.31; UNCLEAR close to certain overall | **re-measured** for the revised design (plan §12) | per-measure verdicts, no overall verdict; measured power table |
| 8 | The two-way CGM interval covers 95% | REFUTED: 87–94% across 9 configurations | **reproduced**: 91.0–93.7% on new seeds | the bootstrap (§7), then the restricted bootstrap (§1.1) |
| 9 | §2's disclosure is complete; the result is blind | REFUTED: edgar-coarse-ledger §9 items 5 and 6 were not listed; the phase-0 noise used close event days | verified: both items are in that ledger | §2 lists both and the phase-0 detail; §6 descriptive |
| 10 | Nothing was missed | REFUTED: H5–H7 not covered; robustness, path and PERSIST_1/5 tables not covered | agreed (no measurement needed) | §11 H5–H7 always get the columns; the other tables are named as not checked |

The review also warned that the check's code was on disk while the plan was being written. That is true: it was
drafted alongside the plan and run only on synthetic data (the tests and the simulation). Plan §2 says so, and §13
now pushes the draft with the plan and freezes it in a second push.

## 2. The code freeze

| Item | Value |
|---|---|
| plan push | `f59e5c5` (plan, map, ledger and the check's code) |
| code freeze | `f59e5c5`: no code changed after the plan push; this ledger commit changes `ledger.md` only |
| fresh clone of `f59e5c5` | plan and map SHA-256 equal §1; `tests/test_snapshot_timing.py` + layering: 69 passed; `tools/snapshot_timing_map.py --check`: "timing map ok: 84 off, 8 late, 3 unknown of 1222 sessions" |
| hand mutants | `mutants_check.py`: T1–T5 and C1–C19, 24 of 24 caught, module restored |
| full suite (working tree = `f59e5c5`) | 776 passed |

**Plumbing run** (`tools/snapshot_timing_check.py --plumbing`, 2026-11-18, on the real inputs; it stops before any
fit). Block C equals `crush_mean_adj` and `dsigma_d_mean_adj` row by row (the run stops otherwise). Counts:

| | n | day 0 off | day −1 off | both | day +10 off | late day +10 | Σ s_e (off baseline share) |
|---|---|---|---|---|---|---|---|
| H1 | 349 | 67 | 46 | 15 | | 1 | |
| H2 | 358 | | 51 | | | 1 | 56.58 (151 late baseline sessions in 30 events) |
| H3 | 331 | | | | 59 | 1 | 42.66 |
| H4 | 263 | 49 | 28 | 11 | | 0 | |

All equal the plan's §4 and §5a (H4: 49 + 28 − 11 = 66 events with day −1 or day 0 off). No crush or ΔSIGMA_D
event has day −1 or day 0 late or unknown. The lines equal the published se (0.011237, 0.017046, 0.023384,
0.011169).

Block rows (rows / off rows / ISO weeks), against the simulation of plan §12 (one world, every level present):

| Block | Real | Simulation |
|---|---|---|
| cm30 O | 16,879 / 1,278 / 100 | 18,690 / 1,382 / 104 |
| cm30 P | 288 / 37 / 69 | 297 / 45 / 69 |
| cm30 A | 303 / 35 / 69 | 308 / 35 / 70 |
| cm30 C | 349 / 67 and 46 / 75 | 349 / 67 / 75 |
| σ P | 203 / 27 / 63 | 227 / 35 / 66 |
| σ A | 168 / 18 / 58 | 241 / 25 / 68 |
| σ C | 263 / 49 and 28 / 74 | 263 / 49 / 74 |

**What this changes, recorded before the run:** the real data lack some `ok` snapshots and σ_d levels that the
simulation had, so the real blocks have fewer off rows, most of all for σ (P 27 against 35, A 18 against 25). The
simulated power is therefore an upper bound, most of all for H4, and the tests' size was measured with more treated
rows than the real blocks have. The plan is not changed; the results file will repeat this.

## 3. The run

| Item | Value |
|---|---|
| when | 2026-11-18T09:25:39−06:00; 17 s; exit code 0 |
| command | `.venv/bin/python -I tools/snapshot_timing_check.py` on a clean tree at `f2d0d37` (its code equals `f59e5c5`: `git diff --stat f59e5c5 f2d0d37` lists `ledger.md` only) |
| output | `aggregate.json` (plan and map SHA-256 equal §1; stage `d51877f495f7ae67`); the tool printed "verdicts {'H1': 'SMALL', 'H2': 'SMALL', 'H3': 'SMALL', 'H4': 'SMALL'}; identity rejected {'cm30': False, 'sigma': False}" |
| deviations | none |
| results | [results.md](results.md): all four SMALL; H4 by a narrow margin (p 0.040 and 0.036) |

The check ran once and is not run again. `aggregate.json` was scanned before the commit: no event id, ticker, date,
or per-day VX\* or IV value. One figure of results.md was re-derived by a separate script, not by the check: the
plan's +0.0546 for the 2026 crush gap is the mean of 50 companies' differences (+0.0546, se 0.0099), not D2's
regression (+0.0558); results.md §5 says so.

## 4. Validation after the run

_(verifier and adversarial pass)_
