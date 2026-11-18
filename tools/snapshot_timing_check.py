"""Run the 2026 snapshot-timing check once (plan: docs/validation/snapshot-timing/preregistration.md §6-§12).

    uv run python -I tools/snapshot_timing_check.py      # writes docs/validation/snapshot-timing/aggregate.json

Inputs, all local and fixed before the run: the stage cache of the current params (the stats layer's frame,
iv_daily, chain_expiry, results), the frozen timing map (timing_map.json, whose params hash must be the current one),
the Yahoo prices of the map, and for D1 the Cboe VX* files of the VX check. The output holds aggregates, counts and
dates only: no per-day or per-company level, price or VX value, and no event id.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from earnings_vol import params as params_mod, store
from earnings_vol.events.run import stage_dir
from earnings_vol.stats import regression, run as stats_run, snapshot_timing as stm, vx_crosscheck as vx

REPO = Path(__file__).resolve().parents[1]
DOCS = REPO / "docs/validation/snapshot-timing"
OUT = DOCS / "aggregate.json"
PLAN = DOCS / "preregistration.md"
MAP = DOCS / "timing_map.json"

# §10: the lines, as the report prints them (checked against the results rows below)
LINES = {"H1": 0.0112, "H2": 0.0170, "H3": 0.0234, "H4": 0.0112}
LINE_ROWS = {"H1": ("crush_cm30", "twoway_date_t"), "H2": ("runup", "twoway_season_t"),
             "H3": ("persist_10", "twoway_season_t"), "H4": ("dsigma_d", "twoway_date_t")}
# §4: the sample sizes the plan was written for; a different n stops the run (it would be a deviation)
N_PLAN = {"H1": 349, "H2": 358, "H3": 331, "H4": 263}
SHIFT = {"H1": ("cm30", "crush"), "H2": ("cm30", "runup"), "H3": ("cm30", "persist_10"), "H4": ("sigma", "dsigma_d")}
BOOT_REPS, BOOT_SEED = 9999, 20261118  # §7: the wild cluster bootstrap, fixed before the run
REL = {"s_m2": -2, "s_m1": -1, "s_0": 0, "s_p1": 1, "s_p10": 10}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rnd(x, nd: int = 6):
    return None if x is None or not np.isfinite(x) else round(float(x), nd)


def tool(name: str):
    spec = importlib.util.spec_from_file_location(name, REPO / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- inputs -------------------------------------------------------------------------------------------------

def timing_map(p) -> tuple:
    m = json.loads(MAP.read_text())
    if m["inputs"]["params_hash"] != p.params_hash:
        raise RuntimeError("timing_map.json was built on other params; rebuild it (a deviation, plan §13 item 4)")
    cls_of = {date.fromisoformat(d): c for c, key in (("off", "off_dates"), ("late", "late_dates"),
                                                      ("unknown", "unknown_dates")) for d in m[key]}

    def cls(s) -> str:
        # a Timestamp or datetime never equals a date key, so it would read as close without a word: refuse it
        if type(s) is not date:
            raise TypeError(f"session {s!r} is a {type(s).__name__}, not a datetime.date")
        return cls_of.get(s, "close")
    return cls, m


def event_frame(f, rows: np.ndarray) -> pd.DataFrame:
    """event_id, firm, season and the sessions of rel days -2, -1, 0, +1, +10 for the Frame rows."""
    from earnings_vol.panel import abnormal
    dates = f.sessions.dates
    out = pd.DataFrame({"event_id": f.ev["event_id"].to_numpy(object)[rows],
                        "firm": f.ev["security_id"].to_numpy(object)[rows],
                        "season": f.ev["season"].to_numpy(object)[rows], "row": rows})
    for col, rel in REL.items():
        out[col] = [dates[int(i)] for i in f.sess[rows, abnormal.col(rel)]]
    return out


def cm30_levels(iv: pd.DataFrame) -> dict:
    ok = iv[(iv["snapshot_status"] == "ok") & (iv["cm30_iv"] > 0)]
    return dict(zip(zip(ok["security_id"], ok["session_date"]), np.log(ok["cm30_iv"].to_numpy(float))))


def sigma_levels(st: Path, iv: pd.DataFrame, ev: pd.DataFrame) -> dict:
    """lv[(event_id, session)] = 1/2 ln sigma_d^2 between the event's expiry pair (E's pair at day -1, as
    measures/event_iv.py holds it), on days -2 .. +1."""
    daily = iv.set_index(["security_id", "session_date"])
    want = defaultdict(set)
    pair = {}
    for r in ev.itertuples(index=False):
        m1 = daily.loc[(r.firm, r.s_m1)]
        if m1["next_event_id"] != r.event_id or pd.isna(m1["ev_exp1"]) or pd.isna(m1["ev_exp2"]):
            continue
        pair[r.event_id] = (r.firm, m1["ev_exp1"], m1["ev_exp2"])
        for s in (r.s_m2, r.s_m1, r.s_0, r.s_p1):
            want[r.firm].add(s)
    ce = pd.read_parquet(st / "chain_expiry.parquet",
                         columns=["security_id", "session_date", "expiration", "tau_sessions", "w_atm", "status"])
    ce = ce[(ce["status"] == "ok") & ce["security_id"].isin(list(want))]
    ce = ce[[d in want[s] for s, d in zip(ce["security_id"], ce["session_date"])]]
    rows = {(s, d, e): (w, t) for s, d, e, w, t in zip(ce["security_id"], ce["session_date"], ce["expiration"],
                                                       ce["w_atm"], ce["tau_sessions"])}
    ok = set(zip(iv.loc[iv["snapshot_status"] == "ok", "security_id"],
                 iv.loc[iv["snapshot_status"] == "ok", "session_date"]))
    lv = {}
    for r in ev.itertuples(index=False):
        if r.event_id not in pair:
            continue
        sid, e1, e2 = pair[r.event_id]
        for s in (r.s_m2, r.s_m1, r.s_0, r.s_p1):
            a, b = rows.get((sid, s, e1)), rows.get((sid, s, e2))
            if (sid, s) not in ok or a is None or b is None or b[1] == a[1]:
                continue
            v = (b[0] - a[0]) / (b[1] - a[1])
            if v > 0:
                lv[(r.event_id, s)] = 0.5 * float(np.log(v))
    return lv


def near_event_set(events: pd.DataFrame, sessions: list[date]) -> set:
    idx = {d: i for i, d in enumerate(sessions)}
    out = set()
    for sid, d0 in zip(events["security_id"], events["day0_session"]):
        if d0 is None or pd.isna(d0) or d0 not in idx:
            continue
        i = idx[d0]
        out.update((sid, sessions[j]) for j in range(max(0, i - 2), min(len(sessions), i + 3)))
    return out


# --- the counts of §4 and §9 ------------------------------------------------------------------------------

def counts(f, ev: pd.DataFrame, cls, measure: str) -> dict:
    """k0, km1, k10 and s_sum for one measure's events; late sessions count with an error of 0 (plan §5a)."""
    c = lambda col, k: int(sum(cls(s) == k for s in ev[col]))  # noqa: E731
    out = {"n": int(len(ev)), "k0": c("s_0", "off"), "km1": c("s_m1", "off"), "k10": c("s_p10", "off"),
           "late_m1": c("s_m1", "late"), "late_0": c("s_0", "late"), "late_p10": c("s_p10", "late"),
           "unknown_m1": c("s_m1", "unknown"), "unknown_0": c("s_0", "unknown"),
           "unknown_p10": c("s_p10", "unknown"), "both_off": int(sum(cls(a) == "off" and cls(b) == "off"
                                                                     for a, b in zip(ev["s_m1"], ev["s_0"])))}
    if measure in ("runup", "persist_10"):
        dates = f.sessions.dates
        shares, late_sessions, late_events = [], 0, 0
        for i in ev["row"]:
            b = [dates[int(t)] for t in f.sess[i][f.in_baseline[i]]]
            cl = [cls(s) for s in b]
            shares.append(sum(x == "off" for x in cl) / len(b))
            nl = sum(x == "late" for x in cl)
            late_sessions += nl
            late_events += nl > 0
        out.update(s_sum=float(np.sum(shares)), baseline_sessions_late=int(late_sessions),
                   baseline_events_with_late=int(late_events),
                   baseline_events_with_off=int(sum(s > 0 for s in shares)))
    return out


