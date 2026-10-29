"""p11b: do the committed events-layer tables rebuild byte-identically? (milestone §6 "Rebuild determinism")

  uv run python docs/validation/probes/m1/p11b_rebuild_derived.py <scratch dir>

Builds the events layer in memory from the local cache and writes the committed columns with
store.write_derived into <scratch dir> (never data/derived), then compares bytes.
"""
import hashlib
import sys
from pathlib import Path

from earnings_vol import config, params as params_mod, schema, store
from earnings_vol.events import run as ev_run
from earnings_vol.ingest import prices

out_dir = Path(sys.argv[1])
p = params_mod.load()
out = ev_run.build(p, ev_run.load_inputs(p), lambda s: prices.load(s, config.raw_dir()))
for name in ("session", "security", "ticker_alias", "events", "eps"):
    store.write_derived(out[name], schema.REGISTRY[name], out_dir)
    a = hashlib.sha256((ev_run.DERIVED / f"{name}.parquet").read_bytes()).hexdigest()
    b = hashlib.sha256((out_dir / f"{name}.parquet").read_bytes()).hexdigest()
    print(f"{name:14s} committed {a[:16]} rebuilt {b[:16]} identical={a == b}")
