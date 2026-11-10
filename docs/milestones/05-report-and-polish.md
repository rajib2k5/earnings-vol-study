# Milestone 5: the report and polish

- **Status:** built; adversarially reviewed ([ledger](../validation/m5-ledger.md)) and the review's findings fixed (§9;
  a delta review of the fixes has not run); **the report is a draft for the owner, who has not reviewed it**. **The
  timing labels are provisional**: 20 of the 473 required press-release look-ups are done, and every other event keeps
  the calendar's label until SEC EDGAR runs. Every result in the report, the README and the PR/FAQ depends on them.
  *Since 2026-11-09* SEC EDGAR is in use: 431 of the 473 look-ups are done (20 press releases, 411 EDGAR 8-K
  times), 42 are open and the 50-event audit has not run, so the labels are still provisional. H1–H7, G1 and the
  sample counts did not change; 13 exploratory rows moved slightly (§12); the report, README and PR/FAQ are
  re-rendered with the new counts.
- **Date:** 2026-10-29
- **Scope:** the written report (Markdown, PDF, DOCX) with its trading-implications section; one script that fills
  every measured number in the report, the README and the PR/FAQ from the committed data, with a `--check` mode and a
  test; the PDF/DOCX build; screenshots of every app page, the report's figures and three 3D stills from the
  production build; the README as the portfolio front page; the PR/FAQ revised with the measured results; the app's
  milestone list; a code-only refresh of the graphify graph.
- **Not done here:** Blender hero renders (**not rendered: Blender unreachable, 2026-10-29**; the Blender MCP could
  not connect and the machine has no `blender` binary); the owner's co-authoring pass of the report.
- **Where this fits:** [LEARNING_LOG.md](../../LEARNING_LOG.md) is the index. No new concept note: this milestone
  explains the results of milestones 1–4, it measures nothing new.

---

## 1. What we built and why

1. **The report** ([`docs/report/earnings-vol-report.md`](../report/earnings-vol-report.md), PDF and DOCX beside it).
   It is marked at the top "Draft for owner review (2026-10-29): not yet reviewed by the owner". It covers the question,
   the data and the sample funnel, the method (day 0, the IV measures, the event variance, abnormal IV, the test suite
   and gate G1), H1–H7 against the binding Holm family with every caveat, implied against realised moves, trading
   implications written as observations with their limits (and a plain "not investment advice"), and ends with eight
   numbered questions for the owner (audience, tone, what to cut, the Holm family, the trading-implications framing,
   publishing with provisional labels, the common date component, the export formats). The owner co-authors it
   later, so the draft did not wait for input.
2. **`tools/report_numbers.py`.** Every measured number in the report, in two README blocks and in two PR/FAQ blocks
   is a placeholder in a template (`docs/report/templates/`), filled from `data/derived/results.parquet`, the app
   JSON and the kept ρ̄ output. `--check` renders in memory and fails when a file is stale, when two inputs that hold
   the same number disagree, when the data contradict a hand-written sentence of the templates, or when the PDF/DOCX
   were not built from the current Markdown. `--list` prints each number with its source.
3. **`tools/build_report.py`.** pandoc is not installed, so the Markdown goes through markdown-it-py to HTML and
   Chromium's print-to-PDF (Playwright 1.64.1), and through the same token stream to python-docx. Both are new
   dependencies in a `report` group (`uv add --group report --bounds exact`, lock updated).
4. **`tools/screenshots.py`.** `npm run build`, `npm run preview` on 127.0.0.1, headless Chromium with reduced motion:
   11 desktop page shots, one phone-width home page, six report figures (one part of a page each) and three stills of
   the 3D terrain (trimmed to the surface), all palette-quantised PNGs in `docs/images/`.
5. **README and PR/FAQ.** The README is rewritten as the portfolio front page. The PR/FAQ keeps its milestone-0 text,
   marks every revised passage "revised 2026-10-29", fills the press release's result paragraph, and adds "What we
   measured (2026-10-29)" with a results table and the nine places where the results contradict the draft.
6. **The app.** `studyContent.ts` lists milestones 0–5 with the pages each added (it listed only milestone 0), and the
   About text no longer calls the 3D view synthetic: it has drawn `terrain.json` since milestone 3.
7. **graphify.** `docs/architecture/graph/` refreshed: code layer only, AST pass, no LLM (§6.5).

## 2. Decisions table

