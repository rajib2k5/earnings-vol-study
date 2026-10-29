# ADR 0002: Day 0 is the first session whose closing snapshot reflects the news

- **Status:** Accepted (milestone 0), **revised 2026-10-28 after the milestone-0 methodology review**, **again
  after the milestone-0 delta review**, **on 2026-10-29 after the milestone-1 review**, and **again the same day after
  its delta review** (notes below). **The EDGAR rule (§3, source 1) is Accepted 2026-10-28; it
  runs once the owner's contact string is set** (milestone-1 note). Until then the **default rule** of §3 applies: the
  press release decides, then the calendar label. At milestone 1 only the first 20 look-ups were done; the rest wait
  for EDGAR (owner default, 2026-10-29), so most labels are still the calendar's (`not_checked`).
- **Date:** 2026-10-28
- **Related:** [0001](0001-overall-architecture.md), [0003](0003-iv-measures.md), [0004](0004-baseline-and-event-windows.md),
  [data model](../architecture/data-model.md) (`events`, `timing_check`, `session`)

> **Revised after milestone-0 review** ([ledger](../validation/m0-methodology-ledger.md)).
>
> 1. **Refuted (claim 2, N5): "the gap check cannot systematically bias the sample toward big movers".**
>    - With the rule exactly as written, quiet events were excluded far more often than big movers: 9.2% against 0.4%
>      of the extreme |move| terciles.
>    - Quiet events' wrong labels were corrected far less often: 6.4% against 88.9%.
>    - The rule also never said whether a hand-checked `date_suspect` event goes back into the sample.
>    - **Changed:** §3. The label now comes from documents, which do not depend on the move: primarily SEC EDGAR 8-K
>      Item 2.02 acceptance times in this revision, since marked *Proposed: pending owner decision* (next note). The price gap is a local diagnostic. It never sets a label and never excludes an
>      event.
> 2. **Inconsistent (N6):** a weekend or holiday release with a NULL label was classed `ambiguous`, although its day 0
>    does not depend on timing. **Changed:** it is no longer `ambiguous` (§3).
> 3. **Unsettled (N10):** a NULL label could be set by Yahoo gaps alone, which does not fit the class-F rationale.
>    **Changed:** no label is set by prices alone (§3, data model §2.1).
> 4. **Inconsistent with the data model:** §1 called `stale_copy` a status, but the data model has it as a drop reason.
>    **Changed:** §1 now matches the data model.
> 5. **A second adversarial review** attacked the first draft of this revision. It found that the claim "documents
>    remove all outcome dependence" was too strong, and two holes in the EDGAR rule. **Changed** in §3:
>    - Gap-triggered hand checks still correct document errors preferentially for big movers. This is now stated,
>      bounded by the audit, and tested by a sensitivity analysis. *(The delta review refuted "bounded by the
>      audit"; see the delta note below.)*
>    - EDGAR is closed on two federal holidays that are NYSE sessions. On those days its timestamps are not read as
>      timing.
>    - A status row was missing: the 8-K contradicts the label, but the press release agrees with it.

> **Status of the EDGAR rule: Proposed: pending owner decision** (added 2026-10-28, after the revision above).
>
> - **Why.** The owner's approved plan excluded SEC EDGAR, because SEC's fair-access policy requires a real contact
>   email in the User-Agent of every request. Making EDGAR the primary timing source reverses that plan, so only the
>   owner can decide it.
> - **The default if the owner declines** (rewritten after the delta review, next note) is §3's "The default rule":
>   1. the company's press release decides; it is looked up for **every event that can fall in `daily` or
>      `mixed`**, and for every event with a NULL label;
>   2. the calendar label (`earnings_calendar.when`) is kept only where no release is found, or, in the `coarse`
>      robustness sample, where nobody looked.
>
>   The price gap stays a local diagnostic that never sets a label. In `daily` and `mixed` it only triggers a second
>   reading of the release. In `coarse` it decides which labelled events are looked up, and the selection that leaves
>   is stated with its measured size. Under the default, `timing_source` is `press_release` or `calendar`, and
>   `timing_status` is class F (Consequences, "Licensing").
> - **The EDGAR-only columns** (`events.edgar_accession`, `events.edgar_accepted_utc`, and the `edgar` value of
>   `timing_source`) stay in the data model, marked "only if the owner approves EDGAR".
> - **Requests already made.** During design the architect made 3 GET requests to `data.sec.gov/submissions/`, one
>   each for GOOGL, NFLX and AAPL. The User-Agent carried a placeholder contact (`admin@example.org`), and no personal
>   data was sent. They produced the acceptance times quoted in §3. A real run needs a contact string that the owner
>   chooses.

> **Revised after the milestone-0 delta review** ([delta ledger](../validation/m0-delta-ledger.md), claims 4a–4c, N1,
> N7, 9c, 9d). The default rule is the operative one until the owner decides on EDGAR, and the review refuted what
> this ADR said about it:
>
> 1. **Refuted (4b-i): "the default is fully specified, including events nobody checked".** A NULL-label event had no
>    rule. Its trigger, "the gap contradicts the label", needs a label, so whether it was looked up was undefined.
>    **Changed:** every NULL-label event, in every sample, gets a press-release look-up (§3, "The default rule").
> 2. **Refuted (4b-ii): `unverified` meant two things.** The data model and the milestone doc defined it as "no
>    document found". This ADR also gave it to every event nobody looked up, which under the old default was 73–84%
>    of the events in each move tercile (`d4_default_gap_selection.py`). **Changed:** `unverified` is split into
>    `no_document` (looked up, nothing found) and `not_checked` (never looked up), here, in data model §3.7 and in
>    the milestone doc.
> 3. **Refuted (4c): "the label … does not differ in accuracy between quiet events and big movers"** (old
>    Consequences), **and "its effect … is bounded by … the stratified audit"** (old §3, jobs 1 and 3).
>    - Under the old default (gap-triggered checks, every NULL looked up, the 17/17/16 audit), kept events had a
>      wrong day 0 in 2.11 / 1.66 / 0.30% (t₃ gaps) and 2.63 / 2.18 / 0.61% (normal gaps) of the lowest / middle /
>      highest true-move tercile. That is `d4` at the real scale, 2,000 samples of 365 events. It was re-run for
>      this revision, and it reproduced every figure the ledger quotes.
>    - The audit could not bound it. In the lowest tercile, where the true residual rate was 4.2%, its 17 events
>      found no error in 48% of samples.
>    - **Decision: route (a)**, look up the press release of every event that can fall in `daily` or `mixed`. §3,
>      "The default rule", gives the numbers behind it. The 50-event audit is deleted. The `coarse` robustness sample
>      keeps a gap-triggered check, and its measured selection is stated, not claimed to be bounded.
> 4. **Refuted (N7): the |r₀|-tercile trend test** (old §3 job 2 and "How we'll know it's wrong").
>    - |r₀| was measured on the day 0 used, so a mislabelled event shows an ordinary day's move and lands in the low
>      tercile. With errors uniform in the true move, wrong day 0 by that tercile was 7.32 / 1.61 / 0.17% (`d4`,
>      control C0, t₃), so the test fired in every world.
>    - **Changed:** the terciles are of `abs_move_cand_max`, the larger parity-forward move over the two candidate
>      day-0 sessions. It does not depend on the BMO/AMC label (it does depend on the date: §3). The C0 control's flatness on it
>      (2.97 / 3.05 / 2.96%, t₃) is no evidence for the measure, since any label-free measure is flat there (delta-2
>      review, claim 2), and the real dependence of the old default without its audit shows through
>      (2.62 / 1.90 / 0.31%). These two rows come from an extension of `d4`, now in the repository as
>      `research/prototypes/route_a_vs_b.py` with its output `route_a_vs_b.out.txt`.
> 5. **Unmarked (4a).** Four passages stated EDGAR's consequences as settled: two Consequences bullets ("EDGAR
>    timestamps resolve both"; "EDGAR becomes an input …" with its hand-check cost) and the Alternatives row. They
>    are now scoped "under the proposed EDGAR rule".
> 6. **Not stated (N1).** The Alternatives row "hand-check every event's press release" was rejected because "EDGAR
>    gives the same fact mechanically". That reason disappears if the owner declines EDGAR. It is now the default.
> 7. **Hygiene (9c, 9d).** The DoltHub option values quoted in Context now carry a CC BY-SA 4.0 attribution. Quoted
>    stock prices are called official opens and closes.
> 8. **Found while fixing, and changed.** A release time inside the session (09:30–16:00) had no reading rule. It
>    now maps like a BMO release (§3). The record of each look-up had no home; it is now a committed file (data model
>    §1.3).
> 9. **Found while fixing, not changed.** Under the proposed EDGAR rule, job 1's gap-triggered press-release check
>    also puts a Yahoo-derived bit into `timing_status`. So "class U under the EDGAR rule" (Consequences, data model
>    §2.1, ADR 0001 §7) holds only if job 1 is dropped. That is settled when the owner decides on EDGAR.

> **Milestone 1, 2026-10-29: owner decisions and what was measured.**
>
> 1. **EDGAR: Accepted 2026-10-28; runs once the owner's contact string is set.** The owner approved EDGAR on
>    2026-10-28 and will supply the contact string for the User-Agent. It has not arrived. The client
>    (`src/earnings_vol/ingest/edgar.py`) refuses to run while `SEC_EDGAR_USER_AGENT` is unset or holds a placeholder;
>    it has no default. **No request was made to sec.gov or data.sec.gov at milestone 1**; the client is tested on
>    hand-written fixtures. Until the string is set, the default rule below is operative, `timing_source` is never
>    `edgar`, and the milestone-1 EDGAR check (coverage, the 50-event audit) has not run.
> 2. **Look-ups: default taken 2026-10-29: the remaining look-ups wait for EDGAR; the owner can override.** The first
>    20 look-ups were done and timed. Choice: the first 19 events in look-up order (announce date from 2024-08-27,
>    10 sessions before 2024-09-11, then ticker), plus GOOGL 2024-10-29; NFLX 2024-10-17 was 15th in that order
>    anyway. Each is one row of `data/manual/press_release_checks.csv`.
>    - Result: 16 `confirmed`, 2 `corrected` (GOOGL and NFLX, both BMO → AMC), 1 `date_corrected` (MS: the calendar
>      says 2024-10-17, the release came out on 2024-10-16 at 07:29 ET, BMO), 1 `inferred` (WFC 2024-10-11, a NULL
>      label, BMO).
>    - No gap contradicted a press-release label and no outside flag fired on these 20, so **no blind re-read was
>      triggered**; the re-read error rate is still unmeasured.
>    - Time: 10.72 minutes of agent wall-clock in total (the sum of `lookup_minutes`), mean 0.54, median 0.35, range 0.27 to 1.99 minutes per look-up
>      (the slowest was the MS date correction, then GOOGL, whose release PDF the fetcher could not read). The 20 are
>      20 different companies, so the "one archive per company" saving is not measured.
>    - The default rule requires 473 look-ups for the 50 companies (422 because D falls from 2024-08-27 to the data
>      end, 30 NULL labels in a sample, 43 gap-triggered `coarse` events; some events have two reasons). At the mean
>      that is about 4.3 hours of agent time; the 453 left would take about 4.1 hours.
>    - Every other event keeps the calendar label as `not_checked`. The build invariant ("any other `not_checked`
>      event is a build error") is therefore **reported, not enforced**, while `params.yaml` says
>      `timing.lookups_complete: false`; the manifests, the funnel JSON and the app say the labels are provisional.
>      A NULL-label event on a session day that nobody looked up has no day 0; it is excluded as
>      `timing_not_checked` (32 events, 2 of them in the daily range; *revised after the delta review:* this said 33,
>      which counted BRK.B's duplicate row of 2024-11-01, now excluded as `duplicate_row`, note 3).
>    - The calendar's error rate cannot be read off these 20: GOOGL was added because it was a known error. Among the
>      18 labelled events of the first 19, 1 was corrected (NFLX) and 1 had another date (MS).
> 3. **Missing calendar events (GS, COST): default taken 2026-10-29: left as orphan zones, no second source. The owner
>    can override.** Measured with the EPS match as revised after the milestone-1 review (§3, "Missing events are
>    detected"): **35 orphan periods against 1,324 matched, 2.58% of expected events, below the "about 3%" line** of
>    "How we'll know it's wrong", so the decision stays optional and **the owner flag is withdrawn**.
>    The 35, as a partition: **18** are 2021-12-31 periods whose reports fall on 8 sessions of early 2022 for which the
>    DoltHub calendar has no row for any company (2022-01-18, 2022-01-24 to 01-28, 2022-02-10 and 02-11; one of them
>    is GS's); of the other 17, **COST 7** (its February quarters: the calendar has none of its March reports),
>    **GS 2** (2024-06-30, 2024-12-31), **AVGO 2** (2022-04-30, 2023-04-30), **PLTR 2** (2020-03-31 and 06-30, before
>    its 2020-09-30 listing; without them, 33 / 1,357 = 2.43%) and **one each for ANET, MS, PG and WMT**.
>    *Revised after the delta review:* this said "GS 3", which counted GS's 2021-12-31 period twice. The counts are
>    unchanged by the delta review's two fixes to the match (§3), re-measured.
>    - *Revised after the milestone-1 review* ([ledger](../validation/m1-ledger.md), claims 5a–5b). This note first
>      said 43 orphans against 1,316 matched, 3.16%, and flagged the decision for the owner. That count came from the
>      first window (10 to 100 days after the period end): it made 8 false orphans (ORCL ×5, COST ×2, CSCO ×1, whose
>      reports came 8–9 days after a month-end) and gave every COST February period the May event.
>    Also found: one duplicate (BRK.B has a Friday 2024-11-01 row with no label next to the real Saturday 2024-11-02
>    release), and BRK.B's labels are NULL on 19 of 29 rows (Berkshire reports on Saturdays; mostly Friday rows).
>    *Revised after the delta review:* the duplicate is now excluded as `duplicate_row` before the EPS match (§3,
>    "Duplicate calendar rows"). Until then the 2024-09-30 period was linked to it, the nearer row (lag 32 against
>    33), so the sampled release had no EPS.
> 4. **"The snapshot is the close", widened from one event to every after-close event of the daily era**
>    (`src/earnings_vol/measures/snapshot_close.py`; Yahoo closes, local only; only these summaries are published):
>    224 after-close events with D from 2024-09-11 on; 211 had a parity spot (4-strike forward of the shortest
>    expiry with at least 5 sessions, plus the present value of dividends before it).
>    - **The level test of "How we'll know it's wrong" trips as written.** Median |ln(S/Close_D)| is 11.2 bp on AMC
>      days against 6.3 bp on 24,514 ordinary company-days (no event within D−1 … next(D)+1); the difference, 4.9 bp,
>      has a bootstrap 95% interval of 3.0 to 7.4 bp, which excludes zero.
>    - **The direction test says there is no after-hours leak.** If the snapshot were taken after the news, ln(S/Close_D)
>      would move with the next morning's gap ln(Open_{D+1}/Close_D), whose median size on these days is 594 bp. The
>      slope is 0.0018 (SE 0.0030, correlation 0.04, n = 211): at most about 0.8% of the overnight move (upper 95%
>      bound) shows up in the snapshot. Large deviations are rarer on AMC days than on ordinary days (1.4% against 6.7%
>      above 1%).
>    - Reading: the snapshots are closing quotes, and quotes are wider into a release (Context, item 3), which makes the
>      parity spot noisier on AMC days. §2 is **not** changed. Because the rule as written fires, **this is flagged for
>      the owner**: either accept the direction test as the criterion (and amend this bullet), or treat the level test
>      as a failure.
> 5. **The stale-copy evidence, widened.** Over the 50 companies, 2,649 option snapshots fall on non-session days.
>    2,101 of them map to a session that has its own snapshot and were dropped as `stale_copy`: **1,905 are exact
>    copies** of that session's snapshot (the same quotes, row for row; AAPL's Labor Day 2024 quotes have the same
>    digest as Friday 2024-08-30's), and **196 share its quotes but differ in their row set** (most on 2022-01-17,
>    2022-06-20, 2026-05-25 and 2024-01-15). The other **548 are kept as the only snapshot of their session**
>    (all before 2024-09-11, 410 of them dated on a Friday holiday such as Good Friday). No weekday snapshot
>    repeated the previous one exactly (`stale_repeat` = 0 of 57,749 observed company-sessions).
>    - *Revised after the milestone-1 review* (claim 7): this said the 2,101 were all copies; 196 are not exact
>      copies. Dropping them is still right, because the session they map to has its own snapshot.

> **Revised after the milestone-1 review** ([ledger](../validation/m1-ledger.md)), 2026-10-29.
>
> 1. **Refuted (claim 5a, material): "the 10–100-day window assigns each period its own announcement".** Period ends
>    are month-end normalised, so a report can come before the stored end (Costco) or under 10 days after it
>    (Oracle, Cisco). **Changed:** §3, "Missing events are detected": the window starts on the first day of the
>    period end's month, and periods and events are paired one-to-one, in order, nearest in total. The orphan rate
>    is 2.58%, not 3.16%, and the owner flag of milestone-1 note 3 is withdrawn. The primary funnel ends at 350
>    events, not 348.
> 2. **Refuted (claim 3b): the build invariant's sentence and the code disagreed on 29 events.** **Changed:** §3,
>    "Build invariant", is scoped to events that can enter a sample, which is what the code checks, with the reason.
> 3. **Defects in the press-release record (claim 3d).** **Changed:** a fourth basis, `announced_time`, and a
>    `source_kind` column (§3, "How a press release is read", "The record"); JPM's and PM's times are their wire
>    time stamps (06:55, 06:59), and URLs to third-party re-hosts were replaced where a company or newswire page was
>    found.
> 4. **Wording.** Note 5 now separates exact copies from snapshots that only share quotes (claim 7). Current-state
>    passages that still called the EDGAR rule "proposed" now say it was accepted 2026-10-28 and is gated on the
>    owner's contact string; the dated history notes above are left as they were. Context item 3 no longer quotes
>    Yahoo prices.

> **Revised after the milestone-1 delta review** ([ledger](../validation/m1-delta-ledger.md)), 2026-10-29.
>
> 1. **Refuted (claim 1a): a duplicate calendar row took the EPS link.** BRK.B's Friday 2024-11-01 row (no label)
>    sits one day before its Saturday 2024-11-02 release, and min-total-|lag| gave the 2024-09-30 period the nearer
>    row. **Changed:** §3, "Duplicate calendar rows": rows of one security within 14 days of each other are one
>    release; the row with the strongest timing evidence is kept and the others are excluded as `duplicate_row`
>    before the match. Now 2024-09-30 is linked to 2024-11-02 (lag 33).
> 2. **Refuted (claim 1b): "a whole chain never shifts by a quarter to gain a link, because every shifted link costs
>    about 90 days more".** That held only while every lag was under about 45 days. With the window opening on the
>    first of the month, a report 60–73 days late was inside the next period's window, and the minimum total moved
>    it there (the review's shapes S1, S2 and S4). **Changed:** §3, "The window": it opens 14 days after the first
>    of the period end's month, so a link can move only from 74 days late; the sentence is replaced by the exact
>    condition. No count of the real data changed (no link is longer than 59 days).
> 3. **The record (claim 8):** NFLX's and JPM's URLs pointed to a pre-announcement and a call announcement; they now
>    point to the results (Netflix's letter to shareholders, JPMorgan Chase's earnings release). A `time_source`
>    column holds the page each stored time was read on (§3, "The record").

## In one paragraph

Event time is counted in NYSE sessions. **Day 0 is the first session whose *closing* option snapshot was taken
after the announcement.** For a before-market-open (BMO) report that is the announcement date. For an
after-market-close (AMC) report it is the next session. Day −1 is the last session whose closing snapshot came
*before* the news, so the crush is `X(0) − X(−1)` for any IV measure `X`. The calendar's timing label is checked
against **documents**. By default that is the company's press release, looked up for every event in the `daily` and
`mixed` samples. Using the acceptance time of the company's SEC 8-K earnings filing (Item 2.02) instead was
**accepted 2026-10-28, gated on the owner's contact string** (see Status); until that string is set, the press
release decides. The label is never checked against IV, because that would
be circular. It is never *decided* by the stock's price move either, because big moves make price evidence strong,
and a rule driven by them corrects and keeps big movers selectively. The overnight price gap stays as a local
diagnostic. No event is dropped because of how much its stock moved. Two move-dependent steps remain (§3), and
neither is claimed to be bounded: a second reading of a release that the gap contradicts, whose effect a sensitivity
analysis measures, and, in the `coarse` robustness sample only, gap-triggered look-ups, whose selection is stated
with its simulated size.

## Context: what we found in the data

All facts below were measured on 2026-10-28 through the DoltHub SQL API (read-only) and public daily stock prices
(official opens and closes). Section 1 of the [data model](../architecture/data-model.md) has the exact schemas.

*Attribution.* The calendar counts below come from DoltHub `post-no-preference/earnings`. The option quotes, vendor
deltas and parity forwards quoted under "When the option snapshot is taken" come from DoltHub
`post-no-preference/options`. Both datasets are licensed CC BY-SA 4.0 (data model §1.1, §1.2), and the values
quoted here are shared under the same licence.

**The earnings calendar** (`earnings.earnings_calendar(act_symbol, date, when)`) holds 122,113 rows from
2020-01-22 to 2026-12-04. That end date is in the future, so the table also holds *scheduled or projected* dates.
`when` takes exactly three values:

| `when` | rows | share |
|---|---:|---:|
| `After market close` | 50,915 | 41.7% |
| `Before market open` | 39,487 | 32.3% |
| NULL | 31,711 | 26.0% |

There is no "during market" value. For 30 large S&P 500 names (2020 → 2026, 784 rows), NULL timing is rare: 9 rows,
1.1% (GS 2, IBM 1, INTC 1, ORCL 5). But **labels are sometimes wrong, and events are sometimes missing**:

| Finding | Evidence |
|---|---|
| GOOGL 2024-10-29 is labelled BMO; Alphabet reported after the close | Overnight gap into 10-29: under 1%. Overnight gap into 10-30: **over 6%** (the official open against the previous official close; Yahoo values, so only their size is given, 2026-10-29). |
| NFLX 2024-10-17 is labelled BMO; Netflix reported after the close | Gap into 10-17: under 1%. Gap into 10-18: **over 7%** (split-adjusted Yahoo prices; only their size is given, 2026-10-29). |
| ADBE 2020-12-10 and 2021-12-16 are labelled BMO | Adobe reports after the close; not price-checked (outside the daily sample). |
| GS has no calendar row for July 2024 or January 2025 | The calendar jumps 2024-04-15 → 2024-10-15 → 2025-04-14, yet `eps_history` has GS periods 2024-06-30 and 2024-12-31. |
| COST has 20 rows where 27 are expected | Gaps of 113–114 sessions between events. Costco's 16-week Q4 explains gaps of about 82 sessions, but not 113–114. |
| META's history before June 2022 is under `FB` | Calendar `FB` until 2022-04-27, `META` from 2022-07-27. `eps_history` has *both* tickers for periods 2021-12-31 and 2022-03-31. |

Two of the three verified label errors (GOOGL, NFLX) fall inside the daily option sample, so this problem is not
hypothetical.

**When the option snapshot is taken.** `option_chain` has no timestamp and no underlying-price column. The evidence
says each snapshot shows the **closing market of the session named in `date`**:

1. *The commit times.* The publisher commits `option_chain <D> update` at about 06:35 UTC on D+1, which is 02:35
   New York time. The scrape therefore happens some time after D's close.
2. *The forward matches the close.* AAPL on 2025-10-31: the put-call-parity forward from four near-the-money
   strikes of the 2025-11-14 expiry is 270.543 to 270.555. Remove 14 days of carry at 3.9% and the $0.26 dividend
   (ex-date 2025-11-10), and the implied spot is ≈ 270.41, within a few cents of the official close.
3. *After-hours prices were not used on an AMC day.* On 2025-10-30 Apple reported after the close. The vendor
   deltas on that snapshot imply a spot of ≈ 270.9, within a fraction of a percent of the official close and far
   below the next morning's official open. *(Edited 2026-10-29: the official prices are no longer quoted here;
   they are Yahoo values, which the repository does not publish.)*
   Quotes were also visibly wider into the release: the 262.5 call was 10.85/13.35 on 10-30, against 11.20/11.70
   the day before and 10.05/10.20 the day after. That is what closing quotes into an after-close release look like.
4. *Non-session dates are stale copies.* `volatility_history` on Labor Day 2024 (2024-09-02) repeats AAPL's
   2024-08-30 row field for field. 2025 has 259 snapshot dates against 250 NYSE sessions. Before 2020 the
   snapshots are dated **Saturdays**; they reflect the previous Friday.

This is **one event examined in detail**. Milestone 1 repeats check 3 on every AMC event (see "How we'll know it's
wrong").

**Snapshot frequency** (`volatility_history`, which shares commits with `option_chain`):

| Period | Frequency | Snapshot dates |
|---|---|---|
| 2019-02-09 → 2020-01-04 | weekly, Saturdays | 48 in 2019 |
| 2020-01-06 → 2024-09-09 | Mon/Wed/Fri, including holidays as stale copies, plus the odd extra day (e.g. Tue 2020-06-09) | ≈150 per year |
| **2024-09-11 → present** | **daily**, plus copies on some holidays | 259 in 2025 |

So the daily sample starts on **2024-09-11, not around October 2024**. Some single days are missing, for example
2024-11-12.

## Decision

### 1. Sessions and snapshots

- **The clock is NYSE sessions** (holidays and early closes from `exchange_calendars`' XNYS calendar, pinned). An
  early-close day (13:00) is a session; its snapshot is the 13:00 close.
- **Mapping a snapshot to a session:** `as_of_session(snapshot_date)` is the snapshot date if that is a session,
  otherwise the last session before it.
  - **Two snapshots on one session.** If two snapshots map to the same session (a holiday copy and the real day, or
    a Saturday and a Friday), keep the one dated on the session and drop the other.
  - `stale_copy` is the **drop reason** recorded for that duplicate, and counted in the stage manifest. It is not a
    session status. The session's `snapshot_status` comes from the snapshot kept (data model §3.6). *Revised after
    the review:* this sentence used to call `stale_copy` a status.
  - A weekday snapshot whose bids and asks equal the previous session's exactly, for every row of the
  symbol, is `stale_repeat`. No measure uses it, but its rows stay in `chain_expiry` with status `stale` so the
  decision can be audited (data model §3.5). Missing sessions are **never imputed**.

### 2. Day 0

Let `D` be the calendar's announcement date and `next(s)` the next session after `s`.

| Timing used | Day 0 | Day −1 |
|---|---|---|
| BMO, D is a session | D | the session before D |
| AMC, D is a session | next(D) | D |
| Any timing, D is not a session (weekend or holiday release) | the first session after D | the last session before D |
| NULL timing, timing taken from a document (§3, `inferred`) | as for the inferred label | as for the inferred label |
| NULL timing and no document (§3, `ambiguous`) | excluded from the primary sample. Kept as a robustness **measure**, a **two-session** crush `X(next(D)) − X(prev(D))` that contains the news under either timing (`event_measures.crush_two_session_*`). It has no `sample` label of its own; its rows are reported separately in `results`. | |

Worked cases. These become the oracle table for `events.day0()`:

| Example | D | Label | Day −1 | Day 0 | Note |
|---|---|---|---|---|---|
| AAPL Q4 FY25 | Thu 2025-10-30 | AMC | 2025-10-30 | Fri 2025-10-31 | |
| JPM Q3 2025 | Tue 2025-10-14 | BMO | Mon 2025-10-13 | 2025-10-14 | Columbus Day is an NYSE session |
| hypothetical | Fri 2025-11-07 | AMC | 2025-11-07 | Mon 2025-11-10 | weekend in between |
| hypothetical | Wed 2025-11-26 | AMC | 2025-11-26 | Fri 2025-11-28 | Thanksgiving skipped; day 0 is a 13:00 half session |
| hypothetical | Thu 2025-07-03 (half day) | AMC | 2025-07-03 | Mon 2025-07-07 | 07-04 holiday |
| hypothetical | Sat 2025-05-03 | any | Fri 2025-05-02 | Mon 2025-05-05 | weekend release |
| GOOGL Q3 2024 | Tue 2024-10-29 | BMO (calendar); AMC per the 8-K and the price gap | 2024-10-29 | Wed 2024-10-30 | 8-K accepted 16:01 ET (measured, §3). Press release looked up 2026-10-29: call at 13:30 PT, after the close, so `corrected` to AMC. |
| NFLX Q3 2024 | Thu 2024-10-17 | BMO (calendar); AMC per the 8-K and the price gap | 2024-10-17 | Fri 2024-10-18 | 8-K accepted 16:01 ET (measured, §3). Press release looked up 2026-10-29: results at about 13:00 PT (16:00 ET), so `corrected` to AMC. |

`rel_day` counts sessions from day 0. It is negative before and positive after. There is no day "−0".

### 3. Establishing the timing label: documents decide, prices only diagnose

*Revised after the milestone-0 review* ([ledger](../validation/m0-methodology-ledger.md) claim 2, N5, N6, N10). The
first version let the overnight price gap correct labels and exclude events, and claimed this "cannot systematically
bias the sample toward big movers". The review refuted that with the rule exactly as written (`p02_gap_selection.py`,
400,000 simulated events, 3% wrong labels):

- **Exclusion fell on quiet events.** 9.2% of the lowest |move| tercile was excluded, against 0.4% of the highest
  (heavy-tailed gaps). Most of it came from `date_suspect`, where an ordinary large gap on a nearby day outranks a
  small event.
- **Corrections went to big movers.** 88.9% of the wrong labels among big movers were corrected, against 6.4% among
  quiet events.
- **So the kept quiet events had a wrong day 0 far more often:** 6.8% against 0.4%.
- **The effect on the crush:** the mean measured crush of the lowest tercile was attenuated (−0.112 against a true
  −0.120), and a spurious slope of crush on |r₀| appeared.

Any rule in which a price move decides a label has this property, because big moves are what make the price evidence
strong. Hence the decision:

**The timing label is a fact about the company and is taken from documents. The price gap never sets a label and
never excludes an event.**

**Sources, in order:**

*Source 1 was accepted by the owner on 2026-10-28 and runs once the owner's contact string is set (milestone-1 note).
Until then sources 2 and 3 are the chain, applied as "The default rule" below.*

1. **SEC EDGAR, Form 8-K Item 2.02 ("Results of Operations"), acceptance time.**
   - EDGAR is US-government public data, with licence class U (data model §2.1).
   - One JSON file per security, `data.sec.gov/submissions/CIK##########.json`, lists every filing's `form`, `items`
     and `acceptanceDateTime` (UTC). It is fetched once per security under SEC's fair-access policy (at most 10
     requests a second, with an identifying User-Agent).
   - **Which filing.** For a calendar event on D, take the 8-K whose `items` include 2.02 and whose acceptance time,
     converted to New York time, falls on D−1, D or D+1.
   - **How to read the time.** Accepted before 09:30 on a session: BMO on that session. Accepted at or after 16:00
     (13:00 on a half day): AMC on that day. In between: `during_session`, which is hand-checked. Accepted on a
     non-session day: the release was outside market hours, and day 0 is the next session.
   - **EDGAR's own holidays** (added after the second review). EDGAR does not accept filings on US federal holidays,
     and two of them are NYSE sessions: Columbus Day and Veterans Day.
     - When D, D−1 or D+1 is such a day, the 8-K's acceptance time is **not** read as timing.
     - A BMO release on Columbus Day would otherwise be filed the next morning and read as "BMO on D+1".
     - The press release decides instead, as in source 2.
   - *Measured on 2026-10-28 for three securities.*
     - GOOGL 2024-10-29 was accepted at 20:01:46 UTC, which is 16:01 EDT. NFLX 2024-10-17 was accepted at 16:01 EDT.
       Both of the calendar's price-verified errors therefore come out AMC from EDGAR alone, with no price data.
     - AAPL's four 2025 releases were accepted at 16:30 New York time in both EDT and EST (20:30 or 21:30 UTC).
     - Seven events is evidence that the field means what it says, not a validation. Milestone 1 validates it
       (below).
2. **The company's press release (hand look-up).** Under the default rule (below) it is read for every event that
   can fall in `daily` or `mixed`, for every NULL-label event, and for `coarse` events the gap flags. Under the
   EDGAR rule (accepted 2026-10-28, gated on the owner's contact string) it is used when:
   - EDGAR contradicts the calendar label;
   - EDGAR says `during_session`;
   - no matching 8-K exists;
   - the 8-K falls on a different date than the calendar's D.

   The release decides, read as "How a press release is read" below says.
3. **The calendar label** (`earnings_calendar.when`). It is the label of last resort when a look-up finds no
   document (`no_document`), and, in the `coarse` sample only, the label of an event nobody looked up
   (`not_checked`). Under the EDGAR rule it is also used when EDGAR agrees with it.

| Situation | Status | Label used | Kept in its sample? |
|---|---|---|---|
| A document agrees with the calendar label (the press release; the 8-K under the EDGAR rule) | `confirmed` | the label | yes |
| A document contradicts the label (under the EDGAR rule: the 8-K, with the press release agreeing) | `corrected` | the document's | yes |
| *EDGAR rule only:* the 8-K contradicts the label, but the press release agrees with the label | `confirmed` (`timing_source = press_release`) | the label | yes. Counted as an EDGAR timing error in the milestone-1 check. |
| The label is NULL, and a document gives the timing | `inferred` | the document's | yes |
| The documents put the announcement on another date | `date_corrected` | the documents' date and timing | yes |
| Looked up, no document found; a label is given | `no_document` | the label | yes |
| Looked up, no document found; the label is NULL | `ambiguous` | none | no: the two-session crush of §2 only |
| Never looked up. Allowed only as the build invariant below states. | `not_checked` | the label | yes, in `coarse`. Any other `not_checked` event is a build error. |

*Revised after the delta review (4b-ii).* `no_document` and `not_checked` replace `unverified`, which this ADR gave
to both "nothing found" and "never looked up". The two are different facts: the first is an event whose label could
not be checked, the second one whose label nobody tried to check.

- **A non-session D** (a weekend or holiday release; ledger N6). Day 0 is the first session after D *whatever the
  label says* (§2). Timing therefore cannot make such an event `ambiguous`. Only the date is checked, and the event is
  `confirmed`, `no_document`, `date_corrected`, or in `coarse` `not_checked`. The first version classed a NULL-label
  weekend release as `ambiguous`, which excluded an event whose day 0 was never in doubt.
- **No label is ever set by prices alone** (ledger N10). A NULL label is filled only from a document. Without one the
  event is `ambiguous`.
- **Exclusion depends only on whether a document is found for a NULL-label event, and every NULL-label event is
  looked up.** *Revised after the delta review (4b-i):* if NULL-label events were looked up only on a gap signal,
  exclusion would fall on quiet events (0.91 / 0.71 / 0.12% of the true-move terciles, `d4` reading R2). Whether a
  release is *found* is assumed not to depend on the move; the funnel tests that (job 3 below). The old
  `date_suspect` exclusion is gone. A date the price diagnostic doubts is checked against the documents and then
  kept, either confirmed or corrected.

**The default rule (no EDGAR; it applies until the owner's contact string is set).** *Rewritten after the delta review*
([delta ledger](../validation/m0-delta-ledger.md) 4b, 4c, N1, N7).

- **Who is looked up.**
  - **Every event whose calendar date D is on or after 2024-09-11.** That is every event that can land in `mixed`
    or `daily` under either timing (ADR 0004 §5). Its release is looked up whatever the gap says.
  - **Every event with a NULL label** that can enter a sample: one of its candidate day-0 sessions, D or next(D),
    falls in any sample's date range (ADR 0004 §5), `coarse` included. Without a label there is nothing for the gap
    to contradict, so no trigger could decide.
  - **A labelled event with D before 2024-09-11** only when the gap contradicts its label or the nearby-session flag
    fires (the diagnostic below). The others keep the calendar label as `not_checked`. In practice these are the
    `coarse` events.
  - **Build invariant** (tested at milestone 1; *one statement, revised after the delta-2 review, claim 3, and
    scoped after the milestone-1 review, claim 3b*): **for an event that can enter a sample**, one whose candidate
    day 0, D (if D is a session) or next(D), lies in a sample's date range (ADR 0004 §5), `not_checked` is allowed
    only with `announce_date` more than 10 sessions before 2024-09-11, a non-NULL label and no gap trigger; any other
    `not_checked` event that can enter a sample is a build error. Labelled events with `announce_date` in the 10
    sessions before 2024-09-11 are looked up because a wrong label or date can move their day 0 into `mixed`.
    - *Why the scope.* A look-up matters only through day 0 and the sample. An event that no timing can put in a
      sample never reaches a test or the export: at milestone 1 these are 28 dates scheduled after the data end
      (2026-10-26), whose releases do not exist yet, and 1 NULL-label event of March 2020, before the `coarse`
      sample starts. The unscoped sentence called those 29 build errors, while the code never did (the milestone-1
      review measured 482 against 453). The code (`timing.can_enter_sample`, `timing.lookup_reasons`) and this
      sentence now say the same thing.
    - The `events` layer stops with an error otherwise, so a half-done set of look-ups can never reach the tests or
      the export.
- **How a press release is read.** The company's own release for the quarter, from its investor-relations page or
  the newswire copy it links to. The timing comes from, in order of preference:
  1. the release's time stamp (`time_stamp`);
  2. the release's own words, "after the market close" (`release_text`);
  3. the release time the company announced beforehand (`announced_time`; *added after the milestone-1 review*,
     which found such times recorded as call times);
  4. the earnings-call time it announces (`call_time`).

  Before 09:30 New York time on a session: BMO on that session. At or after 16:00 (13:00 on a half day): AMC.
  *Added after the delta review:* a time in between, which is rare, gives day 0 = D, because D's close follows the
  news. It is stored as `BMO`, which maps to the same day 0, and the record keeps the time. A release on a
  non-session day gives day 0 = the next session (§2). The basis used is recorded, and it says what the stored time
  is: a time is stored only with `time_stamp` or `announced_time`, and the parser refuses any other pairing.
- **The record.** Each look-up is one row of a committed, hand-maintained file, `data/manual/press_release_checks.csv`
  (data model §1.3). The row holds the event, whether a release was found, its date and time, the basis, the URL,
  what kind of source the URL is (`source_kind`: `company`, `newswire`, or `aggregator` for a third-party re-host,
  kept only where neither of the others could be found), the page on which the stored time was read (`time_source`,
  *added after the delta review*: the URL itself when that page shows the time; required with a time and only with
  one) and the date of the look-up. The `events` layer reads it; an event with no row is `not_checked`. Anyone can then
  re-check any hand label. The old rule's look-ups could not offer that, because their trigger was local Yahoo data.
- **The gap re-checks the reading, blind.** When the gap contradicts a press-release label, or the nearby-session flag
  fires, the release is read again by a reader who sees neither the gap's side nor the first reading. The label
  changes only if this second reading disagrees with the first and a third blind reading agrees with the second.
  - *Revised after the delta-2 review* ([ledger](../validation/m0-delta2-ledger.md), claim 1). This used to say the
    step "can only fix misreadings". That was wrong: at t₃ gaps about 21 of the 23 re-reads per 365 events fall on
    labels that were already right. A re-reader primed by the gap who flips 10% of them gives a wrong day 0 of
    2.07 / 1.17 / 0.14% by true-move tercile, as move-dependent as the old default. A blind re-read with a 1% error
    rate gives 0.97 / 0.72 / 0.12%. Requiring a blind third reading to agree means a wrong flip needs two independent
    errors. The simulation behind the table assumes a perfect re-read (`route_a_vs_b.py`), so the re-read error rate
    is measured at milestone 1 on the events it touches.
  - This is the one move-dependent step left in `daily` and `mixed`.
  - Each label it changes is flagged (`events.gap_check_changed`). The funnel reports how many, by tercile. The
    report gives the primary results without those changes as a sensitivity analysis (job 1 below).
- **No audit.** The first revision's 17/17/16 audit is deleted. It could not bound what it was meant to bound
  (delta ledger 4c), and with every `daily` and `mixed` event looked up it has nothing left to sample.

**Why route (a), and the numbers behind it.** The delta review asked for a choice: (a) look up every event's press
release, or (b) keep the partial check and state its selection honestly. Measured in `d4`'s world: samples of 365
events, 3% wrong labels, 1.1% NULL labels, a look-up always right unless the row says otherwise. Wrong day 0 is
among kept events, by tercile of the true move:

| Rule | Look-ups per 365 events | Wrong day 0, low / mid / high tercile |
|---|---|---|
| No check: the calendar label everywhere (control C0) | 0 | 2.96 / 3.01 / 3.01% (t₃ gaps) |
| Old default: gap triggers, every NULL, the 17/17/16 audit | 79.2 (t₃), 58.8 (normal); 50 of them the audit | 2.11 / 1.66 / 0.30% (t₃); 2.63 / 2.18 / 0.61% (normal) |
| (a): every event, the look-up always right | 365 | 0 / 0 / 0 |
| (a), 1% of look-ups misread, no re-read | 365 | 0.99 / 1.02 / 1.01% (t₃) |
| (a), 1% misread, gap-triggered re-read | 387.6 (t₃), 367.8 (normal) | 0.85 / 0.67 / 0.11% (t₃); 0.94 / 0.83 / 0.23% (normal) |
| (a), 5% of releases not found, 1% misread, re-read | 386.4 (t₃), 367.6 (normal) | 0.95 / 0.81 / 0.26% (t₃); 1.05 / 0.93 / 0.37% (normal) |

The first two rows are `docs/validation/probes/m0-delta/d4_default_gap_selection.py`. It was re-run for this
revision with `--nu=3` and `--nu=1e9`, and it reproduced every figure the delta ledger quotes. The (a) rows come from
an extension of `d4` that adds misreadings, missing releases and the re-read. It draws the same world from the same
seed, and its no-check control matches `d4`'s wrong-day-0 shares exactly (the mean crush differs in the 4th decimal). It is `research/prototypes/route_a_vs_b.py`, with its output in `route_a_vs_b.out.txt`, so the (a) rows can be re-run
from the repository.

- **What (a) buys.**
  - The calendar's own errors, about 3% in this world, stop depending on the move.
  - What is left is the reader's misreadings, whose rate is unknown: 1% is an assumption, not a measurement. The
    re-read fixes them more often for big movers. At 1% that leaves a low-minus-high gap of about 0.7 points
    (t₃), against 1.8–2.0 points under the old default.
  - A release that cannot be found leaves the calendar label in place. Its errors stay uniform as long as finding a
    release does not depend on the move, which the funnel tests.
- **What (a) costs.**
  - About 365 `daily` look-ups, plus about 50 for the one `mixed` season, which holds both known errors (GOOGL and
    NFLX 2024).
  - Plus re-reads: 1.6–2.8 per 365 events with normal gaps and 20.0–22.6 with t₃ gaps, in the simulation.
  - Against 58.8–79.2 per 365 under the old default, so about 306–309 more per 365 events under either gap law.
  - The time per look-up has **not** been measured. A company's releases usually sit in one investor-relations
    archive, so the cost may grow more with the number of companies (about 50) than with the number of events.
    That is untested too. A milestone-1 agent with a browser can do the look-ups, and every row stays checkable.
- **What (b) would have cost.** No extra look-ups. But it leaves a known selection on the move: 2.1–2.6% wrong
  day 0 among quiet events against 0.3–0.6% among big movers. The study could describe that selection but not bound
  it or remove it. And H7 (implied against realised moves) and every crush-by-move breakdown condition on exactly
  that variable.
- **What would make (b) win.** Milestone 1 times the first 20 look-ups before doing the rest. If the measured cost
  makes about 415 look-ups impractical, the owner may move `daily` and `mixed` to the `coarse` terms below. That
  must happen **before any IV measure is computed** (milestone 2), so the choice cannot depend on results. The
  switch is recorded in this ADR.

**The `coarse` sample: a partial check, with its selection stated.** Looking up the coarse sample's events (roughly
850–900, an estimate from 50 names over about 18 seasons; milestone 1 counts them) would multiply the cost. Coarse
results are robustness, reported separately and never pooled (ADR 0004 §4). So `coarse` keeps route (b)'s terms.

- **Who is looked up:** a labelled event only on a gap trigger; every NULL-label event; the rest are `not_checked`.
- **The measured selection.** This is the rule as written, without the deleted audit, in `d4`'s world. Wrong day 0
  among kept events is 2.51 / 1.96 / 0.35% (t₃) and 3.04 / 2.56 / 0.70% (normal) across the true-move terciles.
  The mean crush of the lowest tercile is attenuated by 2.4% (t₃) and 3.1% (normal) of the true crush. In the
  highest it is 0.3% and 0.8%. These are from the same extension of `d4`, `research/prototypes/route_a_vs_b.py`.
- **It is not bounded.** No audit is run: 17 events per tercile cannot see a rate of 2–4% (delta ledger 4c).
  Instead the full check of `daily` and `mixed` measures two things: the calendar's error rate, and which of those
  errors the gap trigger would have flagged, by tercile. The coarse sample's expected residual by tercile is computed
  from them and reported as an estimate. It rests on few errors (about 12 at a 3% rate over 415 events), and it
  assumes the calendar erred as often in 2020–2024, which is untested.
- **Every coarse table says** that quiet events there carry more label error than big movers.

**The price gap, kept as a local diagnostic.** For each event, with Yahoo daily prices (local only; columns suffixed
`_yf`, never committed):

$$
g_t = \ln\frac{O_t}{C_{t-1}} - \ln\frac{O^{SPY}_t}{C^{SPY}_{t-1}}, \qquad
z_t = \frac{|g_t|}{\operatorname{median}_{s\in[-60,-22]} |g_s|}
$$

$z_B$ is the value at D when D is a session, and $z_A$ the value at next(D). For a non-session D only next(D) is a
candidate. The diagnostic gives three verdicts:

- **the gap contradicts the label:** the other candidate has $z \ge 4$ and $z \ge 3\times$ the label's;
- **the gap supports the label:** the reverse;
- **quiet:** neither.

A separate flag marks a session in [D−3, D+4], other than the candidates, with $z \ge 6$ and $z \ge 3\max(z_B, z_A)$.
These are the first version's thresholds. They now do three jobs:

1. **Re-check of a document label.** Under the default, a gap that contradicts a press-release label triggers one
   more reading of the release (above). Under the EDGAR rule, a gap that contradicts the 8-K's label
   triggers a press-release check, and an EDGAR error found that way is corrected and counted.
   - *This is the one move-dependent step left wherever every event has a document* (second review). The gap can
     only contradict a label when the stock moved, so document errors are found more often among big movers.
   - It is kept because it fixes real errors. **No audit bounds it.** *Revised after the delta review (4c):* this
     used to say that its effect "is bounded by EDGAR's own error rate, which the stratified audit below measures per
     |r₀| tercile". At 17 events per tercile the audit cannot measure a rate of a few percent. Its size is limited
     by the misreading rate under the default, and by EDGAR's error rate under the EDGAR rule. Neither is known.
   - Its effect is measured directly instead. The report gives the primary results with these corrections, and as a
     sensitivity analysis without them. If the two differ by more than the primary estimate's standard error, the
     difference is reported as a finding.
2. **The trigger for the `coarse` sample's look-ups** (the default rule, above). This is the larger move-dependent
   step, and its measured size is stated there.
3. **Measure of outcome dependence.** The sample funnel reports, by tercile of `event_measures.abs_move_cand_max`:
   - the status counts;
   - the share of gap contradictions, and the number of labels a re-read changed;
   - the mean crush.

   `abs_move_cand_max` is the larger parity-forward move over the two candidate day-0 sessions (prev(D) → D and
   D → next(D), from `chain_expiry` as in ADR 0003 §e; one move, prev(D) → next(D), for a non-session D). It does not
   depend on the BMO/AMC label, and it exists for `ambiguous` events too. *Revised after the delta-2 review (claim 2):*
   D here is the announcement date used: the document's date for a `date_corrected` event, otherwise `announce_date`.
   So the measure does depend on the date. A calendar date error that nobody finds lands in the low tercile: with 1%
   date errors the delta-2 probe gives 2.28 / 0.64 / 0.10% across the terciles. A trend in the `date_corrected` share
   by tercile is therefore expected even when date errors are uniform, and is not read as selection. *Revised after the delta review (N7):* the
   terciles used to be of $|r_0|$ on the day 0 used. A mislabelled event then shows an ordinary day's move and lands
   in the low tercile, so the status mix trended in every world.

   **How to read it.**
   - In `daily` and `mixed`, a trend in the `corrected` share is a fact about the calendar (it errs more for some
     moves), not a bias in the study's labels.
   - A trend in `no_document` or `ambiguous` would mean that finding a release depends on the move. That is a
     selection channel, and it is reported.
   - In `coarse` the status mix trends by construction, because the look-ups are triggered by the move.
   - The mean crush may trend for real reasons: bigger moves come with bigger event variance. It is reported, but it
     is not a test of label quality.

**Milestone-1 check of the EDGAR rule** (it runs once the owner's contact string is set). On the daily sample:

- **Coverage:** at least 95% of events have an Item 2.02 8-K on D−1…D+1.
- **Agreement:** every disagreement with the calendar label is hand-checked.
- **Accuracy:** a random audit of 50 `confirmed` events is checked against press releases. More than one error means
  EDGAR is not trusted, and the default rule above applies.
  - *Revised after the delta review (4c).* The audit was stratified 17/17/16 across the |r₀| terciles and was also
    to catch "errors concentrated in one tercile". At 17 events per tercile it cannot.
  - What it can do, by the binomial distribution with 50 events: it finds at least one error with 95% probability
    only when EDGAR's error rate is 5.8% or more, and more than one error only at 9.1% or more. At a 3% rate it
    finds more than one error 45% of the time. It detects a gross failure. It does not measure a small error rate.

Three design points that matter:

- **We never use IV to validate timing.** The study measures the IV crush on day 0. If IV chose day 0, a crush on day
  0 would follow by construction. That is circular.
- **No event is dropped because of how much its stock moved, and labels come from documents.**
  - This replaces the first version's "We never drop an event because its stock barely moved". That sentence was true
    of the `not_contradicted` rule alone, but false of the rule as a whole: the `date_suspect` exclusion and the
    price-triggered corrections both selected on move size.
  - Where every event has a document, one move-dependent step remains: a gap contradiction can *trigger* a second
    reading (default) or a press-release check (EDGAR rule) that corrects a document error (job 1 above).
    *Revised after the delta review (4c):* this said "its size is bounded and measured". It is measured, by the
    sensitivity analysis without those corrections, but no audit bounds it. It is not claimed to be zero. The
    `coarse` sample keeps a larger step, whose simulated size is stated under "The default rule".
  - Whether a release is found could itself depend on the event. The funnel reports `no_document` and `ambiguous` by
    `abs_move_cand_max` tercile (job 3).
  - *Under the EDGAR rule:* whether a filing exists, or is late, could depend on the event too. In the three
    securities checked, no 8-K was late or missing, but nobody has measured whether lateness relates to the move. The
    milestone-1 coverage check would report missing and late (acceptance after D+1) filings by `abs_move_cand_max`
    tercile.
- **Missing events are detected, not invented.** *Rewritten after the milestone-1 review* ([ledger](../validation/m1-ledger.md),
  claims 5a–5b). Each `eps_history` period is linked to the calendar event that announced it, in two steps.
  - **The window.** `eps_history` stores each period end as the last day of the month the quarter ended in
    (Costco's quarter that ended on Sunday 2025-05-11 is stored as 2025-05-31). The true end is therefore no
    earlier than the first day of that month, and a report comes after the true end. So a period can take an event
    from **14 days after the first day of its period end's month** to **100 days after the stored end**
    (`params.yaml`: `window_start: month_start+14`).
    - *Why 14 days.* Over the 1,324 links, the earliest report comes 24 days after the first of its month
      (Costco's 2023-05-25 report of its quarter stored as 2023-05-31; the next earliest is Oracle at 36), so 14
      days leaves 10 days of margin. The 14 days are what stop a long lag from moving a link (below): a report
      must be at least 74 days late to fall in the next period's window. From +0 to +21 days the real counts do
      not change (milestone 1 §6.5).
    - *History.* The first version's window started 10 days after the stored end. It missed Oracle's and Cisco's
      reports 8–9 days after a month-end and Costco's reports inside the same month, and so made 8 false orphans and
      8 links to the next quarter's report (every Costco February period took the May event). *Revised after the
      delta review:* the window then opened on the first of the month itself, which let a report 60–73 days late
      into the next period's window (below).
  - **The assignment.** Periods and events are paired **one-to-one and in order** (a later period never gets an
    earlier event), choosing the pairing with the smallest total distance, where a link costs |lag| days and a
    period left without an event costs 101 days (`lag_max_days` + 1), more than any link it could have had. 101 is
    derived, not a parameter: it is the smallest cost that never gives a link up for nothing, and a larger one would
    only pull harder towards extra links. When one report is missing, the remaining event goes to the period it is
    nearest to, and the period whose report is missing is the **orphan**. Costco's 2025-02-28 period (its March
    report is absent from the calendar) does not take 2025-05-29 (lag 90) from the 2025-05-31 period (lag −2).
  - **When a link can still move to another period.** *Rewritten after the delta review* (claim 1b). The first
    revision said "a whole chain never shifts by a quarter to gain a link, because every shifted link costs about 90
    days more". That is false for long lags: moving a report of lag L to the next period changes its cost from L to
    about 91 − L, which is cheaper once L passes about 45 days. What is true now:
    - A link can move to the **next** period only when its report lies in that period's window, i.e. **at least 74
      days after its own stored end** (60 days to the first of the month two months on for a December or January
      end, 61–63 otherwise, plus the 14; so 74–77 days). Below that, no pairing can move it.
    - From there, the minimum total moves it whenever the next period's own report is missing, and also when that
      report is present but the late lag is long enough: from 81–82 days when the next report comes 30 days after
      its period. A run of such reports shifts as a chain.
    - A move to the **previous** period never lowers the total, unless a second calendar row of the same release
      sits within about 10 days of it: hence duplicate rows are removed first (below).
    - On the real data the longest lag is 59 days (Berkshire's Q4), so no link is near the 74-day line. These
      statements are checked by tests (`test_a_link_moves_to_the_next_period_only_from_74_days_late`, the delta
      review's shapes S1, S2, S4) and, for the last two, by 30,000 random chains each (0 wrong links with every lag
      at most 73 days; 0 backward moves with lags up to 100).
  - **Duplicate calendar rows.** *Added after the delta review* (claim 1a; note 3 above). Calendar rows of one
    security whose dates in use lie within **14 days** of each other (`eps_match.duplicate_within_days`) are one
    release; two real releases of one company are at least 63 days apart in the data. The row with the strongest
    timing evidence is the release: a press-release (or EDGAR) reading beats a calendar label, which beats nothing.
    If two rows tie, the build stops, because which one is the release is then a look-up's to decide. Every other
    row of the group is excluded as **`duplicate_row`**, the first exclusion reason (data model §3.7). It is never
    linked to an EPS period, and it has **no zone of its own** in other events' baselines: its release's zone is the
    kept row's (ADR 0004 §1). It stays in the `events` table and its prev/next chain, which list calendar rows, and
    it still counts as a required look-up while it is `not_checked` (a look-up of it would settle which row is the
    release). The data hold one: BRK.B 2024-11-01 (Friday, no label) beside the 2024-11-02 release (Saturday, BMO).
  - **Orphan or pre-calendar.** A period left without an event is an orphan (GS 2024-06-30 and 2024-12-31 are
    examples), unless its window starts before the calendar does (2020-01-22) **and** holds no event at all; then
    it is `pre_calendar`. That can only happen to periods ending on or before 2020-01-31. Its event was not missed;
    the calendar simply does not reach back that far. A period whose window holds an event that went to another
    period is an orphan even then: its own event is the one missing.
  - Both kinds of zone, period end + 10 to + 60 sessions, are marked as contaminated for neighbouring events'
    baselines (ADR 0004). The sensitivity of the counts to the window's lower bound is in milestone 1 §6.5.
  Recovering the missing date from a second source is a **milestone-1 decision for the owner**.
  - EDGAR's Item 2.02 8-Ks are the obvious candidate once EDGAR runs (accepted 2026-10-28, gated on the owner's
    contact string), being public domain (not
    checked for GS).
  - Under the default, the press-release look-up of a neighbouring period can supply the date by hand.
  - Yahoo's earnings-dates endpoint would make some event dates Yahoo-derived facts.

### 4. Tickers

A `security` table keys every company by a stable `security_id`. A `ticker_alias` table maps
`(ticker, valid_from, valid_to)` to it: `FB` until 2022-06-08, `META` from 2022-06-09. Calendar rows, EPS rows and
option rows are resolved through the alias before joining. When the same `(security_id, period_end_date)` appears
under two tickers (FB/META 2021-12-31 and 2022-03-31), they are deduplicated. If they disagree the period is
flagged `ticker_conflict` and its EPS values are set to null. That blocks it from the surprise analyses (H5 and the
surprise robustness checks). The event itself stays in the IV tests, because its date and timing are not in doubt.

### 5. What "IV crush" means under this convention

For any IV measure X from ADR 0003:

$$
\text{CRUSH}^X = \ln X(0) - \ln X(-1) \quad\text{(primary, log points)}, \qquad X(0) - X(-1) \quad\text{(vol points, for display)}
$$

- X(−1) is the last close before the news and X(0) the first close after it. **Exactly one session of ordinary
  diffusion plus the news sits between them.**
- Using X(+1) − X(−1) would add a second session of noise for no information. The event variance leaves the
  option price as soon as the news is public. For a BMO release that is before the day-0 open. For an AMC release
  it is overnight. Day 0's close reflects it either way.
- In the daily primary sample, **day −1 and day 0 must both be observed**. Otherwise the event has no crush
  (status `missing_m1` or `missing_0`) and is never imputed. The coarse Mon/Wed/Fri sample has its own rule in
  ADR 0004.
- ADR 0003 explains which X is primary (the event-aware 30-day IV) and how the crush splits into "event variance
  removed" and "change in ordinary volatility".

## Consequences

- Good: day 0 is defined by when the information reaches the closing price, which is the price we observe. The
  convention is the same for BMO and AMC, so mixing them does not smear the crush across two days.
- Good: label errors like GOOGL and NFLX 2024 are caught by a source that depends neither on the variable being
  studied (IV) nor on the size of the move. Under the default, the press release of every `daily` and `mixed` event
  is read. Under the EDGAR rule, EDGAR timestamps would resolve both from the filing alone (measured for
  these two, §3).
- Good: under the default, the label of every `daily` and `mixed` event that has a release is a document fact. So the
  calendar's own errors no longer differ in accuracy between quiet events and big movers.
  - Two small move-dependent effects are left, and both are measured: re-reads fix misreadings more often for big
    movers (the sensitivity analysis), and finding a release might depend on the move (`no_document` by tercile).
  - The `coarse` robustness sample does select on the move, by the simulated amount in §3.
  - *Revised after the delta review (4c):* this bullet used to claim equal accuracy under the old default, whose
    gap-triggered checks left a wrong day 0 in 2.1–2.6% of quiet events against 0.3–0.6% of big movers.
- **Licensing** (revised after the review, and again after the delta review).
  - Under the default, a gap contradiction decides which labels get a second reading, and in `coarse` which events
    are looked up at all. The status then encodes one Yahoo-derived bit per event, so it is class F, as before: the
    label is still a document fact, and no Yahoo value can be recovered from it.
  - *Under the EDGAR rule* (once the contact string is set), `timing_used` and `timing_status` would come from the DoltHub
    calendar, EDGAR (US-government public data) and hand-checked press releases, with no Yahoo value in them: **class
    U** (data model §2.1). That holds only if job 1's gap-triggered check is dropped (delta revision note, item 9).
  - The gap values themselves (`timing_check`, all `_yf`) stay local in every case.
- Cost (default): about 365 `daily` and 50 `mixed` press-release look-ups, plus re-reads (1.6–22.6 per 365 events in
  simulation), plus the `coarse` sample's gap-triggered and NULL-label look-ups. The old default needed 58.8–79.2
  per 365 events. Each look-up is a row of a committed file. The time per look-up is not yet measured; milestone 1
  times the first 20.
- Cost, *under the EDGAR rule* (once the contact string is set): EDGAR becomes an input of the `events` layer. That means
  one extra fetch per security and a parser for its JSON, pinned and cached like the Dolt reads (ADR 0001). Then a
  hand check for every disagreement, every `during_session` filing and every event without an 8-K, plus a 50-event
  audit. At about 365 primary events and a 3% label-error rate, that is a few dozen press releases.
- Cost: orphan periods shrink the sample, and so do `ambiguous` events, which are now only those with neither a label
  nor a document. The funnel makes the loss visible.
- Risk: the snapshot-timing evidence rests on one detailed event plus commit times. Milestone 1 must widen it.

## Alternatives rejected

| Alternative | Why rejected | What would make it win |
|---|---|---|
| Day 0 = announcement date for every event | For AMC events the snapshot on D is taken *before* the news, so the crush would appear on +1. Averaging BMO and AMC events then smears it over two days and halves the day-0 effect. | All events are BMO. |
| Always use a two-session window [−1, +1] (the classic hedge against timing errors) | Every event pays an extra session of noise, and run-up/crush timing becomes blurred. We use it only where the timing really is unknown. | NULL timing becomes common in the sample (it is 1.1% for large caps). |
| Validate timing with the IV drop | Circular, as explained in §3. | Never. |
| Validate with the largest close-to-close \|return\| in [−1, +1] (the PR/FAQ's first idea) | It works, but it is noisier than the overnight gap: it includes the whole day's trading after a BMO release, and it cannot tell "BMO on D" from "AMC on D−1" as sharply. It is kept as a secondary diagnostic. | No open prices are available. |
| Drop every event the gap test does not confirm | Selection on the outcome: it keeps big movers only. | Never for this study. |
| Let the price gap correct labels and exclude `date_suspect` events (the milestone-0 rule) | Selection and differential mislabelling by move size, measured by the review (§3): exclusion 9.2% against 0.4%, wrong day 0 among kept events 6.8% against 0.4%, lowest against highest \|move\| tercile. | No documentary timing source exists, and then only as in the `coarse` sample of §3, where a gap only *triggers* a look-up. |
| Use the calendar label for every event, with no check | Uniform across move sizes, but it keeps known errors such as GOOGL and NFLX 2024 inside the daily sample. | Documents unavailable *and* hand checks unaffordable. |
| Keep the old default for `daily` and `mixed`: gap-triggered look-ups, every NULL looked up, a 17/17/16 audit (route (b); added after the delta review) | It leaves a measured selection on the move, a wrong day 0 in 2.1–2.6% of quiet events against 0.3–0.6% of big movers (`d4`), that no audit of practical size can bound. Kept for `coarse` only. | Milestone 1 measures the look-ups as too costly for about 415 events, and the owner switches before any IV measure is computed (§3). |
| *Under the EDGAR rule:* hand-check every event's press release | About 365 manual look-ups for the primary sample alone, while EDGAR gives the same fact mechanically. **Under the default it is the rule** (§3). *Revised after the delta review (N1):* the row used to reject it outright, but its reason, EDGAR, disappears if the owner declines EDGAR. | EDGAR fails its milestone-1 check, and then it is the rule anyway. |
| Treat a holiday snapshot as a session | It is a stale copy of the previous session. It would add a fake "zero change" day and break session counting. | Never. |

## How we'll know it's wrong

- **The snapshot is not at the close.** For every AMC event, compare the parity-implied spot on day −1 with the
  official close. If the median absolute difference on AMC announcement days exceeds the same statistic on ordinary
  days by more than its own noise (bootstrap 95% CI), the snapshot leaks after-hours information. Day −1 would then
  be partly post-news and §2 must change.
- **The mean IV path has its biggest one-day drop on day +1, not day 0**, for either the BMO or the AMC subsample.
  This check uses IV, but it is *after* the fact and is not used to assign labels. It means the convention or the
  snapshot timing is off for that subsample.
- *Once EDGAR runs (accepted 2026-10-28, gated on the owner's contact string):* **EDGAR fails its milestone-1
  check** (§3): coverage below 95%, or more than
  one error in the 50-event audit. Then the default rule of §3 applies, and this ADR says so. (*Revised after the
  delta review:* "audit errors concentrated in one |r₀| tercile" is dropped, because 17 events per tercile cannot
  show it.)
- **`no_document` or `ambiguous` trends across `abs_move_cand_max` terciles in `daily` and `mixed`.** Finding a
  release would then depend on the move. Investigate those events, and report the trend as a selection channel.
  (*Revised after the delta review, N7:* this used to read "the status mix or the mean crush trends across |r₀|
  terciles", which with |r₀| on the day 0 used fires in every world.)
- **Re-reads change more than about 1% of `daily` and `mixed` labels.** Re-reads only see the misreadings the gap can
  detect, so the misreading rate is at least that high. The re-read's move dependence is then no longer small, and
  every `daily` and `mixed` release gets a second, independent reading.
- **Corrections exceed about 5% of labelled `daily` and `mixed` events.** The calendar is then worse than assumed,
  and the `coarse` sample's `not_checked` events carry more risk than its stated selection. Look them all up too.
- **Orphan periods are common in the 50-name universe** (more than about 3% of expected events, counting `orphan`
  only, not `pre_calendar`). Then the missing-event decision in §3 stops being optional.
