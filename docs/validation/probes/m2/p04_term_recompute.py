"""p04-p08: recompute tau, spans, cm30, E, sigma_d and T1* independently of earnings_vol.measures.

Claims 4, 5, 6, 7, 8a, 8b. Sessions come from exchange_calendars XNYS directly, the next event from
the events table, the measures from ADR 0003 §0 step 5, §a, §b, §c as written there. Nothing from
earnings_vol is imported.
Run from the repository root:
  python docs/validation/probes/m2/p04_term_recompute.py <stage dir> [--mutant-tau]
--mutant-tau adds 1 to the stored tau before comparing (falsifier for claim 4).
"""
import math
import sys
from bisect import bisect_left, bisect_right
from datetime import date
from pathlib import Path

import exchange_calendars as xcals
import numpy as np
import pandas as pd

stage = Path(sys.argv[1])
ce = pd.read_parquet(stage / "chain_expiry.parquet")
iv = pd.read_parquet(stage / "iv_daily.parquet")
ev = pd.read_parquet(stage / "events.parquet")
eiv = pd.read_parquet(stage / "event_iv.parquet")
if "--mutant-tau" in sys.argv:
    ce["tau_sessions"] = ce["tau_sessions"] + 1

cal = xcals.get_calendar("XNYS", start="2016-01-04", end="2027-12-31")
S = [t.date() for t in cal.sessions]
IDX = {d: i for i, d in enumerate(S)}
early = {t.date() for t in cal.early_closes}
stab = pd.read_parquet(stage / "session.parquet")
print(f"session table == XNYS sessions: {list(stab['session_date']) == S}; early closes in XNYS {len(early)}, "
      f"is_half_day in table {int(stab['is_half_day'].sum())}")


def as_of(d):
    return d if d in IDX else S[bisect_right(S, d) - 1]


def n_between(a, b):            # sessions in (a, b], a and b sessions
    return IDX[b] - IDX[a]


fails = []

# ---- claim 4: tau --------------------------------------------------------------------------------
tau = np.array([(IDX[as_of(e)] - IDX[s]) for s, e in zip(ce["session_date"], ce["expiration"])])
# a plain count, written differently: sessions strictly after s and on or before expiry
tau2 = np.array([bisect_right(S, e) - bisect_right(S, s) for s, e in zip(ce["session_date"], ce["expiration"])])
assert (tau == tau2).all()
bad = int((ce["tau_sessions"].to_numpy() != tau).sum())
spans_half = [any(x in early for x in S[IDX[s] + 1: IDX[as_of(e)] + 1]) for s, e in zip(ce["session_date"], ce["expiration"])]
nonsession_exp = int(sum(e not in IDX for e in ce["expiration"]))
print(f"[4] tau rows {len(ce)}, mismatches {bad}; rows whose (t, expiry] holds an early close: {sum(spans_half)} "
      f"(counted as 1 each); rows whose expiration is not a session: {nonsession_exp}")
if bad:
    fails.append("4")
tcal = int(((pd.to_datetime(ce["expiration"]) - pd.to_datetime(ce["session_date"])).dt.days != ce["tau_cal_days"]).sum())
print(f"[4] tau_cal_days mismatches {tcal}")

# ---- claim 7: spans ------------------------------------------------------------------------------
anch: dict = {}
for r in ev.itertuples(index=False):
    if r.exclusion_reason == "duplicate_row":
        continue
    d0 = r.day0_session if r.day0_session is not None else S[bisect_right(S, r.announce_date_used)]
    anch.setdefault(r.security_id, []).append((d0, r.event_id, r))
for v in anch.values():
    v.sort(key=lambda x: x[0])


def nxt(sid, d, k=0):
    a = anch.get(sid, [])
    i = bisect_right([x[0] for x in a], d) + k
    return a[i] if i < len(a) else None


sp_ind, nid_ind = [], []
edge = {"amc_on_expiry_day": 0, "bmo_on_expiry_day": 0, "nonsession_expiry_eq_day0_minus": 0}
amc_rows = []
for s, e, sid in zip(ce["session_date"], ce["expiration"], ce["security_id"]):
    n = nxt(sid, s)
    sp_ind.append(None if n is None else as_of(e) >= n[0])
    nid_ind.append(None if n is None else n[1])
    if n is not None:
        r = n[2]
        if r.timing_used == "AMC" and r.announce_date_used == e and r.day0_session is not None:
            edge["amc_on_expiry_day"] += 1
            amc_rows.append((sid, s, e, n[1]))
        if r.timing_used == "BMO" and r.day0_session == e:
            edge["bmo_on_expiry_day"] += 1
st = ce["spans_next_event"].map(lambda v: None if v is None or (isinstance(v, float) and math.isnan(v)) else bool(v))
mism = sum(1 for a, b in zip(st, sp_ind) if a != b)
mism_id = sum(1 for a, b in zip(ce["next_event_id"], nid_ind) if (a if isinstance(a, str) else None) != b)
print(f"[7] spans mismatches {mism}; next_event_id mismatches {mism_id}; edge counts {edge}")
if mism or mism_id:
    fails.append("7")
