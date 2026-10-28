# Milestone 0 delta review: were the refuted claims fixed, and did the fixes break anything?

- **Date:** 2026-10-28.
- **Scope:** the fixes made after [`m0-code-ledger.md`](m0-code-ledger.md) and
  [`m0-methodology-ledger.md`](m0-methodology-ledger.md). That covers:
  - ADRs 0001–0005, the data model, the PR/FAQ and the milestone doc;
  - `research/prototypes/`, the code and app fixes, and the public-repo hygiene of the final tree.
- **Default verdict on every claim:** broken.
- **Method:** evidence-gated validation.
  - Tier 2 (two channels) for statistics, numerics and version-sensitive API claims.
  - Tier 1 (a probe plus a falsifier) for everything else.
- **Mode: hybrid.** Agreement is "dual-confirmed (hybrid)", not independent proof.
  - **Channel A (primary literature, library source) was run by an independent sub-agent.**
    - It saw only the frozen claims, never a probe or its output, and it executed nothing.
    - It read the MDPI PDF of Pynnönen (2022) in full, the authors' preprints of Cameron-Gelbach-Miller (2011) and
      Cameron-Miller (2015), the Webb QED working paper 1315, Canay-Santos-Shaikh (2021), Crossref, and the
      installed statsmodels 0.15.0 source.
    - The MDPI article pages and SSRN returned 403.
  - **Where the "documentation" is the ADR text itself** (*spec*), I read it myself. That is the single-context
    fallback.
  - **Claims 8 and 10 were run by a forked sub-context** on a scratch copy of the repo. I re-ran three of its results
    myself (marked ✔ below).
- **Pre-registration:** the claims and probe designs in the appendix were written to a file before any new probe ran
  and before Channel A started. The task required the repo's own prototypes to be re-run first, so those runs came
  earlier.
- **Environment:** Linux aarch64, CPython 3.12.13 (`.venv`), uv 0.11.25, numpy 2.5.4, scipy 1.18.1, pandas 3.1.0,
  statsmodels 0.15.0, Node 22.23.1, npm 10.9.8, git 2.43.0.
- **What was run:**
  - Every probe runs from the repo root with `PYTHONDONTWRITEBYTECODE=1 uv run --no-sync --frozen python <probe>`.
  - Mutations, `npm ci`, `npm run verify` and the exporter ran only on a scratch copy outside the repository.
- **What was not done:**
  - No `dolt` command and no DoltHub query.
  - No contact with SEC EDGAR.
  - Nothing committed.
- **Integrity:**
  - The md5 of `research/prototypes/*`, `uv.lock` and `pyproject.toml` was the same before and after: 19/19 OK.
  - There is no `__pycache__` outside `.venv`.
  - The sub-context's sha256 check of 69 code files and 88 doc and data files found no change.

## Verdict table

Severity applies to a REFUTED row. On a SURVIVES row it is the severity of the attached note, or "–".

