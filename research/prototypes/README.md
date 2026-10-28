# Design prototypes (milestone 0)

Small throwaway scripts the architect wrote while deciding ADRs 0003–0005. They are kept so that
every number those ADRs quote can be re-run. They are **not** part of the `earnings_vol` package.
They are **not reviewed or tested** to the package's standard. Milestones 1–3 replace each one
with tested code in `src/`.

| Script | Backs which claim | Output kept here |
|---|---|---|
| `spacing.py` | ADR 0004: the gaps between consecutive reports, how often a fixed [−60, −20] baseline would overlap the previous report's [0, +10] window (97.1%) or contain its day 0 (20.3%), and how many clean baseline sessions remain after the exclusion | (run it: it prints in under a second) |
| `worked.py` | ADR 0003: the hand-worked AAPL 2025-10-30/31 example (4-strike parity forward, ATM total variance, event variance E, an identity check that can fail) | `worked.out.txt`. **Licence notice:** its values are derived from bid and ask quotes in the DoltHub database `post-no-preference/options` (CC BY-SA 4.0; attribution: DoltHub, post-no-preference; changes: selected and computed on by this project). The notice is here, not in the file, because the file is regenerated with `> worked.out.txt` (see `worked.py`) and a hand-added first line would be lost. |
| `leak_grid.py` | ADR 0003 §b: the range of the event-variance leak of blind 30-day interpolation over the vendor's expiry grid | `leak_grid.out.txt` |
| `kp_sim.py` | ADR 0005 §2g: size of t, BMP and KP (2010) when every event shares the same dates (equicorrelation) | `kp_sim.out.txt` |
| `kp_partial.py` | ADR 0005 §2g: size of BMP, KP (2010) with r̄ over all pairs, and the per-pair overlap form, when one-session event dates only partly overlap | `kp_partial.out.txt` |
| `kp_partial_clamp.py` | ADR 0005 §2g: the same, with the correlation clamped at 0 | `kp_partial_clamp.out.txt` |
| `h2h3_size_sim.py` | ADR 0005 §2g and gate G1: size and power of every candidate statistic for RUNUP, PERSIST_10 and CRUSH at the real daily design (N = 352, everything estimated, 2,000 reps per design). It takes about 2.5 minutes on 20 cores. | `h2h3_size_sim.out.txt` |
| `h2h3_followup_sim.py` | ADR 0005 §2g table 4: after the second review, one-way vs two-way (× firm) clustering, CR2, Rademacher enumeration and the Webb bootstrap under firm drift, random firm effects and unbalanced seasons (4,000 reps per design, about 15 seconds). It imports the design from `h2h3_size_sim.py`. | `h2h3_followup_sim.out.txt` |
| `route_a_vs_b.py` | ADR 0002 §3 (delta note): how often the kept events have a wrong day 0, by true-move tercile, under no check, the old gap-triggered default, route (a) (a press-release look-up for every event) and the `coarse` rule; plus the C0 control's terciles (flat for any label-free measure, so not evidence for `abs_move_cand_max` itself). Simulated world: 365 events, 3% wrong labels. | `route_a_vs_b.out.txt`: two runs, the default (t₃ gaps) and `--nu 1e9` (normal gaps) |

Run from the repository root, for example `uv run --no-sync --frozen python research/prototypes/spacing.py`.

**Revised after the milestone-0 review** (`docs/validation/m0-methodology-ledger.md`):

- **`worked.py`** took the parity forward as the median over *all* strikes. ADR 0003 takes it over the 4 strikes with
  the smallest |C − P|.
  - It now follows the ADR, which moved the oracle E from 0.00069327 to 0.00088284.
  - Its old "identity check" compared an expression with itself. It is replaced by one that runs a second time with a
    planted bug and must fail there.
- **`spacing.py`** labelled 97.1% as "day −60 within the previous [0, +10]". It is the share of gaps in which the
  baseline *overlaps* that window. The day −60 share, 83.3%, is now printed too.
- **`h2h3_size_sim.py`**, **`h2h3_followup_sim.py`** and **`leak_grid.py`** are new.
  - `h2h3_size_sim.py` is the first size evidence for the multi-session measures. It moved H2/H3 to season clusters.
  - A second adversarial review found that firm-level persistence breaks one-way clusters. The follow-up measured it
    and moved every H1–H4 primary to two-way clustering with firm.
  - The second review also found two bugs in the prototypes, both fixed:
    - `h2h3_size_sim.py`'s "ISO week" used numpy's Thursday-anchored weeks. The fix moved that row by at most 0.4
      points.
    - `spacing.py` and `h2h3_size_sim.py` sent an AMC release on a non-session day one session too far. The fix
      changes nothing, because no row of the extract has a non-session date.
- The overlap-weighted KP is **not** our own generalisation, as this page used to say. It is the per-pair form of
  Kolari, Pape & Pynnönen (2018). Pynnönen (2022, J. Risk Financial Manag. 15(4):149) gives the per-pair weight. Both
  are cited in ADR 0005 §2e.

**Limits.**

- `kp_*.py` cover a one-session measure at N = 50 with no autocorrelation.
- `h2h3_size_sim.py` and `h2h3_followup_sim.py` cover the daily design with baselines that have no internal holes or
  missing sessions. They do not cover:
  - the coarse sample;
  - cross-firm lagged correlation;
  - persistent common changes;
  - the real event set after milestone 1.

  Gate G1 in ADR 0005 §5 adds those at milestone 3.
- Their 187 distinct day-0 dates are inflated by the synthetic firms' ±3-session jitter.

`iv_persistence_mc.py` (from the literature review, `docs/concepts/00-background.md` §9) simulates
why abnormal IV *levels* must not be summed. It uses assumed parameters and checks size at 5%
nominal. It printed:
pooled lag-1 autocorrelation of daily IV changes −0.173; false-positive rate 0.675 for summed
levels and 0.022 for summed changes, over 11 days.

**Data.** `spacing.py` and `h2h3_size_sim.py` read `data/derived/earnings_calendar_30_large_caps.json`, a DoltHub
`post-no-preference/earnings` extract. `worked.py` hard-codes a handful of bid/ask quotes from DoltHub
`post-no-preference/options`. Both sources are CC BY-SA 4.0 (attribution: DoltHub,
post-no-preference); see `data/derived/README.md`. `h2h3_size_sim.py` uses only the event dates; the IV paths it
tests are simulated.
