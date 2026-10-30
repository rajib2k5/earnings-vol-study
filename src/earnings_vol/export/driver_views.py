# =============================================================================
# driver_views.py — The milestone-4 views (data model §4, contract 0.5.0):
#   drivers              the regression rows of `results` (family "regression"),
#                        model by model: every named term with its statistics,
#                        R^2, and gate G1's verdict on H5-H7 with the rates and
#                        power behind it. Fixed-effect coefficients are never
#                        rows of `results`, so never here (data model §2.1).
#                        Since the fixes after the milestone-4 review, Holm's
#                        binding family is read from the rows (holm_family),
#                        H5-H7's primaries stay in it with their G1 size and a
#                        note, and `holm.post_gate` is the descriptive Holm p
#                        without every failed G1 primary.
#   implied_vs_realised  one point per primary event with a realised move: the
#                        implied move at day -1 (E, sqrt E, the expected
#                        |total move| sqrt(2/pi) sqrt(E + sigma_d^2/252)) and the
#                        realised move r0 (DoltHub option forwards, class F), and
#                        the H7 rows and the exceed share from `results`.
# Pure: committed tables in, dicts out (tools/export_app_data.py writes them).
# The app draws these numbers; it computes none of them.
# Rounding as event_views: estimates 4 dp (moves 5 dp, variances 8 dp, R^2 and
# rates 4 dp), p-values 4 significant figures.
# =============================================================================

import math

import numpy as np
import pandas as pd

from earnings_vol.export.event_views import (_int, _r, _sig, holm_family, lookups, post_gate, primary_events,
                                             provisional_caveat)
from earnings_vol.stats import g1, g1_drivers

MODEL_LABEL = {        # also the order of drivers.json's models
    ("crush_drivers", "market", "daily"): "CRUSH on the drivers (H5, H6)",
    ("crush_drivers", "mean", "daily"): "CRUSH on the drivers, mean-adjusted twin",
    ("implied_realised", "none", "daily"): "realised r0^2 on implied E + sigma_d^2/252 (H7)",
    ("dsigma_d_drivers", "market", "daily"): "DSIGMA_D on the drivers (decomposition)",
    ("crush_prior_cm30", "market", "daily"): "prior level as ln cm30 (mechanically linked)",
    ("crush_sue", "market", "daily"): "|SUE_hist| in place of |surprise|",
    ("crush_disp", "market", "daily"): "|dispersion-scaled surprise| in place of |surprise|",
    ("crush_signed", "market", "daily"): "the signed surprise added",
    ("crush_firm_fe", "market", "daily"): "firm fixed effects in place of sector",
    ("crush_vix", "market", "daily"): "VIX terciles in place of seasons, with |surprise| x tercile",
    ("crush_drivers", "market", "coarse"): "CRUSH on the drivers, coarse sample (2020-2024)",
    ("implied_realised_m2", "none", "daily"): "realised r0^2 on implied variance with E at day -2",
}
DEP_VAR = {"crush_cm30": "CRUSH (cm30, log)", "dsigma_d": "DSIGMA_D (log)", "r0_squared": "r0^2",
           "abs_r0_over_implied": "|r0| > implied |move|"}
FIXED = {"crush_drivers": ["sector", "season"], "dsigma_d_drivers": ["sector", "season"],
         "crush_prior_cm30": ["sector", "season"], "crush_sue": ["sector", "season"],
         "crush_disp": ["sector", "season"], "crush_signed": ["sector", "season"], "crush_firm_fe": ["firm", "season"],
         "crush_vix": ["sector", "vix_regime"], "implied_realised": [], "implied_realised_m2": []}
TERM_LABEL = {"abs_surprise": "|surprise| / price (winsorised)", "ln_sigma_d": "ln sigma_d at day -1",
              "slope": "term-structure slope at day -1", "size": "ln market cap at day -1",
              "ln_cm30": "ln cm30 at day -1", "abs_sue": "|SUE_hist|", "abs_disp": "|dispersion-scaled surprise|",
              "surprise": "signed surprise / price", "abs_surprise_x_mid": "|surprise| x mid-VIX tercile",
              "abs_surprise_x_high": "|surprise| x high-VIX tercile", "a": "intercept a (tested against 0)",
              "b": "slope b (tested against 1)", "a=0,b=1": "joint test a = 0, b = 1",
              "exceed_share": "share with |r0| above the implied |move| (tested against 0.425)"}
