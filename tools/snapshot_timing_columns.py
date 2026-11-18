"""The descriptive columns of the snapshot-timing check for H5-H7 (docs/validation/snapshot-timing/preregistration.md §11).

    .venv/bin/python -I tools/snapshot_timing_columns.py      # writes docs/validation/snapshot-timing/columns.json

Plan §11 gives H5, H6 and H7 two columns at every outcome of the check, worded "not covered by the timing check":
the primary regression without the events whose day -1 or day 0 is off, and without the events whose day 0 is in
2026. Each column is the primary's own statistic (two-way date x company t of the term; for H7 the slope b and the
two-way Wald of a = 0, b = 1), with no Holm correction and no G1 check, so no verdict.

A column re-runs the whole primary regression on the smaller event set: the excluded events leave as incomplete
cases (their |surprise| or their realised move is set to missing), so the regressors are re-standardised and the
fixed effects rebuilt on the events that remain. The run first refits the full set and stops unless it reproduces
the committed results rows exactly, so a column differs from the published row only by the events it drops.

Aggregates only: no event id, date or per-event value is written.
"""

from __future__ import annotations

import dataclasses
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from earnings_vol import params as params_mod
from earnings_vol import store
from earnings_vol.stats import drivers, regression
from earnings_vol.stats import run as stats_run

REPO = Path(__file__).resolve().parents[1]
DOCS = REPO / "docs/validation/snapshot-timing"
OUT = DOCS / "columns.json"
RESULTS = REPO / "data/derived/results.parquet"
# The column each set drops through: a missing value there makes the event an incomplete case of the model.
DROP_VIA = {"crush": "abs_surprise_scaled_w", "h7": "realized_ret_0"}
TOL = 1e-9


