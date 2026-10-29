# Milestone 1: universe and events

- **Status:** done, pending owner review; **revised 2026-10-29 after the milestone-1 adversarial review**
  ([ledger](../validation/m1-ledger.md); the fixes are listed at its end), **and again the same day after its delta
  review** ([delta ledger](../validation/m1-delta-ledger.md); the fixes are listed at its end). **The timing labels are provisional**: 20
  press releases were looked up and timed, and the rest wait for SEC EDGAR (owner default, 2026-10-29).
- **Date:** 2026-10-29
- **Scope:** [milestone 0 §8](00-scaffold-and-design.md#8-whats-next-milestone-1-universe-and-events), items 1 to 5.
- **Source of truth:** the ADRs (milestone-1 notes in [0001](../adr/0001-overall-architecture.md) and
  [0002](../adr/0002-day-zero-convention.md)), [`data-model.md`](../architecture/data-model.md) and the code. This page
  restates them and records what was measured.
- **Where this fits:** [LEARNING_LOG.md](../../LEARNING_LOG.md) is the index. The new first-principles ideas have
  concept notes: [sessions and day 0](../concepts/01-sessions-and-day-zero.md), [the EPS period
  match](../concepts/02-eps-period-match.md), [reading shared data read-only](../concepts/03-shared-data-read-only.md),
  [the parity spot](../concepts/04-parity-spot-and-snapshot-time.md), [survivorship bias](../concepts/05-survivorship-bias.md).

---

## 1. What we built and why

Milestone 0 designed the study. Milestone 1 builds the part that everything later stands on: **which companies, which
announcements, and on which session each announcement reached the option market.** No IV is computed yet.

1. **A universe of 50 companies** (`security`, `ticker_alias`). The 50 largest current S&P 500 members by Yahoo market
   cap that have DoltHub calendar rows and option snapshots, one share class each. The five names with a CBOE
   single-stock VIX index were all inside the 50 already. FB → META and UTX → RTX are handled as ticker changes. The
   rule selects today's winners, so the sample has **survivorship bias**; it is stated in the output.
2. **An ingest layer** that reads the shared DoltHub clones without ever writing to them. Its first test found that
   `dolt sql` *does* write on a pure SELECT, so, as ADR 0001 had decided for that case, it reads a private copy.
3. **The events layer's tables**: NYSE `session`s, `market_daily` (the T-bill rate and VIX per session), `events` with
   day 0, the timing label and its status, the prev/next chain, the sample and the exclusion reason, `eps` matched to
   events, and the local price-gap diagnostic `timing_check`. A schema registry gives every column its type and
   licence class, and a writer refuses anything that does not match.
4. **Timing from documents.** The default rule of ADR 0002 needs a press-release look-up for 473 events. The first 20
   were done and timed; the owner chose to let the rest wait for EDGAR (approved 2026-10-28, contact string pending).
   An EDGAR client exists and refuses to run without that string.
5. **Evidence checks**: "the snapshot is the close" widened to every after-close event of the daily era, the
   holiday-copy rule checked on all 50 companies, and the orphan rate measured.
6. **The sample funnel** (contract 0.2.0): Python counts how many events survive each rule and writes
   `app/public/data/sample_funnel.json`; the app's new Sample page only draws it. The primary sample holds **350
   events** by this count (an upper bound until milestone 2 removes sessions without a usable IV). It was 348 before
   the review corrected the EPS period match (§6.5).
7. **A generated notebook**, `notebooks/01_events.ipynb`, with its sync test.

---

## 2. Why this design

| Choice | Alternatives | Why | Cost |
|---|---|---|---|
| Query a **private mirror** of each Dolt clone in `cache/dolt_mirror/` | Query the shared clone (the ADR 0001 plan); `dolt sql-server` | Measured: a pure SELECT rewrites four files in `.dolt/` (same bytes, new mtimes). ADR 0001 named the mirror as the fallback for exactly this. | 10 GB of disk; the mirror is refreshed by copying when the shared clone's data files change |
| **Two fingerprints**: (size, mtime) on the shared clone, (size, SHA-256 of metadata) on the mirror | One stat fingerprint everywhere | Dolt's harmless mtime touches in the mirror would trip a stat check on every query; the shared clone must not be touched at all | Two functions to explain |
| `dolt sql -r parquet` | CSV with a `'<NULL>'` sentinel (ADR 0001) | Typed output, real nulls; same speed (40.75 s vs 40.25 s for one month) | Decimals need a text cast: pyarrow's direct cast is not correctly rounded |
| **Commits pinned in `params.yaml`** | Read HEAD every run (ADR 0001) | A re-run reads the same data after the hub pulls; the commits enter `params_hash` | Moving to new data is a deliberate edit |
| Universe = **top 50 by today's Yahoo market cap** among eligible S&P 500 members, plus any VX\* name | Point-in-time ranks; a hand-picked list; the milestone-0 30 names | Reproducible, one rule, covers the CBOE names | Survivorship bias (stated); the rank is a class-F label |
| `security` holds **all 499 constituents** (497 of them ranked), `in_universe` flags the 50 | Only the 50 | The data model's "one row per company considered" | A larger table (14 KB). The market-cap rank itself is **not** committed: it is a per-row Yahoo-derived number (review claim 10), so it stays in the local `cache/universe.parquet` |
| EPS period match: **duplicate calendar rows** of one release removed first, then a window from **14 days after the first day of the period end's month** to +100 days, then a **one-to-one, in-order assignment, nearest in total** | The first event 10 to 100 days after the period end (the first version); a fixed −31-day bound; the first of the month itself (the rule until the delta review); costing a link by its distance from the company's usual lag | The stored period end is month-end normalised, so the true end is no earlier than the first of the month, and a report can come before the stored end (Costco) or within 10 days of it (Oracle, Cisco). The assignment keeps a period whose report is missing from taking the next quarter's. A fixed −31 days would let Berkshire's late-February Q4 release into the March quarter's window (2025-02-28 is 31 days before 2025-03-31). Opening on the first of the month let a report 60–73 days late into the next period's window, where the assignment could move it (the delta review's S1, S2, S4); 14 days later, a report must be 74 days late, and the earliest real report still has 10 days of margin. A "usual lag" cost would depend on the links it decides | A small dynamic program instead of a lookup (`events/eps.py`); a link can still move from 74 days late (ADR 0002 §3); see the sensitivity table, §6.5 |
| **First 19 in look-up order + GOOGL** for the 20 timed look-ups | 20 known errors; a random 20 | The ADR's "first 20"; GOOGL was required by the brief (NFLX was 15th anyway) | 20 different companies, so the cheaper "same archive" repeat look-up is not measured |
| **Invariant reported, not enforced**, while `timing.lookups_complete: false` | Enforce it (ADR 0002) and stop the build | The owner's default leaves 453 events `not_checked`; the build must still run | The labels are provisional; every output says so |
| New exclusion reason **`timing_not_checked`** | Call these events `ambiguous`; give them a day 0 from a guess | `ambiguous` means "looked up, nothing found"; these were never looked up | One more code to explain; it disappears once the look-ups are done |
| New column **`events.announce_date_used`** | Re-key the event to the documents' date | `event_id` stays the calendar's, so a look-up row always finds its event | A column the ERD lacks (edits listed in the report) |
| New table **`session_snapshot`** (iv_daily's first four columns) | Wait for `iv_daily` (milestone 2); count snapshots ad hoc | The funnel's baseline step needs observed sessions now, from committed data | A table milestone 2 will fold into `iv_daily` |
| Funnel computed from **committed tables only** | From the local stage cache | The committed JSON can be rebuilt and checked by a test without the cache | `session_snapshot` had to be committed (146 KB) |
| `by_move_tercile` and `evar_nonpositive` **null with a status** | Leave them out of 0.2.0; compute them from Yahoo moves | Their inputs are milestone-2 measures; Yahoo-based terciles would be a class-R aggregate | The app accepts only null for them until the contract moves on |
| **EDGAR client gated** on `SEC_EDGAR_USER_AGENT` | A default User-Agent; no client yet | The owner approved EDGAR but must supply the contact; SEC's policy needs a real one | Nothing runs until the string arrives |

---

## 3. Code walkthrough by `file:line`

Line numbers are those of the files as delivered at this milestone.

### 3.1 Parameters, registry and writer

- [`params.yaml`](../../params.yaml) holds every choice: the universe rule, the pinned commits, the session range, the
  snapshot eras, the sample ranges (ADR 0004 §5), the windows, the EPS window, the look-up rule and the gap thresholds.
- [`params.py:64`](../../src/earnings_vol/params.py#L64) `load()` parses it and hashes the **canonical JSON** of the
  parsed values ([`params.py:39`](../../src/earnings_vol/params.py#L39)), so comments and key order do not change
  `params_hash`, and a changed value does.
- [`schema.py:55`](../../src/earnings_vol/schema.py#L55) `Column` (dtype, nullability, licence class, enum) and
  [`schema.py:73`](../../src/earnings_vol/schema.py#L73) `Table`. The tables are
  [`schema.py:106`](../../src/earnings_vol/schema.py#L106) to [`schema.py:210`](../../src/earnings_vol/schema.py#L210).
- [`store.py:66`](../../src/earnings_vol/store.py#L66) `validate()`: exact column order, nulls only where allowed, the
  right Python type (a `datetime` is refused where a date belongs), int ranges, enum members, unique keys. Every
  problem is listed in one error.
- [`store.py:151`](../../src/earnings_vol/store.py#L151) `write_table()` writes Parquet plus a manifest (rows,
  `params_hash`, commits, code commit, time, SHA-256).
- [`store.py:186`](../../src/earnings_vol/store.py#L186) `committable()` and
  [`store.py:203`](../../src/earnings_vol/store.py#L203) `write_derived()`: refuse local-only tables
  ([`store.py:193`](../../src/earnings_vol/store.py#L193)), drop class R
  ([`store.py:195`](../../src/earnings_vol/store.py#L195)), refuse a suffixed column the registry forgot
  ([`store.py:196`](../../src/earnings_vol/store.py#L196)).

### 3.2 Ingest

- [`ingest/dolt.py:80`](../../src/earnings_vol/ingest/dolt.py#L80) `check_statement()`: one statement
  ([`:85`](../../src/earnings_vol/ingest/dolt.py#L85)), no write word anywhere
  ([`:92`](../../src/earnings_vol/ingest/dolt.py#L92)), no `dolt_*()` call
  ([`:94`](../../src/earnings_vol/ingest/dolt.py#L94)).
- [`ingest/dolt.py:108`](../../src/earnings_vol/ingest/dolt.py#L108) `as_of()` pins a table to a checked commit hash.
- [`ingest/dolt.py:129`](../../src/earnings_vol/ingest/dolt.py#L129) `stat_fingerprint()` (every path in the clone
  folder, `.dolt/` and beside it, since the review) and
  [`:159`](../../src/earnings_vol/ingest/dolt.py#L159) `content_fingerprint()` (its known blind spot, same-size
  changes to the unhashed table files, is documented at [`:148`](../../src/earnings_vol/ingest/dolt.py#L148));
  [`:180`](../../src/earnings_vol/ingest/dolt.py#L180) `guard()` checks both around a batch, the shared clone first
  ([`:186`](../../src/earnings_vol/ingest/dolt.py#L186)).
- [`ingest/dolt.py:192`](../../src/earnings_vol/ingest/dolt.py#L192) `refresh_mirror()`: skip when the mirror's data
  files equal the shared clone's ([`:202`](../../src/earnings_vol/ingest/dolt.py#L202)); otherwise copy to a
  temporary folder, and keep the copy only if the shared clone did not change meanwhile.
- [`ingest/dolt.py:224`](../../src/earnings_vol/ingest/dolt.py#L224) `query()` runs `dolt sql --disable-auto-gc -r
  parquet` ([`:232`](../../src/earnings_vol/ingest/dolt.py#L232)) and reads the bytes without threads
  ([`:238`](../../src/earnings_vol/ingest/dolt.py#L238)); [`:246`](../../src/earnings_vol/ingest/dolt.py#L246)
  `normalise()` refuses a timestamp with a time of day ([`:262`](../../src/earnings_vol/ingest/dolt.py#L262)) and
  casts decimals through text ([`:267`](../../src/earnings_vol/ingest/dolt.py#L267)).
- [`ingest/dolt.py:298`](../../src/earnings_vol/ingest/dolt.py#L298) `extract_months()`: one query per month, `date`
  first, cached by commit, symbol set and `NORMALISE_VERSION`.
- [`ingest/wikipedia.py:57`](../../src/earnings_vol/ingest/wikipedia.py#L57) parses the constituents table of one
  pinned revision; [`ingest/universe.py:92`](../../src/earnings_vol/ingest/universe.py#L92) `select_universe()` is the
  rule; [`ingest/universe.py:46`](../../src/earnings_vol/ingest/universe.py#L46) lists the known ticker changes.
- [`ingest/edgar.py:90`](../../src/earnings_vol/ingest/edgar.py#L90) `user_agent()` raises unless
  `SEC_EDGAR_USER_AGENT` holds a real contact ([`:94`](../../src/earnings_vol/ingest/edgar.py#L94),
  [`:96`](../../src/earnings_vol/ingest/edgar.py#L96)); [`:57`](../../src/earnings_vol/ingest/edgar.py#L57)
  `is_real_contact()` wants a well-formed email whose domain is not reserved (`example.com` and its subdomains,
  `.example`, `.test`, `.invalid`, `.localhost`, `.local`, and since the delta review `home.arpa`, `.onion`, `.alt`,
  `.internal`), with no leading, trailing or double dot in the local part, no label over 63 characters and no domain
  over 253; it fails closed on a trailing full stop, a punycode top-level domain and a Unicode address (its docstring); [`:106`](../../src/earnings_vol/ingest/edgar.py#L106)
  `fetch_submissions()` calls `user_agent()` first ([`:113`](../../src/earnings_vol/ingest/edgar.py#L113)), before
  cache or network; [`:159`](../../src/earnings_vol/ingest/edgar.py#L159) reads an acceptance time as BMO/AMC/during
  the session, and refuses to read it around EDGAR's holidays ([`:173`](../../src/earnings_vol/ingest/edgar.py#L173)).
- [`ingest/run.py:130`](../../src/earnings_vol/ingest/run.py#L130) `main()` orders it all and checks at the end that
  neither shared clone changed during the run.

### 3.3 Events

- [`events/calendar.py:85`](../../src/earnings_vol/events/calendar.py#L85) builds `session` from XNYS;
  [`:115`](../../src/earnings_vol/events/calendar.py#L115) `day0()` is ADR 0002 §2: a non-session D first
  ([`:124`](../../src/earnings_vol/events/calendar.py#L124)), then BMO ([`:128`](../../src/earnings_vol/events/calendar.py#L128)),
  AMC, and an undecidable case ([`:132`](../../src/earnings_vol/events/calendar.py#L132)).
- [`events/market.py:30`](../../src/earnings_vol/events/market.py#L30) converts the bank-discount T-bill rate
  ([`:32`](../../src/earnings_vol/events/market.py#L32)); VIX is taken for its own date only
  ([`:52`](../../src/earnings_vol/events/market.py#L52)).
- [`events/securities.py:38`](../../src/earnings_vol/events/securities.py#L38) `resolve_on()` (calendar rows, by ticker
  and date) and [`:50`](../../src/earnings_vol/events/securities.py#L50) `resolve_any()` (EPS rows, by ticker);
  [`:30`](../../src/earnings_vol/events/securities.py#L30) `build_ticker_alias()` takes the alias rows that
  `events/run.py` reads from `ingest.universe` (a pure module imports no ingest module; delta review, claim 5a).
- [`events/timing.py:55`](../../src/earnings_vol/events/timing.py#L55) `parse_when()`;
  [`:68`](../../src/earnings_vol/events/timing.py#L68) `label_from_time()`;
  [`:94`](../../src/earnings_vol/events/timing.py#L94) `parse_checks()` refuses a row whose time and label disagree,
  and a time whose basis is not `time_stamp` or `announced_time`;
  [`:156`](../../src/earnings_vol/events/timing.py#L156) `final_reading()` (two blind readings must agree to change a
  label); [`:179`](../../src/earnings_vol/events/timing.py#L179) `resolve_timing()` is ADR 0002 §3's status table.
- [`events/timing.py:212`](../../src/earnings_vol/events/timing.py#L212) `overnight_gaps()` and
  [`:236`](../../src/earnings_vol/events/timing.py#L236) `gap_check()`: the local diagnostic;
  [`:292`](../../src/earnings_vol/events/timing.py#L292) `can_enter_sample()` and
  [`:305`](../../src/earnings_vol/events/timing.py#L305) `lookup_reasons()` are the default rule's "who is looked up",
  scoped to events that can enter a sample ([`:318`](../../src/earnings_vol/events/timing.py#L318)).
- [`events/eps.py:95`](../../src/earnings_vol/events/eps.py#L95) `window()`: from 14 days after the first day of the
  period end's month (`month_start+14`) to +100 days; [`:113`](../../src/earnings_vol/events/eps.py#L113) `match_periods()`: the one-to-one, in-order
  assignment with the smallest total cost, a dynamic program over (period, event)
  ([`:138`](../../src/earnings_vol/events/eps.py#L138)), walked forwards with ties to the earlier event
  ([`:147`](../../src/earnings_vol/events/eps.py#L147)); pre-calendar only for a window that starts before the
  calendar and holds no event ([`:158`](../../src/earnings_vol/events/eps.py#L158)); a period left unlinked costs
  `lag_max` + 1 ([`:129`](../../src/earnings_vol/events/eps.py#L129)).
  [`:165`](../../src/earnings_vol/events/eps.py#L165) `build_eps()` adds values and the last consensus on or before
  day −1; [`:236`](../../src/earnings_vol/events/eps.py#L236) gives the orphan zones.
- [`events/events.py:51`](../../src/earnings_vol/events/events.py#L51) `base_events()`;
  [`:78`](../../src/earnings_vol/events/events.py#L78) `check_sample_ranges()` (the three ranges must be contiguous);
  [`:92`](../../src/earnings_vol/events/events.py#L92) `duplicate_rows()` (rows within 14 days are one release;
  the strongest timing evidence is kept, a tie stops the build);
  [`:134`](../../src/earnings_vol/events/events.py#L134) `build_events()` (timing, day 0, links, season, sample);
  [`:173`](../../src/earnings_vol/events/events.py#L173) `finish_events()` (EPS link, `orphan_nearby`, exclusion
  reasons [`:186`](../../src/earnings_vol/events/events.py#L186)); [`:206`](../../src/earnings_vol/events/events.py#L206)
  `check_chain()`; [`:241`](../../src/earnings_vol/events/events.py#L241) and
  [`:254`](../../src/earnings_vol/events/events.py#L254) the look-up invariant.
- [`events/run.py:59`](../../src/earnings_vol/events/run.py#L59) `build()` runs the layer in ADR 0001's order.

### 3.4 Measures, panel and export (the milestone-1 parts)

- [`measures/snapshots.py:29`](../../src/earnings_vol/measures/snapshots.py#L29) `quote_digests()` (an order-free hash
  of each snapshot's quotes); [`:48`](../../src/earnings_vol/measures/snapshots.py#L48) `build_session_snapshot()`:
  keep the snapshot dated on the session ([`:64`](../../src/earnings_vol/measures/snapshots.py#L64),
  [`:66`](../../src/earnings_vol/measures/snapshots.py#L66)), flag exact repeats
  ([`:72`](../../src/earnings_vol/measures/snapshots.py#L72)).
- [`measures/forward.py:37`](../../src/earnings_vol/measures/forward.py#L37) `parity_forward()`: the 4 strikes with the
  smallest |C − P| ([`:53`](../../src/earnings_vol/measures/forward.py#L53)), $F_K = K + (C-P)/DF$
  ([`:54`](../../src/earnings_vol/measures/forward.py#L54)).
- [`measures/snapshot_close.py:30`](../../src/earnings_vol/measures/snapshot_close.py#L30) `parity_spot()`;
  [`measures/run.py:54`](../../src/earnings_vol/measures/run.py#L54) `run_close()` classifies days
  ([`:109`](../../src/earnings_vol/measures/run.py#L109)) and summarises ([`:116`](../../src/earnings_vol/measures/run.py#L116)).
- [`panel/baseline.py:34`](../../src/earnings_vol/panel/baseline.py#L34) `clean_baseline()`: ADR 0004 §1 without the
  IV rule.
- [`export/funnel.py:78`](../../src/earnings_vol/export/funnel.py#L78) `funnel_data()`: the five steps
  ([`:92`](../../src/earnings_vol/export/funnel.py#L92) to [`:102`](../../src/earnings_vol/export/funnel.py#L102)).
- [`tools/export_app_data.py:137`](../../tools/export_app_data.py#L137) `meta_data()` and
  [`:159`](../../tools/export_app_data.py#L159) `main()` write `meta.json` and `sample_funnel.json` from committed
  inputs only.
- The app: `app/src/lib/funnel.ts` (`parseSampleFunnel`, `loadSampleFunnel`), `app/src/lib/FunnelPage.tsx` (draws the
  steps, counts, statuses and caveats), `app/src/lib/meta.ts` (the 0.2.0 meta keys), `app/src/lib/contract.ts`
  (`SCHEMA_VERSION = '0.2.0'`).

---

## 4. Data flow

```
 shared clones (read-only)      Wikipedia rev 1382178819   Yahoo (local)   FRED      data/manual/
 ~/data/vol-projects/dolthub    S&P 500 list               prices, caps    DTB3,VIX  press_release_checks.csv
        │ copy + fingerprint            │                        │            │                │
        ▼                               ▼                        ▼            ▼                │
 cache/dolt_mirror/{earnings,options}   raw/wikipedia      raw/yfinance   raw/fred             │
        │ dolt sql -r parquet, AS OF the pinned commits                        │                │
        ▼                                                                       │                │
 cache/dolt/<repo>@<commit>/{earnings_calendar, eps_history, eps_estimate,      │                │
                             option_chain/<yyyy-mm>}.parquet                    │                │
        │                                                                       │                │
        ▼  python -m earnings_vol.events.run  (pure functions, ADR 0001 order)  ▼                ▼
 session → market_daily → security → ticker_alias → base events → timing → day 0 + links → eps
        → orphan zones → orphan_nearby, sample → exclusion_reason; timing_check (local); invariant report
        │
        ├─► cache/stage/<hash>/*.parquet + manifests   (every column, local)
        └─► data/derived/{session,security,ticker_alias,events,eps}.parquet   (committed columns)
        │
        ▼  python -m earnings_vol.measures.run
 session_snapshot (from option_chain) ─► data/derived/session_snapshot.parquet
 snapshot-close check (Yahoo, local) ──► cache/stage/<hash>/snapshot_close.json
        │
        ▼  uv run python tools/export_app_data.py   (reads data/derived + params.yaml only)
 app/public/data/meta.json, sample_funnel.json  (contract 0.2.0) ─► app: Sample page draws them
```

---

## 5. Pitfalls and their guards

| # | Pitfall | Guard (`file:line`) | Test |
|---|---|---|---|
| 1 | `dolt sql` writes into `.dolt/` on a SELECT | private mirror [`ingest/dolt.py:192`](../../src/earnings_vol/ingest/dolt.py#L192); shared-clone check [`:186`](../../src/earnings_vol/ingest/dolt.py#L186) over every path in the clone folder | `test_a_pure_select_touches_files_but_keeps_their_bytes` (asserts the touched files), `test_guard_stops_on_a_change_in_either_folder`, `test_the_shared_clone_fingerprint_sees_a_new_file_anywhere_in_the_clone` |
| 2 | Auto-GC rewriting a store as a side effect | `--disable-auto-gc` [`ingest/dolt.py:232`](../../src/earnings_vol/ingest/dolt.py#L232) | (by construction) |
| 3 | A second statement or a write hidden in a query | [`ingest/dolt.py:85`](../../src/earnings_vol/ingest/dolt.py#L85), [`:92`](../../src/earnings_vol/ingest/dolt.py#L92), [`:94`](../../src/earnings_vol/ingest/dolt.py#L94) | `test_allowlist_refuses_hostile_statements` |
| 4 | pyarrow's decimal → float cast is off by one ulp (0.2678 → 0.26780000000000004) | text cast [`ingest/dolt.py:267`](../../src/earnings_vol/ingest/dolt.py#L267); cache invalidated by `NORMALISE_VERSION` | `test_normalise_turns_dolt_types_into_ours` |
| 4a | A timestamp with a time of day silently truncated to its date (review, claim 9) | refused [`ingest/dolt.py:262`](../../src/earnings_vol/ingest/dolt.py#L262) | `test_normalise_refuses_a_timestamp_with_a_time_of_day` |
| 5 | Reading a 0-row Parquet buffer with threads crashes the interpreter at exit (aarch64, pyarrow 26) | `use_threads=False` [`ingest/dolt.py:238`](../../src/earnings_vol/ingest/dolt.py#L238) | reproduced by hand (exit code 134) |
| 6 | pandas 3 turns `None` in a text or int column into NaN or float | `dtype=object` [`events/events.py:63`](../../src/earnings_vol/events/events.py#L63), [`:149`](../../src/earnings_vol/events/events.py#L149); the writer refuses floats in int columns [`store.py:66`](../../src/earnings_vol/store.py#L66) | `test_validate_names_the_broken_rule` |
| 7 | A wrong BMO/AMC label moves day 0 by one session | documents decide [`events/timing.py:179`](../../src/earnings_vol/events/timing.py#L179) | oracle table in `tests/test_calendar.py`; status table in `tests/test_timing.py` |
| 8 | A weekend release with no label wrongly made `ambiguous` | [`events/timing.py:189`](../../src/earnings_vol/events/timing.py#L189) | `test_resolve_timing_status_table` |
| 9 | A primed re-reader flipping right labels | two blind readings must agree [`events/timing.py:174`](../../src/earnings_vol/events/timing.py#L174) | `test_final_reading_needs_two_independent_readings_to_change_a_label` |
| 10 | Unlooked-up events treated as checked | `not_checked` status; invariant reported [`events/events.py:254`](../../src/earnings_vol/events/events.py#L254), enforced when `lookups_complete`, scoped to events that can enter a sample [`events/timing.py:318`](../../src/earnings_vol/events/timing.py#L318) | `test_lookup_invariant_is_reported_and_enforced_when_complete`, `test_lookup_reasons_only_for_events_that_can_enter_a_sample` |
| 11 | Month-end-normalised periods: a report before the stored end, or within 10 days of it; a period whose report is missing taking the next quarter's; a slow reporter's report moved to the next period (delta review) | window from 14 days after the first of the month [`events/eps.py:95`](../../src/earnings_vol/events/eps.py#L95); one-to-one assignment, nearest in total [`:113`](../../src/earnings_vol/events/eps.py#L113), an unlinked period costing `lag_max` + 1 [`:129`](../../src/earnings_vol/events/eps.py#L129) | `tests/test_eps.py` (Costco-, Oracle- and Berkshire-shaped fixtures, each bound; the delta review's S1, S2, S4; the 74-day line; the unlinked cost at 100, 101, 102 days), `tests/test_events_eps_link.py`, `tests/test_events_run.py` (the window parameter reaches the match) |
| 11a | A day 0 in no sample because the ranges leave a gap (2024-09-10, 09-11) | `check_sample_ranges` [`events/events.py:78`](../../src/earnings_vol/events/events.py#L78), called by `build()` [`events/run.py:76`](../../src/earnings_vol/events/run.py#L76) | `test_the_project_sample_ranges_partition_the_timeline`; `test_build_stops_on_sample_ranges_with_a_gap` (the call, delta review M-c) |
| 11b | A second calendar row of one release taking the EPS link (BRK.B 2024-11-01 beside 2024-11-02; delta review) | `duplicate_rows` [`events/events.py:92`](../../src/earnings_vol/events/events.py#L92), marked first in `build_events` [`:150`](../../src/earnings_vol/events/events.py#L150), skipped by the match [`events/eps.py:173`](../../src/earnings_vol/events/eps.py#L173) and by other events' baselines [`export/funnel.py:61`](../../src/earnings_vol/export/funnel.py#L61) | `tests/test_events.py` (the duplicate rules), `test_build_eps_never_links_a_duplicate_row`, `test_build_marks_the_duplicate_row_and_links_the_release`, `test_a_duplicate_row_blocks_no_session_and_leaves_at_timing_known`, `test_duplicate_rows_have_no_link_and_one_row_per_release_is_kept` |
| 12 | FB/META and UTX/RTX duplicates | [`ingest/universe.py:46`](../../src/earnings_vol/ingest/universe.py#L46), [`events/eps.py:78`](../../src/earnings_vol/events/eps.py#L78) | `test_dedupe_merges_agreeing_tickers_and_flags_a_conflict` |
| 13 | Holiday snapshots counted as sessions | [`measures/snapshots.py:64`](../../src/earnings_vol/measures/snapshots.py#L64) | `test_session_snapshot_copy_repeat_and_missing` |
| 14 | VIX carried over a missing day (a fake zero change) | [`events/market.py:52`](../../src/earnings_vol/events/market.py#L52) | `test_market_daily_carries_the_rate_but_never_vix` |
| 15 | A Yahoo or CBOE value leaving the machine | class R dropped [`store.py:195`](../../src/earnings_vol/store.py#L195); funnel built from committed tables only | `test_class_r_exactly_when_suffixed_over_every_value_column`, `test_exported_json_has_no_restricted_field` |
| 16 | EDGAR called with a placeholder contact, a reserved or special-use domain (also `home.arpa`, `.onion`, `.alt`, `.internal` since the delta review) or a malformed address (a local part with a leading, trailing or double dot; a label over 63 or a domain over 253 characters) | [`ingest/edgar.py:57`](../../src/earnings_vol/ingest/edgar.py#L57), [`:90`](../../src/earnings_vol/ingest/edgar.py#L90) | `test_edgar_refuses_without_a_real_contact_and_makes_no_request` (no request made) |
| 17 | A split making the as-of close wrong (NFLX 10-for-1 in 2025) | `split_factor_after` [`ingest/prices.py:64`](../../src/earnings_vol/ingest/prices.py#L64) | `test_split_factor_after_undoes_only_later_splits` |
| 18 | A layer importing from its right; I/O inside the pure middle | `tests/test_layering.py` (parses modules with `ast`, relative imports resolved): import direction, and, *since the delta review*, an **allow-list** for a middle module other than `run.py` (pure stdlib, numpy, pandas, scipy, statsmodels, exchange_calendars, `params`, `schema`, middle modules of its own layer or to its left) and no `open`, `exec`, `__import__`, `getattr`, numpy file call, or pandas `read_*`/`to_*` I/O method. To pass it, `events/securities.py` now receives the alias rows from `events/run.py` instead of importing `ingest.universe`, and `events/timing.py` reads the CSV text without `io` | itself, plus two checker tests (the delta review's 17 I/O forms of `pd08` among their cases) |

---

## 6. Measured results

All on 2026-10-29, on this machine, at the pinned commits (earnings `fjrb6h5le9h1qiif2j4pl6cpaas7pnee`, options
`msfqpodh24viv7prdqdan8517rkjp861`).

| What | Command | Result |
|---|---|---|
| Does `dolt sql` write on a SELECT? | `dolt sql -r csv -q "SELECT HASHOF('HEAD')"` in a copy of the earnings clone, stat fingerprint before/after | yes: `noms/manifest`, `noms/journal.idx`, the chunk journal and `stats/` rewritten, bytes identical (SHA-256 compared) |
| Does `-r parquet` work on dolt 2.6.1? | `dolt sql -r parquet -q "…"`, read with pyarrow | yes: `timestamp[us]` dates, `decimal128` numbers, real nulls; a 0-row result is a valid file |
| Parquet vs CSV speed | one month (2025-10) of `option_chain`, 50 names, both formats | 40.75 s vs 40.25 s; 159,604 rows (*corrected after the delta review:* this said 160,584. Re-counted from `cache/dolt/options@…/option_chain/2025-10.parquet` and its manifest, and both 2025-10 extractions in `cache/ingest_log.json` hold 159,604; where 160,584 came from could not be traced: no ticker or date of the month accounts for the 980 rows) |
| Mirror copy time | `cp -a` of each clone | 0.30 s (earnings, 1.8 GB), 5.23 s (options, 8.3 GB); both shared clones unchanged before/after |
| Option-chain extraction | `python -m earnings_vol.ingest.run --only chain --chain-from …` | 82 months, 52 source tickers, 8,174,225 rows, 1,294 s of query time (21.6 min); daily-era month median 41 s (max 51 s), Mon/Wed/Fri month median 6.4 s. Repeated after the decimal fix: 1,332 s of query time (22.2 min), the same 8,174,225 rows month by month; daily-era median 40.6 s (max 66.6 s) |
| Small extracts | `--only small` | `earnings_calendar` 1,353 rows in 0.1 s; `eps_history` 1,973 in 0.1 s; `eps_estimate` (Current Quarter) 22,835 in 65.5 s |
| Market caps for the rank | `--only universe` (Yahoo, one request per name) | 499 names in 107 s, 0 missing |
| Shared clones untouched | stat fingerprint at session start vs after all runs | identical for both (checked by `ingest/run.py` on every run and by hand at the end) |
| Universe | `select_universe` | 50 of 497 ranked (499 constituents; SKYD and VYLR are unranked because they had no option snapshot on the last data date: `volatility_history` has no row for either at the pinned commit. They do have Yahoo market caps; *corrected after the delta review*, which this said they lacked); GS 42nd, IBM 48th; sectors: IT 18, Financials 8, Health Care 7, Consumer Staples 5, Communication Services 3, Consumer Discretionary 3, Industrials 3, Energy 2, Materials 1 |
| Events | `python -m earnings_vol.events.run` | 1,353 events: `daily` 368, `mixed` 49, `coarse` 868, `none` 68 (ORCL 2024-09-09, day 0 on 09-10, moved from `none` to `coarse` when the review closed the gap between the sample ranges) |
| Timing status | same | 16 confirmed, 2 corrected, 1 date_corrected, 1 inferred, 1,333 not_checked, 0 no_document, 0 ambiguous |
| Exclusions | same | `duplicate_row` 1 (BRK.B 2024-11-01), `timing_not_checked` 32, `outside_samples` 61, none 1,259 (*after the delta review;* before it, the duplicate row was the 33rd `timing_not_checked`) |
| Look-ups required (default rule) | `events.lookup_violations` with no look-ups | 473 (422 by date, 30 NULL labels, 43 gap triggers; some have two reasons); 453 left after the 20. The rule covers only events that can enter a sample (ADR 0002 §3, scoped after the review): the unscoped sentence would also have counted 29 more, 28 dates scheduled after 2026-10-26 and 1 NULL-label event of March 2020 |
| Gap verdict (local diagnostic) | `timing_check` | on the calendar labels, before any look-up: 725 supports, 538 quiet, 22 contradicts, 68 none (no label, or one candidate); on the labels in use after the 20 look-ups: 729, 537, 20, 67. On the 20 press-release labels: 0 contradictions, 0 outside flags |
| EPS match | same | 1,324 matched, 35 orphan, 606 pre_calendar, 0 ticker_conflict; **orphan rate 35 / 1,359 = 2.58%**, below ADR 0002's 3% line (the first window gave 1,316 / 43 / 3.16%; §6.5). Lags −6 to +59 days (0 links of 60 days or more). The 35 orphans: 18 are 2021-12-31 periods (the calendar's early-2022 gap), then COST 7 (its February quarters), GS 2, AVGO 2, PLTR 2 (before its 2020-09-30 listing), and ANET, MS, PG and WMT 1 each. *Re-measured after the delta review's fixes* (the duplicate rule and the 14-day window): every count is the same; one link changed, BRK.B 2024-09-30 from the duplicate row `BRK.B:2024-11-01` (lag 32) to the release `BRK.B:2024-11-02` (lag 33) |
| Calendar gaps | `SELECT DISTINCT date FROM earnings_calendar … 2022-01-10 … 2022-02-20` | no row for any company on 2022-01-18, 2022-01-24 to 01-28, 2022-02-10, 02-11 |
| Duplicates | events of one company within 5 days; *after the delta review*, `events.duplicate_rows` with 14 days | 1 pair: BRK.B 2024-11-01 (no label) and 2024-11-02 (BMO). The smallest gap between two other rows of one company is 63 days (BRK.B), so any window from 1 to 62 days finds the same pair. The 2024-11-01 row is now `duplicate_row` |
| Session snapshots | `python -m earnings_vol.measures.run --only snapshots` | 59,850 snapshot company-dates read; 2,101 dropped as `stale_copy`; 0 `stale_repeat`; of 85,650 company-sessions 57,749 `ok` and 27,901 `missing` |
| The holiday-dated snapshots | a scratch script over the same digests: each off-session snapshot against the kept snapshot of its session | 2,649 snapshots fall on non-session days. **2,101** map to a session with its own snapshot and are dropped: **1,905 are exact copies** of it (same quotes, row for row) and **196 share its quotes but differ in their row set** (2022-01-17 ×41, 2022-06-20 ×40, 2026-05-25 ×40, 2024-01-15 ×23, …). **548 are kept** as the only snapshot of their session (all before 2024-09-11; 410 dated on a Friday holiday) |
| Snapshot is the close | `python -m earnings_vol.measures.run --only close` | 224 AMC events in the daily era, 211 with a parity spot. Median \|ln(S/Close)\| 11.2 bp on AMC days against 6.3 bp on 24,514 ordinary days; difference 4.9 bp, bootstrap 95% CI [3.0, 7.4] bp (2,000 draws, seed 20261029). Slope of ln(S/Close) on the next overnight gap: 0.0018 (SE 0.0030, corr 0.04, n = 211); median \|overnight gap\| on those days 594 bp. Share with \|ln(S/Close)\| > 1%: 1.4% (AMC days) vs 6.7% (ordinary) |
| Rebuild determinism | `md5sum data/derived/*.parquet`, rebuild events and snapshots, compare | byte-identical (re-checked after the review's fixes, and again after the delta review's); the six committed tables total 277,479 bytes (277,461 before the delta review's fixes changed one link and one exclusion reason) |
| Gap between consecutive day 0s | `events.gap_sessions_prev` | median 63 sessions, min 44, max 131 |
| Python tests | `uv run pytest -q` | `251 passed, 32 warnings in 8.08s` (2 of the 251 are `tests/test_diagrams.py`, from the diagram work running in parallel); the two `dolt`-marked tests: `2 passed`. *After the review's fixes:* `305 passed, 36 warnings` (the `dolt`-marked tests included). *After the delta review's fixes* (`uv run --frozen pytest -q -p no:cacheprovider`): `370 passed, 36 warnings in 17.81s`, the two `dolt`-marked tests among them |
| App gate | `cd app && npm run verify` | lint clean; `Test Files  27 passed (27)`, `Tests  447 passed (447)`; coverage statements 99.31%, branches 98.06%, functions 98.08%, lines 99.64%; `✓ built in 2.85s`. Unchanged after the review's fixes, and after the delta review's (lint clean, 447 tests, the same four coverage figures, exit 0) |
| Licence scan | `uv run python tools/licensing/scan_real_rows.py` (local: it compares with the raw Yahoo and FRED files) | after the review's fixes: `clean: 0 lines flagged`. *The delta review found a Cboe VIX close in `tests/test_measures.py` that the scanner cannot see* (it reads no `date(Y, M, D)` literals); it is replaced by a made-up 12.5. After the delta review's fixes: `clean: 0 lines flagged in 337 text file(s) of working tree against 55 raw file(s)` |
| Notebooks | `uv run python tools/build_notebooks.py --check` | `OK: 2 notebooks … are in sync with src/` |

### 6.1 The sample funnel (primary, `daily`)

| Step | Kept | Removed | Why removed |
|---|---:|---:|---|
| Calendar events of the 50 companies (2020-01-22 → 2026-12-01, scheduled dates included; *corrected after the delta review:* this said 2026-12-04, the last date of the whole calendar) | 1,353 | | |
| One row per release, and day 0 can be placed | 1,320 | 33 | `duplicate_row` 1 (BRK.B 2024-11-01, a second row of the 2024-11-02 release; *since the delta review*), `timing_not_checked` 32 (no label, never looked up) |
| Day 0 in the daily range 2024-12-05 → 2026-10-26 | 366 | 954 | in `mixed`, `coarse` or no sample (49 + 868 + 68 = 985 events, 31 of which were already removed above) |
| Snapshots on day −1 and day 0 | 356 | 10 | a missing snapshot; 9 of the 10 fall on days the vendor skipped in May 2026 (05-01, 05-05, 05-13, 05-14), 1 on 2026-10-22 |
| ≥ 20 clean baseline sessions and ≥ 15 clean changes | **350** | 6 | short baseline: GS 2025-04-14 and MS 2025-07-16 have no clean session at all, because an orphan period's zone covers the whole baseline; COST 2025-05-29 (7 sessions) and 2026-05-28 (8), whose baselines hold the zone of the February quarter, whose March report the calendar lacks; BRK.B 2025-05-03 (12: its previous row, 2025-02-28, is a Friday with no label, so its zone spans both candidate days and covers 27 of the 39 baseline sessions; *corrected after the delta review*, which this put next to the duplicate rows of 2024-11); PM 2026-04-22 (19) |

Command: `uv run python tools/export_app_data.py` (the funnel is in `app/public/data/sample_funnel.json`). 350
replaces the `⟨n⟩` of the PR/FAQ. It is an upper bound: milestone 2 also removes sessions without a usable IV.
ADR 0004 §5 expected "about 330–360". *Revised after the review:* this was 348 with the first EPS window, whose false
orphans removed four clean baselines (COST 2025-09-25 and 2026-09-24, ORCL 2025-03-10 and 2025-12-10) and whose
wrong links kept the two COST May events that the missing March reports contaminate.

### 6.2 Predictions P1 to P3 (`LEARNING_LOG.md`, "My predictions")

The owner wrote no guesses, so the measured values are recorded here and the guess fields stay empty.

| # | Question | Measured value | How |
|---|---|---|---|
| P1 | Share of `earnings_calendar` rows for the ~50 names in the daily period with a NULL label | **0.96%**: 4 of 417 rows dated 2024-09-11 → 2026-10-26 (BRK.B ×3, WFC ×1). Over the daily range by day 0 (368 events): 2, 0.54%. All 1,353 rows, 2020–2026: 37, 2.73% | `events.timing_raw` |
| P2 | Share of labelled events the documents *correct* | **not measurable yet.** Of 19 labelled events looked up, 2 were flipped (10.5%), but GOOGL was added because it was a known error. Of the 18 labelled events in the natural first 19, 1 was flipped (NFLX, 5.6%; 95% interval roughly 0.1% to 27%), and 1 more had another date (MS). Between "1–5%" and "over 5%", with no power to tell | `events.timing_status` of the 20 |
| P3 | Primary daily events after the baseline-minimum rule (≥ 20 clean sessions) | **359** of the 366 daily events with a day 0 have ≥ 20 clean sessions (and ≥ 15 changes). After also requiring snapshots on day −1 and day 0: **350**. Clean sessions per daily event: median 30, 5th percentile 24. Both are upper bounds until the IV rule of milestone 2. *Revised after the review:* 357 and 348 (5th percentile 23.25) with the first EPS window. *Re-counted after the delta review's fixes:* unchanged (359, 350, median 30, 5th percentile 24) | `export/funnel.py`, `baseline_counts` (a scratch script calling it on the committed tables) |

### 6.3 The 20 timed look-ups

The record is `data/manual/press_release_checks.csv`, one row per look-up, in look-up order (the first 19 by announce
date from 2024-08-27 and ticker, then GOOGL). "Label used" and "Status" are from `events.parquet`. The basis says what
the stored time is (ADR 0002 §3): `time_stamp` a release time stamp, `announced_time` the time the company announced
beforehand, `call_time` no time (the label follows from the call time). The source is the kind of page the URL is;
`aggregator` marks a third-party re-host kept because no company or newswire page could be fetched in two searches.

| # | Event | Calendar label | Release (date, time ET) | Basis | Label used | Status | Source | Minutes |
|---:|---|---|---|---|---|---|---|---:|
| 1 | CRWD:2024-08-28 | AMC | 2024-08-28 | `call_time` | AMC | `confirmed` | aggregator | 0.70 |
| 2 | NVDA:2024-08-28 | AMC | 2024-08-28 16:20 | `time_stamp` | AMC | `confirmed` | company | 0.34 |
| 3 | DELL:2024-08-29 | AMC | 2024-08-29 | `call_time` | AMC | `confirmed` | company | 0.30 |
| 4 | AVGO:2024-09-05 | AMC | 2024-09-05 | `call_time` | AMC | `confirmed` | aggregator | 0.36 |
| 5 | ORCL:2024-09-09 | AMC | 2024-09-09 16:05 | `time_stamp` | AMC | `confirmed` | newswire | 0.69 |
| 6 | MU:2024-09-25 | AMC | 2024-09-25 16:07 | `time_stamp` | AMC | `confirmed` | aggregator | 0.30 |
| 7 | COST:2024-09-26 | AMC | 2024-09-26 | `call_time` | AMC | `confirmed` | company | 0.30 |
| 8 | JPM:2024-10-11 | BMO | 2024-10-11 06:55 | `time_stamp` | BMO | `confirmed` | company | 0.65 |
| 9 | WFC:2024-10-11 | NULL | 2024-10-11 07:03 | `time_stamp` | BMO | `inferred` | company | 0.61 |
| 10 | BAC:2024-10-15 | BMO | 2024-10-15 06:45 | `time_stamp` | BMO | `confirmed` | company | 0.27 |
| 11 | GS:2024-10-15 | BMO | 2024-10-15 | `call_time` | BMO | `confirmed` | company | 0.49 |
| 12 | JNJ:2024-10-15 | BMO | 2024-10-15 | `call_time` | BMO | `confirmed` | company | 0.31 |
| 13 | UNH:2024-10-15 | BMO | 2024-10-15 05:55 | `time_stamp` | BMO | `confirmed` | company | 0.58 |
| 14 | MS:2024-10-17 | BMO | 2024-10-16 07:29 | `time_stamp` | BMO | `date_corrected` | newswire | 1.99 |
| 15 | NFLX:2024-10-17 | BMO | 2024-10-17 16:00 | `announced_time` | AMC | `corrected` | company | 0.49 |
| 16 | PG:2024-10-18 | BMO | 2024-10-18 06:55 | `time_stamp` | BMO | `confirmed` | aggregator | 0.29 |
| 17 | GE:2024-10-22 | BMO | 2024-10-22 | `call_time` | BMO | `confirmed` | company | 0.29 |
| 18 | PM:2024-10-22 | BMO | 2024-10-22 06:59 | `time_stamp` | BMO | `confirmed` | company | 0.30 |
| 19 | RTX:2024-10-22 | BMO | 2024-10-22 | `call_time` | BMO | `confirmed` | company | 0.29 |
| 20 | GOOGL:2024-10-29 | BMO | 2024-10-29 | `call_time` | AMC | `corrected` | company | 1.17 |

Look-up time: 10.72 minutes in total (the sum of `lookup_minutes`), mean 0.536, median 0.35, range 0.27 to 1.99.
*Revised after the review:* this page said 10.71. The record was also corrected: JPM's and PM's times are now their
wire time stamps (06:55 and 06:59; they held the announced 07:00 under `call_time`), NFLX's 16:00 is an
`announced_time`, ORCL's PR Newswire stamp is 16:05 (a re-host showed 16:10), and seven third-party URLs were replaced
by company or newswire pages (NVDA, ORCL, WFC, UNH, MS, NFLX, PM). For NVDA, WFC, UNH, JPM and PM the cited page shows
no time stamp, and the note of the row says where the stored stamp was read; MS's Business Wire URL carries its date
(20241016) in its path, but the page refused automated fetches. Four rows stay `aggregator` (CRWD, AVGO, MU, PG).
*Revised after the delta review* (claim 8): NFLX's URL was the 2024-09-13 pre-announcement and JPM's the call
announcement; they now point to the results (Netflix's Q3 2024 letter to shareholders, dated October 17, 2024, since
Netflix issued no separate results press release; JPMorgan Chase's earnings release PDF). A new column, `time_source`,
holds the page on which each stored time was read, required with a time and only with one: the URL itself for ORCL,
BAC, MU and PG; a re-host of the newswire item that shows date, time and EDT for NVDA, JPM, WFC, UNH, MS and PM (each
re-read on 2026-10-29, the Business Wire and GlobeNewswire pages themselves refusing automated fetches); and for NFLX
the pre-announcement, whose "1:00 p.m. Pacific Time" is the stored 16:00 ET. JPM's 06:55 is the time of the Business
Wire notice that the results were out, not of the PDF, which shows none.

### 6.4 Not measured

- The calendar's label error rate (needs the remaining look-ups or EDGAR).
- The blind re-read error rate: no re-read was triggered among the 20.
- EDGAR coverage and accuracy: no request may be made until the owner's contact string is set.
- The status counts, gap contradictions and mean crush **by tercile of `abs_move_cand_max`**: that measure needs the
  option forwards of milestone 2. The funnel says so (`by_move_tercile_status`).
- P3 after removing sessions without a usable IV (milestone 2).
- Whether look-ups are cheaper for a second event of the same company: the 20 were 20 companies.

### 6.5 The EPS period match: sensitivity to the window's lower bound

*Added after the milestone-1 review* ([ledger](../validation/m1-ledger.md), claims 5a–5c), *revised after its delta
review* ([ledger](../validation/m1-delta-ledger.md), claims 1a–1b). The first rule matched a period to the first
calendar event 10 to 100 days after its stored end. The stored end is month-end normalised, so the true end lies in
the stored month, and a report can come before the stored end (Costco: the quarter that ended 2025-05-11 is stored as
2025-05-31 and was reported 2025-05-29) or within 10 days of it (Oracle and Cisco, 8–9 days). The review's rule
started the window on the first day of the period end's month; the delta review showed that this let a report 60–73
days late into the next period's window, where the assignment could move it (its shapes S1, S2, S4, none in the data).
The rule now opens the window **14 days after the first day of the period end's month**, removes **duplicate calendar
rows** first, and pairs periods and events one-to-one, in order, nearest in total (ADR 0002 §3; `events/eps.py`).

Command: `uv run python tools/eps_match_sensitivity.py` (committed tables only, without the one `duplicate_row`;
1,965 periods). "Later-quarter links" are links with a lag of 70 days or more, the next quarter's report: no link of
the rule exceeds 59 days (Berkshire). "Earlier-quarter links" go to an event before the first day of the period end's
month, before the quarter could have ended.

| Lower bound | Assignment | Matched | Orphan | Pre-calendar | Orphan rate | Later-quarter links | Earlier-quarter links | Differs from the rule | Max lag |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| +10 days (before the review) | first in window, tie to smaller lag | 1,316 | 43 | 606 | 3.16% | 8 | 0 | 23 | 100 |
| -31 days | first in window, tie to smaller lag | 1,323 | 36 | 606 | 2.65% | 0 | 1 | 2 | 59 |
| +10 days | one-to-one, nearest in total | 1,316 | 43 | 606 | 3.16% | 8 | 0 | 23 | 100 |
| +0 days | one-to-one, nearest in total | 1,324 | 35 | 606 | 2.58% | 7 | 0 | 14 | 91 |
| -10 days | one-to-one, nearest in total | 1,324 | 35 | 606 | 2.58% | 0 | 0 | 0 | 59 |
| -20 days | one-to-one, nearest in total | 1,324 | 35 | 606 | 2.58% | 0 | 0 | 0 | 59 |
| -31 days | one-to-one, nearest in total | 1,324 | 35 | 606 | 2.58% | 0 | 0 | 0 | 59 |
| -40 days | one-to-one, nearest in total | 1,324 | 35 | 606 | 2.58% | 0 | 0 | 0 | 59 |
| first of the month (before the delta review) | one-to-one, nearest in total | 1,324 | 35 | 606 | 2.58% | 0 | 0 | 0 | 59 |
| first of the month + 7 days | one-to-one, nearest in total | 1,324 | 35 | 606 | 2.58% | 0 | 0 | 0 | 59 |
| first of the month + 14 days (**the rule**) | one-to-one, nearest in total | 1,324 | 35 | 606 | 2.58% | 0 | 0 | 0 | 59 |
| first of the month + 21 days | one-to-one, nearest in total | 1,324 | 35 | 606 | 2.58% | 0 | 0 | 0 | 59 |

- **The lower bound matters only above −10 days after the stored end**, through Costco (lags −1 to −6) and the
  Oracle/Cisco reports 8–9 days after a month-end. From −10 days down to −40, and from the first of the month to 21
  days after it, every count is the rule's: on this data the 14 days change nothing (the earliest report comes 24
  days after the first of its month). They are there for data the calendar does not hold yet: a report 60–73 days
  late.
- **The assignment matters for wide bounds.** With a fixed −31 days and the old "first event in the window, tie to
  the smaller lag", Berkshire's Q4 release of 2025-02-28 (59 days after 2024-12-31, 31 days before 2025-03-31) goes
  to the March quarter: one earlier-quarter link and one false orphan. The one-to-one assignment keeps it with
  December, and the March window, which opens on 03-15, cannot take it. With a fixed −31-day bound and the Q1 report
  missing, even the one-to-one assignment would give the release to the nearer March quarter (31 days against 59)
  (`test_berkshire_shaped_february_report_stays_with_the_december_quarter`).
- **When a link can still move.** *Corrected after the delta review:* this page said that the first-of-the-month
  bound "excludes it structurally". It does not. The one-to-one assignment moves a report to the next period when
  that lowers the total, which happens once the lag passes about 45 days, if the report lies in the next period's
  window. With the window opening on the first of the month that took a lag of 60–63 days: a Berkshire-shaped Q4
  release on 1 March (60 days) with the Q1 report missing would go to March (the delta review's synthetic S4), and a
  slow reporter's whole chain would shift (S2). With the 14 days a report must be **at least 74 days** late (74–77, by
  month) to reach the next period's window; then it moves whenever the next period's own report is missing, and
  even when that report is present if the lag is long enough (from 81–82 days with the next report 30 days after
  its period). No link in the data is longer than 59 days
  (`test_a_link_moves_to_the_next_period_only_from_74_days_late`, `test_s1_…`, `test_s2_…`, `test_s4_…`).
- **Duplicate rows.** BRK.B's Friday 2024-11-01 row (no label) was 32 days after the 2024-09-30 period and its
  Saturday 2024-11-02 release 33, so the period took the duplicate and the sampled release had no EPS. The duplicate
  is now excluded as `duplicate_row` before the match (ADR 0002 §3), and the link is to 2024-11-02.
- **Orphans, 35 (2.58%)**, a partition: 18 are 2021-12-31 periods (8 sessions of early 2022 with no calendar row for
  any company); of the other 17, COST 7 (its February quarters; the calendar has none of its March reports), GS 2
  (2024-06-30, 2024-12-31), AVGO 2 (2022-04-30, 2023-04-30), PLTR 2 (quarters before its 2020-09-30 listing; without
  them 33 / 1,357 = 2.43%), and one each for ANET (2020-12-31), MS (2025-03-31), PG (2020-03-31) and WMT
  (2021-01-31). *Corrected after the delta review:* this said "GS 3, … and one each for 15 more companies", which
  counted GS's 2021-12-31 period twice and the 2021-12-31 companies again. Re-measured after the delta review's
  fixes: unchanged. The rate is below ADR 0002's "about 3%" line, so the owner flag raised at milestone 1 is
  withdrawn.
- **Downstream:** the funnel's last step keeps 350 events, not 348 (§6.1), and P3 is 359 (§6.2). The delta review's
  fixes change neither (re-counted; the duplicate row now leaves at the second step instead of as
  `timing_not_checked`).

---

## 7. Concepts used

- **Trading-session calendar and day 0** — [concept note](../concepts/01-sessions-and-day-zero.md).
- **The EPS period match: duplicate rows first, a window from 14 days after the first of the month, a one-to-one
  assignment nearest in total, orphans**
  — [concept note](../concepts/02-eps-period-match.md).
- **Reading shared data read-only: allowlist, commit pinning, stat versus content fingerprints, a private mirror** —
  [concept note](../concepts/03-shared-data-read-only.md).
- **Put-call parity and the implied spot; testing a timestamp with a level test and a direction test** —
  [concept note](../concepts/04-parity-spot-and-snapshot-time.md).
- **Survivorship bias** — [concept note](../concepts/05-survivorship-bias.md).
- **Bank-discount versus continuously compounded rates** — `events/market.py` header: a 3-month bill quoted at 4.05%
  discount costs 0.9897625 per dollar, a continuous rate of 4.127%.
- **Licence classes per column (U, R, S, F)** — milestone 0 §4.6; now enforced by the registry and the writer.
- **Schema validation at write time, manifests, a parameter hash** — ADR 0001 §1–2, `store.py`, `params.py`.
- **Mutation checking**: every new test module lists the mutations it must catch; each was applied and seen to fail
  (50 mutations; one candidate, "skip the event's own zone", turned out to be equivalent and is noted in
  `tests/test_baseline_funnel.py`).

---

## Appendix: what I ran

Run in this repository on 2026-10-29 (`VOL_DATA_DIR` unset, so `~/data/vol-projects`):

```
uv add exchange-calendars==4.13.2
uv run python -m earnings_vol.ingest.run --only universe      # Wikipedia + 499 Yahoo market caps + eligibility
uv run python -m earnings_vol.ingest.run --only small         # calendar, eps_history, eps_estimate
uv run python -m earnings_vol.ingest.run --only prices        # Yahoo, 50 names + SPY (local)
uv run python -m earnings_vol.ingest.run --only fred          # DTB3, VIXCLS
uv run python -m earnings_vol.ingest.run --only chain --chain-from 2020-01-01   # run twice (before/after the decimal fix)
uv run python -m earnings_vol.events.run
uv run python -m earnings_vol.measures.run
uv run python tools/export_app_data.py
uv run python tools/build_notebooks.py && uv run python tools/build_notebooks.py --check
uv run pytest -q
cd app && npm run verify
```

After the milestone-1 review (same day), with the fixes listed at the end of its ledger:

```
uv run python -m earnings_vol.events.run          # the new EPS match, sample ranges and look-up scope
uv run python -m earnings_vol.measures.run        # session_snapshot unchanged (same bytes); snapshot_close identical
uv run python tools/export_app_data.py            # funnel 1,353 / 1,320 / 366 / 356 / 350
uv run python tools/eps_match_sensitivity.py      # §6.5
uv run python tools/build_notebooks.py && uv run python tools/build_notebooks.py --check
uv run --group diagrams python tools/diagrams/build.py docs/architecture/specs --out docs/architecture/out
uv run python tools/licensing/scan_real_rows.py
uv run pytest -q
cd app && npm run verify
```

The fixes' tests were mutation-checked the same way, on a scratch copy of the tree (never the working tree): 30
mutants (the window's bounds, the assignment, the tie order, the pre-calendar rule, the look-up scope, the sample
ranges, the record's checks, the security columns, the EDGAR guard, the fingerprints, the timestamp check, the I/O
check, the notebook caveat, and a swapped link in a copy of the committed `eps.parquet`). All were killed; one
("a one-label domain such as `a@b` accepted") survived at first, because the top-level-domain rule rejected every
input, and was killed by adding `x@corp` to the test.

After the delta review (same day), with the fixes listed at the end of [its ledger](../validation/m1-delta-ledger.md):

```
uv run --frozen python -m earnings_vol.events.run      # duplicate rows, the 14-day window: 2 events rows, 1 eps row change
uv run --frozen python -m earnings_vol.measures.run    # session_snapshot unchanged (same bytes); snapshot_close identical
uv run --frozen python tools/export_app_data.py        # funnel 1,353 / 1,320 / 366 / 356 / 350 (unchanged)
uv run --frozen python tools/eps_match_sensitivity.py  # §6.5
uv run --frozen python tools/build_notebooks.py && uv run --frozen python tools/build_notebooks.py --check
uv run --frozen --group diagrams python tools/diagrams/build.py docs/architecture/specs --out docs/architecture/out
uv run --frozen --group diagrams --with playwright==1.64.1 python tools/diagrams/build.py docs/architecture/specs --verify-mermaid
uv run --frozen python tools/licensing/scan_real_rows.py
uv run --frozen pytest -q -p no:cacheprovider
cd app && npm run verify
```

The delta review's probes `pd01` and `pd02` were re-run unmodified and, in a scratch copy with `"month_start"` replaced
by `"month_start+14"`, against the new rule; the first review's `p07` was re-run unmodified (results in the delta
ledger's "Fixes applied"). The new tests were mutation-checked on a scratch copy: 30 mutants plus two corruptions of a
copy of the committed tables, all killed, and the 17 I/O forms of `pd08` against the new `test_layering`, all killed.

The mirrors were first made by hand with `cp -a` and the fingerprints compared with `find … -printf '%P\t%s\t%T@'`
before and after; `refresh_mirror` does the same in code and found them current afterwards. Mutation checks: a script
outside the repository applied 50 mutations one at a time to `src/` and `tools/` (listed in each test module's
docstring), ran the named tests, and restored the bytes (checked by SHA-256). 47 made a test fail at once; two
survived until a test was added for them (the sample decided by `announce_date`, and the exclusion order); one
(skipping the event's own zone in `clean_baseline`) is equivalent and cannot fail, as the docstring of
`tests/test_baseline_funnel.py` says. One more check corrupted one `fiscal_period_end` in the committed
`events.parquet` (restored after) and `test_3_events_fiscal_period_end_is_the_linked_copy` failed. The app's
mutations were run by the agent that built the Sample page (listed in its report, all killed).

**Not done:** the remaining 453 look-ups (owner default); any EDGAR request; `npm ci`. The adversarial review of this
milestone was run on 2026-10-29 ([ledger](../validation/m1-ledger.md)); its fixes were reviewed again the same day
([delta ledger](../validation/m1-delta-ledger.md)), and the delta review's fixes, listed at the end of that ledger,
have not been reviewed again.
