# =============================================================================
# synth.py - A made-up option market for the falsifier probes of the
# vx-iv-checks pre-registration. No real data is read here.
#
# WHAT IT MAKES
#   One "Panel" per run: for each session of a 500-session window, a set of
#   3-4 expiries (like the vendor's: a front at 7+ sessions, a second two
#   weeks later, a third 5-6 weeks after the front, sometimes a fourth), a
#   sparse strike grid (2.5 / 5 / 10 apart), and call and put bid/ask quotes
#   in whole cents. The prices are European Black-76 prices from this file's
#   own pricer (math.erfc), not from the package, so a bug in the package's
#   pricer cannot cancel out.
#
# THE TRUE SURFACE
#   ATM total variance of an expiry with tau sessions:
#       w_atm = sigma_d(tau)^2 * tau / 252 + E * [the expiry spans the next event]
#   sigma_d(tau) = sigma_t * (tau / 21) ** ts_slope   (ts_slope = 0: flat, the
#   ADR 0003 model, so w is linear in tau inside a class).
#   The smile: w(k) = w_atm * (1 + b x + c x^2)^2 with x = k / sqrt(w_atm).
#   b = -0.12 and c = 0.09 give a 25-delta put about 3 vol points above ATM
#   and a 25-delta call about 1 below at 25% vol: an ordinary equity smile.
#   sigma_t follows a mean-reverting random walk in logs (4% a day).
#
# PLANTED DATA FAULTS (all default to 0 = the clean world)
#   atm_drop_prob     on that share of (session, expiry), the atm_drop_n
#                     strikes nearest the forward are not listed (like the
#                     missing 270 strike of ADR 0003): a listing change near
#                     the money.
#   atm_filter_prob   on that share of (session, expiry), the OTM legs of the
#                     atm_filter_n strikes nearest the forward get a spread of
#                     60% of the mid, so the quote filter (max 50%) drops them.
#   fault_scope       "expiry": the two faults above are drawn per (session,
#                     expiry); "session": one draw per session hits every
#                     expiry of that session at once (a vendor-wide bad day).
#   ts_slope          a diffusive term structure that is not flat, so w is
#                     not linear in tau and a change of expiry pair moves w*.
#   monthly_bump      monthly expiries (third Fridays) trade this many vol
#                     points above the others, every day: a persistent
#                     per-expiry bias that a change of expiry pair releases.
#
# GRID OPTIONS
#   atm_step          strike step within 10% of the spot (2x beyond, 4x past
#                     25%). 2.5 at a spot of 200 is a 1.25% grid; 10 is 5%.
#   fixed_grid        every multiple of atm_step from 0.4 to 2.5 times the
#                     starting spot, every day: no strike ever appears or
#                     disappears (with no random drops: no listing change).
#
# EVENTS
#   Every events_every sessions; they alternate BMO (announced on day 0) and
#   AMC (announced on day -1). The anchors come from the package's
#   tables.event_anchors on an events table, so its AMC branch of spans_from
#   is exercised. This file decides for its own prices which expiries hold
#   the event, by the ADR rule written out here (last session on or after the
#   first session on or after the announcement date), and the truth check in
#   ivchecks.py derives it a third time from the same events table.
# =============================================================================

import math
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np
import pandas as pd

from earnings_vol.events import calendar
from earnings_vol.measures import chain, tables

SQRT2 = math.sqrt(2.0)


def ncdf(x: float) -> float:
    return 0.5 * math.erfc(-x / SQRT2)


def price76(f: float, k: float, w: float, df: float, call: bool) -> float:
    """European Black-76 price on the forward f with total variance w (this file's own pricer)."""
    s = math.sqrt(w)
    d1 = (math.log(f / k) + 0.5 * w) / s
    d2 = d1 - s
    if call:
        return df * (f * ncdf(d1) - k * ncdf(d2))
    return df * (k * ncdf(-d2) - f * ncdf(-d1))


@dataclass
class SynthSpec:
    n_sessions: int = 500
    start: date = date(2024, 9, 12)
    s0: float = 200.0
    sigma0: float = 0.25
    phi: float = 0.98              # daily persistence of log sigma
    volvol: float = 0.04           # daily sd of log sigma
    smile_b: float = -0.12
    smile_c: float = 0.09
    r: float = 0.04
    events_every: int = 63         # sessions between events
    event_var: float = 0.0015      # E
    p_strike_drop: float = 0.05    # a strike not listed on a day (both legs)
    p_leg_drop: float = 0.02       # one leg not listed
    mid_noise: float = 0.25        # the quote mid sits uniformly within +-mid_noise * spread of the true price
    atm_drop_prob: float = 0.0     # planted listing fault
    atm_filter_prob: float = 0.0   # planted filter fault
    atm_drop_n: int = 1            # how many strikes nearest F the planted listing fault removes
    atm_filter_n: int = 2          # how many strikes nearest F the planted filter fault hits
    fault_scope: str = "expiry"    # "expiry": a fault draw per (session, expiry); "session": one per session
    ts_slope: float = 0.0          # planted term-structure fault
    monthly_bump: float = 0.0      # planted per-expiry bias (decimal vol)
    atm_step: float = 2.5
    fixed_grid: bool = False
    seed: int = 1