def tool(name: str):
    spec = importlib.util.spec_from_file_location(name, REPO / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def rnd(x, nd: int = 6):
    return None if x is None or not np.isfinite(x) else round(float(x), nd)


def without(f, drop: np.ndarray, column: str):
    """A copy of the Frame whose events in `drop` (bool over f.ev rows) have `column` missing. Pure."""
    if drop.shape != (len(f.ev),):
        raise ValueError(f"drop mask has shape {drop.shape}, the Frame {len(f.ev)} events")
    ev = f.ev.copy()
    ev.loc[drop, column] = np.nan
    return dataclasses.replace(f, ev=ev)


def _cell(res: dict) -> dict:
    return {"estimate": rnd(res["estimate"]), "se": rnd(res["se"]), "ci_lo": rnd(res["ci_lo"]),
            "ci_hi": rnd(res["ci_hi"]), "p": rnd(res["p_value"]), "df": rnd(res["df"], 1), "n": int(res["n"]),
            "dates": int(res["n_clusters"]),
            "companies": None if res.get("n_clusters_firm") is None else int(res["n_clusters_firm"]),
            "fallback": bool(res.get("fallback", False))}


def crush_cells(f, winsor: tuple) -> dict:
    """H5 and H6: the two-way t of their terms in the primary crush model (drivers.PRIMARY)."""
    m = drivers.model_inputs(f, drivers.PRIMARY, winsor)
    fit, cov = drivers.fit_model(m, True)
    return {h: _cell(regression.coef_test(fit, cov, m["names"].index(t))) for h, t in drivers.HYP_TERMS.items()}


def h7_cell(f) -> dict:
    """H7: the slope b with its two-way t interval and p of b = 1 (as the published b row), and the two-way Wald
    of a = 0, b = 1 (H7's primary)."""
    m = drivers.h7_inputs(f, "evar_m1")
    fit, cov = drivers.fit_model(m, True)
    b = _cell(drivers.shift_null(regression.coef_test(fit, cov, 1), 1.0))
    w = regression.wald_test(fit, cov, np.eye(2), np.array([0.0, 1.0]))
    return b | {"wald_F": rnd(w["stat"]), "wald_p": rnd(w["p_value"])}


def cells(f, drop: np.ndarray, winsor: tuple) -> dict:
    out = crush_cells(without(f, drop, DROP_VIA["crush"]), winsor)
    out["H7"] = h7_cell(without(f, drop, DROP_VIA["h7"]))
    return out


def published(res: pd.DataFrame) -> dict:
    """The committed rows the full-set refit must reproduce."""
    def one(**want) -> pd.Series:
        r = res
        for k, v in want.items():
            r = r[r[k] == v]
        if len(r) != 1:
            raise RuntimeError(f"results.parquet {want}: expected 1 row, found {len(r)}")
        return r.iloc[0]
    out = {h: one(model_id="crush_drivers", adjustment="market", sample="daily", subgroup_key="all",
                  statistic="twoway_date_t", term=t) for h, t in drivers.HYP_TERMS.items()}
    out["H7"] = one(model_id="implied_realised", sample="daily", subgroup_key="all", statistic="twoway_date_t",
                    term="b")
    return out


def reproduces(full: dict, pub: dict) -> list[str]:
    """The fields where the full-set refit differs from the committed row (empty: it reproduces them)."""
    bad = []
    for h, row in pub.items():
        for k, col in (("estimate", "estimate"), ("se", "se"), ("ci_lo", "ci_lo"), ("ci_hi", "ci_hi"), ("n", "n")):
            if abs(float(full[h][k]) - float(row[col])) > (0 if k == "n" else 1e-6):
                bad.append(f"{h} {k}: refit {full[h][k]}, published {row[col]}")
    return bad


def compute() -> dict:
    stc = tool("snapshot_timing_check")
    p = params_mod.load()
    cls, _ = stc.timing_map(p)
    f = stats_run.load(p)
    ev = stc.event_frame(f, np.arange(len(f.ev)))
    c_m1 = np.array([cls(s) for s in ev["s_m1"]], dtype=object)
    c_0 = np.array([cls(s) for s in ev["s_0"]], dtype=object)
    drops = {"all": np.zeros(len(f.ev), bool),
             "no_off": (c_m1 == "off") | (c_0 == "off"),
             "no_2026": np.array([s.year == 2026 for s in ev["s_0"]])}
    winsor = tuple(p["drivers"]["surprise_winsor"])
    out = {k: cells(f, d, winsor) for k, d in drops.items()}
    bad = reproduces(out["all"], published(pd.read_parquet(RESULTS)))
    if bad:
        raise RuntimeError("the full-set refit does not reproduce the committed rows: " + "; ".join(bad))
    # How many of each model's events each column drops, and whether any late or unknown session sits at day -1
    # or day 0 among them (plan §11 names off sessions only).
    in_model = {"H5": drivers.model_inputs(f, drivers.PRIMARY, winsor)["rows"], "H7": drivers.h7_inputs(f)["rows"]}
    in_model["H6"] = in_model["H5"]
    dropped = {h: {k: int(d[r].sum()) for k, d in drops.items() if k != "all"} for h, r in in_model.items()}
    other = {h: int(np.isin(c_m1[r], ["late", "unknown"]).sum() + np.isin(c_0[r], ["late", "unknown"]).sum())
             for h, r in in_model.items()}
    return {
        "kind": "snapshot_timing_columns",
        "plan": "docs/validation/snapshot-timing/preregistration.md §11",
        "plan_sha256": hashlib.sha256(stc.PLAN.read_bytes()).hexdigest(),
        "timing_map_sha256": hashlib.sha256(stc.MAP.read_bytes()).hexdigest(),
        "params_hash": p.params_hash,
        "code_commit": store.code_commit(),
        "statistic": {"H5": "twoway_date_t of abs_surprise in crush_drivers (market)",
                      "H6": "twoway_date_t of ln_sigma_d in crush_drivers (market)",
                      "H7": "twoway_date_t of b in implied_realised; wald_F/wald_p: twoway_date_wald of a=0,b=1"},
        "columns": {"all": "every event (reproduces results.parquet)",
                    "no_off": "without the events whose day -1 or day 0 is off",
                    "no_2026": "without the events whose day 0 is in 2026"},
        "dropped": dropped,
        "late_or_unknown_at_day_m1_or_0": other,
        "cells": {h: {k: out[k][h] for k in drops} for h in ("H5", "H6", "H7")},
    }


def main(argv=None) -> int:
    out = compute()
    OUT.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(f"wrote {OUT.relative_to(REPO)}: dropped {out['dropped']}")
    for h, c in out["cells"].items():
        print(h, {k: (v["estimate"], v["ci_lo"], v["ci_hi"], v["n"]) for k, v in c.items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
