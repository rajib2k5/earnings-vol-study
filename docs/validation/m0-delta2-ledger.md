# Milestone 0, delta-2 adversarial review: ledger

- Scope: the architect's last pass (route (a), `no_document`/`not_checked`, `abs_move_cand_max`, Holm floor, G1
  reference-distribution check, ADR 0003 check list, EDGAR wording). Seven claims, given by the orchestrator.
- Protocol: evidence-gated validation, **mode: single-context sequential fallback**. Tier 2 (spec/doc channel A +
  runtime channel B) for claims 1, 2, 4, 5; Tier 1 (runtime/grep only) for 3, 6, 7. Default verdict: broken.
- Environment pin (scratch `env-pin.txt`): Python 3.12.13, statsmodels 0.15.0, numpy 2.5.4, scipy 1.18.1,
  pandas 3.1.0, Linux 7.0.0. No network, no EDGAR, no dolt.
- Probes: `docs/validation/probes/m0-delta2/`. Each copies or imports, never edits, repository code. Run each with
  `.venv/bin/python <probe>` from the repository root.

## Part 1: pre-registered claims and probes (written before any probe ran)

| ID | Claim (as given) | Tier | Probe (pass condition / falsifier) |
|---|---|---|---|
| 1 | Route (a) removes the move dependence of calendar timing errors; ADR 0002's table (misread and re-read rows included) is right | 2 | `e1_route_a.py`: re-run `research/prototypes/route_a_vs_b.py` at `--nu=3` and `--nu=1e9`, byte-compare with `route_a_vs_b.out.txt`; check every number of ADR 0002 :361-368 and :384-387, :405-408 against it; check the d4 C0 control matches. Extension: let the re-read itself err (1%, and 10% on gap-contradicted correct labels). Falsifier: re-read always right must reproduce 0.85/0.67/0.11. |
| 2 | `abs_move_cand_max` is label-free and its terciles are flat under uniform errors | 2 | `e2_cand_max.py`: same world plus uniform calendar **date** errors (the jump is not in either candidate session of the calendar D). Pass: wrong-date share flat across `abs_move_cand_max` terciles. Falsifier: the measure computed around the true date must be flat; the sim's label flips must stay flat. |
| 3 | The `not_checked` invariant is complete for `daily` and `mixed`, at the 2024-09-11 boundary and when day 0 lands in another sample than D | 1 | `e3_boundary.py`: NYSE sessions Aug 2024 to Dec 2024 and Oct 2026; for every (D, recorded label, true timing, date error) compute the true sample; flag any case that the ADR 0002 invariant or the data-model §3.7 invariant lets stay `not_checked` while the true day 0 is in `mixed` or `daily`. Falsifier: move the ADR boundary to 2024-09-12, the probe must flag D = 2024-09-11 AMC. |
| 4 | Holm's "fifth step" derivation for `rad_season_p`'s floor 2/128 in a family of 7, with adjusted p 0.0469 / 0.0625 | 2 | `e4_holm.py`: full 2^7 enumeration of a wild cluster restricted Rademacher test on random data (minimum p); statsmodels `multipletests(method="holm")` with k = 0..5 smaller p-values. Falsifier: the "fourth step" version must be contradicted by the run. |
| 5 | G1's reference-distribution check catches statsmodels' `use_t=False` default for regressions as well as intercept-only tests | 2 | `e5_use_t.py`: statsmodels 0.15.0 OLS, two-way and one-way cluster, intercept-only and a 2-regressor model, t rows and a 2-restriction Wald. Apply the G1 check (df from cluster counts; p from the t / F tail) to default and `use_t=True` fits. Also report what the default does to `ci_lo`/`ci_hi`, which the check does not read. Falsifier: `use_t=True` rows must pass, default rows must fail. |
| 6 | ADR 0003's list of what the identity check and the 4-dp check do and do not catch is accurate | 1 | `e6_identity_omissions.py`: re-run the listed mutants (E values), and plant bugs the list does not name (Black-76 inversion, OTM/ITM side, quote mid) in a scratch copy of `worked.py`; record exit code and E. Falsifier: m1 (lost 252) must exit non-zero. |
| 7 | No EDGAR mention in `docs/`, `README.md`, `LEARNING_LOG.md` presents it as decided rather than proposed | 1 | `e7_edgar_grep.sh`: list every EDGAR / 8-K line lacking a proposal qualifier; read each in context. |

## Part 2: results

Channel A (spec / primary source) and channel B (probe) per claim. All probes ran on 2026-10-28 with the pin above;
verbatim outputs are in the scratch directory (`e1.out` … `e7.out`). Repository sources were checksummed before and
after (`route_a_vs_b.py`, `.out.txt`, `worked.py`, `d4`): unchanged.

