# =============================================================================
# regressors.py — The regressor columns of `event_measures` (data model §3.11,
# ADR 0005 §3), left null at milestone 3 and filled at milestone 4. Pure:
# every input comes in as a DataFrame or a dict; panel/run.py reads them.
#
# THE COLUMNS, per event
#   price_ref          the as-of, unadjusted parity spot at the event's pre
#                      session (day -1 in daily): chain_expiry.forward x df of
#                      iv_daily.front_expiry there. Dividends inside about two
#                      weeks are ignored (data model). The pre session is
#                      event_iv's, the same session as E, sigma_d and SLOPE.
#   surprise_scaled    eps.surprise / price_ref (the linked eps row, R13). The
#                      EPS history is not split-adjusted, so the price must be
#                      the as-of one: the option forward is (ADR 0005 §3).
#   abs_surprise_scaled_w  |surprise_scaled| winsorised at the 1% / 99%
#                      quantiles (numpy's linear rule) over the events with the
#                      same events.sample and a surprise_scaled.
#   sue_hist, sue_hist_n   (surprise_scaled - mean of the security's previous
#                      sue_prev price-scaled surprises) / their sd (ddof 1),
#                      ordered by day 0 (the effective day 0 when it is null);
#                      only events with a surprise_scaled count as quarters;
#                      null, with sue_hist_n null, when fewer than sue_min_prev
#                      are there or their sd is 0.
#   vix_regime         the tercile of the VIX close at day -1 (`low`, `mid`,
#                      `high`), cut at the 1/3 and 2/3 quantiles over the events
#                      of the same events.sample with a VIX there (`none`: null).
#                      A value on a cut point goes to the lower bin.
#   realized_ret_0_yf  Yahoo close-to-close from the pre to the post session,
#                      ln((close_post + dividend_post) / close_pre): a
#                      cross-check of realized_ret_0. Split-adjusted closes on
#                      both days, so the ratio is unaffected by splits.
#   ln_mcap_yf         ln market cap at day -1 = ln(cap on the rank date) +
#                      ln(close(day -1) / close(last day in the file)), closes
#                      split-adjusted. It assumes the share count of the rank
#                      date (buybacks and issues ignored): the only market cap
#                      the project holds is the rank date's (ingest/universe).
#   _yf columns are class R (local); the others are class F, like every column
#   that depends on day 0 (data model §2.1).
# =============================================================================

import math

import numpy as np
import pandas as pd

from earnings_vol.events import calendar

REGIMES = ("low", "mid", "high")
COLUMNS = ("price_ref", "surprise_scaled", "abs_surprise_scaled_w", "sue_hist", "sue_hist_n", "vix_regime",
           "realized_ret_0_yf", "ln_mcap_yf")


def _finite(v) -> bool:
    return v is not None and isinstance(v, (int, float, np.floating)) and math.isfinite(float(v))


def price_ref(event_iv: pd.DataFrame, events: pd.DataFrame, iv_daily: pd.DataFrame,
              chain_expiry: pd.DataFrame) -> dict:
    """{event_id: forward x df of the front expiry at the event's pre session}, for the events
    with a pre session, a front expiry there and an ok chain_expiry row with a forward."""
    sec = dict(zip(events["event_id"], events["security_id"]))
    front = {(s, d): f for s, d, f in zip(iv_daily["security_id"], iv_daily["session_date"], iv_daily["front_expiry"])
             if f is not None}
    ce = chain_expiry[(chain_expiry["status"] == "ok") & chain_expiry["forward"].notna()]
    spot = {(s, d, x): f * q for s, d, x, f, q in zip(ce["security_id"], ce["session_date"], ce["expiration"],
                                                      ce["forward"], ce["df"])}
    out = {}
    for eid, pre in zip(event_iv["event_id"], event_iv["pre_session"]):
        if pre is None:
            continue
        s = sec[eid]
        fx = front.get((s, pre))
        v = None if fx is None else spot.get((s, pre, fx))
        if _finite(v) and v > 0:
            out[eid] = float(v)
    return out


def surprise_scaled(eps: pd.DataFrame, price: dict) -> dict:
    """{event_id: eps.surprise / price_ref} over the linked eps rows with both."""
    out = {}
    for eid, s in zip(eps["event_id"], eps["surprise"]):
        if eid is None or not _finite(s) or eid not in price:
            continue
        out[eid] = float(s) / price[eid]
    return out


def winsorise(values: dict, group: dict, q: tuple[float, float]) -> dict:
    """{key: value clipped to the [q0, q1] quantiles of its group}, quantiles over the keys of
    `values` in the same group (numpy's linear interpolation)."""
    by: dict = {}
    for k, v in values.items():
        by.setdefault(group[k], []).append(v)
    cut = {g: (float(np.quantile(v, q[0])), float(np.quantile(v, q[1]))) for g, v in by.items()}
    return {k: float(min(max(v, cut[group[k]][0]), cut[group[k]][1])) for k, v in values.items()}