# an expiry on the AMC announcement date that is usable (tau >= 5) at a session that measures E or cm30
amc = pd.DataFrame(amc_rows, columns=["security_id", "session_date", "expiration", "event_id"])
amc = amc.merge(ce[["security_id", "session_date", "expiration", "tau_sessions", "status"]])
print(f"[7] chain rows with expiry == AMC announcement date: {len(amc)}; ok and tau>=5: "
      f"{int(((amc['status'] == 'ok') & (amc['tau_sessions'] >= 5)).sum())}; distinct events {amc['event_id'].nunique()}")

# ---- claims 6, 8: iv_daily -------------------------------------------------------------------------
ce["spans_ind"] = sp_ind
use = ce[(ce["status"] == "ok") & (ce["tau_sessions"] >= 5)]
groups = {k: g.sort_values(["tau_sessions", "expiration"]) for k, g in use.groupby(["security_id", "session_date"])}


def interp(rows, target, max_x):
    seen, ex = set(), []
    for r in rows:                         # one per tau, the first listed
        if r[0] not in seen:
            seen.add(r[0]); ex.append(r)
    if len(ex) < 2:
        return None
    lo = [r for r in ex if r[0] <= target]
    hi = [r for r in ex if r[0] > target]
    if lo and hi:
        a, b = lo[-1], hi[0]
    elif hi:
        a, b = hi[0], hi[1]
        if a[0] - target > max_x:
            return None
    else:
        a, b = lo[-2], lo[-1]
        if target - b[0] > max_x:
            return None
    return a[1] + (target - a[0]) / (b[0] - a[0]) * (b[1] - a[1]), a, b


res = {"cm30": 0, "blind": 0, "evar": 0, "sigma_d": 0, "front": 0}
cross_class_interp, two_comp = 0, 0
dup_tau_spanning, t2_after_next_next = 0, 0
n_rows = 0
for r in iv[iv["snapshot_status"] == "ok"].itertuples(index=False):
    n_rows += 1
    g = groups.get((r.security_id, r.session_date))
    rows = [] if g is None else list(zip(g["tau_sessions"], g["w_atm"], g["expiration"], g["spans_ind"]))
    n = nxt(r.security_id, r.session_date)
    to_ev = None if n is None else n_between(r.session_date, n[0])
    contains = to_ev is not None and to_ev <= 21
    cls = [x for x in rows if bool(x[3]) == contains]
    cm = None
    if len(cls) >= 2:
        got = interp(cls, 21, 10)
        cm = None if got is None else got[0]
        if got is not None and bool(got[1][3]) != bool(got[2][3]):
            cross_class_interp += 1
    elif len(cls) == 1:
        e = cls[0]
        if contains:
            clean = [x for x in rows if not x[3]]
            if clean:
                c = max(clean, key=lambda x: (x[0], x[2]))
                cm = c[1] / c[0] * 21 + (e[1] - c[1] / c[0] * e[0])
                two_comp += 1
        elif abs(21 - e[0]) <= 10:
            cm = e[1] * 21 / e[0]
    cm_iv = math.sqrt(252 * cm / 21) if cm is not None and cm > 0 else None
    if not ((cm_iv is None and pd.isna(r.cm30_iv)) or (cm_iv is not None and abs(cm_iv - r.cm30_iv) < 1e-12)):
        res["cm30"] += 1
    bl = interp(rows, 21, 10)
    b = bl[0] if bl else (rows[0][1] * 21 / rows[0][0] if len(rows) == 1 and abs(21 - rows[0][0]) <= 10 else None)
    b_iv = math.sqrt(252 * b / 21) if b is not None and b > 0 else None
    if not ((b_iv is None and pd.isna(r.cm30_blind_iv)) or (b_iv is not None and abs(b_iv - r.cm30_blind_iv) < 1e-12)):
        res["blind"] += 1
    span = [x for x in rows if x[3]]
    clean = [x for x in rows if not x[3]]
    E, s2 = None, None
    if len(span) >= 2:
        (t1, w1, e1, _), (t2, w2, e2, _) = span[0], span[1]
        if t1 == t2:
            dup_tau_spanning += 1
        else:
            E, s2 = (w1 * t2 - w2 * t1) / (t2 - t1), (w2 - w1) / (t2 - t1)
            nn = nxt(r.security_id, r.session_date, 1)
            if nn is not None and as_of(e2) >= nn[0]:
                t2_after_next_next += 1
    elif len(clean) >= 2:
        s2 = (clean[1][1] - clean[0][1]) / (clean[1][0] - clean[0][0])
    if not ((E is None and pd.isna(r.event_var)) or (E is not None and abs(E - r.event_var) <= 1e-15 + 1e-12 * abs(E))):
        res["evar"] += 1
    sd = math.sqrt(252 * s2) if s2 is not None and s2 >= 0 else None
    if not ((sd is None and pd.isna(r.sigma_d_iv)) or (sd is not None and abs(sd - r.sigma_d_iv) < 1e-12)):
        res["sigma_d"] += 1
    if E is not None and E <= 0 and not (pd.isna(r.implied_move) and r.implied_move_status == "nonpositive_event_variance"):
        res["evar"] += 1
    fr = rows[0][2] if rows else None
    if (fr is None) != pd.isna(r.front_expiry) or (fr is not None and fr != r.front_expiry):
        res["front"] += 1
