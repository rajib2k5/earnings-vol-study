# =============================================================================
# event_views.py — The milestone-3 views (data model §4, contract 0.4.0):
#   tests        the event-test rows of `results`, gate G1's verdicts and sizes,
#                the Holm family
#   event_paths  the mean abnormal path per rel_day -10 .. +10 with its two-way
#                bands (results, family descriptive), and every primary event's
#                own path (event_window_obs.aliv_mean_adj) for the animated
#                crush paths
#   terrain      company x event day: each company's mean aliv_mean_adj over its
#                primary events, per rel_day (the 3D view)
#   heatmap      the same company x event-day grid with n per cell, and the
#                company x season grid of crush_mean_adj
# Pure: the inputs are the committed tables, so the committed JSON can be
# rebuilt and checked without the local cache. Per-event and per-company
# values are MEAN-adjusted: the market-adjusted per-row values stay local
# (data model §2.1); market-adjusted numbers appear only as results' aggregates.
#
# THE PRIMARY SAMPLE here is the funnel's last step: daily events with
# eligible_crush (347 at milestone 3).
# Rounding (data model §4): log quantities 4 dp, p-values 4 significant
# figures, rates 4 dp. Missing is null, never NaN.
# Each tests row also carries `g1_size` (the calibrated G1 rejection rate of a
# robustness statistic whose p-value is withheld as mis-sized, else null) and
# `note` (why, or the season-cut counterfactual of a rad_season_p primary;
# else null): both added after the milestone-3 review (row_notes). Since the
# second fix round `g1_reps` gives the replications g1_size was measured on
# (2,000, or 10,000 for a rate re-measured near the bar: stats.g1.size_verdicts,
# the rule the results run withheld by), and a re-measured row that keeps its
# p-value says so in its note.
# Milestone 4: H5-H7 are regression rows (export/driver_views.py draws them);
# here they count in the Holm summary (`tested`, `left_family`), gate G1's
# calibrated list and designs; the power curves stay H1-H4's (H5-H7's power is
# per coefficient or slope, in drivers.json). Fixes after the milestone-4
# review: the Holm family is read from the rows as the results run built it
# (holm_family: H1-H7, H5-H7 staying in with a failed size check), and the
# caveat gives the post-gate sensitivity (post_gate).
# =============================================================================

import math

import pandas as pd

from earnings_vol.stats import g1, results as results_mod

REL_DAYS = list(range(-10, 11))
UNITS = {"crush_cm30": "log change of the 30-day IV", "runup": "abnormal log IV", "persist_1": "abnormal log IV",
         "persist_5": "abnormal log IV", "persist_10": "abnormal log IV", "dsigma_d": "log change of sigma_d",
         "crush_front_fixed": "log change of the front-expiry IV"}
SA_UNITS = "mean standardised value (precision-weighted)"


def provisional_caveat(lookups: dict) -> str:
    return (f"Timing labels are provisional: {lookups['n_done']} press releases were looked up and every other event "
            "keeps the calendar's label (not_checked) until SEC EDGAR is set up, so a few events may sit on the wrong "
            "day 0. Every number here depends on those labels.")


def lookups(events: pd.DataFrame, p) -> dict:
    return {"n_done": int((events["timing_status"] != "not_checked").sum()),
            "complete": bool(p["timing"]["lookups_complete"])}


def _r(v, dp: int = 4):
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return None
    return round(float(v), dp)


def _sig(v, n: int = 4):
    """4 significant figures (p-values)."""
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return None
    v = float(v)
    return 0.0 if v == 0 else float(f"{v:.{n}g}")


def _int(v):
    return None if v is None or (isinstance(v, float) and not math.isfinite(v)) else int(v)


def primary_events(events: pd.DataFrame, measures: pd.DataFrame) -> pd.DataFrame:
    """The primary sample (see the header), with ticker, sector and day 0."""
    j = events.merge(measures[["event_id", "eligible_crush"]], on="event_id")
    return j[(j["sample"] == "daily") & j["eligible_crush"]].sort_values("event_id", kind="mergesort")


def _null(v) -> bool:
    return v is None or (isinstance(v, float) and not math.isfinite(v))


