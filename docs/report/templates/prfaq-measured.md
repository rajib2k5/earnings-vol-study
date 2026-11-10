## What we measured (2026-10-29)

Measured at milestones 1–4, collected here at milestone 5 and re-measured on 2026-11-09 with SEC EDGAR timing labels,
which are still **provisional** ({{lookups.done}} of {{lookups.required}} required look-ups done, {{lookups.left}} open). Day 0 from {{sample.first_day0}} to
{{sample.last_day0}}; {{sample.n_events}} primary events of {{sample.n_companies}} companies. The full account is the
[report](report/earnings-vol-report.md) (a draft the owner has not reviewed yet).

| | Result | Holm p (H1–H7) |
|---|---|---:|
| H1 crush | 30-day IV falls by {{h1.fall}} log points from day −1 to day 0 (interval {{h1.ci}}) | {{h1.p_holm}} |
| H2 run-up | IV sits {{h2.est}} log points above its baseline at day −1 | {{h2.p_holm}} ({{h2.cut_g}} seasons: {{h2.cut_p_holm}}) |
| H3 persistence | {{h3.est}} at day +10 (interval {{h3.ci}}) | {{h3.p_holm}} |
| H4 ordinary volatility | {{h4.est}} (interval {{h4.ci}}) | {{h4.p_holm}} |
| H5 surprise | {{h5.est}} per sd (interval {{h5.ci}}); the test's size is {{h5.g1}} | {{h5.p_holm}} |
| H6 prior volatility | {{h6.est}} per sd (interval {{h6.ci}}); size {{h6.g1}} | {{h6.p_holm}} |
| H7 implied vs realised | b = {{h7.b}} (interval {{h7.b_ci}}); {{ivr.share}} of moves beyond the implied \|move\| against a fair {{ivr.benchmark}}; size {{h7.g1}} | {{h7.p_holm}} |

**Where the milestone-0 draft was wrong, or has changed.** The draft above is kept as written at milestone 0 except
where marked "revised 2026-10-29". These are the places the results contradict it:

1. **Timing look-ups.** The draft said every event since daily option data began would be looked up by hand (How it
   works, step 1; Internal FAQ, "Timing labels"), and that quiet events would be checked as thoroughly as big movers.
   Instead, since 2026-11-09 the SEC EDGAR 8-K filing time decides where no press release was looked up:
   {{lookups.press_release}} required look-ups rest on press releases and {{lookups.edgar}} on EDGAR, and
   {{lookups.left}} are open. Neither claim holds fully yet: the open look-ups and the {{lookups.audit}}-event audit of
   the EDGAR labels remain, so every number here is provisional.
2. **The size check of the driver tests.** The draft planned regressions with two-way clustered errors and no size
   check of their own. Gate G1, extended to them at milestone 4 and run before their results run, found their
   statistics liberal: {{h5.g1}} (H5), {{h6.g1}} (H6) and {{h7.g1}} (H7) under a true null at 5%. They stay in the
   declared Holm family; none is rejected.
3. **The number of seasons.** ADR 0005 expected the run-up's events to fall into 7 seasons. There are
   {{h2.floor_g}}, unbalanced, so the randomisation p-value is H2's primary and its Holm verdict depends on that count
   ({{h2.p_holm}} with {{h2.floor_g}}; {{h2.cut_p_holm}} with {{h2.cut_g}}).
4. **The surprise question.** The external FAQ asks whether a bigger surprise causes a bigger crush. The measured
   coefficient points the other way, a slightly smaller fall ({{h5.est}} per sd), and it is not rejected after Holm and
   does not survive other surprise measures.
5. **The Cboe cross-check and subsample.** The draft named Cboe's single-stock volatility indices for five names as
   an independent check on the IV measures, as a second daily subsample ("How far back does it go?") and as a source of
   extra events (Internal FAQ, "Feasibility"). *Revised 2026-11-09:* the check ran, with its bars fixed before the
   download, and its result is mixed (report §3.2). The level spread passes its pre-registered rule for all five names
   (a rule with little power) and the day-0 crush ratio is {{vx.iv.ratio}}, inside 1 ± 0.2 (provisional). The
   correlation of daily changes is below the planned 0.8 for GOOGL ({{vx.googl.r}}), IBM ({{vx.ibm.r}}) and the pooled
   sample ({{vx.pooled.r}}), and every slope is below 1 (pooled {{vx.pooled.slope}}). The pre-registration wrongly said
   ADR 0003 set no tolerance for the slope; by the ADR's own reading its slope falsifier is met ({{vx.ii_below}} of 5
   slopes are below {{vx.ii_band_lo}}). The second subsample and the extra events are not built.
6. **What is committed.** The draft said no Cboe or Yahoo data would be committed. Under the owner's decision of
   2026-10-29 the repository commits the data the app and the docs need: aggregates of VIX-adjusted values, a VIX
   tercile label, two Yahoo-derived labels and the size coefficients (DATA.md). The VIX series, per-event VIX-adjusted
   values and raw downloads stay local. *Revised 2026-11-09:* the Cboe VX\* index values stay local too; only the
   cross-check's aggregate statistics are committed (`data/derived/vx_crosscheck.json`).
7. **The robustness tests.** The draft (How it works, step 4) said the Boehmer-Musumeci-Poulsen test and the
   Kolari-Pynnönen family are reported as robustness. They are computed, but for the crush (H1) gate G1 found them
   oversized, so their p-values are withheld and only their estimates are shown ({{withheld.n}} robustness rows in all
   lose their p-value this way).
8. **The warning line on ρ̄.** ADR 0005, written at milestone 0, read a same-date correlation above about 0.2 as a
   failed VIX adjustment or a data error. The crush's ρ̄ is {{rhobar}}. No data error and no single bad date was found:
   it is one common date component, linearly unrelated to the change in ln VIX (milestone 4 §6.6). That last part is
   close to automatic, because each company's β is fitted on the change in ln VIX, so it cannot rule out VIX entering
   in another form.
9. **Where the report is.** The draft pointed to `reports/report.pdf`; the report is
   `docs/report/earnings-vol-report.pdf` (and `.docx`, `.md`).

Confirmed as predicted: the sample size ({{sample.n_events}} events, inside the draft's 330–360), and a crush large
against day-to-day noise (t = {{h1.t}}).
