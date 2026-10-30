Daily sample (day-0 window {{sample.day0_from}} to {{sample.day0_to}}; the {{sample.n_events}} primary events have day 0
from {{sample.first_day0}} to {{sample.last_day0}}), market-adjusted (VIX, β per company). **Timing labels
provisional: {{lookups.done}} of {{lookups.required}} required look-ups done.** H1–H4 are equal-weighted means of
abnormal log IV in log points; H5 and H6 are log points of crush per standard deviation of the regressor (positive: a
smaller fall); H7 is the joint test that the implied variance is unbiased for the realised squared move. "G1 size" is
how often the primary statistic rejects a true null at 5% in gate G1's calibrated simulation ({{g1.reps}}
replications; pass at most {{g1.band_hi}}). Holm runs over the declared family H1–H7, which is binding.

| | Question | n | Estimate | p | G1 size | Holm p (H1–H7) |
|---|---|---:|---:|---:|---:|---:|
| H1 | How much does the 30-day IV fall from day −1 to day 0? | {{h1.n}} | {{h1.est}} | {{h1.p}} | {{h1.g1}} | **{{h1.p_holm}}** |
| H2 | Is IV abnormally high at day −1? | {{h2.n}} | {{h2.est}} | {{h2.p}} | {{h2.g1}} | **{{h2.p_holm}}**; with {{h2.cut_g}} seasons {{h2.cut_p_holm}} |
| H3 | Is IV back at its baseline at day +10? | {{h3.n}} | {{h3.est}} | {{h3.p}} | {{h3.g1}} | {{h3.p_holm}} |
| H4 | Does ordinary volatility (σ_d) change? | {{h4.n}} | {{h4.est}} | {{h4.p}} | {{h4.g1}} | {{h4.p_holm}} |
| H5 | Does a bigger earnings surprise change the crush? | {{h5.n}} | {{h5.est}} per sd | {{h5.p}} | **{{h5.g1}}** (fail) | {{h5.p_holm}} |
| H6 | Does the prior volatility level change it? | {{h6.n}} | {{h6.est}} per sd | {{h6.p}} | **{{h6.g1}}** (fail) | {{h6.p_holm}} |
| H7 | Is the implied variance unbiased (a = 0, b = 1)? | {{h7.n}} | b = {{h7.b}} {{h7.b_ci}} | {{h7.p}} | **{{h7.g1}}** (fail) | {{h7.p_holm}} |

- **H1 and H2 are rejected; H3–H7 are not.** H2's p is the floor of a randomisation test over {{h2.floor_g}} season
  clusters, so its Holm verdict depends on that count: with the October 2026 tail merged into July
  ({{h2.cut_g}} seasons, as ADR 0005 expected) it is {{h2.cut_p_holm}}, not rejected. Its direction is not in doubt
  (two-way t {{h2.twoway_t}}).
- **H5–H7 failed gate G1**: their statistics reject {{h5.g1}}, {{h6.g1}} and {{h7.g1}} of the time under a true null,
  so a rejection by them would not be trusted. They stay in the declared Holm family with their real p-values.
  Without them (a descriptive sensitivity, not binding) the Holm p would be H1 {{postgate.h1}}, H2 {{postgate.h2}}
  ({{h2.cut_g}} seasons: {{postgate.h2_cut}}). Which family binds is the owner's decision.
- {{ivr.share}} of day-0 moves exceeded the implied |move|, against {{ivr.benchmark}} under fair pricing of a normal
  move (p {{ivr.share_p}}). Exploratory: a steeper term structure at day −1 goes with a larger crush
  ({{slope.est}} per sd, q {{slope.q}}, from the same liberal two-way t).
- {{withheld.n}} robustness rows keep their estimate but not their p-value, because G1 found them oversized. The
  crush's same-date correlation after the VIX adjustment is ρ̄ = {{rhobar}}: one common date component, which H1's
  two-way statistic is robust to.

Every measured number in this block is filled in by `tools/report_numbers.py` from `data/derived/results.parquet`,
`app/public/data/*.json` and, for ρ̄, the kept output `research/prototypes/rhobar_crush.out.txt`; the {{lookups.required}} required
look-ups are pinned in the script. `--check` fails when a number is stale or the data contradict a sentence here.
