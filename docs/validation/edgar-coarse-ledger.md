route: rows 2, 10 | primary: Tier 0 gates (events-stage tests, full pytest, report_numbers --check) + one hand mutant per new test (7 of 7 killed) | complement: verifier (Sonnet) re-measured 11 claim groups of §4–§6, before-figures from the committed data/derived/events.parquet: 11 of 11 AGREE | not-run: adversarial (no T3 change and no number for a spend or a stake; the switch is reversible by setting it false), EGV (no API-existence claim; the EDGAR reader is unchanged) | stop: met for the events stage; the full suite has 9 provenance failures until the rebuild (§6)

# SEC EDGAR labels the `coarse` sample: switch, tests and measured effect

- **Date:** 2026-11-17. **Scope:** ADR 0002 §3, source 1, applied to the `coarse` events that the default rule leaves
  `not_checked` (the open question of [edgar-ledger.md](edgar-ledger.md) §9 item 3 and D1).
- **Owner decision, 2026-11-17 (relayed):** "Label the 812 coarse events with EDGAR and amend ADR 0002. A
  contradiction waits for its press-release check before any day 0 moves."
- **What changed:**
  - `params.yaml`, timing block: `edgar_coarse: true`, with the decision in its comment.
  - `src/earnings_vol/events/run.py`: `coarse_scope()` (the `coarse` events the first pass leaves `not_checked`);
    `build()` adds them to EDGAR's scope when `timing.edgar` and `timing.edgar_coarse` are both true; `build()`
    returns `edgar_coarse` and `edgar_press_release_checks`; `edgar_report()` gains `coarse` and
    `press_release_checks`.
  - `src/earnings_vol/events/timing.py`: `EDGAR_WAIT_FOR_RELEASE = ("contradicts", "other_date")`; header comment.
  - `tests/test_edgar_timing.py`: 5 new tests, a made-up company with coarse releases; `inputs()` takes a calendar
    and an EPS history.
  - ADR 0002: a sentence in Status and the note "SEC EDGAR also labels the `coarse` sample, 2026-11-17".
- **Not changed, on purpose:** `resolve_edgar()` (its rules), `events.build_events()` (a press release still decides
  where one was read), the build invariant (`lookup_reasons`, `lookup_violations`), `data/derived/`, the stage
  directories and every downstream stage. No stage was run; no file under `data/` or `app/` was written.
- **No network.** The EDGAR files were read from `$VOL_DATA_DIR/earnings-vol-study/raw/edgar/` through
  `run.edgar_loader` (`ingest.edgar.cached_item_202`, which makes no request). No request was made to sec.gov or
  data.sec.gov. No `dolt` command was run; the calendar came from the parquet extracts in `cache/dolt/`.

## 1. What the switch does

| | `edgar_coarse: false` (or absent) | `edgar_coarse: true` |
|---|---|---|
| EDGAR is read for | the default rule's open look-ups and the press-release events (2026-11-09, D1) | the same, **plus every `coarse` event that the first pass leaves `not_checked`** |
| Rules | `resolve_edgar`, ledger §5 D2–D15 | the same |
| `confirmed` / `inferred` | set the label (`timing_source = edgar`) | the same |
| `contradicts`, `other_date` | the event keeps the calendar label and day 0, `not_checked` | the same, and the event is listed in `edgar_press_release_checks` |
| `no_8k`, `edgar_holiday`, `several_8k`, `during_session` | `not_checked`, calendar label | the same; a `coarse` event that stays `not_checked` is allowed (the build invariant is unchanged) |
| An event with a press-release row | the release decides; the 8-K is recorded | the same |

`edgar_press_release_checks` holds every consulted event whose outcome is `contradicts` or `other_date`, in all
samples, so with the switch off it lists the 5 such required look-ups of 2026-11-09. `edgar_coarse` has no effect
while `timing.edgar` is false: EDGAR is then not read at all.

## 2. Tests (RED, then GREEN, then one mutant each)

The tests are in `tests/test_edgar_timing.py`, section "coarse". The world: one made-up company with a release
before the coarse sample (2020-02-13, sample `none`), five coarse releases (2023-04-27 AMC with an agreeing 8-K;
2023-07-27 BMO with an 8-K at 16:05; 2023-10-26 AMC with an 8-K the next morning; 2024-01-25 AMC with no 8-K;
2024-04-25 with no label), one mixed and two daily. No prices, so no gap trigger.

| Test | Shows (task item) | RED on f5904a9 |
|---|---|---|
| `test_coarse_events_with_a_matching_8k_are_confirmed_by_edgar` | (a) `confirmed`, `edgar`; the release before coarse is not read; violations unchanged | `'not_checked' != 'confirmed'` |
| `test_a_coarse_contradiction_keeps_the_calendar_label_and_waits_for_a_press_release` | (b) label, source and day 0 as without EDGAR; listed with the other-date case | `assert None == 'contradicts'` (not consulted) |
| `test_the_coarse_switch_leaves_daily_and_mixed_as_they_were` | (c) daily and mixed rows, EPS, violations and gap checks equal with the switch on and off; the switch changes exactly the three labelled coarse rows that have an 8-K | `assert [] == ['XYZ:2023-04...']` (the switch did nothing) |
| `test_the_coarse_switch_off_gives_the_old_output` | (d) off and absent give equal frames and lists; the rows are the old ones; only the old look-ups are read | `KeyError: 'edgar_press_release_checks'` |
| `test_a_press_release_still_decides_in_coarse` | a press release decides over a confirming or a contradicting 8-K | `KeyError: 'edgar_press_release_checks'` |