@dataclass
class Panel:
    """Everything a check needs for one name. Phase 2 builds the same object from the real files."""

    name: str
    sessions: calendar.Sessions
    days: list                          # the window's sessions, in order
    quotes: dict                        # session -> {expiration: chain.ExpiryQuotes}
    rate: dict                          # session -> r_cont
    anchors: list                       # [tables.Anchor], sorted
    status: dict                        # session -> snapshot status ('ok', 'stale_repeat', 'missing')
    close: dict                         # session -> an independent close (Yahoo in phase 2; the true spot here)
    exdiv: set = field(default_factory=set)   # sessions that are ex-dividend dates (skipped by the Yahoo check)
    truth: dict = field(default_factory=dict)
    events: list = field(default_factory=list)  # [{event_id, announce_date_used, day0_session}], as in events.parquet


def session_table() -> calendar.Sessions:
    t = calendar.build_session_table(date(2024, 1, 1), date(2027, 12, 31),
                                     {"weekly_from": "2019-02-09", "mwf_from": "2020-01-06",
                                      "daily_from": "2024-09-11", "data_end": "2027-12-31"})
    return calendar.Sessions(t["session_date"].tolist())


def _fridays_after(d: date, n: int) -> list:
    first = d + timedelta(days=(4 - d.weekday()) % 7 or 7)
    return [first + timedelta(days=7 * i) for i in range(n)]


def is_monthly(d: date) -> bool:
    """A third Friday."""
    return d.weekday() == 4 and 15 <= d.day <= 21


def _expiries(t: date, sessions: calendar.Sessions, rng) -> list:
    """3 or 4 vendor-like expiries: a weekly front (>= 7 sessions), the weekly two weeks later, the first
    monthly with >= 27 sessions, and on 20% of days the monthly after it. The two weeklies turn over
    together once a week; the monthly stays for about a month (like ADR 0003's AAPL table)."""
    fr = [f for f in _fridays_after(t, 30) if sessions.between(t, sessions.as_of(f)) >= 7]
    front = fr[0]
    months = [f for f in fr if is_monthly(f) and sessions.between(t, sessions.as_of(f)) >= 27]
    out = [front, front + timedelta(days=14), months[0]]
    if rng.random() < 0.2:
        out.append(months[1])
    return sorted(set(out))


def _grid(s: float, step0: float, s0: float, fixed: bool) -> list:
    """Strikes on multiples of step0 within 10% of s, 2 step0 to 25%, 4 step0 beyond; 0.7 s to 1.4 s.
    fixed: every multiple of step0 from 0.4 s0 to 2.5 s0, whatever s is."""
    if fixed:
        return [round(step0 * i, 2) for i in range(math.ceil(0.4 * s0 / step0), math.floor(2.5 * s0 / step0) + 1)]
    out = []
    k = step0 * math.floor(0.7 * s / step0)
    while k <= 1.4 * s:
        m = abs(k / s - 1.0)
        step = step0 if m < 0.10 else (2 * step0 if m < 0.25 else 4 * step0)
        if abs(k / step - round(k / step)) < 1e-9:
            out.append(round(k, 2))
        k += step0
    return out


def _rng(seed: int, *key) -> np.random.Generator:
    """A random stream keyed by (seed, purpose, session, expiry, strike...): a planted fault changes
    only its own draws, so a planted world and its control share the market path and the quote noise."""
    return np.random.default_rng([seed, *key])


def _quote(price: float, rng, mid_noise: float, blow_out: bool) -> tuple:
    spread = max(0.02, 0.03 * price + 0.01)
    if blow_out:
        spread = max(spread, 0.6 * price)
    mid = price + rng.uniform(-mid_noise, mid_noise) * spread
    bid = round(mid - spread / 2.0, 2)
    ask = round(mid + spread / 2.0, 2)
    if ask <= bid:
        ask = round(bid + 0.01, 2)
    return max(bid, 0.0), ask