COV = {"twoway_date_t": "two-way day-0 date x firm, t", "cluster_date_t": "one-way day-0 date, t",
       "twoway_date_wald": "two-way day-0 date x firm, Wald F", "cluster_date_wald": "one-way day-0 date, Wald F"}


def _f(v, dp: int = 4):
    return _r(v, dp)


def _s(v):
    """A text cell, None when missing (pandas 3 reads a missing string as NaN)."""
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else v


def g1_summary(results: pd.DataFrame, alpha: float) -> dict:
    """Gate G1 for H5-H7 from the committed validation rows: the calibrated rates of every H5-H7
    statistic with the verdict (the primary's gate; for the others, oversized or not, decided on the
    replications measured: g1.size_verdicts), every design's rates, and the power curves."""
    val = results[(results["family"] == "validation") & results["measure"].str.startswith("g1:")
                  & results["hypothesis"].isin(["H5", "H6", "H7"])]
    reps = int(val.loc[val["measure"] == "g1:calibrated", "n"].iloc[0])
    lo, hi = g1.binom_band(reps, alpha)
    cal = val[val["measure"] == "g1:calibrated"]
    rates: dict = {}
    for r in cal.to_dict("records"):
        rates.setdefault(r["hypothesis"], {})[r["statistic"]] = float(r["estimate"])
        if r["role"] == "primary":
            rates[r["hypothesis"]]["_primary"] = r["statistic"]
    rem = val[val["measure"] == "g1:calibrated_remeasured"]
    remeasured = None
    if len(rem):
        remeasured = {"reps": int(rem["n"].iloc[0]), "rates": {}}
        for r in rem.to_dict("records"):
            remeasured["rates"].setdefault(r["hypothesis"], {})[r["statistic"]] = float(r["estimate"])
    verdicts = g1.size_verdicts(rates, reps, alpha, remeasured)
    calibrated = []
    for h in sorted(rates):
        for st, rate in sorted(rates[h].items()):
            if st == "_primary":
                continue
            prim = st == rates[h]["_primary"]
            v = verdicts.get((h, st))
            calibrated.append({"hypothesis": h, "statistic": st, "primary": prim,
                               "rejection_rate": _f(rate if prim else v["rate"]),
                               "reps": reps if prim else int(v["reps"]),
                               "pass": bool(rate <= hi) if prim else not v["oversized"]})
    designs, power = [], {}
    for r in val.to_dict("records"):
        name = r["measure"][len("g1:"):]
        if name.startswith("power_"):
            power.setdefault(r["hypothesis"], []).append((float(name.split(":")[1]), float(r["estimate"])))
        elif name != "calibrated_remeasured":
            designs.append({"design": name, "hypothesis": r["hypothesis"], "statistic": r["statistic"],
                            "primary": r["role"] == "primary", "rejection_rate": _f(r["estimate"])})
    pw = []
    for h in sorted(power):
        pts = sorted(power[h])
        sh, pv = [s for s, _ in pts], [x for _, x in pts]
        pw.append({"hypothesis": h, "kind": "b" if h == "H7" else "beta", "shifts": sh, "power": [_f(x) for x in pv],
                   "detectable_80": None if h == "H7" else _f(g1.detectable_shift(sh, pv))})
    c7 = results[(results["family"] == "validation") & (results["measure"] == "g1_calibration_h7:params")]
    return {"reps": reps, "band": [lo, hi], "calibrated": calibrated, "designs": designs, "power": pw,
            "calibration_h7": {r["statistic"]: _f(r["estimate"], 6) for r in c7.to_dict("records")}}


