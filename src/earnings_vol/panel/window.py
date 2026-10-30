# =============================================================================
# window.py — `event_window_obs` and `event_measures` (data model §3.10,
# §3.11), in the panel layer's fixed order (ADR 0001 §1):
#   1. window rows: rel_day -60 .. +10 of every event with a null
#      exclusion_reason, with observed / in_baseline / the reason a baseline
#      session is not clean;
#   2. beta per security from the pooled clean baseline changes of its
#      events whose baseline passes the 20/15 minimum (ADR 0004 §1);
#   3. the market-adjusted columns (e_abn_cboe, aliv_cboe);
#   4. the rest of event_measures: the tested quantities, eligibility, the
#      scale s_i and the standardised values SA_i.
# Pure: every table comes in as a DataFrame or a look-up; panel/run.py reads
# and writes them.
#
# WHAT IS TESTED, PER EVENT (ADR 0004 §3)
#   RUNUP      ALIV at day -1            PERSIST_h  ALIV at day +h (h = 1, 5, 10)
#   CRUSH      e between pre and post    DSIGMA_D   dsigma_d_mean_adj - beta dM(pre, post)
#   pre / post are event_iv's: day -1 / day 0 in `daily` and `mixed` (both
#   required there), the nearest observed within one session in `coarse`
#   (ADR 0004 §4). In `coarse` RUNUP is read at pre and PERSIST_h at the first
#   usable of +h, +h-1, +h+1 inside the window.
#
# ELIGIBILITY (data model §3.11), per measure crush, runup, persist_10; the
# first failing rule is its reason:
#   event_excluded   events.exclusion_reason is set
#   beyond_data_end  persist_10 only: day +10 is after the data end
#   missing_m1 / missing_0 / missing_target   the sessions the measure reads
#                    are not usable (no ok snapshot or no cm30_iv)
#   short_baseline   fewer than 20 clean sessions or 15 clean changes
# A clean change is a one-session change with both ends in B in `daily`. In
# `mixed` and `coarse` the baseline lies (partly) in the Mon/Wed/Fri era,
# where one-session changes are mostly missing, so a change there may span
# up to two sessions across unobserved sessions only (ADR 0004 §4; default
# taken at milestone 3, params windows.baseline_max_change_span).
#
# THE SCALE AND SA (ADR 0005 §1)
#   s_i and SA_i = A_i / (s_i sqrt(a' R-hat a)) are built for `daily` events
#   only. The Mon/Wed/Fri scale of `mixed` and `coarse` needs the span-change
#   correction of ADR 0005 §1, which is not built (milestone-3 note).
#   R-hat is pooled over the measure's own event set (its eligible daily
#   events), as ADR 0005 §1 says. For DSIGMA_D, s_i is the sd of the abnormal
#   baseline changes of ln sigma_d_iv (sigma_d_baseline below).
# =============================================================================

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from earnings_vol.events import calendar
from earnings_vol.events.eps import orphan_zones
from earnings_vol.measures import chain, tables, termstructure
from earnings_vol.panel import abnormal
from earnings_vol.panel.baseline import baseline_reasons, event_centres, zones_of_events

W = abnormal.REL_DAYS.size
PERSIST_H = (1, 5, 10)
MEASURES = ("crush", "runup", "persist_10")


@dataclass
class Panel:
    """The window matrices of the events that get window rows (one row each)."""

    events: pd.DataFrame          # their events rows, in order
    session: np.ndarray           # N x W session indices
    observed: np.ndarray          # ok snapshot
    usable: np.ndarray            # ok snapshot and a cm30_iv
    in_baseline: np.ndarray
    reason: np.ndarray            # object: the baseline_excluded_reason
    X: np.ndarray                 # ln cm30_iv where usable
    M: np.ndarray                 # ln VIX
    cm30: np.ndarray              # cm30_iv where usable
    sigma_d: np.ndarray           # sigma_d_iv where observed
    event_var: np.ndarray         # iv_daily.event_var where its next event is this one