def size_verdicts(sizes: pd.DataFrame, alpha: float) -> tuple[int, dict]:
    """(reps, verdicts): gate G1's verdict on every calibrated robustness statistic, rebuilt from
    the committed validation rows (g1:calibrated and g1:calibrated_remeasured) by the same rule
    the results run withheld by (stats.g1.size_verdicts)."""
    cal = sizes[sizes["measure"] == "g1:calibrated"]
    reps = int(cal["n"].iloc[0])
    rates: dict = {}
    for r in cal.to_dict("records"):
        rates.setdefault(r["hypothesis"], {})[r["statistic"]] = float(r["estimate"])
        if r["role"] == "primary":
            rates[r["hypothesis"]]["_primary"] = r["statistic"]
    rem = sizes[sizes["measure"] == f"g1:{results_mod.REMEASURED}"]
    remeasured = None
    if len(rem):
        remeasured = {"reps": int(rem["n"].iloc[0]), "rates": {}}
        for r in rem.to_dict("records"):
            remeasured["rates"].setdefault(r["hypothesis"], {})[r["statistic"]] = float(r["estimate"])
    return reps, g1.size_verdicts(rates, reps, alpha, remeasured)


def row_notes(ev: pd.DataFrame, verdicts: dict, reps: int, alpha: float) -> dict:
    """{result_id: (note, g1_size, g1_reps)} for the event-test rows that need a note:
      - a robustness row whose p-value is withheld because gate G1's calibrated design found its
        statistic oversized for the replications it was measured on (ADR 0005 §4, dated notes):
        g1_size is that rejection rate under the null, g1_reps those replications;
      - a robustness row re-measured near the bar that keeps its p-value (it says so);
      - a primary row whose rad_season_p sits on its floor, with the season-cut counterfactual
        row of stats/results.season_cut_rows (its Holm verdict depends on G alone), and that
        counterfactual row itself.
    A row the verdicts call oversized that still has a p-value is an error, not a note."""
    out = {}
    recs = ev.to_dict("records")
    hi = g1.binom_band(reps, alpha)[1]
    for r in recs:
        v = verdicts.get((r["hypothesis"], r["statistic"]))
        if v is None or not (r["role"] == "robustness" and r["subgroup_key"] == "all" and r["adjustment"] == "market"):
            continue
        again = (f" Its rate on {reps:,} replications was within one point of that count's bar ({hi:.2%}), so it "
                 f"was re-measured on {v['reps']:,} fresh replications and decided on those." if v["reps"] != reps else "")
        if v["oversized"]:
            if not _null(r["p_value"]):
                raise ValueError(f"{r['hypothesis']} {r['statistic']}: G1 finds it oversized but it keeps a p-value")
            out[r["result_id"]] = (f"p-value and interval withheld: under gate G1's calibrated null this statistic "
                                   f"rejects {v['rate']:.2%} of the time at 5% over {v['reps']:,} replications (band "
                                   f"upper edge {v['bar']:.2%} for that count), so ADR 0005 §4 drops its p-value. "
                                   f"The estimate stands.{again}", _r(v["rate"]), int(v["reps"]))
        elif again:
            out[r["result_id"]] = (f"p-value kept: under gate G1's calibrated null this statistic rejects "
                                   f"{v['rate']:.2%} of the time at 5% over {v['reps']:,} replications, within the "
                                   f"band upper edge {v['bar']:.2%} for that count.{again}", None, None)
    for c in recs:
        if c["subgroup_key"] != "season_cut":
            continue
        prim = [r for r in recs if r["role"] == "primary" and r["hypothesis"] == c["hypothesis"]]
        tw = [r for r in recs if r["hypothesis"] == c["hypothesis"] and r["statistic"] == "twoway_season_t"
              and r["subgroup_key"] == "all" and r["adjustment"] == "market"]
        if not prim:
            continue
        pr = prim[0]
        g = int(pr["n_clusters"])
        last, _, prev = c["subgroup_value"].partition("_into_")
        verdict = "not rejected" if c["p_holm"] > alpha else "rejected"
        sign = f" The sign is not in question: the two-way t is {tw[0]['stat']:.1f}." if tw else ""
        out[pr["result_id"]] = (
            f"This Holm p rests on {g} season clusters: {pr['statistic']} sits at its floor 2/2^{g} = "
            f"{_sig(2 / 2 ** g)}, so the verdict depends on G alone. With {last} merged into {prev} ({g - 1} "
            f"clusters, as ADR 0005 §2b expected) the p is {_sig(c['p_value'])} and the Holm p {_sig(c['p_holm'])}: "
            f"{verdict} at 5%.{sign}", None, None)
        out[c["result_id"]] = (f"Counterfactual season cut ({last} merged into {prev}), not a test of its own. "
                               f"Its p_holm ({_sig(c['p_holm'])}) is the Holm p {c['hypothesis']} would get with "
                               "this p, the family's other p-values as reported.", None, None)
    return out


