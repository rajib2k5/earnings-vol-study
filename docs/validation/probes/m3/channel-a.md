# M3 validation — Channel A (documentation audit)

Read-only, 2026-10-29, no code run. HEAD = `fca9972`; ADR 0005's only working-tree edit is its status note. Papers are paraphrased (copyright) and cited by equation/page.
**Not reached:**
- CGM 2011 JBES text (paywalled; NBER WP t0327 (2006) and the 2008 author draft read instead);
- MacKinnon & Webb 2017 and Webb WP 1315 (HTTP 403 / TLS error);
- Kendall 1954, Corrado 1989, Corrado & Zivney 1992, Cowan 1992, Patell 1976, BMP 1991, Holm 1979 (paywalled).

## A1 — β pool REFUTED (one deviation); look-ahead permitted CONFIRMED
- ADR 0004:102: "over **all clean baseline sessions of all of security s's non-excluded events** (≈ 7 × 30 ≈ 200 changes)".
- Code pools every null-`exclusion_reason` row in every sample (window.py:104) and never applies `base_ok` (window.py:180-189; abnormal.py:77-99).
- So events failing the 20/15 minimum feed β, although ADR 0004:85-86 says such an event "gets no baseline and is excluded from every measure that needs one".
- Including mixed/coarse fits the literal text. "≈ 7 × 30" implies daily only, so the text is ambiguous.
- ADR 0004:119-120: "Using later baselines to adjust earlier events is harmless here: this is a description of the past, not a forecast."

## A2 — formulas CONFIRMED; coarse rule PARTIAL; `baseline_max_change_span` REFUTED
- **CRUSH** = (X[post]−X[pre]) − βΔM (window.py:212-214). Daily/mixed force exactly −1/0 (205-207). pre ∈ {−1,−2}, post ∈ {0,+1} (event_iv.py:86-92,188) = ADR 0004:131,177.
- **ΔSIGMA_D**: σ_d² = (w₂−w₁)/(τ₂−τ₁) of E's expiry pair fixed at pre, on both days; ½ln ratio (event_iv.py:166-171,212-216), then −βΔm (window.py:216-218) = ADR 0004:134.
- **EVAR** is E at pre (event_iv.py:199-202). In `daily` it falls back to −2 (flag `pre_is_m2`), while ADR 0004:133 says "at −1".
- **RUNUP/PERSIST** = ALIV at −1/+h ✓.
- **Coarse**: RUNUP reads pre (never 0). PERSIST tries [h, h−1, h+1] capped at +10 (window.py:160-166), so PERSIST_10 uses {10, 9}. That is within ±1, but the tie-break and the cap are code choices. ADR 0004:183's "flagged" is not implemented: `event_measures` has no such flag.
- **`baseline_max_change_span`** {mixed: 2, coarse: 2} (params.yaml:66-71; window.py:137-146) has no ADR authority. ADR 0004:85 demands "at least 15 one-session changes (both ends clean)"; §4 uses 2-session changes only for scale. Params: "default taken at milestone 3".
- **Day 0** (calendar.py:115-132) = ADR 0002:325-329. CONFIRMED.

## A3 — CGM two-way CONFIRMED (fallback caveat)
- V = V₁+V₂−V₁∩₂ (WP eq. 2.15).
- Each component gets Gᵣ/(Gᵣ−1)·(N−1)/(N−K), the intersection its own count (WP pp. 8-9). With K = 1 that is exactly G/(G−1), as in clustering.py:40-46,65-79.
- df = min(G,H)−1, as in the Monte Carlo (WP pp. 14, 16).
- Non-PSD: WP p. 9 suggests the larger one-way SE ad hoc, which is the code's/ADR's `max(V_A,V_B)` (ADR 0005:265). Cameron & Miller 2015 p. 21 say the **published** 2011 paper zeroes negative eigenvalues. For a scalar that gives V = 0, so `max` is the workable choice (my derivation).

## A4 — Rademacher floor CONFIRMED; pre-declared rules CONFIRMED
- Cameron & Miller 2015 p. 27 (citing Webb 2013): at most 2^G samples and 2^(G−1) distinct |t|.
- Full enumeration (clustering.py:105-129): the all-ones vector and its mirror reproduce the CR1 t, so p ≥ 2/2^G (invariants.py:83-86).
- HEAD ADR 0005:279-282: "A season with fewer than 10 events in the test's event set is merged into the neighbouring season whose median day 0 is nearest… the October 2026 tail joins July's." Code matches (clustering.py:82-96); its tie-break is not in the ADR.
- HEAD 295-296: "more than **1.5×** the smallest, the two-way t is not used. The p-value comes from `rad_season_p`." Code matches (clustering.py:99-102; suite.py:67-69).
- The October tail merge was a prediction. The new status note's "8 RUNUP seasons" says it failed for RUNUP (not counted by me).

## A5 — Holm formula CONFIRMED; p = 1 has no ADR authority; upper bound CONFIRMED
- multiple.py:19-30 is the standard step-down.
- HEAD ADR text says only "declared now before any data is seen" (701) and "Holm then runs on the remaining hypotheses" (800). It is silent on untested members.
- p = 1 is a milestone-3 default (params.yaml:171-175; results.py:151-160).
- Holm's step-down is monotone in every other p (derived): any real p ≤ 1 for H5–H7 can only lower the adjusted p of H1–H4.

