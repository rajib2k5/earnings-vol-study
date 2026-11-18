# =============================================================================
# ivchecks.py - The statistics and decision rules of the vx-iv-checks
# pre-registration (docs/validation/vx-iv-checks/preregistration.md). The
# falsifier probes (run_probes.py) run this file on synthetic panels; phase 2
# runs the same functions on the real panels of GOOGL, GS and IBM.
#
# THE RULE THIS FILE KEEPS
#   Every IV comes from the package's own code path: tables.chain_rows ->
#   chain.expiry_atom for one expiry, tables.iv_daily_row ->
#   termstructure.day_measures for one session. A "counterfactual" never
#   changes that code. It only changes the INPUT (a forward multiplied by
#   exp(eps), or the quotes of the synthetic-truth surface) or chooses which
#   changes to compare. Nothing here is fitted to the Cboe indices.
#
# WORDS
#   change       ln(IV on session t) - ln(IV on session t-1), t-1 the session
#                just before t.
#   share        the part of the variance of the daily changes that one
#                component causes. Two ways to measure it here:
#                - injection (forward): add the component's measured noise once
#                  more and see how much variance it adds;
#                - switch excess (strikes, filter, roll): changes where the
#                  component switched have extra variance compared with changes
#                  where it did not; share = (fraction of switch changes) x
#                  (extra variance) / (variance of all changes).
#                A first design held the component fixed by removing quotes on
#                both days. The falsifier probes showed that it under-reads, even
#                below zero, because the degraded atom has its own day-to-day
#                error. That design is not used (preregistration.md §9).
#   block bootstrap  redraw runs of 20 consecutive sessions with replacement,
#                recompute the statistic, repeat 10,000 times; the spread of the
#                results gives the bounds. Runs keep the day-to-day
#                dependence that a one-day-at-a-time redraw would break.
#   bounds       lo = the 0.05/12 quantile of the 10,000 results (one-sided,
#                Bonferroni over the 12 rules: a FAULT anywhere is claimed at
#                level 0.05 overall); hi = the 0.95 quantile (one-sided 95%:
#                "no fault" is claimed only when every rule clears, which
#                needs no correction, the intersection-union principle).
#                Both are then widened around the point by INFLATE[rule]: on
#                12 synthetic seeds with no fault, the point moved more from
#                seed to seed than the bootstrap said (calib.py).
# =============================================================================

import bisect
import math
from collections import Counter
from contextlib import contextmanager
from dataclasses import replace

import numpy as np

from earnings_vol.measures import chain, forward, tables, termstructure

# Pre-registered constants (preregistration.md §3 and §5).
THRESHOLD_SHARE = 0.10        # rule (c): a component that alone carries >= 10% of the variance is a defect
YAHOO_LINE_BP = 10.0          # rule (b), ADR 0003 "How we'll know it's wrong"
TRUTH_TOL = 1e-6              # rule (b), ADR 0003 synthetic-truth falsifier
N_C_RULES = 12                # rule (c): 4 statistics (forward, filter, strike, roll) x 3 names, Bonferroni
ALPHA = 0.05
BLOCK = 20
REPS = 10_000
SEED = 20261117
INJECT_DRAWS = 20
MIN_OBS = 100                 # fewer observations: UNCLEAR
MAX_DROP_SHARE = 0.20         # more than 20% of candidate observations unusable: UNCLEAR
MIN_GROUP = 30                # switch excess: fewer than 30 changes in the group or in the base: UNCLEAR
ROBUST_BLOCK = 60             # preregistration.md §10: the robustness rerun uses longer blocks, never shorter
# Bootstrap widening per rule: sd of the point over 12 null seeds / mean bootstrap sd (calib.py, calib.out),
# applied only where above 1. Fixed on 2026-11-17 before any real-data value was read.
INFLATE = {"filter": 1.1, "forward": 1.35, "roll_iv": 1.2, "strike": 1.35}
RULES_C = ("forward", "filter", "strike", "roll_iv")
RULES_ALL = ("diff", "truth", "yahoo") + RULES_C


# --- the package's code path, one expiry and one session at a time --------------------------

def next_anchor(panel, day):
    return tables.neighbours(panel.anchors, day)[0]


def atom(panel, day, exp, q, p):
    """The chain_expiry row of one expiry, from tables.chain_rows (None when the expiry is gone)."""
    rows = tables.chain_rows(panel.name, day, day, False, {exp: q}, panel.rate[day], panel.sessions,
                             next_anchor(panel, day), p)
    return rows[0] if rows else None


def usable_row(row, tp) -> bool:
    return row is not None and row["status"] == "ok" and row["tau_sessions"] >= tp.tau_min_sessions


def day_row(panel, day, rows, tp):
    """The iv_daily row of one session from its chain_expiry rows (tables.iv_daily_row)."""
    return tables.iv_daily_row(panel.name, day, day, panel.status[day], [r for r in rows if r is not None],
                               panel.anchors, panel.sessions, tp)


def usable_list(rows, tp):
    return [termstructure.Expiry(r["expiration"], r["tau_sessions"], r["w_atm"], r["iv_atm"],
                                 bool(r["spans_next_event"])) for r in rows if usable_row(r, tp)]


class Cache:
    """Actual atoms and day rows, computed once per (session, expiry)."""

    def __init__(self, panel, p, tp):
        self.panel, self.p, self.tp = panel, p, tp
        self._atoms, self._days = {}, {}

    def atoms(self, day):
        if day not in self._atoms:
            q = self.panel.quotes.get(day, {})
            self._atoms[day] = {e: atom(self.panel, day, e, q[e], self.p) for e in sorted(q)}
        return self._atoms[day]

    def day(self, day):
        if day not in self._days:
            self._days[day] = day_row(self.panel, day, list(self.atoms(day).values()), self.tp)
        return self._days[day]


# --- the sample -------------------------------------------------------------------------------

def event_zone(panel) -> set:
    """Sessions from day -1 to day +1 of every anchor (preregistration.md §2)."""
    z = set()
    for a in panel.anchors:
        for k in (-1, 0, 1):
            try:
                z.add(panel.sessions.shift(a.day0, k))
            except (ValueError, KeyError):
                pass
    return z


def changes(panel):
    """[(t-1, t)]: consecutive sessions of the window, both snapshots ok, neither in the event zone."""
    zone, out, why = event_zone(panel), [], Counter()
    for a, b in zip(panel.days[:-1], panel.days[1:]):
        if panel.sessions.between(a, b) != 1:
            why["not_consecutive"] += 1
        elif panel.status.get(a) != "ok" or panel.status.get(b) != "ok":
            why["snapshot_not_ok"] += 1
        elif a in zone or b in zone:
            why["event_zone"] += 1
        else:
            out.append((a, b))
    return out, why


# --- two days of one expiry on the same strikes ---------------------------------------------

def align(qa, qb):
    """Both expiries' quotes on the union of their strikes; a strike absent on a day is NaN there."""
    ks = np.union1d(qa.strike, qb.strike).astype(float)

    def lift(q):
        pos = np.searchsorted(ks, q.strike)

        def col(v):
            o = np.full(len(ks), np.nan)
            o[pos] = v
            return o
        return chain.ExpiryQuotes(ks, col(q.call_bid), col(q.call_ask), col(q.put_bid), col(q.put_ask),
                                  col(q.call_vol), col(q.put_vol))
    return lift(qa), lift(qb)


