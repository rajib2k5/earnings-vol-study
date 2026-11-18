route: rows 4 + 6 | primary: row 4, falsifier probes on synthetic data (planted code and data faults, metamorphic check M1, a second implementation from the ADR text), then one frozen run on GOOGL, GS, IBM | complement: block bootstrap as inference only, widened by a measured factor; row 6 before the owner acts on a phase-2 number: verifier (S) re-measures every figure, adversarial (O) attacks the procedure | not-run: dual-channel EGV (no API-existence or library-semantics claim); adversarial on values (no real-data value exists yet) | stop: phase 1 met after the adversarial review (22 of 22 probes as expected on seeds 1, 2, 3; the 7 null probes clear; M1 ok; §16), phase 2 not started

# IV checks after the VX\* slope result: pre-registration

Written on 2026-11-17, **before any check below was run on real data.** No option chain, Yahoo, Cboe or
`volatility_history` value was read to write it. Phase 1 used synthetic data only. An adversarial review of the first
version (synthetic data only) found gaps; §16 lists every change made for it, also before any real-data value was
read. The owner records the SHA-256 of this file in a ledger before phase 2 starts. Phase 2 starts with the first run
of these checks on real data. A change to this file or to a file in `probes/` after that is a deviation (§14).

## 1. Why

The pre-registered VX\* cross-check ([vx-preregistration.md](../vx-preregistration.md), results in
[vx-ledger.md](../vx-ledger.md)) met ADR 0003's falsifier. The OLS slopes of daily Δln VX on daily Δln ours are AAPL
0.835, AMZN 0.814, GOOGL 0.773, GS 0.786 and IBM 0.658. The ADR says: "Then the atom (forward, filters,
interpolation) is wrong before anything else is." The weekend-clock explanation is refuted: on Tuesday-to-Friday
changes the pooled slope is 0.745. Slopes rise over longer horizons. That pattern fits day-to-day noise in our series
(see "attenuation" in §2).

Owner decision, 2026-11-17: check the forward, the filters and the interpolation on **GOOGL, GS and IBM**. Widen to
all five names only if a check finds a fault. A fault must be reproduced before it is fixed. Fixing is not part of
this work.

## 2. Words

| Word | Meaning here |
|---|---|
| change | ln(value on session t) − ln(value on session t−1), where t−1 is the session just before t. |
| atom | One expiry's ATM total variance w on one session (ADR 0003 §0). `iv_atm` = √(252 w / τ). |
| forward | The put-call-parity forward F of one expiry (ADR 0003 §0 step 2). |
| quote filter | ADR 0003 §0 step 1, first part: 0 < bid < ask, mid ≥ 0.05, (ask − bid)/mid ≤ 0.5 (`forward.quote_ok`). |
| listed | A leg (call or put of one strike) is listed when its bid and its ask are both numbers. A leg that is absent from the file, or has an empty bid or ask, is not listed. A leg with bid 0 is listed and fails the quote filter. |
| interpolation in k | How the atom gets w at k = ln(K/F) = 0 from the strikes: a straight line between the two strikes around F (the bracket), else a weighted quadratic (§0 step 4). |
| interpolation in τ | How `cm30_iv` gets the 21-session value from the expiries (ADR 0003 §b). |
| share | The part of the variance of the daily changes that one component causes. 0.10 = 10%. |
| switch | Between t−1 and t, the inputs of an estimate changed: other bracket strikes, another method, or another expiry pair. |
| switch-excess share | (fraction of changes that switched) × (variance of switch changes − variance of no-switch changes) ÷ (variance of all changes). If a switch adds noise, switch changes vary more. |
| injection share | Add a second dose of the measured forward noise to every atom, and divide the variance this adds to the changes by the variance of the changes. |
| common-mode forward error | A forward error that is the same for every expiry of a session. The cross-expiry difference that measures σ_f cancels it, so the forward rule cannot see it (§11.7). |
| block bootstrap | Redraw runs of 20 consecutive sessions with replacement, recompute the statistic, repeat 10,000 times. The spread of the results shows how much the statistic could move by chance. Runs keep the day-to-day dependence. |
| lo, hi | From the bootstrap: lo_raw is the 0.05/12 quantile of the 10,000 results (one-sided, Bonferroni over 12 rules), hi_raw the 0.95 quantile (one-sided 95%). Then both are moved away from the point by the rule's widening factor c: lo = point − c (point − lo_raw), hi = point + c (hi_raw − point). |
| widening factor | c = (standard deviation of the point over 48 synthetic seeds with no fault) ÷ (mean bootstrap standard deviation), at least 1 (§6). The bootstrap was too narrow for most rules. |
| Bonferroni | Divide the error rate by the number of rules (12), so that a false FAULT somewhere among them has a chance of 5% at most. |
| attenuation | If our change = true change + independent noise, the slope of VX on ours falls to about var(true)/var(ours). Then 1 − slope ≈ the noise share of our changes. |
| oracle | On synthetic data only: the same world with and without the planted fault, with identical random numbers. 1 − var(changes without)/var(changes with) is the true share of the fault. |

## 3. Sample, code path and window

- **Names:** GOOGL, GS, IBM. AAPL and AMZN only as descriptive reference (§11), unless §10 widens.
- **Window:** every session of the name from 2020-01-02 to 2026-10-26 (`params.yaml` `snapshot_eras.data_end`), at
  options commit `msfqpodh24viv7prdqdan8517rkjp861`.
- **Changes:** pairs of consecutive NYSE sessions (t−1, t) where both snapshots are `ok` in `session_snapshot` (not
  `stale_repeat`, not `missing`) and neither session is day −1, 0 or +1 of any event anchor of the name
  (`tables.event_anchors`). These are the "non-event days" of the brief. The dropped counts are reported.
- **Code path, frozen at commit `f5904a9`:** the panel is built as `measures/run.py run_iv` builds it:
  `run.snapshot_quotes` on the option-chain month files (calls and puts merged on strike with an outer join, so a
  missing leg has an empty bid and ask, see "listed" in §2), `r_cont` from `market_daily`, anchors from
  `tables.event_anchors`. Every atom comes from `tables.chain_rows` → `chain.expiry_atom` on one expiry, and every
  session from `tables.iv_daily_row` → `termstructure.day_measures`. Parameters: the `iv` block of `params.yaml`
  (SHA-256 in §13). The checks never change this code. They change only its input: a forward multiplied by e^ε, the
  quotes of the synthetic-truth surface, or the choice of which changes to compare. Code: `probes/ivchecks.py`,
  function `run_name`.
- **The calendar and the events** for rules (a) and (b) are derived a second time, not taken from the package: τ from
  an `exchange_calendars` XNYS list (2019-01-02 to 2031-12-31; a date outside it is an error), and day 0 and
  `spans_from` from the rows of `events.parquet` (`ivchecks.own_events`).
- **The driver** `probes/phase2.py` is frozen now. It runs the gates, every rule per name, the robustness rerun, the
  verdict table and the §10 outcome. Its only stub is the **loader** (`load_panel` in `loader.py`, beside this file
  and outside `probes/`), which turns the stage files into a `Panel`. The loader is written at the start of phase 2
  and computes no statistic. It is not in `probes/SHA256SUMS`, so writing it does not stop gate G2; `phase2.py` reads
  its bytes once, records their SHA-256 in `aggregate.json`, and runs those same bytes. Gate G4 (§8) proves the
  loader: it must reproduce every field of the staged `chain_expiry` and `iv_daily` rows of the name exactly.