def holm_family(results: pd.DataFrame, declared: list) -> tuple[list, list]:
    """(binding family, left the family) as the results run built them: a declared hypothesis
    left the family when its declared primary statistic is a row of role exploratory (ADR 0005 §5);
    the others are the family. A family member whose primary row has no p_holm is an error."""
    tested = results[results["family"].isin(results_mod.TESTED_FAMILIES) & results["hypothesis"].notna()]
    left = sorted(set(tested.loc[tested["role"] == "exploratory", "hypothesis"]) & set(declared))
    family = [h for h in declared if h not in left]
    prim = tested[tested["role"] == "primary"]
    bad = sorted(set(prim.loc[prim["p_holm"].isna(), "hypothesis"]) | (set(prim["hypothesis"]) - set(family)))
    if bad:
        raise ValueError(f"primary rows of {', '.join(bad)} without a Holm p, or outside the family")
    return family, left


def post_gate(results: pd.DataFrame) -> dict:
    """The descriptive Holm sensitivity (results.holm_post_gate_rows): the post-gate family, each
    member's Holm p over it, and each season-cut counterfactual's ({hypothesis: Holm p})."""
    d = results[(results["family"] == "descriptive") & (results["measure"] == "holm_post_gate")]
    main = d[d["subgroup_key"] == "all"]
    cut = d[d["subgroup_key"] == "season_cut"]
    return {"family": [h for h in main["hypothesis"]],
            "p_holm": {r["hypothesis"]: _sig(r["estimate"]) for r in main.to_dict("records")},
            "season_cut": {r["hypothesis"]: _sig(r["estimate"]) for r in cut.to_dict("records")}}


def holm_caveat(family: list, failed: list, calibrated: list, stayed: list | None = None,
                pg: dict | None = None) -> str:
    """The sentences on Holm's family: who is in it; who failed G1's size check and stays in it
    (H5-H7, ADR 0005 §5 dated note of 2026-10-29), with the post-gate sensitivity `pg`
    (post_gate()); and who left it after a failed gate (ADR 0005 §5)."""
    rate = {c["hypothesis"]: c["rejection_rate"] for c in calibrated}
    out = f"Holm runs over {', '.join(family)} ({len(family)} hypotheses)"
    if stayed:
        out += (". " + ", ".join(f"{h} ({rate[h]:.2%})" for h in stayed) + " failed gate G1's regression size check, "
                "which ran before their results were computed: their statistics are liberal on this design, so a "
                "rejection by them would not be trusted. They stay in the declared family with their real p-values "
                "(ADR 0005 §5, dated note of 2026-10-29); their rows are in drivers.json")
        if pg and pg["family"]:
            cut = "".join(f", {h}'s season cut {v}" for h, v in pg["season_cut"].items())
            out += (f". Sensitivity, not binding: over the family without them ({', '.join(pg['family'])}) the Holm p "
                    "would be " + ", ".join(f"{h} {v}" for h, v in pg["p_holm"].items()) + cut)
    if failed:
        out += (". " + ", ".join(f"{h} ({rate[h]:.2%})" for h in failed) + " failed gate G1's calibrated design, which "
                "ran before their results were computed, and left the binding family (ADR 0005 §5): their primary "
                "rows are exploratory")
    return out + "."


