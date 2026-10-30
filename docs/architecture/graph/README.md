# Knowledge graph (graphify)

A graph of this repository's **code**, built with [graphify](https://github.com/safishamsi/graphify) 0.9.93. Each code
file is parsed into a syntax tree and read for functions, classes, imports and calls. No LLM is involved, so the graph
is deterministic (the build pins `PYTHONHASHSEED=0` for the community detection).

**Refreshed 2026-10-29, at milestone 5: the code layer only, with graphify's AST pass and no LLM semantic extraction.**
The scope is the one milestone 0 used: Python in `src/`, `tests/`, `tools/`, `research/prototypes/` and the validation
probes; TypeScript, TSX, JavaScript and shell scripts in `app/` and `docs/validation/probes/`; plus `pyproject.toml`,
`app/package.json` and the `app/tsconfig*.json` files. `node_modules/`, `.venv/`, the build output, the notebooks and
`.learning/` are left out. That is **382 code files** (the milestone-5 review's probes included), giving **3,649
nodes, 9,313 edges and 166 communities**. Each community is named after the file that holds most of its nodes.

| File | What it is |
|---|---|
| `graph.html` | Interactive graph (refreshed). Download it and open it in a browser; no server needed. |
| `graph.json` | Raw nodes, edges and communities, for queries (refreshed). |
| `GRAPH_REPORT.md` | The audit report: most-connected nodes, communities and their cohesion, suggested questions (refreshed). |
| `graph.svg` | Static render. **Not refreshed: it is still the milestone-0 render (719 nodes).** The refreshed SVG was 12.4 MB, too large to be useful in the repository, so `graph.html` is the picture to use. |

**Why docs are not in it.** A mid-milestone-0 build also extracted concepts from the docs (ADRs, data model, concept
and milestone pages). Those parts went stale when the adversarial reviews changed the ADRs, so they were dropped.
The doc layer would need graphify's LLM extraction, which this refresh did not run.

**Rebuild.** The working copy lives in `graphify-out/`, which is git-ignored. `graphify update .` re-extracts with the
AST pass but takes in every file type graphify can read (Markdown, text outputs, images), so this refresh used
graphify's Python API on the code files above (`graphify.extract.extract`, `build_from_json`, `cluster`, `to_json`,
`report.generate`) and then `graphify export html`. To ask the graph a question:

```bash
graphify query "what calls envelope()?"
```