# --- forward noise injection ------------------------------------------------------------------

@contextmanager
def forward_shift(eps_box: dict):
    """While active, the forward of every atom is multiplied by exp(eps_box['eps'])."""
    inner = forward.forward_from_pairs

    def shifted(*a, **k):
        r = inner(*a, **k)
        if r is None or eps_box.get("eps") is None:
            return r
        f, n, disp = r
        return f * math.exp(eps_box["eps"]), n, disp
    forward.forward_from_pairs = shifted
    try:
        yield
    finally:
        forward.forward_from_pairs = inner


def _eps(sigma_f, day, exp, draw, common=False):
    """One draw of the injected forward error. common=True: the same error for every expiry of the session
    (keyed by session and draw only), the common-mode sensitivity of preregistration.md §11."""
    key = [SEED, 7, day.toordinal(), draw] if common else [SEED, day.toordinal(), exp.toordinal(), draw]
    return float(np.random.default_rng(key).normal(0.0, sigma_f))


# --- observations -----------------------------------------------------------------------------

def _ln_iv(row):
    return math.log(row["iv_atm"])


def _listed(b, a):
    return np.isfinite(b) & np.isfinite(a)


def strike_change(qa, qb, ra, rb, p):
    """What changed the inputs of one expiry's ATM estimate between two days (both atoms ok).

    None: nothing (same bracket strikes and method, and, when either day used the quadratic, no
    listing or filter change inside the quadratic windows). Otherwise the first that applies:
      'listing'  a leg inside the span is listed on one day only;
      'filter'   a leg inside the span is listed on both days and passes forward.quote_ok on one only;
      'other'    the bracket or the method changed for another reason (F crossed a strike, the OTM
                 leg flipped side, a no-arbitrage bound or the root search failed on one day).
    The span: the union of both days' brackets [strike_lo, strike_hi], or, when either day used the
    quadratic, the union of both days' windows |ln K/F| <= quadratic_max_sd sqrt(w_atm)."""
    same = (ra["strike_lo"], ra["strike_hi"], ra["atm_method"]) == (rb["strike_lo"], rb["strike_hi"], rb["atm_method"])
    quad = "quadratic" in (ra["atm_method"], rb["atm_method"])
    if same and not quad:
        return None
    if quad:
        ends = [r["forward"] * math.exp(sg * p.quadratic_max_sd * math.sqrt(r["w_atm"])) for r in (ra, rb)
                for sg in (-1.0, 1.0)]
        lo, hi = min(ends), max(ends)
    else:
        lo, hi = min(ra["strike_lo"], rb["strike_lo"]), max(ra["strike_hi"], rb["strike_hi"])
    a, b = align(qa, qb)
    inside = (a.strike >= lo) & (a.strike <= hi)
    legs = ((a.call_bid, a.call_ask, b.call_bid, b.call_ask), (a.put_bid, a.put_ask, b.put_bid, b.put_ask))
    if any(np.any(inside & (_listed(ba, aa) != _listed(bb, ab))) for ba, aa, bb, ab in legs):
        return "listing"
    for ba, aa, bb, ab in legs:
        both = _listed(ba, aa) & _listed(bb, ab)
        oka = forward.quote_ok(ba, aa, p.min_mid, p.max_rel_spread)
        okb = forward.quote_ok(bb, ab, p.min_mid, p.max_rel_spread)
        if np.any(inside & both & (oka != okb)):
            return "filter"
    return None if same else "other"


def strike_obs(cache, chg):
    """Rule (c), strikes and filter, on fixed-expiry daily IV changes.

    One observation per (change, expiry e usable on both days, with at least one other such expiry):
    y = change of ln iv_atm(e); cause = strike_change(...); u = y - (change of ln iv_atm(ref)), which
    removes the move common to the expiries, with two choices of ref (nearest tau, ties: the longer):
      u_clean  ref = an other expiry whose own cause is None (its noise is then the same in every
               group); None when there is no such expiry;
      u_any    ref = any other expiry (no observation lost).
    The clean reference decides; NO FAULT also needs the any-reference version to clear
    (preregistration.md §6). Also returns causes {(t, expiry): cause} for every expiry usable on both days."""
    panel, p, tp = cache.panel, cache.p, cache.tp
    out, why, causes = [], Counter(), {}
    for a, b in chg:
        ra, rb = cache.atoms(a), cache.atoms(b)
        es = [e for e in sorted(set(ra) & set(rb)) if usable_row(ra[e], tp) and usable_row(rb[e], tp)]
        y = {e: _ln_iv(rb[e]) - _ln_iv(ra[e]) for e in es}
        cause = {e: strike_change(panel.quotes[a][e], panel.quotes[b][e], ra[e], rb[e], p) for e in es}
        causes.update({(b, e): c for e, c in cause.items()})
        for e in es:
            others = [x for x in es if x != e]
            if not others:
                why["no_other_expiry"] += 1
                continue
            te = rb[e]["tau_sessions"]
            near = lambda xs: min(xs, key=lambda x: (abs(rb[x]["tau_sessions"] - te), -rb[x]["tau_sessions"]))
            clean = [x for x in others if cause[x] is None]
            if not clean:
                why["no_clean_reference"] += 1
            out.append({"t": b, "exp": e, "y": y[e], "cause": cause[e],
                        "u_clean": y[e] - y[near(clean)] if clean else None, "u_any": y[e] - y[near(others)]})
    return out, why, causes


def blind_strike_obs(cache, chg, causes):
    """Descriptive (preregistration.md §11.6): strike and filter switches seen in cm30_blind_iv. One observation
    per change whose blind pair is the same on both days: y = change of ln cm30_blind_iv; cause = 'filter' if
    an expiry of the pair had a filter switch, 'strike' if it had any other switch, None if neither;
    u = y - change of ln iv_atm of the usable expiry outside the pair nearest 21 sessions (any reference:
    its own switches add the same noise to every group on average). No such expiry: left out. Pair-switch
    changes belong to the roll statistic and are left out here."""
    tp, h, out, why = cache.tp, cache.tp.cm30_horizon_sessions, [], Counter()
    for a, b in chg:
        da, db = cache.day(a), cache.day(b)
        if da["cm30_blind_iv"] is None or db["cm30_blind_iv"] is None:
            why["no_value"] += 1
            continue
        ra, rb = cache.atoms(a), cache.atoms(b)
        pa = pair_of(da, usable_list(ra.values(), tp), tp, "blind")
        pb = pair_of(db, usable_list(rb.values(), tp), tp, "blind")
        if pa != pb or not pa:
            why["pair_switch"] += 1
            continue
        cs = [causes.get((b, e), "missing") for e in pa]
        if "missing" in cs:
            why["pair_not_usable_both_days"] += 1
            continue
        refs = [e for e in set(ra) & set(rb) if e not in pa and usable_row(ra[e], tp) and usable_row(rb[e], tp)]
        if not refs:
            why["no_reference"] += 1
            continue
        ref = min(refs, key=lambda e: (abs(rb[e]["tau_sessions"] - h), e))
        y = math.log(db["cm30_blind_iv"]) - math.log(da["cm30_blind_iv"])
        cause = "filter" if "filter" in cs else ("strike" if any(c is not None for c in cs) else None)
        out.append({"t": b, "y": y, "u": y - (_ln_iv(rb[ref]) - _ln_iv(ra[ref])), "cause": cause})
    return out, why


