# Earnings & Implied Volatility (web app)

An event study of how earnings announcements move options implied volatility: the run-up, the
crush and what drives them. Python computes everything; this React app only validates and
visualises the JSON files in `public/data/`. Not financial advice.

Status: **milestone 4**. Pages: About, Sample (how many earnings events survive each sample rule, from
`data/sample_funnel.json`), IV measures (`data/iv_measures.json`), Results (`data/tests.json`: the primary family, robustness
and exploratory rows, the G1 gate and the Holm statement), Crush paths (`data/event_paths.json`: the mean path with its band
and the animated per-event paths), Drivers (`data/drivers.json`: gate G1 for H5 to H7, the Holm statement over the declared family with
its post-gate sensitivity, the power table, and for each regression model a coefficient plot and a table of its rows), Implied vs realised
(`data/implied_vs_realised.json`: a scatter of the expected against the realised absolute move, and the summary of the comparison and of
H7's joint test), Heatmap (`data/heatmap.json`), Architecture and the 3D view (`data/terrain.json`: each
company's mean abnormal log IV by event day), plus a local Metrics page. **The timing labels are provisional**: every page
that shows a result says so, with the look-up count and the caveats of its file, until the timing look-ups are complete.

## Run

```bash
npm ci
npm run dev        # local dev server
npm run verify     # lint + tests + coverage thresholds + production build
```

The built app (`dist/`) uses relative URLs (`base: './'`), so it can be served from any sub-path.

## Data

The app fetches `data/meta.json` on start-up and shows the schema version, milestone and Python
source commit in the footer; each page fetches its own file when it is opened. All nine files are written at
schema 0.5.0. The envelope format, the keys of each file and the data licences are in [DATA.md](DATA.md).
The files in `public/data/` are written by `tools/export_app_data.py` on the Python side, from the
committed tables in `data/derived/` and `params.yaml` only (run `uv run python tools/export_app_data.py`
from the repository root after a change there); do not edit them by hand.

## Tests

- `src/lib/*.test.ts(x)`: unit tests for the pure helpers (JSON contract validator, the parsers of the nine data kinds,
  chart frame and colour logic, 3D mesh builder, seeded RNG, architecture data) and the small components (the data
  pages), with hand-worked or independently computed expected values.
- `src/test/publicData.test.ts`: checks the REAL files in `public/data/` against the parsers (kinds, cross-file counts,
  the Cboe and Yahoo flags in `meta.json`).
- `src/App.test.tsx`: integration test of the whole shell with a fake `fetch` and a stand-in 3D canvas.
- `src/three/*.test.tsx`: the 3D view with the r3f `Canvas` replaced (jsdom has no WebGL).
- Coverage thresholds are enforced on `src/lib/**` (lines and functions 85%, branches 75%).

## Tooling note

Dependencies are pinned exactly. `package-lock.json` was generated with npm 11.21.1, because
npm 10.9.8 crashed while resolving vitest 4.1 from scratch. `npm ci` works with both.
