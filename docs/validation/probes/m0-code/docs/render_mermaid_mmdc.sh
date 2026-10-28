#!/usr/bin/env bash
# Probe: render every Mermaid diagram with mermaid-cli in headless Chrome.
# Usage (from the repo root):  SCRATCH=<empty scratch dir> CHROME=<path to a chrome/chrome-headless-shell binary> \
#        bash docs/validation/probes/m0-code/docs/render_mermaid_mmdc.sh
# Installs @mermaid-js/mermaid-cli@11.4.2 into $SCRATCH (no browser download), extracts all diagrams with
# mermaid_extract.py, appends two deliberately broken diagrams as falsifiers, renders each to SVG and prints
# rc + SVG size. Pass: every repo diagram rc=0 and no "Syntax error in" in its SVG; both falsifiers rc!=0.
set -u
: "${SCRATCH:?set SCRATCH}"; : "${CHROME:?set CHROME}"
here="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$SCRATCH/mmdc/in" "$SCRATCH/mmdc/out"
python3 "$here/mermaid_extract.py" "$SCRATCH/diagrams.json" docs/architecture/*.mmd docs/architecture/README.md \
  docs/milestones/00-scaffold-and-design.md docs/architecture/data-model.md README.md LEARNING_LOG.md docs/prfaq.md
python3 - "$SCRATCH" <<'PY'
import json, re, sys
sp = sys.argv[1]
items = json.load(open(f"{sp}/diagrams.json"))
items += [{"id": "FALSIFIER-broken-flowchart", "code": "flowchart LR\n  A[\"unclosed --> B\n"},
          {"id": "FALSIFIER-broken-erd", "code": "erDiagram\n  a ||--xx b : \"bad\"\n"}]
for i, it in enumerate(items):
    open(f"{sp}/mmdc/in/{i:02d}_" + re.sub(r"[^A-Za-z0-9]+", "_", it["id"])[-60:] + ".mmd", "w").write(it["code"])
PY
cd "$SCRATCH/mmdc"
[ -x node_modules/.bin/mmdc ] || { echo '{"name":"p","private":true}' > package.json; PUPPETEER_SKIP_DOWNLOAD=1 npm i --no-audit --no-fund @mermaid-js/mermaid-cli@11.4.2 >/dev/null 2>&1; }
echo '{"args":["--no-sandbox"]}' > pptr.json
echo "mermaid $(node -e "console.log(require('./node_modules/mermaid/package.json').version)")"
for f in in/*.mmd; do b=$(basename "$f" .mmd)
  PUPPETEER_EXECUTABLE_PATH="$CHROME" timeout 120 ./node_modules/.bin/mmdc -q -p pptr.json -i "$f" -o "out/$b.svg" >"out/$b.log" 2>&1; rc=$?
  echo "rc=$rc svg_bytes=$(stat -c %s "out/$b.svg" 2>/dev/null || echo 0) syntax_errors=$(grep -c 'Syntax error in' "out/$b.svg" 2>/dev/null || echo -) $b"
done