| ID | Verdict | Sev. | Channel A (spec / source) | Channel B (probe, what it printed) |
|---|---|---|---|---|
| 1 | Numbers **SURVIVE**; ADR 0002 :349-350 ("can only fix misreadings, so its size is limited by the misreading rate") **REFUTED** | moderate | Sim assumes the re-read is always right (`route_a_vs_b.py:111`). ADR :347-348: "the second reading decides". | `e1`: re-run byte-identical to `route_a_vs_b.out.txt`; all 11 quoted triples and look-up counts match; re-reads 1.6-2.8 / 20.0-22.6 per 365 match. Falsifier (perfect re-read) gives 0.85/0.67/0.11. Of 22.6 re-reads per 365 (t3), **20.9 are on labels that were already right**. Re-read with its own 1% error: 0.97/0.72/0.12. Primed re-read (10% of gap-contradicted correct labels flipped): **2.07/1.17/0.14**, as move-dependent as the old default (2.11/1.66/0.30). |
| 2 | **REFUTED** for calendar date errors (holds for BMO/AMC flips) | moderate | ADR 0002 :453-455, data model :638 define the measure around "D" without saying calendar D (`announce_date`, :477) or the document date. The sim's check uses max(\|g_B\|,\|g_A\|) with labels drawn independently, so it cannot fail for any label-free measure. | `e2`: 1% uniform date errors, measure around calendar D: wrong-date share **2.28 / 0.64 / 0.10%** by tercile. Around the true date (falsifier): 1.01/1.02/0.99. Label flips: 2.98/3.05/2.96. |
| 3 | ADR 0002 form **SURVIVES** (no hole without a date error); data model §3.7 form **REFUTED**; both miss cross-boundary date errors | minor | ADR 0002 :330-331 vs data model :480 state different invariants; the ADR table row :300 a third (no NULL-label `not_checked` at all). | `e3`: ADR form 0 holes without a date error; data-model form 3: D=2024-09-11 recorded BMO, truly AMC (day 0 09-12, `mixed`); D=2024-09-11 NULL, truly AMC; D=2026-10-26 recorded AMC, truly BMO (`daily`). Date errors of 1-10 days across 2024-09-11: 219 holes (ADR) / 579 (DM). Falsifier (boundary 09-12) exposes D=09-11 AMC. |
| 4 | **SURVIVES** | - | statsmodels `multitest.py:233-245`: reject while p_(k) <= alpha/(m-k+1), adjusted = cummax((m-k+1) p_(k)). | `e4`: full 2^7 WCR enumeration, min p over 200 strong-signal sets = 0.015625 = 2/128. Holm: floor not rejected with k=0..3 smaller p's (adjusted 0.1094 … 0.0625), rejected at k=4 (0.0469). "Fourth step" contradicted. Context: G=8 would pass at step 2, G=6 only at step 7; G=7 rests on the "October 2026 tail joins July" merge (ADR 0005 :281-282). |
| 5 | **SURVIVES** for p-values (t and Wald, intercept-only and regressions); gaps for CIs and timing | minor | statsmodels `linear_model.py:2837-2838` (`use_t = self.use_t` when None), `:3011-3013` (`df_resid_inference = n_groups - 1` whatever `use_t`), `base/model.py:2062-2064` (`use_f` follows `use_t`); `conf_int` uses the normal when `use_t` is False. | `e5`: every default row fails G1 (e.g. regression two-way p 0.000266 vs t6 0.010750; Wald chi2 p 0.000002 vs F(2,6) 0.001021); every `use_t=True` row passes. Default `df_resid_inference` is already 6. Default CI half-width is **1.960 se against 2.447**, and G1 does not read `ci_lo`/`ci_hi`. |
| 6 | Listed items **SURVIVE**; list **REFUTED by omission** | minor | ADR 0003 :303-321 names four uncaught bugs and asks oracles for those four only. | `d3` re-run: m2 0.00069327, m4 0.00029116, m5 0.00088266, m6 0.00008131, all exit 0; m1, m3 caught. `e6`: three unlisted bugs also exit 0: Black-76 d1 +w (E 0.00087993), ITM instead of OTM side (**0.00192540, +118%**), bid instead of mid (0.00053567). Controls: m0 exit 0, m1 exit 1. |
| 7 | **SURVIVES** (one nit) | nit | - | `e7`: 59 unqualified-line hits read in context; each sits under a "proposed / only if approved" heading, a dashed edge labelled proposed, or is a measurement record. Nit: ADR 0002 :225-226 give GOOGL/NFLX "BMO → **corrected to AMC**" in the `day0()` oracle table on the 8-K and the gap, while the operative default's look-up is "not yet looked up". |

### Found while checking, not asked

- ADR 0002 :408 still calls the coarse figures "the same not-yet-committed extension of `d4`"; :89 and :373 were
  updated to name `research/prototypes/route_a_vs_b.py`.
- ADR 0002 :373 "its no-check control matches `d4`'s to the last digit": wrong day 0 matches; mean crush differs in
  the 4th decimal (`d4` C0 high tercile -0.1163, `route_a_vs_b` -0.1164).
- `research/prototypes/README.md:18` calls the sim "the label-free tercile check for `abs_move_cand_max`". It checks
  open gaps with independently drawn labels, which is flat for any label-free measure: no evidence about the
  specified parity-forward measure or about which D it uses.

### Minimal fixes (not applied)

1. ADR 0002 :347-350: make the re-read blind (the re-reader sees neither the gap's side nor the first reading); change
   the label only when the second reading has a stronger basis or a third agrees; delete "can only fix misreadings";
   add a row with re-read error (1%: 0.97/0.72/0.12, t3) to the table.
2. Data model :638, ADR 0002 :453: the measure uses the date used (document date for `date_corrected`, else
   `announce_date`); state that an undetected date error lands in the low tercile, so `date_corrected` and coarse
   errors trend by construction.
3. Data model :480 and ADR 0002 :300: copy ADR 0002 :330-331 verbatim (key on `announce_date >= 2024-09-11`, not on
   `sample`). Optionally look up labelled events with D in the last 10 calendar days before 2024-09-11.
4. ADR 0005 :781-787 and data model :703-709: add `(ci_hi - estimate)/se == t_{df,0.975}`; store the Wald numerator
   df; say the invariant runs on every write of `results`, so milestone-4 rows (H7, :682) are covered.
5. ADR 0003 :303-321: add the IV inversion, OTM side and quote mid to the "not caught" list and to the
   milestone-2 per-component oracles.
6. ADR 0002 :225-226: "BMO; AMC per the 8-K (proposed) and the gap; press release not yet looked up".