def term_note(r: dict, verdicts: dict, gate: dict, cal: dict, reps: int = 0, bar: float = 0.0,
              alpha: float = 0.05) -> tuple:
    """(note, g1_size, g1_reps) of one regression row: a withheld robustness row (its G1 size); a
    primary whose G1 size check failed but which stays in the binding family (H5-H7, ADR 0005 §5
    dated note of 2026-10-29: its p-value and Holm p are shown with its size, g1_reps `reps`, and
    the warning that the statistic is liberal); the declared primary statistic of a hypothesis that
    left the family (exploratory, p-value shown); or nothing."""
    h, st = _s(r["hypothesis"]), r["statistic"]
    key = g1_drivers.TWIN_KEY if r["adjustment"] == "mean" and st == "twoway_date_t" else st
    v = verdicts.get((h, key)) if h else None
    if r["role"] == "robustness" and v is not None and v["oversized"]:
        if r["p_value"] is not None and not (isinstance(r["p_value"], float) and math.isnan(r["p_value"])):
            raise ValueError(f"{h} {key}: G1 finds it oversized but it keeps a p-value")
        return (f"p-value and interval withheld: under gate G1's calibrated null this statistic rejects "
                f"{v['rate']:.2%} of the time at 5% over {v['reps']:,} replications (band upper edge "
                f"{v['bar']:.2%}), so ADR 0005 §4 drops its p-value. The estimate stands.", _f(v["rate"]), int(v["reps"]))
    if h and st == g1_drivers.PRIMARY.get(h) and r["adjustment"] != "mean" and gate[h] is False:
        rate = cal[h][st]
        if r["role"] == "primary":
            ph = float(r["p_holm"])
            verdict = (f"not rejected (Holm p {_sig(ph)})" if ph > alpha else
                       f"rejected at 5% (Holm p {_sig(ph)}), but by a liberal statistic: do not read it as confirmed")
            return (f"Size check failed: under gate G1's calibrated null this statistic rejects {rate:.2%} of the "
                    f"time at 5% over {reps:,} replications (band upper edge {bar:.2%}). It is liberal on this "
                    "design, so a rejection by it would not be trusted. The hypothesis stays in the declared Holm "
                    f"family (ADR 0005 §5, dated note of 2026-10-29) with this p-value: {verdict}.",
                    _f(rate), int(reps))
        return (f"{h} left the binding Holm family before its result was computed: gate G1's calibrated null "
                f"rejects this statistic {rate:.2%} of the time at 5%, above the band's upper edge, so ADR 0005 §5 "
                "reports it as exploratory, p-value shown, not Holm-adjusted.", None, None)
    return None, None, None


