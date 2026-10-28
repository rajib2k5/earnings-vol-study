#!/usr/bin/env bash
# C6.2 probe: are the coverage thresholds in vite.config.ts actually enforced on src/lib/**?
# Usage: coverage_gate_probe.sh <app-COPY with node_modules installed>   (never the real app/)
# Adds an untested 80-function file to src/lib/ (and, separately, to src/three/), runs coverage,
# records exit codes, then deletes the file.
set -u
A="$1"; cd "$A" || exit 2
gen() { for i in $(seq 1 80); do echo "export function f$i(x: number): number { return x + $i }"; done; }
gen > src/lib/zz_untested_probe.ts
npx vitest run --coverage > "$A/.cov_lib.tmp" 2>&1; rc=$?
echo "untested file in src/lib   -> vitest --coverage rc=$rc"; grep -E "zz_untested|ERROR: Coverage|Lines +:|Functions +:" "$A/.cov_lib.tmp"
rm -f src/lib/zz_untested_probe.ts "$A/.cov_lib.tmp"
mkdir -p src/three; gen > src/three/zz_untested_probe.ts
npx vitest run --coverage > "$A/.cov_three.tmp" 2>&1; rc=$?
echo "untested file in src/three -> vitest --coverage rc=$rc"; grep -E "zz_untested|ERROR: Coverage|Lines +:" "$A/.cov_three.tmp"
rm -f src/three/zz_untested_probe.ts "$A/.cov_three.tmp"
npx vitest run --coverage > "$A/.cov_base.tmp" 2>&1; echo "restored baseline -> rc=$?"; grep -E "Lines +:" "$A/.cov_base.tmp"; rm -f "$A/.cov_base.tmp"
