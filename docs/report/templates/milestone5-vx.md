Run on {{vx.fetched}} by `tools/vx_crosscheck.py`; the numbers are filled in by `tools/report_numbers.py`, like the
report's. Window {{vx.window_from}} to {{vx.window_to}}; 95% intervals from a moving-block bootstrap over sessions
({{vx.reps}} draws, blocks of {{vx.block}}).

| Company (index) | Bar i: r of one-session changes [95% interval] | Slope [95% interval] | Median spread | Largest yearly drift | Bar iii |
|---|---|---|---:|---:|:-:|
| AAPL ({{vx.aapl.index}}) | {{vx.aapl.r}} {{vx.aapl.r_ci}} {{vx.aapl.i}} | {{vx.aapl.slope}} {{vx.aapl.slope_ci}} | {{vx.aapl.spread}} | {{vx.aapl.maxdev}} | {{vx.aapl.iii}} |
| AMZN ({{vx.amzn.index}}) | {{vx.amzn.r}} {{vx.amzn.r_ci}} {{vx.amzn.i}} | {{vx.amzn.slope}} {{vx.amzn.slope_ci}} | {{vx.amzn.spread}} | {{vx.amzn.maxdev}} | {{vx.amzn.iii}} |
| GOOGL ({{vx.googl.index}}) | {{vx.googl.r}} {{vx.googl.r_ci}} {{vx.googl.i}} | {{vx.googl.slope}} {{vx.googl.slope_ci}} | {{vx.googl.spread}} | {{vx.googl.maxdev}} | {{vx.googl.iii}} |
| GS ({{vx.gs.index}}) | {{vx.gs.r}} {{vx.gs.r_ci}} {{vx.gs.i}} | {{vx.gs.slope}} {{vx.gs.slope_ci}} | {{vx.gs.spread}} | {{vx.gs.maxdev}} | {{vx.gs.iii}} |
| IBM ({{vx.ibm.index}}) | {{vx.ibm.r}} {{vx.ibm.r_ci}} {{vx.ibm.i}} | {{vx.ibm.slope}} {{vx.ibm.slope_ci}} | {{vx.ibm.spread}} | {{vx.ibm.maxdev}} | {{vx.ibm.iii}} |
| Pooled ({{vx.pooled.n}} changes) | {{vx.pooled.r}} {{vx.pooled.r_ci}} {{vx.pooled.i}} | {{vx.pooled.slope}} {{vx.pooled.slope_ci}} | | | |

Bar ii was pre-registered as descriptive on a false premise (the pre-registration said ADR 0003 set no tolerance;
it did): no slope interval holds 1, the reverse regression's reciprocal is {{vx.rev_min}} to {{vx.rev_max}} by name,
and by the ADR's own reading the slope falsifier is met ({{vx.ii_below}} of 5 slopes, {{vx.ii_below_names}}, are below
{{vx.ii_band_lo}}; the correlation falsifier, {{vx.i_fails}} of 5, and the crush ratio are not). The pair [slope, 1 /
reverse slope] always contains the ratio of the two standard deviations ({{vx.sd_min}} to {{vx.sd_max}}), so that it
holds 1 is not a test. Bar iv, the day-0 crush ratio over {{vx.iv.n}} events (pooled, provisional): {{vx.iv.ratio}}
{{vx.iv.ci}}, {{vx.iv.verdict}}. Alignment: r = {{vx.lag.m1}} at lag −1 and {{vx.lag.p1}} at lag +1. Changes over longer
gaps: r = {{vx.sec.r}} {{vx.sec.r_ci}} ({{vx.sec.n}} changes). `volatility_history.iv_current`: maturity
{{vh.maturity}} sessions (median |difference| {{vh.maturity_med}} vol points); r with the index {{vh.r_vx}}
{{vh.r_vx_ci}}.
