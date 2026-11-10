<!-- template: the source of docs/report/earnings-vol-report.md. Edit here, then run
     `uv run --frozen python tools/report_numbers.py`, which fills every placeholder from the committed data. -->
**Draft for owner review (2026-10-29): not yet reviewed by the owner.**

# Earnings and implied volatility: an event study

> **Not investment advice.** This report describes how option prices behaved around past earnings announcements of
> {{sample.n_companies}} large US companies. It recommends no trade, no position and no size. It ignores transaction
> costs. Past patterns in implied volatility do not predict future returns.
>
> **Every result here is provisional.** The session that each announcement reached the option market ("day 0")
> depends on a before-open or after-close label. ADR 0002 requires {{lookups.required}} of these labels to be checked
> against a document. {{lookups.done}} are checked: {{lookups.press_release}} against the company's press release and,
> since 2026-11-09, {{lookups.edgar}} against the time SEC EDGAR accepted the company's earnings filing (Form 8-K,
> Item 2.02). The other {{lookups.left}} are open: {{lookups.open.no_8k}} have no such filing near the date,
> {{lookups.open.edgar_holiday}} fall next to a day EDGAR was closed, {{lookups.open.other_date}} have the filing on
> another day and {{lookups.open.contradicts}} has a filing against the calendar's label. Of these {{lookups.left}},
> {{lookups.left_labelled}} keep the earnings calendar's label and {{lookups.left_unlabelled}} have no label at all. The audit that the ADR asks for ({{lookups.audit}} EDGAR labels checked against press releases) has
> not run, and {{lookups.gap_questioned}} EDGAR labels that the stock's price gap questions wait for a press-release
> check. So a few events may still sit on the wrong day 0.

Data: DoltHub `post-no-preference/earnings` at `{{meta.dolt_earnings}}` and `post-no-preference/options` at
`{{meta.dolt_options}}`; parameters hash `{{meta.params_hash}}`; app data contract {{meta.schema_version}}, exported from
commit `{{meta.source_commit}}`. Every measured number in this report is filled in by `tools/report_numbers.py` from
`data/derived/results.parquet`, `data/derived/vx_crosscheck.json`, the app's JSON files and the kept ρ̄ output
(section 8); the look-up counts that need a local Yahoo flag (the
{{lookups.required}} required look-ups, why {{lookups.left}} are open, and the {{lookups.gap_questioned}}
gap-questioned EDGAR labels) are pinned in that script. Design parameters quoted from the ADRs (window
lengths, minimum counts) are written by hand.

---

## Summary

- **The crush is large and almost universal.** From the last close before the news (day −1) to the first close after
  it (day 0), the 30-day implied volatility (IV) falls by {{h1.fall}} log points on average, net of the market's
  volatility: about {{h1.pct_fall}}. The market-adjusted change is negative in {{h1.share_below}} of the {{h1.n}} events. The test that allows
  for events on the same date and for one company's events being alike gives p = {{h1.p}} (Holm {{h1.p_holm}}).
- **The crush is the event leaving the 30-day horizon.** Ordinary volatility (σ_d, the volatility outside the event
  day) does not change measurably ({{h4.est}} log points, p = {{h4.p}}), and IV is back at its baseline ten sessions
  later ({{h3.est}}, p = {{h3.p}}).
- **IV is high before the news.** At day −1 the 30-day IV sits {{h2.est}} log points above its own quiet baseline. The
  direction is not in doubt. Whether it passes the multiple-testing correction depends on how many earnings seasons the
  sample is cut into (section 4.3).
- **The options priced the earnings-day move about right on average.** The realised squared move is {{h7.b}} times the
  implied variance (95% interval {{h7.b_ci}}, so 1 is inside). {{ivr.share}} of the moves were larger than the
  expected move, against the {{ivr.benchmark}} that fair pricing of a normal move gives.
- **Neither the earnings surprise nor the prior volatility level explains the size of the crush in a way that
  survives the checks.** The statistics for these driver tests are liberal at this design (they reject {{h5.g1}},
  {{h6.g1}} and {{h7.g1}} of the time under a true null at 5%), and none is rejected.

---

## 1. The question

A stock's implied volatility usually rises before an earnings announcement and falls once the news is out. Traders
call the fall the IV crush. This study measures five things for large US companies:

1. Does IV run up before the announcement? (H2)
2. How large is the crush from day −1 to day 0? (H1)
3. Is IV back at its baseline ten sessions later? (H3)
4. Does ordinary volatility change across the event? (H4)
5. What changes the size of the crush (H5: the earnings surprise; H6: the prior volatility level), and did the
   options price the earnings-day move correctly (H7)?

The seven hypotheses were declared in ADR 0005 before any data was seen. They are corrected together for multiple
testing (Holm, {{holm.m}} hypotheses). Everything else in this report is labelled robustness or exploratory.

## 2. Data and the sample funnel

**Sources.** The earnings calendar (with before-open and after-close labels) and the EPS history come from DoltHub's
open `post-no-preference/earnings` dataset. The option chains come from DoltHub's `post-no-preference/options`. Both
are CC BY-SA 4.0. Company names and GICS sectors come from Wikipedia's list of S&P 500 companies. The risk-free rate is
FRED's 3-month Treasury bill (`DTB3`). The market adjustment uses the VIX close (FRED `VIXCLS`, a Cboe index); only
aggregates of VIX-adjusted values are published. Yahoo Finance prices are used locally for the size regressor and a
timing diagnostic. [DATA.md](../../DATA.md) gives each source's terms.

**Universe.** Today's {{sample.n_companies}} largest S&P 500 members by market capitalisation. This has survivorship
bias: companies that shrank or left the index since 2020 are missing.

**The daily sample.** DoltHub's option snapshots are daily only from September 2024 (weekly, then Monday, Wednesday
and Friday, before that). The baseline needs 60 sessions before day 0, so the primary sample's day-0 window runs from
{{sample.day0_from}} to {{sample.day0_to}}; its {{sample.n_events}} events have day 0 from {{sample.first_day0}} to
{{sample.last_day0}}. The older coarse snapshots form a lower-resolution robustness sample.

