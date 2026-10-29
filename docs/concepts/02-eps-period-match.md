# Matching fiscal periods to announcements (the EPS period match)

Concept note for milestone 1. Written 2026-10-29, revised the same day after the milestone-1 review and again after
its delta review ([ledger](../validation/m1-delta-ledger.md)). The rule is in
[ADR 0002 §3](../adr/0002-day-zero-convention.md) ("Missing events are detected, not invented") and
[data model §3.8](../architecture/data-model.md); the code is `src/earnings_vol/events/eps.py`.

## 1. The problem

Two DoltHub tables describe the same reports from two sides:

- `earnings_calendar` says *when* a company announced: (ticker, date, before/after the market).
- `eps_history` says *what* it announced: (ticker, fiscal period end, reported EPS, consensus estimate).

Nothing links a row of one to a row of the other. Worse, the period ends are **normalised to month-ends**: Apple's
quarter that ended on Saturday 2025-12-27 is stored as 2025-12-31, and Costco's that ended on Sunday 2025-05-11 is
stored as 2025-05-31. So "join on the date" is impossible.

## 2. The window: from 14 days after the first of the month to 100 days after

*Revised after the milestone-1 review* ([ledger](../validation/m1-ledger.md), claim 5a). The first version matched
each period to the first announcement **10 to 100 days** after its stored end, on the idea that nobody reports within a
week of a quarter's end. That idea is right for the *true* end, but the window was measured from the *stored* end:

- Costco reported the quarter above on 2025-05-29, **2 days before** its stored end.
- Oracle and Cisco report about 9 days after a quarter that really does end on a month-end.

So the window now starts from where the normalisation says the true end can start, plus a short delay:

> A period can take an announcement from **14 days after the first day of its period end's month** to **100 days
> after** the stored end.

- *Why the first of the month?* The stored end is the last day of the month the quarter ended in, so the true end is
  no earlier than the first of that month, and a report comes after the true end. A fixed bound such as −31 days is
  looser and admits real mistakes: Berkshire releases its Q4 in late February, and 2025-02-28 is exactly 31 days
  before the March quarter's stored end.
- *Why 14 days after it?* (*Added after the delta review.*) The earliest report in the data comes 24 days after the
  first of its month (Costco), so 14 days lose nothing. They matter for slow reporters: with the window opening on
  the first of the month, a report 60 or more days late was already inside the *next* period's window, and the
  assignment below could move it there (a Berkshire-shaped Q4 release on 1 March, 60 days late, with the March
  quarter's report missing, would have gone to March; the data hold no such case). With the 14 days a report must be
  at least 74 days late to reach the next period.
- *Why 100?* A large company files its annual report within about 60–90 days; no link in this data is longer than
  59 days. 100 leaves room, and the assignment below stops it from taking the next quarter's report.

## 3. The assignment: one-to-one, in order, nearest in total

A window can hold two reports: its own and the next quarter's (Costco's February period reaches 2025-05-29, 90 days
later). So the matcher does not take "the first event in the window". It pairs periods and events **one-to-one and in
order** (a later period never gets an earlier event), choosing the pairing with the **smallest total distance**: a link
costs |lag| days, and a period left without an event costs 101 days, more than any link it could have had.

**Example (the test `test_costco_shaped_quarters_link_to_their_own_reports`).** Costco's periods 2024-11-30,
2025-02-28, 2025-05-31 and 2025-08-31; the calendar has its reports of 2024-12-12, 2025-05-29 and 2025-09-25, but not
its March report. Giving 05-29 to February (lag 90) leaves May without an event: 90 + 101 = 191. Giving it to May
(lag −2) leaves February without one: 2 + 101 = 103. So **February is the orphan**, and May keeps its own report.

Two tempting mistakes, both tested:

1. **"The first event in the window"**, or letting a period whose report is missing take the next one. That event
   belongs to a later period, and every later match would shift by one quarter. The total-distance rule does not
   shift a chain of ordinary reports (`test_a_chain_does_not_shift_to_gain_a_link`), but it is not immune: moving a
   report of lag L to the next period changes its cost from L to about 91 − L, which is cheaper once L passes about
   45 days. *Corrected after the delta review:* this note said "never", which is false for long lags. The window's
   14 days are what keep a move out of reach until a report is 74 days late; the longest lag in the data is 59
   (`test_a_link_moves_to_the_next_period_only_from_74_days_late`).
2. **Dropping the orphan.** A missing announcement still happened in the market. Its IV crush is somewhere in the data,
   so the sessions around it (period end + 10 to + 60 sessions) are removed from other events' baselines.

A period whose window starts before the calendar does (2020-01-22) and holds no event at all is **pre_calendar**: its
report was not missed, the calendar just does not reach back that far. Its zone is removed from baselines too, but it
does not count as a data error. A period whose window holds an event that went to another period is an orphan even
then: its own report is the missing one.

## 4. What milestone 1 found

On the 50 companies: 1,324 matched periods, 35 orphans and 606 pre-calendar periods (most of `eps_history` reaches
back to 2016). The orphan rate is 35 / (1,324 + 35) = 2.58%, under ADR 0002's 3% line. Most orphans come from gaps in
the DoltHub calendar itself: it has no row at all, for any company, on 8 sessions of early 2022 (2022-01-18, 2022-01-24
to 2022-01-28, 2022-02-10 and 2022-02-11). That removed the 2021-12-31 reports of 18 of the 50 companies. Costco's 7
are its February quarters (the calendar has none of its March reports). The other 10: GS 2, AVGO 2, PLTR 2
(quarters before its 2020-09-30 listing), and one each for ANET, MS, PG and WMT. (*Corrected after the delta
review:* this said "GS has 3", counting GS's 2021-12-31 period twice.)

**Duplicate calendar rows** (*added after the delta review*). BRK.B has a Friday 2024-11-01 row with no label beside
its Saturday 2024-11-02 release. The Friday row was nearer the 2024-09-30 period (lag 32 against 33), so it took the
EPS link and the real release had none. Now calendar rows of one company within 14 days of each other are one
release: the row with the strongest timing evidence is kept, and the others are excluded as `duplicate_row` before
the match.

The first window gave 1,316 / 43 / 3.16%: 8 false orphans (Oracle ×5, Costco ×2, Cisco) and 8 links to the next
quarter's report. Milestone 1 §6.5 shows how the counts move with the lower bound
(`uv run python tools/eps_match_sensitivity.py`).

**Tickers.** Facebook's history is filed under both `FB` and `META` (and United Technologies' under `UTX` and `RTX`).
Two rows for one company and period are merged when they agree; if they disagreed, the period would be
`ticker_conflict` and its EPS values set to null. None disagreed.

## 5. Things to be able to say in an interview

- Why a window and not a join (month-end normalisation, two tables with no key in common).
- Why the window starts 14 days after the first of the month, not 10 days after the stored end, not at a fixed
  −31 days, and not on the first of the month itself; and exactly when a link can still move to the next period
  (from 74 days late).
- Why a one-to-one, in-order assignment by total distance, and not "the first event in the window".
- What an orphan is, why it is kept as a contaminated zone, and why a period whose report is missing must not take
  the next quarter's.
- How the invariants are tested: on the committed data (`tests/test_events_eps_link.py`) and on fixtures shaped like
  the review's cases (Costco, Oracle, Berkshire), where each wrong rule (a bound moved, first-in-window, most links
  first, the tie order) makes a test fail.