| # | Claim | Channel A (sources) | Channel B (what ran → what it printed) | Verdict | Sev |
|---|---|---|---|---|---|
| 1a | Every number ADR 0005 and the PR/FAQ quote from the H2/H3 simulations reproduces (4.75–5.80, 4.15–5.80, 4.25–6.08, 1.65–2.25, 8.95–9.12 / 5.22–5.65, bands [4.12, 5.90] / [3.80, 6.30]) | *spec*: ADR 0005:81-87, :534-547, :554-569; PR/FAQ :121-125 | `h2h3_followup_sim.py` re-run (16 s). The diff against `h2h3_followup_sim.out.txt`, ignoring the timing lines, is **identical**. `h2h3_size_sim.py` re-run (3 m 10 s): also **identical**. Every quoted range is the min/max of the right cells: CRUSH two-way, nine size designs 4.75–5.80, twelve designs 4.15–5.80; ramp two-way under random walk 4.25–6.08; under mean reversion 1.65–2.25. The cross-season overlap shares were re-measured from the design: **4.6% / 9.4%**, of which **67.3% / 47.8%** involve the 30 off-cycle events. ADR :261-264 matches. | **SURVIVES** | – |
| 1b | ADR 0005 §2b's two-way CR1 is the Cameron-Gelbach-Miller estimator, and statsmodels' 2-D `groups` computes the same | CGM preprint (May 2009) eq. 2.11: V = V^G + V^H − V^{G∩H}, factor G/(G−1)·(N−1)/(N−K) per component. With K = 1 that is the ADR's formula. statsmodels 0.15.0 source: `cov_both = cov0 + cov1 - cov01`, `use_correction=True`, `df_resid_inference = min(G_A, G_B) − 1`, **but `use_t` defaults to False for cluster**. **Refuted citation:** ADR 0005:241 credits t_{min(G)−1} to Cameron & Miller (2015). CM 2015 gives no df for multiway clustering. For "multi-way clustering and few clusters" it says the authors are "not aware of an ideal approach" (§VI.E.3). The min(G,H)−1 critical value is CGM's (preprint p. 16). | `d1_twoway_cgm.py`. Hand 4-event example: hand **0.000608333333333** = ADR = statsmodels. Over 400 random designs (study-shaped, and with repeated firm×season cells): max relative difference **1.4e-15**, p-value difference 6.1e-16, df identical (5 or 6). Falsifiers: intersection added **0.16**, G/(G−1) dropped **0.10**, intersection dropped **0.08** relative difference, so all are caught. With default `use_t`, p = 0.898 (normal); with `use_t=True`, 0.903 (t₅). | **SURVIVES** (formula). **REFUTED** (the CM 2015 attribution). | minor |
| 1c | Full Rademacher enumeration at G = 7 has the floor 2/128, and that p "can pass only from the fourth step on" | Webb WP 1315 pp. 5-6: 2^G samples; v and −v give equal \|t\|; the enumeration p-values lie in {1/2^(G−1), …}, so the minimum is 2/2^G. CSS (2021) Remark 2: with no nuisance regressors and H₀ fixing β (our intercept-only case), the test is a randomisation test, exact under sign symmetry. Holm (1979) itself was not reachable. statsmodels' `holm` compares p_(k) with α/(m−k+1). | `d1_rademacher_holm.py`. Smallest p over 20,000 data sets: **0.015625**. \|t\*(+1) − t\| and \|t\*(v) + t\*(−v)\| ≤ 1.1e-13. Falsifier (128 sampled sign vectors) gives p = 0, below the floor. **Holm, m = 7:** step 4's threshold is 0.05/4 = 0.0125 < 0.0156, so the floor fails there. It **first passes at step 5** (0.05/3). statsmodels `holm` rejects the floor p only after **4** smaller p-values. Nit: the prototype's absolute tolerance `-1e-12` lets p fall to 0 once \|t\| ≳ 286. | **SURVIVES** (floor). **REFUTED** ("fourth step": it is the fifth, ADR 0005:406-407 and :676). | minor |
| 1d | The primary is correctly sized in the cases its own routing rules send it to, which the repo never simulated | *spec*: ADR 0005:270-275 (1.5× rule), §5 mutation table :755 ("expected to be caught, not yet measured") | `d1_unmeasured_designs.py`, 4,000 reps per design, band [4.12, 5.90]. **R0 control** (the repo's unbalanced row, same seeds): 9.12 / 8.95 and 5.22 / 5.65, reproduced exactly. **U1**, seasons 35 vs 52 (ratio 1.49, so the two-way t is used): **5.73 / 5.67**. **U2**, unbalanced + firm drift 0.0015 (so `rad_season_p` is used): **5.25 / 5.92**. **U3**, unbalanced + firm effects 0.03: **4.85 / 5.22**. **U4**, two-way with normal instead of t₆ critical values: **10.35 / 11.22**, so G1 (bar 6.30) does catch it. **D2 with fresh seeds**, PERSIST_10 two-way in 5 more runs: 6.30, 5.67, 6.85, 5.17, 5.67. Pooled with the repo's 6.05 that is **5.95%** (24,000 reps, se 0.15), i.e. truly about 1 point liberal, as ADR :85-86 says. | **SURVIVES** | minor (N2) |
| 2a | KPP (2018) and Pynnönen (2022) are cited correctly | Crossref 10.2139/ssrn.3167271: title, authors Kolari / Pape / Pynnonen, 2018, and the quoted abstract phrase word for word. MDPI PDF: J. Risk Financial Manag. 2022, 15, 149, doi 10.3390/jrfm15040149, CC BY. The reference list (29 entries) does not cite SSRN 3802405, as ADR :329-331 says. | Not applicable: bibliographic text (the Crossref probe was already run by `m0-methodology/p10`) | **SURVIVES** (single channel: text claim) | – |
| 2b | Eq. 25 is the per-pair weight (τ_ij/τ)ρ_ij; eqs. 27 and 32-35 are what ADR 0005 §2e says | MDPI PDF: **eq. 25** = ((T−1)/(T−τ))·(τ_ij/τ)·ρ_ij. **Eqs. 32-35**: ρ̂̄ = (1/M)Σ_tΣ_{i≠j}U_itU_jt, M = Σn_t(n_t−1), = (N/M)(s²_U − 1). **Eq. 27**: ρ̄ = (nσ²_z̄ − 1)/(n − 1), "the method introduced by Edgerton and Toops". §2 names KPP for BMP under partial clustering. Before eq. 40: (1 + (n−1)νρ̄), ν = τ̄/τ, credited to KPP. No clamp anywhere. Rank-test size at 11/21 days, partial clustering: 0.065–0.086. **Two overstatements:** (i) Assumption 1 is stated for *stock returns* r_it, not abnormal returns (ADR :104, :333). (ii) ADR :394 says eq. 27 "is the same identity" as KP's pair, but E[s²] = σ²(1−r̄) is not in Pynnönen. | Not applicable (text claim) | **SURVIVES** (single channel: text claim) | minor (wording) |
| 2c | No "ours / no published procedure" claim remains anywhere in `docs/`, `README.md`, `LEARNING_LOG.md` | n/a | Grep over every file, generated ones included. **Hand-written docs: clean** (only quoted refutations). **But** `docs/architecture/graph/` is generated graphify output dated before the fixes, and it still says so: `GRAPH_REPORT.md:79,139,304,306` "kp_ow_t … (PRIMARY, authors' own)"; `graph.json` and `graph.html` (2 hits each) and `graph.svg:39190` "kp_ow_t: overlap-weighted KP, the primary statistic and our own unvalidated generalisation". It also carries "H2: mean RUNUP = 0 (kp_ow_t, no size evidence yet)", "A wrong s_i costs efficiency, not …", "H7 … (date-clustered Wald)". | **REFUTED** | **major** (public, under `docs/`, the exact claim refuted in round 1) |
| 3a | `worked.py` gives E = 0.00088284, √E = 2.9713%, and every value quoted in ADR 0003, ADR 0004 §3 and the milestone doc | *spec*: ADR 0003:13-18, :180-195, :286-287, :320-345, :352, :377, :440; ADR 0004:16, :139; ADR 0005:652; milestone :552-554, :786-792; 00-background :121 | The re-run is identical to `worked.out.txt`. Every quoted value matches after rounding: F, w, τ, IV per row; σ_d² 2.3667e-4 (24.4%); 0.00088267 from 6-dp w; 2.37 / 2.67 / 4.71%; calendar 0.001204 / 3.47% (+36% / +17%); −12.3 = −4.1 − 8.2; 0.0011195; −0.31%. **Independent hand check of the 4-strike rule** on 10-30 / 11-14: \|C−P\| mids are 272.5: 1.15, 275: 3.50, 267.5: 4.55, 277.5: 6.15 (then 265: 7.08, 280: 8.30, 262.5: 9.19). That selects {267.5, 272.5, 275, 277.5}, median (271.35 + 271.49)/2 = **271.42**. | **SURVIVES** | – |
| 3b | The new identity check can fail on a planted bug | *spec*: ADR 0003:274-287 says it catches a lost 252 | `d3_worked_mutants.py` on a scratch copy. **Caught (rc 1):** m1 `iv_reported` loses the 252; m3 E-formula denominator t2 + t1. **Not caught (rc 0):** m2, the forward over all strikes (ledger N1's own bug), E 0.00069327; m4, 12 sessions in E, E 0.00029116; m5, a 360-day DF; m6, ATM w = lower strike only (E 0.00008131). Control rc 0. The check tests the two E formulas against each other on literals (11, 20), not the printed E. | **SURVIVES** (it can fail) | minor (N6) |
| 4a | "Proposed: pending owner decision" is marked consistently wherever EDGAR is mentioned | n/a | Grep for EDGAR / 8-K across the commit set: 70 hits, each read. **Marked:** ADR 0001:15-17, :74; ADR 0002:4, :34, :60-61, :194, :292; ADR README :10; data model :22-27, :151, :200-210, :461-465, :792-795; PR/FAQ :107-108; milestone :8, :699-705, :1107, :1122; README :16-17; LEARNING_LOG :29; architecture README :27-29, :613-615; every `.mmd` / `.yaml` (dashed, "(proposed)", "only if approved"). **Unmarked, stated as consequences of the decision:** ADR 0002:**359-360** ("EDGAR timestamps resolve both"), **:361-363** (see 4c), **:371-374** ("EDGAR becomes an input of the `events` layer"; "a hand check for … every event without an 8-K … a few dozen press releases"), **:390** (Alternatives: "EDGAR gives the same fact mechanically"); ADR 0001:**75** (`events` inputs list "SEC EDGAR 8-K filing index"). | **REFUTED** | minor |
| 4b | The default (press release, then calendar; gaps only trigger; stratified audit; tercile reporting) is fully specified, including events nobody checked | n/a (*spec*) | Read ADR 0002 §3, the data model and the milestone doc. **(i) NULL-label events have no rule.** The trigger "the gap contradicts the label" (ADR 0002:259) is undefined without a label. ":286-288 Every other event keeps the calendar label … `unverified`" is undefined for NULL. Row :235 makes an unchecked NULL event `ambiguous`, i.e. excluded. Whether a NULL-label event is looked up is therefore unspecified, so 4c simulates both readings. **(ii) `unverified` has two meanings.** The data model (:462) and the milestone doc (:711) define it as "no document found" (a search failed). ADR 0002:287-288 assigns it to every event never searched. Under the default that is about 3/4 of the sample (4c), indistinguishable in the data. | **REFUTED** | **major** |
| 4c | The default no longer selects on move size (or: by how much) | n/a | `d4_default_gap_selection.py`: p02's world at the real scale, 2,000 samples × 365 events, the 17/17/16 audit inside each sample. Favourable assumption: every hand check finds a correct press release. Shares are by the true move's tercile, low / mid / high.<br>**Wrong day 0 among kept events:**<br>• t(3) gaps: **2.11 / 1.66 / 0.30%**<br>• normal gaps: **2.63 / 2.18 / 0.61%**<br>• control "no check": 2.96 / 3.01 / 3.01% (flat, so the probe can report no dependence)<br>• check every event: 0 / 0 / 0<br>**Mislabels corrected:** **28 / 44 / 90%** (t3), **15 / 26 / 80%** (normal).<br>**Attenuation of the mean crush:** low tercile 2.0% (t3) / 2.7% (normal) of the true crush; high 0.25% / 0.6%.<br>**Exclusion:** none under reading R1 (every NULL looked up). Under R2 (NULL looked up only on a gap signal), **0.91 / 0.71 / 0.12%** (t3), so it selects on the move.<br>**The audit cannot bound the selection.** In the low \|r₀\| tercile (true residual rate 4.2%), 17 audited events find **0 errors in 48%** of samples. The estimate's sd (4.8%) is about its mean. The 95% upper bound at 0 found is 16%. P(the audit finds more errors in the low tercile than in the high one) = **0.51**; P(≥ 2 more) = **0.15**.<br>**The tercile report is confounded.** \|r₀\| is measured on the day 0 used, so a mislabelled event shows an ordinary day's move and falls in the low tercile. With uniform errors ("no check"), wrong day 0 by *measured* tercile is **7.32 / 1.61 / 0.17%**. Under the default, the `unverified` share trends **0.71 / 0.81 / 0.83** by construction. ADR 0002:404-405's "status mix or mean crush trends across \|r₀\| terciles" therefore fires in every world.<br>**For scale:** the old rule gave 6.8 / 0.4% and 9.2 / 0.4% exclusion. | **REFUTED** for ADR 0002:**361-363** ("does not differ in accuracy between quiet events and big movers") and **:244** (under R2). The selection is **about 3× smaller** than the old rule's, **but not bounded** by the audit as ADR 0002:270-271, :288-290 claim. | **major** |
| 5 | The ALIV gap fix (span changes over observed sessions, weight constant across each gap) is exact | *spec*: ADR 0005:128-172, ADR 0004:172-174 | `d5_aliv_span.py`, 2,000 random paths per case. Cases: all observed + hole; 3 unobserved; **Mon/Wed/Fri**; unobserved t−1; unobserved min B+1; unobserved inside an excluded zone. Max \|rule − ALIV\| ≤ **3.3e-16** in every case. Falsifiers bite: n/(\|B\|−1) up to 3.9e-2; walk from after min B 4.4e-3–8.0e-3; weight at span start up to 3.7e-2; one-session changes only up to 0.63 (equal when all sessions are observed, as expected). | **SURVIVES** | – |
| 6 | 97.1% / 20.3% / 83.3% are reproduced and worded consistently | n/a | `spacing.py` re-run: 306 gaps, **0.971 / 0.203 / 0.833**, clean median 31. Grep of the three numbers and of 97% / 20%: ADR 0004:10-14, :27-28, :52-56, :220; PR/FAQ :116; milestone :824-827, :1038; prototypes README :10, :28-29; `spacing.py:25`. Each is attached to its own definition (overlap / contains day 0 / day −60 inside). | **SURVIVES** | nit: "contains its day 0, the crush itself" holds only if day −1 is also inside (g ≤ 59) |
| 7a | T1\* has τ ≥ 5 at day 0 | n/a | ADR 0003:138-142, milestone :745-746, data model :400, :427: all τ ≥ 5. No "4 sessions" rule left (grep). | **SURVIVES** | – |
| 7b | H7 is written as r₀² = a + b(E + σ²_d,ann/252) everywhere | n/a | Correct: ADR 0005:646-653, ADR 0003:256-257, :362, data model :611. **Wrong:** `docs/concepts/00-background.md:153`, **:669** and **:671** write E + σ_d². In that document σ_d is annualised: §1.4, :47, and :115 and :122 write σ_E² + σ_d²/252. So H7 there is off by 252× in its own notation, and :153 claims it "matches the [3] standardisation". | **REFUTED** | minor |
| 7c | `sigma_d*` columns are annualised | n/a | Data model :407 (`sigma_d_iv` "annualised volatility"), :579, :611 (`sigma_d_m1`). | **SURVIVES** | – |
| 7d | The leak range is 0–0.66 / 0–2.73 vol points | n/a | `leak_grid.py` re-run, identical: f median 0.128, max 0.400; leak 0.66 / 0.83 / 2.73 max, 0.21 / 0.27 / 0.90 median. ADR 0003:180-195, :26-27 and PR/FAQ :118 match. | **SURVIVES** | – |
| 8a | Exporter values: exp-6..9 are now killed | n/a | Sub-context, `code/mutate_py_delta.py`: exp-6, 7, 8, 9 **KILLED**, as are 7 new mutants of DATA_SOURCES / DATA_LICENCE. One survivor, exp-18 (`or` fallback), is equivalent. | **SURVIVES** | – |
| 8b | CRLF notebook drift | n/a | Sub-context, `code/nb_drift_delta.sh`: CRLF, CR-only, first-line-only and last-newline CRLF all give **rc 1**; unchanged rc 0; reverting to the text compare is killed by `test_notebooks_sync.py:33-43`. | **SURVIVES** | minor (N10) |
| 8c | Envelope types and the 2**53 boundary | n/a | Sub-context, `code/contract_boundary_probe.py` (✔ re-run by me on the real repo). ±(2**53−1) accepted; ±2**53, nested values and `10**400` rejected; strings with digits are not false-rejected; bad kind / source_commit / data raise TypeError. 13/13 boundary and type mutants killed. | **SURVIVES** | nit (N12) |
| 8d | MetaFooter stale-response guard | n/a | Sub-context, `code/mutate_app_delta.mjs`: guard removed, cleanup a no-op and empty deps are all **KILLED** by "ignores a late answer for an old url". The same holds for `DataSourcesSection`. | **SURVIVES** | – |
| 8e | `parseMetaData` rules | n/a | Sub-context: **24/24** rule mutants killed. `publicData.test.ts` fails on an http URL, CBOE committed=true and an unknown `applies_to`. | **SURVIVES** | – |
| 8f | `meta.json` is the single source of the About page's data-sources table | n/a | **(i) SURVIVES:** there is no hard-coded copy in `app/src`, the production `<App/>` renders a changed licence from `meta.json`, and the exporter's output equals the committed file apart from `generated_at` and `source_commit`. **(ii) REFUTED:** a wrong committed `meta.json` passes everything. V1 (DoltHub rows "CC BY 4.0"), V2 (BY licence everywhere) and V3 (Yahoo row dropped, wrong URL) each give **208/208 app + 70/70 Python**. ✔ My grep: no Python test reads `app/public/data/meta.json`, and `publicData.test.ts` checks shape only. `app/DATA.md:33-34` ("a wrong licence cannot hide in two places") and `:23` ("the only place that lists the data sources"; `app/DATA.md:38-43` and `README.md:114-117` list them again) are false. | **SURVIVES** (i) / **REFUTED** (ii) | **major** |
| 8g | `charts.tsx` / `LineChart.tsx` are gone | n/a | Sub-context: the files are absent and no code references them. The stale generated `docs/architecture/graph/*` still describes them (GRAPH_REPORT.md:243, :279; graph.svg). | **SURVIVES** (code) | minor |
| 9 | Public-repo hygiene of the final tree | n/a | `git status --porcelain --untracked-files=all`: **156** files before this review, **169** with this ledger and its 12 probe files. Grep of all of them: no home-directory or temp-directory path, personal email (only `t@example.com`, `admin@example.org`) or secret pattern. `research/prototypes/*.out.txt` hold no local path. `resolved_commit` is present (32-char Dolt hash) with a candid note; that it re-runs identically is UNVERIFIABLE here, since no dolt or DoltHub query was allowed. **Defects:**<br>(a) `docs/validation/m0-code-ledger.md:73` names a sibling repository that `gh repo view` reports as **PRIVATE**.<br>(b) PR/FAQ :136 calls `vol-strategy-backtester` "not yet public"; `gh repo view` reports it **PUBLIC**.<br>(c) CC BY-SA attribution is missing where DoltHub values are copied: ADR 0002:**103-107** (bid/ask quotes and vendor deltas) and `worked.out.txt` (values derived from the quotes).<br>(d) PR/FAQ :**138** "No CBOE or Yahoo data committed … DoltHub data appears only … in `data/derived/`" is false in letter. DoltHub quotes are in `worked.py` and ADRs 0002 and 0003; Yahoo-labelled closes are in `worked.py:142` and ADR 0002:86, :103-105.<br>(e) `m0-methodology-ledger.md:26` points to notes in a session scratchpad that is not in the repo.<br>(f) `docs/architecture/graph/` (6.8 MB, stale) is in the commit set. | **REFUTED** | minor (a, b, c, d, e); see 2c for (f) |
| 10a | 20 sampled `file:line` links in the milestone doc are correct | n/a | Sub-context: `link_resolver.py` gives **256 resolved, 0 broken**. More than 40 targets were read against their link text, with 0 mismatches. | **SURVIVES** | – |
| 10b | 70 Python tests; 208 app tests in 23 files; coverage 98.96 / 96.98 / 97.67 / 99.48 | n/a | ✔ Me: `uv run pytest -q` gives **70 passed**. Sub-context on a copy: `npm ci && npm run verify` gives `Test Files 23 passed (23)`, `Tests 208 passed (208)`, `All files \| 98.96 \| 96.98 \| 97.67 \| 99.48`; lint clean; build ok. The six §2.5 mutation counts re-measure exactly. | **SURVIVES** | – |
| 10c | The docs say nothing false about the fixes | n/a | False: `app/DATA.md:23`, `:33-34` (8f); milestone **:204** (`contract.ts:83,87` accept empty `kind` / `source_commit`, so "the app would reject them" is false for ""); ADR 0003:285 calls the 4-dp-IV check "independent", but it moves with the forward bug m2 (3b). | **REFUTED** | minor |

**Gate notes.**

- **1b, 1c (floor):** dual-confirmed (hybrid). A quotes the CGM and Webb texts and the statsmodels source; B matches
  them numerically, with falsifiers.
- **1b (citation):** A only. I re-read the downloaded CM 2015 text myself and found the §VI.E.3 sentence. A text
  claim cannot be probed.
- **1c (Holm):** A could not reach Holm (1979). B is arithmetic plus statsmodels' implementation, and both agree on
  step 5.
- **2a, 2b:** text claims, so Channel B is not applicable. Accepted on A alone, and labelled as such.
- **4b, 4c:** the spec was read by me (*spec*). B produced the counterexamples, with a flat control. For a "does not
  differ" claim, a valid counterexample is decisive.
- **8, 10:** Tier 1. They rest on the sub-context's probes, of which I re-ran three.

## New problems (not in the claim list)

| ID | Problem | Evidence | Sev |
|---|---|---|---|
| N1 | **Under the default, the cheapest fix is the rejected alternative.** ADR 0002:390 rejects "hand-check every event's press release" because "EDGAR gives the same fact mechanically". If the owner declines EDGAR, that reason is gone, and the "what would make it win" column does not list that case. | `d4`: the default costs **59–79** hand checks per 365-event sample (50 of them the audit) and leaves 2–3% wrong day 0 in the quiet tercile. Checking every event costs 365 and removes all move dependence (0 / 0 / 0). | major |
| N2 | **statsmodels' default p-values are normal for `cov_type="cluster"`.** ADR 0005:629-630 plans to check the two-column `groups` covariance against CGM on a 4-event example. That check does not pin the df. At G = 7, normal critical values give **10.4–11.2%** (U4). G1 covers this only for the intercept-only H2/H3, not for the H5–H7 regressions or the ramp regressions. | `d1_twoway_cgm.py` [defaults]; `d1_unmeasured_designs.py` U4 | minor |
| N3 | **The non-PSD fallback can return V = 0.** "If V ≤ 0 use max(V_A, V_B)" (ADR 0005:241) gives 0 when both one-way cluster sums are 0, so t = ±∞. CGM recommend eigenvalue clipping (which gives 0 too for a scalar). Neither rule says what to report then. | `d1_twoway_cgm.py` [non-PSD]: V_A = V_B = 0, V_I = 0.333, ADR uses 0.000 | minor |
| N4 | **The G1 bar cannot separate 5% from 6%.** PERSIST_10 under D2 has a true size of about 5.95%. Six independent 4,000-rep runs gave 5.17–6.85%. At 2,000 reps a statistic with true size 5.95% passes the 6.30% bar about 3 times in 4. This matters only if the calibrated design resembles D2. | `d1_unmeasured_designs.py` U4, U5a–d | minor |
| N5 | **`rad_season_p` in the prototype** compares \|t\*\| ≥ \|t\| − 1e-12 with an absolute tolerance, and computes t\* by a different route than t. The ADR's floor (and its "never passes Holm's first step") then fails once \|t\| ≳ 286. That is unrealistic for ramps, but the §5 oracle should count the identity vector explicitly. | `d1_rademacher_holm.py` (b) | nit |
| N6 | **The worked example's checks do not protect the oracle value.** Neither check in `worked.py` would have caught ledger N1 (m2), a wrong session count (m4) or a wrong ATM interpolation (m6). The hand-computed 4-strike selection in 3a is the only independent check of the forward rule. | `d3_worked_mutants.py` | minor |
| N7 | **The \|r₀\|-tercile diagnostics are confounded by construction** (4c). The sample-funnel trend test (ADR 0002:274-280, :404-405; data model `sample_funnel.by_move_tercile`) will flag "label quality depends on move size" even when errors are uniform, and the status mix trends because triggers are defined by the move. | `d4` control C0 by measured tercile: 7.32 / 1.61 / 0.17%; `unverified` 0.71 / 0.81 / 0.83 | major (with 4c) |
| N8 | **No regression guard on the committed `meta.json`** (8f-ii). The notebook got a byte-level `--check` for exactly this class of problem; `meta.json` did not. A related gap: `parseMetaData` does not check that a source named in `applies_to` carries `licence == data_licence.name`. The sub-context's mutant dt-4 survived. | sub-context V1–V3, dt-4 | major |
| N9 | **With no `.gitattributes`, the byte-strict notebook check fails on a Git-for-Windows checkout** (`core.autocrlf=true`). Also, `build_notebooks.py:130` writes with `write_text` and no `newline="\n"`. | Sub-context clone probe: "CR count 96". ✔ I confirmed there is no `.gitattributes` and that `:111` compares bytes. | minor |
| N10 | **Ledger N6 is still open.** `tests/test_notebooks_sync.py:77-78` says "7 cells" but asserts over `range(len(nb.cells))`. | read | minor |
| N11 | **Wording drift in ADR 0005 §2e.** Assumption 1 is attributed to abnormal returns (it is on returns), and eq. 27 is called "the same identity" as KP's two-part result. | Channel A, 2b | nit |

## Minimal fixes for the refuted claims (not applied)

- **1b:** ADR 0005:241. Change it to: "The t_{min(G)−1} reference follows Cameron, Gelbach & Miller (2011); Cameron &
  Miller (2015, §VI.E) know of no ideal approach for multiway clustering with few clusters, which is why §2g measures
  it." Also add `use_t=True` and an assertion on `df_resid_inference` to the planned statsmodels check (:629).
- **1c:** ADR 0005:406-407 and :676. Change "from the fourth step on" to "from the fifth step on". At that step the
  threshold is 0.05/3; it needs four other rejections first.
- **2c:** delete `docs/architecture/graph/`, or regenerate it after the milestone is final, or move it to the
  git-ignored `graphify-out/` (see deletion below).
- **4a:**
  - Scope ADR 0002:359-360, :371-374 and :390 with "under the proposed EDGAR rule".
  - Mark ADR 0001:75's "SEC EDGAR 8-K filing index" "(only if approved)".
- **4b:**
  - In ADR 0002 §3, "The fallback", add: "Every NULL-label event gets a press-release check" (reading R1).
  - Split `unverified` into `unverified_not_checked` and `unverified_no_document`, or add a `hand_checked` bool. Do
    this in ADR 0002:287-288, the data model :462 and the milestone doc :711.
- **4c:** the cheapest complete fix is N1: under the default, hand-check every event (about 365 look-ups).
  - Otherwise, replace ADR 0002:361-363 with the measured statement: "under the default, quiet events keep a wrong
    day 0 about 2–2.6% of the time against 0.3–0.6% for big movers (`d4`)".
  - Drop the claim that the 50-event audit bounds it, or size the audit for power.
  - Compute the funnel terciles on a move measure that does not depend on the day 0 used, e.g. max(\|g_B\|, \|g_A\|).
- **7b:** `docs/concepts/00-background.md:153, :669, :671`. Write E + σ_d²/252, matching that document's annualised
  σ_d, and point to ADR 0003 §c "Units".
- **8f-ii and 10c:**
  - Add a Python test that loads `app/public/data/meta.json` and asserts `kind`, `schema_version` and `data` equal
    `export_app_data.meta_data()` (or add an exporter `--check`).
  - Add a `parseMetaData` rule: a source in `applies_to` must carry `licence === data_licence.name`.
  - Fix `app/DATA.md:23, :33-34`.
  - Fix milestone :204: "the app rejects non-strings; Python also rejects empty strings".
- **9:**
  - Replace the private repository name at `m0-code-ledger.md:73` with "a private sibling repository".
  - Drop "(not yet public)" at PR/FAQ :136.
  - Add a one-line CC BY-SA 4.0 notice (DoltHub, post-no-preference) to ADR 0002 §Context and to `worked.out.txt`
    (have `worked.py` print it).
  - Reword PR/FAQ :138: "DoltHub data appears as small CC BY-SA extracts in `data/derived/` and as a few quoted values
    in `research/prototypes/worked.py` and ADRs 0002–0003".
  - Call the closes "official close", not "Yahoo".
  - Drop or inline the scratchpad reference at `m0-methodology-ledger.md:26`.

## Single most important fix

**ADR 0002's default timing rule (4b, 4c, N1, N7).** It is the operative rule until the owner decides on EDGAR, and it
decides every event's day 0.

- **It is not fully specified:** NULL labels have no rule, and `unverified` has two meanings.
- **It still selects on move size:**
  - wrong day 0 is 2.1–2.6% for quiet events against 0.3–0.6% for big movers;
  - 15–28% of quiet events' wrong labels are corrected, against 80–90% of big movers'.
- **The two tools meant to bound and detect that cannot do it:**
  - the 17-per-tercile audit finds zero errors half the time;
  - the measured-|r₀| terciles trend even when errors are uniform.

Hand-checking every event's press release under the default costs about 365 look-ups. The default already needs 59–79,
and the full check removes the dependence entirely.

## One item to delete

`docs/architecture/graph/`: 6.8 MB of graphify output generated at 10:09, before the fixes.

- It republishes the refuted novelty claim ("PRIMARY, authors' own"; "our own unvalidated generalisation").
- It also republishes the withdrawn `kp_ow_t` primary and "no size evidence", and documents the deleted `charts.tsx` /
  `LineChart.tsx`.

Regenerate it after milestone 0 is final, or keep it in the ignored `graphify-out/`.

## Probe index (`docs/validation/probes/m0-delta/`; no probe contains a local path)

| Probe | Claim | Notes |
|---|---|---|
| `d1_twoway_cgm.py` | 1b | ADR two-way CR1 vs statsmodels 2-D groups; hand example; 3 falsifiers; defaults; non-PSD case. rc 0. |
| `d1_rademacher_holm.py` | 1c | enumeration floor, ±v symmetry, sampled-sign falsifier, large-\|t\| tolerance, Holm steps. rc 0. |
| `d1_unmeasured_designs.py` | 1d, N2, N4 | imports the repo's design and statistics unchanged; R0 control reproduces the repo row. 20 workers, ~10 s. |
| `d3_worked_mutants.py <scratch_dir>` | 3b, N6 | mutates a copy of `worked.py` outside the repo; checks the original's sha256. |
| `d4_default_gap_selection.py [--nu=3\|1e9]` | 4c, N1, N7 | default rule, readings R1 and R2, controls C0 and C1, per-sample audit. |
| `d5_aliv_span.py` | 5 | span-change rule vs ALIV_t in 6 gap patterns; 4 falsifiers. rc 0. |
| `code/mutate_py_delta.py`, `code/nb_drift_delta.sh`, `code/contract_boundary_probe.py`, `code/mutate_app_delta.mjs`, `code/meta_single_source.sh`, `code/realMetaRender.probe.test.tsx` | 8, 10 | sub-context. All mutations run on a scratch copy given as an argument. The `.tsx` probe is copied into the scratch app only. |

## Appendix: pre-registered claims and probe designs

Frozen before any new probe ran and before Channel A started. The repo's own prototypes were re-run first, because
the task names them. "Pass" is what the claim needs. "Falsifier" is the change that must make the probe fail.

| ID | Claim | Probe | Pass | Falsifier |
|---|---|---|---|---|
| 1a | quoted numbers from the H2/H3 sims reproduce | re-run, diff, grep | identical except timing | edit one kept cell |
| 1b | two-way CR1 = CGM = statsmodels 2-D groups | `d1_twoway_cgm.py` | rel diff < 1e-10; df = min(G)−1 | intersection added; G/(G−1) dropped |
| 1c | floor 2/128; passes Holm from step 4 | `d1_rademacher_holm.py` | floor 0.015625; first passing step = 4 | sampled signs go below the floor |
| 1d | correctly sized where the routing sends it | `d1_unmeasured_designs.py` | ≤ 6.30% | the repo's unbalanced row reproduces |
| 2a/2b | citations and equations | Channel A only (text) | verbatim | – |
| 2c | no novelty claim remains | grep incl. generated files | 0 live claims | – |
| 3a | worked values reproduce and are quoted right | re-run, grep | identical; quotes match | – |
| 3b | the identity check can fail | `d3_worked_mutants.py` | each mutant rc ≠ 0 | (the probe is the falsifier) |
| 4a | EDGAR marked "Proposed" everywhere | grep, read | every normative sentence scoped | – |
| 4b | default fully specified | read | one status per event | – |
| 4c | default does not select on move size | `d4_default_gap_selection.py` | wrong day 0 flat across terciles | control "no check" must be flat by true move |
| 5 | span rule exact | `d5_aliv_span.py` | < 1e-12 | four wrong rules ≥ 1e-6 |
| 6 | overlap shares reproduce and are worded consistently | `spacing.py`, grep | each number on its own definition | – |
| 7a–d | T1\* τ ≥ 5; H7 /252; σ_d annualised; leak range | grep, `leak_grid.py` | everywhere | – |
| 8 | code fixes hold | sub-context mutants on a copy | each former survivor killed | – |
| 9 | hygiene | `git status`, grep, `gh repo view` (visibility only) | 0 hits; attribution everywhere | – |
| 10 | links, counts, coverage | sub-context + my `pytest` | 20/20 links; 70; 208/23; coverage as stated | – |
