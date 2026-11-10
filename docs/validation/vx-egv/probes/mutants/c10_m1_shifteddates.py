"""The Cboe VX* cross-check of our 30-day IV (ADR 0003 validation items 1 and 3), as committed aggregates.

    uv run --frozen python tools/vx_crosscheck.py            # compute; write data/derived/vx_crosscheck.json
    uv run --frozen python tools/vx_crosscheck.py --check    # recompute and compare with the committed file

The plan is ``docs/validation/vx-preregistration.md``; the decisions it left open are D1-D12 of
``docs/validation/vx-ledger.md``. The statistics are pure functions in ``earnings_vol.stats.vx_crosscheck``; this
script only reads and writes.

Inputs (only the committed file is public; everything else is local):

- ``$VOL_DATA_DIR/earnings-vol-study/raw/cboe/<SYM>.csv`` (``python -m earnings_vol.ingest.cboe``);
- ``data/derived/{iv_daily,session,session_snapshot,events,eps}.parquet`` (committed); ``iv_daily`` must be
  byte-identical to the stage copy at the current params hash;
- ``cache/stage/<params hash>/chain_expiry.parquet`` (the per-expiry ATM IVs, local), for the maturity of §5;
- ``volatility_history.iv_current`` from the private Dolt mirror ``cache/dolt_mirror/options`` at the pinned options
  commit, read with ``dolt sql -r csv`` from inside the mirror (never in a shared clone), filtered on ``date`` first,
  inside ``dolt.guard``; the extract is cached in ``cache/vx_crosscheck/`` (local).

Output: ``data/derived/vx_crosscheck.json``, aggregates only (ADR 0001 §7, data model §2.1): no VX* value per day or
per event, no ``iv_current`` value per day. ``tools/licensing/check_data_files.py`` checks its shape.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from earnings_vol import config, params as params_mod, schema, store
from earnings_vol.export import funnel
from earnings_vol.ingest import cboe, dolt
from earnings_vol.ingest.universe import VX_INDEX
from earnings_vol.measures import termstructure
from earnings_vol.stats import vx_crosscheck as vx

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "data/derived/vx_crosscheck.json"
PREREG = REPO / "docs/validation/vx-preregistration.md"
PREREG_SHA256 = "94b246039e4cbd4d679e4d7e567ee7a2f35ad7ab333f182e6498096a653351d6"
KIND = "vx_crosscheck"
VERSION = 1
NAMES = tuple(VX_INDEX)                      # AAPL, AMZN, GOOGL, GS, IBM
DOLT_BIN = os.environ.get("DOLT_BIN", str(Path.home() / ".local/bin/dolt"))


# --- small helpers -------------------------------------------------------------------------------------------

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rnd(x, nd: int = 4):
    """A float rounded for the JSON; NaN and inf become null."""
    if x is None:
        return None
    x = float(x)
    return round(x, nd) if np.isfinite(x) else None


def ci(values: np.ndarray, nd: int = 4) -> dict:
    lo, hi, dropped = vx.percentile_ci(values)
    return {"lo": rnd(lo, nd), "hi": rnd(hi, nd), "undefined_reps": dropped}


# --- inputs ----------------------------------------------------------------------------------------------------

def committed(name: str) -> pd.DataFrame:
    return store.read_table(REPO / f"data/derived/{name}.parquet", store.committed_schema(schema.REGISTRY[name]))


def stage_dir(p) -> Path:
    return config.cache_dir() / "stage" / p.params_hash[:16]


def check_inputs(p) -> dict:
    """The pre-registration is unchanged; the committed iv_daily is the stage's; chain_expiry is of these params."""
    if sha256(PREREG) != PREREG_SHA256:
        raise RuntimeError(f"{PREREG} changed after the download (a deviation the ledger must list)")
    st = stage_dir(p)
    iv_c, iv_s = sha256(REPO / "data/derived/iv_daily.parquet"), sha256(st / "iv_daily.parquet")
    if iv_c != iv_s:
        raise RuntimeError("data/derived/iv_daily.parquet differs from the stage copy at the current params hash")
    man = json.loads((st / "chain_expiry.manifest.json").read_text())
    if man["params_hash"] != p.params_hash or man["sha256"] != sha256(st / "chain_expiry.parquet"):
        raise RuntimeError("the staged chain_expiry is not the one of the current params")
    return {"iv_daily_sha256": iv_c, "chain_expiry_sha256": man["sha256"], "stage": st.name}


