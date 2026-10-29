# M2 adversarial validation: pre-registered claims and probe designs

Frozen 2026-10-29 before any literature was read and before any probe below was run. Mode: single-context
sequential fallback for Channel B; Channel A (method and documentation) delegated to a separate subagent that
sees this ledger and the code, never the probe outputs. Every material claim starts REJECTED.

Paths: `<repo>` is the repository root; `<cache>` is `$VOL_DATA_DIR/earnings-vol-study/cache`; `<stage>` is
`<cache>/stage/8286751e4eaca31e`. Probes write only to a scratch folder outside the repository; the repository's
own files are read, never written, except this folder and `docs/validation/m2-ledger.md`.

Env pin: `env-pin.txt` (Python 3.12, numpy 2.5.4, scipy 1.18.1, pandas 3.1.0, exchange-calendars 4.13.2).

| ID | Claim (atomic) | Mat | Probe (pass condition / falsifier) |
|---|---|---|---|
| 1a | `black76` equals the textbook Black-76 price and satisfies C − P = DF(F − K) on k ∈ [−3, 3], w ∈ [1e-8, 4] | M | `p01_black76.py`: textbook formula with `scipy.stats.norm`, max abs err < 1e-12·F. Falsifier: d1 with +w instead of +w/2 |
| 1b | `implied_w` round-trips w on the OTM side, deep OTM and near-zero time value included | M | `p01_black76.py`: grid of (k, w); rel err < 1e-9 wherever `has_root`. Falsifier: same mutant |
| 1c | No root ⇒ None; never clipped, never a wider interval | M | `p01_black76.py`: prices at and beyond Black76(w=4) and below Black76(1e-8) give None |
| 1d | bid = 0, crossed, locked and NaN quotes on the OTM side never enter w_atm | M | `p01_black76.py`: corrupt one strike of a synthetic chain; w_atm equals the chain without that strike |
| 2a | F = median F_K over the 4 smallest \|C − P\| among strikes with both legs passing, ties to the lower strike | M | `p02_forward.py`: independent selection by `sorted((gap, strike))`; decimal ties whose binary floats differ |
| 2b | Stored `chain_expiry.forward` equals an independent recomputation from the raw option_chain quotes | M | `p02_forward.py`: 2,000 random rows, abs diff < 1e-9. Falsifier: 5 strikes |
| 3a | Bracket: nearest valid k_lo ≤ 0 < k_hi, linear in k, width ≤ 1.5√w | M | `p03_atm.py`: recompute bracket rows from raw quotes; compare w_atm to 1e-10 |
| 3b | The quadratic fallback is sound on the 293 rows (no one-sided extrapolation artefacts) | M | `p03_atm.py`: classify the 293 by wide_bracket / no_bracket and one-sided support; compare with same-day neighbours |
| 4  | τ = XNYS sessions in (t, as_of(expiry)], half sessions count 1 | M | `p04_tau.py`: every chain_expiry row against `exchange_calendars` directly. Falsifier: +1 |
| 5  | T1* = shortest ok expiry at pre with τ(day 0) ≥ 5; followed while τ ≥ 5; interpolated, never extrapolated | M | `p05_front_fixed.py`: recompute every event_iv row from chain_expiry |
| 6  | cm30 interp/extrap uses one class only, the class set by sessions_to_next_event ≤ 21 | M | `p06_cm30.py`: join cm30_exp_lo/hi to chain_expiry spans flags over all iv_daily rows; recompute cm30 |
| 7  | spans ⇔ as_of(expiration) ≥ effective day 0 of the next event; AMC-on-expiry-day clean; Good-Friday expiry | M | `p07_spans.py`: recompute every row from events; enumerate the edge cases present in the data |
| 8a | E from the two shortest usable spanning expiries; E ≤ 0 kept signed, no move, excluded from √E stats | M | `p08_evar.py`: recompute E on every iv_daily row from chain_expiry |
| 8b | sigma_d fallback (two shortest clean) is the forward variance of the model | M | `p08_evar.py`: recompute; synthetic surface check |
| 9  | The worked example gives E = 0.00088284, √E = 2.9713%, and the test does not read its oracle from the code | M | `p09_worked.py`: independent pricer + forward + bracket on worked.py's quotes; read the test source |
| 10 | Funnel 1,353/1,320/366/356/354/348; terciles; 285 events lack abs_move_cand_max for the stated reasons | M | `p10_funnel.py`: recompute steps 1–5 without funnel.py; terciles by own ranking; classify the 285 |
| 11 | P4, P5, P6 and the leak numbers | M | `p11_numbers.py`: recompute each from committed tables / chain_expiry |
| 12 | iv_daily, event_iv, timing_check rebuild byte-identically; chain_expiry local, 17 MB | M | `p12_rebuild.sh`: rebuild in a scratch copy with a scratch VOL_DATA_DIR; md5 |
| 13 | Contract 0.3.0 consistent; the app only draws; coverage holds | M | `p13_contract.sh`: grep versions; read the page code; `npm run verify` in the scratch copy |
| 14 | Tests meaningful: 5 mutants re-run; no test re-implements the code under test | M | `p14_mutants.py`: 5 mutants on a scratch copy; read the tests for circular oracles |
| 15 | DATA.md terms; check_data_files reads the index, catches renamed copies, cannot be bypassed; no bulk raw files | M | `p15_datafiles.sh`: plant files in a scratch clone's index |
| 16 | The layering allow-list holds for the new modules | M | `p16_layering.py`: parse imports of every module; compare with the allow-list test |
