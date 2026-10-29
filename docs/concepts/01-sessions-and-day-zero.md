# Trading-session calendars and day 0

Concept note for milestone 1. Written 2026-10-29. The decision it explains is
[ADR 0002 §1–2](../adr/0002-day-zero-convention.md); the code is `src/earnings_vol/events/calendar.py`.

## 1. Why a calendar of sessions, not of days

An event study counts time from an event: day −1, day 0, day +1. With daily stock or option data, "a day" has to
mean a day on which a price was set. A *session* is one opening of the exchange. Weekends and exchange holidays are
not sessions. A half day (the NYSE closes at 13:00 on, for example, the day after Thanksgiving) is a full session
that ends early.

If you counted calendar days instead, a Friday → Monday step would count as three days, and a step across Good Friday
as four. Two consequences, both wrong:

- *Relative days stop meaning the same thing.* "Day +5" would sometimes be five trading opportunities later and
  sometimes three.
- *Variance would be spread over days when nothing trades.* Option variance accrues mostly while markets are open.
  ADR 0003 measured the effect on the worked AAPL example: the calendar clock inflates the event variance by 36%.

So the study uses one clock for variance and event time, NYSE sessions, and keeps calendar days only for interest
(a bond accrues interest every day).

**Where the list comes from.** The `exchange_calendars` package (calendar `XNYS`, pinned at 4.13.2) holds every NYSE
holiday and early close, including one-off closures such as the national day of mourning on 2025-01-09. The test
`tests/test_calendar.py` checks that 2025 has 250 sessions and that 2024-09-11 → 2026-10-26 has 533 (both numbers the
ADRs measured independently).

## 2. Day 0 is defined by the snapshot, not by the announcement

The option data are *closing snapshots*: one picture of the market per session, taken at the close. The question for
each event is therefore: **which is the first close that already knows the news?** That close is day 0. The close
before it is day −1. The IV crush is `X(0) − X(−1)`: exactly one session of ordinary price movement plus the news sits
between them.

| When the company reports | Day −1 | Day 0 |
|---|---|---|
| Before the open (BMO) on a session D | the session before D | D |
| After the close (AMC) on a session D | D | the session after D |
| On a weekend or holiday | the last session before | the first session after |
| Timing unknown, D a session | — | undefined: the event is excluded |

**Worked example (the oracle table's first row).** Apple reported after the close on Thursday 2025-10-30. The 10-30
close was taken before the news, so day −1 = 10-30. The first close after the news is Friday 10-31 = day 0.

**Why the label matters so much.** Alphabet's calendar row of 2024-10-29 said "before market open", but Alphabet
reported after the close. With the wrong label, day 0 would be 10-29 — a close taken *before* the news — and the
measured "crush" would be an ordinary day's IV change. The real crush would land on day +1. Averaging events with
right and wrong labels smears the effect over two days and shrinks it.

**A release during the session** (rare) is stored as BMO: D's close follows the news, which is all day 0 needs.

## 3. Snapshots that are not sessions

The vendor sometimes publishes a snapshot on a holiday. It is a copy of the session before (milestone 1 checked one:
the AAPL quotes of Labor Day 2024 have the same digest as those of Friday 2024-08-30). Rule: map every snapshot to the
session on or before its date; if two land on one session, keep the one dated on the session. The other is dropped
as `stale_copy`. Missing sessions are never filled in.

## 4. Things to be able to say in an interview

- Why sessions: event time and variance accrue on trading sessions; calendar days distort both.
- Day 0 is "first close after the news", which makes BMO and AMC events line up.
- A wrong BMO/AMC label moves day 0 by exactly one session, and this smears the measured crush.
- The label is never inferred from the IV move (circular) and never decided by the price move (selection on the
  outcome); it comes from documents (ADR 0002 §3).
