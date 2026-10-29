# Earnings & Implied Volatility: an event study

An event study of how earnings announcements move options implied volatility. For each announcement by about 50 large
US companies, the project lines up the implied-volatility (IV) series in event time and measures the run-up before the
news, the fall ("IV crush") after it, and how long the fall lasts. It also compares the move the options priced with the
move the stock really made. A Python pipeline computes every number from open data and exports versioned JSON files. A
React app only checks and draws those files. Every design choice is written down in a short decision record.

**Not financial advice.** This is research for learning. It describes the past, ignores transaction costs and covers
large, liquid US stocks only.

**Status:** Milestone 2: IV measures (done, pending the owner's review). Milestone 1 chose the 50 companies, built
their 1,353 earnings announcements with the session each one reached the option market (day 0), the
before/after-market label and its status, and matched each announcement to its EPS period. Milestone 2 recomputes
implied volatility from the DoltHub bid/ask quotes (Black-76 on the put-call-parity forward): per company and session
the event-aware 30-day IV, the event variance and the implied move; per announcement the 30-day and front-expiry
crushes and the realised move. The primary sample holds 347 events; the app's Sample page draws the funnel, and its IV
measures page draws how the implied move and the crush are distributed. No statistical test has run yet, so there are
no results. **The timing labels are provisional**: 20 press releases were looked up and timed, and the rest keep the
calendar's labels until SEC EDGAR filing times can be read. EDGAR is accepted as the timing source (2026-10-28), but
its client runs only once the owner's contact string is set; until then the rule in force is the company's press
release, then the calendar label ([ADR 0002](docs/adr/0002-day-zero-convention.md)). The universe is today's 50 largest
S&P 500 members, so the sample has survivorship bias. The primary significance test is a t-test with two-way
cluster-robust standard errors: by announcement date and company for the crush, and by earnings season and company for
the run-up and persistence. Its size has been checked in simulations at the real design; the check on the real event
set (gate G1) comes at milestone 3. BMP and the Kolari-Pynnönen family are reported as robustness
([ADR 0005](docs/adr/0005-statistical-test-suite.md)).

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
│   ├── panel/                  the clean baseline (the rest arrives at milestone 3)
│   └── export/                 the sample funnel and the IV-measures view
├── tools/
│   ├── export_app_data.py      writes app/public/data/meta.json, sample_funnel.json and iv_measures.json
│   ├── build_notebooks.py      generates the notebooks from src/
│   ├── diagrams/               vendored local diagram toolkit (build.py + diagram_kit/); also public at github.com/rajib2k5/vol-diagram-kit
│   └── blender/                3D hero-render script
├── tests/                      pytest tests for src/ and tools/
├── notebooks/                  generated notebooks (never edited by hand)
│   ├── 00_scaffold_tour.ipynb
│   ├── 01_events.ipynb
│   └── 02_iv_measures.ipynb
├── data/derived/               small derived tables, CC BY-SA 4.0
│   ├── README.md               what is here, and the licence terms
│   ├── LICENSE                 CC BY-SA 4.0 notice
│   ├── security, ticker_alias, session, events, eps, session_snapshot   .parquet, written by the pipeline
│   └── earnings_calendar_30_large_caps.json   DoltHub extract, input to research/prototypes/spacing.py
├── data/manual/
│   └── press_release_checks.csv   the hand-kept record of press-release timing look-ups (read by the events layer)
├── research/prototypes/        throwaway scripts behind numbers quoted in the ADRs (not tested, not reviewed)
│   ├── README.md               which script backs which claim, and their limits
│   ├── spacing.py, worked.py   event spacing (ADR 0004), the AAPL worked example (ADR 0003)
│   ├── leak_grid.py            the event-variance leak of blind 30-day interpolation (ADR 0003)
│   ├── kp_sim.py, kp_partial.py, kp_partial_clamp.py   size of the KP tests, one-session measure (ADR 0005)
│   ├── h2h3_size_sim.py, h2h3_followup_sim.py   size and power at the real daily design (ADR 0005)
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
│   │   └── 01-sessions-and-day-zero.md … 05-survivorship-bias.md
│   ├── milestones/             one learning page per milestone
│   │   ├── 00-scaffold-and-design.md
│   │   └── 01-universe-and-events.md
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
  [`DATA.md`](DATA.md) for each source's terms). At milestone 2 the only such column is
  `timing_check.gap_verdict_yf` (ADR 0001 §7, data model §2.1).
- **Wikipedia (CC BY-SA 4.0) and SEC EDGAR.** Company names, GICS sectors and CIKs come from a pinned revision of
  Wikipedia's "List of S&P 500 companies". The before/after-market labels come from documents: company press releases
  (looked up by hand and recorded in `data/manual/press_release_checks.csv`) and, once the owner's contact string is
  set, SEC EDGAR 8-K filing times (US government public data). No EDGAR request has been made yet.
- **`data/derived/`** holds the committed part of each pipeline table (`security`, `ticker_alias`, `session`,
  `events`, `eps`, `session_snapshot`, and since milestone 2 `iv_daily`, `event_iv` and `timing_check`); the writer
  drops every Yahoo or CBOE column first, except those a table names in `keep_restricted` (only
  `timing_check.gap_verdict_yf`, under the owner's decision of 2026-10-29; see the root `DATA.md`). They are licensed CC BY-SA
  4.0, not MIT. See [`data/derived/README.md`](data/derived/README.md). It also still holds
  `earnings_calendar_30_large_caps.json`, a DoltHub extract that `research/prototypes/spacing.py` reads.

Details and the JSON contract are in [`app/DATA.md`](app/DATA.md).

## Results

No test results yet. Measured numbers appear here from milestone 3, each re-measured by an independent verifier.
Milestones 1 and 2 measured the sample and the IV measures: the primary sample holds **347 events** (app's Sample
page; [milestone 2 page](docs/milestones/02-iv-measures.md#61-the-sample-funnel-primary-daily)), and the app's IV
measures page draws how the implied move and the 30-day crush are distributed over them.

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
  [milestone 2 page](docs/milestones/02-iv-measures.md) and the concept notes in
  [`docs/concepts/`](docs/concepts/).

## License

The code is MIT licensed (see [`LICENSE`](LICENSE)). The tables in `data/derived/` are licensed CC BY-SA 4.0 (see
[`data/derived/LICENSE`](data/derived/LICENSE)).
