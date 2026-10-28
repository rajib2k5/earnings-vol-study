# M0 adversarial ledger: code, app, repo hygiene, learning docs

*Edited for publication: repository names were replaced by descriptions.*

Date: 2026-10-28. Reviewer: adversarial (Opus). Scope: claims 1-14 of the M0 code/app/hygiene/docs
review. The ADRs and the literature are out of scope; a separate methodology reviewer covers them.

**Default verdict for every claim: broken.** A claim survives only on evidence produced here.

**Method.** The protocol is evidence-gated validation. Tier 2 (official docs or registry as channel A, a runtime probe run here as channel B) covers library/API behaviour, versions and numerics. Tier 1 (a runtime probe plus a falsifier) covers the rest.

**Mode.** Single-context sequential fallback. Claims 10-12 and the browser half of 4.4 ran in a forked
sub-context. Before the probes ran, the claims and their probe designs were pre-registered in a scratch file.
Results are therefore "dual-confirmed (fallback mode)", not independently confirmed.

**Isolation.** Every mutation, `npm ci`, `npm run verify` and exporter run used a scratch copy of the repo outside
`~/dev`. Afterwards the repo files, the scratch sources and the vendored local diagram toolkit were checked by sha256 or
`git status`: nothing in place changed. Nothing was committed.

## Environment pin

| Item | Version |
|---|---|
| Machine | Linux aarch64 |
| Python | CPython 3.12.13 (`.venv`, fresh `uv sync --frozen` venv) |
| uv | 0.11.25 |
| Node / npm | v22.23.1 / 10.9.8 |
| git | 2.43.0 |
| Browser (fork) | Chromium 152.0.7977.167, arm64 |
| Mermaid render (fork) | mermaid-cli 11.4.2, mermaid 11.17.2 |
| Diagram toolkit | vendored local diagram toolkit, HEAD 56aad83 |
| Locked Python packages | matplotlib 3.11.2, nbformat 5.11.1, numpy 2.5.4, pandas 3.1.0, pyarrow 26.0.0, pyyaml 6.0.3, requests 2.34.2, scipy 1.18.1, statsmodels 0.15.0, yfinance 1.7.0, pytest 9.2.0 |

## Verdict table

Severity applies to REFUTED rows only. For a SURVIVES row the column carries the severity of any attached note,
or "-".