| # | Choice | Alternatives | Why | Cost |
|---|---|---|---|---|
| 1 | Numbers live as **placeholders in templates**; the report, README blocks and PR/FAQ blocks are rendered | write numbers by hand and grep for them | A grep finds a number anywhere, also where it means something else; a render has one source per number | The owner edits the template, not the report (a note at the top of the file says so) |
| 2 | **One pinned number**: the 473 required look-ups | recompute from committed tables | The gap trigger reads `outside_flag_yf`, which stays local; recomputing from committed tables gives 414 + 20, not 453 + 20 | `--check` compares it with the local stage report when there is one (never in CI). *Since 2026-11-09 (§12):* it also pins the open look-ups by reason and the 37 gap-questioned labels |
| 3 | `prose_check`: the templates' qualitative sentences are claims the script checks (53 of them: 24 on the study, 29 on the VX\* cross-check) | trust the sentences | The review's p02 showed new data could render false sentences beside right numbers (§9 F1) | A sentence added to a template needs a claim added too |
| 4 | **PDF via Chromium, DOCX via python-docx**, from one markdown-it token stream | pandoc (not installed); LibreOffice for both | The owner named the fallback; one parser keeps both exports faithful to the Markdown | Tables and lists are re-implemented in `DocxWriter`; DOCX links keep their text but not their targets |
| 5 | Exports **stamped** with the SHA-256 of the Markdown they came from (`earnings-vol-report.build.json`) | compare PDF text | A PDF embeds a creation time, so it is never byte-reproducible; the stamp says which Markdown it was built from | The stamp trusts the build tool |
| 6 | Screenshots are the **top 3,000 px** of each page, palette-quantised | full pages | Drivers runs 12,844 px; a README cannot show that | Results, Drivers, Heatmap and Architecture are cut (the run prints each height) |
| 7 | **Report figures cropped from the app** (`fig-*.png`) | a second charting stack in Python | The app already draws every committed number, checked by its tests; a second stack could disagree | Dark-theme figures in a white document (owner question 8) |
| 8 | 3D stills from **three.js at 2× density, trimmed** | wait for Blender | Blender is unreachable; the stills are real renders of `terrain.json` | Not a hero render |
| 9 | The day-0 **window** and the events' **range** are two numbers | one | meta.json's `day0_from/to` is params.yaml's window (2024-12-05 to 2026-10-26); the 347 events run 2024-12-10 to 2026-10-22 (§9 F4) | none |
| 10 | Holm family: the **declared H1–H7 binds**, the post-gate H1–H4 is reported as a sensitivity | adopt the post-gate family | Milestone 4's decision (row 24) stands until the owner decides | Owner question 4 |
| 11 | graphify: **code files only through the Python API**, not `graphify update .` | `graphify update .` | `update` also took in Markdown, text outputs and images (4,246 nodes); milestone 0 published code only | A small script, run once |
| 12 | `graph.svg` **not refreshed** and labelled so | publish the new one | The refreshed SVG is 12.4 MB; `graph.html` is the usable picture | A stale file, labelled |

## 3. Code walkthrough by `file:line`