| Step | Events left | Removed | Why |
|---|---:|---:|---|
| Calendar events of the {{sample.n_companies}} companies | {{funnel.calendar_events}} | – | |
| One row per release, and day 0 can be placed | {{funnel.timing_known}} | {{funnel.timing_known.removed}} | duplicate rows, timing not placeable |
| Day 0 in the daily range | {{funnel.daily_range}} | {{funnel.daily_range.removed}} | outside {{sample.day0_from}} to {{sample.day0_to}} |
| Option snapshots on day −1 and day 0 | {{funnel.crush_observed}} | {{funnel.crush_observed.removed}} | a missing snapshot |
| A 30-day IV on day −1 and day 0 | {{funnel.iv_usable}} | {{funnel.iv_usable.removed}} | no 30-day IV |
| At least 20 clean baseline sessions and 15 changes | **{{funnel.baseline_minimum}}** | {{funnel.baseline_minimum.removed}} | short baseline |

The {{funnel.calendar_events}} calendar events split into {{events.daily}} daily-era, {{events.mixed}} mixed-era,
{{events.coarse}} coarse-era and {{events.none}} outside every sample's date range. Each hypothesis then has its own eligibility
rules, so its event count (the `n` in section 4) differs a little from {{funnel.baseline_minimum}}.

![The sample funnel, as the app draws it from sample_funnel.json](../images/fig-funnel.png)

**Timing labels.** {{lookups.done}} labels rest on a document, {{lookups.press_release}} on a press release and
{{lookups.edgar}} on an SEC EDGAR filing time ({{timing.confirmed}} confirmed, {{timing.corrected}} corrected,
{{timing.date_corrected}} with a corrected date and {{timing.inferred}} inferred). {{timing.not_checked}} events stay
`not_checked`: {{timing.not_checked_labelled}} keep the calendar's label and {{timing.not_checked_unlabelled}} have none.
{{lookups.left}} of the {{timing.not_checked}} are required look-ups that are still open, the others are `coarse` events
that the rule does not require to be looked up, or events outside every sample. EDGAR's acceptance time is a UTC instant: read that way
it agrees with each of the {{lookups.press_release}} press releases looked up on date and label; read as New York time
it would put each before-open one inside the trading session (docs/validation/edgar-ledger.md §2). A wrong label puts the crush on the wrong day, which makes a
crush look smaller and a run-up look longer.

## 3. Method

### 3.1 Day 0

Day 0 is the first session close after the news reaches the market: the announcement day for a before-open report,
the next session for an after-close one ([ADR 0002](../adr/0002-day-zero-convention.md)). The label comes from a
document, never from the size of the stock's move: a price-gap rule would fix the labels of big movers and leave the
quiet events wrong. Time is counted in NYSE sessions.

### 3.2 IV measures

Every IV is recomputed from bid/ask mid prices with Black-76 on the forward price implied by put-call parity, so no
spot price, dividend or snapshot time is needed ([ADR 0003](../adr/0003-iv-measures.md)). The stored quantity is the
at-the-money total variance w = σ²T of each expiry. From it:

- **The 30-day IV** (the primary series): constant maturity of {{params.cm30_sessions}} sessions, interpolated between
  expiries on the same side of the event (extrapolated by at most {{vh.extrap.max}} sessions when none brackets the
  horizon), so it never borrows event variance from an expiry on the wrong side.
  The vendor's chain lists only a few expiries, so the weekly expiry right after an announcement is usually absent.
- **The front-expiry IV**: the first listed expiry after the event, followed through the window (exploratory).

**Checked against Cboe's single-stock volatility indices (run {{vx.fetched}}).** Cboe publishes a daily 30-day index
for five of our companies. ADR 0003 describes these indices as built with the VIX method from the whole out-of-the-money
strip, so they should sit above an at-the-money IV. The check compares our blind 30-day IV (`cm30_blind_iv`) with
each index from {{vx.window_from}} to {{vx.window_to}}. Its four bars come from ADR 0003 and were fixed in a
pre-registration before any download ([pre-registration](../validation/vx-preregistration.md),
[ledger](../validation/vx-ledger.md)). The correlation and the slope use changes in ln IV between two consecutive
sessions where both series have a value. The 95% intervals come from a moving-block bootstrap over sessions
({{vx.reps}} draws, blocks of {{vx.block}} sessions; the five names share the draws). Only these aggregates are
committed (`data/derived/vx_crosscheck.json`); the index values stay on the build machine.

| Company (index) | Changes | Correlation r [95% interval] | Bar i: r > 0.8 | Slope [95% interval] | 1 / reverse slope | Median spread, vol points | Largest yearly drift | Bar iii |
|---|---:|---:|:-:|---:|---:|---:|---:|:-:|
| AAPL ({{vx.aapl.index}}) | {{vx.aapl.n}} | {{vx.aapl.r}} {{vx.aapl.r_ci}} | {{vx.aapl.i}} | {{vx.aapl.slope}} {{vx.aapl.slope_ci}} | {{vx.aapl.rev}} | {{vx.aapl.spread}} | {{vx.aapl.maxdev}} | {{vx.aapl.iii}} |
| AMZN ({{vx.amzn.index}}) | {{vx.amzn.n}} | {{vx.amzn.r}} {{vx.amzn.r_ci}} | {{vx.amzn.i}} | {{vx.amzn.slope}} {{vx.amzn.slope_ci}} | {{vx.amzn.rev}} | {{vx.amzn.spread}} | {{vx.amzn.maxdev}} | {{vx.amzn.iii}} |
| GOOGL ({{vx.googl.index}}, on GOOG) | {{vx.googl.n}} | {{vx.googl.r}} {{vx.googl.r_ci}} | {{vx.googl.i}} | {{vx.googl.slope}} {{vx.googl.slope_ci}} | {{vx.googl.rev}} | {{vx.googl.spread}} | {{vx.googl.maxdev}} | {{vx.googl.iii}} |
| GS ({{vx.gs.index}}) | {{vx.gs.n}} | {{vx.gs.r}} {{vx.gs.r_ci}} | {{vx.gs.i}} | {{vx.gs.slope}} {{vx.gs.slope_ci}} | {{vx.gs.rev}} | {{vx.gs.spread}} | {{vx.gs.maxdev}} | {{vx.gs.iii}} |
| IBM ({{vx.ibm.index}}) | {{vx.ibm.n}} | {{vx.ibm.r}} {{vx.ibm.r_ci}} | {{vx.ibm.i}} | {{vx.ibm.slope}} {{vx.ibm.slope_ci}} | {{vx.ibm.rev}} | {{vx.ibm.spread}} | {{vx.ibm.maxdev}} | {{vx.ibm.iii}} |
| Pooled | {{vx.pooled.n}} | {{vx.pooled.r}} {{vx.pooled.r_ci}} | {{vx.pooled.i}} | {{vx.pooled.slope}} {{vx.pooled.slope_ci}} | {{vx.pooled.rev}} | | | |