def forward_pairs(cache, chg):
    """d = dln F(e1) - dln F(e2) for every pair of expiries usable on both days (rule (c), forward), when
    no ex-dividend session of panel.exdiv lies in (e1, e2]: across an ex-date the two forwards differ by a
    dividend forecast that can really change from day to day. Under independent forward errors of sd
    sigma_f, var(d) = 4 sigma_f^2. Other true changes of the carry between the expiries (rate, borrow)
    remain in d, so sigma_f is an upper bound of the noise and the forward share leans toward FAULT."""
    tp, out = cache.tp, []
    exdiv = sorted(cache.panel.exdiv)
    for a, b in chg:
        ra, rb = cache.atoms(a), cache.atoms(b)
        es = [e for e in sorted(set(ra) & set(rb)) if usable_row(ra[e], tp) and usable_row(rb[e], tp)]
        for i in range(len(es)):
            for j in range(i + 1, len(es)):
                e1, e2 = es[i], es[j]
                if any(e1 < x <= e2 for x in exdiv):
                    continue
                d = (math.log(rb[e1]["forward"] / ra[e1]["forward"]) - math.log(rb[e2]["forward"] / ra[e2]["forward"]))
                out.append({"t": b, "d": d})
    return out


def forward_injection(cache, chg, sigma_f, draws=INJECT_DRAWS, common=False):
    """Rule (c), forward: add an independent forward error eps ~ N(0, sigma_f^2) to every atom on every
    day and record how far each fixed-expiry change moves (resp = y_eps - y0), per draw.
    Also (descriptive): the same draws pushed through tables.iv_daily_row, so the response of the
    30-day series cm30_iv and cm30_blind_iv to the same forward noise. Returns (fixed, day_level)."""
    panel, p, tp = cache.panel, cache.p, cache.tp
    box, pert, out, pday = {}, {}, [], {}

    def patom(day, e, k):
        key = (day, e, k)
        if key not in pert:
            box["eps"] = _eps(sigma_f, day, e, k, common)
            pert[key] = atom(panel, day, e, panel.quotes[day][e], p)
            box["eps"] = None
        return pert[key]
    with forward_shift(box):
        for a, b in chg:
            ra, rb = cache.atoms(a), cache.atoms(b)
            for e in sorted(set(ra) & set(rb)):
                if not (usable_row(ra[e], tp) and usable_row(rb[e], tp)):
                    continue
                y0 = _ln_iv(rb[e]) - _ln_iv(ra[e])
                resp = []
                for k in range(draws):
                    xa, xb = patom(a, e, k), patom(b, e, k)
                    resp.append(_ln_iv(xb) - _ln_iv(xa) - y0 if usable_row(xa, tp) and usable_row(xb, tp) else None)
                out.append({"t": b, "exp": e, "y0": y0, "resp": resp})

        def pday_row(day, k):
            if (day, k) not in pday:
                rows = [patom(day, e, k) for e in sorted(panel.quotes[day])]
                pday[(day, k)] = day_row(panel, day, rows, tp)
            return pday[(day, k)]
        day_level = {}
        for col in ("cm30_iv", "cm30_blind_iv"):
            obs = []
            for a, b in chg:
                da, db = cache.day(a), cache.day(b)
                if da[col] is None or db[col] is None:
                    continue
                y0 = math.log(db[col]) - math.log(da[col])
                resp = []
                for k in range(draws):
                    xa, xb = pday_row(a, k)[col], pday_row(b, k)[col]
                    resp.append(math.log(xb) - math.log(xa) - y0 if xa and xb else None)
                obs.append({"t": b, "y0": y0, "resp": resp})
            day_level[col] = obs
    return out, day_level


def lag1_noise_share(cache, chg, col):
    """Descriptive: -2 x the lag-1 autocorrelation of the daily changes of ln col, over pairs of
    adjacent changes of the sample. If our series = truth + independent day noise, and the true
    changes are not autocorrelated, the noise share of var(changes) is -2 rho1."""
    d = {}
    for a, b in chg:
        va, vb = cache.day(a)[col], cache.day(b)[col]
        if va and vb:
            d[b] = (a, math.log(vb) - math.log(va))
    x, y, t = [], [], []
    for b, (a, yb) in d.items():
        if a in d:
            x.append(d[a][1])
            y.append(yb)
            t.append(b)
    return t, np.array(x), np.array(y)


def roll_obs(cache, chg, series="iv"):
    """Rule (c), interpolation in tau (series 'iv' = cm30_iv, the rule; 'blind' = cm30_blind_iv, descriptive).

    Per change: y = the actual change of ln cm30; ref = the usable expiry listed on both days with the
    largest tau (it never rolls between the two days); u = y - (change of ln iv_atm of ref), the part of
    the 30-day change that the day's move of a continuing expiry does not explain; switched = the
    expiries the interpolation used differ between the two days. A change of pair that releases a
    persistent per-expiry bias shows up as extra variance of u on switch days."""
    tp, h = cache.tp, cache.tp.cm30_horizon_sessions
    col = "cm30_iv" if series == "iv" else "cm30_blind_iv"
    out, why = [], Counter()
    for a, b in chg:
        da, db = cache.day(a), cache.day(b)
        if da[col] is None or db[col] is None:
            why["no_value"] += 1
            continue
        ca = da["sessions_to_next_event"] is not None and da["sessions_to_next_event"] <= h
        cb = db["sessions_to_next_event"] is not None and db["sessions_to_next_event"] <= h
        if series == "iv" and ca != cb:
            why["class_switch"] += 1
            continue
        ra, rb = cache.atoms(a), cache.atoms(b)
        common = [e for e in set(ra) & set(rb) if usable_row(ra[e], tp) and usable_row(rb[e], tp)]
        if not common:
            why["no_common_expiry"] += 1
            continue
        ref = max(common, key=lambda e: (rb[e]["tau_sessions"], e))
        y = math.log(db[col]) - math.log(da[col])
        u = y - (_ln_iv(rb[ref]) - _ln_iv(ra[ref]))
        pa = pair_of(da, usable_list(ra.values(), tp), tp, series)
        pb = pair_of(db, usable_list(rb.values(), tp), tp, series)
        out.append({"t": b, "y": y, "u": u, "switched": pa != pb})
    return out, why


def pair_of(drow, usable, tp, series):
    """The expirations the interpolation used on a day (cm30_exp_lo/hi, or termstructure.interpolate's pair)."""
    if series == "iv":
        return frozenset(x for x in (drow["cm30_exp_lo"], drow["cm30_exp_hi"]) if x is not None)
    r = termstructure.interpolate(usable, tp.cm30_horizon_sessions, tp.cm30_max_extrap_sessions)
    if r is not None:
        return frozenset((r[1].expiration, r[2].expiration))
    return frozenset(e.expiration for e in usable) if len(usable) == 1 else frozenset()