| # | Claim | Channel A (docs / registry) | Channel B (probe → output) | Verdict | Sev |
|---|---|---|---|---|---|
| 1.1 | `uv run pytest -q` prints 40 passed | n/a (count) | Ran `uv run pytest -q` → `40 passed in 0.22s`, rc 0. Counts per file 11/15/7/7. | SURVIVES | - |
| 1.2a | Every test file has a test that fails when its code is broken | n/a | `probes/m0-code/mutate_py.py`: 33 mutants on a scratch copy. Every test file killed at least one. | SURVIVES | - |
| 1.2b | At least 3 killed mutants per module: config, contract, build_notebooks | n/a | config 7/7 killed. contract 9/9. build_notebooks 7/7, plus 2 extra re-measured below. | SURVIVES | - |
| 1.2c | Same, for `tools/export_app_data.py` | n/a | 6/10 killed. **4 survive with 40 passed**: (exp-6) drop `--short` and the full 40-char hash passes the `{7,40}` regex; (exp-7) wrong `DEFAULT_OUT` path; (exp-8) DoltHub licence becomes "CC BY 4.0"; (exp-9) the earnings URL points at the options repo. | **REFUTED** | major |
| 1.3 | No test asserts on a helper that reimplements the code under test | n/a | Read all 4 files. `make()` (test_contract.py:15-18) and `load_tool` (conftest.py:9-22) call the real code. No reimplementation found. | SURVIVES | - |
| 1.4 | No test greps source text | n/a | Grep of `tests/` for `read_text` / `open(` / `getsource`. `test_notebooks_sync.py:93` checks that the third code cell prints `inspect.getsource(...)` and starts `def envelope(`. That asserts on the notebook's output, which is source by design. No test reads `src/` or `tools/` to judge behaviour. | SURVIVES | - |
| 2.1a | Dependencies use exact `==` pins and Python `>=3.12,<3.13` | n/a | tomllib parse: 11/11 dependencies `==`. `requires-python = ">=3.12,<3.13"`; uv.lock has `==3.12.*`. | SURVIVES | - |
| 2.1b | The whole build is pinned | n/a | `pyproject.toml:20` reads `requires = ["hatchling"]`, unpinned, and hatchling is not in uv.lock. | **REFUTED** | minor |
| 2.2 | `uv lock --check` passes | n/a | Scratch copy: `uv lock --check` → `Resolved 56 packages`, rc 0. With `--offline` also rc 0. | SURVIVES | - |
| 2.3 | Every pin exists on PyPI and installs on aarch64 / py3.12 | `probes/m0-code/pypi_pins.py` (PyPI JSON API): all 11 found, none yanked, each with a usable wheel. pytest 9.2.0 was uploaded 2026-10-27T21:30Z, under 24 h before it was pinned. | Fresh venv: `uv sync --frozen` rc 0, then all 11 imports print the pinned versions on `aarch64 3.12.13`. | SURVIVES | - |
| 3.1 | Notebook output is byte-identical across processes | nbformat ids are random by default (fork: docs + 2 builds differ). That is why fixed ids are needed. | `probes/m0-code/nb_determinism.sh` part 1: 6 processes (PYTHONHASHSEED 0/1/42/12345/random/7, different cwd/HOME/LANG/TZ) all give `8716be19…`, equal to the file on disk. | SURVIVES | - |
| 3.2 | `--check` exits non-zero on any drift | Python docs: `read_text` opens with universal newlines (`\r\n` → `\n`) (fork) | Same probe, part 2. These drifts give rc 1: trailing space, BOM, missing final newline, deleted file. These give **rc 0 although the bytes differ**: CRLF line endings (sha b45408…, 2636 B) and CR-only endings. Cause: `build_notebooks.py:109` compares `read_text()` output, not bytes. | **REFUTED** | minor |
| 3.3a | The notebook's code cells run | n/a | A fresh process ran the 3 code cells from the `.ipynb` on disk: all ran. Mutant nbk-4 (broken cell) is killed by `test_notebook_code_cells_run`. | SURVIVES | - |
| 3.3b | The notebook runs as a notebook, as it says | n/a | Notebook cell 1 (`notebooks/00_scaffold_tour.ipynb:10`, from `tools/build_notebooks.py:49`) says "Run it with `uv run jupyter lab`". The command fails with "Jupyter command `jupyter-lab` not found.", rc 1. `import ipykernel` raises ModuleNotFoundError. Only `jupyter-core` is installed. | **REFUTED** | major |
| 4.1 | The envelope has exactly 5 keys | n/a | `probes/m0-code/contract_py_probe.py` → `['data','generated_at','kind','schema_version','source_commit']`. Mutant con-1 killed by 4 tests. | SURVIVES | - |
| 4.2 | `generated_at` is UTC with `Z`; naive datetimes are rejected | Python docs: `astimezone` (fork) | All of these produce `…Z` with the correct UTC instant: +02:00, +05:45, +00:00:30, NY fold 0 and 1 (05:30Z / 06:30Z), .999999 µs. Naive input and a tzinfo returning None both raise ValueError. Edge case: year 999 gives `999-01-01T00:00:00Z` (not 4 digits), which `contract.ts` rejects. The exporter cannot reach it. | SURVIVES | minor note |
| 4.3 | `dumps` rejects NaN and ±inf | Python 3.12 json docs: "If `False`, serialization of out-of-range float values (nan, inf, -inf) will result in a ValueError, in strict compliance with the JSON specification." | float nan/inf/-inf, np.float64 nan, nan inside a tuple, nan/inf as a **dict key** → ValueError. np.float32 and Decimal NaN → TypeError. Mutant con-4 killed by 4 tests. | SURVIVES | - |
| 4.4 | Python's default writes a bare `NaN`, and the browser's `JSON.parse` throws SyntaxError | Python docs: "If True (the default), their JavaScript equivalents (NaN, Infinity, -Infinity) are used." RFC 8259 §6: "Infinity and NaN … are not permitted." MDN JSON.parse: SyntaxError if not valid JSON. | Python `json.dumps(float('nan'))` → `'NaN'`. Node 22 `JSON.parse('NaN')` → `SyntaxError: "NaN" is not valid JSON`. Chromium 152 pane (fork): the same message, plus `Unexpected token 'N'` for `{"x": NaN}`. | SURVIVES | - |
| 5.1a | `contract.ts` rejects every listed deviation | n/a | `probes/m0-code/contract_ts_probe.mjs` (node strip-types on the real `contract.ts`). Wrong version, numeric version, missing key, extra key, `__proto__` key, `+00:00`, no zone, lower-case z, array/null/string data, numeric kind and null commit are all rejected with a named rule. Bare `NaN` / `Infinity` make `JSON.parse` throw SyntaxError before the validator runs. 6 `contract.ts` mutants killed. | SURVIVES | - |
| 5.1b | `contract.ts` accepts exactly what `contract.py` emits | n/a | Every well-typed envelope from `contract.py` is accepted, including the real `meta.json`. **Not an equivalence:** (i) `contract.py` does not check its own types. With data as a list or None, kind=5 or source_commit=None it writes the file and the browser rejects it. That contradicts the "fail at export, not in the browser" rationale in `contract.py:50-53`. (ii) `{"x": 10**400}` passes `dumps` and arrives in the app as `data.x=Infinity`, and `2**64` arrives as `18446744073709552000`; `parseEnvelope` accepts both. | **REFUTED** | minor |
| 5.2 | `publicData.test.ts` validates the real `app/public/data/meta.json` | n/a | `probes/m0-code/public_data_probe.sh` (scratch copy). The test fails for: version 0.2.0, an extra key, `+00:00`, milestone `"0"`, a bare NaN, a deleted file. **But** the full app suite (168) still passes when `data.data_sources` has a wrong licence or is emptied, because nothing reads it. See N1. | SURVIVES | - |
| 5.3 | `meta.ts` treats milestone as an integer and shows errors | n/a | met-1 (fractional), met-2 (negative), met-6 (string coerced) are killed. met-4 (ignore HTTP status) is killed by MetaFooter/App tests, and the footer renders `role="alert"`. An invalid milestone shows as "unknown" in a status line, not as an error, by design (`meta.ts:36-38`). | SURVIVES | - |
| 6.1 | `npm ci && npm run verify` is green | n/a | Scratch copy, npm 10.9.8: `npm ci` → added 319 packages, rc 0. `npm run verify` → lint clean, `Test Files 24 passed (24)`, `Tests 168 passed (168)`, Stmts 97.51 / Branch 93.03 / Funcs 96.37 / Lines 99, build ok, rc 0. | SURVIVES | - |
| 6.2 | Coverage thresholds are 85/85/75 on `src/lib/**`, enforced and not weakened | Vitest 4 migration guide: "If `coverage.include` is not defined, coverage report will include only files that were loaded during test run", so with `include` set, unloaded files count. | `vite.config.ts:16` reads `lines: 85, functions: 85, branches: 75`. `probes/m0-code/coverage_gate_probe.sh`: an untested 80-function file in `src/lib/` gives rc 1 with "Coverage for lines (82.6%) does not meet global threshold (85%)". The same file in `src/three/` gives rc 0, which is excluded as documented. No git history exists to compare against, so "not weakened" can only be checked against `app/CLAUDE.md`, and it matches. | SURVIVES | - |
| 6.3 | Every dependency in `package.json` is pinned exactly | n/a | Regex `^\d+\.\d+\.\d+$` matches 22 of 22. | SURVIVES | - |
| 6.4 | `npm ci` works on npm 10.9.8 | npm docs: lockfileVersion 3 is "used by npm v9 and above. Backwards compatible to npm v7." | `npm ci` rc 0 on npm 10.9.8. Also reproduced: `npm install --package-lock-only` on npm 10.9.8 crashes with `Cannot read properties of null (reading 'edgesOut')`, so any dependency change needs npm 11. There is no `engines` / `packageManager` field to say so. | SURVIVES | minor note |
| 7.1 | fiber / drei / three / react pins satisfy each other's peerDependencies | `npm view`: fiber 9.8.2 needs react `>=19 <19.4` and three `>=0.156`. drei 10.7.9 needs react `^19`, three `>=0.159`, fiber `^9.0.0`. react-dom 19.3.1 needs react `^19.3.1`. | `semver.satisfies` true for all 6. `npm ls --all` rc 0; the only UNMET entries are optional peers (expo, react-native, …). Note: `stats-gl@2.4.2` (through drei) installs a second `three@0.170.0`. The bundle contains only REVISION "186". | SURVIVES | - |
| 7.2 | The `THREE.Clock` deprecation warning is harmless | three `src/core/Clock.js`: "@deprecated since r183." r3f 9.8.2 `events-*.esm.js:1207`: `clock: new THREE.Clock()`. | Node: `new THREE.Clock()` warns "This module has been deprecated. Please use THREE.Timer instead." and keeps working: `getDelta` 0.0500 after a 50 ms wait, stop/start/elapsedTime fine. Harmless while three stays pinned; a future three release may remove it. | SURVIVES | minor note |
| 8.1 | App tests fail when contract / terrain / meta / rng are broken | n/a | `probes/m0-code/mutate_app.mjs`: 27 mutants, 26 killed. contract 6/6, terrain 7/7, meta 6/6, rng 4/5, 3D 3/3. **Survivor rng-2**: `seed >>> 0` → `seed`. The test "treats the seed as an unsigned 32-bit integer" (`rng.test.ts:35-37`) cannot fail for integer seeds, because the `>>> 0` after the add normalises anyway. | SURVIVES | minor note |
| 8.2 | The `rng.ts` mulberry32 oracle values come from an independent implementation | C reference (gist tommyettinger): `z = (x += 0x6D2B79F5UL); z = (z ^ (z >> 15)) * (z \| 1UL); z ^= z + (z ^ (z >> 7)) * (z \| 61UL); return z ^ (z >> 14);` | `probes/m0-code/mulberry32_oracle.py`, a uint32-masked Python port of the C reference: seeds 0 and 42 give all 6 pinned values exactly. Falsifier: shift 15→16 gives MISMATCH. How the values were first generated cannot be checked; that they match an independent implementation is now shown. | SURVIVES | - |
| 8.3 | The 3D view respects `prefers-reduced-motion` | n/a | `EventTerrain3D.tsx:47` reads it through `controlsConfig(prefersReducedMotion())`. Mutant 3d-1 (`controlsConfig(false)`) is killed by 2 tests. Limit: the setting is read once at mount (`useState` initialiser), so changing the OS setting while the 3D page is open has no effect until it remounts. | SURVIVES | minor note |
| 8.4 | The label reads exactly "Illustrative synthetic shape — not data" | n/a | `illustrative.ts:9` codepoints: one non-ASCII character, U+2014. The built bundle contains the exact string once. Mutants 3d-2 (hyphen) and 3d-3 (not rendered) are killed. | SURVIVES | - |
| 9a | No secrets, API keys or tokens in the committable files | n/a | Grep of all 147 `git ls-files --others --exclude-standard` files for api key / secret / password / `sk-` / `ghp_` / `AKIA` / private-key headers: no hits beyond prose and identifiers. | SURVIVES | - |
| 9b | No absolute local paths or personal email | n/a | `docs/milestones/00-scaffold-and-design.md:59` contains the author's absolute home-directory path to `notebooks/…`. Emails found: only `t@example.com` (test). `LICENSE:3` carries the author's name, which is intended. | **REFUTED** | minor |
| 9c | No private repo names or references to the quant-hub suite | n/a | `quant-hub`: 0 hits. But the repo names things that are not in it. The diagram toolkit (`docs/architecture/README.md:4`) is a vendored local toolkit with no git remote; it is deliberately not on GitHub, and the README now says so. A sibling repository (`docs/prfaq.md:126`) did not resolve on GitHub (`gh repo view`: "Could not resolve") when this review ran; the delta ledger (claim 9) found it public later. Also unexplained private context: "the shared-data hub" (`config.py:20,85`, milestone :171) and "the owner's global CLAUDE.md" (`specs/process.yaml:2`). | **REFUTED** | minor |
| 9d | No CBOE or Yahoo data | n/a | The only committed data are the DoltHub calendar JSON, `meta.json`, the simulation `.out.txt` files and DoltHub option quotes in `worked.py`. No price or index tables (date,price CSV grep: 0 hits); no binary files. | SURVIVES | - |
| 9e | `.gitignore` covers the required paths, and `app/dist` holds no home-directory path | n/a | `git check-ignore -v` matches `data/raw/`, `data/cache/`, `.env`, `.env.*`, `.venv/`, `node_modules/`, `app/node_modules`, `graphify-out/`, `app/dist`, `app/coverage`, `*.tsbuildinfo`. `app/dist` and a scratch build made under a temp-directory path: 0 home-directory or temp-directory path strings (the build does not depend on the path). | SURVIVES | - |
| 9f | DoltHub data and quotes carry attribution | n/a | Present: `data/derived/README.md` and `data/derived/LICENSE` (CC BY-SA 4.0), `research/prototypes/README.md:29-32`, and the About-page `ATTRIBUTION`. **Inaccurate:** `data/derived/README.md:24` says "aggregated" and `studyContent.ts:80` says "summarised", but the file is 336 raw SELECT rows. The README says "the commit ref [is] inside the file", but it is `"commit_ref":"master"`, a moving branch, so the extract cannot be reproduced. `worked.py` has no in-file notice and sits under the root MIT licence. `prototypes/README.md:30` calls them "mid quotes", but they are bid/ask. | SURVIVES (present), with defects | minor |
| 10a | Every `file:line` link resolves to the line it describes (at least 25 sampled) | n/a | Fork, `probes/m0-code/docs/link_resolver.py`: 226/226 relative links resolve and 164/164 `#L` anchors are in range. Every link text was read against its target: 0 mismatches. Falsifier: lines shifted by +900 give rc 1. | SURVIVES | - |
| 10b | Every number in the doc was measured | n/a | Fork re-measured pytest 40 (11/15/7/7), vitest 24/168, coverage 97.51/93.03/96.37/99, chunk sizes 249.07 kB / 944.27 kB with identical hashes, 504 vertices / 920 triangles. I re-ran all 5 mutation counts in §2.5 on a scratch copy: 3/37, 4/36, 2/38 (`return path.exists()`), 5/35, 1/39. All match. Timings differ as expected (0.21 s vs 0.18 s). | SURVIVES | - |
| 10c | The doc's explanations of the code are technically correct | Python docs: "`%f` Microsecond as a decimal number, zero-padded to 6 digits"; universal newlines | `:196` "`strftime` has no fraction field" is false: `%f` prints `.123456`, and microseconds are dropped only because the format omits `%f`. `:284` "byte for byte" is false: the CRLF probe in 3.2 passes. `:280` "The first cell prints the package version": cell 1 is markdown that only stamps the text. | **REFUTED** | minor |
| 10d | The doc presents no study results as measured | n/a | Fork: no event-study result is presented as measured. Framing nit: `:7-10` says every other number is an ADR design fact, but §2.7 build sizes and the KP simulation rates are prototype outputs. | SURVIVES | - |
| 11a | Commands in README / LEARNING_LOG / arch README work as written | n/a | Fork, scratch copy: `uv sync` rc 0 (lock unchanged); `uv run pytest -q` 40 passed; `build_notebooks.py --check` OK; `export_app_data.py` rc 0 and its output passes `publicData.test.ts`; `npx vite` serves 200. I ran `npm ci && npm run verify` (6.1). | SURVIVES | - |
| 11b | Relative links resolve | n/a | Fork: 63/63, anchors included. | SURVIVES | - |
| 11c | The repo-layout tree matches reality | n/a | Fork: every path listed exists. Omitted: `src/earnings_vol/__init__.py`, and now `docs/validation/` and `docs/architecture/graph/`. | SURVIVES | minor note |
| 11d | The embedded Mermaid is valid | mermaid parse/render | Fork: 10/10 diagrams render with rc 0 in mermaid-cli 11.4.2 (mermaid 11.17.2, headless Chrome). The architecture README blocks are byte-equal to `architecture.mmd` / `erd.mmd`. 2 broken falsifiers give rc 1. The built-in pane could not open local files, so the CLI path was used. | SURVIVES | - |
| 12a | `prfaq.md` has no unmeasured result numbers | n/a | Fork: results are ⟨x⟩ / ⟨y⟩ / ⟨p⟩ / ⟨n⟩ placeholders; 330-360 is labelled as an estimate. | SURVIVES | - |
| 12b | Each design fact in it names its source | n/a | Fork: `:73` (October 2026), `:75` (weekly, then Mon/Wed/Fri) and `:77` (AAPL, AMZN, GOOG, GS, IBM; calendar from 2020) name no source; they are correct against `data-model.md`. `:115` rounds ADR 0003's 0.26-1.1 to "0.3-1". | **REFUTED** | minor |
| 12c | No sentence presents a plan as a result | n/a | Fork: SURVIVES inside the working-backwards frame. But `:128` "No raw third-party data (DoltHub extracts, CBOE, Yahoo) committed" is false: `data/derived/earnings_calendar_30_large_caps.json` is a raw DoltHub extract, and `README.md:50,113` calls it exactly that. | SURVIVES (12c); `:128` see N4 | - |
| 13a | `docs/architecture/specs/*.yaml` validate with the vendored local diagram toolkit | Kit `SCHEMA.md` (kinds flow / erd / sequence) | Kit copied to scratch and run read-only with the kit's own venv (`PYTHONDONTWRITEBYTECODE=1`): `build.py specs --out <scratch>` gives "built 5 spec(s)", rc 0. Falsifier: a `kind: nonsense` spec gives rc 2 with "'nonsense' is not one of flow, erd, sequence". Kit `git status` afterwards: clean. | SURVIVES | - |
| 13b | Each `.mmd` equals the kit's output | n/a | `cmp`: all 5 files (architecture, data_flow, erd, event_sequence, process) IDENTICAL. Falsifier: renaming lane label Learner → "Learner X" makes `process.mmd` differ. | SURVIVES | - |
| 14 | `app/src` computes no statistic or result, only UI transforms | `app/CLAUDE.md`: "UI-only transforms (grid to mesh, formatting, layout) are fine; statistics are not." | `charts.tsx:17-30` `binValues` computes a histogram, i.e. per-bin frequency counts of raw values, which is a statistic. It is dead code (no production import) and is tested and counted in the coverage gate. `studyContent.ts:15` tells users "nothing on screen is calculated in the browser", but the 3D surface is generated in the browser (`illustrative.ts`, labelled illustrative) and the Metrics page sums event counts (`shell.tsx:134`). Related drift: see N1. | **REFUTED** | minor |

