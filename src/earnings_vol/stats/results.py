# =============================================================================
# results.py — The `results` table (data model §3.13) from the stats Frame:
# the primary family H1-H4 with its robustness rows, the mean-adjusted twins,
# the exploratory rows, the descriptive mean paths, and gate G1's rows.
# Pure: arrays in, a DataFrame out. Holm and BH are applied here.
#
# ROLES
#   primary      the declared statistic of each hypothesis in the binding Holm
#                family (ADR 0005 §4): H1-H4 when gate G1 passed for them, and
#                H5-H7 (regressions, stats/drivers.py) whatever G1's regression
#                size check says (binding_family; ADR 0005 §5, dated note of
#                2026-10-29: the size designs declared at milestone 0 cover
#                H1-H4 only); Holm-adjusted over that family
#   robustness   the rows ADR 0005 §4 lists beside each primary, and the
#                mean-adjusted twin of each primary (ADR 0004 §2: "always
#                reported next to it")
#   exploratory  everything else (other rel_days, PERSIST_1 and _5, the timing
#                subgroups, the front-expiry crush, the mixed and coarse
#                samples), with BH q-values within each sample; and the primary
#                of a hypothesis that left the family (ADR 0005 §5)
# Fixes after the milestone-4 review: result_rows refuses a G1 report without a
# verdict for every hypothesis that gets rows (require_verdicts); the Holm p
# of the family after dropping every failed G1 primary is a descriptive
# sensitivity (holm_post_gate_rows), not the binding one.
# Added after the milestone-3 review:
#   - a robustness row whose statistic gate G1's calibrated design rejects
#     above the band's top keeps estimate, se and stat and loses p_value and
#     the CI (ADR 0005 §4: rows known to be mis-sized; oversized, withhold);
#     since the second fix round the band is the one for the replications the
#     rate was measured on, and a rate within one point of the 2,000 bar is
#     re-measured on 10,000 (g1.size_verdicts; G1 rows g1:calibrated_remeasured);
#   - a ramp primary on rad_season_p gets its season-cut counterfactual (the
#     last season merged into the one before, role robustness, subgroup
#     season_cut) with the Holm p it would get (season_cut_rows).
# DESCRIPTIVE rows: the mean abnormal path per rel_day -10 .. +10 with pointwise
# 95% bands, two-way clustered by season x firm (ADR 0004 §3). No p-value.
# VALIDATION rows: G1's rejection rates (estimate = rate, n = replications) and
# its calibration numbers. The reference-distribution invariant skips them.
# =============================================================================

import hashlib

import numpy as np
import pandas as pd

from earnings_vol import schema
from earnings_vol.panel import abnormal
from earnings_vol.stats import clustering, g1, inputs, multiple, suite

HYP = {"H1": "crush", "H2": "runup", "H3": "persist_10", "H4": "dsigma_d"}
# The hypotheses whose failed G1 primary leaves the binding Holm family (ADR 0005 §5): the ones G1's
# size designs were declared for at milestone 0 (the intercept-only H1-H4). H5-H7's regression size
# check (milestone 4) is reported beside their rows; it does not move them out (fix R1 after the
# milestone-4 review). An owner who prefers the post-gate family sets this to all seven.
SIZE_GATED = tuple(HYP)
MEASURE_NAME = {"crush": "crush_cm30", "runup": "runup", "persist_1": "persist_1", "persist_5": "persist_5",
                "persist_10": "persist_10", "dsigma_d": "dsigma_d", "crush_front_fixed": "crush_front_fixed"}
KEY = ("family", "hypothesis", "role", "measure", "statistic", "rel_day", "sample", "subgroup_key",
       "subgroup_value", "adjustment", "model_id", "term")
# The validation rows of the near-bar robustness rates re-measured on g1.REMEASURE_REPS replications
# (measure "g1:calibrated_remeasured", n = those replications; second fix round).
REMEASURED = "calibrated_remeasured"


def row(**kw) -> dict:
    """A results row with every column (None where not given) and its result_id: SHA-1 of the
    key columns (data model §3.13), with `role` left out so that a role change after G1 does
    not change the id."""
    r = {c: None for c in schema.RESULTS.names}
    r.update(kw)
    key = "|".join("" if r[k] is None else str(r[k]) for k in KEY if k != "role")
    r["result_id"] = hashlib.sha1(key.encode("utf-8")).hexdigest()
    return r


