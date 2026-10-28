# PR/FAQ — Earnings & Implied Volatility: an event study

> **Status: milestone-0 draft, written working backwards.** The press release below is
> dated for when the study is finished and describes what it *will* show. **No results
> have been measured yet.** Every `⟨…⟩` is a result that will be measured, re-checked by an
> independent verifier agent, and filled in when this PR/FAQ is revised at milestone 5.
>
> A few *design facts* do appear below, such as snapshot dates and gaps between earnings
> dates. They come from milestone-0 checks of the source data, and each one names its
> source. They are inputs to the design, not results.
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

The headline result will be stated with its uncertainty. From day −1 to day 0, 30-day IV falls by ⟨x⟩% on average (⟨y⟩ vol points). That is significant at ⟨p⟩, under a test that allows for events sharing calendar dates and for one company's events being alike; the internal FAQ explains which test, and the size check it must pass first. The study also reports:
- whether IV is back to its baseline by day +10;
- whether the size of the crush tracks the size of the earnings surprise, or how high IV was beforehand;
- how often the stock's actual move exceeded the move the options implied.

"Every options desk has a rule of thumb for earnings. Few of them get tested out loud," said ⟨the author⟩. "We wanted numbers anyone could rerun from public data, line by line."

**How it works.**
1. A Python pipeline reads earnings dates, before-open/after-close labels and analyst estimates from DoltHub's open `earnings` dataset. It reads daily option chains from DoltHub's open `options` dataset. Some before-open/after-close labels are wrong, so each label is checked against documents, never against the size of the stock's move. By default the document is the company's press release, looked up by hand for every event since daily option data began (September 2024), and the calendar label is kept only when no release is found. Using the acceptance time of the company's SEC 8-K earnings filing instead is a proposal that waits for the owner's decision. The stock's overnight price gap only flags a label for a second reading; it never sets one ([ADR 0002](adr/0002-day-zero-convention.md)).
2. The pipeline recomputes implied volatility from mid prices. It derives three measures:
   - an ATM IV on the first *listed* expiry after the announcement;
   - a 30-day constant-maturity IV that never blends an expiry ending before the news with one ending after it;
   - the *implied move*: the earnings-day variance backed out from the difference between two expiries.
3. CBOE's single-stock volatility indices for five large names provide an independent check on the IV measures.
4. Every test works on log IV, after removing each company's measured sensitivity to market-wide volatility (VIX). The primary event test is a t-test with two-way cluster-robust standard errors on the plain (equal-weighted) mean. For the one-day crush the clusters are the announcement date and the company. For the run-up and the persistence, which span weeks, they are the earnings season and the company, and a randomisation (Rademacher) p-value by season takes over when seasons are unbalanced. The Boehmer-Musumeci-Poulsen test and the Kolari-Pynnönen family, including Kolari, Pape & Pynnönen's adjustment for overlapping windows, are reported as robustness and labelled as tests of the precision-weighted mean. The driver regressions use standard errors clustered two ways, by company and by date ([ADR 0005](adr/0005-statistical-test-suite.md)).
5. Every number shown is exported to a versioned JSON file and drawn by an interactive app. The app never computes a result itself.

"I sell earnings straddles a few times a season," said ⟨Sam, a hypothetical options-trader persona⟩. "What I want to know is how often the stock actually moves more than the options priced, and whether that depends on how expensive the options were going in."

**Get started.** When the study is released, clone the repository and set `VOL_DATA_DIR` to where the DoltHub clones live. Then run the pipeline, or just open the app or `reports/report.pdf`. This is research for learning, not financial advice.

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
The primary sample uses *daily* option snapshots. DoltHub's API shows these start on 11 September 2024 ([data-model §1.2](architecture/data-model.md)). The baseline reaches back 60 sessions before day 0, so the first usable day 0 falls in December 2024 ([ADR 0004](adr/0004-baseline-and-event-windows.md)). The sample runs to the latest snapshot, which is October 2026 at the time of writing. It holds ⟨n⟩ events, counted at milestone 1.

Earlier snapshots are weekly, then Monday/Wednesday/Friday ([ADR 0002](adr/0002-day-zero-convention.md)). That is too coarse to separate day −1 from day 0, so 2020–2024 is a lower-resolution robustness check.

CBOE's daily 30-day IV indices for five names (AAPL, AMZN, GOOG, GS, IBM) give a second, daily subsample. The indices go back further, but our earnings calendar starts in 2020 ([data-model §1.1](architecture/data-model.md)), so this subsample starts in 2020 too. Going earlier would need a second source of announcement dates.

**Q: Does a bigger earnings surprise cause a bigger crush?**
That is one of the two driver hypotheses tested at milestone 4. The other is that the prior IV level drives it. The answer will be reported with its confidence interval, even if that answer is "no detectable effect".

**Q: Can I trade on this?**
No. It describes the past, before transaction costs, on a sample of large liquid names. It is not a trading system. The report's "trading implications" section will say what the evidence does and does not support.

**Q: Is the data free to reuse?**
The DoltHub datasets are published under CC BY-SA 4.0. Small derived tables in `data/derived/` are shared under the same licence, with attribution. CBOE index data and Yahoo prices are fetched by your own copy of the code and never committed to the repository.

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
- **Proposed, pending the owner's decision:** the architect's rule takes the timing from the acceptance time of the company's SEC 8-K earnings filing (Item 2.02). The owner's approved plan excluded SEC EDGAR, because SEC's fair-access policy requires a real contact email in every request.
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

   These are simulated sizes, not results. Gate G1 repeats the check on the real event set at milestone 3; it is pending, and no p-value for the four event hypotheses is reported before it passes. The overlap of event windows is handled in the published literature by Kolari, Pape & Pynnönen (2018, SSRN 10.2139/ssrn.3167271) and Pynnönen (2022, *J. Risk Financial Management* 15(4):149). Their statistics are reported as robustness, beside BMP ([ADR 0005](adr/0005-statistical-test-suite.md)).
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
- No CBOE or Yahoo data committed to the repository. DoltHub data, licensed CC BY-SA 4.0, appears in two forms: small extracts in `data/derived/`, with attribution, and a few quoted values (option quotes, parity forwards, vendor deltas and calendar counts) in ADRs 0002 and 0003 and in `research/prototypes/worked.py` and its output. The quoted values are shared under the same licence.
- No result numbers in this document until they have been measured.
