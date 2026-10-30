# Milestone 5 adversarial review: claims ledger

- **Reviewed:** the uncommitted working tree on top of `4a24127` (milestone 5, "Report and polish"), 2026-10-29.
- **Protocol:** `evidence-gated-validation`, Tier 2 for every numeric and statistical claim (documents channel plus a
  runtime probe), Tier 1 elsewhere. Default verdict for every claim: broken.
- **Mode, stated honestly: single-context sequential fallback.** The change set, the templates, `report_numbers.py`,
  `build_report.py`, `screenshots.py` and the test file were read first; the probe designs were then frozen in
  [`probes/m5/00-preregistration.md`](probes/m5/00-preregistration.md). The same context ran Channel B, so agreement
  is **dual-confirmed (fallback mode)**, not independent. Deviations from the pre-registration: `p06`'s loose scan was
  **PROBE_INVALID** (13,354 per-event forms at 2–3 dp collide with almost any short decimal: 166 "hits", falsifier +1
  only) and was replaced by its `--strict` mode (4+ dp per-event forms, 2-dp VIX-like levels 9–90); `p01c` (double
  rounding of 4-dp JSON printed at 3 dp) and `p06b` (adjustment of the committed per-event values) were added; `p13`
  was folded into `p10`'s app run (the A-mutants are the falsifier).
- **Environment:** [`probes/m5/env-pin.txt`](probes/m5/env-pin.txt) (Python 3.12.13, pandas 3.1.0, numpy 2.5.4,
  python-docx 1.2.0, markdown-it-py 4.2.0, Node 22.23.1, Vite 7.3.7, three 0.186.1, Playwright 1.64.1 from the uv
  cache, Chromium `chromium-1234`).
- **Isolation.** Every mutant, rebuild, re-render and screenshot run used scratch copies under the session scratchpad
  (`<s>` below). Stage-cache reads printed counts, signs and dates only. No dolt, no sec.gov, no token, no network
  (`uv --offline`). No probe prints a VIX value or a per-event VIX-adjusted value. `p99`: see §4.
- Probes: [`probes/m5/`](probes/m5/); verbatim outputs in `probes/m5/out/`.

## 1. Verdicts

