# =============================================================================
# report.py — Counts and validation statistics of the milestone-2 tables, for
# the docs (cache/stage/<hash>/iv_report.json). Pure: tables in, numbers out.
#
# THE VENDOR COMPARISON (ADR 0003 §d, validation plan item 2; prediction P6)
#   On non-event days, the vendor's `vol` of the OTM quotes at the two bracket
#   strikes, interpolated in k like our w (chain_expiry.vendor_iv_atm), against
#   our ATM IV of the same expiry, the front one (the shortest with tau >= 5).
#   The vendor's annualisation is undocumented; ADR 0003 §d found it calendar-
#   annualised, so the like-for-like comparison is with ours on the calendar
#   clock, sqrt(365 w / tau_cal). The difference to our reported
#   (session-annualised) iv_atm is given too.
#   A non-event day is a session more than `away` sessions from every event's
#   day 0 (both iv_daily.sessions_to_next_event and sessions_since_prev_event
#   above `away`; a missing neighbour counts as far).
#   Differences are vendor minus ours, in vol points (0.01 = 1 point).
# =============================================================================

import numpy as np
import pandas as pd


def _summary(diff: np.ndarray) -> dict:
    if diff.size == 0:
        return {"n": 0}
    a = np.abs(diff)
    return {"n": int(diff.size), "mean_vol_pts": float(np.mean(diff) * 100), "median_vol_pts": float(np.median(diff) * 100),
            "median_abs_vol_pts": float(np.median(a) * 100), "p95_abs_vol_pts": float(np.percentile(a, 95) * 100),
            "share_vendor_below": float(np.mean(diff < 0))}


def non_event_days(iv: pd.DataFrame, away: int = 2) -> pd.Series:
    """True for ok sessions more than `away` sessions from every event's day 0."""
    to_next = iv["sessions_to_next_event"].map(lambda v: v is None or v > away)
    since = iv["sessions_since_prev_event"].map(lambda v: v is None or v > away)
    return (iv["snapshot_status"] == "ok") & to_next.astype(bool) & since.astype(bool)


def vendor_gap(ce: pd.DataFrame, iv: pd.DataFrame, away: int = 2) -> dict:
    """The vendor-minus-ours ATM IV gap on the front expiry of non-event days (P6)."""
    days = iv[non_event_days(iv, away) & iv["front_expiry"].notna()][["security_id", "session_date", "front_expiry"]]
    m = days.merge(ce, left_on=["security_id", "session_date", "front_expiry"],
                   right_on=["security_id", "session_date", "expiration"], how="inner")
    m = m[(m["atm_method"] == "bracket_linear") & m["vendor_iv_atm"].notna()]
    cal = np.sqrt(365.0 * m["w_atm"].to_numpy(float) / m["tau_cal_days"].to_numpy(float))
    vendor = m["vendor_iv_atm"].to_numpy(float)
    return {"away_sessions": away, "calendar_clock": _summary(vendor - cal),
            "session_clock": _summary(vendor - m["iv_atm"].to_numpy(float))}


def _counts(s: pd.Series) -> dict:
    return {str(k): int(v) for k, v in s.value_counts().sort_index().items()}


def _flag_counts(s: pd.Series) -> dict:
    out: dict[str, int] = {}
    for f in s:
        for code in filter(None, f.split("|")):
            out[code] = out.get(code, 0) + 1
    return dict(sorted(out.items()))


def iv_report(ce: pd.DataFrame, iv: pd.DataFrame, eiv: pd.DataFrame, events: pd.DataFrame) -> dict:
    ok = iv[iv["snapshot_status"] == "ok"]
    joined = eiv.merge(events[["event_id", "sample", "exclusion_reason"]], on="event_id")
    return {
        "chain_expiry": {"rows": int(len(ce)), "status": _counts(ce["status"]), "atm_method": _counts(ce["atm_method"]),
                         "flags": _flag_counts(ce["flags"])},
        "iv_daily": {"rows": int(len(iv)), "ok_sessions": int(len(ok)),
                     "with_front": int(ok["front_atm_iv"].notna().sum()), "with_cm30": int(ok["cm30_iv"].notna().sum()),
                     "with_cm30_blind": int(ok["cm30_blind_iv"].notna().sum()),
                     "with_event_var": int(ok["event_var"].notna().sum()), "cm30_method": _counts(ok["cm30_method"]),
                     "implied_move_status": _counts(ok["implied_move_status"]), "flags": _flag_counts(ok["flags"])},
        "event_iv": {"rows": int(len(eiv)),
                     "implied_move_status_by_sample": {s: _counts(g["implied_move_status"].dropna())
                                                       for s, g in joined.groupby("sample")},
                     "with_crush_mean_adj": int(eiv["crush_mean_adj"].notna().sum()),
                     "with_abs_move_cand_max": int(eiv["abs_move_cand_max"].notna().sum()),
                     "flags": _flag_counts(eiv["flags"])},
        "vendor_gap": vendor_gap(ce, iv),
    }
