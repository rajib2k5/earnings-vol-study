An event study of how earnings announcements move option implied volatility (IV), on {{sample.n_events}}
announcements by {{sample.n_companies}} large US companies with day 0 from {{sample.first_day0}} to
{{sample.last_day0}}. A Python pipeline recomputes IV from DoltHub's open option quotes, lines each announcement up in
event time and tests seven hypotheses declared before any data was seen, after a simulation gate (G1) has checked each
test's size on the real event structure. **Measured:** from the last close before the news to the first close after it,
the 30-day IV falls by {{h1.fall}} log points (about {{h1.pct_fall}}; p = {{h1.p}}, Holm {{h1.p_holm}}), ordinary
volatility does not change ({{h4.est}}, p = {{h4.p}}), IV is back at its baseline ten sessions later, and the options
priced the earnings-day move about right on average (realised squared move {{h7.b}} × the implied variance, interval
{{h7.b_ci}}). **Provisional:** only {{lookups.done}} of the {{lookups.required}} required before-open/after-close labels
have been checked against a document. A React app draws the exported results, and a written report sums them up.
