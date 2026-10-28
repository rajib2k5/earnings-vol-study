# Learning log

The index of what this project teaches, one milestone at a time. Each milestone gets a page in
[`docs/milestones/`](docs/milestones/). The goal is that the owner can explain the architecture and the code, at a low
level, in an interview.

Last updated: 2026-10-28 (milestone 0), after the ADRs and the data model were revised.

## Milestones

| # | Milestone | Status | Page |
|---|---|---|---|
| 0 | Scaffold and design | done, pending owner review | [`docs/milestones/00-scaffold-and-design.md`](docs/milestones/00-scaffold-and-design.md) |
| 1 | Universe and events | planned | written when the milestone is done, in [`docs/milestones/`](docs/milestones/) |
| 2 | IV measures | planned | written when the milestone is done, in [`docs/milestones/`](docs/milestones/) |
| 3 | Event study | planned | written when the milestone is done, in [`docs/milestones/`](docs/milestones/) |
| 4 | Drivers | planned | written when the milestone is done, in [`docs/milestones/`](docs/milestones/) |
| 5 | Report | planned | written when the milestone is done, in [`docs/milestones/`](docs/milestones/) |

The milestone names come from the [PR/FAQ](docs/prfaq.md).

## Reference documents

| Document | What it is for |
|---|---|
| [`docs/concepts/00-background.md`](docs/concepts/00-background.md) | The finance and statistics background, in plain English. |
| [`docs/prfaq.md`](docs/prfaq.md) | The product story, written backwards from the finished study. No results yet. |
| [`docs/adr/0001-overall-architecture.md`](docs/adr/0001-overall-architecture.md) | ADR 0001: the layered pipeline, where the data lives, the JSON contract, licensing (a licence class per column). |
| [`docs/adr/0002-day-zero-convention.md`](docs/adr/0002-day-zero-convention.md) | ADR 0002: what "day 0" means, and how the before/after-market label is checked against documents (SEC EDGAR is proposed, pending the owner's decision; the default is the press release, then the calendar label). |
| [`docs/adr/0003-iv-measures.md`](docs/adr/0003-iv-measures.md) | ADR 0003: how IV is recomputed, the 30-day IV, event variance and implied move. |
| [`docs/adr/0004-baseline-and-event-windows.md`](docs/adr/0004-baseline-and-event-windows.md) | ADR 0004: the event window, the baseline, abnormal IV, and why not CAAIV. |
| [`docs/adr/0005-statistical-test-suite.md`](docs/adr/0005-statistical-test-suite.md) | ADR 0005: the tests (a two-way cluster-robust t as primary; BMP and the Kolari-Pynnönen family as robustness), the regressions, the size gate G1, and the multiple-testing rule. |
| [`docs/adr/README.md`](docs/adr/README.md) | The ADR index. |
| [`docs/architecture/README.md`](docs/architecture/README.md) | The architecture diagrams. |
| [`docs/architecture/data-model.md`](docs/architecture/data-model.md) | Every table, key, licence class, and the Python to app JSON contract. |
| [`research/prototypes/README.md`](research/prototypes/README.md) | The throwaway scripts behind numbers quoted in the ADRs (event spacing, the AAPL worked example, the leak range, the KP and real-design size simulations, why IV levels must not be summed). Not tested to the package's standard. |
| [`data/derived/README.md`](data/derived/README.md) | The one derived file so far, `earnings_calendar_30_large_caps.json` (a DoltHub extract that the spacing script reads), and the CC BY-SA 4.0 terms. |

## My predictions

Write your guesses below **before milestone 1 runs**. They are graded against the measured values. Do not edit a guess
after the measurement exists. P1 to P3 are about the event table from milestone 1. P4 to P6 are about the IV measures
(milestone 2 in the plan), so they may be graded a little later.

**P1.** Of the earnings_calendar rows for our ~50 names in the daily period, what share will have a NULL
before/after-market label?

- My guess: ______________________________________________
- Why I think so: ________________________________________
- Date written: __________
- Measured value and grade (filled in at grading): ______________________________

**P2.** What share of the labelled events will the timing check (documents, not prices) *correct* (label flipped)?
Under 1%, 1–5%, or over 5%?

- My guess: ______________________________________________
- Why I think so: ________________________________________
- Date written: __________
- Measured value and grade (filled in at grading): ______________________________

**P3.** How many events will the primary daily sample hold after the baseline-minimum rule (at least 20 clean
sessions)?

- My guess: ______________________________________________
- Why I think so: ________________________________________
- Date written: __________
- Measured value and grade (filled in at grading): ______________________________

**P4.** For a typical mega-cap (AAPL, MSFT), what will the implied move sqrt(E) be on day −1: about 1%, 3%, or 6%?

- My guess: ______________________________________________
- Why I think so: ________________________________________
- Date written: __________
- Measured value and grade (filled in at grading): ______________________________

**P5.** What fraction of events will give a negative event-variance estimate (E ≤ 0) on day −1?

- My guess: ______________________________________________
- Why I think so: ________________________________________
- Date written: __________
- Measured value and grade (filled in at grading): ______________________________

**P6.** Will the vendor's IV column sit above or below our recomputed ATM IV on average, and by roughly how many vol
points?

- My guess: ______________________________________________
- Why I think so: ________________________________________
- Date written: __________
- Measured value and grade (filled in at grading): ______________________________

## Explain-it-back answers and grades

The questions are in [section 7 of the milestone 0 page](docs/milestones/00-scaffold-and-design.md#7-explain-it-back).
Answer them in chat. The session grades honestly and fills gaps. Then record the result here.

| # | Topic | Answer | Grade | Gaps filled |
|---|---|---|---|---|
| Q1 | The app never computes: the failure it prevents, and where the boundary is | | | |
| Q2 | `json.dumps` and NaN, the browser parse, and `allow_nan=False` | | | |
| Q3 | Apple after the close on 30 October 2025: day −1, day 0, and a wrong label | | | |
| Q4 | Deriving the event variance E, and what E ≤ 0 means | | | |
| Q5 | Why a fixed [−60, −20] baseline is contaminated, and what ADR 0004 does | | | |
| Q6 | Why not CAAIV, and what is tested instead | | | |
| Q7 | The two-way clustered primary (why two dimensions, why season × firm for ramps) and BMP's precision-weighted estimand | | | |
| Q8 | The notebook sync test and deterministic cell ids | | | |