def sue_hist(order: list[tuple], values: dict, n_prev: int, min_prev: int) -> dict:
    """{event_id: (sue, n)}: `order` is [(security_id, sort key, event_id)]; each event with a
    value is compared with its security's previous n_prev values (by sort key). Events with
    fewer than min_prev previous values, or with an sd of 0, are left out."""
    hist: dict = {}
    out = {}
    for sid, _, eid in sorted(order, key=lambda t: (t[0], t[1], t[2])):
        if eid not in values:
            continue
        prev = hist.setdefault(sid, [])
        use = prev[-n_prev:]
        if len(use) >= min_prev:
            sd = float(np.std(use, ddof=1))
            if sd > 0:
                out[eid] = ((values[eid] - float(np.mean(use))) / sd, len(use))
        prev.append(values[eid])
    return out


def vix_regime(vix: dict, sample: dict) -> dict:
    """{event_id: 'low' | 'mid' | 'high'}: the tercile of vix[event] among the events of the
    same sample (`none` left out). A value on a cut point goes to the lower bin."""
    by: dict = {}
    for k, v in vix.items():
        if sample[k] != "none":
            by.setdefault(sample[k], []).append(v)
    cut = {g: (float(np.quantile(v, 1 / 3)), float(np.quantile(v, 2 / 3))) for g, v in by.items()}
    out = {}
    for k, v in vix.items():
        if sample[k] == "none":
            continue
        lo, hi = cut[sample[k]]
        out[k] = REGIMES[0] if v <= lo else (REGIMES[1] if v <= hi else REGIMES[2])
    return out


def yahoo_return(px: pd.DataFrame, pre, post) -> float | None:
    """ln((close_post + dividend_post) / close_pre) from one security's Yahoo rows (columns
    date, close, dividends), or None when a day is missing or a close is not positive."""
    rows = px.set_index("date")
    if pre not in rows.index or post not in rows.index:
        return None
    c0, c1, dv = rows.at[pre, "close"], rows.at[post, "close"], rows.at[post, "dividends"]
    if not (_finite(c0) and _finite(c1)) or c0 <= 0 or c1 <= 0:
        return None
    return float(math.log((c1 + (dv if _finite(dv) else 0.0)) / c0))


def ln_mcap(px: pd.DataFrame, cap_now: float | None, day) -> float | None:
    """ln(cap_now) + ln(close(day) / close(last row)), split-adjusted closes (see the header)."""
    if cap_now is None or not _finite(cap_now) or cap_now <= 0 or px.empty:
        return None
    rows = px.set_index("date")
    if day not in rows.index:
        return None
    c, last = rows.at[day, "close"], px.sort_values("date")["close"].iloc[-1]
    if not (_finite(c) and _finite(last)) or c <= 0 or last <= 0:
        return None
    return float(math.log(cap_now) + math.log(c / last))


def regressor_table(events: pd.DataFrame, eps: pd.DataFrame, event_iv: pd.DataFrame, iv_daily: pd.DataFrame,
                    chain_expiry: pd.DataFrame, market_daily: pd.DataFrame, sessions: calendar.Sessions,
                    yahoo: dict, caps: dict, drivers: dict) -> pd.DataFrame:
    """One row per event with the COLUMNS of the header (None where not computed).

    yahoo  {security_id: Yahoo rows (date, close, dividends)}; caps {security_id: market cap on
    the rank date}; drivers  params.yaml's drivers section."""
    ids = events["event_id"].tolist()
    sec = dict(zip(ids, events["security_id"]))
    smp = dict(zip(ids, events["sample"]))
    pre = dict(zip(event_iv["event_id"], event_iv["pre_session"]))
    post = dict(zip(event_iv["event_id"], event_iv["post_session"]))
    price = price_ref(event_iv, events, iv_daily, chain_expiry)
    surp = surprise_scaled(eps, price)
    absw = winsorise({k: abs(v) for k, v in surp.items()}, smp, tuple(drivers["surprise_winsor"]))
    order = [(s, calendar.effective_day0(a, d, sessions), e)
             for e, s, a, d in zip(ids, events["security_id"], events["announce_date_used"], events["day0_session"])]
    sue = sue_hist(order, surp, int(drivers["sue_prev"]), int(drivers["sue_min_prev"]))
    vix_at = {d: v for d, v in zip(market_daily["session_date"], market_daily["vix_close_cboe"]) if _finite(v)}
    vix = {e: vix_at[d] for e, d in zip(ids, events["day_m1_session"]) if d is not None and d in vix_at}
    regime = vix_regime(vix, smp)
    m1s = dict(zip(ids, events["day_m1_session"]))
    out = []
    for e in ids:
        px = yahoo.get(sec[e])
        m1 = m1s[e]
        ret = None if px is None or pre.get(e) is None or post.get(e) is None else yahoo_return(px, pre[e], post[e])
        mc = None if px is None or m1 is None else ln_mcap(px, caps.get(sec[e]), m1)
        out.append({"event_id": e, "price_ref": price.get(e), "surprise_scaled": surp.get(e),
                    "abs_surprise_scaled_w": absw.get(e), "sue_hist": sue[e][0] if e in sue else None,
                    "sue_hist_n": sue[e][1] if e in sue else None, "vix_regime": regime.get(e),
                    "realized_ret_0_yf": ret, "ln_mcap_yf": mc})
    df = pd.DataFrame(out, columns=["event_id", *COLUMNS])
    df["sue_hist_n"] = pd.Series([r["sue_hist_n"] for r in out], dtype=object)
    return df