# --- §6 ordering -----------------------------------------------------------------------------------------

def ordering(st: Path, ev: pd.DataFrame, cls) -> dict:
    need = {(r.firm, s) for r in ev.itertuples(index=False) for s in (r.s_m1, r.s_0)}
    sp = tool("snapshot_timing_map").spots(st, keep=lambda sid, d: (sid, d) in need)
    S = {(a, b): v for a, b, v in zip(sp["security_id"], sp["session_date"], sp["spot"])}
    C = {(a, b): v for a, b, v in zip(sp["security_id"], sp["session_date"], sp["close"])}
    Op = {(a, b): v for a, b, v in zip(sp["security_id"], sp["session_date"], sp["open"])}
    rows = []
    for r in ev.itertuples(index=False):
        m1, d0 = (r.firm, r.s_m1), (r.firm, r.s_0)
        if m1 not in S or d0 not in S or not np.isfinite(Op.get(d0, np.nan)):
            continue
        c1 = C[m1]
        rows.append({"event_id": r.event_id, "day0": r.s_0.isoformat(), "cls_m1": cls(r.s_m1), "cls_0": cls(r.s_0),
                     "g": np.log(Op[d0] / c1), "pre": np.log(S[m1] / c1), "post": np.log(S[d0] / c1),
                     "ret0": np.log(C[d0] / c1)})
    o = pd.DataFrame(rows)
    out = {"n_events_with_prices": int(len(o))}

    def slope(sub, y):
        if len(sub) < 3:
            return None
        t = stm.ordering_slope(sub[y], sub["g"], sub["day0"])
        return {k: rnd(t[k]) for k in ("estimate", "se", "ci_lo", "ci_hi")} | {"n": int(len(sub)),
                                                                               "clusters": int(sub["day0"].nunique())}

    big = o["g"].abs() >= 0.03
    flag1 = big & (o["pre"] / o["g"] >= 0.5)
    flag2 = big & (o["post"] / o["g"] <= 0.25) & (o["ret0"] / o["g"] >= 0.5)
    for name, col, y, flag in (("O1", "cls_m1", "pre", flag1), ("O2", "cls_0", "post", flag2)):
        grp = {}
        for k in ("off", "close"):
            sel = o[col] == k
            grp[k] = {"slope": slope(o[sel], y), "n_big_gap": int((sel & big).sum()),
                      "n_flagged": int((sel & flag).sum())}
        out[name] = grp
    return out