print(f"[6/8] ok iv_daily rows {n_rows}; mismatches {res}")
print(f"[6] interp/extrap using expiries of two classes: {cross_class_interp}; two_component rows: {two_comp}")
print(f"[8] spanning pairs with equal tau (would divide by zero): {dup_tau_spanning}; "
      f"E pairs whose 2nd expiry also spans the event after next: {t2_after_next_next}")
if any(res.values()) or cross_class_interp:
    fails.append("6/8")
mc = iv[iv["cm30_method"].isin(["interp_clean", "interp_spanning", "extrap_clean", "extrap_spanning",
                                "two_component", "flat_sigma"])]
k = ce.set_index(["security_id", "session_date", "expiration"])["spans_ind"]
lo = [k.get((s, d, e)) for s, d, e in zip(mc["security_id"], mc["session_date"], mc["cm30_exp_lo"])]
hi = [k.get((s, d, e)) for s, d, e in zip(mc["security_id"], mc["session_date"], mc["cm30_exp_hi"])]
tab = pd.DataFrame({"method": mc["cm30_method"].astype(str).to_numpy(), "lo": lo, "hi": hi})
print("[6] stored cm30_exp_lo / cm30_exp_hi classes (spans) by method:")
print(tab.groupby(["method", "lo", "hi"]).size().to_string())

# ---- claim 5: T1* --------------------------------------------------------------------------------
okrows = {k_: g for k_, g in ce[ce["status"] == "ok"].groupby(["security_id", "session_date"])}
evs = ev.set_index("event_id")
t1_bad, iv_bad, listed_post, interp_post, n_t1 = 0, 0, 0, 0, 0
shorter_nonok = 0
for r in eiv.itertuples(index=False):
    e = evs.loc[r.event_id]
    if r.pre_session is None or pd.isna(r.pre_session) or e.day0_session is None:
        continue
    if r.post_session is None or pd.isna(r.post_session):
        continue                           # no crush pair: event_row stops before T1* (documented in p04 notes)
    g = okrows.get((e.security_id, r.pre_session))
    d0 = e.day0_session
    c = [] if g is None else sorted(x for x in g["expiration"] if n_between(d0, as_of(x)) >= 5)
    t1 = c[0] if c else None
    n_t1 += t1 is not None
    stored = None if pd.isna(r.front_fixed_expiry) else r.front_fixed_expiry
    if t1 != stored:
        t1_bad += 1
    elif t1 is not None:
        want = float(g.loc[g["expiration"] == t1, "iv_atm"].iloc[0])
        if abs(want - r.front_fixed_iv_m1) > 1e-12:
            iv_bad += 1
        tpost = n_between(r.post_session, as_of(t1))
        gp = okrows.get((e.security_id, r.post_session))
        listed = gp is not None and (gp["expiration"] == t1).any()
        if tpost >= 5 and listed:
            listed_post += 1
            if abs(float(gp.loc[gp["expiration"] == t1, "iv_atm"].iloc[0]) - r.front_fixed_iv_0) > 1e-12:
                iv_bad += 1
        elif tpost >= 5:
            interp_post += 1
        elif not pd.isna(r.front_fixed_iv_0):
            iv_bad += 1                    # followed past tau < 5
    if t1 is not None:
        allpre = ce[(ce["security_id"] == e.security_id) & (ce["session_date"] == r.pre_session)]
        if any(x < t1 and n_between(d0, as_of(x)) >= 5 for x in allpre["expiration"]):
            shorter_nonok += 1
print(f"[5] iv_m1/iv_0 mismatches {iv_bad}; T1* listed at post {listed_post}, not listed (interp branch) {interp_post}")
print(f"[5] events with T1* {n_t1}; T1* mismatches {t1_bad}; events where a shorter listed but non-ok expiry "
      f"with tau(day0)>=5 was skipped: {shorter_nonok}")
if t1_bad or iv_bad:
    fails.append("5")
print("[5] front_fixed_interpolated:", eiv["front_fixed_interpolated"].value_counts().to_dict(),
      "; crush_front_fixed non-null:", int(eiv["crush_front_fixed"].notna().sum()))
print("RESULT", "FAIL " + ",".join(fails) if fails else "PASS")
sys.exit(1 if fails else 0)
