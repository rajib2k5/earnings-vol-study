# Architecture decision records

Each ADR records one decision. It gives the reasoning, the alternatives rejected (and what would have to be true for
them to win), and how we would notice that the decision is wrong. The data model they share is
[`../architecture/data-model.md`](../architecture/data-model.md).

| ADR | Decision in one line | Status |
|---|---|---|
| [0001](0001-overall-architecture.md) | One-way layered pipeline. Read-only, commit-pinned Dolt CLI reads. Parquet cache outside the repo. Versioned per-view JSON. Only DoltHub-derived tables committed. | Accepted (M0), revised after review |
| [0002](0002-day-zero-convention.md) | Day 0 = first session whose closing snapshot follows the news (BMO → D, AMC → next session). Timing taken from documents, never from IV and never decided by the price move. By default the press release of every `daily` and `mixed` event is looked up by hand; SEC EDGAR 8-K Item 2.02 acceptance times instead are **proposed: pending owner decision**. The overnight gap is a local diagnostic. | Accepted (M0), revised after review and delta review |
| [0003](0003-iv-measures.md) | Recompute IV (Black-76 on the 4-strike parity forward, OTM side, session clock). Event-aware 30-day IV is primary. Event variance E à la Dubinsky-Johannes, stored signed. | Accepted (M0), revised after review |
| [0004](0004-baseline-and-event-windows.md) | Window [−10, +10]. Baseline [−60, −22] minus other events' [−21, +10], with at least 20 sessions. Market-adjusted log IV. Test run-up, crush and persistence, not CAAIV. | Accepted (M0), revised after review |
| [0005](0005-statistical-test-suite.md) | $A=\sum a e$ representation. H1–H4 are equal-weighted means. Primary statistic: a two-way cluster-robust t, clustered by day-0 date × firm for one-session measures and by season × firm for run-up and persistence. The Kolari-Pynnönen family (KP 2010; Kolari, Pape & Pynnönen 2018; Pynnönen 2022) is reported as robustness. Seven-hypothesis Holm family. | Accepted (M0), revised after review |

Format: Status / Context / Decision / Consequences / Alternatives rejected / How we'll know it's wrong.

**Revised after the milestone-0 review** ([ledger](../validation/m0-methodology-ledger.md)). Each ADR opens with a
short note naming the refuted claims and what changed. Two statements on this page changed with them:

- **ADR 0005's statistic.** This page said its primary statistic was "our own, non-standard generalisation". It was
  at most a refinement of Kolari, Pape & Pynnönen (2018), and it is no longer primary.
- **Where the simulations live.** This page said the scratch simulations "are not in the repository". They are.

**Where the numbers come from.** Numbers stated as measured were measured on 2026-10-28 through the DoltHub API, a
public API (SEC EDGAR, Crossref), or a prototype script. Each ADR says which.

- Every simulation an ADR quotes is in [`research/prototypes/`](../../research/prototypes/) with its output kept
  beside it, or is a review probe in [`../validation/probes/`](../validation/probes/). Each re-runs with fixed seeds.
- **One exception, added after the delta review:** ADR 0002 §3's route-(a) rows and its label-free-tercile check come
  from an extension of the delta probe `d4_default_gap_selection.py` that is not yet in the repository. ADR 0002
  says so where it quotes them. Milestone 1 adds the script and its output to `research/prototypes/`.
- ADR 0005 states the design of each one. Milestone 3 rebuilds them as seeded tests, including gate G1.