## New problems (not in the claim list)

The first problem is a design drift; the rest follow.

**N1 (major). `meta.json`'s `data.data_sources` is dead data, and the app keeps its own copy.**
- `app/src/lib/studyContent.ts:46-77` hard-codes the source and licence table that the About page shows.
- `tools/export_app_data.py:28-53` writes a second copy into `meta.json`, which no app code reads.
- `public_data_probe.sh` showed:
  - a wrong licence in `meta.json` passes all 168 app tests;
  - so does an emptied `data_sources` list;
  - a wrong licence in `export_app_data.py` passes all 40 Python tests (exp-8, exp-9).
- So the CC BY-SA attribution, a legal obligation, has two sources of truth. Neither side checks the other.
- This breaks the invariant "Python owns the content and the app draws the JSON".
- Fix: render the data-sources table from `meta.json`, or add one test that asserts `studyContent.DATA_SOURCES` equals `meta.json` `data.data_sources`.

**N2 (major). The notebook cannot be opened as a notebook in the locked environment.**
- See 3.3b. The learner-facing instruction fails on its first command.

**N3 (minor). `contract.py` does not enforce its own contract.**
- `envelope()` accepts any `kind`, `data` and `source_commit` types.
- `dumps()` allows integers beyond 2^53 (precision lost) and beyond about 1.8e308 (which become `Infinity` in the browser).
- That is the same browser-side failure class that `allow_nan=False` was added to prevent.