def drivers_data(results: pd.DataFrame, events: pd.DataFrame, p, provenance: dict) -> dict:
    alpha = float(p["stats"]["alpha"])
    reg = results[results["family"] == "regression"]
    gs = g1_summary(results, alpha)
    cal = {}
    for c in gs["calibrated"]:
        cal.setdefault(c["hypothesis"], {})[c["statistic"]] = c["rejection_rate"]
    gate = {c["hypothesis"]: c["pass"] for c in gs["calibrated"] if c["primary"]}
    family, left = holm_family(results, list(p["stats"]["holm_family"]))
    verdicts = {(c["hypothesis"], c["statistic"]): {"rate": c["rejection_rate"], "reps": c["reps"],
                                                    "bar": g1.binom_band(c["reps"], alpha)[1],
                                                    "oversized": not c["pass"]}
                for c in gs["calibrated"] if not c["primary"]}
    models = []
    for (mid, adj, smp), g in reg.groupby(["model_id", "adjustment", "sample"], sort=False):
        r2 = g[g["statistic"] == "r2"]
        terms = []
        for r in g[g["statistic"] != "r2"].to_dict("records"):
            note, size, reps = term_note(r, verdicts, gate, cal, gs["reps"], gs["band"][1], alpha)
            terms.append({"term": _s(r["term"]), "label": TERM_LABEL.get(_s(r["term"]), _s(r["term"])),
                          "hypothesis": _s(r["hypothesis"]), "role": r["role"], "statistic": r["statistic"],
                          "cov_type": COV[r["statistic"]], "n": int(r["n"]), "n_clusters_date": _int(r["n_clusters"]),
                          "n_clusters_firm": _int(r["n_clusters_firm"]), "coef": _f(r["estimate"], 6),
                          "se": _f(r["se"], 6), "t": _f(r["stat"]), "df": _f(r["df"], 2), "df_num": _f(r["df_num"], 2),
                          "p_value": _sig(r["p_value"]), "ci_lo": _f(r["ci_lo"], 6), "ci_hi": _f(r["ci_hi"], 6),
                          "p_holm": _sig(r["p_holm"]), "q_bh": _sig(r["q_bh"]), "g1_size": size, "g1_reps": reps,
                          "note": note})
        first = g.iloc[0]
        models.append({"model_id": mid, "adjustment": adj, "sample": smp,
                       "label": MODEL_LABEL.get((mid, adj, smp), mid),
                       "dep_var": DEP_VAR.get(first["measure"], first["measure"]), "fixed_effects": FIXED.get(mid, []),
                       "n": int(first["n"]), "n_clusters_date": _int(first["n_clusters"]),
                       "n_clusters_firm": _int(first["n_clusters_firm"]),
                       "r2": _f(r2["estimate"].iloc[0]) if len(r2) else None, "terms": terms})
    order = {k: i for i, k in enumerate(MODEL_LABEL)}
    models.sort(key=lambda m: order.get((m["model_id"], m["adjustment"], m["sample"]), len(order)))
    lk = lookups(events, p)
    over = [c for c in gs["calibrated"] if c["primary"] and not c["pass"]]
    stay = [c for c in over if c["hypothesis"] in family]
    gone = [c for c in over if c["hypothesis"] in left]
    pg = post_gate(results)
    two = sorted(c["rejection_rate"] for c in gs["calibrated"] if c["primary"] and c["statistic"] == "twoway_date_t")
    caveats = [provisional_caveat(lk),
               "Coefficients are in log points of the outcome per standard deviation of the regressor (z-scored "
               "over each model's own events). Fixed-effect coefficients are not shown (data model §2.1).",
               "Two-way standard errors cluster by day-0 date and firm, with t (or F) on min(G) - 1 degrees of "
               "freedom (ADR 0005 §3)."]
    if stay:
        caveats.append("Gate G1's regression size check ran before these results were computed. Its calibrated null "
                       "rejects " + "; ".join(f"{c['hypothesis']} {c['statistic']} {c['rejection_rate']:.2%}"
                                              for c in stay)
                       + f" of the time at 5% (band upper edge {gs['band'][1]:.2%} over {gs['reps']:,} replications): "
                       "these statistics are liberal on this design, so a rejection by them would not be trusted. "
                       f"{', '.join(c['hypothesis'] for c in stay)} stay in the declared Holm family with their real "
                       "p-values (ADR 0005 §5, dated note of 2026-10-29: G1's size designs were declared for H1-H4 "
                       "only); " + ("none of them is rejected." if all(
                           (_holm_of(models, c["hypothesis"]) or 1.0) > alpha for c in stay) else
                           "a rejection among them rests on a liberal statistic.")
                       + " The Holm p over the family without them (" + ", ".join(pg["family"])
                       + ") is a sensitivity, shown apart, not the binding one.")
    if gone:
        caveats.append(", ".join(c["hypothesis"] for c in gone) + " failed gate G1 and left the binding Holm family "
                       "(ADR 0005 §5): their rows are exploratory, with p-values shown and no Holm adjustment.")
    if two:
        caveats.append("Every exploratory p-value and BH q-value on this page comes from the same two-way t (or F) "
                       "on this design. G1 measured that t for H5's and H6's coefficients: under its calibrated null "
                       f"it rejects {two[0]:.2%} to {two[-1]:.2%} at 5%, so it is liberal here. G1 never sized the "
                       "other coefficients, the slope's included: read their p and q as indications, not tests at "
                       "5%.")
    return {"models": models, "g1": gs,
            "holm": {"family": family, "left_family": left, "post_gate": pg},
            "lookups": lk, "caveats": caveats, "provenance": dict(provenance)}


def _holm_of(models: list, h: str):
    """The binding Holm p of hypothesis h's primary term, or None."""
    for m in models:
        for t in m["terms"]:
            if t["hypothesis"] == h and t["role"] == "primary":
                return t["p_holm"]
    return None


