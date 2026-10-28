"""Probe: extract every ```mermaid block from Markdown files, plus every .mmd file given,
into one JSON list for the browser renderer (mermaid_render.html), and check that each
fenced block in docs/architecture/README.md is byte-identical to the .mmd file it claims
to copy.

Usage (from the repo root):
    python3 docs/validation/probes/m0-code/docs/mermaid_extract.py OUT.json FILE [FILE ...]

FILE may be .md (fenced blocks are extracted) or .mmd (whole file).
Prints, for every fenced block, whether it equals any .mmd file given (and which).
Exit code 0 always; the comparison lines are the evidence.
"""

import json
import re
import sys
from pathlib import Path


def blocks(md: Path):
    lines = md.read_text(encoding="utf-8").splitlines(keepends=True)
    out, buf, start, inside = [], [], 0, False
    for i, line in enumerate(lines, 1):
        if not inside and re.match(r"^```mermaid\s*$", line):
            inside, buf, start = True, [], i + 1
        elif inside and re.match(r"^```\s*$", line):
            out.append((start, "".join(buf)))
            inside = False
        elif inside:
            buf.append(line)
    return out


def main(argv: list[str]) -> int:
    out_path, files = Path(argv[0]), [Path(a) for a in argv[1:]]
    items, mmd = [], {}
    for f in files:
        if f.suffix == ".mmd":
            text = f.read_text(encoding="utf-8")
            mmd[str(f)] = text
            items.append({"id": str(f), "code": text})
    for f in files:
        if f.suffix == ".md":
            for start, code in blocks(f):
                ident = f"{f}:{start}"
                items.append({"id": ident, "code": code})
                same = [k for k, v in mmd.items() if v == code]
                near = [k for k, v in mmd.items() if v.strip() == code.strip()]
                print(f"BLOCK {ident}: {len(code.splitlines())} lines; "
                      f"identical to {same or 'none'}; equal-after-strip to {near or 'none'}")
    out_path.write_text(json.dumps(items), encoding="utf-8")
    print(f"wrote {len(items)} diagrams to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