**N4 (major). `docs/prfaq.md:128` makes a false licensing statement.**
- It says no DoltHub extracts are committed, but one is.
- This is a public-facing licence statement.
- Fix: "No CBOE or Yahoo data. DoltHub data only as small CC BY-SA extracts in `data/derived/`, with attribution."

**N5 (minor). The ERD draws fields that `meta.json` does not have.**
- `docs/architecture/erd.mmd:274` and `specs/erd.yaml:299` draw `object provenance` and `from_events FK` on `meta.json` as existing fields.
- `export_app_data.py:72-78` emits only `project`, `milestone`, `title` and `data_sources`, and `test_export_app_data.py:34` pins that set.
- Fix: mark them `_planned`.

**N6 (minor). Two weak test assertions.**
- `test_notebooks_sync.py:64-65` says "7 cells" in a comment but asserts over `range(len(nb.cells))`, so it cannot detect a change in cell count.
- `test_export_app_data.py:77` accepts a 40-character hash where it means a short hash.

**N7 (minor). Dead template code inflates the coverage gate.**
- `charts.tsx` (Histogram, Heatmap) and `LineChart.tsx` have no production import.
- They are 2 of the 7 files below 100% in the coverage table, and they contain the only statistic in `app/src`.
- `diagrams.tsx:12` cites "BUILD_SPEC", which is not in this repo.
- The `qd:` storage prefix and the Metrics page are carried over from a template.