- [`tools/report_numbers.py:59`](../../tools/report_numbers.py#L59) `LOOKUPS_REQUIRED` (the pinned 473),
  [`:72`](../../tools/report_numbers.py#L72) `BLOCKS`, [`:80`](../../tools/report_numbers.py#L80) `PLACEHOLDER` (any
  key, so an upper-case typo fails instead of passing through); the formatters
  [`:89`](../../tools/report_numbers.py#L89) `fnum` (Unicode minus, no "−0.000"), [`:109`](../../tools/report_numbers.py#L109) `fp` (p-values), [`:121`](../../tools/report_numbers.py#L121) `fpct`; [`:137`](../../tools/report_numbers.py#L137) `load`; [`:178`](../../tools/report_numbers.py#L178) `primary` (the binding row of each hypothesis);
  [`:227`](../../tools/report_numbers.py#L227) `numbers` (every key, with its source);
  [`:807`](../../tools/report_numbers.py#L807) `prose_check`; [`:893`](../../tools/report_numbers.py#L893) `cross_check`; [`:961`](../../tools/report_numbers.py#L961) `render`; [`:975`](../../tools/report_numbers.py#L975) `splice` (a README/PR-FAQ block); [`:990`](../../tools/report_numbers.py#L990) `rendered`;
  [`:1004`](../../tools/report_numbers.py#L1004) `check_exports`; [`:1024`](../../tools/report_numbers.py#L1024) `check_lookups_against_stage`; [`:1054`](../../tools/report_numbers.py#L1054) `main`.
- [`tools/build_report.py:89`](../../tools/build_report.py#L89) `to_html`, [`:99`](../../tools/build_report.py#L99)
  `build_pdf` (refuses a page whose images did not load), [`:131`](../../tools/build_report.py#L131) `DocxWriter`
  (raises on a token it does not handle, so a new construct cannot vanish), [`:248`](../../tools/build_report.py#L248)
  `table`, [`:348`](../../tools/build_report.py#L348) `main` (the 10 MB limit and the stamp).
- [`tools/screenshots.py:47`](../../tools/screenshots.py#L47) `PAGES`, [`:68`](../../tools/screenshots.py#L68)
  `FIGURES`, [`:95`](../../tools/screenshots.py#L95) `compress`, [`:109`](../../tools/screenshots.py#L109) `trim`,
  [`:148`](../../tools/screenshots.py#L148) `shoot` (fails on any page error).
- [`app/src/lib/studyContent.ts:38`](../../app/src/lib/studyContent.ts#L38) `MILESTONES`;
  [`app/src/lib/StudySections.tsx:24`](../../app/src/lib/StudySections.tsx#L24) the pages line.

## 4. Data flow

```
 data/derived/results.parquet ─┐
 app/public/data/*.json ───────┼─> report_numbers.numbers ─> cross_check, prose_check
 rhobar_crush.out.txt ─────────┘            │
 docs/report/templates/*.md ────────────────┴─> render ─> docs/report/earnings-vol-report.md
                                                       ─> README.md, docs/prfaq.md (marked blocks only)
 earnings-vol-report.md ─> build_report: markdown-it ─> HTML ─> Chromium ─> .pdf
                                                     └─> DocxWriter ─────────> .docx   (+ .build.json stamp)
 app/ ─> npm run build ─> npm run preview ─> screenshots: app-*.png, fig-*.png, terrain-*.png ─> docs/images/
```

## 5. Pitfalls and guards

| # | Pitfall | Guard | Test |
|---|---|---|---|
| 1 | A number typed by hand goes stale when the data change | placeholders, `--check` | `test_check_fails_when_a_rendered_file_was_edited`, `test_new_data_are_rendered_and_make_the_old_files_stale` |
| 2 | A right number beside a sentence the new data make false | `prose_check` | `test_data_that_contradict_a_sentence_fail_the_check`, `test_disagreeing_or_contradicting_data_fail_the_check` |
| 3 | Two exports of the same number disagree | `cross_check` (H1–H7, G1 rates and flags, post-gate, sample sizes) | `test_inputs_that_disagree_fail_the_check`, the parametrised test |
| 4 | "falls by −0.199" | `h1.fall` (and a refusal if H1 turns positive) | `test_key_numbers_from_the_committed_data` |
| 5 | A placeholder left in the text | unknown keys raise; leftovers raise | `test_render_refuses_an_unknown_key_and_splice_needs_both_markers` |
| 6 | A PDF built from an older Markdown | the build stamp | `test_check_fails_when_an_export_is_missing_or_changed` |
| 7 | The window printed as the sample's span | two keys | `test_the_sample_dates_are_the_events_range_and_the_window_apart` |
| 8 | A raw VIX value or a per-event VIX-adjusted value in a picture | the app draws only the committed JSON, whose per-event values are mean-adjusted | the review's `p06` scan (strict mode) and `p06b` |
| 9 | An animated page caught mid-frame | `reduced_motion="reduce"` | the re-run reproduces 18 of 21 files byte for byte (review claim 8) |

## Before you read §6: predict

1. How many of the seven hypotheses are rejected after Holm, and which one could flip on a choice that is not about
   the data?
2. Would a reader of the README's results table see that H5–H7's tests are liberal?
3. A PDF and a DOCX from the same Markdown: byte-identical on a rebuild, or not?

---

## 6. Measured results

All on 2026-10-29 in the working tree, after the review's fixes. **Timing labels provisional.**

### 6.1 The report and its numbers

<!-- numbers:milestone5-results -->
The report's headline numbers, filled in from the data by `tools/report_numbers.py` like the report itself: H1
−0.199 log points (Holm 4.1e−22); H2 +0.232 (Holm 0.0469; 0.0781 with 7
seasons); H3 and H4 not rejected (1, 1); H5–H7 not rejected (Holm 0.0511,
1, 1) with G1 sizes 9.55%, 8.10% and 16.15%; b = 0.77 [0.46, 1.07]; 40.1% of
moves beyond the expected size against a fair 42.5%. 14 robustness rows are withheld. The
report's §4 has the table and §7 every caveat.
<!-- /numbers:milestone5-results -->

### 6.2 The exports

| File | Size | How |
|---|---:|---|
| `docs/report/earnings-vol-report.md` | rendered by `tools/report_numbers.py` | 224 numbers, 4 files (report, README, PR/FAQ, this page); **2026-11-09: 464 numbers** (`--check`) |
| `docs/report/earnings-vol-report.pdf` | 768,625 B, 13 pages (`pdfinfo`); **2026-11-09: 816,866 B, 16 pages** | Chromium print-to-PDF, A4 |
| `docs/report/earnings-vol-report.docx` | 372,082 B; **2026-11-09: 378,524 B** | python-docx |

Both are under the 10 MB limit, which `build_report.py` enforces. The review checked that all headings, table rows,
images and number tokens of the Markdown appear in both (review claim 7).

### 6.3 The pictures

21 PNGs in `docs/images/`, **1,994,462 B in all** (the script's last line; **2026-11-09: 2,038,408 B** by `du -cb`, after the nine
pictures that showed pre-EDGAR numbers were re-taken): `app-<page>.png` × 11, `app-about-phone.png`,
`fig-*.png` × 6, `terrain-*.png` × 3. Full page heights at 1,280 px (the run prints them): About 2,776, Sample 2,451,
IV measures 1,698, Results 5,115, Drivers 12,844, Implied vs realised 2,202, Crush paths 2,206, Heatmap 3,231,
Architecture 3,867, 3D view 1,264, Metrics 1,594 px; the four over 3,000 px are cut there. (2026-11-09, with the
longer provisional notice: Sample 2,520, IV measures 1,721, Results 5,138, Drivers 12,867, Implied vs realised 2,225,
Crush paths 2,230, Heatmap 3,254, Architecture 3,867, 3D view 1,287, Metrics 1,594 px.)

### 6.4 The app

`MILESTONES` lists 0–5. Each navigation page belongs to exactly one milestone (a test compares the list with the
rendered navigation).

### 6.5 graphify (code layer only)

The AST pass over 382 code files (Python, TypeScript, TSX, JavaScript, shell, and four config files, the review's
probes included): **3,649 nodes, 9,313 edges, 166 communities**. The review's `p11` checked the build before the fixes
(371 files, 3,559 nodes): every edge came from the AST; the rebuild after the fixes used the same script. `graph.json`, `graph.html` and
`GRAPH_REPORT.md` are refreshed; `graph.svg` is not (12.4 MB) and is labelled as the milestone-0 render.

### 6.6 The gates

In §10.

---

## 7. Explain it back (interview questions)

1. Why render numbers from templates instead of typing them and checking them with a grep?
2. What can `prose_check` catch that comparing rendered files cannot, and what can it still not catch?
3. Why is the 473 pinned, and what would it take to derive it from committed data?
4. Why does the PDF need a build stamp when the Markdown does not?
5. The README shows H2 as rejected. What single choice, not about the data, would make it not rejected?
6. Why is "the IV fall was near-universal in direction" an observation and "the fall is predictable" a claim this
   study cannot make?

## 8. What's next, and what is not done

- **The owner's pass on the report** (its §9 questions), then a re-render and a rebuild.
- **The timing look-ups:** 42 of 473 are still open and the 50-event audit has not run (SEC EDGAR in use since
  2026-11-09, §12); every number is provisional until then.
- **Blender hero renders: not rendered, Blender unreachable (2026-10-29).** `tools/blender/event_terrain.py` has never
  run.
- **A delta review** of the §9 fixes has not run.
- **DOCX links** keep their text but not their targets (relative links would need the repository's public URL).
- **Owner decisions still open:** the binding Holm family (milestone 4 row 24), a second market factor for the common
  date component, the PR/FAQ's release date and quotes (the `⟨…⟩` placeholders are the author's to write).
- **Provenance:** the app JSON names `source_commit` ca25cdd and `results.code_commit` ends in `-dirty`; this
  milestone did not re-run the pipeline.

## 9. Fixes after review

The review ([ledger](../validation/m5-ledger.md)) refuted claims 2 and 3 and found claims 1, 5, 9 and 12 partial.
Each fix: what was wrong, the change.

- **F1 (claim 2, major): `--check` let false sentences through.** The review's p02 rendered 8 edited data sets whose
  text was false (a negative run-up "above" the baseline, "b is 0.60 … may inflate E", 365 events "inside 330–360", a
  7.00% G1 rate printed "pass", 15 + 2 + 1 + 1 summed to "20", a literal `{{H2.twoway_t}}`, ρ̄ 0.02 "spread over most
  dates", "not in doubt" beside p 0.27), and each passed `--check`. *Change:* `prose_check` has claims for each of
  them; `cross_check` compares tests.json's G1 rates and pass flags with results.parquet and the band; the
  placeholder pattern takes any key and a leftover brace fails; `check_exports` covers the PDF and DOCX. Tests: the
  parametrised `test_disagreeing_or_contradicting_data_fail_the_check`, the export and upper-case-key tests; mutants
  R12–R18.
- **F2 (claim 3): a dead link.** README linked this page before it existed. *Change:* this page.
- **F3 (claims 3, 9): the PR/FAQ corrections.** Item 7 credited the 0.2 warning line to the PR/FAQ draft; it is ADR
  0005's. Three contradicted statements were missing (BMP/KP "reported as robustness" while their H1 p-values are
  withheld; the Cboe daily subsample; quiet events "checked as thoroughly"). *Change:* item 1 and item 5 widened,
  a new item 7, item 8 credited to ADR 0005 with the β caveat.
- **F4 (claim 1): the window shown as the span.** *Change:* `sample.first_day0` and `sample.last_day0` from the events.
- **F5 (claim 12): the long pages.** About and Sample were cut at 2,400 px too. *Change:* the crop is 3,000 px.
- **F6 (claim 5): one forward-looking heading.** "Predictable in direction and roughly in size" → "near-universal in
  direction in this sample".
- **F7 (claim 3): provenance sentences.** "Every number from results.parquet and the app JSON" now names the ρ̄ output,
  the pinned 473 and the hand-typed design parameters; "before any result was computed" now says the results run
  refuses to start without the gate's report and that the order is recorded, not provable from the files.
- **Evidence after the fixes.** The review's `p02`, copied to the session's scratch folder (the original is
  untouched) with the new inputs added (this page, the exports and their stamp) and a simulated rebuild of the exports
  after each render, so that step 3 tests the prose and cross checks rather than export staleness: **0 of 8**
  contradicting scenarios render and pass `--check` (was 8 of 8); each is now stopped by the claim or cross-check
  named for it, S3 by the sample-size cross-check. The test module's mutants, re-run on a fresh scratch copy with the
  full module per mutant: **R01–R18 and R05c, 19 of 19 killed**; the app's **A1–A7, 7 of 7 killed**; every restore
  `sha256 ok=True`.
- **F8 (trivial):** the §4.2 median is named as the mean-adjusted crush; p-values keep trailing zeros (q 0.750); the
  unused `fig-implied-move.png` is now in §3.3; "3D view" is listed under milestone 0, where the page was added.

## 10. The gates (final run)

All on 2026-10-29 in the working tree, after the review's fixes.

| What | Command | Result |
|---|---|---|
| Python tests | `uv run --frozen pytest -q -p no:cacheprovider` | `648 passed, 53 warnings in 231.77s (0:03:51)` (`tests/test_report_numbers.py`, new, holds 21 of them) |
| App gate | `cd app && npm run verify` | `eslint .` clean; `Test Files  44 passed (44)`, `Tests  1894 passed (1894)`; `All files | 99.78 | 99.42 | 99.39 | 99.88` (statements, branches, functions, lines); `✓ built in 9.17s` |
| Notebooks | `uv run --frozen python tools/build_notebooks.py --check` | `OK: 5 notebooks in /home/…/notebooks are in sync with src/` |
| Data files | `uv run --frozen python tools/licensing/check_data_files.py` (and on a scratch copy with every file staged) | `clean: no raw vendor file and no oversized data file` (both) |
| Diagrams | `uv run --frozen --group diagrams python tools/diagrams/build.py docs/architecture/specs --out docs/architecture/out --check` | `ok: 5 spec(s) up to date in docs/architecture/out` |
| Numbers | `uv run --frozen python tools/report_numbers.py --check` | `ok: 4 file(s) match 224 numbers from the committed data; the PDF and DOCX were built from this Markdown; look-ups: 453 left + 20 done = 473, as pinned (local events_report.json)` |
| Mutants | a script in the session's scratch folder, full test module per mutant on a scratch copy | R01–R18 and R05c: 19 of 19 killed; A1–A7: 7 of 7 killed; every restore `sha256 ok=True` |

**2026-11-09, after the Cboe and EDGAR work and the review fixes** (same commands; the working tree): `742 passed, 61 warnings in
152.23s`; `Test Files  44 passed (44)`, `Tests  1894 passed (1894)`, coverage `99.78 / 99.42 / 99.39 / 99.88`, `✓ built in 4.71s`;
notebooks `OK: 5 notebooks … are in sync with src/`; data files `clean: no raw vendor file and no oversized data file`;
diagrams `ok: 5 spec(s) up to date`; numbers `ok: 4 file(s) match 464 numbers from the committed data; …; look-ups: 42 left +
431 done = 473, as pinned`.

## 11. The Cboe VX\* cross-check (added 2026-11-09)

ADR 0003 planned two outside checks of our 30-day IV that milestone 2 did not run: Cboe's single-stock volatility
indices (VXAPL, VXAZN, VXGOG, VXGS, VXIBM) and the vendor's `volatility_history.iv_current`. Both ran on 2026-11-09.
The bars, the alignment, the intervals and the event set were fixed in
[`docs/validation/vx-preregistration.md`](../validation/vx-preregistration.md) before the first download; the
[ledger](../validation/vx-ledger.md) holds the file hashes, the decisions the plan left open (D1–D15), the deviations
(a bootstrap axis one session short in a first run, corrected, only interval bounds moved; horizons extrapolated up to
10 sessions where the plan said "interpolate"), an erratum on bar ii (the pre-registration wrongly said ADR 0003 set no
tolerance for the slope), the exploratory analyses added after the adversarial review of 2026-11-09 and the mutants.

- **Code:** `src/earnings_vol/ingest/cboe.py` downloads the five CSVs (five requests, a generic User-Agent with no
  contact address) into `$VOL_DATA_DIR/earnings-vol-study/raw/cboe/`. `src/earnings_vol/stats/vx_crosscheck.py` holds
  the statistics as pure functions. `tools/vx_crosscheck.py` reads the local files, the committed `iv_daily`, the
  staged per-expiry ATM IVs and `iv_current` (from the private Dolt mirror only, filtered on `date` first), and writes
  `data/derived/vx_crosscheck.json`.
- **Aggregates only.** No index value per day or per event and no `iv_current` value per day is committed.
  `tools/licensing/check_data_files.py` checks the JSON's shape (no list of more than 16 items, no object of more than
  32 keys, no keys shaped like dates, at most 2,000 numbers).
- **Re-run after the timing labels change:** `uv run --frozen python tools/vx_crosscheck.py`, then
  `uv run --frozen python tools/report_numbers.py`. The runner takes seconds once the `iv_current` extract is cached;
  every statistic except bar iv reads data that the timing labels do not touch, and the fixed seed reproduces them.
  The JSON records the SHA-256 of the `events.parquet` it used, and its bar-iv caveat follows the events' timing
  status. If the new labels contradict a sentence of the templates, `report_numbers.py` names the sentence.

<!-- numbers:milestone5-vx -->
Run on 2026-11-09 by `tools/vx_crosscheck.py`; the numbers are filled in by `tools/report_numbers.py`, like the
report's. Window 2020-01-02 to 2026-10-26; 95% intervals from a moving-block bootstrap over sessions
(10,000 draws, blocks of 20).

| Company (index) | Bar i: r of one-session changes [95% interval] | Slope [95% interval] | Median spread | Largest yearly drift | Bar iii |
|---|---|---|---:|---:|:-:|
| AAPL (VXAPL) | 0.858 [0.794, 0.906] pass | 0.83 [0.78, 0.88] | 3.13 | 1.67 | pass |
| AMZN (VXAZN) | 0.838 [0.756, 0.897] pass | 0.81 [0.73, 0.88] | 2.87 | 0.95 | pass |
| GOOGL (VXGOG) | 0.778 [0.691, 0.843] **fail** | 0.77 [0.67, 0.85] | 2.64 | 0.52 | pass |
| GS (VXGS) | 0.848 [0.789, 0.894] pass | 0.79 [0.71, 0.85] | 2.38 | 1.73 | pass |
| IBM (VXIBM) | 0.668 [0.549, 0.754] **fail** | 0.66 [0.54, 0.75] | 2.09 | 1.14 | pass |
| Pooled (3,697 changes) | 0.790 [0.721, 0.842] **fail** | 0.77 [0.70, 0.83] | | | |

Bar ii was pre-registered as descriptive on a false premise (the pre-registration said ADR 0003 set no tolerance;
it did): no slope interval holds 1, the reverse regression's reciprocal is 1.09 to 1.48 by name,
and by the ADR's own reading the slope falsifier is met (3 of 5 slopes, GOOGL, GS and IBM, are below
0.8; the correlation falsifier, 2 of 5, and the crush ratio are not). The pair [slope, 1 /
reverse slope] always contains the ratio of the two standard deviations (0.93 to 0.99), so that it
holds 1 is not a test. Bar iv, the day-0 crush ratio over 34 events (pooled, provisional): 0.92
[0.87, 0.97], pass. Alignment: r = +0.035 at lag −1 and −0.038 at lag +1. Changes over longer
gaps: r = 0.879 [0.843, 0.909] (2,351 changes). `volatility_history.iv_current`: maturity
21 sessions (median |difference| 0.62 vol points); r with the index 0.839
[0.763, 0.892].
<!-- /numbers:milestone5-vx -->

**What it says.** The level check (bar iii) passes for every name: the index sits above our IV on most days and in the median,
as a VIX-method index built from the whole strip should. It passes the pre-registered rule, but the rule has little
power: GS's yearly medians step from about 3.8–4.1 vol points (2020–22) to about 1.7–2.1 (2023–26), a ~2 vol-point step
that passes only because the all-years median sits between the two levels. The day-0 crush
ratio (bar iv) passes. The correlation of daily changes (bar i) passes for AAPL, AMZN and GS and fails for GOOGL, IBM
and the pooled sample, and every slope is below 1; by ADR 0003's own reading (which the pre-registration missed) the
slope falsifier is met, for GOOGL, GS and IBM, 3 of 5. The low daily slopes are consistent with being largely a clock
effect (Cboe's calendar-day clock against our session clock across weekends): they shrink at longer horizons, except
for IBM, which stays below 1 (exploratory, not proof). `iv_current` behaves like a 30-calendar-day IV, which shows up as
about 21 sessions on our grid.

**Limits.**

- **The bar-i split is not sharp.** The verdict uses the point estimate, as pre-registered; only IBM's interval lies
  wholly below 0.8.
- **Whose noise?** The check cannot say whether the noise is in our series, in the index, or in both. `iv_current`
  tracks the index a little more closely than ours does, with overlapping intervals.
- **Different instruments.** The index uses the whole out-of-the-money strip, so a change in skew moves it and not an
  ATM IV. VXGOG is on GOOG; our universe holds GOOGL (noted in the pre-registration, not corrected).
- **Bar iv is provisional and pooled.** Day 0 rested on the calendar's timing labels for every one of its events
  until the SEC EDGAR look-ups ran (§12); since 2026-11-09, 32 of its 34 events have an EDGAR-confirmed label and 2
  (GS next to Columbus Day) keep the calendar's, and the ratio did not change. There are too few events per name for
  a per-name ratio.
- **The maturity is identified among the horizons we can build.** No listed expiry reaches 63 sessions, so that
  horizon has no value; the minimum at 21 sessions is interior, so it does not rest on the grid's edge.
- **Whether the results meet ADR 0003's "How we'll know it's wrong"** (the slope falsifier is met, the correlation and
  crush-ratio falsifiers are not) is an owner question (report §9, question 9). Nothing in the pipeline changed because of this check.

## 12. SEC EDGAR timing labels (added 2026-11-09)

ADR 0002 §3 makes the acceptance time of each company's Item 2.02 8-K the timing source. The owner accepted it on
2026-10-28 and set the contact string on 2026-11-09; the same day the owner chose to switch it on
(`params.yaml` `timing.edgar: true`). The [EDGAR ledger](../validation/edgar-ledger.md) holds the evidence, the
decisions (D1–D15) and the mutants; the probes are in `docs/validation/probes/edgar/`.

- **What was fetched.** 186 requests to `data.sec.gov/submissions/` (about 3.4 a second), the contact set only in the
  command: 51 submissions files and 135 extra pages (72.8 MB), every company back before 2020-01-01. XOM's filings
  before July 2026 are under its predecessor CIK, read with it (`data/manual/edgar_predecessor_ciks.csv`). The events
  stage reads only this local cache.
- **The time zone.** `acceptanceDateTime` is a UTC instant. Read as UTC it agrees with all 20 press-release look-ups,
  with 1,273 of 1,306 calendar labels, with EDGAR's 17:30 filing-date cut-off (4,444 of 4,444 earlier acceptances on
  the same date) and with EDGAR's 06:00–22:00 hours (0.08% outside). Read as New York wall time it puts all 11
  before-open releases of the 20 inside the session, 20% of all filings outside EDGAR's hours, and moves every
  company's median filing time by about an hour between summer and winter. `edgar.parse_acceptance` refuses any
  other format.
- **What changed in the labels.** Of the 473 look-ups ADR 0002 requires, 20 rest on press releases (kept as they were;
  EDGAR agrees with all 20), 405 are `confirmed` by an 8-K and 6 NULL labels are `inferred` from one (all AMC). 42
  stay open with the calendar's label: no Item 2.02 8-K near the date 26 (23 BRK.B, which releases on Saturdays and
  files days later), an EDGAR-closed day in the window 11, the 8-K on another date 4, the 8-K against the calendar's
  label 1 (TXN 2024-10-22). 37 EDGAR labels that the price gap questions wait for a press-release check.
- **What changed in the results.** No event's day 0 moved; 6 `coarse` events (IBM, INTC and four ORCL) gained one.
  Every sample count, every primary and robustness row, every G1 rate and every VX\* bar is the same as before.
  13 exploratory regression rows moved slightly, because the 6 new day 0s enter the earnings-surprise history and
  the coarse driver model. The before → after table is in the ledger, §10.
- **Coverage.** An Item 2.02 8-K on D−1…D+1 for 98.1% of `daily` events (361 of 368): the milestone-1 criterion
  (95%) is met.

**Limits.**

- **Still provisional.** `timing.lookups_complete` stays false: 42 look-ups are open, and the ADR's audit of 50
  `confirmed` EDGAR labels against press releases has not run. The 20 press releases that agree with EDGAR were not
  a random sample.
- **`inferred` rests on the 8-K alone.** An 8-K filed hours after a before-open release would read AMC. The 20
  look-ups put the 8-K within −18 to +13 minutes of the stated release time, but 6 events are too few to measure the
  risk.
- **EDGAR's closed days are measured, not known in advance.** Six sessions with no acceptance in any of the 51 CIKs
  (Christmas Eves, 2021-06-18, 2021-12-31, 2025-12-26) are added to Columbus Day and Veterans Day; a future one-off
  closure has to be added when the data are refreshed.
- **Scope.** EDGAR labels only the look-ups the default rule requires. Whether it should also label the `coarse`
  events the rule leaves alone, and whether to look up BRK.B's Saturday releases by hand, are owner questions
  (report §9, question 6).
- **Screenshots.** The About shots were re-taken first. The nine pictures that still showed pre-EDGAR numbers were
  re-taken afterwards with `tools/screenshots.py`: the sample funnel (`app-sample.png`, `fig-funnel.png`, now 1,326
  events at "day 0 can be placed") and the pages with the provisional notice (`app-iv.png`, `app-results.png`,
  `app-drivers.png`, `app-implied.png`, `app-paths.png`, `app-heatmap.png`, `app-3d.png`, now 431 look-ups done).

## Appendix: what I ran

```
uv add --group report --bounds exact python-docx markdown-it-py      # python-docx 1.2.0, markdown-it-py 4.2.0
uv run --frozen python tools/report_numbers.py                        # render; then --check
uv run --frozen --with playwright==1.64.1 python tools/screenshots.py
uv run --frozen --group report --with playwright==1.64.1 python tools/build_report.py
PYTHONHASHSEED=0 <graphify python> <scratch>/graph_code_only.py . <scratch>/labels.json   # AST pass, code files only
PYTHONHASHSEED=0 graphify export html --labels <scratch>/labels.json
cp graphify-out/{graph.json,graph.html,GRAPH_REPORT.md} docs/architecture/graph/

# §12, SEC EDGAR (2026-11-09); the contact string only in the fetch command, never in a file
SEC_EDGAR_USER_AGENT="<name> <email>" uv run --frozen python -m earnings_vol.ingest.edgar
uv run --frozen python -m earnings_vol.events.run                     # params timing.edgar: true
uv run --frozen python -m earnings_vol.measures.run
uv run --frozen python -m earnings_vol.panel.run
uv run --frozen python -m earnings_vol.stats.run --g1                 # 265 s on 20 workers
uv run --frozen python -m earnings_vol.stats.run
uv run --frozen python tools/export_app_data.py
uv run --frozen python tools/vx_crosscheck.py
uv run --frozen python tools/report_numbers.py
uv run --frozen --with playwright==1.64.1 python tools/screenshots.py --out <scratch>   # only app-about*.png copied
uv run --frozen --group report --with playwright==1.64.1 python tools/build_report.py
```

### 9.1 After the independent re-measurement (2026-10-29)

The verifier agreed with every number it recomputed (README table, 35 report and PR/FAQ numbers, sizes, links,
screenshots). It found two things outside the claims, both fixed before the commit:

- **The PDF carried five `file:///home/…` links** (relative links resolved against the local build file), dead on
  any other machine and naming the local user folder. `tools/build_report.py` now points every relative link at its
  page in the public repository (`public_href`, tested in `tests/test_build_report.py`, 3 mutants killed). The
  rebuilt PDF has 0 `file:///` links.
- **"Median realised |move| 4.4%"** sat under the 332-event row but is the median over all 336 events (4.5% over
  the 332). The label now says "all 336 events".