def _stat_row(base: dict, name: str, res: dict) -> dict:
    out = dict(base, statistic=name, estimand=suite.ESTIMAND.get(name))
    for k in ("estimate", "se", "stat", "df", "p_value", "ci_lo", "ci_hi", "rbar", "n", "n_clusters",
              "n_clusters_firm"):
        if k in res and res[k] is not None and not (isinstance(res[k], float) and np.isnan(res[k])):
            out[k] = res[k]
    out["n"] = int(res.get("n", base.get("n") or 0))
    if out.get("n_clusters") is not None:
        out["n_clusters"] = int(out["n_clusters"])
    if out.get("n_clusters_firm") is not None:
        out["n_clusters_firm"] = int(out["n_clusters_firm"])
    return row(**out)


def run_measure(f: inputs.Frame, measure: str, sample: str, adjustment: str, st: dict, *, timing: str | None = None,
                robust: bool = False) -> dict:
    """{statistic: results} of one test (the suite), with "primary" naming the primary statistic."""
    rows = inputs.event_set(f, measure, sample, timing)
    A = inputs.values(f, rows, measure, adjustment)
    ok = np.isfinite(A)
    rows, A = rows[ok], A[ok]
    ev = f.ev.iloc[rows]
    firm = ev["security_id"].to_numpy(object)
    one = measure in ("crush", "dsigma_d", "crush_front_fixed")
    if one:
        day0 = ev["day0_session"].astype(str).to_numpy(object)
        kw = inputs.robust_inputs(f, rows, measure) if robust else {}
        return suite.one_session(A, day0, firm, patell=measure == "crush", min_shared=int(st["kp_min_shared"]),
                                 robust=robust, **kw)
    d0 = np.array([f.sessions.index[d] for d in ev["day0_session"]])
    sa = ev[inputs.SA[measure]].to_numpy(float) if robust else None
    return suite.ramp(A, ev["season"].to_numpy(object), d0, firm, sa=sa, min_events=int(st["season_min_events"]),
                      ratio=float(st["unbalanced_ratio"]), min_clusters=int(st["min_season_clusters"]),
                      robust=robust)


def oversized(report: dict, alpha: float) -> dict:
    """{(hypothesis, statistic): {"rate", "reps", "bar", "oversized"}} of the robustness statistics
    whose rejection rate under gate G1's calibrated null is above the upper edge of the exact
    binomial band for the replications it was measured on (6.30% at 2,000; a statistic within
    one point of that bar is re-measured on 10,000 and decided against 5.57%: g1.size_verdicts,
    ADR 0005 §4). date_cluster_t is G1's rejected mutant, not a reported row."""
    v = g1.size_verdicts(report["rates"]["calibrated"], int(report["reps"]), alpha, report.get("remeasured"))
    return {k: x for k, x in v.items() if x["oversized"]}


def withhold(r: dict) -> dict:
    """ADR 0005 §4 (dated note of the milestone-3 review): a row known to be mis-sized keeps
    its estimate, se and statistic, and loses its p-value and confidence interval."""
    return dict(r, p_value=None, ci_lo=None, ci_hi=None)


def event_test_rows(f: inputs.Frame, st: dict, gate: dict, common: dict, mis_sized: dict | None = None) -> list[dict]:
    """Every event_test row; `gate` maps H1-H4 to True when the hypothesis is in the binding Holm
    family (binding_family: its G1 gate passed) or False, read strictly; `mis_sized` is
    oversized()'s {(hypothesis, statistic): rate}: those robustness rows are withheld."""
    out = []
    mis_sized = mis_sized or {}
    base = dict(family="event_test", subgroup_key="all", subgroup_value="all", **common)
    # The primary family, its robustness rows, and the mean-adjusted twins.
    for h, m in HYP.items():
        res = run_measure(f, m, "daily", "market", st, robust=True)
        prim = res["primary"]
        b = dict(base, hypothesis=h, measure=MEASURE_NAME[m], sample="daily", adjustment="market")
        for name, r in res.items():
            if not isinstance(r, dict):
                continue
            role = ("primary" if gate[h] else "exploratory") if name == prim else "robustness"
            new = _stat_row(dict(b, role=role), name, r)
            out.append(withhold(new) if role == "robustness" and (h, name) in mis_sized else new)
        twin = run_measure(f, m, "daily", "mean", st)
        out.append(_stat_row(dict(b, role="robustness", adjustment="mean"), twin["primary"], twin[twin["primary"]]))
    # Exploratory rows: the primary statistic of each measure's kind.
    plan = [("daily", "market", None, ("persist_1", "persist_5")),
            ("daily", "mean", None, ("crush_front_fixed",)),
            ("mixed", "market", None, ("crush", "runup", "persist_10")),
            ("mixed", "mean", None, ("crush",)),
            ("coarse", "market", None, ("crush", "runup", "persist_10")),
            ("coarse", "mean", None, ("crush",))]
    plan += [("daily", "market", t, ("crush", "runup", "persist_10")) for t in ("BMO", "AMC")]
    for sample, adj, timing, ms in plan:
        for m in ms:
            if len(inputs.event_set(f, m, sample, timing)) < 10:
                continue
            res = run_measure(f, m, sample, adj, st, timing=timing)
            prim = res["primary"]
            sub = dict(subgroup_key="timing", subgroup_value=timing) if timing else {}
            out.append(_stat_row(dict(base, **sub, role="exploratory", measure=MEASURE_NAME[m], sample=sample,
                                      adjustment=adj), prim, res[prim]))
    return out