def tests_data(results: pd.DataFrame, events: pd.DataFrame, p, provenance: dict) -> dict:
    ev = results[results["family"] == "event_test"]
    val = results[results["family"] == "validation"]
    sizes = val[val["measure"].str.startswith("g1:")]
    alpha = float(p["stats"]["alpha"])
    reps, verdicts = size_verdicts(sizes, alpha)
    lo, hi = g1.binom_band(reps, alpha)
    notes = row_notes(ev, verdicts, reps, alpha)
    rows = []
    for r in ev.to_dict("records"):
        units = SA_UNITS if r["estimand"] == "precision_weighted" else UNITS.get(r["measure"], "")
        if r["statistic"] == "gen_sign_z":
            units = "share of events below 0"
        elif r["statistic"] == "rank_t":
            units = "mean standardised rank"
        note, g1_size, g1_reps = notes.get(r["result_id"], (None, None, None))
        rows.append({
            "hypothesis": r["hypothesis"], "role": r["role"], "measure": r["measure"], "statistic": r["statistic"],
            "estimand": r["estimand"], "sample": r["sample"], "subgroup_key": r["subgroup_key"],
            "subgroup_value": r["subgroup_value"], "adjustment": r["adjustment"], "rel_day": _int(r["rel_day"]),
            "units": units, "n": int(r["n"]), "n_clusters": _int(r["n_clusters"]),
            "n_clusters_firm": _int(r["n_clusters_firm"]), "estimate": _r(r["estimate"]), "se": _r(r["se"]),
            "stat": _r(r["stat"]), "df": _r(r["df"], 2), "p_value": _sig(r["p_value"]), "p_holm": _sig(r["p_holm"]),
            "q_bh": _sig(r["q_bh"]), "ci_lo": _r(r["ci_lo"]), "ci_hi": _r(r["ci_hi"]), "rbar": _r(r["rbar"], 6),
            "g1_size": g1_size, "g1_reps": g1_reps, "note": note})
    designs, calibrated, power = [], [], {}
    for r in sizes.to_dict("records"):
        name = r["measure"][len("g1:"):]
        if name == results_mod.REMEASURED:      # other replications than g1.reps: in the rows' notes
            continue
        if name.startswith("power_"):
            if r["role"] == "primary" and r["hypothesis"] in g1.TESTS:
                power.setdefault(r["hypothesis"], []).append((float(name.split(":")[1]), float(r["estimate"])))
            continue
        item = {"design": name, "hypothesis": r["hypothesis"], "statistic": r["statistic"],
                "primary": r["role"] == "primary", "rejection_rate": _r(r["estimate"])}
        designs.append(item)
        if name == "calibrated" and r["role"] == "primary":
            calibrated.append({"hypothesis": r["hypothesis"], "statistic": r["statistic"],
                               "rejection_rate": _r(r["estimate"]), "pass": bool(r["estimate"] <= hi)})
    pw = []
    for h in sorted(power):
        pts = sorted(power[h])
        pw.append({"hypothesis": h, "shifts": [s for s, _ in pts], "power": [_r(x) for _, x in pts],
                   "detectable_80": _r(g1.detectable_shift([s for s, _ in pts], [x for _, x in pts]))})
    cal = val[val["measure"] == "g1_calibration:params"]
    cal_sd = val[val["measure"] == "g1_calibration_sigma_d:params"]
    family, left = holm_family(results, list(p["stats"]["holm_family"]))
    tested_rows = results[results["family"].isin(results_mod.TESTED_FAMILIES)]
    tested = sorted(set(tested_rows.loc[tested_rows["role"] == "primary", "hypothesis"]))
    failed = [c["hypothesis"] for c in calibrated if not c["pass"]]
    stayed = [h for h in failed if h in family]
    over = sorted((h, s, v["rate"], v["reps"]) for (h, s), v in verdicts.items() if v["oversized"])
    again = sorted((h, s, v["rate"], v["reps"], v["oversized"]) for (h, s), v in verdicts.items() if v["reps"] != reps)
    lk = lookups(events, p)
    hi_re = {n: g1.binom_band(n, alpha)[1] for n in {v["reps"] for v in verdicts.values()}}
    bars = ", ".join(f"{hi_re[n]:.2%} at {n:,}" for n in sorted(hi_re))
    oversized = ([f"Gate G1's calibrated design finds these robustness rows oversized (rejection rate under the null "
                  f"above the band's upper edge for the replications it was measured on: {bars}): "
                  + "; ".join(f"{h} {s} {r:.2%}" + ("" if n == reps else f" (on {n:,})") for h, s, r, n in over)
                  + ". As ADR 0005 §4 does for rows known to be mis-sized, their p-values and intervals are withheld "
                  "(null; g1_size and g1_reps give the rate and its replications instead) and their estimates are "
                  "shown."] if over else [])
    if again:
        oversized.append(f"Robustness rates within one point of the {hi:.2%} bar on {reps:,} replications are "
                         f"re-measured on more replications and decided against that count's bar (ADR 0005 §4): "
                         + "; ".join(f"{h} {s} {r:.2%} on {n:,}, " + ("withheld" if o else "p-value kept")
                                     for h, s, r, n, o in again) + ".")
    return {
        "rows": rows,
        "g1": {"reps": reps, "band": [lo, hi], "calibrated": sorted(calibrated, key=lambda c: c["hypothesis"]),
               "designs": designs, "power": pw,
               "calibration": {**{r["statistic"]: _r(r["estimate"], 6) for r in cal.to_dict("records")},
                               **{f"sigma_d:{r['statistic']}": _r(r["estimate"], 6)
                                  for r in cal_sd.to_dict("records")}}},
        "holm": {"family": family, "tested": tested, "untested": [h for h in family if h not in tested],
                 "left_family": left},
        "lookups": lk,
        "caveats": [
            provisional_caveat(lk),
            holm_caveat(family, left, calibrated, stayed, post_gate(results)),
            "Primary rows are equal-weighted means of market-adjusted abnormal log IV (VIX, beta per company). "
            "Precision-weighted rows (BMP, KP, KPP, Patell) test another estimand and are robustness only.",
            "Market-adjusted numbers are aggregates of values computed with the Cboe VIX index (via FRED VIXCLS); "
            "see DATA.md for Cboe's terms.",
        ] + oversized,
        "provenance": dict(provenance),
    }