| # | Claim | Verdict | Channel B (what ran, what it printed) | Channel A |
|---|---|---|---|---|
| 1 | Every generated number equals the data, right row, right rounding | **PARTIAL** | `p01_oracle.py` (own pandas/json selection and `Decimal` half-even rounding; no import of the tool) aligned each rendered file with its template: **412 placeholders, 182 keys, 400 equal**. The 12 mismatches are all `sample.day0_from/to`: the docs print **2024-12-05 to 2026-10-26** (meta.json = params.yaml's daily *window*), but the 347 events' day 0 runs **2024-12-10 to 2026-10-22** (`event_paths.json` per_event and the stage events, `p04 (b)`). Falsifier (H1 read from the mean-adjusted twin): **41 mismatches, rc 1**. `p01c`: 54 path values, 4-dp JSON vs full precision at 3 dp: **0 differ**. H1–H4 rows are `event_test`/primary/market/daily/all; H5/H6 `crush_drivers` two-way primary; H7 the `implied_realised` Wald; subgroups AMC/BMO, coarse/mixed, front (mean-adjusted, labelled so) all equal the oracle | `iv_view.py:60`: the "median log change, **before the market adjustment**" (report §4.2) is `crush_mean_adj`, the mean-adjusted abnormal change, not the raw log change (JSON units say "log change" too) |
| 2 | `--check` fails on a stale number, an input disagreement, or data that contradict a hand-written sentence | **REFUTED** | `p02_check_gaps.py`, fresh scratch input copies: control S0 (stale number in a block) rc 1. **8 of 8 contradicting scenarios render (rc 0) and then pass `--check` (rc 0)** while the rendered text is false: S1 "IV sits **−0.232** log points above its own quiet baseline" (H2 sign never checked); S2 "b is **0.60**: … which may inflate E a little" (backwards); S3 "the sample size (**365** events, inside the draft's 330–360)"; S4 G1 table "**7.00%** … **pass**" (tests.json rate vs results.parquet 4.60%, and rate vs pass flag, never cross-checked); S5 "20 labels … (**15** confirmed, 2, 1, 1)" (sums to 19; `ambiguous` is in the cross-check sum but not the sentence); S6 README renders the literal **`{{H2.twoway_t}}`** (`PLACEHOLDER` matches `[a-z0-9_.]` only); S7 "spread over most dates (**0.02** without the ten largest)"; S8 "The direction is not in doubt: … t … is **1.20 (p 0.27)**". Step 1 of each (files stale) did fail: staleness works, prose and cross checks do not cover the sentences | `report_numbers.py:439-495` checks 18 claims; `:511-548` ~20 pairs; `:63` the regex. PDF/DOCX are outside `--check` by design (`build_report.py:16-18`), so they can go stale silently |
| 3 | No hand-written text states a wrong or unverified result | **REFUTED** | `README.md:206` links `docs/milestones/05-report-and-polish.md`: **the file does not exist**. `README.md:81-82` (and `tools/screenshots.py:13-14`) say Results, Drivers, Heatmap and Architecture run longer than 2,400 px: re-run captured **About 2,729 px and Sample 2,451 px** too (`out/screenshots_rerun.txt`; About's cut drops M5 and the disclaimer). `prfaq-measured.md:41` item 7 "The draft read a same-date correlation above about 0.2…": `git show HEAD:docs/prfaq.md` has no ρ, 0.2 or correlation; the line is ADR 0005:997. `readme-results.md:33` and report template :19 "every number … from results.parquet and the app JSON": ρ̄ comes from `rhobar_crush.out.txt`, 473 is pinned, and 60, 20/15, [−21, +10], 21, 0.2 are typed (the report's §8 is accurate). "before any result was computed" (template :161) / "before their results" (`prfaq-measured.md:26`) for H5–H7: the m4 ledger (claim 1) found the order **cannot be proven from artifacts**. Checked and right: 60/22, 20/15, [−21, +10] (`params.yaml:59-62`), "decisions table row 24" (`04-drivers.md:92`), "milestone 3 §6.2", "§6.6", 330–360 (`prfaq.md:176`), EDGAR accepted 2026-10-28 (ADR 0002:5,109), the 7-season expectation (ADR 0005:343-346) | — |
| 4 | Agreement with milestones 3/4 and ledgers | **SURVIVES** (numbers); one unprovable sentence | Own Holm in `p01`: H1 4.1e−22, H2 2/2⁸ = 0.0078 → **0.0469**, G = 7 floor 0.0156 → **0.0781** (ranks after H5's 0.0102), post-gate 2.3e−22 / 0.0234 / 0.0469: all equal the placements. Withheld rows: own count over three JSON files **14** = tests.json caveat list. ρ̄: prototype re-run **byte-identical** (`out/rhobar_rerun_cmp.txt`): 0.3006, 0.1920, −0.0282. H7: own recount share **40.1%** (133/332), benchmark 2(1−Φ(√(2/π))) **0.42494**, b 0.767 [0.465, 1.069]. **"Negative in 99.1%"**: `eventtests.gen_sign` returns `w/n`, w = #(A_i < 0) of the market-adjusted crush; `p04 (a)`: **344 of 347** stage `crush_cboe` < 0 = 0.9914 (falsifier ≤ −0.05: 0.9251); mean-adjusted 345/347. Every season mean positive: **9 of 9** raw seasons (8 after the 4-event 2024Q4 merges) | `03-event-study.md:364-379`, `04-drivers.md:92, 307-325, 336-366, 403-441` agree. G1-before-results for H5–H7: m4 ledger claim 1 PARTIAL |
| 5 | §6 has no advice; each observation follows with its limit; plainly not advice | **PARTIAL** | Grep of §6 for buy/sell/short/long/straddle/should/recommend/position/size/trade/profit/edge: only the disclaimer, "short options" as a caution, "size" as the crush's size, "position limits" in the cannot-say list. Not-advice at report lines 6-8 and 300. **But observation 1's heading "The IV fall is predictable in direction and roughly in size" (report.md:305)** is a forward-looking claim: the numbers are an in-sample share (99.1%) and no prediction error, out-of-sample or otherwise, is measured for the size (the only fit is the in-sample R² 0.427 with fixed effects). It also sits against the report's own "Past patterns … do not predict" (line 8) | — |
| 6 | Data policy: no VIX value or per-event VIX-adjusted value anywhere; licence check clean when staged | **SURVIVES** | `check_data_files.py` on a scratch copy after `git add -A` (66 staged paths): **clean**, rc 0; `scan_real_rows.py`: the same 3 pre-milestone lines as m4. `p06 --strict` over report.md, README, PR/FAQ, PDF text, DOCX text: **0 unexplained** hits except `prfaq.md:188` "E = 0.0007" (milestone-0 design parameter, unchanged since HEAD); falsifier (one planted 4-dp per-event value) found. App JSON: no VIX key; `p06b`: the 347 committed per-event path values equal the **mean-adjusted** level 347/347 (VIX-adjusted: 2, coincidences). Screenshots can only draw that JSON; viewed app-about, app-3d and the three stills | DATA.md:19 lists every Cboe aggregate, including the ρ̄ output |
| 7 | PDF and DOCX are faithful exports, < 10 MB, build command recorded | **SURVIVES** | `p07_exports.py`: Markdown 22 headings, 29 table rows, 6 images, 95 paragraphs, 644 number tokens: **all present** in the PDF (13 pages, 699,850 B, 6 embedded images) and the DOCX (337,424 B, 4 tables / 29 rows, 6 inline images). Falsifier (a planted row and image in a scratch Markdown): **7 missing items, rc 1**. Rebuild on a scratch copy with the README's command (`--offline`): rc 0 in 4.3 s; **PDF text and DOCX text identical** to the committed files. Command in README:135, report §8, `build_report.py:3` | Trivial: DOCX links keep their text, not their target (`build_report.py:173-176`) |
| 8 | Every route + phone shot, production build, < ~8 MB, terrain stills real | **SURVIVES** | 21 PNGs, **1,888,411 B (1.80 MiB)**; 11 routes + `app-about-phone`. Re-run of `screenshots.py` on a scratch copy (`npm run build`, `npm run preview`): **18 of 21 byte-identical**, app-implied pixel-identical, app-metrics (local counters) and app-paths differ in 0.07% / 0.02% of pixels. Terrain stills: byte-identical on re-run, 36–68% non-background, and **with `terrain.json` negated they change** (size and an inverted surface, viewed) | — |
| 9 | "What we measured" lists every contradicted milestone-0 statement, corrections accurate | **PARTIAL** | Items 1–6 and 8 accurate. Item 7 misattributes the 0.2 line (claim 3) and drops the caveat the report keeps (β is fitted on Δ ln VIX, so "unrelated" is near-automatic; m4 ledger defect 6). **Unlisted and unmarked:** `prfaq.md:60` "BMP and the Kolari-Pynnönen family … are reported as robustness" (for H1 all their p-values are withheld, G1 17–66%); `prfaq.md:140` "CBOE's daily 30-day IV indices … give a second, daily subsample" and the Feasibility line "the CBOE subsample add[s] events" (item 5 covers only the "independent check"); `prfaq.md:173` "Quiet events are checked as thoroughly as big movers … Looking up every release removes the calendar's errors" (untrue at 20 of 473). `prfaq.md:143` keeps "the prior IV level"; H6 tests ln σ_d (the prior-IV model, `crush_prior_cm30` ln_cm30 −0.0077, q 0.707, agrees, so the revision's "no reliable effect" holds) | — |
| 10 | Header mutants R01–R11, R05c and app A1–A7 are killed | **SURVIVES** | `p10_mutants.py` on a scratch copy, restore SHA-256 ok on all 21: **R01–R11 and R05c: 12 of 12 killed**; **A1–A7: 7 of 7 killed** (baselines 11 passed; 30 passed). **Own X1 (prose claim "b's interval holds 1" set True) and X2 (H7 F cross-check deleted) SURVIVE**: only 1 of 18 prose claims and 1 of ~20 cross-check pairs is pinned by a test. Many R-kills come from `test_check_passes_on_the_committed_files`, a golden-file test: it catches change, not wrongness | — |
| 11 | Graph refresh: code layer, AST only, 371 / 3,559 / 9,107 / 141; svg labelled | **SURVIVES** | `p11_graph.py`: **371 source files, 3,559 nodes, 9,107 edges, 141 communities**; every edge `_origin: ast` (3,491 nodes ast, 68 external package nodes); the 297 INFERRED edges are AST call/uses resolutions (0.85/0.95); 0 files outside the stated scope; the four new tools/tests files are in it. `graph.svg` last changed in `6e4ef9d` (milestone 0) and the README says so | — |
| 12 | README: validation bullets, run commands, screenshot sentence | **PARTIAL** | Bullets match: m0-methodology claim 2 (gap simulation), m1-ledger 3b (scoped look-up rule), m2-ledger 2a/3b, m3-ledger 1a′, defect 5, defect 8 + m3-delta, m4-ledger claim 3 and defect 2. Commands on a scratch copy: pytest **636 passed, 2 deselected**; notebooks OK; licence clean; report check ok; diagrams ok; `npm run verify` **44 files, 1,894 tests, coverage 99.78/99.42/99.39/99.88, built**. "Most test modules list mutations": Python **33 of 38**, app 10 of 44. **Screenshot sentence wrong** (About and Sample also cut) and the broken milestone-5 link (claim 3) | — |
| 13 | MILESTONES 0–5 match the navigation; About no longer says synthetic | **SURVIVES** | vitest on the three files: 30 passed; A2 (misspelt label), A6 (listed twice), A7 (listed nowhere) killed by the App test that compares with the rendered navigation; A5 killed. Trivial: "3D view" is listed as added by M3, but the page was added at M0 (`6e4ef9d`, then "3D preview", synthetic) and turned into data at M3 (`d6d5ea4`) | — |

## 2. Claim 2: what `--check` lets through

`out/p02_check_gaps.txt`. Each scenario: fresh copy of the inputs, an edit, `--check` (rc 1, stale), render (rc 0),
`--check` (rc 0).

| Scenario | Edit | Sentence now rendered, and passed |
|---|---|---|
| S1 | H2 estimate −0.2319 (results + tests.json, same floor p) | "IV is high before the news. At day −1 the 30-day IV sits −0.232 log points above its own quiet baseline." |
| S2 | `implied_realised_m2` b 0.60 | "With E read one session earlier, b is 0.60: day −1 quotes are often wide …, which may inflate E a little." |
| S3 | sample 365 (meta, funnel, H1 n, consistent) | "Confirmed as predicted: the sample size (365 events, inside the draft's 330–360)" |
| S4 | tests.json H1 G1 rate 0.07, `pass` true | "\| Primary rejects … \| 7.00% \| … \| Verdict \| pass" (results.parquet still 4.60%) |
| S5 | timing statuses: 15 confirmed + 1 ambiguous | "20 labels … (15 confirmed, 2 corrected, 1 with a corrected date and 1 inferred)" |
| S6 | template typo `{{H2.twoway_t}}` | README: "two-way t {{H2.twoway_t}})" |
| S7 | ρ̄ without the top 10 dates 0.0200 | "It is spread over most dates (0.02 without the ten largest)" |
| S8 | H2 two-way season t 1.20, p 0.27 | "The direction is not in doubt: the two-way season × company t … is 1.20 (p 0.27)" |

## 3. Defects, by severity

1. **Major (the check gives false assurance):** `prose_check`/`cross_check` miss eight sentence-level contradictions
   (§2), and the docstring (`report_numbers.py:25-30`) and README block footer promise more. *Fix:* add claims for
   H2 > 0 and every season mean > 0 (or drop the sentence), `m2_b > b`, `330 ≤ n ≤ 360`, `pass == (rate ≤ band)` and
   tests.json-vs-results.parquet G1 rates, `ambiguous == no_document == 0`, `rhobar.no_top10` well above 0 (or
   reword), the two-way t's p < 0.05; make `PLACEHOLDER` find any `{{…}}` and fail on what it cannot parse; add one
   test per new claim (today X1/X2-type mutants survive).
2. **Moderate (docs):** `README.md:206` dead link to `docs/milestones/05-report-and-polish.md`. *Fix:* write the page
   or drop the link until it exists.
3. **Moderate (PR/FAQ corrections list):** three contradicted draft statements are not listed or marked
   (`prfaq.md:60`, `:140` + Feasibility, `:173`); item 7 (`prfaq-measured.md:41`) attributes ADR 0005's warning line
   to "the draft" and drops the β caveat. *Fix:* add items for the withheld BMP/KP rows, the missing Cboe subsample
   and the unmet quiet-event guarantee; reword item 7 as "ADR 0005 read …", add "(close to automatic, because β is
   fitted on that change)".
4. **Minor (wording of a number):** "day 0 from 2024-12-05 to 2026-10-26" describes the window, not the sample
   (realised 2024-12-10 to 2026-10-22). Right in the funnel row; wrong in `readme-summary.md:1-3` ("347 announcements
   … with day 0 from"), the README results line, report §2 "the primary sample has day 0 from" and §6, PR/FAQ. *Fix:*
   say "day 0 in the window …" or export the realised range.
5. **Minor (README/screenshots):** `README.md:81-82`, `tools/screenshots.py:13-14`: add About (2,729 px) and Sample
   (2,451 px); About's shot loses M5 and the disclaimer.
6. **Minor (§6 obs. 1, report template :306):** "predictable in direction and roughly in size" → "near-universal in
   direction in this sample"; drop "roughly in size" or give a measured error.
7. **Minor (provenance sentences):** report :19 and `readme-results.md:33` say every number is from results.parquet
   and the JSON; name the ρ̄ output, the pinned 473 and the typed parameters. "Before any result" for H5–H7 (template
   :161, `prfaq-measured.md:26`) should say "before the results were written (order not provable from artifacts)".
8. **Trivial:** report §4.2 "median log change, before the market adjustment" is the mean-adjusted change
   (`iv_view.py:60`); "q 0.75" (3 s.f. with the zero dropped) beside "q 0.773"; `slope.q` at fixed 4 dp (one s.f.);
   AMC/BMO day −1 run-up from the 347-event path (+0.270/+0.191) vs the 356-event RUNUP rows (+0.268/+0.193); "3D view"
   listed under M3; DOCX links lose their targets; `fig-implied-move.png` is made but used nowhere.

## 4. Commands and integrity

From the repository root; `<s>` is `/tmp/claude-1000/-home-rajib2k5-dev/9fcceee1-9f95-4cb4-9f87-030ec5521894/scratchpad/m5`.

```
uv run --frozen --offline --no-sync python tools/report_numbers.py --check            # ok: 3 files, 222 numbers, 453+20=473
uv run --frozen --offline --no-sync python docs/validation/probes/m5/p01_oracle.py --contexts   # 412 checked, 12 mismatch (day0 range)
uv run --frozen --offline --no-sync python docs/validation/probes/m5/p01_oracle.py --falsify    # 41 mismatches, rc 1
uv run --frozen --offline --no-sync python docs/validation/probes/m5/p01b_rounding.py           # exact ties exist only in pre-rounded JSON
uv run --frozen --offline --no-sync python docs/validation/probes/m5/p01c_double_rounding.py    # 0 of 54 differ
uv run --frozen --offline --no-sync python docs/validation/probes/m5/p02_check_gaps.py <s>/p02  # 8 of 8 pass --check
uv run --frozen --offline --no-sync python docs/validation/probes/m5/p04_stage.py [--falsify]   # 344/347; 2024-12-10..2026-10-22; 9/9
uv run --frozen --offline --no-sync python docs/validation/probes/m5/p06_vix_scan.py --strict [--plant]   # 0 (+1 planted)
uv run --frozen --offline --no-sync python docs/validation/probes/m5/p06b_per_event_adjustment.py         # 347 mean-adjusted
uv run --frozen --offline --no-sync python docs/validation/probes/m5/p07_exports.py docs/report/earnings-vol-report.{md,pdf,docx}  # 0 missing
(cd <s>/repo && uv run --frozen --offline --group report --with playwright==1.64.1 python tools/build_report.py)  # text identical
(cd <s>/repo && uv run --frozen --offline --with playwright==1.64.1 python tools/screenshots.py --out <s>/shots --port 4199)
.venv/bin/python docs/validation/probes/m5/p10_mutants.py <s>/repo .venv/bin/python all          # killed 19 of 21 (X1, X2 survive)
python3 docs/validation/probes/m5/p11_graph.py
(cd <s>/repo_dfc && git add -A && PYTHONPATH=src <repo>/.venv/bin/python tools/licensing/check_data_files.py)  # clean
uv run --frozen --offline --no-sync python research/prototypes/rhobar_crush.py > <s>/rhobar_rerun.txt   # byte-identical
bash docs/validation/probes/m5/p99_integrity.sh <s>
```

**Integrity** (`out/p99_integrity.txt`): `git status --porcelain` differs from the start only by
`docs/validation/probes/m5/` (and this ledger). The SHA-256 of the 664 other tracked and untracked files and of the
1,443 stage-cache files are identical to the snapshots taken before the first probe; the set of cache files is
unchanged. All 21 mutant restores: `sha256 ok=True`. No preview server of this review is left running.