## 4. What counts as a fault

| Class | Definition | Examples |
|---|---|---|
| (a) bug | The code does not do what ADR 0003 or `params.yaml` says. | A wrong parameter value, a wrong strike ranking, a wrong pair in the interpolation, a wrong event class. |
| (b) ADR falsifier | A falsifier that ADR 0003 already states is met. | Parity forward vs Yahoo close, median above 10 bp. Synthetic truth not recovered to 1e-6. |
| (c) measured defect | One component alone carries at least **10%** of the variance of the daily IV changes on non-event days. | Forward noise, quote filtering, strike switches, expiry rolls. |

**Not a fault:** a different design choice that would only move our IV closer to Cboe's. For example: a VIX-style
model-free variance, calendar-day time, interpolation in calendar time, or another expiry set. **Our IV is never tuned
to match Cboe.** Cboe is used once, descriptively (§11.5), and no rule reads it.

**Why 10%.** Under attenuation, the slopes imply that noise is about 1 − slope of the variance of our changes: GOOGL
0.23, GS 0.21, IBM 0.34. One component at 10% would explain a third to a half of that gap. Below 10%, a component
cannot explain most of the gap alone. The number was fixed here, before phase 2.

## 5. The checks

Each rule runs on each of GOOGL, GS and IBM. Rows marked (c) are the 4 statistics of the Bonferroni family (4 × 3
names = 12).

| Component | Rule | Statistic | Observations | Code |
|---|---|---|---|---|
| Whole atom and §b | (a) differential | Every atom and every `ok` session, compared with a second implementation written from the ADR text (`probes/ref_spec.py`), which reads its own atoms, τ from the calendar list, DF from `r_cont`, and the event class from `events.parquet`. Atom: `tau_sessions`, `df`, `spans_next_event` (the calendar); status, `forward_n_strikes`, `n_strikes_valid`, `atm_method`, `strike_lo`, `strike_hi` exact; `forward` within 1e-9 relative; `w_atm`, `iv_atm` within 1e-8 relative. Session: `sessions_to_next_event`, `cm30_method`, `cm30_exp_lo`, `cm30_exp_hi` exact; `cm30_iv`, `cm30_blind_iv`, `event_var`, `sigma_d_iv` within 1e-8 relative. Every mismatch gets a tag from the code (§6). | Every atom and every `ok` session of the window. | `differential` |
| Whole atom and §b | (b) synthetic truth | ADR 0003's own falsifier: every quote of the real panel is replaced by a two-component surface (w = σ²τ + E for an expiry that spans the next event, flat smile, ±0.01 spread) on the **real** strikes, legs, expiries, sessions and events. The package must recover E, σ_d, `cm30_iv`, `cm30_blind_iv` (the §b interpolation of the true w's) and `sessions_to_next_event` within 1e-6. τ, DF and the event class (BMO and AMC) are derived inside the check from the calendar list and `events.parquet`. | Every `ok` session. | `synthetic_truth` |
| Forward | (b) forward vs close | d = (Δln F of the shortest expiry usable on t−1 and `ok` on t) + r_{t−1} × calendar days / 365 − Δln(Yahoo close). FAULT when median \|d\| > **10 bp** (ADR 0003, "How we'll know it's wrong"). A 95% block-bootstrap interval is reported beside it. | Every change; sessions that are ex-dividend dates are skipped, because the forward return is a total return and the close return is not. | `yahoo_obs` |
| Forward | (c) injection share | σ_f² = var(Δln F_e1 − Δln F_e2)/4 over every pair of expiries usable on both days with no ex-dividend date in (e1, e2]. Then 20 draws: every atom of every session gets F × e^ε, ε ~ N(0, σ_f²), seed `[20261117, session, expiry, draw]`. Share = var(response) / var(y), response = change with ε − actual change, y = actual change of ln `iv_atm`. In each bootstrap replicate the share is scaled by σ_f²(replicate)/σ_f². | Every (change, expiry usable on both days) whose 20 perturbed atoms are all usable. | `forward_pairs`, `forward_injection`, `injection_stat` |
| Filters | (c) filter switch-excess | Switch-excess share with group = "filter" changes. | See "strike observations" below. | `strike_obs`, `excess_stat` |
| Interpolation in k | (c) strike switch-excess | Switch-excess share with group = every change whose bracket or method moved (listing, filter or other). | See "strike observations" below. | `strike_obs`, `excess_stat` |
| Interpolation in τ | (c) roll switch-excess | y = change of ln `cm30_iv`; ref = the usable expiry listed on both days with the largest τ (it never rolls between the two days); u = y − change of ln `iv_atm`(ref); switch = the pair (`cm30_exp_lo`, `cm30_exp_hi`) differs between the days. | Every change with `cm30_iv` on both days and the same event class on both days (a class switch is excluded: it is the event approaching, not a roll) and a common usable expiry. | `roll_obs`, `excess_stat` |

**Strike observations.** One per (change, expiry e usable on both days, with another such expiry).
y = change of ln `iv_atm`(e). The cause of a switch (`strike_change`) is the first that applies:

- **listing:** a call or put inside the span is listed on one day only;
- **filter:** a leg inside the span is listed on both days and passes the quote filter on one day only;
- **other:** the bracket strikes or the method changed for another reason (F crossed a strike, the out-of-the-money
  leg changed side, a no-arbitrage bound or the root search failed on one day);
- **none:** nothing above. The span is the union of the two days' brackets, or, when either day used the quadratic, the
  union of the two windows |k| ≤ 2√w.

u = y − change of ln `iv_atm`(ref), which removes the move common to all expiries. **Clean reference** (decides):
ref = the other expiry with cause "none" and the nearest τ (ties: the longer one). Then the reference adds the same
noise in every group. A change with no clean reference is left out and counted. **Any reference** (guard): ref = the
nearest other expiry, nothing left out. A fault that hits every expiry of a session at once leaves no clean
reference on that session, so the clean version cannot see it; the guard of §6 stops a NO FAULT there.

## 6. Decision rules for one rule on one name

- **(a):** MATCH or MISMATCH. The code tags every mismatching atom or session (`ivchecks.differential`), with the
  first tag that applies:
  - no tag, when a calendar field differs (`tau_sessions`, `df`, `spans_next_event`, `sessions_to_next_event`);
  - `upstream`, a session whose atoms already mismatch;
  - `S1`, an expiry with a strike listed twice;
  - `S2` to `S6`, a point where the ADR is silent (`probes/ref_spec.py`), when an alternative choice removes the
    mismatch **and is consistent**: no matching atom (or session) where the point matters, and every mismatching
    one where it matters is removed by the same alternative;
  - `S7`, the reference met w\* ≤ 0;
  - `boundary`, an input within 1e-9 (relative) of a threshold. Every record keeps this distance (`margin`).

  MISMATCH when at least one mismatch has no tag. Tagged mismatches are reported as "unspecified", with their count
  and tags. Only the code tags; nothing is labelled "unspecified" by hand. A MISMATCH is a fault (a) once it is traced
  (§10) to an input where the package contradicts the ADR text or `params.yaml`.