def yahoo_obs(cache, chg):
    """Rule (b), forward: d = parity-forward daily return - independent close-to-close return (ADR 0003 §e
    applied to every change of the sample). The expiry is the shortest one usable on t-1 that is also ok
    on t; the carry uses t-1's rate and the calendar days between the sessions. Ex-dividend sessions skip."""
    panel, tp, out = cache.panel, cache.tp, []
    for a, b in chg:
        if b in panel.exdiv or a not in panel.close or b not in panel.close:
            continue
        ra, rb = cache.atoms(a), cache.atoms(b)
        es = sorted((r["tau_sessions"], e) for e, r in ra.items() if usable_row(r, tp))
        e = next((x for _, x in es if x in rb and rb[x] is not None and rb[x]["status"] == "ok"), None)
        if e is None:
            continue
        rf = math.log(rb[e]["forward"] / ra[e]["forward"]) + panel.rate[a] * (b - a).days / 365.0
        ry = math.log(panel.close[b] / panel.close[a])
        out.append({"t": b, "d_bp": (rf - ry) * 1e4})
    return out


# --- the calendar and the events, derived here and not taken from the package ---------------------

def _missing(x):
    return x is None or x != x                    # None, NaN or NaT


class Clock:
    """tau and session counts from a sorted list of XNYS sessions (exchange_calendars), not the package's."""

    def __init__(self, xnys):
        self.x = list(xnys)
        self.set = set(self.x)

    def as_of(self, d):
        if not self.x[0] <= d <= self.x[-1]:
            raise ValueError(f"{d} is outside the calendar list ({self.x[0]} to {self.x[-1]}); extend xnys")
        return d if d in self.set else self.x[bisect.bisect_left(self.x, d) - 1]

    def count(self, a, b):                        # sessions in (a, b]
        return bisect.bisect_right(self.x, b) - bisect.bisect_right(self.x, a)

    def tau(self, day, e):
        return self.count(day, self.as_of(e))

    def on_or_after(self, d):
        self.as_of(d)
        return self.x[bisect.bisect_left(self.x, d)]

    def after(self, d):
        self.as_of(d)
        return self.x[bisect.bisect_right(self.x, d)]


def own_events(panel, clock):
    """[(day0, spans_from)] sorted, from panel.events (the events table) and the calendar list:
    day0 = day0_session, else the first session after the announcement date (data model §3.7);
    spans_from = the first session on or after the announcement date (ADR 0003 amendment 3: an expiry on
    the day of an after-close announcement spans). Rows with exclusion_reason 'duplicate_row' are left
    out. An empty table is an error: the checks never fall back to the package's anchors."""
    if not panel.events:
        raise ValueError(f"{panel.name}: panel.events is empty; the checks need the events table")
    out = []
    for ev in panel.events:
        if ev.get("exclusion_reason") == "duplicate_row":
            continue
        a = ev["announce_date_used"]
        d0 = clock.after(a) if _missing(ev["day0_session"]) else ev["day0_session"]
        out.append((d0, clock.on_or_after(a)))
    return sorted(out)


def _next_event(own, day):
    return next((x for x in own if x[0] > day), None)


# --- rule (b): the ADR's synthetic-truth falsifier on the panel's own grids ---------------------

def synthetic_truth(cache, xnys, s2=0.25 ** 2 / 252.0, ev=0.0015):
    """Replace every quote of the panel by a two-component, flat-smile surface (w = s2 tau + E [spans])
    on the SAME strikes, legs, expiries, sessions and events; run the package; compare E, sigma_d,
    cm30_iv, cm30_blind_iv and sessions_to_next_event with the truth. tau, DF, the next event and its class
    come from the calendar list `xnys` and panel.events (own_events), not from the package, so a wrong
    count in the package cannot cancel out. The cm30_blind_iv truth is the ADR §b interpolation (all
    usable expiries) of the TRUE w's, done by ref_spec._interp. Returns the largest absolute errors (a
    sessions_to_next_event that is null on one side only counts as 999) and the counts."""
    import ref_spec
    panel, p, tp = cache.panel, cache.p, cache.tp
    clock = Clock(xnys)
    own = own_events(panel, clock)
    worst = {"event_var": 0.0, "sigma_d_iv": 0.0, "cm30_iv": 0.0, "cm30_blind_iv": 0.0,
             "sessions_to_next_event": 0.0}
    n = Counter()
    h, max_ex = tp.cm30_horizon_sessions, tp.cm30_max_extrap_sessions
    for day in panel.days:
        if panel.status.get(day) != "ok" or day not in panel.quotes:
            continue
        nxt = _next_event(own, day)
        real = cache.atoms(day)
        spots = [r["forward"] * r["df"] for r in real.values() if r is not None and r["forward"] is not None]
        if not spots:
            n["no_forward_day"] += 1
            continue
        s = float(np.median(spots))
        rows, true_w = [], {}
        for e, q in panel.quotes[day].items():
            if e <= day:
                continue
            tau = clock.tau(day, e)
            if tau < 1:
                continue
            df = math.exp(-panel.rate[day] * (e - day).days / 365.0)
            spans = nxt is not None and clock.as_of(e) >= nxt[1]
            f = s / df
            w = s2 * tau + (ev if spans else 0.0)
            true_w[e] = (tau, w)
            cb, ca, pb, pa = (np.full(len(q.strike), np.nan) for _ in range(4))
            for i, k in enumerate(q.strike):
                c, pp = _price(f, float(k), w, df, True), _price(f, float(k), w, df, False)
                if np.isfinite(q.call_bid[i]) and np.isfinite(q.call_ask[i]):
                    cb[i], ca[i] = c - 0.01, c + 0.01
                if np.isfinite(q.put_bid[i]) and np.isfinite(q.put_ask[i]):
                    pb[i], pa[i] = pp - 0.01, pp + 0.01
            rows.append(atom(panel, day, e, replace(q, call_bid=cb, call_ask=ca, put_bid=pb, put_ask=pa), p))
        d = day_row(panel, day, rows, tp)
        n["days"] += 1
        ste = clock.count(day, nxt[0]) if nxt is not None else None
        if _missing(d["sessions_to_next_event"]) != (ste is None):
            worst["sessions_to_next_event"] = 999.0
        elif ste is not None:
            worst["sessions_to_next_event"] = max(worst["sessions_to_next_event"],
                                                  float(abs(d["sessions_to_next_event"] - ste)))
        contains = ste is not None and ste <= h
        if d["event_var"] is not None:
            n["event_var"] += 1
            worst["event_var"] = max(worst["event_var"], abs(d["event_var"] - ev))
        if d["sigma_d_iv"] is not None:
            n["sigma_d_iv"] += 1
            worst["sigma_d_iv"] = max(worst["sigma_d_iv"], abs(d["sigma_d_iv"] - math.sqrt(252.0 * s2)))
        if d["cm30_iv"] is not None:
            n["cm30_iv"] += 1
            truth = math.sqrt(252.0 * (s2 * h + (ev if contains else 0.0)) / h)
            worst["cm30_iv"] = max(worst["cm30_iv"], abs(d["cm30_iv"] - truth))
        usable = sorted((true_w[r["expiration"]][0], true_w[r["expiration"]][1], r["expiration"]) for r in rows
                        if r is not None and r["status"] == "ok" and r["expiration"] in true_w
                        and true_w[r["expiration"]][0] >= tp.tau_min_sessions)
        got = ref_spec._interp(usable, h, max_ex)
        wb = got[0] if got is not None else (usable[0][1] * h / usable[0][0]
                                             if len(usable) == 1 and abs(h - usable[0][0]) <= max_ex else None)
        if d["cm30_blind_iv"] is not None and wb is not None and wb > 0:
            n["cm30_blind_iv"] += 1
            worst["cm30_blind_iv"] = max(worst["cm30_blind_iv"], abs(d["cm30_blind_iv"] - math.sqrt(252.0 * wb / h)))
        elif (d["cm30_blind_iv"] is None) != (wb is None or wb <= 0):
            n["cm30_blind_iv_presence_differs"] += 1          # descriptive: presence follows the §b limits
    return worst, dict(n)


