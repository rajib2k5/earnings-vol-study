#!/usr/bin/env bash
# Delta-2 probe e7 (claim 7): every EDGAR / 8-K mention in docs/, README.md, LEARNING_LOG.md that carries no
# proposal qualifier on the same line. Each hit must then be read in context (the ledger records the reading).
# Review records under docs/validation/ are excluded: they describe earlier states on purpose.
# Run from the repository root: bash docs/validation/probes/m0-delta2/e7_edgar_grep.sh
set -u
echo "all hits (files):"; grep -rli "edgar\|8-K" docs README.md LEARNING_LOG.md | grep -v '^docs/validation/' | sort
echo; echo "hits with no qualifier on the line:"
grep -rn -i "edgar\|8-K" docs README.md LEARNING_LOG.md | grep -v '^docs/validation/' \
  | grep -v -i "propos\|pending\|if the owner\|owner approv\|only if\|owner decid\|owner's\|would\|if approved\|declin" \
  | grep -v -i "graph\.\(json\|svg\|html\)" | cut -c1-200