**N8 (minor). Dependency hygiene.**
- `eslint@9.39.5` prints "This version is no longer supported" during `npm ci`.
- pytest 9.2.0 was pinned less than 24 hours after its release.
- `stats-gl` pulls a duplicate `three@0.170.0` into `node_modules` (not into the bundle).
- The `EventTerrain3D` chunk is 944 kB and triggers Vite's warning for chunks over 500 kB.

**N9 (minor, observed during the review). A large generated graph appeared in the commit set.**
- `docs/architecture/graph/` appeared at 10:09, from another session.
- It holds 6.8 MB of generated graphify output (`graph.svg` 4.7 MB, `graph.json` 1.1 MB, `graph.html` 1.1 MB) and is not ignored.
- It contains no absolute paths (grep: 0 hits). Decide deliberately whether this belongs in git.

**N10 (minor). Smaller doc defects.**
- `docs/prfaq.md:29` says "Four questions need answers:" and lists three.
- `app/DATA.md:38` says "The same text appears on the About page", but `studyContent.ts:80` words it differently.

## Single most important fix

N1 together with 1.2c. Make `meta.json` the single source of the data-sources and licence table: the app renders
it, and a Python test pins each source's licence and URL. Today a wrong CC BY-SA licence passes all 208 tests on
both sides.