## A6 — Pynnönen ρ̄ formula CONFIRMED; input differences
- Eq. 32-33 (p. 8): Σ_t Σ_{i≠j} U_it U_jt / Σ n_t(n_t−1) over ordered pairs of stocks, where U are standardised ranks with mean 0 and variance 1 (eq. 10-13).
- eventtests.py:96-101 computes this exactly.
- Differences:
  1. z = e/s is **uncentred** (inputs.py:124-127), so it estimates correlation plus a product of means. ADR §2e owns the ranks→z switch, not the centring.
  2. Rows are events, so same-firm pairs are possible if baselines share dates. That needs a day-0 gap ≤ 38 sessions (derived).
  3. Estimation window only, which the paper allows (p. 9).

## A7 — Kendall CONFIRMED (secondary); corrections have no ADR authority
- van Giersbergen (UvA DP 2004/08, eq. 3-4) attributes the bias −(1+3ρ)/T to Kendall/Marriott-Pope. The inversion (Lφ̂+1)/(L−3) (g1.py:340) is correct.
- Subtracting n·σ²_ε from the lag-0 sum (g1.py:336) is a correct first-order fix for white noise added to the level.
- Caveats (derived):
  - Kendall's bias is derived for a noiseless series.
  - σ²_ε = −ρ̂₁s² also absorbs the −(1−φ)/2 that mean reversion alone produces.
  - L is a mean present count, not the length of a series with holes.
- ADR (HEAD:769) asks only for "the AR coefficient of abnormal log-IV levels, from the baseline levels".

## A8 — code = ADR CONFIRMED; code = Corrado/Cowan REFUTED in detail (secondary)
- eventstudytools.com/methodology/test-statistics (2026-10-29):
  - Corrado's S(K) is the time-series sd of the mean ranks. The code uses the independence variance ΣL/(12(L+2)) (eventtests.py:129-139).
  - Cowan's p̂ is the mean of the firms' shares. The code pools all changes (eventtests.py:121-122), which agrees only with equal L_i.
- U = K/(L+2) − ½ and its variance are consistent with Pynnönen eq. 7-8 (T = L+1).
- Primary papers: UNVERIFIABLE.

## A9 — Patell, BMP CONFIRMED
- With no intercept, e₀ is not demeaned and s_i has ddof 1, so SA ~ t_{L−1} with variance d/(d−2), d = L−1. The secondary's (M−K)/(M−K−2) gives the same with K = 1.
- Code: eventtests.py:112-116, L = count of clean e (inputs.py:132).
- BMP (eventtests.py:41-46) ✓.

## A10 — G1 calibration (HEAD ADR 0005:764-772)
| ADR parameter | Code |
|---|---|
| same-date corr within/across sector | estimated (g1.py:370-375) |
| lag-1 acf; lag-1 cross-firm corr | estimated; c1 > 0 → ψ, **c1 < 0 → κ** |
| cross-sectional-mean acf lags 1-10 | measured, only lag 1 used |
| AR of levels | estimated, plus noise and Kendall corrections |
| drift "slope of each firm's baseline levels on time" | **different estimator**: sd of firm-mean changes (g1.py:379-381) |
| mean-crush spread, s_i dispersion, day-0 variance ratio | estimated |
- κ (`noise_common`) has no ADR authority. The ADR frames lag-1 cross-firm correlation as stale quotes (HEAD:762).
- H4: the ADR does not explicitly require a σ_d simulation (§1 only places ΔSIGMA_D "on the σ_d series"). The code simulates H4 as the **cm30** day-0 change on H4's event set (g1.py:51-52,87-88,197), calibrated on H1 rows (run.py:75-98). `sigma_d_baseline` is never called, so H4's gate is crush evidence.
- Re-estimated in every replication: TRUE for β, ALIV, e, s_i, R̂, SA, ρ_ij, ρ̄, merged seasons and the unbalanced verdict (g1.py:184-215; suite.py:61-69).
- Caveat: G1's β pools only the design rows (run.py:55-57). Production pools all non-excluded events (A1).

## A11 — VIX-derived values: **escalate**
- **HEAD ADR 0001 §7:** the owner note (277-282) allows committed "class-R columns built from… Cboe, FRED". The body still says S is "committed only under the export rules in data-model §2.1" (324-325), including a disclosure test.
- **Current ADR 0001 §7:** the M3 note (290-296) commits aggregates of VIX-derived values and keeps per-row values local. The S bullet is unchanged.
- **ADR 0004:221-223:** per-event market-adjusted values stay local and only aggregates are published, "under the strict licensing default", a basis that has since been superseded.
- **Data model §2.1:** at HEAD, `beta_vix` S committed and `results` S "only under the export rules" (288-289). Now `beta_vix_cboe` R local; `results` committed; export rules "not built". This **conflicts** with ADR 0001's S bullet.
- By code reading, committed `results.parquet` holds `dm_sd` (sd of daily Δln VIX) and `beta_median` rows (run.py:100-101; results.py:186-195). Not confirmed, because the file is compressed. With an odd firm count the median equals one firm's β.
- Whether these ship is the owner's licensing call.