"Median spread" is the index minus our IV over all days. "Largest yearly drift" is the largest distance of one calendar
year's median spread from that all-days median; bar iii passes when it is at most {{vx.tolerance}} vol points.

- **Bar i (correlation of daily changes above 0.8) passes for AAPL, AMZN and GS and fails for GOOGL, IBM and the pooled
  sample.** The verdict uses the point estimate, as pre-registered. Only IBM's interval lies wholly below 0.8. The
  intervals of the other four names and of the pooled sample hold 0.8, so for them the split between pass and fail is
  not sharp. With blocks of {{vx.block60}} sessions the pooled interval is {{vx.pooled.r_ci60}}.
- **Bar ii (slope ≈ 1): the pre-registration called it descriptive because it said the ADR set no tolerance, and that
  was wrong; by ADR 0003's own reading its slope falsifier is met.** ADR 0003's "How we'll know it's wrong" says the
  VX\* checks fail if the correlation is below 0.8, the slope is outside {{vx.ii_band}} or the day-0 crush ratio is
  outside {{vx.ii_band}} "for most of the five names" (erratum in [the ledger](../validation/vx-ledger.md)). The slope
  is below {{vx.ii_band_lo}} for {{vx.ii_below}} of the 5 names ({{vx.ii_below_names}}), which is most, so the slope
  falsifier is met. The correlation is below 0.8 for {{vx.i_fails}} of the 5, so that falsifier is not met, and the
  crush ratio ({{vx.iv.ratio}}, pooled, provisional) is inside its band, so that one is not met either. AAPL and AMZN
  are inside the slope band. Every slope is below 1 and no interval holds 1. Noise in our daily changes pulls this
  slope toward 0, and noise in the index's daily changes pulls the reciprocal of the reverse slope (our change on the
  index's) above the true slope; here that reciprocal is above 1 for every name ({{vx.rev_min}} to {{vx.rev_max}}), so
  the pair [slope, 1 / reverse slope] holds 1. That is not a test of a slope of 1 plus daily noise. The slope times the
  reverse slope is r², so the pair always contains the ratio of the two series' standard deviations, and here that
  ratio is {{vx.sd_min}} to {{vx.sd_max}} for the names ({{vx.pooled.sd}} pooled). The pair sits around 1 because the
  two series move by similar amounts, whatever the true slope is, and this check cannot say which series holds the
  noise.
- **Bar iii (a stable level spread) passes for all five names by the pre-registered rule, but the rule has little
  power.** The index sits above our IV on {{vx.above_min}} to {{vx.above_max}} of days, as ADR 0003 expects. No year's
  median moves more than {{vx.maxdev_max}} vol points from its name's all-days median. That does not show the spread
  holds still: GS's yearly medians step from about {{vx.gs.early_lo}}–{{vx.gs.early_hi}} vol points (2020–22) to about
  {{vx.gs.late_lo}}–{{vx.gs.late_hi}} (2023–26), a step of about {{vx.gs.step}} vol points, and GS passes only because
  its all-years median ({{vx.gs.spread}}) sits between the two levels.