def _price(f, k, w, df, call):
    from synth import price76            # the probes' own pricer, not the package's
    return price76(f, k, w, df, call)


# --- rule (a): the second implementation against the package -----------------------------------

ATOM_EXACT = ("status", "forward_n_strikes", "n_strikes_valid", "atm_method", "strike_lo", "strike_hi")
ATOM_FLOAT = (("forward", 1e-9), ("w_atm", 1e-8), ("iv_atm", 1e-8))
DAY_EXACT = ("cm30_method", "cm30_exp_lo", "cm30_exp_hi")
DAY_FLOAT = (("cm30_iv", 1e-8), ("cm30_blind_iv", 1e-8), ("event_var", 1e-8), ("sigma_d_iv", 1e-8))
BOUNDARY = 1e-9                       # an input this close (relative) to a threshold: "boundary"
ATOM_POINTS, DAY_POINTS = ("S2", "S3", "S4"), ("S5", "S6")


def _differs(x, y, tol=None):
    if _missing(x) or _missing(y):
        return _missing(x) != _missing(y)
    if tol is None:
        return x != y
    return abs(x - y) > tol * max(abs(y), 1e-12)


def _atom_bad(r, ref):
    return ([f for f in ATOM_EXACT if _differs(r[f], ref[f])]
            + [f for f, tol in ATOM_FLOAT if _differs(r[f], ref[f], tol)])


def _day_bad(d, ref):
    return ([f for f in DAY_EXACT if _differs(d[f], ref[f])]
            + [f for f, tol in DAY_FLOAT if _differs(d[f], ref[f], tol)])


def _accepted(recs, points):
    """The (S-point, alternative) pairs the package is consistent with: at least one mismatching record where
    the point matters, every such record is removed by this alternative, and no MATCHING record has the point
    mattering (there the package did what the default does)."""
    import ref_spec
    out = set()
    for s_ in points:
        rel = [x for x in recs if s_ in x["matters"]]
        if not rel or any(not x["bad"] for x in rel):
            continue
        for alt in ref_spec.ALTERNATIVES[s_]:
            if all((s_, alt) in x["explained"] for x in rel):
                out.add((s_, alt))
    return out


def differential(cache, ref_p, xnys):
    """Rule (a). Compare every atom and every ok session with ref_spec, which reads its own atoms, tau from
    `xnys` (a sorted list of XNYS sessions from exchange_calendars), DF from r_cont, and spans and the next
    event from panel.events (own_events), not from the package.
    Atom fields: tau_sessions, df, spans_next_event (the calendar; never tagged); status, forward_n_strikes,
    n_strikes_valid, atm_method, strike_lo, strike_hi (exact); forward (1e-9 relative), w_atm, iv_atm (1e-8).
    Day fields: sessions_to_next_event, cm30_method, cm30_exp_lo, cm30_exp_hi (exact); cm30_iv, cm30_blind_iv,
    event_var, sigma_d_iv (1e-8 relative).
    Each mismatching atom or day gets a tag from the code, first that applies: none for a calendar field;
    'upstream' (a day whose atoms already mismatch); 'S1' (a duplicate strike); 'S2'..'S6' (an alternative
    accepted by _accepted removes it); 'S7' (the reference met w* <= 0); 'boundary' (an input within 1e-9,
    relative, of a threshold). A mismatch with no tag is a bug candidate: verdict MISMATCH. Tagged ones are
    'unspecified'. Every record keeps its margin, the distance to the nearest decision boundary."""
    import ref_spec
    panel, tp = cache.panel, cache.tp
    clock = Clock(xnys)
    own = own_events(panel, clock)
    n = Counter()
    atoms, days = [], []
    for day in panel.days:
        if panel.status.get(day) != "ok" or day not in panel.quotes:
            continue
        rows = cache.atoms(day)
        nxt = _next_event(own, day)
        mine, day_atom_bad = [], False
        for e, q in panel.quotes[day].items():
            r = rows.get(e)
            if r is None:
                continue
            n["atoms"] += 1
            tau = clock.tau(day, e)
            df = math.exp(-panel.rate[day] * (e - day).days / 365.0)
            spans = nxt is not None and clock.as_of(e) >= nxt[1]
            ref = ref_spec.ref_atom(q.strike, q.call_bid, q.call_ask, q.put_bid, q.put_ask, df, tau, ref_p)
            cal = [f for f, bad in (("tau_sessions", r["tau_sessions"] != tau), ("df", abs(r["df"] - df) > 1e-15),
                                    ("spans_next_event", bool(r["spans_next_event"]) != spans)) if bad]
            bad = cal + _atom_bad(r, ref)
            rec = {"day": day, "exp": e, "bad": bad, "calendar": bool(cal), "matters": ref["matters"],
                   "dup": ref["duplicate_strike"], "margin": ref["margin"], "explained": set()}
            if bad and not cal:
                for s_ in ATOM_POINTS:
                    if s_ in ref["matters"]:
                        for alt in ref_spec.ALTERNATIVES[s_]:
                            x = ref_spec.ref_atom(q.strike, q.call_bid, q.call_ask, q.put_bid, q.put_ask, df, tau,
                                                  ref_p, {s_: alt})
                            if not _atom_bad(r, x):
                                rec["explained"].add((s_, alt))
            atoms.append(rec)
            day_atom_bad |= bool(bad)
            if ref["status"] == "ok" and tau >= ref_p.tau_min:
                mine.append((tau, ref["w_atm"], e, spans))
        d = cache.day(day)
        n["days"] += 1
        ste = clock.count(day, nxt[0]) if nxt is not None else None
        ref = ref_spec.ref_cm30(mine, ste, ref_p)
        cal = ["sessions_to_next_event"] if _differs(d["sessions_to_next_event"], ste) else []
        bad = cal + _day_bad(d, ref)
        rec = {"day": day, "exp": None, "bad": bad, "calendar": bool(cal), "matters": ref["matters"],
               "upstream": day_atom_bad, "s7": ref["s7"], "margin": math.nan, "explained": set()}
        if bad and not cal and not day_atom_bad:
            for s_ in DAY_POINTS:
                if s_ in ref["matters"]:
                    for alt in ref_spec.ALTERNATIVES[s_]:
                        if not _day_bad(d, ref_spec.ref_cm30(mine, ste, ref_p, {s_: alt})):
                            rec["explained"].add((s_, alt))
        days.append(rec)
    acc = _accepted(atoms, ATOM_POINTS) | _accepted(days, DAY_POINTS)
    mism, tags, out = Counter(), Counter(), []
    for rec in atoms + days:
        if not rec["bad"]:
            continue
        mism.update(rec["bad"])
        tag = None
        if rec["calendar"]:
            tag = None
        elif rec.get("upstream"):
            tag = "upstream"
        elif rec.get("dup"):
            tag = "S1"
        elif rec["explained"] & acc:
            tag = sorted(rec["explained"] & acc)[0][0]
        elif rec.get("s7"):
            tag = "S7"
        elif rec["margin"] < BOUNDARY:
            tag = "boundary"
        tags[tag or "untagged"] += 1
        out.append({"day": str(rec["day"]), "exp": str(rec["exp"]) if rec["exp"] else "-", "fields": rec["bad"],
                    "tag": tag or "untagged", "margin": rec["margin"]})
    untagged = tags.get("untagged", 0)
    n["mismatching_records"] = len(out)
    examples = [x for x in out if x["tag"] == "untagged"][:8] + [x for x in out if x["tag"] != "untagged"][:4]
    return {"mismatches": dict(mism), "tags": dict(tags), "untagged": untagged,
            "unspecified": len(out) - untagged, "accepted_alternatives": sorted(acc), "n": dict(n),
            "examples": examples, "verdict": "MISMATCH" if untagged else "MATCH"}


