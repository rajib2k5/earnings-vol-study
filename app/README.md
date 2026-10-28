# Earnings & Implied Volatility (web app)

An event study of how earnings announcements move options implied volatility: the run-up, the
crush and what drives them. Python computes everything; this React app only validates and
visualises the JSON files in `public/data/`. Not financial advice.

Status: **milestone 0**, the app shell. Pages: About, Architecture, 3D preview (an illustrative
synthetic surface, labelled as such), plus a local Metrics page. No real results are shown yet.

## Run

```bash
npm ci
npm run dev        # local dev server
npm run verify     # lint + tests + coverage thresholds + production build
```

The built app (`dist/`) uses relative URLs (`base: './'`), so it can be served from any sub-path.

## Data

The app fetches `data/meta.json` on start-up and shows the schema version, milestone and Python
source commit in the footer. The envelope format and the data licences are in [DATA.md](DATA.md).
The files in `public/data/` are written by `tools/export_app_data.py` on the Python side; do not
edit them by hand.

## Tests

- `src/lib/*.test.ts(x)`: unit tests for the pure helpers (JSON contract validator, 3D mesh builder,
  seeded RNG, architecture data) and the small components, with hand-worked or independently
  computed expected values.
- `src/App.test.tsx`: integration test of the whole shell with a fake `fetch` and a stand-in 3D canvas.
- `src/three/*.test.tsx`: the 3D view with the r3f `Canvas` replaced (jsdom has no WebGL).
- Coverage thresholds are enforced on `src/lib/**` (lines and functions 85%, branches 75%).

## Tooling note

Dependencies are pinned exactly. `package-lock.json` was generated with npm 11.21.1, because
npm 10.9.8 crashed while resolving vitest 4.1 from scratch. `npm ci` works with both.