# --- §12 descriptive -------------------------------------------------------------------------------------

def d1_vx(cls) -> dict:
    vxt = tool("vx_crosscheck")
    frames, _ = vxt.cboe_inputs()
    sessions = sorted(vxt.committed("session")["session_date"].tolist())
    iv = vxt.committed("iv_daily")
    names = iv["security_id"].isin(vxt.NAMES)
    first, last = min(iv.loc[names, "session_date"]), max(iv.loc[names, "session_date"])
    pos = {d: i for i, d in enumerate(sessions)}
    w0, w1 = pos[first], pos[last]
    groups = {"close_close_2020_2025": [], "close_close_2026": [], "off_end_2026": []}
    for nm in vxt.NAMES:
        mine = iv[iv["security_id"] == nm]
        fr = frames[vxt.VX_INDEX[nm]]
        fr = fr[(fr["date"] >= sessions[0]) & (fr["date"] <= sessions[-1])]
        o = vx.on_grid(mine["session_date"], mine["cm30_blind_iv"], sessions)
        v = vx.on_grid(fr["date"], fr["close"] / 100.0, sessions)
        o[:w0] = np.nan
        o[w1 + 1:] = np.nan
        ch = vx.primary(vx.matched_changes(o, v))
        for a, b, x, y in zip(ch["start"], ch["end"], ch["d_ours"], ch["d_vx"]):
            ca, cb, yr = cls(sessions[a]), cls(sessions[b]), sessions[b].year
            if "late" in (ca, cb) or "unknown" in (ca, cb):
                continue
            if ca == cb == "close":
                key = "close_close_2026" if yr == 2026 else "close_close_2020_2025" if yr <= 2025 else None
            else:
                key = "off_end_2026" if yr == 2026 else None
            if key:
                groups[key].append((x, y))
    out = {}
    for k, xy in groups.items():
        a = np.array(xy, float).reshape(-1, 2)
        s = vx.ols_summary(a[:, 0], a[:, 1])
        out[k] = {"n": s["n"], "slope": rnd(s["slope"], 4), "r": rnd(s["r"], 4)}
    cc, c6, off = (out[k]["slope"] for k in ("close_close_2020_2025", "close_close_2026", "off_end_2026"))
    out["prediction_holds"] = bool(abs(c6 - cc) <= 0.05 and off < min(cc, c6))
    return out