The RED of (d) and of the last test is the new key alone. In the last test every other assertion passed on
f5904a9; in (d) the frame comparisons before the key passed, and the pinned rows after it were not reached. Both
describe old behaviour and are guards; the mutants below show that each one fails when its behaviour breaks.

Command and output (RED, 2026-11-17, code of f5904a9 with the new tests):

```
.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_edgar_timing.py -k coarse
5 failed, 29 deselected, 4 warnings in 1.15s
```

GREEN after the change: `tests/test_edgar_timing.py` **34 passed** (29 old, 5 new).

**Mutants** (`mutants.py`, on a scratch copy of `src/`, `tests/`, `params.yaml`, `pyproject.toml` and
`data/manual/`; pytest's `pythonpath = ["src"]` imports the copy; each mutant applied alone, the named test run,
the file restored and its SHA-256 compared). Baseline of the copy: 34 passed.

| # | Mutant | Test | Result |
|---|---|---|---|
| MC1 | `coarse_scope` returns no event | (a) | killed (1 failed); SHA equal |
| MC2 | `coarse_scope` without its sample filter (every `not_checked` event) | (a) | killed; SHA equal |
| MC3 | `EDGAR_WAIT_FOR_RELEASE = ("other_date",)` | (b) | killed; SHA equal |
| MC4 | `resolve_edgar` takes the 8-K's label on a contradiction (status stays `not_checked`) | (b) | killed; SHA equal |
| MC5 | `build` reads `coarse_scope` instead of the default rule's look-ups, not as well as them | (c) | killed; SHA equal |
| MC6 | `build` ignores `edgar_coarse: false` | (d) | killed; SHA equal |
| MC7 | `build_events` lets EDGAR decide where a press release was read | press release | killed; SHA equal |

**7 of 7 killed.**

## 3. How the effect was measured

Four builds of the events layer, in memory, each saved to `$VOL_DATA_DIR/earnings-vol-study/cache/edgar-coarse/<tag>/`
(`out.pkl`: every table and list of `run.build`; `report.json`: `run.report`). Nothing was written to `data/derived/`
or to `cache/stage/`.

| Tag | Code | `timing.edgar_coarse` | params hash (first 16) |
|---|---|---|---|
| `before` | f5904a9 (before this change) | absent | `d23d18972bf0c8d4` (the committed stage) |
| `off` | this change | false (params copy) | `b9ab6c28f0bc281e` |
| `absent` | this change | key removed (params copy) | `d23d18972bf0c8d4` |
| `on` | this change | true (`params.yaml` as committed now) | `d51877f495f7ae67` |

```
cd ~/dev/earnings-vol-study
.venv/bin/python -I build_tag.py before            # run before the code change
.venv/bin/python -I build_tag.py on
.venv/bin/python -I build_tag.py off false
.venv/bin/python -I build_tag.py absent absent
.venv/bin/python -I compare.py                     # §4 tables 1-8
.venv/bin/python -I unresolved.py                  # §4.3
.venv/bin/python -I terciles.py                    # §4.6
```

The scripts are in the appendix and in `cache/edgar-coarse/probe/`; their outputs are in `cache/edgar-coarse/*.out`.
They print counts, dates and EDGAR times only, never a price or a gap value. The `before` report equals the
committed stage report `cache/stage/d23d18972bf0c8d4/events_report.json` (compared key by key).

## 4. Measured outcomes

### 4.1 The switch off is the old output

`off == before` and `absent == before`: every table (`session`, `market_daily`, `security`, `ticker_alias`, `events`,
`eps`, `timing_check`) equal by `pandas.testing.assert_frame_equal`, and `lookup_violations`, `edgar_outcome`,
`edgar_pending_gap_checks`, `edgar_on` equal. The reports are equal except two new keys in `edgar`: `coarse` and
`press_release_checks`.

### 4.2 The newly consulted events

Consulted: 473 before, 1,285 on; **812 new, all `coarse`**, none lost. Before, all 812 were `not_checked` with a
calendar label (AMC 414, BMO 398). No event consulted before changed its outcome.

| Outcome of the 812 new | coarse | daily | mixed | All |
|---|---:|---:|---:|---:|
| `confirmed` (EDGAR) | 798 | 0 | 0 | **798** |
| `inferred` (EDGAR) | 0 | 0 | 0 | 0 |
| unresolved: `no_8k` | 6 | 0 | 0 | 6 |
| unresolved: `edgar_holiday` | 5 | 0 | 0 | 5 |
| unresolved: `contradicts` | 1 | 0 | 0 | 1 |
| unresolved: `other_date` | 1 | 0 | 0 | 1 |
| unresolved: `during_session` | 1 | 0 | 0 | 1 |
| unresolved: `several_8k` | 0 | 0 | 0 | 0 |
| **All** | 812 | 0 | 0 | **812** |

