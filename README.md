# Earnings & Implied Volatility: an event study

An event study of how earnings announcements move options implied volatility. For each announcement by about 50 large
US companies, the project lines up the implied-volatility (IV) series in event time and measures the run-up before the
news, the fall ("IV crush") after it, and how long the fall lasts. It also compares the move the options priced with the
move the stock really made. A Python pipeline computes every number from open data and exports versioned JSON files. A
React app only checks and draws those files. Every design choice is written down in a short decision record.

**Not financial advice.** This is research for learning. It describes the past, ignores transaction costs and covers
large, liquid US stocks only.

**Status:** Milestone 4: the drivers of the crush and implied against realised moves (built, adversarially reviewed
and fixed; pending the owner's review). Its three driver hypotheses (H5–H7) failed the size gate G1, run before their
results: their statistics are liberal at this design. They stay in Holm's declared family H1–H7 with their real
p-values and their G1 size beside them, and none is rejected
([milestone 4 page](docs/milestones/04-drivers.md)). Milestone 3: the event study (built, reviewed and fixed). Milestone 1
chose the 50 companies and built their 1,353 earnings announcements with the session each reached the option market
(day 0); milestone 2 recomputed implied volatility from the DoltHub bid/ask quotes. Milestone 3 measures abnormal IV
around each announcement (log IV against its own clean baseline, adjusted for VIX with a beta per company) and tests
the run-up, the crush, the persistence and the change in ordinary volatility on the primary sample of 347 events. The
primary test is a t with two-way cluster-robust standard errors (announcement date × company for the one-session
measures, season × company for the run-up and persistence), and its size was checked first on the real event set
(gate G1: every primary passed). **The timing labels are provisional**: 20 press releases were looked up and timed,
and the rest keep the calendar's labels until SEC EDGAR filing times can be read; EDGAR is accepted as the timing
source (2026-10-28), but its client runs only once the owner's contact string is set
([ADR 0002](docs/adr/0002-day-zero-convention.md)). The universe is today's 50 largest S&P 500 members, so the sample
has survivorship bias.

## What the study answers

- Does IV run up in the days before an earnings announcement?
- How big is the crush right after the announcement, and how quickly does IV settle?
- Is IV abnormal compared with a baseline window, and is that statistically significant when many companies report in
  the same few weeks?
- What drives the size of the run-up and the crush: the earnings surprise, or the level of IV beforehand?
- Do the moves that options imply for earnings match the moves that are actually realised?

The full story, written backwards from the finished study, is in the [PR/FAQ](docs/prfaq.md).

## Repository layout

```
earnings-vol-study/
├── README.md
├── LEARNING_LOG.md             index of milestone pages, my predictions, explain-it-back grades
├── LICENSE                     MIT, for the code
├── params.yaml                 every tunable choice: universe rule, pinned Dolt commits, sample ranges, windows
├── pyproject.toml              Python project and pinned dependencies
├── uv.lock                     exact Python dependency versions
├── .python-version             3.12
├── src/earnings_vol/           the Python package, one sub-package per ADR 0001 layer
│   ├── __init__.py             the package version
│   ├── config.py               where the data lives on disk (VOL_DATA_DIR)
│   ├── contract.py             the JSON envelope Python gives the app
│   ├── params.py               loads params.yaml and hashes it (params_hash)
│   ├── schema.py               the schema registry: every stored table, column, type and licence class
│   ├── store.py                the writer: checks a table against the registry, writes Parquet and a manifest
│   ├── ingest/                 Dolt (through a private mirror), Wikipedia, Yahoo, FRED; the gated EDGAR client
│   ├── events/                 sessions, market_daily, security, events, eps, timing_check
│   ├── measures/               session_snapshot, Black-76 on the parity forward, chain_expiry, iv_daily, event_iv
│   ├── panel/                  the window matrices, abnormal IV, event_measures and its regressor columns
│   ├── stats/                  clustering, the event tests, regressions, gate G1 (H1-H7), Holm and BH, results
│   └── export/                 the JSON views: funnel, IV measures, tests, paths, terrain, heatmap, drivers
├── tools/
│   ├── export_app_data.py      writes the nine app/public/data/*.json files (contract 0.5.0)
│   ├── build_notebooks.py      generates the notebooks from src/
│   ├── diagrams/               vendored local diagram toolkit (build.py + diagram_kit/); also public at github.com/rajib2k5/vol-diagram-kit
│   └── blender/                3D hero-render script
├── tests/                      pytest tests for src/ and tools/
├── notebooks/                  generated notebooks (never edited by hand)
│   ├── 00_scaffold_tour.ipynb
│   ├── 01_events.ipynb
│   ├── 02_iv_measures.ipynb
│   ├── 03_event_study.ipynb
│   └── 04_drivers.ipynb
├── data/derived/               small derived tables, CC BY-SA 4.0
│   ├── README.md               what is here, and the licence terms
│   ├── LICENSE                 CC BY-SA 4.0 notice
│   ├── security, ticker_alias, session, events, eps, session_snapshot, iv_daily, event_iv,
│   │   timing_check, event_window_obs, event_measures, results   .parquet, written by the pipeline
│   └── earnings_calendar_30_large_caps.json   DoltHub extract, input to research/prototypes/spacing.py
├── data/manual/
│   └── press_release_checks.csv   the hand-kept record of press-release timing look-ups (read by the events layer)
├── research/prototypes/        throwaway scripts behind numbers quoted in the ADRs (not tested, not reviewed)
│   ├── README.md               which script backs which claim, and their limits
│   ├── spacing.py, worked.py   event spacing (ADR 0004), the AAPL worked example (ADR 0003)
│   ├── leak_grid.py            the event-variance leak of blind 30-day interpolation (ADR 0003)
│   ├── kp_sim.py, kp_partial.py, kp_partial_clamp.py   size of the KP tests, one-session measure (ADR 0005)
│   ├── h2h3_size_sim.py, h2h3_followup_sim.py   size and power at the real daily design (ADR 0005)
│   ├── g1_moments.py, g1_phi.py   gate G1's moment check and its sensitivity to the AR of levels (milestone 3)
│   ├── g1_regression_size.py, rhobar_crush.py   why H5-H7 fail G1; the crush's common IV factor (milestone 4)
│   └── iv_persistence_mc.py    why IV levels must not be summed (ADR 0004); outputs in *.out.txt
├── docs/
│   ├── prfaq.md                the product story
│   ├── adr/                    architecture decision records 0001 to 0005
│   ├── architecture/           diagrams, specs and the data model
│   │   ├── README.md
│   │   ├── data-model.md
│   │   ├── specs/              YAML sources of the diagrams
│   │   ├── out/                diagrams built from specs/ (Mermaid, SVG, PNG, draw.io, Lucid)
│   │   └── graph/              a graphify knowledge graph of the repository (generated; see its README)
│   ├── concepts/               background reading, one note per new idea
│   │   ├── 00-background.md
│   │   └── 01-sessions-and-day-zero.md … 15-a-common-factor-in-single-stock-iv.md
│   ├── milestones/             one learning page per milestone
│   │   ├── 00-scaffold-and-design.md
│   │   ├── 01-universe-and-events.md, 02-iv-measures.md, 03-event-study.md
│   │   └── 04-drivers.md
│   └── validation/             adversarial review ledgers and the probe scripts behind them
│       ├── m0-code-ledger.md, m0-methodology-ledger.md, m0-delta-ledger.md, m0-delta2-ledger.md
│       └── probes/
└── app/                        the React + TypeScript + Vite app
    ├── src/lib/                small pure helpers and thin components (shell, About, Sample, Architecture), with tests beside them
    ├── src/three/              the lazy-loaded 3D view
    ├── src/test/               shared test fixtures
    ├── public/data/            JSON written by Python (never edited by hand)
    ├── CLAUDE.md               rules for working in the app
    ├── DATA.md                 the JSON contract and the data licences
    └── package.json
```

The diagrams are in [`docs/architecture/README.md`](docs/architecture/README.md). They are not copied here, so there is
only one version to keep right.

## How to run

You need Python 3.12 with [uv](https://docs.astral.sh/uv/), and Node with npm for the app. The tests, the notebook
check, the exporter and the app need no market data: they use fixtures and the committed tables in `data/derived/`.
Rebuilding those tables does need data (below).

```bash
uv sync                                          # install the Python dependencies
uv run pytest -q                                 # run the Python tests (the two dolt-marked tests skip without dolt)
uv run python tools/build_notebooks.py --check   # check the notebooks match src/
uv run python tools/export_app_data.py           # write app/public/data/meta.json and sample_funnel.json (reads data/derived and params.yaml only)
cd app && npm ci && npm run dev                  # run the app locally; the Sample page draws sample_funnel.json
npm run verify                                   # inside app/: lint + tests + coverage + production build
```

`uv run python tools/build_notebooks.py` (without `--check`) rewrites the notebooks. Never edit them by hand.

### Rebuilding the data (milestones 1 and 2)

This needs the `dolt` binary (2.6.1 was used), the two shared DoltHub clones in `$VOL_DATA_DIR/dolthub/` (`earnings`
and `options`; `cd $VOL_DATA_DIR/dolthub && dolt clone post-no-preference/<name>`), about 10 GB of disk for the mirrors,
and network access to Wikipedia, Yahoo Finance and FRED. The option-chain extract took about 22 minutes of query time
on the development machine.

```bash
uv run python -m earnings_vol.ingest.run --chain-from 2020-01-01   # mirrors, then universe, calendar, EPS, prices, FRED, option chains
uv run python -m earnings_vol.events.run                           # session, market_daily, security, ticker_alias, events, eps, timing_check
uv run python -m earnings_vol.measures.run                         # session_snapshot, the close check, chain_expiry, iv_daily, event_iv
uv run python tools/export_app_data.py                             # meta.json, sample_funnel.json, iv_measures.json for the app
```

`ingest.run --only mirrors|universe|small|prices|fred|chain` runs one step. Nothing calls SEC EDGAR yet: its client
(`src/earnings_vol/ingest/edgar.py`) refuses to run until the environment variable `SEC_EDGAR_USER_AGENT` holds a real
contact, and no request has been made. The commits read from DoltHub are pinned in `params.yaml`, so a re-run reads the
same data. The milestone pages list the exact commands and what each one measured.

## Data

- **Where it lives.** Large and unshareable data stays *outside* the repository, under `VOL_DATA_DIR`
  (default `~/data/vol-projects`). `src/earnings_vol/config.py` is the only place that knows the folder layout. From
  milestone 1 the pipeline never queries the two shared DoltHub clones in `$VOL_DATA_DIR/dolthub/`: on dolt 2.6.1 even
  a `SELECT` rewrites a clone's files. It copies each clone to a private mirror in
  `$VOL_DATA_DIR/earnings-vol-study/cache/dolt_mirror/` and runs `dolt sql -r parquet` there, `SELECT` only, `AS OF` a
  pinned commit. It checks around every batch that the shared clone did not change.
- **DoltHub (CC BY-SA 4.0).** The earnings calendar, EPS history and option chains come from the DoltHub repositories
  `post-no-preference/earnings` and `post-no-preference/options`. Both declare *Attribution-ShareAlike 4.0
  International*. Attribution: "Contains data from the DoltHub repositories post-no-preference/earnings and
  post-no-preference/options, licensed under CC BY-SA 4.0. Changes: selected and filtered by this project."
- **CBOE, Yahoo and FRED.** CBOE single-stock volatility indices, the VIX (FRED's `VIXCLS` is a CBOE index) and
  Yahoo Finance prices (via `yfinance`) are downloaded to your own machine and used there; raw downloads are never
  committed. Every column computed from them carries a `_yf` or `_cboe` suffix. Until 2026-10-29 none of them left the
  machine; since the owner's decision of that day, values the app or the docs need may be committed (see the root
  [`DATA.md`](DATA.md) for each source's terms). Committed: the Yahoo-derived labels `timing_check.gap_verdict_yf`
  and `security.in_universe`, since milestone 3 aggregates of VIX-adjusted values (the market-adjusted rows of
  `results.parquet` and of the app's `tests.json`, `event_paths.json` and, since milestone 4, `drivers.json`), under
  Cboe's terms, and since milestone 4 the VIX tercile label `event_measures.vix_regime` (Cboe) and the regression
  coefficients of ln market cap (Yahoo). The VIX series and every
  per-event VIX-adjusted value stay local (ADR 0001 §7, data model §2.1).
- **Wikipedia (CC BY-SA 4.0) and SEC EDGAR.** Company names, GICS sectors and CIKs come from a pinned revision of
  Wikipedia's "List of S&P 500 companies". The before/after-market labels come from documents: company press releases
  (looked up by hand and recorded in `data/manual/press_release_checks.csv`) and, once the owner's contact string is
  set, SEC EDGAR 8-K filing times (US government public data). No EDGAR request has been made yet.
- **`data/derived/`** holds the committed part of each pipeline table (`security`, `ticker_alias`, `session`,
  `events`, `eps`, `session_snapshot`, since milestone 2 `iv_daily`, `event_iv` and `timing_check`, and since
  milestone 3 `event_window_obs`, `event_measures` and `results`); the writer
  drops every Yahoo or CBOE column first, except those a table names in `keep_restricted` (only
  `timing_check.gap_verdict_yf`, under the owner's decision of 2026-10-29; see the root `DATA.md`). They are licensed CC BY-SA
  4.0, not MIT. See [`data/derived/README.md`](data/derived/README.md). It also still holds
  `earnings_calendar_30_large_caps.json`, a DoltHub extract that `research/prototypes/spacing.py` reads.

Details and the JSON contract are in [`app/DATA.md`](app/DATA.md).

## Results

Milestone 4, 2026-10-29, **provisional timing labels**, adversarially reviewed and fixed (no delta review yet). Daily sample (day 0 from
2024-12-05). H1–H4: equal-weighted means of VIX-adjusted abnormal log IV (milestone 3). H5–H6: coefficients of the
crush regression, log points per standard deviation of the regressor; H7: the joint test that the options' implied
variance is unbiased for the realised squared move. **Gate G1 ran first and failed H5–H7**: their primary statistics
reject 9.55%, 8.10% and 16.15% at 5% under its calibrated null, above the 6.30% bar, so they are liberal and a
rejection by them would not be trusted. ADR 0005 declared G1's size designs for H1–H4 only, so H5–H7 stay in the
declared Holm family H1–H7 with their real p-values
([milestone 4 page](docs/milestones/04-drivers.md#6-measured-results), §6.2 and §9):

| | Question | n | Estimate | p | Holm p (H1–H7) |
|---|---|---:|---:|---:|---:|
| H1 | How much does the 30-day IV fall from day −1 to day 0? | 347 | −0.199 log points | 5.8e−23 | 4.1e−22 |
| H2 | Is IV abnormally high at day −1? | 356 | +0.232 log points | 0.0078 (randomisation floor, G = 8) | 0.047; with G = 7: 0.078 |
| H3 | Is IV back at its baseline at day +10? | 329 | +0.008 log points | 0.74 | 1 |
| H4 | Did ordinary volatility (σ_d) change? | 262 | +0.003 log points | 0.78 | 1 |
| H5 | Does a bigger earnings surprise change the crush? | 347 | +0.013 per sd (a smaller fall) | 0.010 (G1 size 9.55%: liberal) | 0.051 |
| H6 | Does the prior ordinary volatility level change it? | 347 | −0.001 per sd | 0.89 (G1 size 8.10%) | 1 |
| H7 | Is the implied variance unbiased for the realised one (a = 0, b = 1)? | 336 | b = 0.77 (CI 0.46–1.07) | 0.28 (G1 size 16.15%) | 1 |

The crush is the event variance leaving the 30-day horizon; ordinary volatility does not change measurably, and IV is
back at its baseline within ten sessions. H2's p sits on the enumeration floor 2/2^G, so its Holm verdict depends on
the number of season clusters (with the October 2026 tail merged into July, G = 7, it is 0.078: not rejected); its
direction is not in doubt (all 8 season means are positive). Over the family without H5–H7 (a descriptive
sensitivity, not binding) the Holm p would be H1 2.3e−22 and H2 0.023 (G = 7: 0.047). Among the drivers, the
term-structure slope at day −1 is the strongest (−0.032 per sd, exploratory, BH q 0.0006): a steeper slope, a larger
crush. That q, and every other driver p and q, comes from the same two-way t that G1 measured as liberal at this
design (9.55% and 8.10% for H5's and H6's coefficients); G1 never sized the slope's coefficient itself, so read them
as indications, not tests at 5%. The surprise effect does not survive other surprise measures or firm fixed effects.
Realised day-0 moves exceed the implied |move| 40.1% of the time against the 42.5% that fair pricing of a normal move
gives. The app draws the results, the
drivers' coefficients, the implied-against-realised scatter, the animated crush paths, a heatmap and the 3D terrain.

## Screenshots

Added at the final milestone.

## Read more

- [PR/FAQ](docs/prfaq.md): what the study will show and what could make it wrong.
- Decision records: [ADR 0001 architecture](docs/adr/0001-overall-architecture.md),
  [0002 day zero](docs/adr/0002-day-zero-convention.md), [0003 IV measures](docs/adr/0003-iv-measures.md),
  [0004 baseline and windows](docs/adr/0004-baseline-and-event-windows.md),
  [0005 statistical tests](docs/adr/0005-statistical-test-suite.md).
- Architecture: [diagrams](docs/architecture/README.md) and the [data model](docs/architecture/data-model.md).
- Prototypes: [`research/prototypes/`](research/prototypes/README.md), the throwaway scripts behind numbers in the ADRs.
  They are not part of the package and are not tested or reviewed.
- Learning: [LEARNING_LOG.md](LEARNING_LOG.md), the [milestone 0 page](docs/milestones/00-scaffold-and-design.md), the
  [milestone 1 page](docs/milestones/01-universe-and-events.md), the
  [milestone 2 page](docs/milestones/02-iv-measures.md), the [milestone 3 page](docs/milestones/03-event-study.md), the
  [milestone 4 page](docs/milestones/04-drivers.md) and the concept notes in
  [`docs/concepts/`](docs/concepts/).

## License

The code is MIT licensed (see [`LICENSE`](LICENSE)). The tables in `data/derived/` are licensed CC BY-SA 4.0 (see
[`data/derived/LICENSE`](data/derived/LICENSE)).