def implied_vs_realised_data(results: pd.DataFrame, events: pd.DataFrame, measures: pd.DataFrame,
                             security: pd.DataFrame, p, provenance: dict) -> dict:
    """One point per primary event with a realised move, and H7's numbers (see the header)."""
    prim = primary_events(events, measures).merge(measures, on=["event_id", "eligible_crush"]) \
        .merge(security[["security_id", "gics_sector"]], on="security_id")
    pts = []
    for r in prim.itertuples(index=False):
        if r.realized_ret_0 is None or not np.isfinite(r.realized_ret_0):
            continue
        ivar = None if not (np.isfinite(r.evar_m1) and np.isfinite(r.sigma_d_m1)) else r.evar_m1 + r.sigma_d_m1 ** 2 / 252
        pts.append({"event_id": r.event_id, "ticker": r.ticker_at_event, "sector": r.gics_sector,
                    "day0": r.day0_session.isoformat(), "timing_used": r.timing_used,
                    "event_var": _r(r.evar_m1, 8), "implied_var_total": _r(ivar, 8),
                    "implied_move": _r(r.implied_move_m1, 5),
                    "implied_abs_move_total": _r(r.implied_abs_move_total_m1, 5),
                    "realized_ret_0": _r(r.realized_ret_0, 5), "abs_realized": _r(abs(r.realized_ret_0), 5),
                    "implied_move_status": r.implied_move_status, "surprise_scaled": _r(r.surprise_scaled, 6)})
    with_e = [x for x in pts if x["implied_abs_move_total"] is not None]
    ratio = np.array([math.log(x["abs_realized"] / x["implied_abs_move_total"]) for x in with_e
                      if x["abs_realized"] > 0])
    reg = results[(results["family"] == "regression") & (results["model_id"] == "implied_realised")]
    by = {(r["term"], r["statistic"]): r for r in reg.to_dict("records")}
    w2, w1 = by[("a=0,b=1", "twoway_date_wald")], by.get(("a=0,b=1", "cluster_date_wald"))
    a, b, ex = by[("a", "twoway_date_t")], by[("b", "twoway_date_t")], by[("exceed_share", "twoway_date_t")]
    gs = g1_summary(results, float(p["stats"]["alpha"]))
    g7 = [c for c in gs["calibrated"] if c["hypothesis"] == "H7" and c["primary"]][0]
    g7w = [c for c in gs["calibrated"] if c["hypothesis"] == "H7" and c["statistic"] == "cluster_date_wald"]
    lk = lookups(events, p)
    summary = {
        "n": len(pts), "n_evar_nonpositive": sum(1 for x in pts if x["event_var"] is not None and x["event_var"] <= 0),
        "n_with_implied_abs_move": len(with_e),
        "share_exceed": _f(ex["estimate"]), "share_exceed_se": _f(ex["se"]),
        "share_exceed_p": _sig(ex["p_value"]), "share_exceed_benchmark": 0.425,
        "mean_log_ratio": _f(float(ratio.mean())), "median_ratio": _f(float(np.exp(np.median(ratio)))),
        "regression": {"n": int(w2["n"]), "a": _f(a["estimate"], 8), "a_se": _f(a["se"], 8),
                       "b": _f(b["estimate"]), "b_se": _f(b["se"]), "b_ci": [_f(b["ci_lo"]), _f(b["ci_hi"])],
                       "wald_f": _f(w2["stat"]), "wald_df_num": _f(w2["df_num"], 2), "wald_df": _f(w2["df"], 2),
                       "wald_p": _sig(w2["p_value"]), "role": w2["role"], "p_holm": _sig(w2["p_holm"]),
                       "n_clusters_date": _int(w2["n_clusters"]), "n_clusters_firm": _int(w2["n_clusters_firm"]),
                       "wald_p_one_way": None if w1 is None else _sig(w1["p_value"]),
                       "g1_rate": g7["rejection_rate"], "g1_pass": g7["pass"], "g1_bar": _f(gs["band"][1]),
                       "g1_rate_one_way": g7w[0]["rejection_rate"] if g7w else None,
                       "g1_pass_one_way": g7w[0]["pass"] if g7w else None}}
    caveats = [provisional_caveat(lk),
               "Implied: at day -1, E (event variance) and sigma_d (ordinary variance per session = sigma_d^2/252, "
               "ADR 0003 §c). The expected |move| of a normal move with variance E + sigma_d^2/252 is "
               "sqrt(2/pi) sqrt(E + sigma_d^2/252); it is exceeded 42.5% of the time, not 50%, when pricing is fair.",
               "Realised: r0, the log change of the option-implied forward from day -1 to day 0 plus carry "
               "(DoltHub option quotes), on the same expiry both days."]
    if not g7["pass"] and w2["role"] == "primary":
        caveats.append(f"H7's Wald test failed gate G1's size check (its calibrated null rejects "
                       f"{g7['rejection_rate']:.2%} at 5%, band upper edge {gs['band'][1]:.2%}): the test is liberal on "
                       "this design, so a rejection by it would not be trusted. H7 stays in the declared Holm family "
                       f"(ADR 0005 §5, dated note of 2026-10-29) with this p-value; its Holm p is {_sig(w2['p_holm'])}"
                       + (", not rejected." if w2["p_holm"] > float(p["stats"]["alpha"]) else ", rejected by a liberal "
                          "statistic.")
                       + " The coefficient and share p-values come from the same kind of two-way statistic.")
    elif not g7["pass"]:
        caveats.append(f"H7's Wald test failed gate G1 (calibrated null rejects {g7['rejection_rate']:.2%} at 5%): H7 left "
                       "the binding Holm family and its p-value is exploratory (ADR 0005 §5).")
    return {"points": pts, "summary": summary, "lookups": lk, "caveats": caveats, "provenance": dict(provenance)}
