# =============================================================================
# inputs.py — The stats layer's view of the panel: the window matrices back
# from event_window_obs (one row per event, rel_day -60 .. +10 in columns),
# joined with event_measures, events and security. Pure: DataFrames in,
# arrays out.
#
# THE EVENT SET OF A TEST (ADR 0005 §1, data model §3.11)
#   CRUSH (H1)       eligible_crush, the market-adjusted crush not null
#   RUNUP (H2)       eligible_runup
#   PERSIST_10 (H3)  eligible_persist_10
#   DSIGMA_D (H4)    eligible_crush, dsigma_d_cboe not null
#   PERSIST_1, _5    a passing baseline (persist_h_cboe not null)
# within one sample, and for a subgroup (timing) its events only.
# =============================================================================

from dataclasses import dataclass

import numpy as np
import pandas as pd

from earnings_vol.events import calendar
from earnings_vol.panel import abnormal, window

VALUE = {"crush": "crush_cboe", "runup": "runup_cboe", "persist_1": "persist_1_cboe", "persist_5": "persist_5_cboe",
         "persist_10": "persist_10_cboe", "dsigma_d": "dsigma_d_cboe"}
MEAN_ADJ = {"crush": ("measure", "crush_mean_adj"), "dsigma_d": ("measure", "dsigma_d_mean_adj"),
            "runup": ("aliv0", -1), "persist_1": ("aliv0", 1), "persist_5": ("aliv0", 5),
            "persist_10": ("aliv0", 10), "crush_front_fixed": ("measure", "crush_front_fixed")}
SA = {"crush": "sa_crush_cboe", "runup": "sa_runup_cboe", "persist_1": "sa_persist_1_cboe",
      "persist_5": "sa_persist_5_cboe", "persist_10": "sa_persist_10_cboe", "dsigma_d": "sa_dsigma_d_cboe"}


@dataclass
class Frame:
    """Every event with window rows, as arrays aligned on `ev` (one row per event)."""

    ev: pd.DataFrame              # events joined with event_measures and the sector
    sess: np.ndarray              # N x W session index
    usable: np.ndarray
    in_baseline: np.ndarray
    e: np.ndarray                 # e_abn_cboe
    aliv: np.ndarray              # aliv_cboe
    aliv0: np.ndarray             # aliv_mean_adj
    sigma_d: np.ndarray
    M: np.ndarray                 # ln VIX
    sessions: calendar.Sessions


def build_frame(events: pd.DataFrame, measures: pd.DataFrame, ewo: pd.DataFrame, security: pd.DataFrame,
                market_daily: pd.DataFrame, session_tbl: pd.DataFrame, eps: pd.DataFrame | None = None) -> Frame:
    """The Frame; `eps` (milestone 4), when given, adds the linked eps row's surprise_disp."""
    sessions = calendar.Sessions(session_tbl["session_date"].tolist())
    w = ewo.sort_values(["event_id", "rel_day"], kind="mergesort")
    ids = w["event_id"].to_numpy(object)[::abnormal.REL_DAYS.size]
    n, W = ids.size, abnormal.REL_DAYS.size
    if len(w) != n * W or not (w["rel_day"].to_numpy().reshape(n, W) == abnormal.REL_DAYS[None]).all():
        raise ValueError("event_window_obs must hold rel_day -60 .. +10 for every event")

    def mat(c, dtype=float):
        v = w[c].to_numpy()
        return (v.astype(float) if dtype is float else v.astype(dtype)).reshape(n, W)

    sess = np.array([sessions.index[d] for d in w["session_date"]]).reshape(n, W)
    vix = {sessions.index[d]: v for d, v in zip(market_daily["session_date"], market_daily["ln_vix_cboe"])}
    M = np.array([vix.get(t, np.nan) for t in sess.ravel()], float).reshape(n, W)
    ev = pd.DataFrame({"event_id": ids}).merge(events, on="event_id", how="left") \
        .merge(measures, on="event_id", how="left") \
        .merge(security[["security_id", "gics_sector"]], on="security_id", how="left")
    if eps is not None:
        linked = eps[eps["event_id"].notna()][["event_id", "surprise_disp"]]
        ev = ev.merge(linked, on="event_id", how="left")
    return Frame(ev, sess, np.isfinite(mat("cm30_iv")), mat("in_baseline", bool), mat("e_abn_cboe"),
                 mat("aliv_cboe"), mat("aliv_mean_adj"), mat("sigma_d_iv"), M, sessions)


