# Survivorship bias in the universe

Concept note for milestone 1. Written 2026-10-29. The rule is in `params.yaml` (section `universe`) and
`src/earnings_vol/ingest/universe.py`.

## 1. The rule used

The 50 largest current S&P 500 members by Yahoo market cap on 2026-10-29, one share class per company, among those
with DoltHub calendar rows from 2024-09-11 on and option snapshots on 2026-10-26. The five companies with a CBOE
single-stock volatility index (AAPL, AMZN, GOOGL, GS, IBM) are added if the rank leaves them out; at this rank date all
five were inside the top 50 anyway (GS 42nd, IBM 48th).

## 2. What survivorship bias is

A sample chosen by *today's* status contains only the firms that survived to today in good shape. Looking back from
2026, it holds firms that are large now, and leaves out firms that were large in 2020 but shrank, were bought, or left
the index. A study of how stocks behaved since 2020 on such a sample over-weights the winners.

## 3. What it does to this study, and what it does not

- **Who is in.** Firms that grew into the top 50 (Palantir, CrowdStrike, Arista, Micron in this list) are in it for
  their whole history, including years when they were much smaller and their options less liquid.
- **Direction of a bias.** Firms whose stock rose may have had more good surprises. If the size of the IV crush relates
  to surprise size or sign, the sample's average may differ from that of "large firms at the time".
- **Why it is limited here.** The primary (daily) sample runs from December 2024, about two years before the rank
  date, so few of its firms changed rank dramatically within it. The 2020–2024 robustness sample is more exposed.
- **What it does not do.** It does not bias the *day-0 convention* or the timing labels; it is about which firms, not
  which days.

## 4. Remedy, not taken

A point-in-time universe (the 50 largest at the start of each year) removes the bias but needs historical market
caps (shares outstanding over time), which the free sources do not give reliably. The bias is stated instead: in
`app/public/data/sample_funnel.json` (`caveats`), on the app's Sample page and here.