Resolved by label: AMC 408, BMO 390. All EDGAR outcomes over the 1,285 consulted (stage report `edgar.outcome`):
confirmed 1,203, inferred 6, press_release 20, no_8k 32, edgar_holiday 16, other_date 5, contradicts 2,
during_session 1.

### 4.3 The 14 that stay `not_checked`

| Outcome | Event | Label | 8-K accepted (New York) |
|---|---|---|---|
| `contradicts` | AMD 2020-10-27 | AMC | 2020-10-27 Tue 06:34 |
| `other_date` | COST 2022-09-22 | AMC | 2022-09-23 Fri 13:38 |
| `during_session` | PM 2021-02-04 | BMO | 2021-02-04 Thu 10:32 |
| `edgar_holiday` | JNJ 2020-10-13, JPM 2020-10-13 (Columbus Day) | BMO | 07:12, 06:45 |
| `edgar_holiday` | AMAT, CSCO, PLTR 2020-11-12 (Veterans Day 11-11) | AMC | 16:04, 16:09, 16:16 |
| `no_8k` | BRK.B 2020-05-02, 2021-02-27, 2021-05-01, 2022-04-30 (Saturdays) | BMO | none on D−1 … D+1 |
| `no_8k` | GE 2020-04-29 | BMO | none |
| `no_8k` | AMAT 2024-05-16 | AMC | none |

Every EDGAR-holiday 8-K time agrees with its calendar label, as in 2026-11-09.

### 4.4 Day 0

**Moved 0, lost 0, newly defined 0; day −1 changed 0.** `events` differs from `before` in four columns only, all on
`coarse` rows: `timing_status` and `timing_source` (798 rows), `edgar_accession` and `edgar_accepted_utc` (806 rows:
the 798 plus the 8 unresolved events that have an 8-K). `eps`, `timing_check`, `session`, `market_daily`, `security`
and `ticker_alias` are equal. `lookup_violations` is equal (42).

### 4.5 Press-release checks, gap checks, exclusions and samples

`edgar_press_release_checks` (on): **7**. If a release agrees with the 8-K:

| Event | Sample | Outcome | Label | 8-K | Day 0 now | Day 0 then |
|---|---|---|---|---|---|---|
| **AMD 2020-10-27** (new) | coarse | contradicts | AMC | 2020-10-27 06:34, BMO | 2020-10-28 | **2020-10-27** |
| **COST 2022-09-22** (new) | coarse | other_date | AMC | 2022-09-23 13:38, in the session | 2022-09-23 | a hand reading decides |
| META 2020-07-29 | coarse | other_date | AMC | 2020-07-30 19:18, AMC | 2020-07-30 | 2020-07-31 |
| MS 2020-04-15 | coarse | other_date | NULL | 2020-04-16 07:16, BMO | none | 2020-04-16 |
| ORCL 2020-09-09 | coarse | other_date | NULL | 2020-09-10 16:16, AMC | none | 2020-09-11 |
| TXN 2024-10-22 | mixed | contradicts | BMO | 2024-10-22 16:03, AMC | 2024-10-22 | 2024-10-23 |
| WFC 2022-10-13 | coarse | other_date | NULL | 2022-10-14 06:45, BMO | none | 2022-10-14 |

The last five were already open required look-ups (ledger of 2026-11-09, §6).

