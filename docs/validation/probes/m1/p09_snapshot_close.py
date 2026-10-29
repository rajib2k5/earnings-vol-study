"""p09: re-run the "snapshot is the close" check and attack its reading (claim 8).

  uv run python docs/validation/probes/m1/p09_snapshot_close.py <scratch dir>

Runs measures.run.run_close() against a SCRATCH stage folder (copies of the stage's
events and market_daily tables), so cache/stage is not written. Yahoo values stay
local: only summary statistics are printed.
Adds: a heteroskedasticity-robust (HC1) slope SE, the slope on BMO days as a placebo,
and the slope that a leak of a given size would produce (power).
"""
import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np

from earnings_vol import params as params_mod, schema, store
from earnings_vol.events import calendar
from earnings_vol.events.run import stage_dir
from earnings_vol.measures import run as mrun, snapshot_close


def main():
    scratch = Path(sys.argv[1])
    scratch.mkdir(parents=True, exist_ok=True)
    p = params_mod.load()
    sd = stage_dir(p)
    for n in ("events", "market_daily"):
        for suf in (".parquet", ".manifest.json"):
            src = sd / f"{n}{suf}"
            if src.exists():
                shutil.copy2(src, scratch / src.name)
    st = store.read_table(sd / "session.parquet", schema.SESSION)
    sessions = calendar.Sessions(st["session_date"].tolist())
    sec = store.read_table(sd / "security.parquet", schema.SECURITY)
    aliases = store.read_table(sd / "ticker_alias.parquet", schema.TICKER_ALIAS)
    ids = sorted(sec.loc[sec["in_universe"], "security_id"])

    # Capture the per-day frame by wrapping DataFrame construction inside run_close.
    captured = {}
    orig = mrun.pd.DataFrame

    def spy(*a, **k):
        df = orig(*a, **k)
        if a and isinstance(a[0], list) and a[0] and isinstance(a[0][0], dict) and "gap_next" in a[0][0]:
            captured["d"] = df
        return df

    mrun.pd.DataFrame = spy
    try:
        summary = mrun.run_close(p, scratch, sessions, aliases, ids)
    finally:
        mrun.pd.DataFrame = orig
    print(json.dumps(summary, indent=1, sort_keys=True))
    committed = sd / "snapshot_close.json"
    if committed.exists():
        print("identical to the stage's snapshot_close.json:", json.loads(committed.read_text()) == summary)

    d = captured["d"]
    amc = d[d.kind == "amc_day"].dropna(subset=["gap_next"])
    x, y = amc.gap_next.to_numpy(), amc["diff"].to_numpy()
    X = np.column_stack([np.ones_like(x), x])
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ beta
    xtx_inv = np.linalg.inv(X.T @ X)
    hc1 = xtx_inv @ (X.T * e**2) @ X @ xtx_inv * len(x) / (len(x) - 2)
    print(f"slope {beta[1]:.4f}; plain SE {snapshot_close.ols_slope(x, y)['se']:.4f}; HC1 SE {math.sqrt(hc1[1, 1]):.4f}")
    rng = np.random.default_rng(1)
    for lam in (0.02, 0.05, 0.10):
        hits = 0
        for _ in range(500):
            yy = y + lam * x
            bs = snapshot_close.ols_slope(x, yy)
            hits += (bs["slope"] - 1.96 * bs["se"]) > 0
        print(f"a leak of {lam:.0%} of the overnight move: detected (slope CI excludes 0) in {hits / 5:.0f}% "
              f"(deterministic shift: slope -> {snapshot_close.ols_slope(x, y + lam * x)['slope']:.4f})")
    # Placebo: an ordinary day's diff against its next overnight gap.
    o = d[d.kind == "ordinary"].dropna(subset=["gap_next"])
    print("placebo slope on ordinary days:", snapshot_close.ols_slope(o.gap_next, o["diff"]))
    print("n_strikes used on AMC days:", amc.n_strikes.value_counts().to_dict())


if __name__ == "__main__":
    main()