def make_panel(spec: SynthSpec, name: str = "SYN", sessions: calendar.Sessions | None = None) -> Panel:
    path = _rng(spec.seed, 1)                  # spot, sigma and event jumps
    sessions = sessions or session_table()
    i0 = sessions.index[sessions.first_on_or_after(spec.start)]
    days = sessions.dates[i0:i0 + spec.n_sessions]
    # Events: alternately BMO (announced on day 0) and AMC (announced on the session before day 0).
    day0s = [days[j] for j in range(spec.events_every // 2, len(days) + 70, spec.events_every) if j < len(days)]
    extra = sessions.dates[i0 + len(days) + 10] if i0 + len(days) + 10 < len(sessions.dates) else None
    events = []
    for j, d in enumerate(day0s + ([extra] if extra is not None else [])):
        announce = d if j % 2 == 0 else sessions.shift(d, -1)
        events.append({"event_id": f"{name}:{d}", "security_id": name, "announce_date_used": announce,
                       "day0_session": d, "exclusion_reason": None, "timing": "BMO" if j % 2 == 0 else "AMC"})
    anchors = tables.event_anchors(pd.DataFrame(events), sessions)[name]
    day0_set = set(day0s)
    # This file's own rule for its prices: an expiry holds an event when its last session is on or after
    # the first session on or after the announcement date (ADR 0003 §b, tables.py header).
    own = sorted((ev["day0_session"], ev["announce_date_used"] if ev["announce_date_used"] in sessions.index
                  else sessions.next_after(ev["announce_date_used"])) for ev in events)

    s, lsig = spec.s0, math.log(spec.sigma0)
    quotes, rate, status, close, truth = {}, {}, {}, {}, {}
    for t in days:
        sig = math.exp(lsig)
        nxt = next((x for x in own if x[0] > t), None)
        exps = _expiries(t, sessions, _rng(spec.seed, 2, t.toordinal()))
        grid = _grid(s, spec.atm_step, spec.s0, spec.fixed_grid)
        per_exp = {}
        tw = {}
        for e in exps:
            tau = chain.tau_sessions(t, e, sessions)
            cal = (e - t).days
            df = math.exp(-spec.r * cal / 365.0)
            f = s * math.exp(spec.r * cal / 365.0)
            spans = nxt is not None and sessions.as_of(e) >= nxt[1]
            sd = sig * (tau / 21.0) ** spec.ts_slope + (spec.monthly_bump if is_monthly(e) else 0.0)
            w_atm = sd * sd * tau / 252.0 + (spec.event_var if spans else 0.0)
            tw[e] = {"tau": tau, "w_atm": w_atm, "forward": f, "spans": spans, "df": df}
            near = sorted(grid, key=lambda kk: abs(kk - f))
            plant = (_rng(spec.seed, 3, t.toordinal()) if spec.fault_scope == "session"
                     else _rng(spec.seed, 3, t.toordinal(), e.toordinal()))
            drop_atm = set(near[:spec.atm_drop_n]) if plant.random() < spec.atm_drop_prob else set()
            blow = set(near[:spec.atm_filter_n]) if plant.random() < spec.atm_filter_prob else set()
            rows = []
            for kk in grid:
                rng = _rng(spec.seed, 4, t.toordinal(), e.toordinal(), int(round(kk * 100)))
                if rng.random() < spec.p_strike_drop or kk in drop_atm:
                    continue
                x = math.log(kk / f) / math.sqrt(w_atm)
                wk = w_atm * (1.0 + spec.smile_b * x + spec.smile_c * x * x) ** 2
                c = price76(f, kk, wk, df, True)
                p = price76(f, kk, wk, df, False)
                otm_call = kk >= f
                cb, ca = _quote(c, rng, spec.mid_noise, kk in blow and otm_call)
                pb, pa = _quote(p, rng, spec.mid_noise, kk in blow and not otm_call)
                if rng.random() < spec.p_leg_drop:
                    cb, ca = math.nan, math.nan
                if rng.random() < spec.p_leg_drop:
                    pb, pa = math.nan, math.nan
                rows.append((kk, cb, ca, pb, pa))
            a = np.array(rows, float)
            nan = np.full(len(rows), np.nan)
            per_exp[e] = chain.ExpiryQuotes(a[:, 0], a[:, 1], a[:, 2], a[:, 3], a[:, 4], nan, nan)
        quotes[t], rate[t], status[t], close[t] = per_exp, spec.r, "ok", s
        truth[t] = {"sigma": sig, "spot": s, "expiries": tw}
        # Move to the next session: the spot (with the event jump on day 0) and log sigma.
        z_jump, z_s, z_v = path.normal(size=3)
        jump = z_jump * math.sqrt(spec.event_var) if sessions.next_after(t) in day0_set else 0.0
        s *= math.exp(z_s * sig / math.sqrt(252.0) + jump)
        lsig = math.log(spec.sigma0) + spec.phi * (lsig - math.log(spec.sigma0)) + spec.volvol * z_v
    return Panel(name, sessions, list(days), quotes, rate, anchors, status, close, set(), truth, events)