# --- bootstrap and verdicts ---------------------------------------------------------------------

def block_counts(n_axis, block=BLOCK, reps=REPS, seed=SEED):
    """counts[r, s] = how often session s of the axis is drawn in replicate r (moving blocks, not circular)."""
    rng = np.random.default_rng(seed)
    nb = math.ceil(n_axis / block)
    starts = rng.integers(0, n_axis - block + 1, size=(reps, nb))
    idx = (starts[:, :, None] + np.arange(block)).reshape(reps, -1)[:, :n_axis]
    counts = np.zeros((reps, n_axis), np.int32)
    np.add.at(counts, (np.repeat(np.arange(reps), idx.shape[1]), idx.ravel()), 1)
    return counts


def _bounds(reps, k_rules):
    """(lo, hi): the one-sided Bonferroni lower bound for FAULT and the one-sided 95% upper bound for
    NO FAULT (see the header). NaN replicates (an empty group in a redraw) are left out."""
    if reps is None or not np.isfinite(reps).any():
        return math.nan, math.nan
    lo, hi = np.nanquantile(reps, [ALPHA / k_rules, 1 - ALPHA])
    return float(lo), float(hi)


def interval(rule, point, reps, k_rules):
    """{lo_raw, hi_raw, lo, hi, boot_sd}: the bootstrap bounds, then widened around the point by INFLATE[rule]
    (lo = point - c (point - lo_raw), hi = point + c (hi_raw - point))."""
    lo_r, hi_r = _bounds(reps, k_rules)
    c = INFLATE.get(rule, 1.0)
    sd = float(np.nanstd(reps)) if reps is not None and np.isfinite(reps).any() else math.nan
    return {"lo_raw": lo_r, "hi_raw": hi_r, "lo": point - c * (point - lo_r), "hi": point + c * (hi_r - point),
            "boot_sd": sd, "inflate": c}


def _var(n, s, q):
    with np.errstate(divide="ignore", invalid="ignore"):
        return (q - s * s / n) / (n - 1)


def injection_stat(sess_y, y0, sess_r, resp, sess_d, d, counts):
    """Forward share = var(resp) / var(y0), scaled in each replicate by var(d)(rep) / var(d)(point), where d
    is the series that measured the injected sd (the response is linear in a small forward error).
    Returns (point, replicates)."""
    if len(y0) < 2 or len(d) < 2:
        return math.nan, None
    N = counts.shape[1]
    agg = lambda s, v: np.bincount(s, weights=v, minlength=N)
    ny, sy, qy = agg(sess_y, np.ones_like(y0)), agg(sess_y, y0), agg(sess_y, y0 * y0)
    nr, sr, qr = agg(sess_r, np.ones_like(resp)), agg(sess_r, resp), agg(sess_r, resp * resp)
    nd, sd, qd = agg(sess_d, np.ones_like(d)), agg(sess_d, d), agg(sess_d, d * d)
    v_d = _var(nd.sum(), sd.sum(), qd.sum())
    point = _var(nr.sum(), sr.sum(), qr.sum()) / _var(ny.sum(), sy.sum(), qy.sum())
    reps = (_var(counts @ nr, counts @ sr, counts @ qr) / _var(counts @ ny, counts @ sy, counts @ qy)
            * _var(counts @ nd, counts @ sd, counts @ qd) / v_d)
    return float(point), reps


def excess_stat(sess, y, u, group, base, counts):
    """Switch-excess share R = (n_group / n) (var(u | group) - var(u | base)) / var(y), over all n
    observations: the share of the variance of the changes y that comes from the extra noise of the
    group's changes. Returns (point, replicates); (NaN, None) when the group or the base has < 2."""
    if group.sum() < 2 or base.sum() < 2:
        return math.nan, None
    N = counts.shape[1]
    agg = lambda s_, v: np.bincount(s_, weights=v, minlength=N)
    s_g, u_g, s_b, u_b = sess[group], u[group], sess[base], u[base]
    ng, sg, qg = agg(s_g, np.ones_like(u_g)), agg(s_g, u_g), agg(s_g, u_g * u_g)
    nb, sb, qb = agg(s_b, np.ones_like(u_b)), agg(s_b, u_b), agg(s_b, u_b * u_b)
    ny, sy, qy = agg(sess, np.ones_like(y)), agg(sess, y), agg(sess, y * y)

    def r(ng_, sg_, qg_, nb_, sb_, qb_, ny_, sy_, qy_):
        return ng_ / ny_ * (_var(ng_, sg_, qg_) - _var(nb_, sb_, qb_)) / _var(ny_, sy_, qy_)
    point = r(*(x.sum() for x in (ng, sg, qg, nb, sb, qb, ny, sy, qy)))
    with np.errstate(divide="ignore", invalid="ignore"):
        reps = r(*(counts @ x for x in (ng, sg, qg, nb, sb, qb, ny, sy, qy)))
    return float(point), reps