## One item to delete

`app/src/lib/charts.tsx` and `app/src/lib/LineChart.tsx`, with their tests. Nothing in production uses them, they
inflate the coverage gate, and `binValues` is the only statistic computed in `app/src`. Bring them back when a page
needs them.

## Minimal fixes for REFUTED rows (not applied)

- **1.2c:** In `test_export_app_data.py`, assert the full `DATA_SOURCES` value: name, URL and licence per source.
  Assert `len(git_short_commit()) <= 12`. Add a test that `main([])` writes to `DEFAULT_OUT`, using a
  monkeypatched `ROOT`.
- **2.1b:** `requires = ["hatchling==<version>"]`.
- **3.2 and 10c (`:284`):** `build_notebooks.py:109` →
  `path.exists() and path.read_bytes() == render().encode("utf-8")`.
- **3.3b:** Add pinned `jupyterlab` and `ipykernel` to `[dependency-groups].dev` and re-lock, or change the text
  (`build_notebooks.py:49`) to `uv run --with jupyterlab jupyter lab`. Then rebuild the notebook.
- **5.1b:** In `envelope()`, raise `TypeError` unless `kind` and `source_commit` are `str` and `data` is a `dict`.
  Optionally reject `int` outside ±2^53 in `dumps` (a `default=`/walk check). Or document the asymmetry.