def d2_crush_gap(f, ev: pd.DataFrame, cls) -> dict:
    crush = dict(zip(f.ev["event_id"], f.ev["crush_mean_adj"]))
    e = ev[[s.year in (2025, 2026) for s in ev["s_0"]]].copy()
    e["y"] = [crush[i] for i in e["event_id"]]
    e["y2026"] = [float(s.year == 2026) for s in e["s_0"]]
    e["clean"] = [cls(a) == "close" and cls(b) == "close" for a, b in zip(e["s_m1"], e["s_0"])]
    out = {}
    for name, sub in (("all", e), ("both_close", e[e["clean"]])):
        d, _ = regression.dummies(sub["firm"], "firm")
        X = np.column_stack([np.ones(len(sub)), d, sub["y2026"].to_numpy()])
        fit = regression.fit(sub["y"].to_numpy(float), X)
        cov = regression.covariance(fit, X, np.array([stm.iso_week(s) for s in sub["s_0"]]),
                                    sub["firm"].to_numpy(object))
        t = regression.coef_test(fit, cov, X.shape[1] - 1)
        out[name] = {k: rnd(t[k]) for k in ("estimate", "se", "ci_lo", "ci_hi", "df")} | {
            "n": int(len(sub)), "n_2026": int(sub["y2026"].sum()), "companies": int(sub["firm"].nunique())}
    return out


# --- the run ---------------------------------------------------------------------------------------------

def prepare() -> dict:
    """Everything up to the blocks; reads no outcome beyond the block-C equality check (plan §13 item 2)."""
    p = params_mod.load()
    st = stage_dir(p)
    cls, tmap = timing_map(p)
    f = stats_run.load(p)
    sets, _ = stats_run.primary_sets(f)
    n = {h: int(len(r)) for h, r in sets.items()}
    if n != N_PLAN:
        raise RuntimeError(f"primary sets {n} differ from the plan's {N_PLAN} (a deviation, plan §13 item 4)")
    ev = {h: event_frame(f, sets[h]) for h in sets}

    res = pd.read_parquet(st / "results.parquet")
    lines_check = {}
    for h, (meas, stat) in LINE_ROWS.items():
        r = res[(res["hypothesis"] == h) & (res["measure"] == meas) & (res["statistic"] == stat)
                & (res["sample"] == "daily") & (res["subgroup_key"] == "all") & (res["adjustment"] == "market")]
        if len(r) != 1 or round(float(r["se"].iloc[0]), 4) != LINES[h]:
            raise RuntimeError(f"{h}: the published se row does not round to the plan's line {LINES[h]}")
        lines_check[h] = rnd(r["se"].iloc[0])

    iv = pd.read_parquet(st / "iv_daily.parquet",
                         columns=["security_id", "session_date", "snapshot_status", "cm30_iv", "next_event_id",
                                  "ev_exp1", "ev_exp2"])
    lv_cm = cm30_levels(iv)
    lv_sd = sigma_levels(st, iv, ev["H4"])
    mkt = pd.read_parquet(st / "market_daily.parquet", columns=["session_date", "ln_vix_cboe"]).dropna()
    m = dict(zip(mkt["session_date"], mkt["ln_vix_cboe"].astype(float)))

    sessions = f.sessions.dates
    events_tbl = pd.read_parquet(st / "events.parquet", columns=["security_id", "day0_session"])
    near = near_event_set(events_tbl, sessions)
    daily_from = p.day("snapshot_eras", "daily_from")
    firms = sorted(iv.loc[iv["session_date"] >= daily_from, "security_id"].unique())

    blocks = {"cm30.O": (stm.block_ordinary(lv_cm, m, firms, sessions, cls, near, daily_from), "O")}
    for kind in ("P", "A", "C"):
        blocks[f"cm30.{kind}"] = (stm.block_event(ev["H1"], lv_cm, m, cls, kind), kind)
    for kind in ("P", "A", "C"):
        blocks[f"sigma.{kind}"] = (stm.block_event(ev["H4"], lv_sd, m, cls, kind, key="event_id"), kind)

    # block C is the published mean-adjusted measure itself (plan §7): any difference is a bug, not a result
    for name, col in (("cm30.C", "crush_mean_adj"), ("sigma.C", "dsigma_d_mean_adj")):
        b = blocks[name][0]
        want = dict(zip(f.ev["event_id"], f.ev[col]))
        diff = np.abs(b["y"].to_numpy(float) - np.array([want[i] for i in b["event_id"]], float))
        if len(b) == 0 or not (diff.max() < 1e-10):
            raise RuntimeError(f"{name}: y differs from {col} (max {diff.max() if len(b) else 'empty'})")
    cnt = {h: counts(f, ev[h], cls, SHIFT[h][1]) for h in ev}
    block_rows = {}
    for name, (b, kind) in blocks.items():
        offcols = stm.OFFS[kind]
        block_rows[name] = {"rows": int(len(b)), "companies": int(b["firm"].nunique()) if len(b) else 0,
                            "weeks": int(b["week"].nunique()) if len(b) else 0,
                            **{f"rows_{c}": int(b[c].sum()) for c in offcols}}
    return {"p": p, "st": st, "cls": cls, "tmap": tmap, "f": f, "ev": ev, "blocks": blocks, "counts": cnt,
            "block_rows": block_rows, "lines_check": lines_check}


