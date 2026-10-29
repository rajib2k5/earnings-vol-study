# Earnings & Implied Volatility — app guide

An event study of how earnings announcements move options implied volatility: the run-up, the
crush and what drives them. Python computes every number; this app only validates and draws the
JSON that Python exports to `public/data/`. React 19 + TypeScript + Vite.

## Commands

```bash
npm ci             # install exactly what package-lock.json says
npm run dev        # local dev server
npm run verify     # lint + tests + coverage thresholds + production build: the gate
npm run coverage   # tests with the coverage table
```

## Invariants

- **The app never computes results.** Numbers come from the Python exporter. The app validates the
  envelope (`src/lib/contract.ts`) and draws. UI-only transforms (grid to mesh, formatting, layout)
  are fine; statistics are not.
- **`src/lib/` stays small and pure.** Transforms (`contract`, `validate`, `dataParts`, `provenance`, `terrain`,
  `pathFrames`, `heatColour`, `format`, `motion`, `rng`, `architecture`) take data and return data: no I/O, no clock, no
  `Math.random()`. The parsers and loaders (`meta`, `funnel`, `ivMeasures`, `results` for tests.json, `eventPaths`,
  `terrainData`, `heatmap`) fetch only through an injected `fetch`. React components in `src/lib/` (`FunnelPage`,
  `IvMeasuresPage`, `ResultsPage`, `CrushPathsPage`, `HeatmapPage`, `ProvisionalNotice`, the shell) are thin and tested in
  jsdom; the animation timer in `CrushPathsPage` only calls the pure `stepPlayback`. WebGL code lives in `src/three/`,
  outside the coverage gate because it needs a GPU; keep it as thin as possible and put every calculation in `src/lib/`.
- **Seeded randomness only**, via `mulberry32` in `src/lib/rng.ts`, in code and in tests.
- **Coverage thresholds (85% lines/functions, 75% branches on `src/lib/**`) are set in
  `vite.config.ts` and are never weakened.** Tests are never deleted or `.skip`ped to go green; a test
  goes only together with the code it tests.
- **Anything illustrative says so on screen** ("Illustrative synthetic shape — not data"). Since milestone 3 nothing is
  illustrative: the 3D view draws `terrain.json`. **Every page that shows a result says the timing labels are provisional**
  (`ProvisionalNotice`, built from the file's `lookups` and `caveats`) while the look-ups are incomplete.
- **The JSON contract is shared with Python.** Envelope keys are exactly `schema_version` ("0.4.0"),
  `kind`, `generated_at` (UTC, ends in `Z`), `source_commit`, `data`. Change `contract.ts` and
  `tools/export_app_data.py` together, and bump the version.
- **Dependencies are pinned exactly** (no `^` or `~`). The lockfile was generated with npm 11
  because npm 10.9.8 crashed resolving vitest 4.1; `npm ci` works on both.
- **Public repo hygiene**: no API keys, no Cboe VX\* data, no VIX series and no per-event VIX-adjusted value (only
  aggregates of VIX-adjusted values are committed, `DATA.md`), no Yahoo prices (only the two derived labels, `DATA.md`), no
  absolute local paths in `dist/`.

## Layout

- `src/lib/` pure helpers and thin components (shell, About, diagrams, footer) with tests beside them
- `src/three/` r3f 3D view (`ThreeDPreview` loads and checks `terrain.json`, `EventTerrain3D` is lazy-loaded)
- `src/test/` shared test fixtures (one per data kind, invented values), `editHelpers.ts`, and `publicData.test.ts`, which
  checks the REAL files in `public/data/`
- `public/data/` JSON written by Python (never edited by hand here): `meta`, `sample_funnel`, `iv_measures`, `tests`,
  `event_paths`, `terrain`, `heatmap`; their keys are in `DATA.md`

## Tests

Oracles are hand-worked in a comment or come from an independent implementation (the `rng` test
values were computed with a separate Python implementation of mulberry32). Boundary cases are expected: empty, single,
NaN/non-finite, wrong type. Every fixed bug leaves a regression test behind.
