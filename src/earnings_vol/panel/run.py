# =============================================================================
# run.py — run_panel(): the panel layer (milestone 3).
#
# Run:  uv run python -m earnings_vol.panel.run
#
# Reads (stage cache of this params hash): session, events, eps, market_daily
# (ln VIX), iv_daily, event_iv, chain_expiry (T1*'s IV inside the window);
# since milestone 4 also raw/yfinance/<symbol>.parquet and the rank date's
# market caps (local, Yahoo) for the regressor columns (panel/regressors.py).
# Writes, in ADR 0001's order (window rows -> beta -> market-adjusted columns
# -> event_measures; each table once, at the end):
#   cache/stage/<hash>/{event_window_obs,event_measures}.parquet + manifests
#                                                   (every column, class R too)
#   data/derived/{event_window_obs,event_measures}.parquet
#                                                   (committed columns only)
#   cache/stage/<hash>/panel_report.json            counts for the docs
# =============================================================================

import json
from collections import Counter

import numpy as np
import pandas as pd

from earnings_vol import config, params as params_mod, schema, store
from earnings_vol.events import calendar
from earnings_vol.events.run import DERIVED, stage_dir
from earnings_vol.ingest import prices, universe
from earnings_vol.measures import tables
from earnings_vol.panel import regressors, window


def build(p, t: dict, yahoo: dict | None = None, caps: dict | None = None) -> dict:
    """The two tables and the report, from the stage tables in `t`; `yahoo` ({security_id: Yahoo
    rows}) and `caps` ({security_id: market cap on the rank date}) feed the _yf regressors."""
    sessions = calendar.Sessions(t["session"]["session_date"].tolist())
    look = window.lookups(t["iv_daily"], t["market_daily"], sessions)
    pan = window.build_panel(t["events"], t["eps"], look, sessions, p["windows"])
    st = p["stats"]
    data_end = sessions.index[p.day("snapshot_eras", "data_end")]
    m = window.measures(pan, t["event_iv"], sessions, p["windows"], data_end, int(st["rhat_max_lag"]),
                        int(st["psd_grid"]))
    ce = t["chain_expiry"]
    ok = ce[ce["status"] == "ok"]
    chains: dict = {}
    for r in ok.to_dict("records"):
        chains.setdefault((r["security_id"], r["session_date"]), []).append(r)
    anchors = tables.event_anchors(t["events"], sessions)
    front = window.front_fixed_ivs(pan, t["event_iv"], chains, anchors, sessions, int(p["iv"]["tau_min_sessions"]))
    ewo = window.window_table(pan, m, front, sessions, schema.EVENT_WINDOW_OBS.names)
    regs = regressors.regressor_table(t["events"], t["eps"], t["event_iv"], t["iv_daily"], ce, t["market_daily"],
                                      sessions, yahoo or {}, caps or {}, p["drivers"])
    em = window.measures_table(t["events"], t["event_iv"], pan, m, schema.EVENT_MEASURES.names, regs)
    smp = pan.events["sample"].to_numpy(object)
    rep = {
        "event_window_obs_rows": int(len(ewo)), "events_with_window": int(len(pan.events)),
        "eligible": {mm: {s: int((m["eligible"][mm] & (smp == s)).sum()) for s in ("daily", "mixed", "coarse")}
                     for mm in window.MEASURES},
        "ineligible_reason": {mm: dict(sorted(Counter(r for r, s in zip(m["reason"][mm], smp)
                                                      if r is not None and s == "daily").items()))
                              for mm in window.MEASURES},
        "baseline_ok": {s: int((m["base_ok"] & (smp == s)).sum()) for s in ("daily", "mixed", "coarse")},
        "baseline_sessions_daily": _q(m["n_sessions"][smp == "daily"]),
        "beta": _q(np.array(sorted({(sec, b) for sec, b in zip(pan.events["security_id"], m["beta"])
                                    if np.isfinite(b)}))[:, 1].astype(float)),
        "beta_n": _q(np.array(sorted({(sec, n) for sec, n in zip(pan.events["security_id"], m["beta_n"])}))[:, 1]
                     .astype(float)),
        "rhat": {k: {"rho": [round(float(x), 4) for x in v[0]], "flag": v[1]} for k, v in m["rhat"].items()},
        "front_fixed_interpolated_rows": int(front[1].sum()),
        "regressors": {c: int(em[c].notna().sum()) for c in regressors.COLUMNS},
        "regressors_daily_crush": {c: int(em.loc[_primary(t["events"], em), c].notna().sum())
                                   for c in regressors.COLUMNS},
        "vix_regime_daily": {k: int(v) for k, v in em.loc[(t["events"]["sample"] == "daily").to_numpy(),
                                                         "vix_regime"].value_counts().items()},
    }
    return {"event_window_obs": ewo, "event_measures": em, "report": rep}


def _primary(events: pd.DataFrame, em: pd.DataFrame) -> np.ndarray:
    """The rows of the primary sample (daily, eligible_crush); em is 1:1 with events, same order."""
    return ((events["sample"] == "daily").to_numpy() & em["eligible_crush"].to_numpy(bool))


def yahoo_inputs(p, security_ids: list[str]) -> tuple[dict, dict]:
    """({security_id: Yahoo rows}, {security_id: market cap on the rank date}), local files only:
    raw/yfinance/<symbol>.parquet and raw/yfinance/market_cap_<rank_date>.csv (ingest/run.py)."""
    raw = config.raw_dir()
    yahoo = {}
    for s in security_ids:
        path = raw / "yfinance" / f"{universe.yahoo_symbol(s)}.parquet"
        if path.exists():
            yahoo[s] = prices.load(universe.yahoo_symbol(s), raw)
    caps_df = pd.read_csv(raw / "yfinance" / f"market_cap_{p['universe']['rank_date']}.csv")
    caps = {s: float(c) for s, c in zip(caps_df["symbol"], caps_df["market_cap_yf"]) if pd.notna(c)}
    return yahoo, caps


def _q(a: np.ndarray) -> dict:
    a = a[np.isfinite(a)]
    if a.size == 0:
        return {"n": 0}
    return {"n": int(a.size), "min": float(a.min()), "p25": float(np.percentile(a, 25)),
            "median": float(np.median(a)), "p75": float(np.percentile(a, 75)), "max": float(a.max())}


def main(argv: list[str] | None = None) -> int:
    p = params_mod.load()
    sd = stage_dir(p)
    names = ("session", "events", "eps", "market_daily", "iv_daily", "event_iv", "chain_expiry")
    t = {n: store.read_table(sd / f"{n}.parquet", schema.REGISTRY[n]) for n in names}
    yahoo, caps = yahoo_inputs(p, sorted(set(t["events"]["security_id"])))
    out = build(p, t, yahoo, caps)
    commits = {"options": p["dolt"]["options_commit"], "earnings": p["dolt"]["earnings_commit"]}
    for name in ("event_window_obs", "event_measures"):
        table = schema.REGISTRY[name]
        store.write_table(out[name], table, sd / f"{name}.parquet", params_hash=p.params_hash, dolt_commits=commits)
        store.write_derived(out[name], table, DERIVED)
    (sd / "panel_report.json").write_text(json.dumps(out["report"], indent=2, sort_keys=True) + "\n")
    print(json.dumps(out["report"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