def lookups(iv_daily: pd.DataFrame, market_daily: pd.DataFrame, sessions: calendar.Sessions) -> dict:
    """Per-(security, session index) look-ups of iv_daily, and ln VIX per session index."""
    idx = [sessions.index[d] for d in iv_daily["session_date"]]
    keys = list(zip(iv_daily["security_id"], idx))
    ok = (iv_daily["snapshot_status"] == "ok").to_numpy()
    cm = iv_daily["cm30_iv"].to_numpy(float)
    return {
        "observed": {k for k, o in zip(keys, ok) if o},
        "cm30": {k: v for k, o, v in zip(keys, ok, cm) if o and np.isfinite(v)},
        "sigma_d": {k: v for k, o, v in zip(keys, ok, iv_daily["sigma_d_iv"].to_numpy(float)) if o and np.isfinite(v)},
        "event_var": {(k, n): v for k, o, n, v in zip(keys, ok, iv_daily["next_event_id"],
                                                     iv_daily["event_var"].to_numpy(float))
                      if o and n is not None and np.isfinite(v)},
        "ln_vix": {sessions.index[d]: v for d, v in zip(market_daily["session_date"],
                                                         market_daily["ln_vix_cboe"].to_numpy(float))
                   if np.isfinite(v)},
    }


def build_panel(events: pd.DataFrame, eps: pd.DataFrame, look: dict, sessions: calendar.Sessions,
                windows: dict) -> Panel:
    """Step 1: the window matrices of every event with a null exclusion_reason."""
    zone = tuple(windows["exclusion_zone"])
    bwin = tuple(windows["baseline"])
    orphans = orphan_zones(eps, sessions, tuple(windows["orphan_zone_sessions"]))
    zones = {sid: zones_of_events(event_centres(g, sessions), zone) for sid, g in events.groupby("security_id")}
    keep = events[events["exclusion_reason"].isna()].reset_index(drop=True)
    n = len(keep)
    sess = np.zeros((n, W), dtype=np.int64)
    observed = np.zeros((n, W), bool)
    usable = np.zeros((n, W), bool)
    inb = np.zeros((n, W), bool)
    reason = np.full((n, W), "outside", dtype=object)
    X, M, cm, sd, ev = (np.full((n, W), np.nan) for _ in range(5))
    obs_set = look["observed"]
    for i, r in enumerate(keep.itertuples(index=False)):
        sid, d0 = r.security_id, sessions.index[r.day0_session]
        sess[i] = d0 + abnormal.REL_DAYS
        has_iv = {t for t in sess[i] if (sid, t) in look["cm30"]}
        obs = {t for t in sess[i] if (sid, t) in obs_set}
        reasons = baseline_reasons(d0, r.event_id, zones[sid], orphans.get(sid, []), obs, has_iv, bwin)
        for j, t in enumerate(sess[i]):
            t = int(t)
            observed[i, j] = t in obs
            usable[i, j] = t in has_iv
            if t in reasons:
                reason[i, j] = reasons[t]
                inb[i, j] = reasons[t] is None
            if usable[i, j]:
                cm[i, j] = look["cm30"][(sid, t)]
                X[i, j] = math.log(cm[i, j])
            M[i, j] = look["ln_vix"].get(t, np.nan)
            if observed[i, j]:
                sd[i, j] = look["sigma_d"].get((sid, t), np.nan)
                ev[i, j] = look["event_var"].get(((sid, t), r.event_id), np.nan)
    reason[inb] = None
    return Panel(keep, sess, observed, usable, inb, reason, X, M, cm, sd, ev)


def change_counts(p: Panel, max_span: dict) -> np.ndarray:
    """Clean changes per event: consecutive baseline sessions at most max_span[sample]
    sessions apart, with only unobserved sessions between them (see the header)."""
    out = np.zeros(len(p.events), dtype=np.int64)
    for i, smp in enumerate(p.events["sample"]):
        b = np.flatnonzero(p.in_baseline[i])
        k = int(max_span[smp])
        out[i] = sum(1 for a, c in zip(b[:-1], b[1:])
                     if c - a <= k and all(p.reason[i, j] == "not_observed" for j in range(a + 1, c)))
    return out