- **9b:** `docs/milestones/00-scaffold-and-design.md:59` → `OK: …/notebooks/00_scaffold_tour.ipynb …`.
- **9c:** Describe the diagram kit as a vendored local toolkit that is deliberately not on GitHub, and name the backtester only as a sibling project, or drop the names. Replace "the shared-data hub"
  and "the owner's global CLAUDE.md" with the rule itself.
- **9f:**
  - Replace "aggregated" / "summarised" with "selected and filtered".
  - Replace `commit_ref "master"` with the resolved commit hash (re-query with `dolt_hashof('master')` or record it).
  - Add a two-line CC BY-SA notice at the top of `research/prototypes/worked.py`.
  - Change "mid quotes" to "bid/ask quotes".
- **10c:**
  - `:196` → "the format string omits `%f`, so microseconds are dropped".
  - `:280` → "The first (markdown) cell stamps the package version".
- **12b:** Cite `data-model.md` §… / ADR 0002 for `:73-77`, and write "0.26-1.1 vol points" at `:115`.
- **14:** Delete `charts.tsx` (see above). Change `studyContent.ts:15` to "no result is calculated in the browser;
  the 3D preview is a labelled synthetic shape".

## Probe index (all under `docs/validation/probes/m0-code/`, none contains a local path)

| Probe | What it does |
|---|---|
| `pypi_pins.py` | 2.1/2.3, PyPI registry check |
| `nb_determinism.sh` | 3.1 hashes across processes; 3.2 byte drifts (run on a copy only) |
| `mutate_py.py` | 1.2, 33 Python mutants with restore and sha256 check (run on a copy only) |
| `contract_py_probe.py` | 4.x, plus emitting envelopes for 5.1 |
| `contract_ts_probe.mjs` | 5.1 and 4.4 against the real `contract.ts` (`node --experimental-strip-types`) |
| `coverage_gate_probe.sh` | 6.2 (app copy only) |
| `public_data_probe.sh` | 5.2 and N1 (app copy only) |
| `mutate_app.mjs` | 8.1 / 8.3 / 8.4, 27 app mutants (app copy only) |
| `mulberry32_oracle.py` | 8.2 |
| `docs/` (fork) | `link_resolver.py`, `mermaid_extract.py`, `render_mermaid_mmdc.sh`, `doc_claims_probe.py`, `browser_snippets.js` |