def path_rows(f: inputs.Frame, st: dict, common: dict) -> list[dict]:
    """The mean abnormal path per rel_day -10 .. +10 (descriptive), over the primary sample
    (eligible_crush, daily), for all and per timing, market- and mean-adjusted."""
    out = []
    prim = inputs.event_set(f, "crush", "daily")
    for timing in (None, "BMO", "AMC"):
        rows = prim if timing is None else prim[(f.ev["timing_used"].to_numpy(object)[prim] == timing)]
        for adj, mat in (("market", f.aliv), ("mean", f.aliv0)):
            for rel in range(-10, 11):
                v = mat[rows, abnormal.col(rel)]
                ok = np.isfinite(v)
                r_ = rows[ok]
                if r_.size < 10:
                    continue
                ev = f.ev.iloc[r_]
                d0 = np.array([f.sessions.index[d] for d in ev["day0_session"]])
                res = suite.ramp(v[ok], ev["season"].to_numpy(object), d0, ev["security_id"].to_numpy(object),
                                 min_events=int(st["season_min_events"]), ratio=np.inf, min_clusters=2, robust=False)
                tw = res["twoway_season_t"]
                sub = dict(subgroup_key="timing", subgroup_value=timing) if timing else \
                    dict(subgroup_key="all", subgroup_value="all")
                out.append(row(family="descriptive", role="exploratory", measure="aliv_path", statistic="mean",
                               estimand="equal_weighted", rel_day=rel, sample="daily", adjustment=adj, **sub,
                               n=int(tw["n"]), n_clusters=int(tw["n_clusters"]),
                               n_clusters_firm=int(tw["n_clusters_firm"]), df=tw["df"], estimate=tw["estimate"],
                               se=tw["se"], ci_lo=tw["ci_lo"], ci_hi=tw["ci_hi"], **common))
    return out


TESTED_FAMILIES = ("event_test", "regression")     # milestone 4: H5-H7's primaries are regression rows


def primary_rows(rows: list[dict]) -> dict:
    """{hypothesis: its primary row}, over the event tests (H1-H4) and the regressions (H5-H7)."""
    return {r["hypothesis"]: r for r in rows if r["family"] in TESTED_FAMILIES and r["role"] == "primary"}


def require_verdicts(report: dict, hypotheses) -> None:
    """Refuse gate G1's report unless it holds a verdict for every hypothesis in `hypotheses` (the
    ones the results run writes rows for): a bool in report["gate"] and the calibrated rates the
    hypothesis's robustness rows are withheld by (report["rates"]["calibrated"]). Fix R2 after the
    milestone-4 review: a missing verdict used to count as a pass (gate.get(h, True)), so a
    milestone-3 report gave H5-H7 the primary role with no size check and withheld nothing."""
    gate = report.get("gate") or {}
    cal = (report.get("rates") or {}).get("calibrated") or {}
    missing = sorted(h for h in set(hypotheses) if not isinstance(gate.get(h), bool) or h not in cal)
    if missing:
        raise ValueError(f"gate G1's report has no verdict for {', '.join(missing)}: run "
                         "`python -m earnings_vol.stats.run --g1` again before the results")