def sigma_d_baseline(sigma_d: np.ndarray, M: np.ndarray, in_baseline: np.ndarray, beta: np.ndarray) -> np.ndarray:
    """The abnormal one-session baseline changes of ln sigma_d_iv: N x W, NaN off the clean grid.

    A change counts when both ends are in B and both have a sigma_d_iv."""
    with np.errstate(invalid="ignore", divide="ignore"):
        lsd = np.log(np.where(sigma_d > 0, sigma_d, np.nan))
    e = abnormal.abnormal_changes(lsd, M, beta)
    clean = abnormal.clean_changes(in_baseline) & np.isfinite(e)
    return np.where(clean, e, np.nan)


def _target_col(p: Panel, i: int, h: int, coarse: bool) -> int | None:
    """The column PERSIST_h (h >= 1) or RUNUP (h = -1) reads, or None (see the header)."""
    cands = [h] if not coarse else [h, h - 1, h + 1]
    for rel in cands:
        if abnormal.REL_LO <= rel <= abnormal.REL_HI and p.usable[i, abnormal.col(rel)]:
            return abnormal.col(rel)
    return None


def measures(p: Panel, event_iv: pd.DataFrame, sessions: calendar.Sessions, windows: dict,
             data_end_index: int, max_lag: int = 10, grid: int = 512) -> dict:
    """Steps 2-4. Returns the per-event arrays and the window-level ALIV matrices.

    Keys: beta, beta_n (per row), aliv, aliv0, e (N x W), values {measure: N array},
    eligible {measure: N bool}, reason {measure: [str|None]}, s, sa {measure: N array},
    rhat {measure: (rho, flag)}, n_sessions, n_changes, mu, mu_iv, weights {measure: N x W}.
    """
    n = len(p.events)
    sec = p.events["security_id"].to_numpy(object)
    smp = p.events["sample"].to_numpy(object)
    clean = abnormal.clean_changes(p.in_baseline)
    n_sess = p.in_baseline.sum(1)
    n_chg = change_counts(p, windows["baseline_max_change_span"])
    base_ok = (n_sess >= windows["baseline_min_sessions"]) & (n_chg >= windows["baseline_min_changes"])
    # beta pools only the baselines that pass the 20/15 minimum: ADR 0004 §1 says an event below
    # it "gets no baseline and is excluded from every measure that needs one", beta included.
    dX, dM = abnormal.one_session_changes(p.X), abnormal.one_session_changes(p.M)
    betas = abnormal.beta_by_security(sec, p.session, dX, dM, clean & base_ok[:, None])
    beta = np.array([np.nan if betas[s][0] is None else betas[s][0] for s in sec])
    beta_n = np.array([betas[s][1] for s in sec], dtype=np.int64)
    al, al0 = abnormal.aliv(p.X, p.M, p.in_baseline, beta)
    e = abnormal.abnormal_changes(p.X, p.M, beta)
    daily = smp == "daily"
    s = np.where(daily, abnormal.baseline_sd(e, clean), np.nan)

    eiv = event_iv.set_index("event_id")
    c0, cm1 = abnormal.col(0), abnormal.col(-1)
    vals = {m: np.full(n, np.nan) for m in ("crush", "runup", "persist_1", "persist_5", "persist_10", "dsigma_d")}
    weights = {m: np.zeros((n, W)) for m in vals}
    elig = {m: np.zeros(n, bool) for m in MEASURES}
    why = {m: [None] * n for m in MEASURES}
    for i, r in enumerate(p.events.itertuples(index=False)):
        coarse = r.sample == "coarse"
        row = eiv.loc[r.event_id]
        pre, post = row["pre_session"], row["post_session"]
        pc = None if pre is None else abnormal.col(sessions.index[pre] - int(p.session[i, c0]))
        qc = None if post is None else abnormal.col(sessions.index[post] - int(p.session[i, c0]))
        if not coarse:                      # daily and mixed: exactly day -1 and day 0
            pc = pc if pc == cm1 else None
            qc = qc if qc == c0 else None
        pc = pc if pc is not None and p.usable[i, pc] else None
        qc = qc if qc is not None and p.usable[i, qc] else None
        has_beta = np.isfinite(beta[i])
        # CRUSH and DSIGMA_D (one change, spanning pre -> post)
        if pc is not None and qc is not None and has_beta:
            dm = p.M[i, qc] - p.M[i, pc]
            vals["crush"][i] = (p.X[i, qc] - p.X[i, pc]) - beta[i] * dm
            weights["crush"][i, pc + 1:qc + 1] = 1.0
            ds = row["dsigma_d_mean_adj"]
            if ds is not None and np.isfinite(ds):
                vals["dsigma_d"][i] = ds - beta[i] * dm
                weights["dsigma_d"][i, pc + 1:qc + 1] = 1.0
        # RUNUP and PERSIST_h (ALIV at a target; the span-change weights for the variance)
        targets = {"runup": pc if coarse else (cm1 if p.usable[i, cm1] else None)}
        for h in PERSIST_H:
            beyond = int(p.session[i, c0]) + h > data_end_index
            targets[f"persist_{h}"] = None if beyond else _target_col(p, i, h, coarse)
        for m, t in targets.items():
            if t is not None and base_ok[i] and has_beta:
                vals[m][i] = al[i, t]
                weights[m][i] = abnormal.grid_weights(abnormal.span_changes(p.in_baseline[i], p.usable[i], t), W)
        # eligibility, first failing rule
        crush_miss = "missing_m1" if pc is None else ("missing_0" if qc is None else None)
        rules = {"crush": [crush_miss],
                 "runup": [None if targets["runup"] is not None else "missing_m1"],
                 "persist_10": ["beyond_data_end" if int(p.session[i, c0]) + 10 > data_end_index else None,
                                None if targets["persist_10"] is not None else "missing_target"]}
        for m in MEASURES:
            first = next((x for x in rules[m] if x is not None), None)
            if first is None and not (base_ok[i] and has_beta):
                first = "short_baseline"
            why[m][i] = first
            elig[m][i] = first is None

    # SA_i: daily events, R-hat over each measure's own event set (ADR 0005 §1)
    e_sd = sigma_d_baseline(p.sigma_d, p.M, p.in_baseline, beta)
    s_sd = np.where(daily, abnormal.baseline_sd(e_sd, np.isfinite(e_sd)), np.nan)
    sets = {"crush": elig["crush"], "dsigma_d": elig["crush"] & np.isfinite(vals["dsigma_d"]),
            "runup": elig["runup"], "persist_10": elig["persist_10"],
            "persist_1": base_ok & np.isfinite(vals["persist_1"]), "persist_5": base_ok & np.isfinite(vals["persist_5"])}
    sa, rh = {}, {}
    for m, member in sets.items():
        member = member & daily & np.isfinite(vals[m])
        scale = s_sd if m == "dsigma_d" else s
        if m in ("crush", "dsigma_d"):
            q = abnormal.lag_products(weights[m], max_lag)
            rho, flag = np.zeros(max_lag), ""
        else:
            rows = np.flatnonzero(member)
            rho, flag = abnormal.rhat(e[rows], s[rows], clean[rows], max_lag, grid)
            q = abnormal.lag_products(weights[m], max_lag)
        rh[m] = (rho, flag)
        with np.errstate(invalid="ignore", divide="ignore"):
            sa[m] = np.where(member, vals[m] / (scale * np.sqrt(abnormal.quad_form(q, rho))), np.nan)
    return {"beta": beta, "beta_n": beta_n, "aliv": al, "aliv0": al0, "e": e, "values": vals, "eligible": elig,
            "reason": why, "s": s, "s_sigma_d": s_sd, "sa": sa, "rhat": rh, "n_sessions": n_sess, "n_changes": n_chg,
            "base_ok": base_ok, "mu": abnormal.baseline_mean(p.X, p.in_baseline),
            "mu_iv": abnormal.baseline_mean(p.cm30, p.in_baseline), "weights": weights, "clean": clean}


