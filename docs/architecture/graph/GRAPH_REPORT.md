# Graph Report - earnings-vol-study  (2026-10-28)

## Corpus Check
- Large corpus: 157 files · ~601,651 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder.

## Summary
- 719 nodes · 1348 edges · 38 communities (30 shown, 8 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS · INFERRED: 5 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- event_terrain
- studyContent
- meta
- External modules
- test_contract
- terrain
- package
- metrics
- worked
- diagrams
- p06_identity
- tsconfig.app
- External modules
- package
- tsconfig.node
- contract_ts_probe
- test_export_app_data
- p01_calendar
- h2h3_followup_sim
- d5_aliv_span
- config
- h2h3_size_sim
- pypi_pins
- d1_twoway_cgm
- d4_default_gap_selection
- spacing
- route_a_vs_b
- browser_snippets
- mulberry32_oracle
- nb_determinism
- public_data_probe
- meta_single_source
- nb_drift_delta
- tsconfig
- coverage_gate_probe
- render_mermaid_mmdc
- pyproject

## God Nodes (most connected - your core abstractions)
1. `vitest` - 25 edges
2. `make()` - 21 edges
3. `compilerOptions` - 20 edges
4. `compilerOptions` - 16 edges
5. `react` - 12 edges
6. `@testing-library/react` - 12 edges
7. `parseMetaData()` - 12 edges
8. `StorageLike` - 12 edges
9. `main()` - 12 edges
10. `AppShell()` - 11 edges

## Surprising Connections (you probably didn't know these)
- `test_datetime_whose_timezone_gives_no_offset_is_rejected()` --calls--> `NoOffset`  [INFERRED]
  tests/test_contract.py → docs/validation/probes/m0-code/contract_py_probe.py
- `App()` --calls--> `MetaFooter()`  [EXTRACTED]
  app/src/App.tsx → app/src/lib/MetaFooter.tsx
- `App()` --calls--> `AppShell()`  [EXTRACTED]
  app/src/App.tsx → app/src/lib/shell.tsx
- `StudySections()` --calls--> `DataSourcesSection()`  [EXTRACTED]
  app/src/lib/StudySections.tsx → app/src/lib/DataSourcesSection.tsx
- `DiagramSections()` --calls--> `track()`  [EXTRACTED]
  app/src/lib/about.tsx → app/src/lib/metrics.ts

## Import Cycles
- None detected.

## Communities (38 total, 8 thin omitted)

### Community 0 - "event_terrain"
Cohesion: 0.06
Nodes (29): add_camera(), add_floor(), add_label(), add_lights_and_world(), add_object(), add_terrain(), build_surface(), _cell() (+21 more)

### Community 1 - "studyContent"
Cohesion: 0.07
Nodes (30): App(), PAGES, STORE, ErrorBoundary, Props, bps(), fmt(), pct() (+22 more)

### Community 2 - "meta"
Cohesion: 0.08
Nodes (41): Envelope, ENVELOPE_KEYS, fail(), isIsoUtc(), isPlainObject(), parseEnvelope(), ParseResult, SCHEMA_VERSION (+33 more)

### Community 3 - "External modules"
Cohesion: 0.07
Nodes (18): anchors(), check(), main(), slug(), main(), sha(), main(), sha() (+10 more)

### Community 4 - "test_contract"
Cohesion: 0.07
Nodes (25): NoOffset, load_tool(), test_dolt_repo_dir_without_dot_dolt_raises(), test_dolt_repo_missing_dir_raises_with_clone_hint(), make(), test_datetime_whose_timezone_gives_no_offset_is_rejected(), test_dumps_accepts_the_largest_integers_that_javascript_holds_exactly(), test_dumps_does_not_check_floats() (+17 more)

### Community 5 - "terrain"
Cohesion: 0.10
Nodes (29): EVENT_DAYS, ILLUSTRATIVE_LABEL, illustrativeIvGrid(), ivBump(), controlsConfig, prefersReducedMotion(), gaussian(), mulberry32() (+21 more)

### Community 6 - "package"
Cohesion: 0.05
Nodes (38): dependencies, react, react-dom, @react-three/drei, @react-three/fiber, three, description, name (+30 more)

### Community 7 - "metrics"
Cohesion: 0.12
Nodes (27): EMPTY, EVENT_CAP, getMetrics(), MetricEvent, metricsKey(), MetricsState, resetMetrics(), timeIt() (+19 more)

### Community 8 - "worked"
Cohesion: 0.06
Nodes (13): atm(), wK(), black(), black(), crr(), pipeline(), wK(), atm_w() (+5 more)

### Community 9 - "diagrams"
Cohesion: 0.16
Nodes (22): AboutContent, AboutPage(), DiagramContent, DiagramSections(), base, UseCase, ACTIVITY_EDGES, ACTIVITY_NODES (+14 more)

### Community 10 - "p06_identity"
Cohesion: 0.11
Nodes (10): aliv(), one_rep(), ramp(), bmp(), cs(), analytic_changes(), sim(), sim() (+2 more)

### Community 11 - "tsconfig.app"
Cohesion: 0.09
Nodes (21): compilerOptions, allowImportingTsExtensions, jsx, lib, module, moduleDetection, moduleResolution, noEmit (+13 more)

### Community 12 - "External modules"
Cohesion: 0.13
Nodes (4): blocks(), main(), BigIntSubclass, show()

### Community 13 - "package"
Cohesion: 0.11
Nodes (18): devDependencies, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, jsdom, @testing-library/jest-dom (+10 more)

### Community 14 - "tsconfig.node"
Cohesion: 0.11
Nodes (17): compilerOptions, allowImportingTsExtensions, lib, module, moduleDetection, moduleResolution, noEmit, noFallthroughCasesInSwitch (+9 more)

### Community 15 - "contract_ts_probe"
Cohesion: 0.14
Nodes (6): [contractPath, pyLines, metaPath], dev, good, MUTANTS, MUTANTS, ONLY

### Community 16 - "test_export_app_data"
Cohesion: 0.17
Nodes (8): exporter(), run_export(), test_cboe_and_yahoo_are_never_committed(), test_data_licence_covers_exactly_the_sources_that_name_its_licence(), test_data_licence_is_exactly_the_expected_value(), test_data_sources_are_exactly_the_expected_table(), test_meta_data_fields(), test_writes_envelope_with_five_keys()

### Community 17 - "p01_calendar"
Cohesion: 0.22
Nodes (8): close_et(), day0_rule(), day0_spacing(), is_session(), next_session(), prev_session(), n_sessions(), nxt()

### Community 18 - "h2h3_followup_sim"
Cohesion: 0.19
Nodes (7): keep_cut(), one_rep(), twoway_normal(), cl_stats(), crush_stats(), ik_df(), one_rep()

### Community 20 - "config"
Cohesion: 0.29
Nodes (5): cache_dir(), data_dir(), dolt_repo(), project_dir(), raw_dir()

### Community 21 - "h2h3_size_sim"
Cohesion: 0.36
Nodes (6): bartlett_if_needed(), build_design(), cr1(), gen(), one_rep(), quad()

### Community 22 - "pypi_pins"
Cohesion: 0.43
Nodes (3): main(), pins(), usable()

### Community 23 - "d1_twoway_cgm"
Cohesion: 0.38
Nodes (3): adr_twoway(), cr1(), sm_twoway()

### Community 24 - "d4_default_gap_selection"
Cohesion: 0.38
Nodes (3): r0_of(), run(), terc_within_rep()

### Community 26 - "route_a_vs_b"
Cohesion: 0.40
Nodes (3): contra_of(), report(), terc_within_rep()

### Community 27 - "browser_snippets"
Cohesion: 0.50
Nodes (3): ctl, out, res

### Community 29 - "nb_determinism"
Cohesion: 0.83
Nodes (3): chk(), render_hash(), nb_determinism.sh script

### Community 30 - "public_data_probe"
Cohesion: 0.83
Nodes (3): py(), run(), public_data_probe.sh script

### Community 31 - "meta_single_source"
Cohesion: 0.83
Nodes (3): run_all(), meta_single_source.sh script, variant()

### Community 32 - "nb_drift_delta"
Cohesion: 0.83
Nodes (3): chk(), edit(), nb_drift_delta.sh script

## Knowledge Gaps
- **8 isolated node(s):** `@types/react`, `@types/react-dom`, `@types/three`, `@vitest/coverage-v8`, `eslint` (+3 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 277 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **8 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `vitest` connect `studyContent` to `meta`, `terrain`, `package`, `metrics`, `diagrams`?**
  _High betweenness centrality (0.065) - this node is a cross-community bridge._
- **What connects `@types/react`, `@types/react-dom`, `@types/three` to the rest of the system?**
  _8 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `event_terrain` be split into smaller, more focused modules?**
  _Cohesion score 0.06429070580013976 - nodes in this community are weakly interconnected._
- **Why does `react` connect `meta` to `studyContent`, `terrain`, `package`, `metrics`, `diagrams`?**
  _High betweenness centrality (0.025) - this node is a cross-community bridge._
- **Should `studyContent` be split into smaller, more focused modules?**
  _Cohesion score 0.07474600870827286 - nodes in this community are weakly interconnected._
- **Why does `devDependencies` connect `package` to `package`?**
  _High betweenness centrality (0.018) - this node is a cross-community bridge._
- **Should `meta` be split into smaller, more focused modules?**
  _Cohesion score 0.08078431372549019 - nodes in this community are weakly interconnected._