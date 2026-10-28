#!/usr/bin/env bash
# M0 delta review, claim 8f. Usage: meta_single_source.sh <repo-COPY>
# (NEVER the real repo: it rewrites app/public/data/meta.json and adds a test file to app/src.)
# The copy needs app/node_modules (npm ci) and a .venv (uv sync --frozen).
#  1. Copy realMetaRender.probe.test.tsx into the copy's app/src and run it on the committed meta.json.
#  2. Rewrite meta.json in three schema-valid but wrong ways (V1-V3) and three ways the app's
#     publicData.test.ts should catch (V4-V6); for each, run the probe test
#     (does the page change?), the full app suite and the full Python suite (does anything fail?).
#  3. Restore meta.json, remove the probe test, compare sha256.
set -u
R="$(cd "$1" && pwd)"; HERE="$(cd "$(dirname "$0")" && pwd)"
A="$R/app"; META="$A/public/data/meta.json"; PY="$R/.venv/bin/python"
cp "$META" "$META.orig"; H0=$(sha256sum "$META" | cut -c1-64)
cp "$HERE/realMetaRender.probe.test.tsx" "$A/src/realMetaRender.probe.test.tsx"

run_all() {
  echo "-- probe render:"
  (cd "$A" && npx vitest run src/realMetaRender.probe.test.tsx --silent=false --reporter=verbose 2>&1 | grep -E "PROBE|Tests ")
  echo "-- full app suite (without the probe file):"
  (cd "$A" && npx vitest run --exclude src/realMetaRender.probe.test.tsx --reporter=dot 2>&1 | grep -E "Test Files|Tests |FAIL")
  echo "-- full Python suite:"
  (cd "$R" && "$PY" -m pytest -q -p no:cacheprovider 2>&1 | tail -1)
}
variant() { "$PY" - "$META" "$1" <<'EOF'
import json, sys
p, v = sys.argv[1], sys.argv[2]
d = json.load(open(p))
src, lic = d["data"]["data_sources"], d["data"]["data_licence"]
if v == "V1":    # only the two DoltHub rows say CC BY 4.0 (table disagrees with data_licence)
    for s in src[:2]: s["licence"] = "CC BY 4.0"
elif v == "V2":  # a consistently wrong, stale licence everywhere
    for s in src[:2]: s["licence"] = "CC BY 4.0"
    lic["name"] = "CC BY 4.0"; lic["url"] = "https://creativecommons.org/licenses/by/4.0/"
    lic["attribution"] = lic["attribution"].replace("Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)", "Attribution 4.0 International (CC BY 4.0)")
elif v == "V3":  # stale file: the Yahoo row is missing and the earnings URL points at the options repo
    d["data"]["data_sources"] = src[:3]
    src[0]["url"] = "https://www.dolthub.com/repositories/post-no-preference/options"
elif v == "V4":  # schema-INVALID: an http:// URL (publicData.test.ts must fail)
    src[0]["url"] = "http://www.dolthub.com/repositories/post-no-preference/earnings"
elif v == "V5":  # schema-valid but CBOE marked as committed (publicData.test.ts must fail)
    src[2]["committed"] = True
elif v == "V6":  # schema-INVALID: applies_to names a source that is not in the table
    lic["applies_to"] = ["DoltHub post-no-preference/earnings", "DoltHub post-no-preference/opts"]
open(p, "w").write(json.dumps(d, indent=2, sort_keys=True) + "\n")
EOF
}
echo "== committed meta.json"; run_all
for v in V1 V2 V3 V4 V5 V6; do cp "$META.orig" "$META"; variant "$v"; echo; echo "== variant $v"; run_all; done
cp "$META.orig" "$META"; rm "$META.orig" "$A/src/realMetaRender.probe.test.tsx"
H1=$(sha256sum "$META" | cut -c1-64)
[ "$H0" = "$H1" ] && echo "restored: meta.json sha matches; probe test removed" || echo "RESTORE FAILED"