- **(b):** FAULT or NO FAULT, by the ADR's own line (10 bp on the median; 1e-6 on the worst error).
- **(c):** FAULT when lo > 0.10. NO FAULT when hi < 0.10. Otherwise UNCLEAR. Bootstrap: moving blocks of 20 sessions
  on the name's session axis, 10,000 replicates, seed 20261117, one draw matrix per name.
  - Why two different bounds: a FAULT on any of 12 rules is a claim about the family, so lo uses 0.05/12. "No fault"
    is only claimed when every rule clears; a claim that needs every test to pass needs no correction (the
    intersection-union principle), so hi uses 0.05.
  - **Widening.** lo and hi are moved away from the point by the rule's factor c (§2): forward 1.35, filter 1.1,
    strike 1.35, roll 1.2 (`ivchecks.INFLATE`). They were measured by `probes/calib.py` on 48 synthetic seeds (101 to
    148) of each rule's world with no fault (`probes/calib.out`):

    | Rule (world) | sd of the point over seeds ÷ mean bootstrap sd, blocks of 20 | blocks of 60 |
    |---|---|---|
    | forward (clean) | 1.34 | 1.43 |
    | filter, clean ref / any ref (flat_filter) | 0.86 / 1.09 | 0.96 / 1.25 |
    | strike, clean ref / any ref (lowvol) | 1.31 / 1.08 | 1.50 / 1.21 |
    | roll (clean) | 1.15 | 1.23 |

    c = the larger of the two references, rounded up to 0.05, at least 1. The ratio is itself an estimate (relative
    standard error about 10% with 48 seeds). A first run with 16 seeds gave 0.92 for the forward rule, while the
    reviewer's seeds 1 to 12 give 1.71 (reproduced here): one reason for 48 seeds.
  - UNCLEAR, whatever the share: fewer than 100 observations; or more than 20% of the candidate observations unusable
    (forward: an unusable perturbed atom; roll: no value or no common expiry; strike and filter, any reference: no
    other expiry).
  - Switch-excess rules: fewer than 30 no-switch changes → UNCLEAR. Fewer than 30 switch changes → NO FAULT if the
    group's whole spread, Σ(u − mean u of the no-switch changes)² ÷ ((n − 1) var(y)), is below 0.10 (that is an
    upper bound of the share), else UNCLEAR.
  - **Strike and filter: the clean reference decides, and NO FAULT also needs the any-reference version to say NO
    FAULT** (hi < 0.10, or the small-group bound above). Otherwise the verdict is "UNCLEAR (any reference does not
    clear)". The any-reference version never decides a FAULT: on a fault that hits every expiry of a session it
    over-reads by 1.4 to 2.2 (§7).

## 7. Falsifier probes (synthetic data only)

`probes/run_probes.py` builds synthetic panels (`probes/synth.py`, its own Black-76, 500 XNYS sessions from
2024-09-12, 3 or 4 expiries a day like the real chain, quarterly events that alternate before-open (BMO) and
after-close (AMC), a day-0 jump), runs `run_name` on each, and checks each rule's verdict. The worlds are defined once
in `probes/worlds.py`. Every random draw comes from a stream keyed by (seed, purpose, session, expiry, strike), so a
planted world and its control share the market path and the quote noise.

Command, from the clone (the `-I` flag is safe because the script inserts the clone's `src` first and stops if
`earnings_vol` is imported from anywhere else). `--out` must be outside this folder; the script never writes here:

```
~/dev/earnings-vol-study/.venv/bin/python -I docs/validation/vx-iv-checks/probes/run_probes.py --out DIR --seed 1
```

The frozen outputs `probes/run_probes.seed1.out`, `.seed2.out`, `.seed3.out` and the `.json` files beside them were
copied by hand from runs into a scratch folder. Each `.out` ends with one `elapsed:` line, the only line that changes
between runs. Exit status 0 on all three seeds: every probe gave its expected verdict, every oracle condition held, M1
held, and P12 is not vacuous.

| Probe | Rule | Planted | Expected | Seed 1 / 2 / 3 measured |
|---|---|---|---|---|
| P01 | (a) | nothing | MATCH | 0 mismatches; 1,603 / 1,598 / 1,609 atoms, 500 sessions |
| P02 | (a) | params drift: forward from 3 strikes | MISMATCH | untagged 1,603 / 1,594 / 1,609 |
| P03 | (a) | params drift: min mid 0.10 | MISMATCH | untagged 5 / 214 / 194 (seed 2: 4 more tagged `boundary`) |
| P04 | (a) | params drift: bracket limit 0.1 sd | MISMATCH | untagged 833 / 1,510 / 1,545 |
| P05 | (a) | code: interpolation takes the shortest expiry ≤ 21 | MISMATCH | untagged 500 / 500 / 500 sessions |
| P06 | (b) forward vs close | nothing | NO FAULT | median \|d\| 0.84 / 1.06 / 0.82 bp |
| P07 | (b) forward vs close | code: forward from the 1 strike with the largest \|C − P\| | FAULT | 16.75 / 16.06 / 16.66 bp |
| P08 | (b) synthetic truth | nothing | NO FAULT | worst error 4.0e-15 / 5.5e-15 / 4.2e-15 |
| P09 | (b) synthetic truth | code: τ counts the snapshot session | FAULT | E error 2.5e-4, `cm30_iv` error 1.1e-2 (each seed) |
| P10 | (c) forward | nothing (σ_f 1.17 / 1.39 / 1.17 bp) | NO FAULT | 0.004 [0.002, 0.005] / 0.004 [0.003, 0.005] / 0.004 [0.003, 0.005] |
| P11 | (c) forward | code: forward from the 4 largest \|C − P\| | FAULT | 0.356 [0.200, 0.466] / 0.172 [0.100, 0.227] / 0.270 [0.157, 0.368] |
| P12 | (c) filter | data: OTM leg of the strike nearest F fails the filter on 25% of (session, expiry), no smile: 229 to 253 filter switches that add almost nothing (oracle 0.002 / 0.005 / −0.004) | NO FAULT | −0.016 [−0.064, 0.011] / 0.041 [−0.008, 0.077] / 0.033 [−0.017, 0.072]; any ref NO FAULT on each |
| P13 | (c) filter | data: OTM legs of the 2 strikes nearest F fail the filter on 50% of (session, expiry) | FAULT | 0.229 [0.115, 0.296] / 0.261 [0.165, 0.337] / 0.358 [0.201, 0.474] |
| P14 | (c) strike | nothing (vol 15%, strikes every 2.5%) | NO FAULT | 0.023 [−0.041, 0.076] / 0.010 [−0.009, 0.024] / 0.014 [−0.026, 0.041] |
| P15 | (c) strike | data: the 2 strikes nearest F unlisted on 50% of (session, expiry) | FAULT | 0.293 [0.172, 0.373] / 0.369 [0.236, 0.461] / 0.370 [0.221, 0.479] |
| P16 | (c) roll | nothing | NO FAULT | −0.002 [−0.008, 0.001] / −0.001 [−0.004, 0.000] / −0.002 [−0.008, 0.001] |
| P17 | (c) roll | data: diffusive term structure (τ/21)^−0.4 | not NO FAULT | UNCLEAR 0.485 [0.022, 0.622] / 0.516 [0.015, 0.621] / 0.542 [0.012, 0.643] |
| P18 | (c) roll | data: monthly expiries 1.5 vol points above the weeklies | FAULT | 0.235 [0.132, 0.305] / 0.198 [0.126, 0.255] / 0.313 [0.196, 0.389] |
| P19 | (c) filter | data: OTM legs of the 2 strikes nearest F fail the filter on 15% of **sessions**, every expiry at once (oracle 0.129 / 0.170 / 0.210) | not NO FAULT | UNCLEAR (any reference does not clear) on each; clean ref −0.001 / −0.000 / 0.002 with 8 / 2 / 3 switches; any ref 0.180 / 0.375 / 0.391 |
| P20 | (c) strike | data: the 2 strikes nearest F unlisted on 12% of **sessions** (oracle 0.121 / 0.167 / 0.155) | not NO FAULT | UNCLEAR / UNCLEAR (any) / UNCLEAR (any); clean ref 0.036 / 0.015 / 0.024; any ref 0.241 / 0.360 / 0.285 |
| P21 | (b) synthetic truth | code: an expiry spans only from day 0 on (an AMC announcement-day expiry becomes clean) | FAULT | σ_d error 6.7e-2, `cm30_iv` error 3.4e-2 (each seed) |
| P22 | (a) | the same code fault | MISMATCH | untagged 10 (`spans_next_event`) on each seed |
| M1 | metamorphic | no strike ever listed or unlisted | 0 "listing" switches | 0 on each seed |