def paths_data(results: pd.DataFrame, ewo: pd.DataFrame, events: pd.DataFrame, measures: pd.DataFrame,
               security: pd.DataFrame, p, provenance: dict) -> dict:
    d = results[(results["family"] == "descriptive") & (results["measure"] == "aliv_path")]
    series = []
    for (adj, key, val), g in d.groupby(["adjustment", "subgroup_key", "subgroup_value"], sort=True):
        by = {int(r["rel_day"]): r for r in g.to_dict("records")}
        series.append({"measure": "aliv", "adjustment": adj, "units": "abnormal log IV", "subgroup_key": key,
                       "subgroup_value": val,
                       "n": [_int(by[k]["n"]) if k in by else None for k in REL_DAYS],
                       "mean": [_r(by[k]["estimate"]) if k in by else None for k in REL_DAYS],
                       "ci_lo": [_r(by[k]["ci_lo"]) if k in by else None for k in REL_DAYS],
                       "ci_hi": [_r(by[k]["ci_hi"]) if k in by else None for k in REL_DAYS]})
    prim = primary_events(events, measures).merge(security[["security_id", "gics_sector"]], on="security_id")
    w = ewo[ewo["event_id"].isin(prim["event_id"]) & ewo["rel_day"].between(-10, 10)]
    vals = {(e, int(r)): v for e, r, v in zip(w["event_id"], w["rel_day"], w["aliv_mean_adj"])}
    per_event = [{"event_id": r.event_id, "ticker": r.ticker_at_event, "sector": r.gics_sector,
                  "day0": r.day0_session.isoformat(), "timing_used": r.timing_used,
                  "values": [_r(vals.get((r.event_id, k))) for k in REL_DAYS]}
                 for r in prim.itertuples(index=False)]
    lk = lookups(events, p)
    return {"rel_days": REL_DAYS, "series": series, "per_event": per_event, "lookups": lk,
            "caveats": [provisional_caveat(lk),
                        "Each path is the event's abnormal log IV, mean-adjusted: ln IV minus its mean over the "
                        "clean baseline [-60, -22] (ADR 0004). The bands are pointwise 95% intervals, two-way "
                        "clustered by season and company: a description, not a test of each day.",
                        "The market-adjusted mean path (VIX-adjusted) is shown as an aggregate only; per-event "
                        "values are mean-adjusted."],
            "provenance": dict(provenance)}