def front_fixed_ivs(p: Panel, event_iv: pd.DataFrame, chains: dict, anchors: dict, sessions: calendar.Sessions,
                    tau_min: int) -> tuple[np.ndarray, np.ndarray]:
    """IV of the event's T1* expiry on each event-window session (rel_day -10 .. +10), and
    whether it was interpolated because T1* was not listed (ADR 0003 §a). `chains` maps
    (security_id, session date) to its ok chain_expiry rows. Outside the window: NaN, False."""
    iv = np.full(p.X.shape, np.nan)
    interp = np.zeros(p.X.shape, bool)
    t1s = dict(zip(event_iv["event_id"], event_iv["front_fixed_expiry"]))
    for i, r in enumerate(p.events.itertuples(index=False)):
        t1 = t1s.get(r.event_id)
        if t1 is None:
            continue
        for rel in range(-10, 11):
            j = abnormal.col(rel)
            if not p.observed[i, j]:
                continue
            d = sessions.dates[int(p.session[i, j])]
            if t1 <= d:
                continue
            tau = chain.tau_sessions(d, t1, sessions)
            if tau < tau_min:
                continue
            rows = chains.get((r.security_id, d), [])
            listed = [x for x in rows if x["expiration"] == t1]
            if listed:
                iv[i, j] = listed[0]["iv_atm"]
                continue
            nxt, _ = tables.neighbours(anchors.get(r.security_id, []), d)
            spans = nxt is not None and tables.spans(t1, nxt, sessions)
            ex = [termstructure.Expiry(x["expiration"], x["tau_sessions"], x["w_atm"], x["iv_atm"],
                                       bool(x["spans_next_event"]))
                  for x in rows if x["tau_sessions"] >= tau_min and bool(x["spans_next_event"]) == spans]
            got = termstructure.interpolate(ex, tau, 0)
            if got is not None and got[0] > 0:
                iv[i, j] = chain.annualised_iv(got[0], tau)
                interp[i, j] = True
    return iv, interp