| | before | on |
|---|---:|---:|
| `edgar_pending_gap_checks` (job 1) | 37 | **37** (none added, none removed) |
| `timing_not_checked` exclusions | 26 | **26** |
| Exclusions: none / duplicate_row / outside_samples / timing_not_checked | 1,265 / 1 / 61 / 26 | the same |
| Events by sample: coarse / daily / mixed / none | 868 / 368 / 49 / 68 | the same |
| Open required look-ups (`lookup_violations`) | 42 | 42 |
| `timing_status` confirmed / corrected / date_corrected / inferred / not_checked | 421 / 2 / 1 / 7 / 922 | **1,219** / 2 / 1 / 7 / **124** |
| `timing_source` press_release / edgar / calendar / none | 20 / 411 / 892 / 30 | 20 / **1,209** / **94** / 30 |
| `coarse` `not_checked` | 833 | **35** (21 open required look-ups and the 14 of §4.3) |
| Events with `timing_status != not_checked` (the funnel's `lookups.n_done`) | 431 | **1,229** |

Why job 1 found nothing new: a newly `confirmed` event keeps its calendar label, and its gap did not trigger on that
label (else the default rule would have required it already). The outside flag does not depend on the label.

The 61 labelled `not_checked` events in sample `none` are not read: none can enter a sample
(`timing.can_enter_sample`), measured.

### 4.6 The coarse selection by move

Over the 640 `coarse` events with an `abs_move_cand_max` (from `cache/stage/d23d18972bf0c8d4/event_iv.parquet`; day 0
is the same in both builds), by tercile, lowest to highest move, as `export.funnel.move_terciles` cuts them:

| | t1 | t2 | t3 |
|---|---:|---:|---:|
| `not_checked`, before | 211 | 204 | 205 |
| `not_checked`, on | 8 | 7 | 6 |
| of which on: no_8k / edgar_holiday / other_date / contradicts / during_session | 7 / 1 / 0 / 0 / 0 | 6 / 0 / 0 / 0 / 1 | 1 / 1 / 3 / 1 / 0 |

## 5. Paths that mix samples, and what can move

Each path below reads only day 0, day −1, the sample, the exclusion reason, `announce_date_used`, `timing_used` or the
EPS links. All of them are identical in the two builds (§4.4), so none of them changes:

- **`sue_hist`** (`panel/regressors.py`): a security's previous 8 price-scaled surprises (`sue_prev`), in day-0
  order, across samples; a coarse event can enter a daily event's history. Inputs: day 0, `announce_date_used`,
  the EPS link, `price_ref` at the pre session. Unchanged.
- **Winsorisation** of |surprise| (1% / 99%, per sample) and **VIX terciles** (per sample, at day −1): the event set
  per sample and day −1 are unchanged.
- **Baselines** (`panel/baseline.py`, `export/funnel.py`): neighbouring events' zones from their day 0, orphan zones
  from the EPS links. Unchanged.
- **Bar iv of the VX\* check**: the primary (daily) sample only; its label counts do not change.

No module under `measures/`, `panel/` or `stats/` reads `timing_status`, `timing_source`, `edgar_accession` or
`edgar_accepted_utc`, except `stats/vx_crosscheck.bar_iv_provisional` (a sentence about the bar-iv events, which are
daily). **So no primary and no exploratory row of `results` can move with this change**, unlike 2026-11-09, when 6
newly dated coarse events moved 13 exploratory rows through `sue_hist`, the coarse winsorisation and the VIX terciles.
At the rebuild every row's `params_hash` changes (`d23d18972bf0c8d4` → `d51877f495f7ae67`).

**What will change at the rebuild** (not done here):

- The label counts: `sample_funnel.json` (`timing_status_counts`, `timing_status_by_sample`, `by_move_tercile`
  status counts, `lookups.n_done` 431 → 1,229), the app's look-up count (`export/event_views.py`), the report's
  `timing.*` and `lookups.*` numbers.
- **`tools/report_numbers.py` will fail its checks.** It reads `lookups.n_done` as "required look-ups done": it
  checks `473 − n_done` against the pinned open reasons (42) and `n_done` against press releases + EDGAR, and
  `--check` compares the stage report's `edgar.outcome` (all unresolved outcomes, now 56 rather than 42) with
  `LOOKUPS_OPEN_BY_REASON`. With the switch on, `n_done` counts the 798 coarse labels too, so `lookups.left` would be
  473 − 1,229. The pins and the meaning of `n_done` (required look-ups done, 431, against documented labels, 1,229)
  need a decision before or at the rebuild. This change does not touch `tools/` or `export/`.
- **If a press release later confirms an 8-K** of §4.5: AMD's day 0 moves within `coarse`. Its surprise enters
  the `sue_hist` of the next 8 AMD releases with a surprise (from 2021-01-27); AMD's first non-coarse release
  (2024-10-30, mixed) is the 15th after it, so in practice only coarse rows could move. The other cases are as in
  the 2026-11-09 ledger.

## 6. Gates (2026-11-17, after the last code edit)

| Gate | Command | Printed |
|---|---|---|
| Events-stage tests | `.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_edgar_timing.py tests/test_ingest_sources.py tests/test_events_run.py tests/test_timing.py tests/test_events.py tests/test_layering.py tests/test_calendar.py tests/test_eps.py tests/test_events_eps_link.py` | `255 passed, 32 warnings in 2.22s` |
| Full suite | `.venv/bin/python -m pytest -q -p no:cacheprovider` | `9 failed, 738 passed, 61 warnings in 68.85s` |
| Numbers | `.venv/bin/python tools/report_numbers.py --check` | `ok: 4 file(s) match 464 numbers from the committed data; …; look-ups: 42 left + 431 done = 473; open by reason and 37 gap-questioned, as pinned (local events_report.json)` |

**The 9 failures** are all `tests/test_export_app_data.py::test_committed_json_matches_what_the_exporter_writes`
(`meta`, `sample_funnel`, `iv_measures`, `tests`, `event_paths`, `terrain`, `heatmap`, `drivers`,
`implied_vs_realised`). In each, the only differing item is `provenance.params_hash`: the committed app JSON says
`d23d18972bf0c8d4…`, the exporter now computes `d51877f495f7ae67…` from `params.yaml`. That is the new
`edgar_coarse` key: with the key removed the hash is `d23d18972bf0c8d4` again (§3, tag `absent`). They clear when the
rebuild re-exports the app data; `data/derived/` and `app/` were not touched here. `report_numbers --check` still
passes because it reads the stage of the committed hash.

## 7. Open, and least sure

1. The press-release checks of the 7 listed events (2 new: AMD 2020-10-27, COST 2022-09-22).
2. The 50-event audit of `confirmed` EDGAR labels (ADR 0002 §3, milestone-1 check) has not run. It was defined on the
   daily sample; whether it should also sample the 798 new coarse labels is not decided.
3. `not_checked` now covers, in `coarse` too, events that were read on EDGAR and not settled, not only events "never
   looked up" (ADR 0002 status table; data model `timing_status`). The ADR note lists the passages to rewrite.
4. BRK.B's Saturday releases: 4 more rows (coarse) stay `no_8k`; the owner's second question of 2026-11-09 item 7 is
   still open. *Answered 2026-11-17; see §8.*
5. A verifier re-measured §4–§6 on 2026-11-17 (11 claim groups, all AGREE; the before-figures from the committed
   `data/derived/events.parquet` and the committed stage report, the on-figures from the saved build). It did not
   make a second fresh build.

## 8. After the rebuild (2026-11-17): Berkshire's releases, the pins and the stage report

The owner's third answer of 2026-11-17 timed BRK.B from its own dated releases (ADR 0002, note "Berkshire Hathaway
timed from its own releases"). That answers §7 item 4. The rebuild ran the events stage with both changes, then every
stage after it, in the order of the README (stage `d51877f495f7ae67`).

- **Labels.** 26 BRK.B rows in `data/manual/press_release_checks.csv` (one per release, BMO). The calendar's Friday
  row of 2024-11-01, a duplicate of the Saturday 2024-11-02 release, has no check row. Statuses over all events:
  confirmed 1,232, corrected 2, date_corrected 14, inferred 7, not_checked 98. Sources: EDGAR 1,209, press release 46,
  calendar 84, none 14. So `sample_funnel.json` `lookups.n_done` is 1,255 (§5 predicted 1,229 for this step
  alone; the 26 BRK.B labels make the rest).
- **Required look-ups, measured, not derived.** `events/run.py` now writes `required_lookups` to the stage report:
  every event that ADR 0002 §3's default rule requires to be looked up, whatever its status, with
  `done_by_source`. `lookup_violations` gains `by_edgar_outcome`. Measured: 473 required, 453 done (42 press
  release, 411 EDGAR), 20 open (no 8-K 4, EDGAR holiday 11, other date 4, against the label 1; by sample coarse 7,
  daily 10, mixed 3). (*Correction, 2026-11-17, §9: the duplicate row BRK.B:2024-11-01 was counted; 472 required and
  19 open, no 8-K 3, mixed 2.*)
- **`tools/report_numbers.py`** (the decision §5 asked for): `lookups.done`, `.press_release`, `.edgar` and `.left`
  now count the required look-ups, pinned from the stage report (`LOOKUPS_DONE_BY_SOURCE`,
  `LOOKUPS_OPEN_BY_REASON`); new keys `lookups.documented` (every label on a document, `n_done`, 1,255),
  `lookups.extra` (1,255 − 453 = 802), `lookups.all_press_release` and `lookups.all_edgar` (from `events.parquet`) and
  `lookups.utc_reference` (the 20 press releases of the UTC check). The script refuses pins that do not add up
  (required = done by source + open) and a source pinned above its labels in `events.parquet`; `--check`
  compares the pins with `required_lookups` and `lookup_violations.by_edgar_outcome` of the local stage report.
  Printed: `look-ups: 20 left + 453 done = 473; done by source, open by reason and 37 gap-questioned, as pinned
  (local events_report.json)`. (*Since the §9 fix: 19 left + 453 done = 472.*)
- **What moved downstream.** No non-BRK.B day 0, status or sample changed. Two daily-sample BRK.B events gained a
  day 0, so the primary sample is 349 events (was 347), and every statistic was re-run. H5's Holm p went from 0.0511
  to 0.0469; the report says why that rejection is not trusted (§4.5 there).

## 9. Validation of the rebuild (2026-11-17)

route: row 6 (result numbers to the owner) | primary: the rebuild and its Tier 0 gates | verifier (Sonnet): 12 of 12
rebuilt numbers AGREE | adversarial (Opus): claims 1, 2, 3 and 5 survive, claim 4 (the look-up counts) is partly
correct; every finding acted on below was reproduced here first | stop: each changed number re-measured once and
attacked once

The adversarial pass attacked five claims: the sample change, H5's Holm p, the G1 rate moves, the look-up counts and
the order of the 2026 snapshots around day 0. Its scripts are in the session scratchpad, not in the repository.

1. **Fixed: a duplicate calendar row was counted as an open look-up.** `events.required_lookups` read only dates
   (`timing.can_enter_sample`), so BRK.B:2024-11-01, the `duplicate_row` beside the Saturday 2024-11-02 release, was a
   required look-up, open, with no 8-K and a NULL label. A duplicate row never enters a sample, so ADR 0002 §3 does
   not require its look-up. Reproduced here first: the new test `test_a_duplicate_row_needs_no_lookup` failed on the
   old code (RED), and so did the extended `test_events_timing_counts_labels_and_the_open_events_without_one`
   (6, 4, 3 against 6, 4, 2). After the fix both pass. The events stage was re-run. All 30 derived and stage tables
   are byte-identical (SHA-256 before and after). Only the stage report moved:
   - required 473 → 472, open 20 → 19;
   - by EDGAR outcome, no 8-K 4 → 3; by reason, NULL label 7 → 6 and daily-or-mixed era 13 → 12; by sample, mixed
     3 → 2;
   - EDGAR consulted 1,285 → 1,284 and its `no_8k` outcomes 6 → 5 (the duplicate row is no longer sent to EDGAR).

   Done look-ups stay 453 (42 press release, 411 EDGAR). No result changes.
2. **Added: H5's rejection does not rest on H2's season floor.** With H2's raw p taken from its 7-season cut
   (0.0156), H5 sorts second and its Holm p is 0.0473, still below 5%. The report now prints this from the data
   (`h5.p_holm_h2cut`), and `--check` fails if it goes above 0.05.
3. **Exploratory, not in the report: a size-corrected reading of H5.** This is not pre-registered. ADR 0005 §5
   forbids a substitute statistic, so it is a sensitivity only. G1's calibrated null design for H5, as the stats run
   builds it:
   - Measured here, 2,000 replications per seed block (`h5_null_tail.py`, 8 s). The production block reproduces the
     committed size, 8.45%. Two fresh blocks (offsets 40 and 41) give a size of 8.40%, a null 95% critical |t| of
     2.280 (2.010 for t₄₉), and a null tail of 2.08% (83 of 4,000) at H5's observed |t| of 2.7705, against 0.79%
     nominal.
   - The reviewer's figures, 12,000 replications on other blocks: 2.06%, critical |t| 2.293.
   - With a p of 0.0208, Holm over H1–H7 gives H5 0.104 (5 × 0.0208), so H5 is not rejected.
4. **The G1 rate moves are Monte Carlo noise** (the reviewer's measurement, not re-measured here). The seeds are
   unchanged. `g1.generate` draws day-0 jumps per firm, so BRK.B's two extra day-0s shift the random stream, and the
   old and new H5 t per replication correlate at 0.175. On 5 other seed blocks, H5's size is 7.55–9.60% and H6's
   7.00–8.10%. The production H6, 6.75%, is a low draw above the 6.3% bar. H7's calibrated firm sd went from 0
   (clipped) to 0.273 on the two events. No G1 verdict changes.
5. **The 2026 crush is smaller.** Exploratory, measured here on `crush_mean_adj`, daily sample: the 2026 mean is
   −0.167 (155 events) and the 2025 mean −0.224 (190 events). Within firm (50 firms with both years), 2026 minus
   2025 is +0.0546 (se 0.0099), and the crush is smaller in 2026 for 80% of firms. The reviewer finds that most of this
   follows the smaller day −1 event variance, with a rest of +0.020 ± 0.015; that split was not re-measured here.
   The pooled H1 mixes 155 events from the 2026 intraday-snapshot period. This belongs to the open question of
   report §9 Q9.
6. **Order of the 2026 snapshots** (the reviewer's measurement). On the 102 events of 2026 with an overnight gap
   above 3%, no day −1 snapshot sits past halfway from the pre-news close to the post-news open. The day-0 snapshot
   is inside day 0's high-low range for every AMC event and for all but one BMO event (PG 2026-07-29, inside on raw
   prices). So the intraday timing does not put a snapshot on the wrong side of the news.

## Appendix: the probe scripts

`build_tag.py`:

```python
# Build the events layer in memory and save it under cache/edgar-coarse/<tag>/.
# Usage: python -I build_tag.py <tag> [true|false|absent]
#   the second argument sets params timing.edgar_coarse in a params copy
#   (absent: the key removed; omitted: params.yaml as it is).
# Writes pickles (exact frames, own files) and report.json. Never writes data/derived/.
import json
import pickle
import sys

import yaml

from earnings_vol import config, params as params_mod
from earnings_vol.events import run
from earnings_vol.ingest import prices

tag = sys.argv[1]
flag = sys.argv[2] if len(sys.argv) > 2 else None
out_dir = config.cache_dir() / "edgar-coarse" / tag
out_dir.mkdir(parents=True, exist_ok=True)
if flag is None:
    p = params_mod.load()
else:
    raw = yaml.safe_load(params_mod.DEFAULT_PATH.read_text(encoding="utf-8"))
    if flag == "absent":
        raw["timing"].pop("edgar_coarse", None)
    else:
        raw["timing"]["edgar_coarse"] = flag == "true"
    path = out_dir / "params.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    p = params_mod.load(path)
inp = run.load_inputs(p)
raw_dir = config.raw_dir()
out = run.build(p, inp, lambda s: prices.load(s, raw_dir), edgar_loader=run.edgar_loader(inp["selection"], raw_dir))
keep = {k: v for k, v in out.items() if k != "sessions"}
with open(out_dir / "out.pkl", "wb") as f:
    pickle.dump(keep, f)
rep = run.report(out, p)
(out_dir / "report.json").write_text(json.dumps(rep, indent=2, sort_keys=True, default=str) + "\n")
print(tag, "params_hash", p.params_hash[:16], "timing", dict(p["timing"]))
print("keys", sorted(keep))
```

`compare.py`:

```python
# Compare the saved builds of cache/edgar-coarse/<tag>/: before (code of f5904a9), off, absent, on.
# Prints counts, dates and EDGAR times only, never a price or gap value.
import json
import pickle
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from earnings_vol import config, params as params_mod
from earnings_vol.events import calendar, timing

base = config.cache_dir() / "edgar-coarse"
B = {t: pickle.load(open(base / t / "out.pkl", "rb")) for t in ("before", "off", "absent", "on")}
TABLES = ("session", "market_daily", "security", "ticker_alias", "events", "eps", "timing_check")
LISTS = ("lookup_violations", "edgar_outcome", "edgar_pending_gap_checks", "edgar_on")


def same(a, b):
    for k in TABLES:
        pd.testing.assert_frame_equal(a[k], b[k])
    for k in LISTS:
        assert a[k] == b[k], k
    return True


print("1. off == before:", same(B["off"], B["before"]), "| absent == before:", same(B["absent"], B["before"]))
print("   reports equal apart from the new keys:",
      {t: {k: v for k, v in json.load(open(base / t / "report.json")).items() if k != "edgar"}
       == {k: v for k, v in json.load(open(base / "before" / "report.json")).items() if k != "edgar"}
       for t in ("off", "absent")})
for t in ("off", "absent"):
    e1 = json.load(open(base / t / "report.json"))["edgar"]
    e0 = json.load(open(base / "before" / "report.json"))["edgar"]
    print(f"   {t}: edgar report keys added", sorted(set(e1) - set(e0)), "| shared keys equal:",
          all(e1[k] == e0[k] for k in e0))

on, bef = B["on"], B["before"]
ev1, ev0 = on["events"].set_index("event_id"), bef["events"].set_index("event_id")
assert list(ev1.index) == list(ev0.index)
diff_cols = [c for c in ev0.columns if not ev0[c].equals(ev1[c])]
print("\n2. events columns that differ (on vs before):", diff_cols)
for c in diff_cols:
    ch = [(e) for e in ev0.index if not (ev0.at[e, c] == ev1.at[e, c] or (pd.isna(ev0.at[e, c]) and pd.isna(ev1.at[e, c])))]
    print(f"   {c}: {len(ch)} rows; samples {pd.Series(ev0.loc[ch, 'sample']).value_counts().to_dict()}")
for k in ("eps", "timing_check", "session", "market_daily", "security", "ticker_alias"):
    print(f"   {k} equal:", on[k].equals(bef[k]))
print("   lookup_violations equal:", on["lookup_violations"] == bef["lookup_violations"],
      "n", len(on["lookup_violations"]))

cons0 = {e for e, o in bef["edgar_outcome"].items() if o is not None}
cons1 = {e for e, o in on["edgar_outcome"].items() if o is not None}
new = sorted(cons1 - cons0)
print("\n3. consulted before", len(cons0), "on", len(cons1), "new", len(new), "| lost", len(cons0 - cons1))
print("   new consulted by sample:", ev1.loc[new, "sample"].value_counts().to_dict())
print("   new consulted, before: status", ev0.loc[new, "timing_status"].value_counts().to_dict(),
      "source", ev0.loc[new, "timing_source"].fillna("(none)").value_counts().to_dict(),
      "label", ev0.loc[new, "timing_raw"].fillna("(NULL)").value_counts().to_dict())
oc = pd.Series({e: on["edgar_outcome"][e] for e in new})
tab = pd.crosstab(oc, ev1.loc[new, "sample"], margins=True, margins_name="All")
print("   outcomes of the new consulted events:\n" + tab.to_string())
print("   resolved by label:", ev1.loc[[e for e in new if oc[e] in ("confirmed", "inferred")], "timing_used"]
      .value_counts().to_dict())
same_outcome = {e: (bef["edgar_outcome"][e], on["edgar_outcome"][e]) for e in cons0
                if bef["edgar_outcome"][e] != on["edgar_outcome"][e]}
print("   outcome changed for an event consulted before:", same_outcome)

d0 = [e for e in ev0.index if ev0.at[e, "day0_session"] != ev1.at[e, "day0_session"]]
dm1 = [e for e in ev0.index if ev0.at[e, "day_m1_session"] != ev1.at[e, "day_m1_session"]]
moved = [e for e in d0 if ev0.at[e, "day0_session"] is not None and ev1.at[e, "day0_session"] is not None]
lost = [e for e in d0 if ev0.at[e, "day0_session"] is not None and ev1.at[e, "day0_session"] is None]
gained = [e for e in d0 if ev0.at[e, "day0_session"] is None and ev1.at[e, "day0_session"] is not None]
print("\n4. day 0: moved", len(moved), "lost", len(lost), "newly defined", len(gained), "| day -1 changed", len(dm1))

p = params_mod.load()
st = calendar.build_session_table(p.day("sessions", "start"), p.day("sessions", "end"), p["snapshot_eras"])
sess = calendar.Sessions(st["session_date"].tolist())
close = dict(zip(st["session_date"], st["close_time_et"]))
NY = ZoneInfo("America/New_York")
print("\n5. listed for a press-release check (on):", len(on["edgar_press_release_checks"]),
      "| before the switch the same rule lists:", sorted(e for e, o in bef["edgar_outcome"].items()
                                                         if o in timing.EDGAR_WAIT_FOR_RELEASE))
print("   event | sample | outcome | calendar label | 8-K accepted (New York) | 8-K reads | day 0 now | day 0 if a release agrees with the 8-K")
for e in on["edgar_press_release_checks"]:
    r = ev1.loc[e]
    acc = datetime.strptime(r["edgar_accepted_utc"], "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=ZoneInfo("UTC")).astimezone(NY)
    d, hhmm = acc.date(), acc.strftime("%H:%M")
    lab = None if not sess.is_session(d) else ("BMO" if hhmm < "09:30" else ("AMC" if hhmm >= close[d] else "during"))
    alt = calendar.day0(d, lab if lab in ("BMO", "AMC") else None, sess)[0] if lab != "during" else None
    print(f"   {e} | {r['sample']} | {on['edgar_outcome'][e]} | {r['timing_raw']} | {acc:%Y-%m-%d %H:%M} | {lab} | "
          f"{r['day0_session']} | {alt}{'  (same)' if alt == r['day0_session'] else ''}")

print("\n6. pending gap checks: before", len(bef["edgar_pending_gap_checks"]), "on", len(on["edgar_pending_gap_checks"]),
      "| added", sorted(set(on["edgar_pending_gap_checks"]) - set(bef["edgar_pending_gap_checks"])),
      "| removed", sorted(set(bef["edgar_pending_gap_checks"]) - set(on["edgar_pending_gap_checks"])))
for name, ev in (("before", ev0), ("on", ev1)):
    print(f"\n7. {name}: by sample", ev["sample"].value_counts().sort_index().to_dict())
    print(f"   exclusion", ev["exclusion_reason"].fillna("(none)").value_counts().sort_index().to_dict())
    print(f"   status x sample:\n" + pd.crosstab(ev["timing_status"], ev["sample"], margins=True).to_string())
    print(f"   source", ev["timing_source"].fillna("(none)").value_counts().sort_index().to_dict())
    print(f"   look-ups done (timing_status != not_checked):", int((ev["timing_status"] != "not_checked").sum()))

# Coarse events still not_checked with a calendar label, and labelled not_checked events outside every sample.
c1 = ev1[(ev1["sample"] == "coarse") & (ev1["timing_status"] == "not_checked")]
print("\n8. coarse not_checked after:", len(c1), "with a calendar label:", int((c1["timing_source"] == "calendar").sum()),
      "outcomes:", pd.Series([on["edgar_outcome"][e] for e in c1.index]).value_counts().to_dict())
r = {k: p.date_range("samples", k) for k in ("daily", "mixed", "coarse")}
nn = ev1[(ev1["sample"] == "none") & (ev1["timing_status"] == "not_checked") & ev1["timing_raw"].notna()]
can = [e for e in nn.index if timing.can_enter_sample(nn.at[e, "announce_date"], sess, r)]
print("   labelled not_checked events in sample none:", len(nn), "of them able to enter a sample:", can)
```

`unresolved.py`:

```python
# The newly consulted coarse events that EDGAR did not resolve: event, label, outcome, 8-K time (New York).
import pickle
from datetime import datetime
from zoneinfo import ZoneInfo

from earnings_vol import config

base = config.cache_dir() / "edgar-coarse"
on = pickle.load(open(base / "on" / "out.pkl", "rb"))
bef = pickle.load(open(base / "before" / "out.pkl", "rb"))
ev = on["events"].set_index("event_id")
new = sorted(e for e, o in on["edgar_outcome"].items() if o is not None and bef["edgar_outcome"][e] is None)
for e in new:
    o = on["edgar_outcome"][e]
    if o == "confirmed":
        continue
    acc = ev.at[e, "edgar_accepted_utc"]
    ny = (datetime.strptime(acc, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=ZoneInfo("UTC"))
          .astimezone(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %a %H:%M")) if acc else "-"
    print(f"{o:15} {e:20} label {ev.at[e, 'timing_raw']} day0 {ev.at[e, 'day0_session']} 8-K {ny}")
```

`terciles.py`:

```python
# Coarse status counts by tercile of abs_move_cand_max (ADR 0002 §3 job 3), before and on.
# event_iv is read from the committed stage of params d23d18972bf0c8d4 (day 0 is the same in both builds).
import pickle

import pandas as pd

from earnings_vol import config

base = config.cache_dir() / "edgar-coarse"
eiv = pd.read_parquet(config.cache_dir() / "stage" / "d23d18972bf0c8d4" / "event_iv.parquet",
                      columns=["event_id", "abs_move_cand_max"])
for tag in ("before", "on"):
    out = pickle.load(open(base / tag / "out.pkl", "rb"))
    ev = out["events"].merge(eiv, on="event_id", how="left")
    ev = ev[(ev["exclusion_reason"] != "duplicate_row") & ev["abs_move_cand_max"].notna() & (ev["sample"] == "coarse")]
    g = ev.sort_values(["abs_move_cand_max", "event_id"], kind="mergesort")
    n = len(g)
    g = g.assign(tercile=[1 + (3 * r) // n for r in range(n)])
    print(tag, "coarse events with the move:", n)
    print(pd.crosstab(g["timing_status"], g["tercile"], margins=True).to_string())
    nc = g[g["timing_status"] == "not_checked"]
    print("  not_checked by tercile and EDGAR outcome:")
    print(pd.crosstab(pd.Series([out["edgar_outcome"][e] or "(not consulted)" for e in nc["event_id"]], index=nc.index,
                                name="outcome"), nc["tercile"]).to_string())
```