def event_set(f: Frame, measure: str, sample: str, timing: str | None = None) -> np.ndarray:
    """Row indices of the test's event set (see the header)."""
    ev = f.ev
    keep = (ev["sample"] == sample).to_numpy().copy()
    if timing is not None:
        keep &= (ev["timing_used"] == timing).to_numpy()
    if measure in ("crush", "crush_front_fixed"):
        keep &= ev["eligible_crush"].to_numpy(bool)
    elif measure == "dsigma_d":
        keep &= ev["eligible_crush"].to_numpy(bool) & ev["dsigma_d_cboe"].notna().to_numpy()
    elif measure in ("runup", "persist_10"):
        keep &= ev[f"eligible_{measure}"].to_numpy(bool)
    else:
        keep &= ev[VALUE[measure]].notna().to_numpy()
    return np.flatnonzero(keep)


def values(f: Frame, rows: np.ndarray, measure: str, adjustment: str) -> np.ndarray:
    """A_i of the measure for the rows: market-adjusted (event_measures *_cboe) or the
    mean-adjusted twin (crush_mean_adj, dsigma_d_mean_adj, or aliv_mean_adj at the target)."""
    if adjustment == "market":
        return f.ev[VALUE[measure]].to_numpy(float)[rows]
    kind, key = MEAN_ADJ[measure]
    if kind == "measure":
        return f.ev[key].to_numpy(float)[rows]
    return f.aliv0[rows, abnormal.col(key)]


def clean_e(f: Frame, rows: np.ndarray, series: str) -> np.ndarray:
    """The clean baseline abnormal one-session changes of the rows (N x W, NaN elsewhere):
    series 'cm30' (e_abn_cboe) or 'sigma_d' (ln sigma_d_iv, panel.window.sigma_d_baseline)."""
    clean = abnormal.clean_changes(f.in_baseline[rows])
    if series == "cm30":
        return np.where(clean & np.isfinite(f.e[rows]), f.e[rows], np.nan)
    beta = f.ev["beta_vix_cboe"].to_numpy(float)[rows]
    return window.sigma_d_baseline(f.sigma_d[rows], f.M[rows], f.in_baseline[rows], beta)


def calendar_axis(f: Frame, rows: np.ndarray, win: np.ndarray) -> np.ndarray:
    """Scatter the rows' N x W values onto N x T calendar sessions (T spans the rows)."""
    s = f.sess[rows]
    t0 = int(s.min())
    out = np.full((rows.size, int(s.max()) - t0 + 1), np.nan)
    r = np.repeat(np.arange(rows.size), s.shape[1])
    ok = np.isfinite(win.ravel())
    out[r[ok], (s.ravel() - t0)[ok]] = win.ravel()[ok]
    return out


def robust_inputs(f: Frame, rows: np.ndarray, measure: str) -> dict:
    """The standardised inputs of the one-session robustness rows (stats.suite.one_session)."""
    series = "sigma_d" if measure == "dsigma_d" else "cm30"
    e = clean_e(f, rows, series)
    with np.errstate(invalid="ignore", divide="ignore"):
        s = np.sqrt(np.nanvar(e, axis=1, ddof=1)) if series == "sigma_d" else f.ev["s_abn_cboe"].to_numpy(float)[rows]
    z = calendar_axis(f, rows, e / s[:, None])
    a = np.zeros(z.shape)
    t0 = int(f.sess[rows].min())
    a[np.arange(rows.size), f.sess[rows, abnormal.col(0)] - t0] = 1.0
    return {"sa": f.ev[SA[measure]].to_numpy(float)[rows], "z": z, "a_cal": a,
            "sector": f.ev["gics_sector"].to_numpy(object)[rows],
            "n_changes": np.isfinite(e).sum(1), "baseline": [r_[np.isfinite(r_)] for r_ in e]}