def binding_family(declared: list, gate: dict, gated: tuple = SIZE_GATED) -> list[str]:
    """The binding Holm family: the declared one (params stats.holm_family) minus each hypothesis
    in `gated` whose G1 primary failed (ADR 0005 §5). A hypothesis outside `gated` (H5-H7 by
    default) stays whatever its size check says; its rows carry that size instead. gate[h] is read
    strictly: require_verdicts has run."""
    return [h for h in declared if h not in gated or gate[h]]


def post_gate_family(declared: list, gate: dict) -> list[str]:
    """The declared family minus EVERY hypothesis whose G1 primary failed, H5-H7's regression size
    check included: the family of the descriptive sensitivity (holm_post_gate_rows)."""
    return [h for h in declared if gate[h]]


def apply_holm(rows: list[dict], family: list[str]) -> dict:
    """Set p_holm on the primary rows of the binding family; a hypothesis of the family with no
    primary row (not tested) enters as p = 1. Returns {hypothesis: adjusted p}. Since milestone 4
    H5-H7 have rows."""
    prim = primary_rows(rows)
    pv = {h: (prim[h]["p_value"] if h in prim else None) for h in family}
    adj = multiple.holm(pv)
    for h, r in prim.items():
        r["p_holm"] = adj[h]
    return adj


def holm_post_gate_rows(rows: list[dict], family: list[str], common: dict) -> list[dict]:
    """A sensitivity, not a test: the Holm p each hypothesis of the POST-GATE family (post_gate_family:
    the declared family minus every hypothesis whose G1 primary failed) would get from the primary
    rows' p-values, and the same for each season-cut counterfactual row (its p in place of its
    hypothesis's, the family's other p-values as reported). Family descriptive, measure
    holm_post_gate, statistic holm, estimate = that Holm p, n = the family's size; no p-value of its
    own. The binding p_holm is the primary rows' (fix R1 after the milestone-4 review: until then
    this family was the binding one, and the declared seven a sensitivity)."""
    prim = primary_rows(rows)
    pv = {h: (prim[h]["p_value"] if h in prim else None) for h in family}
    adj = multiple.holm(pv)
    base = dict(family="descriptive", role="exploratory", measure="holm_post_gate", statistic="holm", sample="daily",
                n=len(family), **common)
    out = [row(**base, hypothesis=h, subgroup_key="all", subgroup_value="all",
               adjustment=prim[h]["adjustment"] if h in prim else "market", estimate=float(adj[h])) for h in family]
    for c in rows:
        if c["subgroup_key"] == "season_cut" and c["hypothesis"] in family:
            h = c["hypothesis"]
            out.append(row(**base, hypothesis=h, subgroup_key="season_cut", subgroup_value=c["subgroup_value"],
                           adjustment=c["adjustment"], estimate=float(multiple.holm(dict(pv, **{h: c["p_value"]}))[h])))
    return out


def season_cut_rows(f: inputs.Frame, st: dict, rows: list[dict], family: list[str], common: dict) -> list[dict]:
    """The season-cut counterfactual of a ramp primary whose p comes from rad_season_p.

    rad_season_p sits at its floor 2/2^G whenever every season sum has the same sign, so its
    Holm verdict then depends on the number of season clusters G alone (milestone-3 review,
    ledger claim 4c). ADR 0005 §2b expected the last, partial season (the October 2026 tail) to
    join the one before it. This row is that cut: the last merged season merged into the one
    before it, the primary statistic the 1.5x rule then picks, and in p_holm the Holm p the
    hypothesis would get with that p (the family's other p-values as reported). Role
    robustness, subgroup_key "season_cut", subgroup_value "<last>_into_<previous>"."""
    out = []
    prim = primary_rows(rows)
    for h, r in prim.items():
        if r["statistic"] != "rad_season_p":
            continue
        m = HYP[h]
        idx = inputs.event_set(f, m, "daily")
        A = inputs.values(f, idx, m, "market")
        idx, A = idx[np.isfinite(A)], A[np.isfinite(A)]
        ev = f.ev.iloc[idx]
        d0 = np.array([f.sessions.index[d] for d in ev["day0_session"]])
        merged = clustering.merge_small_seasons(ev["season"].to_numpy(object), d0, int(st["season_min_events"]))
        keys = sorted(set(merged.tolist()))
        if len(keys) - 1 < int(st["min_season_clusters"]):
            continue
        cut = merged.copy()
        cut[cut == keys[-1]] = keys[-2]
        res = suite.ramp(A, cut, d0, ev["security_id"].to_numpy(object), min_events=int(st["season_min_events"]),
                         ratio=float(st["unbalanced_ratio"]), min_clusters=int(st["min_season_clusters"]),
                         robust=False)
        name = res["primary"]
        pv = {k: (prim[k]["p_value"] if k in prim else None) for k in family}
        pv[h] = res[name]["p_value"]
        new = _stat_row(dict(family="event_test", hypothesis=h, role="robustness", measure=r["measure"],
                             sample="daily", adjustment="market", subgroup_key="season_cut",
                             subgroup_value=f"{keys[-1]}_into_{keys[-2]}", **common), name, res[name])
        new["p_holm"] = multiple.holm(pv)[h]
        out.append(new)
    return out