The null probes (no fault: P01, P06, P08, P10, P12, P14, P16) clear on all three seeds. P17 was FAULT on seeds 2 and
3 before the widening; it is UNCLEAR on all three now, which its expectation allows (§9.4).

**Check against oracle (check ÷ oracle), seeds 1 / 2 / 3.** Above 1: the check over-reads; below 1: it under-reads.

| Planted fault | Check | Oracle | Check ÷ oracle |
|---|---|---|---|
| P11 forward | forward rule | 0.172 / 0.120 / 0.188 | 2.07 / 1.43 / 1.44 |
| P13 filter | filter rule | 0.293 / 0.376 / 0.402 | 0.78 / 0.69 / 0.89 |
| P15 strike | strike rule | 0.301 / 0.349 / 0.406 | 0.97 / 1.06 / 0.91 |
| P17 roll, slope | roll rule | 0.550 / 0.592 / 0.625 | 0.88 / 0.87 / 0.87 |
| P18 roll, monthly | roll rule | 0.236 / 0.149 / 0.170 | 1.00 / 1.33 / 1.84 |
| P19 session filter | filter rule, clean ref | 0.129 / 0.170 / 0.210 | about 0 |
| P19 session filter | filter rule, any ref | the same | 1.40 / 2.21 / 1.86 |
| P20 session strike drop | strike rule, clean ref | 0.121 / 0.167 / 0.155 | 0.30 / 0.09 / 0.15 |
| P20 session strike drop | strike rule, any ref | the same | 1.99 / 2.16 / 1.84 |
| Common forward error, 10 bp (out of family) | forward rule | 0.190 / 0.176 / 0.258 | 0.14 / 0.13 / 0.04 |
| Common forward error, 10 bp (out of family) | strike rule (strike observations) | 0.198 / 0.182 / 0.265 | 0.48 / 1.23 / 0.53 |

**Directions.** The forward and roll rules can over-read (up to 2.1). The filter rule under-reads (0.69 to 0.89): a
filter fault with a true share up to about 0.10 ÷ 0.69 ≈ 0.14 could still give NO FAULT. The clean reference cannot
see a fault that hits every expiry of a session (P19, P20); the guard turns its NO FAULT into UNCLEAR, but such a fault
never reads FAULT. The any reference reads 0.54 to 1.01 of the oracle on the per-expiry faults (P13, P15) and 1.4 to
2.2 on the session-wide faults (P19, P20); it is a guard only and never decides a FAULT. The forward rule does not
see a common-mode forward error (0.04 to 0.14 of the oracle); the strike rule reads part of it as strike noise (0.48
to 1.23). A (c) FAULT therefore needs the reproduction in §10 before anyone acts on it.

**Common-mode forward error (descriptive, not a probe verdict).** Run `fwdcommon` adds an error of 10 bp, the same for
every expiry of a session (`mutants.fwd_common`). The forward-vs-close line reads 9.51 / 9.01 / 9.57 bp (NO FAULT,
just under its 10 bp line) and the forward rule NO FAULT, while the oracle share is 0.19 / 0.18 / 0.26. The strike
rule is UNCLEAR on each seed. The descriptive upper bound of §11.7 reads 0.363 / 0.233 / 0.378 at the fixed-expiry
level (above the oracle on each seed, as an upper bound must) and 0.135 / 0.121 / 0.181 for `cm30_blind_iv` (oracle
0.057 / 0.053 / 0.174).

**Power notes (not probes).** (1) A forward from the 4 largest \|C − P\| reads 9.69 / 9.68 / 8.54 bp on the ADR's
forward-vs-close line (NO FAULT on all 3 seeds), while it carries 12% to 19% of the variance (oracle). The (b) line
alone cannot clear the forward. (2) A milder term structure, (τ/21)^−0.25, gives roll UNCLEAR on all 3 seeds
(oracle 0.30 / 0.33 / 0.37). (3) The "two shortest expiries" interpolation mutant is not seen by the roll rule (it only
changes `cm30_blind_iv`), but (a) catches it.

## 8. Gates (phase 2 stops at the first gate that fails)

All five are code in `probes/phase2.py`; G1 and G2 also run alone (`--gates G1,G2`).

- **G1 import path and environment.** `earnings_vol` is imported from the clone's `src` at commit `f5904a9`, with
  `git status --porcelain -- src params.yaml` empty. Measured on 2026-11-17: `PYTHONPATH=<clone>/src python -I` imports
  the venv's editable install (the live `~/dev/earnings-vol-study/src`), because `-I` ignores `PYTHONPATH`. Every
  script inserts the clone's `src` into `sys.path` itself and asserts the import location. The venv's package list
  (`name==version` from `importlib.metadata`, the list `pip freeze` reads, with the Python version) equals
  `probes/env.freeze.txt`: Python 3.12.13, numpy 2.5.4, pandas 3.1.0, exchange-calendars 4.13.2, pyarrow 26.0.0,
  scipy 1.18.1, pyyaml 6.0.3, and 121 more lines.
- **G2 frozen checks.** The SHA-256 of `probes/SHA256SUMS` matches §13, and every file it lists matches it; no other
  file is in `probes/`. A rerun of `run_probes.py --seed 1` into a scratch folder exits 0 and reproduces
  `probes/run_probes.seed1.out` line for line (except the `elapsed:` line) and `probes/run_probes.seed1.json` byte for
  byte. Every script sets one BLAS thread, so the sums run in the same order every time. G2 also records the SHA-256
  of the `loader.py` that the run uses (in its report line and as `loader_sha256` in `aggregate.json`); nothing
  checks that value.
