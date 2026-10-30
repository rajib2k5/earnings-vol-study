# PR/FAQ — Earnings & Implied Volatility: an event study

> **Status: revised 2026-10-29 with the measured results (milestone 5).** The draft below was written "working
> backwards" at milestone 0, before any result existed, and is kept as written except where a passage is marked
> "revised 2026-10-29". The measured results are in [What we measured](#what-we-measured-2026-10-29), which also lists
> every place where the results contradict the milestone-0 draft. **Every result is provisional**: most
> before-open/after-close labels have not yet been checked against a document. The numbers in the two marked blocks are
> filled in from the committed data by `tools/report_numbers.py` and checked by a test.
>
> A few *design facts* also appear below, such as snapshot dates and gaps between earnings dates. They come from
> milestone-0 checks of the source data, and each one names its source. They are inputs to the design, not results.
>
> The milestones are:
> 1. universe and events;
> 2. IV measures;
> 3. event study;
> 4. drivers;
> 5. report.
>
> Quotes are drafts for the author to rewrite. "Sam" is a hypothetical persona, not a real person.

---

## Press release

### Open study measures how much earnings move option volatility, and whether options priced the move right

*A reproducible event study of several hundred earnings announcements by about 50 large US companies. It shows how implied volatility behaves into each report, how much it falls afterwards, and how often the stock moved more than the options implied.*

**Online, ⟨release date, after milestone 5⟩.** A stock's implied volatility (IV) typically rises before an earnings report and falls once the news is out. Traders call the fall the *IV crush*. Rules of thumb about it are common; tested numbers are rare. Three questions need answers:
- How big is the crush on average, and how long does it last?
- Is it statistically real once you allow for hundreds of companies reporting in the same few weeks?
- Did the options price the stock's actual move too high or too low?

`earnings-vol-study` answers these with the standard finance method for measuring the effect of a dated event, the **event study**. It applies the method to option-implied volatility instead of stock returns. For each announcement it lines up the IV series in *event time*. Day 0 is the first trading-session close after the news: the announcement day for a before-open report, the next session for an after-close one. It then measures **abnormal IV** against a quiet baseline period well before the event.

<!-- numbers:prfaq-headline -->
The headline result, measured on 2026-10-29 with provisional timing labels: from day −1 to day 0, 30-day IV falls by
0.199 log points on average, about 18.1%, net of the market's volatility. That is significant at
p = 5.8e−23 (Holm 4.1e−22 over the seven declared hypotheses), under a two-way cluster-robust t that allows for
events sharing calendar dates and for one company's events being alike; its size was checked first on the real event
set (gate G1: 4.60% at 5%). The fall is not reported in vol points: the study measures it in logs, which are
comparable across names (ADR 0004). The study also reports:
- IV is back at its baseline by day +10 (+0.008 log points, p = 0.743);
- the size of the crush does not reliably track the earnings surprise (+0.013 per sd, Holm 0.0511) or how
  high ordinary volatility was beforehand (−0.001, p = 0.895), and both tests turned out liberal at this design;
- the stock's day-0 move exceeded the move the options implied 40.1% of the time, against 42.5%
  under fair pricing of a normal move.
<!-- /numbers:prfaq-headline -->

"Every options desk has a rule of thumb for earnings. Few of them get tested out loud," said ⟨the author⟩. "We wanted numbers anyone could rerun from public data, line by line."

**How it works.**
1. A Python pipeline reads earnings dates, before-open/after-close labels and analyst estimates from DoltHub's open `earnings` dataset. It reads daily option chains from DoltHub's open `options` dataset. Some before-open/after-close labels are wrong, so each label is checked against documents, never against the size of the stock's move. By default the document is the company's press release, looked up by hand for every event since daily option data began (September 2024), and the calendar label is kept only when no release is found. *Revised 2026-10-29:* the owner accepted the acceptance time of the company's SEC 8-K earnings filing as the source on 2026-10-28; it runs once the owner sets a contact string, and until then most events keep the calendar's label. The stock's overnight price gap only flags a label for a second reading; it never sets one ([ADR 0002](adr/0002-day-zero-convention.md)).
2. The pipeline recomputes implied volatility from mid prices. It derives three measures:
   - an ATM IV on the first *listed* expiry after the announcement;
   - a 30-day constant-maturity IV that never blends an expiry ending before the news with one ending after it;
   - the *implied move*: the earnings-day variance backed out from the difference between two expiries.
3. CBOE's single-stock volatility indices for five large names provide an independent check on the IV measures. *Revised 2026-10-29: not built yet; no index file has been downloaded.*
4. Every test works on log IV, after removing each company's measured sensitivity to market-wide volatility (VIX). The primary event test is a t-test with two-way cluster-robust standard errors on the plain (equal-weighted) mean. For the one-day crush the clusters are the announcement date and the company. For the run-up and the persistence, which span weeks, they are the earnings season and the company, and a randomisation (Rademacher) p-value by season takes over when seasons are unbalanced. The Boehmer-Musumeci-Poulsen test and the Kolari-Pynnönen family, including Kolari, Pape & Pynnönen's adjustment for overlapping windows, are reported as robustness and labelled as tests of the precision-weighted mean. The driver regressions use standard errors clustered two ways, by company and by date ([ADR 0005](adr/0005-statistical-test-suite.md)).
5. Every number shown is exported to a versioned JSON file and drawn by an interactive app. The app never computes a result itself.

"I sell earnings straddles a few times a season," said ⟨Sam, a hypothetical options-trader persona⟩. "What I want to know is how often the stock actually moves more than the options priced, and whether that depends on how expensive the options were going in."

**Get started.** When the study is released, clone the repository and set `VOL_DATA_DIR` to where the DoltHub clones live. Then run the pipeline, or just open the app or the report, `docs/report/earnings-vol-report.pdf` (*revised 2026-10-29*; the draft named `reports/report.pdf`). This is research for learning, not financial advice.

---

<!-- numbers:prfaq-measured -->
## What we measured (2026-10-29)

Measured at milestones 1–4 and collected here at milestone 5, with **provisional timing labels**
(20 of 473 required look-ups done). Day 0 from 2024-12-10 to
2026-10-22; 347 primary events of 50 companies. The full account is the
[report](report/earnings-vol-report.md) (a draft the owner has not reviewed yet).

| | Result | Holm p (H1–H7) |
|---|---|---:|
| H1 crush | 30-day IV falls by 0.199 log points from day −1 to day 0 (interval [−0.222, −0.177]) | 4.1e−22 |
| H2 run-up | IV sits +0.232 log points above its baseline at day −1 | 0.0469 (7 seasons: 0.0781) |
| H3 persistence | +0.008 at day +10 (interval [−0.049, 0.065]) | 1 |
| H4 ordinary volatility | +0.003 (interval [−0.019, 0.026]) | 1 |
| H5 surprise | +0.013 per sd (interval [0.003, 0.023]); the test's size is 9.55% | 0.0511 |
| H6 prior volatility | −0.001 per sd (interval [−0.023, 0.020]); size 8.10% | 1 |
| H7 implied vs realised | b = 0.77 (interval [0.46, 1.07]); 40.1% of moves beyond the implied \|move\| against a fair 42.5%; size 16.15% | 1 |

**Where the milestone-0 draft was wrong, or has changed.** The draft above is kept as written at milestone 0 except
where marked "revised 2026-10-29". These are the places the results contradict it:

1. **Timing look-ups.** The draft said every event since daily option data began would be looked up by hand (How it
   works, step 1; Internal FAQ, "Timing labels"), and that quiet events would be checked as thoroughly as big movers.
   Only 20 of the 473 required look-ups are done, so neither holds yet. The owner
   accepted SEC EDGAR 8-K filing times as the source on 2026-10-28, but no request has been made: the client needs the
   owner's contact string. Every number here is provisional until then.
2. **The size check of the driver tests.** The draft planned regressions with two-way clustered errors and no size
   check of their own. Gate G1, extended to them at milestone 4 and run before their results run, found their
   statistics liberal: 9.55% (H5), 8.10% (H6) and 16.15% (H7) under a true null at 5%. They stay in the
   declared Holm family; none is rejected.
3. **The number of seasons.** ADR 0005 expected the run-up's events to fall into 7 seasons. There are
   8, unbalanced, so the randomisation p-value is H2's primary and its Holm verdict depends on that count
   (0.0469 with 8; 0.0781 with 7).
4. **The surprise question.** The external FAQ asks whether a bigger surprise causes a bigger crush. The measured
   coefficient points the other way, a slightly smaller fall (+0.013 per sd), and it is not rejected after Holm and
   does not survive other surprise measures.
5. **The Cboe cross-check and subsample.** The draft named Cboe's single-stock volatility indices for five names as
   an independent check on the IV measures, as a second daily subsample ("How far back does it go?") and as a source of
   extra events (Internal FAQ, "Feasibility"). None of it has been built: no index file has been downloaded.
6. **What is committed.** The draft said no Cboe or Yahoo data would be committed. Under the owner's decision of
   2026-10-29 the repository commits the data the app and the docs need: aggregates of VIX-adjusted values, a VIX
   tercile label, two Yahoo-derived labels and the size coefficients (DATA.md). The VIX series, per-event VIX-adjusted
   values and raw downloads stay local.
7. **The robustness tests.** The draft (How it works, step 4) said the Boehmer-Musumeci-Poulsen test and the
   Kolari-Pynnönen family are reported as robustness. They are computed, but for the crush (H1) gate G1 found them
   oversized, so their p-values are withheld and only their estimates are shown (14 robustness rows in all
   lose their p-value this way).
8. **The warning line on ρ̄.** ADR 0005, written at milestone 0, read a same-date correlation above about 0.2 as a
   failed VIX adjustment or a data error. The crush's ρ̄ is 0.30. No data error and no single bad date was found:
   it is one common date component, linearly unrelated to the change in ln VIX (milestone 4 §6.6). That last part is
   close to automatic, because each company's β is fitted on the change in ln VIX, so it cannot rule out VIX entering
   in another form.
9. **Where the report is.** The draft pointed to `reports/report.pdf`; the report is
   `docs/report/earnings-vol-report.pdf` (and `.docx`, `.md`).

Confirmed as predicted: the sample size (347 events, inside the draft's 330–360), and a crush large
against day-to-day noise (t = −17.73).
<!-- /numbers:prfaq-measured -->

---

## External FAQ

**Q: What exactly is "IV crush" here?**
It is the change in log 30-day constant-maturity IV, measured from the close before the news reaches the market (day −1) to the first close after it (day 0). It is net of market-wide volatility: we subtract β × the same day's change in log VIX, where β is estimated separately for each company from its quiet periods. The 30-day series is comparable across names and dates.

The ATM IV of the first listed expiry after the event is reported as well. It is closer to what traders watch, but its size depends on how many days that expiry has left. [ADR 0002](adr/0002-day-zero-convention.md) defines day 0, and [ADR 0003](adr/0003-iv-measures.md) defines the IV measures.

**Q: What is "abnormal" IV?**
It is how far log IV sits from its own average over a *baseline* of quiet sessions, again net of VIX. The baseline runs from 60 to 22 trading sessions before day 0. Sessions near the company's other earnings dates are removed from it. [ADR 0004](adr/0004-baseline-and-event-windows.md) has the details.

**Q: Why not just average the IV change across all events?**
Because events are not independent. Hundreds of companies report in the same few weeks, so a market-wide volatility move shows up in many events at once, and one company's events resemble each other from quarter to quarter. A plain t-test treats those events as independent evidence and overstates significance. The primary event tests therefore cluster their standard errors two ways: by announcement date (or by earnings season, for measures that span weeks) and by company. The regressions cluster by company and date for the same reason ([ADR 0005](adr/0005-statistical-test-suite.md)).

**Q: How far back does it go?**
The primary sample uses *daily* option snapshots. DoltHub's API shows these start on 11 September 2024 ([data-model §1.2](architecture/data-model.md)). The baseline reaches back 60 sessions before day 0, so the first usable day 0 falls in December 2024 ([ADR 0004](adr/0004-baseline-and-event-windows.md)). The sample runs to the latest snapshot, which is October 2026 at the time of writing. *Revised 2026-10-29:* the measured sample size, after removing the events without a 30-day IV on day −1 and day 0 and the short baselines, is in [What we measured](#what-we-measured-2026-10-29); the timing labels behind it are still provisional ([the milestone-2 page](milestones/02-iv-measures.md#61-the-sample-funnel-primary-daily)).

Earlier snapshots are weekly, then Monday/Wednesday/Friday ([ADR 0002](adr/0002-day-zero-convention.md)). That is too coarse to separate day −1 from day 0, so 2020–2024 is a lower-resolution robustness check.

CBOE's daily 30-day IV indices for five names (AAPL, AMZN, GOOG, GS, IBM) give a second, daily subsample. The indices go back further, but our earnings calendar starts in 2020 ([data-model §1.1](architecture/data-model.md)), so this subsample starts in 2020 too. Going earlier would need a second source of announcement dates.

**Q: Does a bigger earnings surprise cause a bigger crush?**
That is one of the two driver hypotheses tested at milestone 4. The other is that the prior IV level drives it. *Revised 2026-10-29:* no reliable effect in either direction; the measured coefficient, its interval and why the test is weaker than it looks are in [What we measured](#what-we-measured-2026-10-29) (H5, and item 4 of the corrections).

**Q: Can I trade on this?**
No. It describes the past, before transaction costs, on a sample of large liquid names. It is not a trading system. The report's "trading implications" section says what the evidence does and does not support ([report §6](report/earnings-vol-report.md#6-trading-implications-observations-and-their-limits)).

**Q: Is the data free to reuse?**
The DoltHub datasets are published under CC BY-SA 4.0. Small derived tables in `data/derived/` are shared under the same licence, with attribution. *Revised 2026-10-29:* raw CBOE index data and Yahoo prices are fetched by your own copy of the code and never committed; under the owner's decision of 2026-10-29 the repository does commit what the app and the docs need from them (aggregates of VIX-adjusted values, a VIX tercile label, two Yahoo-derived labels and the size coefficients), under those sources' own terms. [DATA.md](../DATA.md) lists each.

---

## Internal FAQ

**Data: what is the riskiest dependency?**
DoltHub's `options` chains. Milestone-0 queries against DoltHub's read-only API found five problems:
- **Snapshots** are daily only from 2024-09-11.
- **The chain is partial.** Each snapshot lists only 3–4 expiries chosen by the data vendor, the same set for every symbol. The weekly expiry just after an earnings date is usually not among them. So the "first listed expiry after the event" is typically 7–11 sessions out, and its crush will look smaller than what traders see on weeklies.
- **Strikes** are sparse and irregular, about 19–27 per expiry.
- **There is no underlying-price column.**
- **The vendor's call and put IVs** can disagree by several vol points.

The plan handles these in four ways:
- Restrict the primary sample to the daily period.
- Recompute IV from mid prices, with the forward price taken from put-call parity.
- Validate against CBOE's indices for five names.
- Record every quote filter and interpolation as a flag in `iv_daily`.

**Timing labels.** The calendar's before-open/after-close label defines day 0, so a wrong label puts the crush on the wrong day. The milestone-0 checks found two already. GOOGL on 2024-10-29 and NFLX on 2024-10-17 are labelled before-open, but their price gaps show after-close reports ([ADR 0002](adr/0002-day-zero-convention.md)). The first plan let the price gap correct labels. The adversarial review showed in simulation that such a rule corrects big movers' labels and leaves quiet events' errors (ADR 0002 §3), so the label now comes from documents and never from the size of the move.
- **Proposed at milestone 0; accepted by the owner on 2026-10-28 (revised 2026-10-29):** the architect's rule takes the timing from the acceptance time of the company's SEC 8-K earnings filing (Item 2.02). SEC's fair-access policy requires a real contact in every request, so the client makes no request until the owner sets one.
- **The default if the owner declines, and the rule until then:** the company's press release, looked up by hand for every event in the daily and mixed samples (about 365 + 50) and for every event with no label; the calendar label is kept only where no release is found. Each look-up is recorded with its URL in a committed file.
- **The price gap stays a local diagnostic.** It never sets a label. A gap that contradicts the label only triggers a second reading of the release (in the older 2020–2024 robustness sample, the look-up itself).
- **Quiet events are checked as thoroughly as big movers.** The delta review simulated the previous default, which looked up only the events a gap flagged plus a 50-event audit: quiet events kept a wrong day 0 in 2.1–2.6% of cases against 0.3–0.6% for big movers, and the audit could not see it. Looking up every release removes the calendar's errors from that comparison. The sample funnel reports the crush by tercile of a move measure that does not depend on the label ([ADR 0002 §3](adr/0002-day-zero-convention.md)).

**Feasibility: are a few hundred events enough?**
From the calendar's spacing, the primary sample should hold roughly 330–360 events. That is an estimate; milestone 1 counts them. The crush should be large relative to day-to-day IV noise, so that many events should be enough to detect it, and milestone 3 will show whether that holds. For the driver regressions with sector effects, it may not be enough. The study will report confidence intervals rather than claim power it does not have. The coarse 2020–2024 sample and the CBOE subsample add events for the questions they can answer.

**Risks: what could make the result wrong?**
1. **A contaminated baseline.** Quarterly reports are about 63 sessions apart. A milestone-0 check on the 306 gaps between consecutive reports across 30 large caps (`research/prototypes/spacing.py`) found that a fixed [−60, −20] baseline would overlap the previous report's [0, +10] window in 97.1% of gaps, and contain its day 0, the crush itself, in 20.3%. [ADR 0004](adr/0004-baseline-and-event-windows.md) starts from [−60, −22] and removes every session near another report by the same company. On the same 306 gaps that leaves a median of 31 clean sessions.
2. **Return-based tests applied to a persistent series.** IV levels are strongly autocorrelated. Patell- and BMP-style tests assume independent days. [ADR 0005](adr/0005-statistical-test-suite.md) writes the crush as one one-session change, and the run-up and persistence as weighted sums of one-session changes. The primary tests are cluster-robust, so they need no autocorrelation model: any dependence inside a season (or a date) and inside a company is absorbed by the clusters. A pooled autocorrelation estimate enters only the standardised robustness rows.
3. **A primary test that has passed simulations, not yet the real-data gate.** The primary test is the two-way cluster-robust t (Cameron, Gelbach & Miller 2011). Its size was simulated at the real daily design, 352 events with every input estimated (`research/prototypes/h2h3_size_sim.out.txt` and `h2h3_followup_sim.out.txt`, 2,000 and 4,000 replications per design). A test at 5% should reject a true null 5% of the time. In the follow-up run's nine size designs it rejected:
   - for the crush (date × company clusters): 4.75–5.80%;
   - for the run-up and persistence (season × company clusters), with random-walk IV levels and balanced seasons: 4.25–6.08%;
   - for the same, when IV levels mean-revert: 1.65–2.25%, which is conservative;
   - with unbalanced seasons, 8.95–9.12%. The Rademacher p-value by season held 5.22–5.65% there, so it takes over in that case.

   These are simulated sizes, not results. Gate G1 repeats the check on the real event set at milestone 3; no p-value for the four event hypotheses is reported before it passes. *Revised 2026-10-29:* G1 ran before any result; H1–H4 passed, and the driver tests H5–H7, gated at milestone 4, failed ([What we measured](#what-we-measured-2026-10-29), item 2). The overlap of event windows is handled in the published literature by Kolari, Pape & Pynnönen (2018, SSRN 10.2139/ssrn.3167271) and Pynnönen (2022, *J. Risk Financial Management* 15(4):149). Their statistics are reported as robustness, beside BMP ([ADR 0005](adr/0005-statistical-test-suite.md)).
4. **Expiry roll and event-variance leakage.** The front expiry changes inside the window. Interpolating to 30 days between an expiry before the event and one after it leaks earnings variance into the baseline. ADR 0003 sizes the leak over the vendor's expiry grid (`research/prototypes/leak_grid.py`): with the clean expiry 17–21 sessions out, the spanning one 27–42 sessions out, each of the 80 pairs counted once and a flat 25% ordinary volatility, the leak runs from 0 to 0.66 vol points (median 0.21) for an event variance E = 0.0007, and from 0 to 2.73 (median 0.90) for E = 0.003, a stock pricing a 5.5% move. [ADR 0003](adr/0003-iv-measures.md) follows one fixed expiry per event, and interpolates only between expiries on the same side of the event.
5. **Survivorship.** The universe is chosen from companies that are large today. This bias is stated, not hidden.

**Success metrics.**
- Every reported number can be reproduced with `uv run` and the public data, and an independent agent re-measures it.
- Every statistical function has a hand-worked test that fails when the code is broken.
- Every milestone passes an adversarial review that uses evidence-gated validation.
- Learning goal: the author can explain every design choice and every line of the pipeline in an interview.

**What we will not do.**
- No intraday data, so no claims about *when* during day 0 the crush happens.
- No transaction-cost-aware backtest. That belongs to a sibling project in this learning programme, `vol-strategy-backtester`.
- No claims beyond large, liquid US names.
- No raw CBOE or Yahoo data committed to the repository (*revised 2026-10-29:* the milestone-0 draft said no CBOE or Yahoo data at all; the owner's decision of 2026-10-29 commits the aggregates and labels the app and the docs need, listed in [DATA.md](../DATA.md)). DoltHub data, licensed CC BY-SA 4.0, appears in two forms: small extracts in `data/derived/`, with attribution, and a few quoted values (option quotes, parity forwards, vendor deltas and calendar counts) in ADRs 0002 and 0003 and in `research/prototypes/worked.py` and its output. The quoted values are shared under the same licence.
- No result numbers in this document until they have been measured. *Revised 2026-10-29:* they appear only in the two marked blocks, filled in from the committed data by `tools/report_numbers.py`.