def apply_bh(rows: list[dict]) -> None:
    """BH q-values within each exploratory family: the exploratory rows with a p-value of one
    sample, event tests and regressions apart (milestone 4: the regression rows of a sample are a
    family of their own, so the milestone-3 q-values do not move)."""
    for family in TESTED_FAMILIES:
        for sample in schema.RESULT_SAMPLES:
            fam = [r for r in rows if r["family"] == family and r["role"] == "exploratory"
                   and r["sample"] == sample and r["p_value"] is not None]
            for r, q in zip(fam, multiple.bh([r["p_value"] for r in fam])):
                r["q_bh"] = q


def g1_rows(report: dict, common: dict) -> list[dict]:
    """Validation rows: every G1 rejection rate (role primary for a hypothesis's primary
    statistic, robustness for the others) and the calibration numbers (role exploratory)."""
    out = []
    reps = int(report["reps"])
    for design, by_h in report["rates"].items():
        for h, rates in by_h.items():
            prim = rates["_primary"]
            for name, rate in rates.items():
                if name.startswith("_"):
                    continue
                out.append(row(family="validation", hypothesis=h, role="primary" if name == prim else "robustness",
                               measure=f"g1:{design}", statistic=name, sample="daily", subgroup_key="all",
                               subgroup_value="all", adjustment="market", n=reps, estimate=float(rate), **common))
    # Second fix round: the robustness rates re-measured near the bar (n = their replications).
    rem = report.get("remeasured") or {}
    for h, by in rem.get("rates", {}).items():
        for name, rate in by.items():
            out.append(row(family="validation", hypothesis=h, role="robustness", measure=f"g1:{REMEASURED}",
                           statistic=name, sample="daily", subgroup_key="all", subgroup_value="all",
                           adjustment="market", n=int(rem["reps"]), estimate=float(rate), **common))
    n_ev = int(report["n_events"])
    # The cm30 calibration (H1-H3) and, since the review, H4's own sigma_d calibration; since
    # milestone 4 H7's (n = its events; an infinite nu, normal moves, is stored as a null estimate).
    for key, label in (("calibration", "g1_calibration"), ("calibration_sigma_d", "g1_calibration_sigma_d"),
                       ("calibration_h7", "g1_calibration_h7")):
        cal = report.get(key)
        if cal is None:
            continue
        n_cal = int((report.get("n_events_drivers") or {}).get("H7", n_ev)) if key == "calibration_h7" else n_ev
        for kind in ("params", "measured"):
            for k, v in cal[kind].items():
                vals = v if isinstance(v, list) else [v]
                for lag, x in enumerate(vals, 1):
                    out.append(row(family="validation", role="exploratory", measure=f"{label}:{kind}",
                                   statistic=k, rel_day=lag if isinstance(v, list) else None, sample="daily",
                                   subgroup_key="all", subgroup_value="all",
                                   adjustment="none" if key == "calibration_h7" else "market", n=n_cal,
                                   estimate=float(x) if np.isfinite(x) else None, **common))
    return out


def frame(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=list(schema.RESULTS.names))
    for c in ("rel_day", "n_clusters", "n_clusters_firm"):
        df[c] = pd.Series([r[c] for r in rows], dtype=object)
    for c in ("df", "df_num", "estimate", "se", "stat", "p_value", "ci_lo", "ci_hi", "p_holm", "q_bh", "rbar"):
        df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)
    return df.sort_values(["family", "sample", "hypothesis", "measure", "statistic", "subgroup_key",
                           "subgroup_value", "adjustment", "rel_day"], kind="mergesort",
                          key=lambda s: s.astype(str)).reset_index(drop=True)