def compute() -> dict:
    x = prepare()
    p, st, cls, tmap, f, ev, blocks, cnt = (x[k] for k in ("p", "st", "cls", "tmap", "f", "ev", "blocks", "counts"))
    fit = stm.stacked_fit(blocks)
    combos = {f"coef {name}:{c}": stm.vector(fit, {f"{name}:{c}": 1.0})
              for name in blocks for c in stm.OFFS[name.split(".")[1]]}
    combos |= {f"coef {name}:dm": stm.vector(fit, {f"{name}:dm": 1.0}) for name in blocks}
    combos |= {f"shift {h}": stm.vector(fit, stm.shift_weights(s, ms, cnt[h], cnt[h]["n"]))
               for h, (s, ms) in SHIFT.items()}
    walds = {s: stm.identity_rows(fit, s) for s in ("cm30", "sigma")}
    tests = {f"{h} {side}": wc for h in SHIFT
             for side, wc in stm.line_tests(combos[f"shift {h}"], LINES[h]).items()}
    boot = stm.wild_bootstrap(fit, combos, BOOT_REPS, BOOT_SEED)
    wcr = stm.wcr_bootstrap(fit, tests, walds, BOOT_REPS, BOOT_SEED)
    rounded = lambda r: {k: (rnd(v) if not isinstance(v, list) else [rnd(x) for x in v]) for k, v in r.items()}  # noqa: E731
    coefs = {k[5:]: rounded(v) for k, v in boot["combos"].items() if k.startswith("coef ")}
    identity = {s: rounded(wcr["walds"][s]) | {"rejected": bool(wcr["walds"][s]["p_boot"] < 0.05)}
                for s in walds}

    shifts, raw = {}, {}
    for h in SHIFT:
        lo, hi = wcr["tests"][f"{h} lo"], wcr["tests"][f"{h} hi"]
        shifts[h] = rounded(boot["combos"][f"shift {h}"]) | {
            "line": LINES[h],
            "test_at_minus_line": rounded({k: lo[k] for k in ("t", "p_up", "p_dn")}),
            "test_at_plus_line": rounded({k: hi[k] for k in ("t", "p_up", "p_dn")})}
        raw[h] = stm.tost_verdict(lo, hi)
    verdicts = stm.gated(raw, {h: s for h, (s, _) in SHIFT.items()},
                         {s: identity[s]["rejected"] for s in identity})
    order = ordering(st, ev["H1"], cls)

    return {
        "kind": "snapshot_timing_check",
        "plan_sha256": sha256(PLAN),
        "timing_map_sha256": sha256(MAP),
        "params_hash": p.params_hash,
        "stage": st.name,
        "code_commit": store.code_commit(),
        "map_counts": {"off": len(tmap["off_dates"]), "late": len(tmap["late_dates"]),
                       "unknown": len(tmap["unknown_dates"]), "sessions": tmap["n_sessions"]},
        "lines": LINES, "lines_published_se": x["lines_check"],
        "counts": cnt,
        "blocks": x["block_rows"],
        "bootstrap": {"reps": boot["reps"], "seed": boot["seed"], "clusters_week": boot["clusters"],
                      "weights": "Webb six-point",
                      "verdicts_and_identity": "restricted wild cluster bootstrap by ISO week (null imposed)",
                      "intervals": "unrestricted wild cluster bootstrap-t by ISO week (descriptive)"},
        "coefficients": coefs,
        "identity": identity,
        "shifts": shifts,
        "verdicts_before_gate": raw,
        "verdicts": verdicts,
        "ordering": order,
        "d1_vx": d1_vx(cls),
        "d2_crush_gap": d2_crush_gap(f, ev["H1"], cls),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--plumbing", action="store_true",
                    help="stop before any fit: print the sample, count and block-row checks only (plan §13 item 2)")
    a = ap.parse_args(argv)
    if a.plumbing:
        x = prepare()
        print(json.dumps({"counts": x["counts"], "blocks": x["block_rows"], "lines_published_se": x["lines_check"],
                          "block_c_equals_published_measure": True}, indent=1))
        return 0
    out = compute()
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    print(f"wrote {OUT.relative_to(REPO)}: verdicts {out['verdicts']}; identity rejected "
          f"{ {s: v['rejected'] for s, v in out['identity'].items()} }")
    return 0


if __name__ == "__main__":
    sys.exit(main())