def lag1_stat(sess, x, y, counts):
    """-2 corr(x, y) and a plain 95% block-bootstrap interval (descriptive)."""
    if len(x) < 3:
        return math.nan, math.nan, math.nan
    N = counts.shape[1]
    agg = lambda v: np.bincount(sess, weights=v, minlength=N)
    parts = [agg(np.ones_like(x)), agg(x), agg(y), agg(x * x), agg(y * y), agg(x * y)]

    def r(n, sx, sy, qx, qy, qxy):
        with np.errstate(divide="ignore", invalid="ignore"):
            return -2.0 * (qxy - sx * sy / n) / np.sqrt((qx - sx * sx / n) * (qy - sy * sy / n))
    point = float(r(*(v.sum() for v in parts)))
    reps = r(*(counts @ v for v in parts))
    lo, hi = np.nanquantile(reps, [0.025, 0.975])
    return point, float(lo), float(hi)


def median_abs_stat(sess, x, counts):
    """Median |x| and a plain 95% block-bootstrap interval (reported beside the ADR's point rule)."""
    if len(x) == 0:
        return math.nan, math.nan, math.nan
    ax = np.abs(x)
    point = float(np.median(ax))
    order = np.argsort(sess, kind="mergesort")
    s_sorted, a_sorted = sess[order], ax[order]
    meds = np.empty(counts.shape[0])
    for r in range(counts.shape[0]):
        w = counts[r, s_sorted]
        meds[r] = np.median(np.repeat(a_sorted, w)) if w.sum() else np.nan
    lo, hi = np.nanquantile(meds, [0.025, 0.975])
    return point, float(lo), float(hi)


def verdict_c(point, lo, hi, n_obs, drop_share):
    if n_obs < MIN_OBS:
        return "UNCLEAR (too few observations)"
    if drop_share > MAX_DROP_SHARE:
        return "UNCLEAR (too many unusable counterfactuals)"
    if lo > THRESHOLD_SHARE:
        return "FAULT"
    if hi < THRESHOLD_SHARE:
        return "NO FAULT"
    return "UNCLEAR"


def group_upper_bound(y, u, group, base):
    """sum over the group of (u - mean u of the base)^2 / ((n - 1) var(y)): the share the group would
    carry if ALL of its spread were extra noise. An upper bound of the switch-excess share."""
    if not group.any():
        return 0.0
    c = u[base].mean() if base.any() else 0.0
    return float(((u[group] - c) ** 2).sum() / ((len(y) - 1) * np.var(y, ddof=1)))


def verdict_excess(pt, lo, hi, n_obs, drop_share, n_group, n_base, ub):
    """verdict_c, plus: too few changes in the base -> UNCLEAR; too few in the group -> NO FAULT when
    even the group's whole spread is under the threshold (ub < 0.10), else UNCLEAR."""
    if n_obs >= MIN_OBS and drop_share <= MAX_DROP_SHARE:
        if n_base < MIN_GROUP:
            return "UNCLEAR (too few changes in the base)"
        if n_group < MIN_GROUP:
            return "NO FAULT" if ub < THRESHOLD_SHARE else "UNCLEAR (too few changes in the group)"
    return verdict_c(pt, lo, hi, n_obs, drop_share)


def _head(v):
    return v.split(" (")[0]


def _inject_block(obs, draws, axis, sd_sess, sd_vals, counts, k_rules, rule):
    """The injection share of a list of {t, y0, resp[draws]}: the observations whose draws are all usable."""
    full = [o for o in obs if all(r is not None for r in o["resp"])]
    sy = np.array([axis[o["t"]] for o in full], dtype=np.int64)
    y0 = np.array([o["y0"] for o in full])
    resp = np.array([r for o in full for r in o["resp"]])
    pt, reps = injection_stat(sy, y0, np.repeat(sy, draws), resp, sd_sess, sd_vals, counts)
    return {"n": len(full), "dropped": len(obs) - len(full), "share": pt,
            **interval(rule, pt, reps, k_rules)}, reps, 1 - len(full) / max(len(obs), 1)


# --- one name, every rule ------------------------------------------------------------------------