def _num(v):
    return None if v is None or (isinstance(v, float) and not math.isfinite(v)) else float(v)


def window_table(p: Panel, m: dict, front: tuple[np.ndarray, np.ndarray], sessions: calendar.Sessions,
                 columns: tuple[str, ...]) -> pd.DataFrame:
    """event_window_obs, one row per (event, rel_day), in the registry's column order."""
    rows = {c: [] for c in columns}
    al, al0 = m["aliv"], m["aliv0"]
    mu_iv = m["mu_iv"]
    for i, eid in enumerate(p.events["event_id"]):
        for j, rel in enumerate(abnormal.REL_DAYS):
            t = int(p.session[i, j])
            rows["event_id"].append(eid)
            rows["rel_day"].append(int(rel))
            rows["session_date"].append(sessions.dates[t])
            rows["observed"].append(bool(p.observed[i, j]))
            rows["in_window"].append(bool(-10 <= rel <= 10))
            rows["in_baseline"].append(bool(p.in_baseline[i, j]))
            rows["baseline_excluded_reason"].append(p.reason[i, j])
            x = p.X[i, j]
            rows["cm30_iv"].append(_num(p.cm30[i, j]))
            rows["ln_cm30"].append(_num(x))
            rows["d_ln_cm30"].append(_num(x - p.X[i, j - 1]) if j > 0 else None)
            rows["e_abn_cboe"].append(_num(m["e"][i, j]))
            rows["aliv_cboe"].append(_num(al[i, j]) if m["base_ok"][i] else None)
            rows["aliv_mean_adj"].append(_num(al0[i, j]) if m["base_ok"][i] else None)
            rows["aiv_level"].append(_num(p.cm30[i, j] - mu_iv[i]) if m["base_ok"][i] else None)
            rows["front_fixed_iv"].append(_num(front[0][i, j]))
            rows["front_fixed_interpolated"].append(bool(front[1][i, j]))
            rows["sigma_d_iv"].append(_num(p.sigma_d[i, j]))
            rows["event_var"].append(_num(p.event_var[i, j]))
            rows["ln_vx_cboe"].append(None)
            rows["e_abn_vx_cboe"].append(None)
    return pd.DataFrame(rows, columns=list(columns))