def company_grid(ewo: pd.DataFrame, events: pd.DataFrame, measures: pd.DataFrame,
                 security: pd.DataFrame) -> tuple[list[dict], list[list], list[list]]:
    """(rows, mean values, n): companies in sector order (then ticker) x rel_day -10 .. +10,
    each cell the mean aliv_mean_adj over the company's primary events observed there."""
    prim = primary_events(events, measures)
    w = ewo[ewo["event_id"].isin(prim["event_id"]) & ewo["rel_day"].between(-10, 10)]
    w = w.merge(prim[["event_id", "security_id"]], on="event_id")
    sec = security.set_index("security_id")
    comps = sorted(set(prim["security_id"]), key=lambda s: (sec.loc[s, "gics_sector"], s))
    rows, values, ns = [], [], []
    tick = prim.sort_values("day0_session").groupby("security_id")["ticker_at_event"].last()
    for c in comps:
        g = w[w["security_id"] == c].dropna(subset=["aliv_mean_adj"])
        agg = g.groupby("rel_day")["aliv_mean_adj"].agg(["mean", "size"])
        rows.append({"security_id": c, "ticker": tick[c], "sector": sec.loc[c, "gics_sector"],
                     "n_events": int((prim["security_id"] == c).sum())})
        values.append([_r(agg.loc[k, "mean"]) if k in agg.index else None for k in REL_DAYS])
        ns.append([int(agg.loc[k, "size"]) if k in agg.index else 0 for k in REL_DAYS])
    return rows, values, ns


def terrain_data(ewo, events, measures, security, p, provenance: dict) -> dict:
    rows, values, _ = company_grid(ewo, events, measures, security)
    lk = lookups(events, p)
    return {"measure": "aliv_mean_adj", "units": "abnormal log IV (mean-adjusted)", "rel_days": REL_DAYS,
            "rows": rows, "values": values, "row_order": "GICS sector, then security_id", "lookups": lk,
            "caveats": [provisional_caveat(lk),
                        "Each cell is one company's mean over its primary events (about 7): a description of "
                        "the event-time shape, not a test."],
            "provenance": dict(provenance)}


def heatmap_data(ewo, events, measures, security, p, provenance: dict) -> dict:
    rows, values, ns = company_grid(ewo, events, measures, security)
    prim = primary_events(events, measures)
    seasons = sorted(set(prim["season"]))
    crush = {(s, q): v for s, q, v in zip(prim["security_id"], prim["season"],
                                          prim.merge(measures[["event_id", "crush_mean_adj"]],
                                                     on="event_id")["crush_mean_adj"])}
    cnt = prim.groupby(["security_id", "season"]).size().to_dict()
    sv = [[_r(crush.get((r["security_id"], q))) if cnt.get((r["security_id"], q), 0) == 1 else None
           for q in seasons] for r in rows]
    sn = [[int(cnt.get((r["security_id"], q), 0)) for q in seasons] for r in rows]
    labels = [r["ticker"] for r in rows]
    keys = [r["security_id"] for r in rows]
    lk = lookups(events, p)
    return {"grids": [
        {"id": "company_by_event_day", "title": "Abnormal log IV by company and event day",
         "measure": "aliv_mean_adj", "units": "abnormal log IV (mean-adjusted)", "row_labels": labels,
         "row_keys": keys, "col_labels": [str(k) for k in REL_DAYS], "values": values, "n": ns, "q": None},
        {"id": "company_by_season", "title": "30-day IV crush by company and season", "measure": "crush_mean_adj",
         "units": "log change of the 30-day IV, day -1 to day 0", "row_labels": labels, "row_keys": keys,
         "col_labels": seasons, "values": sv, "n": sn, "q": None}],
        "lookups": lk,
        "caveats": [provisional_caveat(lk),
                    "Cells are descriptive: one company's mean (event-day grid) or one event (season grid). "
                    "No cell is tested."],
        "provenance": dict(provenance)}


def check_finite(obj) -> None:
    """Raise if any float in a payload is NaN or infinite (the envelope refuses them too)."""
    if isinstance(obj, float) and not math.isfinite(obj):
        raise ValueError("a non-finite number in a payload")
    if isinstance(obj, dict):
        for v in obj.values():
            check_finite(v)
    elif isinstance(obj, list):
        for v in obj:
            check_finite(v)