- **G3 frozen inputs.** The SHA-256 of every input file in §13 matches.
- **G4 loader.** For each name, the panel from `loader.load_panel`, run through the package's own path, reproduces
  **every field** of the staged `chain_expiry.parquet` and `iv_daily.parquet` rows of the name on every `ok` session:
  the same rows, the same values, nulls in the same places (exact, no tolerance). The one column left out is
  `snapshot_date`: the checks pass the session as the snapshot date and never read it. A fix to `loader.py` to pass G4
  is allowed and listed, because G4 forces the loader to reproduce the study exactly. The comparison itself
  (`gate_g4`) is in the frozen `phase2.py`.
- **G5 privacy.** `phase2.py` writes per-name results (with the dates of mismatching atoms) only to
  `$VOL_DATA_DIR/earnings-vol-study/vx-iv-checks/` (local). Only `aggregate.json` may be committed: per name and rule
  n, shares, bounds, verdicts, counts. No per-day value of any series, and no Yahoo or Cboe value.

## 9. What the probes changed in the design (before any real data)

The probes are there to find a check that cannot fail. They found two in the first version, and the review found
more (§16). The changes:

1. **Holding listing and filter fixed.** The first design removed a quote that was listed (or passed the filter) on
   one day only from both days, and compared variances. On the planted worlds it under-read the oracle: listing 0.100,
   0.167, 0.261 against oracle 0.292, 0.345, 0.407 (vol 15%, seeds 1 to 3); with a curved smile (smile_c 0.3) it fell
   below zero (−0.84, −0.28, −0.36 against oracle 0.36 to 0.97). The cause: an atom with the quote removed on both days
   has its own day-to-day error. The switch-excess share replaced it. The scratch script that measured this no longer
   runs against the final `ivchecks.py`. These numbers are design history, not probes.
2. **Two references must agree.** Tried and dropped: the any-reference version is noisier and made P13 to P15
   UNCLEAR. After the review it came back as a one-way guard (§6): it can stop a NO FAULT, never make a FAULT.
3. **Bounds.** The first version used a two-sided 0.05/12 interval for both FAULT and NO FAULT. It made P14 (a world
   with no fault) UNCLEAR (hi 0.104). §6 gives the reason for the one-sided bounds.
4. **P17.** Its share comes from about 4 changes where `cm30_iv` switches from `two_component` to `interp_spanning`
   near an event, with Δln up to 0.55. A share carried by so few changes cannot clear lo on every seed. P17 is
   therefore "must not clear", and P18 is the roll rule's falsifier that must flag.
5. **The null filter world (new P12).** The old P12 had no filter switch at all, so it could not fail. Its replacement
   needs filter switches that add almost nothing, so it has no smile. Three switch rates were tried, with the widening
   in place: 50% of (session, expiry) gave UNCLEAR on seed 1 (hi 0.101), 30% gave UNCLEAR on seed 2 (hi 0.104), 25%
   cleared on seeds 1 to 3. The 25% world was chosen **after** these probe seeds were seen. Its calibration run on 48
   other seeds (101 to 148) then gave NO FAULT on 48 of 48 for both references (`probes/calib.out`). So: when filter
   switches are very frequent, the clean reference has few no-switch changes left, and the filter rule loses power to
   say NO FAULT. That is a limit of the rule, reported here, not hidden.
6. **The strike part of the blind residual (§11.6)** first used a clean reference too. It kept 45 of 467 changes in the
   synthetic world with no fault, so it uses the nearest usable expiry outside the pair (any reference) instead.

## 10. What each outcome leads to

`phase2.py` computes the outcome from the verdict table; a missing rule or an unknown verdict is an error.

- **No fault:** every (a) MATCH, every (b) and (c) NO FAULT, on all three names. It means: **no single tested
  component carries 10% or more of the variance of the daily IV changes, on the denominator each rule uses** (the
  changes of `iv_atm` at fixed expiries for forward, filter and strike; the changes of `cm30_iv` for roll). It does
  not say that the tested components together explain the slopes, and it says nothing about the components of
  §11.8. Report it with the descriptive numbers of §11, the residual line (§11.6) and the common-mode upper bound
  (§11.7) beside it. Do not widen. The owner decides the next step.
- **Fault:** at least one MISMATCH or FAULT on at least one name. First reproduce it, then widen:
  1. *Mechanism trace:* the 20 observations that contribute most (largest \|u\| in the group, largest \|response\|, or
     the untagged mismatching atoms) are traced to their quotes, strikes and expiries, and the mechanism is named.
     **A strike or filter FAULT is first checked against a common-mode forward error** before the strike rule is
     blamed: compare the 20 changes with the forward-vs-close series d on the same sessions, and read the common-mode
     upper bound (§11.7). In the probes a 10 bp common forward error made the strike rule read 0.10 to 0.22, and FAULT
     in the reviewer's first run, while no strike fault was planted.
  2. *Minimal reproduction:* one real change (or one mismatching atom) is rebuilt step by step from its quotes by the
     ADR's steps, and shows the IV move that the mechanism causes. For (a), that input becomes a small test case.
  3. *Robustness (reported, does not decide):* every (c) rule with blocks of 60 sessions and seed 20261118
     (`phase2.run_one`). It runs for every name in every outcome. In the synthetic calibration, blocks of 60 gave a
     narrower bootstrap than blocks of 20 (§6 table), so it is not a more conservative version.
  4. Then run every rule on **AAPL and AMZN**, unchanged, with Bonferroni k = 8 (4 statistics × 2 names), and report
     per name (`phase2.py --widen`). A fault that cannot be reproduced in steps 1 and 2 is reported as "flagged, not
     reproduced", and is not widened.
  Fixing is not part of this work.
- **Unclear:** no FAULT, at least one UNCLEAR. Do not widen. Report which rule and why (a gate, an interval across
  0.10, or the any-reference guard). The owner decides: accept it, or test the same frozen rules on sessions after
  2026-10-26 that nobody has seen yet. The same window is never re-run with changed rules.

## 11. Descriptive numbers (no verdict)

1. **AAPL and AMZN:** all rules, labelled "descriptive reference" (`phase2.py --reference`), unless §10 widens.
2. **Splits:** the strike share split into listing and other. The forward share at the 30-day level: the same draws
   through `iv_daily_row`, for `cm30_iv` and `cm30_blind_iv`.
3. **Roll on `cm30_blind_iv`:** the roll statistic on the blind series, which is the series of the VX comparison. It
   is not a rule. The blind series interpolates through expiries that hold the next event, by design (ADR 0003,
   "Alternatives rejected"), so a pair switch moves event variance in or out. In the synthetic world with no fault this
   already gives 0.262 [0.014, 0.391] (seed 1).
4. **Noise from autocorrelation:** −2 × the lag-1 autocorrelation of the daily changes of `cm30_iv` and
   `cm30_blind_iv`, with a 95% interval. If our series = truth + independent day noise and true changes are not
   autocorrelated, this is the noise share. On synthetic data it is noisy (±0.2).