IV_COPY = ("crush_mean_adj", "dsigma_d_mean_adj", "crush_front_fixed", "crush_span_sessions", "evar_m1", "evar_m2",
           "implied_move_m1", "implied_abs_move_total_m1", "implied_move_status", "sigma_d_m1", "cm30_m1",
           "ts_slope_m1", "realized_ret_0", "abs_move_cand_max", "abs_ret_over_implied")


def measures_table(events: pd.DataFrame, event_iv: pd.DataFrame, p: Panel, m: dict,
                   columns: tuple[str, ...], regs: pd.DataFrame | None = None) -> pd.DataFrame:
    """event_measures, one row per event of `events` (1:1), in the registry's column order.
    `regs` (panel/regressors.regressor_table, milestone 4) fills the regressor columns."""
    pos = {eid: i for i, eid in enumerate(p.events["event_id"])}
    eiv = event_iv.set_index("event_id")
    reg = {} if regs is None else {r["event_id"]: r for r in regs.to_dict("records")}
    out = []
    for r in events.itertuples(index=False):
        row = {c: None for c in columns}
        row["event_id"] = r.event_id
        iv = eiv.loc[r.event_id]
        for c in IV_COPY:
            v = iv[c]
            row[c] = (None if v is None or (isinstance(v, float) and math.isnan(v)) else v)
        for c, v in reg.get(r.event_id, {}).items():
            if c != "event_id":
                row[c] = None if v is None or (isinstance(v, float) and math.isnan(v)) else v
        if row["sue_hist_n"] is not None:
            row["sue_hist_n"] = int(row["sue_hist_n"])
        if row["crush_span_sessions"] is not None:
            row["crush_span_sessions"] = int(row["crush_span_sessions"])
        i = pos.get(r.event_id)
        if i is None:
            for mm in MEASURES:
                row[f"eligible_{mm}"] = False
            row["ineligible_reason"] = "|".join(f"{mm}:event_excluded" for mm in sorted(MEASURES))
            row.update(baseline_n=0, baseline_n_changes=0, beta_n=0)
            out.append(row)
            continue
        for mm in MEASURES:
            row[f"eligible_{mm}"] = bool(m["eligible"][mm][i])
        row["ineligible_reason"] = "|".join(sorted(f"{mm}:{m['reason'][mm][i]}" for mm in MEASURES
                                                   if m["reason"][mm][i] is not None))
        row["baseline_n"] = int(m["n_sessions"][i])
        row["baseline_n_changes"] = int(m["n_changes"][i])
        if m["n_sessions"][i] > 0:
            row["baseline_mean_ln_iv"] = _num(m["mu"][i])
            row["baseline_mean_iv"] = _num(m["mu_iv"][i])
        row["beta_vix_cboe"] = _num(m["beta"][i])
        row["beta_n"] = int(m["beta_n"][i])
        row["s_abn_cboe"] = _num(m["s"][i])
        v = m["values"]
        for name in ("runup", "crush", "persist_1", "persist_5", "persist_10", "dsigma_d"):
            row[f"{name}_cboe"] = _num(v[name][i])
            row[f"sa_{name}_cboe"] = _num(m["sa"][name][i])
        out.append(row)
    df = pd.DataFrame(out, columns=list(columns))
    for c in ("crush_span_sessions", "sue_hist_n"):
        df[c] = pd.Series([x[c] for x in out], dtype=object)
    return df
