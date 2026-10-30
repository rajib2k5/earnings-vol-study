"""p11: the graphify refresh in docs/architecture/graph/: counts, and any trace of an LLM (semantic) pass.

    python3 docs/validation/probes/m5/p11_graph.py

Counts nodes, edges (links), communities and distinct source files in graph.json; tallies every node/edge attribute
value that could mark a semantic extraction (confidence labels, relation kinds, file types, model names); lists
source files outside the scope the README states; compares GRAPH_REPORT.md's own counts.
"""
import collections
import json
import re
from pathlib import Path

G = Path("docs/architecture/graph")
g = json.loads((G / "graph.json").read_text())
print("top-level keys:", sorted(g.keys()))
nodes = g.get("nodes", [])
edges = g.get("links", g.get("edges", []))
print(f"nodes {len(nodes):,}; edges {len(edges):,}")
comm = {n.get("community") for n in nodes if "community" in n}
print(f"communities (distinct node.community): {len(comm)}")
files = {n.get("source_file") for n in nodes if n.get("source_file")}
print(f"distinct source_file over nodes: {len(files)}")
nk = collections.Counter(k for n in nodes for k in n)
ek = collections.Counter(k for e in edges for k in e)
print("node keys:", dict(nk))
print("edge keys:", dict(ek))
for key in ("file_type", "type", "kind", "confidence", "source", "extractor", "model"):
    c = collections.Counter(str(n.get(key)) for n in nodes if key in n)
    if c:
        print(f"node {key}: {dict(c.most_common(12))}")
for key in ("relation", "confidence", "confidence_score", "source", "extractor", "model", "type"):
    c = collections.Counter(str(e.get(key)) for e in edges if key in e)
    if c:
        print(f"edge {key}: {dict(c.most_common(15))}")
ext = collections.Counter(Path(f).suffix for f in files)
print("source file suffixes:", dict(ext))
scope = re.compile(r"^(src/|tests/|tools/|research/prototypes/|docs/validation/probes/|app/|pyproject\.toml)")
out = sorted(f for f in files if not scope.match(f.replace(str(Path.cwd()) + "/", "")))
print(f"source files outside the stated scope: {len(out)} {out[:10]}")
bad = sorted(f for f in files if re.search(r"node_modules|\.venv|/dist/|notebooks/|\.learning/", f))
print(f"source files in excluded folders: {len(bad)} {bad[:5]}")
rep = (G / "GRAPH_REPORT.md").read_text()
print("GRAPH_REPORT summary lines:", [l.strip() for l in rep.splitlines() if re.search(r"\d[\d,]* (files|nodes|edges|communities)", l)][:6])
print("GRAPH_REPORT mentions of LLM/semantic/INFERRED:",
      {w: len(re.findall(w, rep)) for w in ("LLM", "semantic", "INFERRED", "AMBIGUOUS", "EXTRACTED")})