- **Bar iv (day-0 crush ratio in [0.8, 1.2]) passes, provisionally.** Over the {{vx.iv.n}} primary-sample events of the
  five names, the mean day-0 change in ln VX is {{vx.iv.ratio}} times ours (event bootstrap {{vx.iv.ci}}). The
  interval lies below 1: in log terms the index falls a little less on day 0 than our IV. The ratio is pooled only
  ({{vx.iv.per_name_min}} to {{vx.iv.per_name_max}} events per name). Since 2026-11-09, {{vx.iv.documented}} of these
  events have a label that an SEC EDGAR filing confirms; {{vx.iv.not_checked}} (GS on the day after Columbus Day, when
  EDGAR's time is not read) keep the calendar's. The ratio did not change when EDGAR confirmed the labels, because no
  day 0 moved; it stays provisional with the timing labels.
- **Alignment.** Moving the index one session either way leaves almost no correlation (lag −1: {{vx.lag.m1}}; lag +1:
  {{vx.lag.p1}}; lag 0: {{vx.pooled.r}}), so the two series are on the same dates.
- **Changes over longer gaps** (between two shared values more than one session apart; pre-registered, no bar)
  correlate more: pooled r = {{vx.sec.r}} {{vx.sec.r_ci}} over {{vx.sec.n}} changes. Noise in the daily levels
  weighs less in a change over several sessions, so this is consistent with daily noise; but these changes come from
  other days (days where one series has no value), so the two correlations are not like for like. On these changes
  the pooled slope is {{vx.sec.slope}} and the reciprocal of the reverse slope {{vx.sec.rev}} {{vx.sec.rev_ci}}, a
  narrower pair, as the correlation is higher. For AAPL and AMZN alone that reciprocal is just below 1 (its interval
  holds 1).
- **Why the daily slopes are low (exploratory, not pre-registered).** Cboe's index counts calendar days and ours counts
  sessions, so a change across a weekend moves the two differently. Four checks, each exploratory and not
  pre-registered, are consistent with a clock effect. (1) {{vx.cal.end_monday}} of the {{vx.pooled.n}} one-session
  changes ({{vx.cal.end_monday_share}}) end on a Monday; before {{vx.cal.era_from}}, when our snapshots were taken on
  Mondays, Wednesdays and Fridays only, {{vx.cal.early_monday}} of the {{vx.cal.early}} changes end on a Monday. On Monday changes the mean change in ln
  VX is {{vx.cal.mon_vx}} and in ours {{vx.cal.mon_ours}} (other days {{vx.cal.oth_vx}} and {{vx.cal.oth_ours}}).
  (2) On Tuesday-to-Friday changes alone, r is {{vx.tf.pooled.r}} {{vx.tf.pooled.r_ci}} pooled ({{vx.tf.pooled.n}}
  changes; GOOGL {{vx.tf.googl.r}}, IBM {{vx.tf.ibm.r}}). (3) Without the {{vx.d0.dropped}} changes that end on a day 0,
  the pooled r is {{vx.d0.pooled.r}} {{vx.d0.pooled.r_ci}} (AMZN {{vx.d0.amzn.r}}, IBM {{vx.d0.ibm.r}}), so the
  correlation leans on the largest days. (4) Over non-overlapping changes of k sessions in the daily-snapshot era (from
  {{vx.cal.era_from}}), the pooled slope and 1 / reverse slope are {{vx.step1.pooled.slope}} and
  {{vx.step1.pooled.rev}} at k = 1 ({{vx.step1.pooled.n}} changes), {{vx.step10.pooled.slope}} and
  {{vx.step10.pooled.rev}} at k = 10 ({{vx.step10.pooled.n}}) and {{vx.step21.pooled.slope}} and
  {{vx.step21.pooled.rev}} at k = 21 ({{vx.step21.pooled.n}}); IBM stays below 1 ({{vx.step10.ibm.slope}} and
  {{vx.step10.ibm.rev}} at k = 10, {{vx.step21.ibm.slope}} and {{vx.step21.ibm.rev}} at k = 21). So the low daily
  slopes are consistent with being largely a clock effect that shrinks at longer horizons, except for IBM. That is a
  reading of exploratory numbers, with no intervals, and not proof.
- **The vendor's `iv_current` (third check, changes no verdict).** In DoltHub's `volatility_history` table,
  `iv_current` has no documented maturity. Our blind at-the-money IV at {{vh.horizons}} sessions (interpolated between the
  listed expiries, or extrapolated by up to {{vh.extrap.max}} sessions beyond them) comes closest to it at
  **{{vh.maturity}} sessions** (median |difference| {{vh.maturity_med}} vol points over {{vh.maturity_days}}
  company-days), the horizon of our 30-day IV ({{params.cm30_sessions}} sessions); the minimum is not at an edge of the
  grid. Many of the values at the ends of the grid are extrapolated: {{vh.extrap.h42}} of the {{vh.extrap.h42_n}} values
  at 42 sessions lie beyond the last listed expiry, and {{vh.extrap.h10}} of the {{vh.extrap.h10_n}} at 10 sessions
  before the first. *Exploratory, not pre-registered:* interpolating total variance on calendar days at 30 days fits
  better, with a median |difference| of {{vh.cal.med}} vol points against {{vh.cal.med21}} at 21 sessions on the same
  {{vh.cal.n}} company-days, and a change correlation with `iv_current` of {{vh.cal.r}} against {{vh.cal.r21}}. So
  `iv_current` reads as a 30-calendar-day IV, which shows up as about 21 sessions on our grid. This part of the check
  was not blind: ADR 0003 already held the hypothesis of about 30 days, annualised on calendar days. The
  {{vh.longest}}-session horizon has no value on any day, because no listed expiry is that long. The daily changes of
  `iv_current` correlate with the index at r = {{vh.r_vx}} {{vh.r_vx_ci}} (pooled), a little above ours, and the two
  intervals overlap. In the median, `iv_current` sits {{vh.spread_ours}} vol points above our IV and the index
  {{vh.spread_vx}} above `iv_current`.

### 3.3 Event variance and the implied move

For two expiries that both span the event, w_j = σ_d² τ_j + E, where τ_j is the time to expiry in sessions, σ_d² the
ordinary variance per session and E the extra variance of the event day. Two expiries give both unknowns: σ_d² is the
forward variance between them, and E = w₁ − σ_d² τ₁. The **implied move** is √E, the standard deviation of the
earnings-day move that the options price. E is read at day −1. Its median over the {{iv.move_n}} events with E > 0 is
a move of {{iv.move_median}} (10% of events below {{iv.move_p10}}, 10% above {{iv.move_p90}}). {{evar.nonpositive}}
of the {{sample.n_events}} primary events have E ≤ 0 and no implied move.

![The implied move √E at day −1 (iv_measures.json)](../images/fig-implied-move.png)

### 3.4 Abnormal IV

Abnormal IV is log IV against the event's own quiet baseline ([ADR 0004](../adr/0004-baseline-and-event-windows.md)):

- The **baseline** is sessions {{params.baseline}} before day 0, minus every session within [−21, +10] of another
  announcement by the same company. It must keep at least 20 clean sessions. It ends at −22 because from −21 on the
  30-day horizon already contains day 0.
- The **market adjustment** removes β × the change in ln VIX, with β estimated for each company from its pooled clean
  baseline changes. A mean-adjusted twin (no VIX) is kept as a check.
- The tested quantities are levels and one-session changes in log points, not cumulated abnormal IV: IV is a level, so
  summing abnormal levels counts one persistent shift many times. RUNUP is the abnormal level at day −1, CRUSH the
  abnormal change from day −1 to day 0, PERSIST_10 the abnormal level at day +10, ΔSIGMA_D the abnormal change in ln σ_d
  from day −1 to day 0. The event window is {{params.window}}.

### 3.5 The test suite

Events are not independent. Many companies report in the same weeks, so one market move hits many events at once, and
one company's events resemble each other. The **primary statistic** is a t-test of the equal-weighted mean with
two-way cluster-robust standard errors ([ADR 0005](../adr/0005-statistical-test-suite.md)):

- for the one-session measures (CRUSH, ΔSIGMA_D): clusters by day-0 date and by company;
- for the multi-week measures (RUNUP, PERSIST_10): clusters by earnings season and by company;
- t on min(G) − 1 degrees of freedom; when the seasons are very unbalanced, a randomisation (Rademacher) p-value by
  season replaces the t, as the ADR declared in advance.

The drivers (H5, H6) are coefficients in a regression of CRUSH on z-scored regressors: |surprise| (the EPS surprise
over the option forward price), ln σ_d at day −1, the term-structure slope at day −1 and size (ln market cap), with
sector and season fixed effects. H7 regresses the squared realised move r₀² on the implied variance E + σ_d²/252
(σ_d annualised) and tests a = 0 and b = 1 jointly. Both use two-way clustering by day-0 date and company.

**Robustness rows** (one-way clustering, BMP, Kolari-Pynnönen, Patell, sign and rank tests, mean-adjusted twins) are
reported but never decide a hypothesis. **Holm** corrects the seven primaries together; **Benjamini-Hochberg** gives
q-values within each family of exploratory rows.

### 3.6 Gate G1: checking the tests before trusting them

A test at 5% should reject a true null 5% of the time. Gate G1 checks this on the real event structure **before the
results run**: the results run refuses to start without the gate's report, and the milestone pages record that each
gate ran before its hypotheses' results (an order the files themselves cannot prove). It simulates {{g1.reps}} null data sets per design with the real dates, companies, gaps and
baselines, re-estimates every input with the package's own code, and counts how often each statistic rejects. A
statistic passes when its rate is at most {{g1.band_hi}}, the top of the exact 99% binomial band
[{{g1.band_lo}}, {{g1.band_hi}}] for {{g1.reps}} replications.

| | H1 | H2 | H3 | H4 | H5 | H6 | H7 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Primary rejects under the null (target 5%) | {{h1.g1}} | {{h2.g1}} | {{h3.g1}} | {{h4.g1}} | {{h5.g1}} | {{h6.g1}} | {{h7.g1}} |
| Verdict | {{h1.g1_verdict}} | {{h2.g1_verdict}} | {{h3.g1_verdict}} | {{h4.g1_verdict}} | {{h5.g1_verdict}} | {{h6.g1_verdict}} | {{h7.g1_verdict}} |

H1–H4 pass (H2 and H3 are conservative). **H5–H7 fail: their statistics are liberal at this design**, so a rejection
by them would not be trusted. They stay in the declared Holm family with their real p-values (section 4.1). A
robustness row that G1 finds oversized keeps its estimate and loses its p-value: {{withheld.n}} rows are withheld this
way ({{withheld.list}}).

## 4. Results

### 4.1 The seven hypotheses

Daily sample, market-adjusted, equal-weighted means (H1–H4) and two-way clustered regressions (H5–H7). Estimates are
in log points; H5 and H6 are log points of crush per standard deviation of the regressor.

| | Question | n | Estimate | 95% interval | p | G1 size | Holm p (H1–H7, binding) |
|---|---|---:|---:|---|---:|---:|---:|
| H1 | Does the 30-day IV fall from day −1 to day 0? | {{h1.n}} | {{h1.est}} | {{h1.ci}} | {{h1.p}} | {{h1.g1}} | **{{h1.p_holm}}** |
| H2 | Is IV abnormally high at day −1? | {{h2.n}} | {{h2.est}} | – | {{h2.p}} | {{h2.g1}} | **{{h2.p_holm}}** (G = {{h2.cut_g}}: {{h2.cut_p_holm}}) |
| H3 | Is IV back at its baseline at day +10? | {{h3.n}} | {{h3.est}} | {{h3.ci}} | {{h3.p}} | {{h3.g1}} | {{h3.p_holm}} |
| H4 | Does ordinary volatility change? | {{h4.n}} | {{h4.est}} | {{h4.ci}} | {{h4.p}} | {{h4.g1}} | {{h4.p_holm}} |
| H5 | Does a bigger surprise change the crush? | {{h5.n}} | {{h5.est}} | {{h5.ci}} | {{h5.p}} | **{{h5.g1}}** | {{h5.p_holm}} |
| H6 | Does the prior volatility level change it? | {{h6.n}} | {{h6.est}} | {{h6.ci}} | {{h6.p}} | **{{h6.g1}}** | {{h6.p_holm}} |
| H7 | Is the implied variance unbiased (a = 0, b = 1)? | {{h7.n}} | b = {{h7.b}} | {{h7.b_ci}} (b) | {{h7.p}} | **{{h7.g1}}** | {{h7.p_holm}} |

**Rejected at 5% after Holm: {{holm.rejected}}.** H2's verdict depends on the season count (section 4.3). H3–H7 are not
rejected. Bold G1 sizes failed the gate.

**Which Holm family binds is an open owner decision.** The binding family is the one declared at milestone 0, H1–H7.
A descriptive sensitivity drops the three hypotheses whose size check failed and corrects over H1–H4 only: H1
{{postgate.h1}}, H2 {{postgate.h2}}, and H2 with {{h2.cut_g}} seasons {{postgate.h2_cut}}, which would be rejected.
Dropping hypotheses after seeing their size check can only lower the others' Holm p, so it is not used as binding
here (milestone 4, decisions table row 24).

### 4.2 H1: the crush

The 30-day IV falls by {{h1.fall4}} log points from day −1 to day 0 (se {{h1.se}}, t = {{h1.t}} on {{h1.df}} df,
{{h1.g_time}} day-0 dates and {{h1.g_firm}} companies). The mean-adjusted twin, with no VIX adjustment, is {{h1.twin}}.
The median log change of the 30-day IV with no VIX adjustment (the mean-adjusted crush, which for one session is the
plain change of ln IV) is {{iv.crush_median}}; 10% of events are below {{iv.crush_p10}} and 10% above
{{iv.crush_p90}}.

![The distribution of the crush (iv_measures.json)](../images/fig-crush-histogram.png)

The crush is larger for after-close reporters ({{crush.amc}}, n = {{crush.amc_n}}) than for before-open ones
({{crush.bmo}}, n = {{crush.bmo_n}}); this split is exploratory. The front-expiry IV, which holds a larger share of event
variance, falls by {{crush.front_fall}} (mean-adjusted, n = {{crush.front_n}}). The older samples agree in sign and size:
{{crush.mixed}} in the mixed era (n = {{crush.mixed_n}}) and {{crush.coarse}} in the coarse era (n = {{crush.coarse_n}},
where the crush can span two sessions), both exploratory.

### 4.3 H2: the run-up, and its season-count dependence

At day −1 the abnormal 30-day IV is {{h2.est4}} log points. The primary statistic is the randomisation p-value by
season, because the {{h2.floor_g}} seasons are unbalanced. With {{h2.floor_g}} seasons and every season mean on the
same side, the p-value sits on its floor 2/2^{{h2.floor_g}} = {{h2.p}}, and Holm's multiplier for the second-smallest
p gives **{{h2.p_holm}}**: rejected.

**This verdict is a property of the season count, not of the data's strength.** ADR 0005 expected the October 2026
tail to be merged into July, which gives {{h2.cut_g}} seasons. Then the floor is {{h2.cut_p}} and the Holm p is
**{{h2.cut_p_holm}}: not rejected**. The direction is not in doubt: the two-way season × company t, a robustness row,
is {{h2.twoway_t}} (p {{h2.twoway_p}}), and every season mean is positive (milestone 3 §6.2).

The mean path shows where the run-up sits. The abnormal IV is already {{path.m10}} {{path.m10_ci}} at day −10 and
{{path.m1}} {{path.m1_ci}} at day −1: the 30-day IV holds the event from day −21 on, and the last ten sessions add
nothing on average. After-close reporters run higher at day −1 ({{path.amc_m1}}) than before-open ones
({{path.bmo_m1}}).

![The mean abnormal path with its 95% band (event_paths.json, market-adjusted aggregate)](../images/fig-mean-path.png)

### 4.4 H3 and H4: what is left after the event

At day +10 the abnormal IV is {{h3.est4}} (interval {{h3.ci}}, {{h3.g_time}} seasons, {{h3.df}} df). The path is
{{path.d0}} at day 0, {{path.p1}} at day +1, {{path.p5}} at day +5 and {{path.p10}} at day +10. Under the calibrated
design the test detects a persistence of {{h3.power80}} log points 80% of the time, so a smaller lasting effect could
go undetected.

Ordinary volatility changes by {{h4.est4}} log points (interval {{h4.ci}}, n = {{h4.n}}); the test has 80% power at
{{h4.power80}} log points. So the crush is the event variance leaving the 30-day horizon, not the market becoming calmer about the
stock.

![Abnormal log IV by company and event day (heatmap.json; mean-adjusted, descriptive)](../images/fig-heatmap.png)

### 4.5 H5–H7: the drivers, with liberal statistics

The crush regression has R² {{drivers.r2}} on {{h5.n}} events. A positive coefficient means a smaller fall.

- **H5, the surprise:** {{h5.est4}} per sd (interval {{h5.ci}}, p {{h5.p}}, Holm {{h5.p_holm}}): a bigger surprise
  goes with a slightly smaller crush. The statistic rejects {{h5.g1}} of the time under the null, so the p is weaker
  than it looks, and Holm does not reject. The effect does not survive other surprise measures: with the surprise
  scaled by its own history it is {{surprise.sue}} (q {{surprise.sue_q}}), with analyst dispersion {{surprise.disp}}
  (q {{surprise.disp_q}}), and with company fixed effects {{surprise.firmfe}} (q {{surprise.firmfe_q}}).
- **H6, the prior volatility level:** {{h6.est4}} per sd (interval {{h6.ci}}, p {{h6.p}}): no measurable effect.
- **The slope (exploratory):** a steeper term structure at day −1 goes with a larger crush, {{slope.est}} per sd
  (p {{slope.p}}, q {{slope.q}}). That is expected and partly mechanical: the slope proxies the event's share of the
  30-day variance. Its p and q come from the same two-way t that G1 found liberal for H5 and H6; G1 never sized the
  slope's own coefficient, so read it as an indication, not a test at 5%.
- **Size (exploratory):** {{size.est}} per sd (q {{size.q}}).

Power, from G1's calibrated design: H5's test detects {{h5.power80}} log points per sd 80% of the time, H6's
{{h6.power80}}. These powers belong to oversized tests.

## 5. Implied against realised moves

On day −1 the options price the event variance E and the ordinary variance σ_d²/252 of one session. If the day-0 move
is normal with that variance, its expected absolute size is √(2/π)·√(E + σ_d²/252), and fair pricing exceeds it
{{ivr.benchmark}} of the time, not 50%. The realised move r₀ is the change of the option-implied forward from day −1 to
day 0, on the same expiry both days.

| Measure | Value |
|---|---:|
| Events (E, σ_d and r₀ all present) | {{ivr.n}} |
| Events with E > 0, so with an expected move | {{ivr.n_pos}} |
| Median expected \|move\| | {{ivr.median_implied}} |
| Median realised \|move\| (all 336 events) | {{ivr.median_realised}} |
| Median ratio realised / expected | {{ivr.median_ratio}} |
| Share of moves beyond the expected \|move\| (fair: {{ivr.benchmark}}) | {{ivr.share}} (p {{ivr.share_p}}) |
| Mean r₀² over mean implied variance | {{ivr.var_ratio}} |
| H7 regression r₀² = a + b(E + σ_d²/252): b | {{h7.b3}}, interval {{h7.b_ci}} |
| H7 joint test a = 0, b = 1 | F({{h7.df_num}}, {{h7.df}}) = {{h7.f}}, p {{h7.p}}, Holm {{h7.p_holm}} |
| The same with E read at day −2 (n = {{h7.m2_n}}): b; joint p | {{h7.m2_b}}; {{h7.m2_p}} |

The typical realised move is smaller than the expected one (median ratio {{ivr.median_ratio}}), but the mean squared
move is {{ivr.var_ratio}} of the mean implied variance, so large moves weigh heavily in the average. On variance the
options are close to unbiased: b = {{h7.b}} with 1 inside its interval, and the share of moves beyond the expected size
({{ivr.share}}) is close to the fair {{ivr.benchmark}}. With E read one session
earlier, b is {{h7.m2_b}}: day −1 quotes are often wide on after-close announcement days, which may inflate E a little.
The joint test's G1 size is {{h7.g1}}, so even a rejection would not have been trusted; the b and share rows come from
the same kind of two-way statistic.

![Expected against realised move, one dot per event (implied_vs_realised.json)](../images/fig-implied-realised.png)

## 6. Trading implications: observations and their limits

**This section is not investment advice.** It gives no recommendation, no position and no size. It says what the
measured numbers describe about the past, and what they cannot say.

**What the numbers describe.**

1. **The IV fall was near-universal in direction in this sample.** In this sample the market-adjusted 30-day IV
   fell from day −1 to day 0 in {{h1.share_below}} of events, by {{h1.fall}} log points on average. But the fall is the
   event variance leaving the horizon (H4: ordinary volatility unchanged), and the term structure showed that variance
   in advance: E is read from it at day −1. A falling
   IV is not by itself a gain for anyone short options: that position's result depends on the realised move against
   the implied one, plus costs.
2. **On average the options priced the move about right.** b = {{h7.b}} {{h7.b_ci}}, {{ivr.share}} of moves beyond the
   expected size against {{ivr.benchmark}} for fair pricing. The data show no reliable average over- or
   under-pricing of the earnings-day move in this sample. The typical move was smaller than expected
   (median ratio {{ivr.median_ratio}}), while the mean squared move was {{ivr.var_ratio}} of the mean implied variance.
3. **The run-up is in place ten sessions early.** The 30-day IV already holds the event from 21 sessions before
   day 0; the abnormal level at day −10 ({{path.m10}}) and at day −1 ({{path.m1}}) are about the same on average.
4. **A steeper term structure went with a larger crush** ({{slope.est}} per sd). This is exploratory, partly
   mechanical, and from a statistic that is liberal at this design.
5. **The surprise does not reliably size the crush**, and the surprise is unknown before the event anyway.

**What they cannot say.**

- **Nothing about profit.** There are no bid-ask spreads, commissions, margin, slippage or position limits here. Day −1
  quotes on after-close days are often wide. A cost-aware test belongs to the sibling project
  `vol-strategy-backtester`.
- **Nothing intraday.** The data are daily closes, so they cannot say when during day 0 the IV falls or how the stock
  moves on the way.
- **A narrow, survivor sample.** {{sample.n_companies}} of today's largest S&P 500 companies, day 0 from
  {{sample.first_day0}} to {{sample.last_day0}}. Smaller, less liquid names and other periods may behave differently.
- **Provisional timing labels.** {{lookups.left}} of {{lookups.required}} required look-ups are open, and the
  {{lookups.audit}}-event audit of the EDGAR labels has not run. The {{funnel.daily_open}} events of the daily sample
  that still have the calendar's label fall {{funnel.daily_open.t1}} / {{funnel.daily_open.t2}} /
  {{funnel.daily_open.t3}} across the terciles of move size, smallest first, so the unresolved timing sits in the
  smaller-move events.
- **Liberal driver statistics.** H5–H7's tests reject {{h5.g1}}, {{h6.g1}} and {{h7.g1}} of the time under a true
  null at 5%.
- **The averages hide the spread.** The heaviest-tailed events drive the squared-move regression, and a single event
  can move far more than its options priced (the scatter in section 5).

## 7. Caveats, in one place

1. **Provisional timing labels:** {{lookups.done}} of {{lookups.required}} required look-ups are done
   ({{lookups.press_release}} by press release, {{lookups.edgar}} by SEC EDGAR filing time since 2026-11-09);
   {{lookups.left}} are open: {{lookups.left_labelled}} keep the calendar's label and {{lookups.left_unlabelled}}
   have none. The {{lookups.audit}}-event audit of the EDGAR labels and the
   press-release checks of the {{lookups.gap_questioned}} EDGAR labels that the price gap questions have not been done.
2. **H2 depends on the season count:** rejected with {{h2.floor_g}} seasons (Holm {{h2.p_holm}}), not rejected with the
   {{h2.cut_g}} that ADR 0005 expected (Holm {{h2.cut_p_holm}}).
3. **H5–H7's statistics are liberal:** G1 sizes {{h5.g1}}, {{h6.g1}} and {{h7.g1}} at 5% (one-way versions
   {{h5.g1_oneway}}, {{h6.g1_oneway}}, {{h7.g1_oneway}}). Every exploratory regression p and q comes from the same
   two-way t.