def cboe_inputs() -> tuple[dict[str, pd.DataFrame], dict]:
    raw = config.raw_dir() / "cboe"
    log = json.loads((raw / "fetch_log.json").read_text())
    frames, meta = {}, {}
    for sym in cboe.SYMBOLS:
        d = cboe.describe(raw / f"{sym}.csv")
        if d["sha256"] != log[sym]["sha256"]:
            raise RuntimeError(f"{sym}.csv changed since it was downloaded")
        frames[sym] = cboe.load(sym, raw)
        meta[sym] = {**d, "fetched_utc": log[sym]["fetched_utc"],
                     "url": cboe.url(sym)}
    return frames, meta


def dolt_csv(mirror: Path, sql: str) -> pd.DataFrame:
    """One checked read-only statement, run with `dolt sql -r csv` from inside the private mirror."""
    text = dolt.check_statement(sql)
    proc = subprocess.run([DOLT_BIN, "sql", "--disable-auto-gc", "-r", "csv", "-q", text], cwd=mirror,
                          capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"dolt sql failed ({proc.returncode}): {proc.stderr.decode(errors='replace')[:500]}")
    return pd.read_csv(io.BytesIO(proc.stdout), dtype=str, keep_default_na=False)


def volatility_history(p, first: date, last: date, log=print) -> tuple[pd.DataFrame, dict]:
    """iv_current of the five names, snapshot dates first..last, at the pinned options commit (cached)."""
    commit = dolt.check_commit(p["dolt"]["options_commit"])
    cache = config.cache_dir() / "vx_crosscheck"
    path = cache / f"volatility_history@{commit}.parquet"
    man_path = path.with_suffix(".manifest.json")
    if path.exists() and man_path.exists():
        man = json.loads(man_path.read_text())
        if man.get("first") == str(first) and man.get("last") == str(last) and man.get("sha256") == sha256(path):
            return pd.read_parquet(path), man
    mirror = config.cache_dir() / "dolt_mirror" / "options"
    shared = config.dolt_repo("options")
    t0 = time.perf_counter()
    queries = []
    with dolt.guard(shared, mirror):
        n = dolt_csv(mirror, f"SELECT COUNT(*) AS n FROM dolt_log WHERE commit_hash = '{commit}'")
        if int(n["n"].iloc[0]) != 1:
            raise RuntimeError(f"commit {commit} is not in the options mirror")
        parts = []
        for y in range(first.year, last.year + 1):
            lo, hi = max(first, date(y, 1, 1)), min(last, date(y, 12, 31))
            sql = (f"SELECT `date`, act_symbol, iv_current FROM {dolt.as_of('volatility_history', commit)} "
                   f"WHERE `date` BETWEEN '{lo}' AND '{hi}' AND act_symbol IN {dolt.sql_list(NAMES)}")
            parts.append(dolt_csv(mirror, sql))
            queries.append(sql)
    df = pd.concat(parts, ignore_index=True)
    out = pd.DataFrame({"date": [date.fromisoformat(d) for d in df["date"]],
                        "act_symbol": df["act_symbol"].astype(str),
                        "iv_current": pd.to_numeric(df["iv_current"].replace({"": None}), errors="raise")
                        .astype("float64")})
    if out.duplicated(["date", "act_symbol"]).any():
        raise RuntimeError("volatility_history has two rows for one (date, act_symbol)")
    cache.mkdir(parents=True, exist_ok=True)
    out.to_parquet(path, index=False)
    man = {"commit": commit, "first": str(first), "last": str(last), "rows": int(len(out)),
           "rows_with_iv_current": int(out["iv_current"].notna().sum()), "queries": queries,
           "seconds": round(time.perf_counter() - t0, 2), "sha256": sha256(path),
           "extracted_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "shared_clone_unchanged": True}
    man_path.write_text(json.dumps(man, indent=2) + "\n")
    log(f"volatility_history: {len(out)} rows in {man['seconds']} s (shared clone unchanged)")
    return out, man


# --- the computation ---------------------------------------------------------------------------------------------

def bar_i_ii(ch_by_name: dict[str, pd.DataFrame], w0: int, n: int, counts: dict[int, np.ndarray],
             x: str = "d_ours", y: str = "d_vx") -> dict:
    """Bars i and ii (or the same statistics for another pair) per name and pooled, with block intervals."""
    out = {}
    stacked = []
    for key, ch in list(ch_by_name.items()) + [("pooled", None)]:
        if key == "pooled":
            ch = pd.concat(stacked, ignore_index=True)
        else:
            stacked.append(ch.assign(end=(ch["end"] - w0 + 7 * (len(stacked) + 1)) % n + w0))
        pos = ch["end"].to_numpy() - w0
        if len(pos) and (pos.min() < 0 or pos.max() >= n):
            raise ValueError("a change outside the bootstrap window")
        sums = vx.session_sums(pos, ch[x].to_numpy(), ch[y].to_numpy(), n)
        pt = vx.moment_stats(sums)
        row = {"n": int(len(ch)), "r": rnd(pt["r"][0]), "slope": rnd(pt["slope"][0]),
               "reverse_slope": rnd(pt["reverse"][0]),
               "reverse_slope_reciprocal": rnd(1 / pt["reverse"][0]) if pt["reverse"][0] else None}
        for block, c in counts.items():
            b = vx.moment_stats(sums, c)
            with np.errstate(divide="ignore"):
                recip = 1 / b["reverse"]
            row[f"block{block}"] = {"r": ci(b["r"]), "slope": ci(b["slope"]), "reverse_slope": ci(b["reverse"]),
                                    "reverse_slope_reciprocal": ci(recip)}
        out[key] = row
    return out


def changes_by_name(grids: dict, lag: int = 0, a: str = "ours", b: str = "vx") -> dict[str, pd.DataFrame]:
    return {nm: vx.matched_changes(g[a], vx.shift(g[b], lag) if lag else g[b]) for nm, g in grids.items()}


def level_block(grids: dict, sessions: list[date], w0: int, n: int, counts: dict[int, np.ndarray],
                a: str, b: str, by_year: bool) -> dict:
    """The level spread 100 × (b − a) in vol points on the days where both exist, per name and pooled."""
    out, stack_s, stack_p = {}, [], []
    for nm, g in list(grids.items()) + [("pooled", None)]:
        if nm == "pooled":
            if by_year:
                break                                # bar iii has no pooled verdict
            s, pos, yrs = np.concatenate(stack_s), np.concatenate(stack_p), None
        else:
            with np.errstate(invalid="ignore"):
                ok = np.isfinite(g[a]) & np.isfinite(g[b]) & (g[a] > 0) & (g[b] > 0)
            idx = np.flatnonzero(ok)
            s, pos = 100 * (g[b][idx] - g[a][idx]), idx - w0
            yrs = np.array([sessions[i].year for i in idx]) if by_year else None
            stack_s.append(s)
            stack_p.append(pos)
        pt = vx.spread_stats(s, yrs)
        row = {"n_days": int(len(s)), "median_spread": rnd(pt["median"][0], 3),
               "share_above": rnd(pt["share_above"][0])}
        boots = {blk: vx.spread_stats(s, yrs, pos, c) for blk, c in counts.items()}
        for blk, bt in boots.items():
            row[f"block{blk}"] = {"median_spread": ci(bt["median"], 3), "share_above": ci(bt["share_above"])}
        if by_year:
            mad = float(pt["max_abs_dev"][0])
            row["years"] = {str(yv): {"n_days": int((yrs == yv).sum()), "median_spread": rnd(pt["years"][yv][0], 3),
                                      "block20": ci(boots[vx.BLOCK_PRIMARY]["years"][yv], 3)}
                            for yv in sorted(pt["years"])}
            row["max_abs_dev"] = rnd(mad, 3)
            for blk, bt in boots.items():
                row[f"block{blk}"]["max_abs_dev"] = ci(bt["max_abs_dev"], 3)
            row["verdict"] = vx.verdict_bar_iii(mad)
        out[nm] = row
    return out


def crush_events(p, grids: dict, pos_of: dict[date, int]) -> tuple[np.ndarray, np.ndarray, dict]:
    """Bar iv's events: the study's primary sample (export.funnel), five names; Δln VX and Δln ours, day −1 → 0."""
    events, iv, eps, session = (committed(n) for n in ("events", "iv_daily", "eps", "session"))
    _, prim = funnel.run_steps(events, iv, eps, session, p)
    five = prim[prim["security_id"].isin(NAMES)].sort_values("event_id")
    d_vx, d_ours, dropped = [], [], []
    for e in five.itertuples(index=False):
        g = grids[e.security_id]
        i0, im1 = pos_of[e.day0_session], pos_of[e.day_m1_session]
        vals = (g["ours"][im1], g["ours"][i0], g["vx"][im1], g["vx"][i0])
        if not all(np.isfinite(v) and v > 0 for v in vals):
            dropped.append(e.event_id)
            continue
        d_ours.append(np.log(vals[1] / vals[0]))
        d_vx.append(np.log(vals[3] / vals[2]))
    info = {"n_primary_sample": int(len(prim)), "n_events_five_names": int(len(five)),
            "n_by_name": {k: int(v) for k, v in five["security_id"].value_counts().sort_index().items()},
            "n_dropped_missing_value": len(dropped),
            "timing_status_counts": {k: int(v) for k, v in five["timing_status"].value_counts().items() if v},
            "day0_first": str(five["day0_session"].min()), "day0_last": str(five["day0_session"].max())}
    return np.array(d_vx), np.array(d_ours), info


def maturity(grids: dict, p, sessions: list[date], w0: int, n: int, counts20: np.ndarray) -> dict:
    """§5.2: our blind ATM IV at each horizon against iv_current; D10."""
    ce = pd.read_parquet(stage_dir(p) / "chain_expiry.parquet")
    ce = ce[ce["security_id"].isin(NAMES)]
    usable = ce[(ce["status"] == "ok") & (ce["tau_sessions"] >= int(p["iv"]["tau_min_sessions"]))
                & ce["w_atm"].notna()]
    pos_of = {d: i for i, d in enumerate(sessions)}
    max_extrap = int(p["iv"]["cm30_max_extrap_sessions"])
    hgrid = {nm: {h: np.full(len(sessions), np.nan) for h in vx.HORIZONS} for nm in NAMES}
    n_days_with_expiries = 0
    for (sid, d), grp in usable.groupby(["security_id", "session_date"]):
        n_days_with_expiries += 1
        ex = [termstructure.Expiry(r.expiration, int(r.tau_sessions), float(r.w_atm), float(r.iv_atm), False)
              for r in grp.itertuples(index=False)]
        for h in vx.HORIZONS:
            v = vx.iv_at_horizon(ex, h, max_extrap)
            if v is not None:
                hgrid[sid][h][pos_of[d]] = v
    # the check of D10: at 21 sessions this is cm30_blind_iv, day by day
    for nm in NAMES:
        a, b = hgrid[nm][21], grids[nm]["ours"]
        if not (np.array_equal(np.isfinite(a), np.isfinite(b)) and np.allclose(a[np.isfinite(a)], b[np.isfinite(b)],
                                                                                 rtol=0, atol=1e-12)):
            raise RuntimeError(f"{nm}: the 21-session interpolation does not reproduce cm30_blind_iv")
    coverage = {str(h): int(sum(np.isfinite(hgrid[nm][h]).sum() for nm in NAMES)) for h in vx.HORIZONS}
    measurable = [h for h in vx.HORIZONS if coverage[str(h)] > 0]
    # common days: every measurable horizon and iv_current there (D10)
    diffs = {h: [] for h in measurable}
    diffs_all = {h: [] for h in measurable}
    per_name = {}
    n_common = 0
    for nm in NAMES:
        ivc = grids[nm]["ivc"]
        common = np.isfinite(ivc) & np.all([np.isfinite(hgrid[nm][h]) for h in measurable], axis=0)
        n_common += int(common.sum())
        med_nm = {}
        for h in measurable:
            dd = 100 * (ivc - hgrid[nm][h])
            diffs[h].append(np.abs(dd[common]))
            diffs_all[h].append(np.abs(dd[np.isfinite(dd)]))
            med_nm[h] = float(np.median(np.abs(dd[common]))) if common.any() else float("nan")
        per_name[nm] = {"n_common_days": int(common.sum()),
                        "median_abs_diff": {str(h): rnd(med_nm[h], 3) for h in measurable},
                        "identification": vx.identify_maturity(med_nm)}
    med = {h: float(np.median(np.concatenate(diffs[h]))) for h in measurable}
    ident = vx.identify_maturity({**med, **{h: float("nan") for h in vx.HORIZONS if h not in measurable}})
    # change correlation of iv_current with our IV at each measurable horizon (primary changes, all days)
    corr = {}
    for h in measurable:
        hg = {nm: {"ours": hgrid[nm][h], "ivc": grids[nm]["ivc"]} for nm in NAMES}
        ch = {nm: vx.primary(c) for nm, c in changes_by_name(hg, 0, "ours", "ivc").items()}
        pooled = bar_i_ii(ch, w0, n, {vx.BLOCK_PRIMARY: counts20})["pooled"]
        corr[str(h)] = {"n": pooled["n"], "r": pooled["r"], "block20": pooled["block20"]["r"]}
    return {
        "per_expiry_atm_ivs": {"source": f"cache/stage/{stage_dir(p).name}/chain_expiry.parquet (local)",
                               "sessions_with_usable_expiries": n_days_with_expiries,
                               "snapshot_ok_sessions": int(sum(int(np.isfinite(grids[nm]['snap']).sum())
                                                               for nm in NAMES))},
        "horizons": list(vx.HORIZONS),
        "interpolation": ("our blind rule (termstructure.interpolate: linear in total variance, at most "
                          f"{max_extrap} sessions of extrapolation; one expiry: flat sigma); at 21 sessions it "
                          "equals cm30_blind_iv on every day"),
        "coverage_days": coverage,
        "not_measurable": [h for h in vx.HORIZONS if h not in measurable],
        "n_common_days": n_common,
        "median_abs_diff_vol_points": {str(h): rnd(med[h], 3) for h in measurable},
        "identification": ident,
        "change_correlation": {
            "identified": corr.get(str(ident["argmin"])) if ident["argmin"] is not None else None,
            "label_other_horizons": "exploratory, not pre-registered",
            "by_horizon": corr},
        "sensitivity_all_days": {"label": "exploratory, not pre-registered: each horizon on all its own days",
                                 "median_abs_diff_vol_points": {
                                     str(h): rnd(float(np.median(np.concatenate(diffs_all[h]))), 3)
                                     for h in measurable},
                                 "n_days": {str(h): int(sum(len(x) for x in diffs_all[h])) for h in measurable}},
        "per_name": {"label": "exploratory, not pre-registered", **per_name},
    }


def compute(log=print) -> dict:
    p = params_mod.load()
    inputs = check_inputs(p)
    frames, cboe_meta = cboe_inputs()
    session = committed("session")
    sessions = sorted(session["session_date"].tolist())
    pos_of = {d: i for i, d in enumerate(sessions)}
    iv = committed("iv_daily")
    ss = committed("session_snapshot")

    # the grids: ours, VX (close / 100), the snapshot map and iv_current, per name
    # the bootstrap axis (D2): every session of our series' table, 2020-01-02 to 2026-10-26, whether or not a
    # value exists on it (2020-01-02 has no snapshot)
    first_ours = min(iv.loc[iv["security_id"].isin(NAMES), "session_date"])
    last_ours = max(iv.loc[iv["security_id"].isin(NAMES), "session_date"])
    snap = ss[ss["security_id"].isin(NAMES) & (ss["snapshot_status"] == "ok")]
    vh, vh_meta = volatility_history(p, min(snap["snapshot_date"]), max(snap["snapshot_date"]), log=log)
    grids = {}
    for nm in NAMES:
        mine = iv[iv["security_id"] == nm]
        f = frames[VX_INDEX[nm]]
        f = f[(f["date"] >= sessions[0]) & (f["date"] <= sessions[-1])]
        s_nm = snap[snap["security_id"] == nm]
        vh_nm = vh[vh["act_symbol"] == nm]
        ivc_by_snap = dict(zip(vh_nm["date"], vh_nm["iv_current"]))
        ivc = [ivc_by_snap.get(d) for d in s_nm["snapshot_date"]]
        grids[nm] = {"ours": vx.on_grid(mine["session_date"], mine["cm30_blind_iv"], sessions),
                     "vx": vx.on_grid(f["date"], f["close"] / 100.0, sessions),
                     "snap": vx.on_grid(s_nm["session_date"], np.ones(len(s_nm)), sessions),
                     "ivc": vx.on_grid(s_nm["session_date"], [np.nan if v is None else v for v in ivc], sessions)}
    w0, w1 = pos_of[first_ours], pos_of[last_ours]
    n = w1 - w0 + 1
    for g in grids.values():                       # the analysis window is our series' span
        for k in ("ours", "snap", "ivc"):
            g[k][:w0] = np.nan
            g[k][w1 + 1:] = np.nan
    counts = {blk: vx.block_counts(n, blk, vx.REPS, np.random.default_rng(vx.SEED))
              for blk in (vx.BLOCK_PRIMARY, vx.BLOCK_SENSITIVITY)}
    c20 = counts[vx.BLOCK_PRIMARY]

    # bars i and ii, lag 0, primary changes; the secondary changes; the lags
    ch0 = changes_by_name(grids)
    prim = {nm: vx.primary(c) for nm, c in ch0.items()}
    sec = {nm: vx.secondary(c) for nm, c in ch0.items()}
    bars = bar_i_ii(prim, w0, n, counts)
    for row in bars.values():
        row["bar_i_verdict"] = vx.verdict_bar_i(row["r"])
        row["bar_ii_interval_holds_1"] = {f"block{b}": vx.holds(row[f"block{b}"]["slope"]["lo"],
                                                                row[f"block{b}"]["slope"]["hi"])
                                          for b in counts}
        row["exploratory_slope_in_adr_band"] = bool(vx.ADR_SLOPE_BAND[0] <= row["slope"] <= vx.ADR_SLOPE_BAND[1])
    secondary = bar_i_ii(sec, w0, n, counts)
    for nm, row in secondary.items():
        gaps = (pd.concat(list(sec.values())) if nm == "pooled" else sec[nm])["gap"]
        row["gaps"] = {str(k): int(v) for k, v in gaps.value_counts().sort_index().items()}
    lag_r = {}
    lags = {}
    for lag in vx.LAGS:
        chl = {nm: vx.primary(c) for nm, c in changes_by_name(grids, lag).items()}
        pooled = bar_i_ii(chl, w0, n, counts)["pooled"]
        lag_r[lag] = pooled["r"]
        lags[f"{lag:+d}" if lag else "0"] = {"n": pooled["n"], "r": pooled["r"],
                                             "block20": pooled["block20"]["r"], "block60": pooled["block60"]["r"]}
    finding = vx.lag_finding(lag_r)

    # bar iii
    level = level_block(grids, sessions, w0, n, counts, "ours", "vx", by_year=True)

    # bar iv
    d_vx, d_ours, ev_info = crush_events(p, grids, pos_of)
    ratio = vx.crush_ratio(d_vx, d_ours)
    boot = vx.event_bootstrap_ratio(d_vx, d_ours, vx.REPS, np.random.default_rng(vx.SEED))
    provisional = vx.bar_iv_provisional(ev_info["timing_status_counts"])
    per_name_n = sorted(ev_info["n_by_name"].values())

    # §5
    vh_cmp_vx = bar_i_ii({nm: vx.primary(c) for nm, c in changes_by_name(grids, 0, "ivc", "vx").items()}, w0, n,
                         counts, x="d_ours", y="d_vx")
    vh_cmp_ours = bar_i_ii({nm: vx.primary(c) for nm, c in changes_by_name(grids, 0, "ours", "ivc").items()}, w0, n,
                           counts, x="d_ours", y="d_vx")
    vh_lvl_vx = level_block(grids, sessions, w0, n, counts, "ivc", "vx", by_year=False)
    vh_lvl_ours = level_block(grids, sessions, w0, n, counts, "ours", "ivc", by_year=False)
    mat = maturity(grids, p, sessions, w0, n, c20)

    def keep_r(block: dict) -> dict:
        return {k: {"n": v["n"], "r": v["r"], "block20": v["block20"]["r"], "block60": v["block60"]["r"]}
                for k, v in block.items()}

    pooled_i = bars["pooled"]
    return {
        "kind": KIND,
        "version": VERSION,
        "title": "Cboe VX* cross-check of cm30_blind_iv (ADR 0003 validation items 1 and 3)",
        "preregistration": {"path": "docs/validation/vx-preregistration.md", "sha256": PREREG_SHA256,
                            "ledger": "docs/validation/vx-ledger.md"},
        "data_policy": ("aggregates only: no VX* value per day or per event and no volatility_history value per day "
                        "(ADR 0001 §7, data model §2.1)"),
        "provisional": provisional,
        "names": [{"security_id": nm, "vx_index": VX_INDEX[nm]} for nm in NAMES],
        "inputs": {
            "cboe": cboe_meta,
            "ours": "data/derived/iv_daily.parquet cm30_blind_iv (decimal)",
            "iv_daily_sha256": inputs["iv_daily_sha256"],
            "events_sha256": sha256(REPO / "data/derived/events.parquet"),   # bar iv's events and timing labels
            "params_hash": p.params_hash,
            "options_commit": p["dolt"]["options_commit"],
            "earnings_commit": p["dolt"]["earnings_commit"],
            "chain_expiry_sha256": inputs["chain_expiry_sha256"],
            "volatility_history": {"source": "post-no-preference/options volatility_history.iv_current, read in the "
                                              "private mirror", "commit": vh_meta["commit"],
                                   "snapshot_dates": [vh_meta["first"], vh_meta["last"]], "rows": vh_meta["rows"],
                                   "rows_with_iv_current": vh_meta["rows_with_iv_current"]},
        },
        "window": {"first": str(first_ours), "last": str(last_ours), "n_sessions": n},
        "bootstrap": {"seed": vx.SEED, "reps": vx.REPS, "blocks": [vx.BLOCK_PRIMARY, vx.BLOCK_SENSITIVITY],
                      "primary_block": vx.BLOCK_PRIMARY, "interval": "percentile 2.5% and 97.5% (D1)",
                      "scheme": "moving blocks over the session axis, not circular; one draw per block length, "
                                "shared by every name and the pooled statistics (D2)",
                      "events": "bar iv: events resampled with replacement, 10,000 reps, the same seed"},
        "bar_i": {"statistic": "Pearson r of primary dln VX on dln ours (lag 0)", "bar": vx.BAR_I_MIN_R,
                  "rule": "pass when r > 0.8",
                  "per_name": {nm: {"n": bars[nm]["n"], "r": bars[nm]["r"], "block20": bars[nm]["block20"]["r"],
                                    "block60": bars[nm]["block60"]["r"], "verdict": bars[nm]["bar_i_verdict"]}
                               for nm in NAMES},
                  "pooled": {"n": pooled_i["n"], "r": pooled_i["r"], "block20": pooled_i["block20"]["r"],
                             "block60": pooled_i["block60"]["r"], "verdict": pooled_i["bar_i_verdict"]},
                  "names_passing": int(sum(bars[nm]["bar_i_verdict"] == "pass" for nm in NAMES))},
        "bar_ii": {"statistic": "OLS slope of primary dln VX on dln ours, and the reverse slope", "bar": "about 1",
                   "rule": "descriptive: does the 95% interval hold 1",
                   "per_name": {nm: {k: bars[nm][k] for k in ("n", "slope", "reverse_slope",
                                                             "reverse_slope_reciprocal", "bar_ii_interval_holds_1")}
                                | {f"block{b}": {k: bars[nm][f"block{b}"][k] for k in
                                                 ("slope", "reverse_slope", "reverse_slope_reciprocal")}
                                   for b in counts}
                                for nm in NAMES + ("pooled",)},
                   "exploratory_adr_band": {"label": "exploratory, not pre-registered (D12): ADR 0003's 'How we'll "
                                                     "know it's wrong' reads a slope outside [0.8, 1.2] as a failure",
                                            "band": list(vx.ADR_SLOPE_BAND),
                                            "slope_in_band": {nm: bars[nm]["exploratory_slope_in_adr_band"]
                                                              for nm in NAMES + ("pooled",)}}},
        "bar_iii": {"statistic": "level spread VX close − 100 × ours, vol points, every session with both values",
                    "bar": "stable, no breaks", "tolerance_vol_points": vx.BAR_III_TOLERANCE_VOL_POINTS,
                    "rule": "pass when every calendar year's median is within 2.0 vol points of the all-days median",
                    "per_name": level,
                    "names_passing": int(sum(level[nm]["verdict"] == "pass" for nm in NAMES))},
        "bar_iv": {"statistic": "R = mean dln VX(−1→0) / mean dln ours(−1→0), primary-sample events of the five names",
                   "bar": list(vx.BAR_IV_RANGE), "rule": "pass when 0.8 ≤ R ≤ 1.2",
                   "events": ev_info, "n": int(len(d_vx)),
                   "mean_dln_vx": rnd(np.mean(d_vx)), "mean_dln_ours": rnd(np.mean(d_ours)),
                   "ratio": rnd(ratio), "events_bootstrap": ci(boot), "verdict": vx.verdict_bar_iv(ratio),
                   "provisional": provisional,
                   "per_name": f"not computed: {per_name_n[0]} to {per_name_n[-1]} events per name; R is pooled "
                               "only, and a per-name aggregate over fewer than 10 events would count as per-event data "
                               "(D8)"},
        "alignment_falsifier": {"statistic": "pooled r of primary changes with Cboe moved by L sessions",
                                "lags": lags, **finding,
                                "note": "the bars are judged at lag 0 whatever this shows"},
        "secondary": {"statistic": "bars i and ii on changes over gaps of more than one session (no verdict, D11)",
                      **secondary},
        "volatility_history": {
            "label": "third check (pre-registration §5); changes no verdict",
            "iv_current_vs_vx": {"r_primary_changes": keep_r(vh_cmp_vx),
                                 "spread_vx_minus_iv_current": vh_lvl_vx},
            "iv_current_vs_ours": {"r_primary_changes": keep_r(vh_cmp_ours),
                                   "spread_iv_current_minus_ours": vh_lvl_ours},
            "maturity": mat,
        },
    }


def dumps(obj: dict) -> str:
    return json.dumps(obj, indent=1, ensure_ascii=False, sort_keys=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="recompute and compare with the committed file")
    args = ap.parse_args(argv)
    t0 = time.perf_counter()
    text = dumps(compute())
    if args.check:
        if not OUT.exists() or OUT.read_text() != text:
            print(f"FAIL: {OUT.relative_to(REPO)} differs from a fresh computation", file=sys.stderr)
            return 1
        print(f"ok: {OUT.relative_to(REPO)} equals a fresh computation ({time.perf_counter() - t0:.0f} s)")
        return 0
    OUT.write_text(text)
    print(f"wrote {OUT.relative_to(REPO)} ({len(text)} bytes, {time.perf_counter() - t0:.0f} s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