5. **Cboe, how exactly:** the published per-name slopes above, as stored in `vx-ledger.md`, give 1 − slope. The
   report puts the measured shares of §5 and §11.2 to 11.7 beside 1 − slope. It reads no Cboe file and no per-day
   Cboe value. No rule uses it, and nothing is fitted to it. Justification: it is the only way to say how much of the
   gap the measured components cover.
6. **The residual line for `cm30_blind_iv`** (`blind_sum`): the shares that reach the blind series, summed in each
   bootstrap replicate of the same draw matrix (a joint bootstrap), with a 95% interval: the forward share of
   `cm30_blind_iv` (§11.2), the roll share of `cm30_blind_iv` (§11.3), and the strike-and-filter switch-excess share
   of `cm30_blind_iv` (changes with the same blind pair on both days; group: an expiry of the pair switched; u against
   the nearest usable expiry outside the pair). It is printed beside 1 − slope and −2ρ1 of `cm30_blind_iv`. The three
   shares have different denominators (each statistic's own changes), so the sum is an approximation, not an
   identity. In the synthetic world with no fault it reads 0.078 [−0.146, 0.344] (seed 1): wide.
7. **Common-mode forward error, an upper bound.** The forward-vs-close series d holds ε_t − ε_{t−1} for a common error
   ε, so var(ε) ≤ var(d)/2. The check injects ε with σ_c² = var(d)/2 into every expiry of a session alike (seed
   `[20261117, 7, session, draw]`), and reports the share at fixed expiries, for `cm30_iv` and for `cm30_blind_iv`.
   σ_c also holds the close's own noise and true differences between the forward return and the close return, so
   the share is an upper bound (§7 shows it above the oracle on each seed).
8. **Components no rule can see.** A "No fault" says nothing about these:
   - **mid noise at fixed strikes:** a quote mid that moves within the spread with no switch at all. Every change has
     it, so no switch-excess statistic sees it, and the forward injection does not add it;
   - **partial staleness:** some quotes of an `ok` snapshot not updated since the day before;
   - **common-mode forward error:** only the forward-vs-close line (b) and the upper bound of §11.7 see it;
   - **`r_cont`:** an error in the rate moves DF, so the parity forward and every price alike;
   - **the τ-interpolation of `cm30_blind_iv`:** its roll statistic is descriptive only (§11.3).

## 12. Already suspected (from ADR 0003, the code and the probes; not tested on real data)

1. **Validation runs may have used the live tree.** `-I` ignores `PYTHONPATH` (G1). Any earlier check run as
   `PYTHONPATH=<clone>/src python -I` imported `~/dev/earnings-vol-study/src`, not the clone. How it went undetected:
   no script asserted where `earnings_vol` came from.
2. **The ADR's forward line is weak** (§7 power note 1). A NO FAULT on (b) does not clear the forward.
3. **The flat-σ_d assumption** (ADR 0003 "Risk"): with a sloped diffusive term structure, the `two_component` →
   `interp_spanning` switch near an event makes large jumps in `cm30_iv` (§9.4).
4. **`cm30_blind_iv` moves event variance at pair switches** (§11.3). Cboe's index rolls at other times, so these
   jumps would lower the slope. That is a design difference, not a fault (§4).
5. **Low-vol names see the strike grid more.** A strike gap matters more when strikes are wide relative to √w. IBM has
   the lowest slope. Not tested.
6. **σ_f measures only the part of the forward error that differs between expiries.** The first version of this file
   called σ_f an upper bound of the forward noise. That was wrong. A forward error common to every expiry of a session
   cancels in Δln F_e1 − Δln F_e2, so σ_f does not see it, and it leaks into the strike rule (§7). σ_f is an upper
   bound only of the expiry-specific part: pairs across an ex-dividend date are left out, but other true carry changes
   stay in, so for that part the forward rule leans toward FAULT. The common part has its own descriptive upper
   bound (§11.7). How it went undetected: no probe planted a common-mode error; the reviewer's experiment did.
7. **Points where the ADR is silent** (S1 to S7 in `probes/ref_spec.py`): a strike listed twice, the median of an
   even count, the quadratic's weight, the sides of k = 0, equal τ, the blind series with one expiry, w ≤ 0.
8. **`termstructure.event_variance` divides by τ2 − τ1 with no guard.** Two usable spanning expiries with the same τ
   would raise ZeroDivisionError. The reference guards it. Not seen in the probes.

## 13. Phase-2 data, run time and frozen hashes

No `dolt` command is needed: the option chains were already extracted from the private mirror into the package's
cache. No Cboe file and no `volatility_history` value is read.

| Input (all under `~/data/vol-projects/earnings-vol-study/` unless shown) | Used by | SHA-256 |
|---|---|---|
| `cache/dolt/options@msfqpodh24viv7prdqdan8517rkjp861/option_chain/*.parquet` (82 files, 2020-01 to 2026-10) | all rules | the SHA-256 of the text that `sha256sum $(ls *.parquet \| sort)` prints: `ba41a5ca5b99fd1c0bbc95fb57b40134c455933af0e451f575d8f780ae641cda` |
| `cache/stage/74bed6f4b1281810/session_snapshot.parquet` | the sample | `62243781b308bf010c1b7dc230271084c189250666de7475f5a71f0dffc13472` |
| `cache/stage/74bed6f4b1281810/market_daily.parquet` (`r_cont`) | all rules | `82ed6a4df4244c85d92b56fe046c0612d9fc5af0ee64dda38b3a2dcccbdcc5a9` |
| `cache/stage/74bed6f4b1281810/events.parquet` | anchors, event zone, own events | `1e5b88ee1b25f6d237ffbcf876578fc3a2f6e6d3c91d5da469bbbc946b72fbfc` |
| `cache/stage/74bed6f4b1281810/security.parquet` | security ids | `cd17dc2dfe98f1c4f724c99bfb28698eae77ff86354d7654093b9b610df974ff` |
| `cache/stage/74bed6f4b1281810/ticker_alias.parquet` | security ids | `7bd15257b55c1b83303d04685ef3a07525dcbe3ed69d2907f600a39e21f77838` |
| `cache/stage/74bed6f4b1281810/session.parquet` | calendar | `9ce8ddd766e1e4b904c706db5322d00b58481452cdf686c3fc68fd9d685fdb0a` |
| `cache/stage/74bed6f4b1281810/chain_expiry.parquet` | G4 | `ce5a8e688a47230553dec8c088e64767b826aaa9011f8b3d071c6eb0d33af98f` |
| `cache/stage/74bed6f4b1281810/iv_daily.parquet` (= the clone's committed copy) | G4 | `68aa42a346fe748c2fffe09c6768460ebfff09a86ad2798eca88325cbb718bf0` |
| `raw/yfinance/GOOGL.parquet` (close, dividends; local only) | (b) forward vs close, ex-dates | `3ece2b8aa616b21c2074ee65c852454fd28452a770c8207a68d6ef7bf1130b4f` |
| `raw/yfinance/GS.parquet` (local only) | the same | `d9719bbcd8ac7d70ac84e69ed421bd213186b74d117b8047edb7db9f42de0d23` |
| `raw/yfinance/IBM.parquet` (local only) | the same | `2abcf226d5cdc95ada442a2d7dc5a4275fe772206960bffc92ebc3fd52d69cbf` |
| clone `params.yaml` | all rules | `9cc10022ea2bf1b9be3638d5a69a5ff20c6cb4b6107ac98925216ed4f3722467` |
| clone `data/derived/iv_daily.parquet` | G4 | `68aa42a346fe748c2fffe09c6768460ebfff09a86ad2798eca88325cbb718bf0` |

Only file bytes were hashed. No value in these files was read for this pre-registration. AAPL and AMZN inputs
(`raw/yfinance/AAPL.parquet` `47aa0597d62722be2b49fb873373f0c3d5d096277f06be4e019b958fd528b05b`,
`AMZN.parquet` `f39d61cce4e46c9bd0266615f08da9e38718488c9de224836eb4e975bf2dea53`) are read only for §11.1 or §10.

**Frozen check code and outputs** (G2), SHA-256 on 2026-11-17. `probes/SHA256SUMS` lists every file below in
`sha256sum` format; its own hash is the first row, and G2 reads it from this table.

| File | SHA-256 |
|---|---|
| `probes/SHA256SUMS` | `9c39e3cd0aae10728bb69c0c2d784f7bd07abcc66a8c7a46500a95826065fe35` |
| `probes/ivchecks.py` | `ae27dbb1ff105b74a374849347502ed04cfe4cac06e2313d05f1f9b966b935bb` |
| `probes/ref_spec.py` | `4ceeadf3b24cfa941b5da2f26c9eccdf222546f63423b45e242519f5295774c3` |
| `probes/synth.py` | `47f0770e3c5e109e17744886e1429404ac207bf469830e5116513b89adbc28ad` |
| `probes/mutants.py` | `e027be1ddf1600e2763a6cf1f0085a2c7cf1152c2e0d5e954c12a256d4093d18` |
| `probes/worlds.py` | `ef38ed72390f32fed9234a708f76f830a200b77a89267358d10d1749f68ed1b2` |
| `probes/run_probes.py` | `1d5d068bdff8740c023245ceb28e89f5fe7472bc7802ae6c9275e02c7e00289e` |
| `probes/calib.py` | `4dec49ba718a2e4d7674f7f7401ed064acdcf46684f3947ff9aed71e5ec63077` |
| `probes/phase2.py` | `f7e1bab71c25c53cc6036a6b5a448b1b1e8d03e4a14a78f21858f79e5ab3c1bd` |
| `probes/env.freeze.txt` | `8dcc667ee497e82a5f15752289de143d6473b89bb66756df759f4615e6d397db` |
| `probes/calib.out` | `fc89ffa9018d807eb665d60bec3426e86c5993430058962b77bdc367a08c8a18` |
| `probes/calib.json` | `040cc587df2b880249687ac858aec23d77c7770cb75fef87c4d2bda8466028e2` |
| `probes/run_probes.seed1.out` | `1b98967b5e15eade2bc7c28cf7e6f9a756139d16ad0eaa34f102f6beccced23d` |
| `probes/run_probes.seed1.json` | `b6c203089acc2a2426e2d8f8fa0852e1beace891dc03e6fbd9fa521cd3092206` |
| `probes/run_probes.seed2.out` | `b8407d05f1696bfa0f35535c24682a03f3a241eb7fc3eeb211e38adcbb7facca` |
| `probes/run_probes.seed2.json` | `2c28945aba5ac08f5c3d646b69eb5558c20bde5e4c5afc92f9023439206c641c` |
| `probes/run_probes.seed3.out` | `95e03d2ac9be65d84f2f6508236b3757fc342fe42d45525be5674ec61dc0da82` |
| `probes/run_probes.seed3.json` | `a35180197090daf4b62b1846ff758bde773edf0ddc9f5e9c1398178394d06dcd` |

Not frozen, recorded for reference: `loader.py` (the stub, before phase 2) has SHA-256
`ececde2b852bd6ec8dfdc8e99f3efccaef80acfa45c8a3e12aa5995d007d38f5`. Phase 2 changes it; each run records the value it
used (G2).

**Run time.** Measured on synthetic panels on 2026-11-17: `run_probes.py`, one seed, 184 to 216 s (22 runs of 500
sessions, three seeds side by side); `calib.py` 225 s (8 workers); `phase2.py --selftest` 53 to 54 s; `phase2.py --gates
G1,G2` 148 to 161 s. One synthetic name with every
rule takes about 11 s (500 sessions, about 3.2 atoms a session, about 40 strikes an expiry; `ref_spec.ref_atom` 1.0
ms an atom, the package's atom 0.1 ms). **Phase 2 is an estimate, not a measurement:** real panels have up to 1,713
sessions and more expiries and strikes a session. The forward injection runs 2 × 20 perturbed atoms per atom, so
perhaps 15 to 30 minutes per name, and the robustness rerun about as long again. The package's own IV run took
79.9 s (`iv_report.json`). Memory: the draw matrix is 10,000 × 1,713 int32, about 69 MB, two of them per name.

## 14. Deviations

After phase 2 starts, every change to this file, to a file in `probes/`, to an input in §13 or to the order of the
steps is a **deviation**. A ledger lists each one with its time, the reason, and whether a real-data result was
already seen when it was made. Not allowed after phase 2 starts:

- changing a threshold (0.10, 10 bp, 1e-6), a tolerance, the bounds, a widening factor, k, the block length, the
  replicates or the seed;
- changing the window, the sample, the event zone, the reference rules, the any-reference guard, the tag rules of
  (a), or the cause order of §5;
- dropping a name, a rule or a year, or moving a rule between "rule" and "descriptive";
- changing `phase2.py` at all (any change is a deviation). Allowed, not a deviation: writing `loader.py`, and each
  loader fix that G4 forces, each listed in the ledger with the `loader_sha256` of the run;
- tuning anything in our IV toward Cboe.

Any other analysis is labelled "exploratory, not pre-registered".

## 15. Files

| File | What |
|---|---|
| `preregistration.md` | This file. |
| `probes/ivchecks.py` | Every statistic and decision rule of §5 and §6 (`run_name`), and the widening factors. Phase 2 runs these functions. |
| `probes/ref_spec.py` | The second implementation for rule (a), with the ADR-silent points S1 to S7 and their alternatives. |
| `probes/synth.py` | The synthetic market, its own Black-76 pricer, BMO and AMC events. |
| `probes/worlds.py` | The synthetic worlds of the probes, the calibration and the self-test. |
| `probes/mutants.py` | The planted code faults, swapped in while a probe runs; the package files are not edited. |
| `probes/run_probes.py` | The falsifier probes of §7. Writes only to `--out`. |
| `probes/calib.py` | The bootstrap calibration of §6 (the widening factors). Writes only to `--out`. |
| `probes/phase2.py` | The frozen phase-2 driver: gates G1 to G5, rules, robustness, verdicts, outcome; `--selftest` on synthetic panels (13 of 13 checks as expected on 2026-11-17). Its only stub is the loader, in `loader.py`. Once the loader is written, the self-test's check "the loader is a stub" fails by design; the self-test is a phase-1 tool. |
| `loader.py` | The phase-2 loader (`load_panel`), a stub until phase 2 starts. Outside `probes/` and not hashed in `probes/SHA256SUMS`; G2 records the SHA-256 of the version a run uses. |
| `probes/env.freeze.txt` | The venv's package list for G1. |
| `probes/SHA256SUMS` | The SHA-256 of every other file in `probes/`, for G2. |
| `probes/run_probes.seed1.out`, `.json` | Seed 1, the pre-registered probe run (exit status 0); G2 reruns it. |
| `probes/run_probes.seed2.out`, `.seed3.out` (and `.json`) | The same probes on seeds 2 and 3 (exit status 0). |
| `probes/calib.out`, `calib.json` | The calibration run that fixed the widening factors. |

All probe output is synthetic. Nothing in this folder holds a real-data value.

## 16. Revisions after the adversarial review (2026-11-17, before any real-data value was read)

An adversarial review (Opus, synthetic data only) attacked the first version. The coordinator reran two of its
experiments and got the same numbers. Each finding and the change made for it:

| Finding | What was wrong | Change |
|---|---|---|
| (5) | "No fault" could be reached with 13% to 22% of the atom variance unexplained (noise present on no-switch days is invisible to a switch-excess share; three rules at 0.06 to 0.08 each pass), and the text claimed more than the rules test. | §10: "No fault" now means only that no single tested component reaches 10% on its own denominator; the sentence "The forward, the filters and the interpolation, as tested here, do not explain the slopes" is deleted. §11.6 adds the residual line for `cm30_blind_iv` (joint bootstrap) beside 1 − slope and −2ρ1; §11.8 names the components no rule can see. |
| (6) | The clean reference has no cap on exclusion. A fault on every expiry of a session read 0.003 to 0.09 against an oracle of 0.12 to 0.36, and gave NO FAULT. The probes only planted faults per (session, expiry). | §6: strike and filter NO FAULT also needs the any-reference version to say NO FAULT, else UNCLEAR. `synth.fault_scope = "session"`; new probes P19 (session-wide filter, oracle 0.13 to 0.21) and P20 (session-wide strike drop, oracle 0.12 to 0.17) must not give NO FAULT, and do not on seeds 1 to 3. The reviewer's expC and expH, rerun against the revised code: no session-wide case gives NO FAULT for filter or strike. A session-wide fault still never reads FAULT (§7 "Directions"). No cap on exclusion was added: the share of changes with no clean reference is reported per rule (`no_clean_ref_share`), and the guard takes the place of a cap. |
| (7) | A forward error common to all expiries is invisible to σ_f; §12.6 called σ_f an upper bound, and the error leaks into the strike rule. | §12.6 corrected, with how it went undetected. §11.7 adds a common-mode upper bound (σ_c² = var(d)/2). New mutant `fwd_common` and run `fwdcommon` (descriptive). §10 step 1: a strike or filter FAULT is checked against common-mode forward error first. |
| (8) | Outputs were not hashed; `run_probes.py` rewrote files in the frozen folder; the G2 literal diff failed on an appended "exit status 0" line; the venv was not pinned; G4 checked only the cm30 columns; the phase-2 driver was not frozen; `ref_p=None` silently skipped (a). | `run_probes.py` and `calib.py` write only to `--out` outside this folder; the `.out` ends with one `elapsed:` line, the only line G2 ignores; one BLAS thread. `probes/SHA256SUMS` hashes every frozen file and §13 hashes it. `probes/env.freeze.txt`, checked by G1. G4 compares every field of `chain_expiry` and `iv_daily` (`chain_expiry.parquet` hashed in §13), and §2/§3 state how a missing leg is represented. `probes/phase2.py` is frozen with the loader as its only stub; a missing rule key, an unknown verdict, `ref_p=None` or a missing calendar list is an error. |
| (2) | The differential left out `iv_atm`, `cm30_exp_lo/hi`, `cm30_method`, `event_var`, `sigma_d_iv`; `ref_cm30` took the package's τ, w and spans; "unspecified" was labelled by hand. | All these fields are compared. `ref_cm30` reads the reference's own atoms, τ from the calendar list and spans from `events.parquet`. The code tags every mismatch (§6), with a consistency rule for S2 to S6 and the distance to the decision boundary; "unspecified" exists only for code-tagged mismatches. |
| (3) | Synthetic anchors were always BMO, so the AMC branch was untested; no truth check for `cm30_blind_iv`. | `synth.py` alternates BMO and AMC events, and the anchors come from `tables.event_anchors`. The truth check derives its own events and adds `cm30_blind_iv` and `sessions_to_next_event`. New mutant `spans_from_day0`: P21 (truth) and P22 (a) flag it on seeds 1 to 3. |
| (4) | The bootstrap sd was about 0.6 of the seed-to-seed sd for forward and roll (12 seeds); the robustness check used blocks of 10. | `calib.py` measured the ratio on 48 other seeds per rule (§6 table); the intervals are widened by the measured factor (forward 1.35, filter 1.1, strike 1.35, roll 1.2). On 48 seeds the forward ratio is 1.34 (bootstrap sd 0.75 of the seed-to-seed sd), smaller than on the review's 12 seeds (1.71, reproduced). The robustness rerun uses blocks of 60 and seed 20261118. |
| (1) | P12 was vacuous: 0 filter switches. | P12 now runs on a world with 229 to 253 filter switches that add almost nothing (oracle −0.004 to 0.005), NO FAULT on both references on seeds 1 to 3; the run also checks that it is not vacuous (≥ 30 switches). Its choice is disclosed in §9.5. |
| Found by the orchestrator at freeze | The loader stub was inside `probes/phase2.py`, a file hashed in `probes/SHA256SUMS`. Writing the loader at the start of phase 2 would change that hash, so G2 would stop with "changed since frozen" in the very run that needs the loader. No probe ran the driver after a loader was written, so nothing showed it. | The stub moved to `loader.py`, outside `probes/` (not hashed, and not caught by the "files in `probes/` that are not frozen" check). `phase2.py` reads its bytes, records their SHA-256 (G2 report line and `loader_sha256` in `aggregate.json`) and runs them; nothing else in `phase2.py` changed. §14: any change to `phase2.py` is now a deviation; writing `loader.py` and the fixes that G4 forces are allowed and listed. |
| (10) | The filter check under-reads. | Stated with its size in §7 "Directions" (0.69 to 0.89 of the oracle), with what that allows (a true share up to about 0.14 could read NO FAULT). Not changed. |

Not done, and why:

- **No rule for the common-mode error.** The review asked for a descriptive upper bound, and it is descriptive. In the
  probes a 10 bp common error (oracle 0.18 to 0.26) passed the forward-vs-close line (9.0 to 9.6 bp) and the forward
  rule, and made only the strike rule UNCLEAR. A real common error of 5 to 10 bp could therefore sit under a "No
  fault" or an "Unclear"; §10 requires the upper bound beside the outcome.
- **The session-wide case reads UNCLEAR, never FAULT.** Letting the any reference decide a FAULT would turn its 1.4 to
  2.2 over-reading into false FAULTs.
- **The widening factors are point estimates** from 48 seeds, with a relative standard error of about 10%.