4. **Withheld robustness rows:** {{withheld.n}} rows keep their estimates but not their p-values, because G1 found
   them oversized.
5. **A common date component:** after the VIX adjustment the crush's average same-date correlation ρ̄ is
   {{rhobar}} (above ADR 0005's warning line of about 0.2). It is spread over most dates ({{rhobar.no_top10}} without
   the ten largest), not a stale snapshot, and a leave-one-company-out IV factor removes it ({{rhobar.loo}}). It is
   linearly unrelated to the change in ln VIX, which is close to automatic because β is fitted on that change. H1's
   two-way statistic is robust to same-date dependence; the Kolari-Pynnönen rows, which model it, are withheld for
   the crush. Adding a second market factor would change every market-adjusted number and is an owner decision.
6. **Which Holm family binds** (H1–H7 declared, or H1–H4 after the gate) is an owner decision (section 4.1).
7. **Survivorship:** the universe is today's largest companies.
8. **The Cboe check is mixed (section 3.2).** Against Cboe's 30-day indices for five names, the correlation of daily
   changes is below the pre-registered 0.8 for GOOGL ({{vx.googl.r}}), IBM ({{vx.ibm.r}}) and the pooled sample
   ({{vx.pooled.r}}), and every slope is below 1 ({{vx.pooled.slope}} pooled). By ADR 0003's own
   reading, which the pre-registration missed, the slope falsifier is met: {{vx.ii_below}} of the 5 slopes
   ({{vx.ii_below_names}}) are below {{vx.ii_band_lo}}. The correlation falsifier ({{vx.i_fails}} of 5) and the
   crush-ratio falsifier are not met. The level spread passes its pre-registered rule, which has little power (GS's
   yearly medians step by about {{vx.gs.step}} vol points). The day-0 crush ratio is {{vx.iv.ratio}} (pass,
   provisional like the timing labels: {{vx.iv.not_checked}} of its events keep the calendar's label). Exploratory
   checks are consistent with the low daily slopes being largely a clock effect, but do not prove it. Whether this
   meets ADR 0003's "How we'll know it's wrong" is an owner question (section 9).
9. **Not built:** the coarse-sample scale correction, the SPY placebo and the drop-the-largest-companies check of
   ADR 0004.
10. **No 3D hero render:** Blender was unreachable on 2026-10-29, so the Blender script
   (`tools/blender/event_terrain.py`) has not run. The 3D figures are three.js stills of the app's terrain view.

![The 3D terrain: each company's mean abnormal log IV (mean-adjusted) by event day, a three.js still from the app](../images/terrain-default.png)

## 8. How this report is built

The report is written in `docs/report/templates/earnings-vol-report.md`. `tools/report_numbers.py` fills every
placeholder in it (a key in double braces) from `data/derived/results.parquet`, the Cboe cross-check's aggregates
`data/derived/vx_crosscheck.json` (written by `tools/vx_crosscheck.py`), the app's JSON files and the kept output
`research/prototypes/rhobar_crush.out.txt`, and writes this file. A few counts are pinned instead of read: the
{{lookups.required}} required look-ups, why {{lookups.left}} of them are open and the {{lookups.gap_questioned}}
gap-questioned EDGAR labels, which need a Yahoo flag that stays local (`--check` compares them with the local stage
report when one exists). The same script fills the results blocks of the README and the PR/FAQ.

```bash
uv sync --frozen --group report                                      # once: python-docx and markdown-it-py
uv run --frozen python tools/report_numbers.py                       # fill the numbers (--check: verify only)
uv run --frozen --with playwright==1.64.1 python tools/screenshots.py   # app screenshots, figures, 3D stills
uv run --frozen --group report --with playwright==1.64.1 python tools/build_report.py   # PDF and DOCX
```

`tools/build_report.py` turns this Markdown into `earnings-vol-report.docx` (python-docx) and
`earnings-vol-report.pdf` (Chromium's print-to-PDF through Playwright). pandoc is not installed on the build machine.

## 9. Questions for the owner

1. **Audience.** Who is this report for: interviewers reading a portfolio, practitioners who know event studies, or a
   record for yourself? The answer decides how much of section 3 stays in the body.
2. **Tone.** Keep the cautious "measured and provisional" voice throughout, or open with a plainer executive summary
   and move the caveats to the end?
3. **What to cut.** Candidates: the robustness-row list (section 3.6), the exploratory driver variants (section 4.5),
   the older-sample numbers (section 4.2), the ρ̄ paragraph (section 7, item 5). Should any of them move to an
   appendix or out?
4. **The Holm family (milestone 4, decisions table row 24).** Keep the declared family H1–H7 as binding (H2 rejected
   with {{h2.floor_g}} seasons, not with {{h2.cut_g}}), or adopt the post-gate family H1–H4 (H2 rejected either way)?
5. **Trading implications.** Keep section 6 as observations with their limits, shorten it to the "cannot say" list,
   or drop it? Should it point to `vol-strategy-backtester` for a cost-aware test?
6. **Timing labels.** Publish with {{lookups.left}} of {{lookups.required}} required look-ups open and the
   {{lookups.audit}}-event audit of the EDGAR labels not run, or wait for both? Two of the open choices are yours:
   - **BRK.B.** Berkshire releases on Saturdays and files its 8-K days later, so most of the
     {{lookups.open.no_8k}} open look-ups without an 8-K are BRK.B's. Look up its press releases by hand, or leave
     them open?
   - **EDGAR in `coarse`.** EDGAR now labels only the look-ups ADR 0002 requires. Should it also label the `coarse`
     events that the rule leaves `not_checked`? That would remove the gap-triggered selection of that sample, and is
     an ADR change.
7. **The common date component.** Add an equal-weighted single-stock IV factor next to VIX in the market model? It would
   change every market-adjusted number.
8. **Exports.** Are a PDF and a DOCX the right formats, and is the app's dark theme right for the printed figures?
9. **The Cboe check (section 3.2).** ADR 0003 reads a correlation of daily changes below 0.8, a slope outside
   {{vx.ii_band}} or a day-0 crush ratio outside {{vx.ii_band}}, "for most of the five names", as a sign that the IV
   calculation is wrong. The pre-registration wrongly said the ADR set no tolerance for the slope. The slope is below
   {{vx.ii_band_lo}} for {{vx.ii_below}} of the 5 names ({{vx.ii_below_names}}), which is most: that falsifier is met.
   The correlation is below 0.8 for {{vx.i_fails}} of the 5 and the crush ratio is {{vx.iv.ratio}} (pooled,
   provisional): neither is met. Does the ADR's response (re-examine the forward, the filters and the interpolation)
   apply, or do the exploratory checks, which are consistent with the low daily slopes being largely a clock effect
   (slopes of {{vx.step10.pooled.slope}} at 10 sessions and {{vx.step21.pooled.slope}} at 21, except IBM), justify
   leaving the IV calculation as it is?