def run_name(panel, p, tp, ref_p=None, xnys=None, counts=None, draws=INJECT_DRAWS, k_rules=N_C_RULES,
             with_truth=True, with_diff=True, with_common=True):
    """Every rule and descriptive number of preregistration.md §5, §6 and §11 for one name. Rule (a) needs
    ref_p and (a) and (b, truth) need xnys: a missing one is an error, never a silent skip."""
    if with_diff and ref_p is None:
        raise ValueError("rule (a) needs ref_p (ref_spec.load_params); pass with_diff=False to skip it on purpose")
    if (with_diff or with_truth) and xnys is None:
        raise ValueError("rules (a) and (b) need xnys, the exchange_calendars session list")
    cache = Cache(panel, p, tp)
    chg, why = changes(panel)
    axis = {d: i for i, d in enumerate(panel.days)}
    if counts is None:
        counts = block_counts(len(panel.days))
    res = {"n_changes": len(chg), "excluded": dict(why)}
    keep = {}                                  # replicates for the joint bootstrap of §11

    # (c) strikes and filter, on fixed-expiry changes: switch excess against changes with no switch, with
    # the clean reference (decides) and the any reference (NO FAULT also needs it to clear).
    so, swhy, causes = strike_obs(cache, chg)
    res["_y_strike"] = {(o["t"], o["exp"]): o["y"] for o in so}
    for name, cs in (("strike", ("listing", "filter", "other")), ("filter", ("filter",)),
                     ("listing", ("listing",)), ("other", ("other",))):
        part = {}
        for ref in ("clean", "any"):
            ok = [o for o in so if o["u_" + ref] is not None]
            s = np.array([axis[o["t"]] for o in ok], dtype=np.int64)
            y = np.array([o["y"] for o in ok])
            u = np.array([o["u_" + ref] for o in ok])
            cause = np.array([o["cause"] or "none" for o in ok])
            group, base = np.isin(cause, cs), cause == "none"
            drop = 1 - len(ok) / max(len(so) + swhy.get("no_other_expiry", 0), 1) if ref == "any" else 0.0
            excl = 1 - len(ok) / max(len(so), 1)
            pt, reps = excess_stat(s, y, u, group, base, counts) if len(ok) else (math.nan, None)
            iv_ = interval(name if name in INFLATE else "strike", pt, reps, k_rules)
            ub = group_upper_bound(y, u, group, base) if len(ok) else math.nan
            part[ref] = {"n": len(ok), "no_clean_ref_share": excl, "n_group": int(group.sum()),
                         "n_base": int(base.sum()), "share": pt, **iv_, "upper_bound": ub,
                         "verdict": verdict_excess(pt, iv_["lo"], iv_["hi"], len(ok), drop, int(group.sum()),
                                                   int(base.sum()), ub)}
        c, a = part["clean"], part["any"]
        v = c["verdict"]
        if _head(v) == "NO FAULT" and _head(a["verdict"]) != "NO FAULT":
            v = "UNCLEAR (any reference does not clear)"
        res[name] = {**c, "verdict": v, "verdict_clean": c["verdict"], "any_ref": a, "excluded": dict(swhy)}

    # (c) forward: sigma_f from cross-expiry pairs, then injection of independent errors.
    fp = forward_pairs(cache, chg)
    d = np.array([x["d"] for x in fp])
    sd = np.array([axis[x["t"]] for x in fp], dtype=np.int64)
    sigma_f = math.sqrt(np.var(d, ddof=1) / 4.0) if len(d) > 1 else float("nan")
    inj, inj_day = forward_injection(cache, chg, sigma_f, draws)
    blk, _, drop = _inject_block(inj, draws, axis, sd, d, counts, k_rules, "forward")
    res["_y_fixed"] = {(o["t"], o["exp"]): o["y0"] for o in inj}
    res["forward"] = {**blk, "sigma_f_bp": sigma_f * 1e4, "n_pairs": len(d),
                      "verdict": verdict_c(blk["share"], blk["lo"], blk["hi"], blk["n"], drop)}
    # Descriptive: the same draws at the 30-day level (§11.2).
    for col, obs_d in inj_day.items():
        blk, reps, _ = _inject_block(obs_d, draws, axis, sd, d, counts, k_rules, "forward")
        res["forward_" + col] = {**blk, "verdict": "descriptive"}
        keep["forward_" + col] = reps

    # Descriptive: -2 rho1 of the daily changes of the 30-day series (§11.4).
    for col in ("cm30_iv", "cm30_blind_iv"):
        t, x, y = lag1_noise_share(cache, chg, col)
        st = np.array([axis[v] for v in t], dtype=np.int64)
        res["lag1_" + col] = {"n": len(t), **dict(zip(("share", "lo", "hi"), lag1_stat(st, x, y, counts))),
                              "verdict": "descriptive"}

    # (c) roll on cm30_iv (rule); the same on cm30_blind_iv (descriptive).
    for series in ("iv", "blind"):
        ro, rwhy = roll_obs(cache, chg, series)
        s = np.array([axis[o["t"]] for o in ro], dtype=np.int64)
        sw = np.array([o["switched"] for o in ro], dtype=bool)
        yy, uu = np.array([o["y"] for o in ro]), np.array([o["u"] for o in ro])
        pt, reps = excess_stat(s, yy, uu, sw, ~sw, counts)
        iv_ = interval("roll_iv", pt, reps, k_rules)
        cand = len(ro) + sum(rwhy.values()) - rwhy.get("class_switch", 0)
        drop = 1 - len(ro) / max(cand, 1)
        ub = group_upper_bound(yy, uu, sw, ~sw) if len(ro) else math.nan
        v = verdict_excess(pt, iv_["lo"], iv_["hi"], len(ro), drop, int(sw.sum()), int((~sw).sum()), ub)
        res["_y_roll_" + series] = {o["t"]: o["y"] for o in ro}
        res["roll_" + series] = {"n": len(ro), "n_group": int(sw.sum()), "n_base": int((~sw).sum()),
                                 "excluded": dict(rwhy), "share": pt, **iv_, "upper_bound": ub,
                                 "verdict": v if series == "iv" else "descriptive"}
        keep["roll_" + series] = reps

    # Descriptive: strike and filter switches seen in cm30_blind_iv (§11.6).
    bo, bwhy = blind_strike_obs(cache, chg, causes)
    s = np.array([axis[o["t"]] for o in bo], dtype=np.int64)
    yy, uu = np.array([o["y"] for o in bo]), np.array([o["u"] for o in bo])
    cause = np.array([o["cause"] or "none" for o in bo])
    for name, cs in (("strike_cm30_blind_iv", ("strike", "filter")), ("filter_cm30_blind_iv", ("filter",))):
        group, base = np.isin(cause, cs), cause == "none"
        pt, reps = excess_stat(s, yy, uu, group, base, counts) if len(bo) else (math.nan, None)
        res[name] = {"n": len(bo), "n_group": int(group.sum()), "n_base": int(base.sum()), "share": pt,
                     **interval("strike", pt, reps, k_rules), "excluded": dict(bwhy), "verdict": "descriptive"}
        keep[name] = reps
    res["_y_blind"] = {}
    for a_, b_ in chg:
        va, vb = cache.day(a_)["cm30_blind_iv"], cache.day(b_)["cm30_blind_iv"]
        if va and vb:
            res["_y_blind"][b_] = math.log(vb) - math.log(va)

    # (b) forward against the independent close.
    yo = yahoo_obs(cache, chg)
    s = np.array([axis[o["t"]] for o in yo], dtype=np.int64)
    x = np.array([o["d_bp"] for o in yo])
    pt, lo, hi = median_abs_stat(s, x, counts)
    res["yahoo"] = {"n": len(yo), "median_abs_bp": pt, "lo": lo, "hi": hi,
                    "median_signed_bp": float(np.median(x)) if len(x) else None,
                    "verdict": "FAULT" if pt > YAHOO_LINE_BP else "NO FAULT"}

    # Descriptive (§11.7): a forward error COMMON to every expiry of a session is invisible to sigma_f.
    # Its size is bounded by the forward-vs-close series: d = (eps_t - eps_t-1) + other terms, so
    # var(eps) <= var(d)/2. Inject that, the same for every expiry of a session: an UPPER BOUND.
    if with_common and len(x) > 1:
        dl = x / 1e4
        sigma_c = math.sqrt(np.var(dl, ddof=1) / 2.0)
        cinj, cday = forward_injection(cache, chg, sigma_c, draws, common=True)
        blk, _, _ = _inject_block(cinj, draws, axis, s, dl, counts, k_rules, "forward")
        res["common_forward"] = {**blk, "sigma_c_bp": sigma_c * 1e4, "verdict": "descriptive (upper bound)"}
        for col, obs_d in cday.items():
            blk, _, _ = _inject_block(obs_d, draws, axis, s, dl, counts, k_rules, "forward")
            res["common_forward_" + col] = {**blk, "verdict": "descriptive (upper bound)"}

    # Descriptive (§11.6): the residual line. The shares that reach cm30_blind_iv, summed in each bootstrap
    # replicate of the same draw matrix (a joint bootstrap). Their denominators are the variances of the
    # changes in each statistic's own sample, which differ: the sum is an approximation, not an identity.
    parts = ("forward_cm30_blind_iv", "roll_blind", "strike_cm30_blind_iv")
    if all(keep.get(k) is not None for k in parts):
        tot = sum(keep[k] for k in parts)
        pt = sum(res[k]["share"] for k in parts)
        lo, hi = np.nanquantile(tot, [0.025, 0.975])
        res["blind_sum"] = {"parts": list(parts), "share": float(pt), "lo": float(lo), "hi": float(hi),
                            "lag1_cm30_blind_iv": res["lag1_cm30_blind_iv"]["share"], "verdict": "descriptive"}
    else:
        res["blind_sum"] = {"parts": list(parts), "share": math.nan, "verdict": "descriptive (a part is missing)"}

    # (b) synthetic truth on the panel's own grids.
    if with_truth:
        worst, nt = synthetic_truth(cache, xnys)
        res["truth"] = {"worst": worst, "n": nt,
                        "verdict": "FAULT" if max(worst.values()) > TRUTH_TOL else "NO FAULT"}
    # (a) the second implementation.
    if with_diff:
        res["diff"] = differential(cache, ref_p, xnys)
    return res
