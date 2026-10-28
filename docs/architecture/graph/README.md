# Knowledge graph (graphify)

A graph of this repository's **code** at the end of milestone 0, built with
[graphify](https://github.com/safishamsi/graphify) 0.9.93. Each code file is parsed into a syntax tree and
read for functions, classes, imports and calls. No LLM is involved, so the graph is deterministic.

The scope is the 117 code files: Python in `src/`, `tests/`, `tools/`, `research/prototypes/` and the
validation probes; TypeScript and TSX in `app/`; plus config files.

| File | What it is |
|---|---|
| `graph.html` | Interactive graph. Download it and open it in a browser; no server needed. |
| `graph.svg` | Static render. |
| `graph.json` | Raw nodes, edges and communities, for queries. |
| `GRAPH_REPORT.md` | The audit report: most-connected nodes, communities and their cohesion, suggested questions. |

When it was built it had **719 nodes, 1,348 edges and 38 communities**. Each community is named after the
file that holds most of its nodes.

**Why docs are not in it.** A mid-milestone build also extracted concepts from the 28 docs (ADRs, data model,
concept and milestone docs). Those parts went stale when the adversarial reviews changed the ADRs, so they
were dropped rather than published with refuted claims in them. The doc layer is rebuilt at milestone 1,
once the design has settled. Until then, `docs/architecture/README.md` and the ADRs are the map of the design.

**Rebuild.** The working copy lives in `graphify-out/`, which is git-ignored. To rebuild it, run
`/graphify . --update` in Claude Code. To ask the graph a question:

```bash
graphify query "what calls envelope()?"
```
