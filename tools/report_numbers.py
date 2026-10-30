"""Every measured number in the report, the README and the PR/FAQ, regenerated from the committed data.

    uv run --frozen python tools/report_numbers.py            # render the report and the README/PR-FAQ blocks
    uv run --frozen python tools/report_numbers.py --check    # exit 1 if a rendered file is stale or the data disagree
    uv run --frozen python tools/report_numbers.py --list     # print every number with its source

Inputs, all committed:

- ``data/derived/results.parquet`` (the primary, robustness and exploratory rows, Holm, the post-gate sensitivity);
- ``app/public/data/{meta,sample_funnel,iv_measures,tests,event_paths,drivers,implied_vs_realised}.json``;
- ``research/prototypes/rhobar_crush.out.txt``, the kept output of the milestone-4 ρ̄ prototype (its inputs are
  per-event VIX-adjusted values, which stay local, so ρ̄ cannot be recomputed from committed data).

One number is not in the committed data: **the 473 press-release look-ups that ADR 0002 §3 requires**
(``LOOKUPS_REQUIRED``). The events run counts them with the Yahoo gap flags, and one of those flags
(``outside_flag_yf``) stays local. It is pinned here with its source (milestone 1 §6, ``events_report.json``: 453
still to do after the 20 done) and, when the local stage report exists, ``--check`` compares it with that report.

Templates and outputs:

- ``docs/report/templates/earnings-vol-report.md`` → ``docs/report/earnings-vol-report.md`` (the whole file);
- ``docs/report/templates/<block>.md`` → the text between ``<!-- numbers:<block> -->`` and
  ``<!-- /numbers:<block> -->`` in ``README.md`` and ``docs/prfaq.md`` (the rest of those files is hand-written).

A placeholder is ``{{key}}``. An unknown key is an error, so a template cannot render with a hole in it.
``--check`` renders everything in memory and compares it with the files on disk, byte for byte. It also
cross-checks numbers that two inputs both hold (``cross_check``), and checks the qualitative claims that the
templates' hand-written sentences make about the numbers, such as a sign, a verdict or an interval holding 1
(``prose_check``): new data that contradicted a sentence would fail instead of leaving the sentence wrong. The test
``tests/test_report_numbers.py`` runs it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
MINUS = "−"

# ADR 0002 §3's required look-ups (milestone 1 §6: 422 by date, 30 null labels, 43 gap triggers, some with two
# reasons). Not derivable from committed data: the gap trigger also reads the local outside_flag_yf.
LOOKUPS_REQUIRED = 473
LOOKUPS_SOURCE = "docs/milestones/01-universe-and-events.md §6 (events_report.json in the local stage)"

TEMPLATES = "docs/report/templates"
REPORT_TEMPLATE = f"{TEMPLATES}/earnings-vol-report.md"
REPORT_OUT = "docs/report/earnings-vol-report.md"
EXPORTS_STAMP = "docs/report/earnings-vol-report.build.json"  # written by tools/build_report.py
EXPORTS = ("pdf", "docx")
# (file, block name): the block's template is TEMPLATES/<name>.md
BLOCKS: list[tuple[str, str]] = [
    ("README.md", "readme-summary"),
    ("README.md", "readme-results"),
    ("docs/prfaq.md", "prfaq-headline"),
    ("docs/prfaq.md", "prfaq-measured"),
    ("docs/milestones/05-report-and-polish.md", "milestone5-results"),
]
PLACEHOLDER = re.compile(r"\{\{\s*([^{}]*?)\s*\}\}")  # any key; an unknown one is an error


# --- formatting --------------------------------------------------------------------------------------------

def _minus(s: str) -> str:
    return s.replace("-", MINUS)


def fnum(x: float, nd: int) -> str:
    """Fixed decimals, Unicode minus: fnum(-0.19937, 3) == '−0.199'."""
    s = f"{x:.{nd}f}"
    if float(s) == 0:
        s = s.lstrip("-")
    return _minus(s)


def fsigned(x: float, nd: int) -> str:
    """Fixed decimals with an explicit sign: fsigned(0.2319, 3) == '+0.232'."""
    s = fnum(x, nd)
    return s if s.startswith(MINUS) or float(f"{x:.{nd}f}") == 0 else "+" + s


def fsci(x: float, sig: int = 2) -> str:
    """Scientific, `sig` significant digits: fsci(5.8005e-23) == '5.8e−23'."""
    mant, exp = f"{x:.{sig - 1}e}".split("e")
    return _minus(f"{mant}e{int(exp)}")


def fp(p: float) -> str:
    """A p-value: '1' at 1; scientific below 0.001; two significant digits below 0.01; three above (trailing
    zeros kept, so 0.7496 is '0.750')."""
    if p is None or (isinstance(p, float) and math.isnan(p)):
        raise ValueError("a p-value is missing")
    if p >= 0.9995:
        return "1"
    if p < 1e-3:
        return fsci(p, 2)
    return f"{p:#.2g}" if p < 0.01 else f"{p:#.3g}"


def fpct(x: float, nd: int = 2) -> str:
    """A share as a percentage: fpct(0.0955) == '9.55%'."""
    return _minus(f"{100 * x:.{nd}f}%")


def fint(n: int) -> str:
    """An integer with thousands separators: fint(1353) == '1,353'."""
    return f"{int(n):,}"


def fci(lo: float, hi: float, nd: int) -> str:
    return f"[{fnum(lo, nd)}, {fnum(hi, nd)}]"


# --- inputs ------------------------------------------------------------------------------------------------

def load(root: Path) -> dict:
    """Read every input once. The JSON envelopes are unwrapped to their `data`."""
    def js(kind: str) -> dict:
        return json.loads((root / "app/public/data" / f"{kind}.json").read_text())

    env_meta = js("meta")
    return {
        "results": pd.read_parquet(root / "data/derived/results.parquet"),
        "meta_env": env_meta,
        "meta": env_meta["data"],
        **{k: js(k)["data"] for k in ("sample_funnel", "iv_measures", "tests", "event_paths", "drivers",
                                      "implied_vs_realised")},
        "rhobar_out": (root / "research/prototypes/rhobar_crush.out.txt").read_text(),
    }


def one(df: pd.DataFrame, what: str) -> pd.Series:
    """The single row of `df`; anything else is an error (a filter that matches 0 or 2 rows is a bug)."""
    if len(df) != 1:
        raise ValueError(f"{what}: expected 1 row, found {len(df)}")
    return df.iloc[0]


def primary(r: pd.DataFrame, h: str) -> pd.Series:
    return one(r[(r.hypothesis == h) & (r.role == "primary") & (r.family.isin(["event_test", "regression"]))],
               f"{h} primary")


def reg_term(r: pd.DataFrame, model: str, term: str, sample: str = "daily", statistic: str = "twoway_date_t",
             role: str = "exploratory") -> pd.Series:
    return one(r[(r.family == "regression") & (r.model_id == model) & (r.term == term) & (r["sample"] == sample)
                 & (r.statistic == statistic) & (r.role == role)], f"{model}/{term}/{sample}")


def test_row(tests: dict, **want) -> dict:
    rows = [x for x in tests["rows"] if all(x.get(k) == v for k, v in want.items())]
    if len(rows) != 1:
        raise ValueError(f"tests.json {want}: expected 1 row, found {len(rows)}")
    return rows[0]


def g1_rate(tests: dict, h: str) -> float:
    rows = [x for x in tests["g1"]["calibrated"] if x["hypothesis"] == h]
    if len(rows) != 1:
        raise ValueError(f"tests.json g1.calibrated {h}: {len(rows)} rows")
    return rows[0]["rejection_rate"]


def power80(blob: dict, h: str) -> float:
    rows = [x for x in blob["g1"]["power"] if x["hypothesis"] == h]
    if len(rows) != 1:
        raise ValueError(f"g1.power {h}: {len(rows)} rows")
    return rows[0]["detectable_80"]


def path_at(paths: dict, day: int, adjustment: str = "market", subgroup: str = "all") -> tuple[float, float, float]:
    s = [x for x in paths["series"] if x["adjustment"] == adjustment and x["subgroup_value"] == subgroup]
    if len(s) != 1:
        raise ValueError(f"event_paths {adjustment}/{subgroup}: {len(s)} series")
    i = paths["rel_days"].index(day)
    return s[0]["mean"][i], s[0]["ci_lo"][i], s[0]["ci_hi"][i]


def prototype_value(text: str, label: str) -> float:
    m = re.search(re.escape(label) + r"\s*(-?\d+\.\d+)", text)
    if not m:
        raise ValueError(f"rhobar_crush.out.txt has no line '{label}'")
    return float(m.group(1))


# --- the numbers -------------------------------------------------------------------------------------------

def numbers(d: dict) -> dict[str, tuple[str, str]]:
    """key -> (formatted value, source). Every number the templates may use."""
    r, meta, fun, ivm = d["results"], d["meta"], d["sample_funnel"], d["iv_measures"]
    tests, paths, drv, ivr = d["tests"], d["event_paths"], d["drivers"], d["implied_vs_realised"]
    out: dict[str, tuple[str, str]] = {}

    def put(key: str, value: str, source: str) -> None:
        if key in out:
            raise KeyError(f"duplicate key {key}")
        out[key] = (value, source)

    # Sample, provenance and parameters (meta.json)
    smp, prov, par = meta["sample"], meta["provenance"], meta["params"]
    put("sample.n_events", fint(smp["n_events"]), "meta.json sample.n_events")
    put("sample.n_companies", fint(smp["n_securities"]), "meta.json sample.n_securities")
    put("sample.day0_from", smp["day0_from"], "meta.json sample.day0_from (the daily window, params.yaml)")
    put("sample.day0_to", smp["day0_to"], "meta.json sample.day0_to (the daily window, params.yaml)")
    days = sorted(e["day0"] for e in d["event_paths"]["per_event"])
    if len(days) != smp["n_events"]:
        raise ValueError(f"event_paths.json has {len(days)} primary events, meta.json {smp['n_events']}")
    put("sample.first_day0", days[0], "event_paths.json per_event: the earliest day 0")
    put("sample.last_day0", days[-1], "event_paths.json per_event: the latest day 0")
    put("meta.schema_version", d["meta_env"]["schema_version"], "meta.json schema_version")
    put("meta.source_commit", d["meta_env"]["source_commit"], "meta.json source_commit")
    put("meta.params_hash", prov["params_hash"][:16], "meta.json provenance.params_hash (first 16)")
    put("meta.dolt_earnings", prov["dolt_commits"]["earnings"], "meta.json provenance.dolt_commits")
    put("meta.dolt_options", prov["dolt_commits"]["options"], "meta.json provenance.dolt_commits")
    b0, b1 = par["baseline"]
    w0, w1 = par["event_window"]
    put("params.baseline", f"[{fsigned(b0, 0)}, {fsigned(b1, 0)}]", "meta.json params.baseline")
    put("params.window", f"[{fsigned(w0, 0)}, {fsigned(w1, 0)}]", "meta.json params.event_window")
    put("params.cm30_sessions", fint(par["cm30_horizon_sessions"]), "meta.json params.cm30_horizon_sessions")

    # The sample funnel (sample_funnel.json)
    steps = {s["step"]: s for s in fun["steps"]}
    for step in ("calendar_events", "timing_known", "daily_range", "crush_observed", "iv_usable",
                 "baseline_minimum"):
        put(f"funnel.{step}", fint(steps[step]["n_events"]), f"sample_funnel.json steps[{step}].n_events")
        put(f"funnel.{step}.removed", fint(steps[step]["n_removed"]), f"sample_funnel.json steps[{step}].n_removed")
    for s in fun["by_sample"]:
        put(f"events.{s['sample']}", fint(s["n_events"]), f"sample_funnel.json by_sample[{s['sample']}]")
    tsc = fun["timing_status_counts"]
    for k in ("confirmed", "corrected", "date_corrected", "inferred", "not_checked"):
        put(f"timing.{k}", fint(tsc[k]), f"sample_funnel.json timing_status_counts.{k}")
    done = fun["lookups"]["n_done"]
    put("lookups.done", fint(done), "sample_funnel.json lookups.n_done")
    put("lookups.required", fint(LOOKUPS_REQUIRED), LOOKUPS_SOURCE)
    put("lookups.left", fint(LOOKUPS_REQUIRED - done), "lookups.required − lookups.done")
    ev = fun["evar_nonpositive"]
    put("evar.nonpositive", fint(ev["n"]), "sample_funnel.json evar_nonpositive.n")

    # Gate G1 (tests.json, drivers.json)
    lo, hi = tests["g1"]["band"]
    put("g1.band_lo", fpct(lo), "tests.json g1.band[0]")
    put("g1.band_hi", fpct(hi), "tests.json g1.band[1]")
    put("g1.reps", fint(tests["g1"]["reps"]), "tests.json g1.reps")
    for h in ("H1", "H2", "H3", "H4", "H5", "H6", "H7"):
        put(f"{h.lower()}.g1", fpct(g1_rate(tests, h)), f"tests.json g1.calibrated[{h}].rejection_rate")
    for h in ("H1", "H2", "H3", "H4"):
        put(f"{h.lower()}.power80", fnum(power80(tests, h), 3), f"tests.json g1.power[{h}].detectable_80")
    for h in ("H5", "H6"):
        put(f"{h.lower()}.power80", fnum(power80(drv, h), 3), f"drivers.json g1.power[{h}].detectable_80")
    oneway = {x["hypothesis"]: x["rejection_rate"] for x in drv["g1"]["calibrated"]
              if x["statistic"] in ("cluster_date_t", "cluster_date_wald")}
    for h in ("H5", "H6", "H7"):
        put(f"{h.lower()}.g1_oneway", fpct(oneway[h]), f"drivers.json g1.calibrated[{h}, one-way]")

    # H1-H7: the primary rows (results.parquet)
    rows = {h: primary(r, h) for h in ("H1", "H2", "H3", "H4", "H5", "H6", "H7")}
    put("holm.m", fint(len(tests["holm"]["family"])), "tests.json holm.family")
    for h in ("H1", "H2", "H3", "H4", "H5", "H6", "H7"):
        x, k = rows[h], h.lower()
        src = f"results.parquet {h} primary ({x.statistic})"
        put(f"{k}.n", fint(x.n), src + " n")
        put(f"{k}.p", fp(x.p_value), src + " p_value")
        put(f"{k}.p_holm", fp(x.p_holm), src + " p_holm")
        put(f"{k}.statistic", x.statistic, src)
        if not math.isnan(x.n_clusters):
            put(f"{k}.g_time", fint(x.n_clusters), src + " n_clusters")
        if not math.isnan(x.n_clusters_firm):
            put(f"{k}.g_firm", fint(x.n_clusters_firm), src + " n_clusters_firm")
    for h in ("H1", "H2", "H3", "H4", "H5", "H6"):
        x, k = rows[h], h.lower()
        src = f"results.parquet {h} primary"
        put(f"{k}.est", fsigned(x.estimate, 3), src + " estimate")
        put(f"{k}.est4", fsigned(x.estimate, 4), src + " estimate")
        if not math.isnan(x.se):
            put(f"{k}.se", fnum(x.se, 4), src + " se")
            put(f"{k}.t", fnum(x.stat, 2), src + " stat")
            put(f"{k}.ci", fci(x.ci_lo, x.ci_hi, 3), src + " ci_lo, ci_hi")
    h1 = rows["H1"]
    if not h1.estimate < 0:
        raise ValueError(f"the texts say IV falls; H1's estimate is {h1.estimate}")
    put("h1.fall", fnum(-h1.estimate, 3), "−(results.parquet H1 primary estimate)")
    put("h1.fall4", fnum(-h1.estimate, 4), "−(results.parquet H1 primary estimate)")
    put("h1.df", fint(h1.df), "results.parquet H1 primary df")
    put("h1.pct_fall", fpct(1 - math.exp(h1.estimate), 1), "1 − exp(H1 estimate)")
    put("h3.df", fint(rows["H3"].df), "results.parquet H3 primary df")
    h7 = rows["H7"]
    put("h7.f", fnum(h7.stat, 2), "results.parquet H7 primary stat (F)")
    put("h7.df_num", fint(h7.df_num), "results.parquet H7 primary df_num")
    put("h7.df", fint(h7.df), "results.parquet H7 primary df")

    # H2: the season count, its cut, the robustness t
    cut = one(r[(r.hypothesis == "H2") & (r.subgroup_key == "season_cut") & (r.family == "event_test")], "H2 cut")
    put("h2.cut_g", fint(cut.n_clusters), "results.parquet H2 season_cut n_clusters")
    put("h2.cut_p", fp(cut.p_value), "results.parquet H2 season_cut p_value")
    put("h2.cut_p_holm", fp(cut.p_holm), "results.parquet H2 season_cut p_holm")
    tw = one(r[(r.hypothesis == "H2") & (r.statistic == "twoway_season_t") & (r.family == "event_test")
               & (r.adjustment == "market")], "H2 twoway_season_t")
    put("h2.twoway_t", fnum(tw.stat, 2), "results.parquet H2 twoway_season_t stat")
    put("h2.twoway_p", fp(tw.p_value), "results.parquet H2 twoway_season_t p_value")
    floor = 2 / 2 ** int(rows["H2"].n_clusters)
    if not math.isclose(floor, rows["H2"].p_value):
        raise ValueError(f"H2's p {rows['H2'].p_value} is not the enumeration floor {floor}")
    put("h2.floor_g", fint(rows["H2"].n_clusters), "results.parquet H2 primary n_clusters")

    # The post-gate sensitivity (results.parquet holm_post_gate rows)
    pg = r[r.measure == "holm_post_gate"]
    put("postgate.h1", fp(one(pg[pg.hypothesis == "H1"], "post-gate H1").estimate), "results.parquet holm_post_gate H1")
    put("postgate.h2", fp(one(pg[(pg.hypothesis == "H2") & (pg.subgroup_value == "all")], "post-gate H2").estimate),
        "results.parquet holm_post_gate H2")
    put("postgate.h2_cut", fp(one(pg[(pg.hypothesis == "H2") & (pg.subgroup_key == "season_cut")],
                                  "post-gate H2 cut").estimate), "results.parquet holm_post_gate H2 season_cut")

    # H5-H7 details
    b = reg_term(r, "implied_realised", "b")
    a = reg_term(r, "implied_realised", "a")
    put("h7.b", fnum(b.estimate, 2), "results.parquet implied_realised b")
    put("h7.b3", fnum(b.estimate, 3), "results.parquet implied_realised b")
    put("h7.b_ci", fci(b.ci_lo, b.ci_hi, 2), "results.parquet implied_realised b ci")
    put("h7.b_p", fp(b.p_value), "results.parquet implied_realised b p (against 1)")
    put("h7.a", fnum(a.estimate, 5), "results.parquet implied_realised a")
    put("h7.a_p", fp(a.p_value), "results.parquet implied_realised a p")
    b2 = reg_term(r, "implied_realised_m2", "b")
    w2 = reg_term(r, "implied_realised_m2", "a=0,b=1", statistic="twoway_date_wald")
    put("h7.m2_b", fnum(b2.estimate, 2), "results.parquet implied_realised_m2 b")
    put("h7.m2_n", fint(b2.n), "results.parquet implied_realised_m2 n")
    put("h7.m2_p", fp(w2.p_value), "results.parquet implied_realised_m2 Wald p")
    r2 = one(r[(r.model_id == "crush_drivers") & (r.statistic == "r2") & (r["sample"] == "daily")], "crush R2")
    put("drivers.r2", fnum(r2.estimate, 3), "results.parquet crush_drivers r2")

    # Exploratory regression rows
    slope = reg_term(r, "crush_drivers", "slope")
    size = reg_term(r, "crush_drivers", "size")
    put("slope.est", fsigned(slope.estimate, 3), "results.parquet crush_drivers slope")
    put("slope.p", fp(slope.p_value), "results.parquet crush_drivers slope p")
    put("slope.q", f"{slope.q_bh:.4f}" if slope.q_bh >= 1e-4 else fsci(slope.q_bh), "results.parquet slope q_bh")
    put("size.est", fsigned(size.estimate, 3), "results.parquet crush_drivers size")
    put("size.q", fp(size.q_bh), "results.parquet crush_drivers size q_bh")
    for key, model, term in (("sue", "crush_sue", "abs_sue"), ("disp", "crush_disp", "abs_disp"),
                             ("firmfe", "crush_firm_fe", "abs_surprise")):
        x = reg_term(r, model, term)
        put(f"surprise.{key}", fsigned(x.estimate, 3), f"results.parquet {model}/{term}")
        put(f"surprise.{key}_q", fp(x.q_bh), f"results.parquet {model}/{term} q_bh")
    dsl = reg_term(r, "dsigma_d_drivers", "slope")
    put("slope.dsigma", fsigned(dsl.estimate, 3), "results.parquet dsigma_d_drivers slope")

    # Event-test rows of tests.json: robustness and exploratory
    twin = test_row(tests, hypothesis="H1", statistic="twoway_date_t", adjustment="mean", role="robustness")
    put("h1.twin", fsigned(twin["estimate"], 3), "tests.json H1 mean-adjusted twin")
    sign = test_row(tests, hypothesis="H1", statistic="gen_sign_z")
    put("h1.share_below", fpct(sign["estimate"], 1), "tests.json H1 gen_sign_z estimate (share below 0)")
    for key, want in (("amc", dict(subgroup_value="AMC", measure="crush_cm30", sample="daily")),
                      ("bmo", dict(subgroup_value="BMO", measure="crush_cm30", sample="daily")),
                      ("front", dict(measure="crush_front_fixed", sample="daily")),
                      ("coarse", dict(measure="crush_cm30", sample="coarse", adjustment="market")),
                      ("mixed", dict(measure="crush_cm30", sample="mixed", adjustment="market"))):
        x = test_row(tests, role="exploratory", **want)
        put(f"crush.{key}", fsigned(x["estimate"], 3), f"tests.json exploratory {want}")
        if key == "front":
            if not x["estimate"] < 0:
                raise ValueError("the report says the front-expiry IV falls")
            put("crush.front_fall", fnum(-x["estimate"], 3), f"−(tests.json exploratory {want})")
        put(f"crush.{key}_n", fint(x["n"]), f"tests.json exploratory {want} n")
    # Robustness rows whose p-value ADR 0005 §4 withholds: G1 found them oversized (a g1_size and no p-value).
    withheld: set[tuple[str, str]] = set()
    for x in tests["rows"]:
        if x.get("g1_size") is not None and x.get("p_value") is None:
            withheld.add((x["hypothesis"], x["statistic"]))
    for m in drv["models"]:
        for t in m["terms"]:
            if t.get("role") == "robustness" and t.get("g1_size") is not None and t.get("p_value") is None:
                twin = " (mean-adjusted twin)" if m["adjustment"] == "mean" else ""
                withheld.add((t["hypothesis"], t["statistic"] + twin))
    reg = ivr["summary"]["regression"]
    if reg.get("g1_pass_one_way") is False and reg.get("wald_p_one_way") is None:
        withheld.add(("H7", "cluster_date_wald"))
    by_h: dict[str, list[str]] = {}
    for h, stat in sorted(withheld):
        by_h.setdefault(h, []).append(stat)
    put("withheld.n", fint(len(withheld)), "tests.json and drivers.json rows with g1_size and no p-value")
    put("withheld.list", "; ".join(f"{h}: " + ", ".join(_code(s) for s in v) for h, v in by_h.items()),
        "tests.json and drivers.json rows with g1_size and no p-value")

    # The mean path (event_paths.json, market-adjusted aggregate)
    for day, key in ((-10, "m10"), (-1, "m1"), (0, "d0"), (1, "p1"), (5, "p5"), (10, "p10")):
        m, lo_, hi_ = path_at(paths, day)
        put(f"path.{key}", fsigned(m, 3), f"event_paths.json market/all day {day}")
        put(f"path.{key}_ci", fci(lo_, hi_, 3), f"event_paths.json market/all day {day} band")
    put("path.amc_m1", fsigned(path_at(paths, -1, subgroup="AMC")[0], 3), "event_paths.json market/AMC day −1")
    put("path.bmo_m1", fsigned(path_at(paths, -1, subgroup="BMO")[0], 3), "event_paths.json market/BMO day −1")

    # IV measures (iv_measures.json)
    cq, mq = ivm["crush"]["quantiles"], ivm["implied_move"]["quantiles"]
    put("iv.crush_median", fsigned(cq["p50"], 3), "iv_measures.json crush.quantiles.p50")
    put("iv.crush_p10", fsigned(cq["p10"], 3), "iv_measures.json crush.quantiles.p10")
    put("iv.crush_p90", fsigned(cq["p90"], 3), "iv_measures.json crush.quantiles.p90")
    put("iv.move_median", fpct(mq["p50"], 1), "iv_measures.json implied_move.quantiles.p50")
    put("iv.move_p10", fpct(mq["p10"], 1), "iv_measures.json implied_move.quantiles.p10")
    put("iv.move_p90", fpct(mq["p90"], 1), "iv_measures.json implied_move.quantiles.p90")
    put("iv.move_n", fint(ivm["implied_move"]["n"]), "iv_measures.json implied_move.n")

    # Implied against realised (implied_vs_realised.json)
    sm = ivr["summary"]
    pts = ivr["points"]
    put("ivr.n", fint(sm["n"]), "implied_vs_realised.json summary.n")
    put("ivr.n_pos", fint(sm["n_with_implied_abs_move"]), "implied_vs_realised.json summary.n_with_implied_abs_move")
    put("ivr.n_nonpos", fint(sm["n_evar_nonpositive"]), "implied_vs_realised.json summary.n_evar_nonpositive")
    put("ivr.share", fpct(sm["share_exceed"], 1), "implied_vs_realised.json summary.share_exceed")
    put("ivr.benchmark", fpct(sm["share_exceed_benchmark"], 1), "implied_vs_realised.json summary.share_exceed_benchmark")
    put("ivr.share_p", fp(sm["share_exceed_p"]), "implied_vs_realised.json summary.share_exceed_p")
    put("ivr.median_ratio", fnum(sm["median_ratio"], 2), "implied_vs_realised.json summary.median_ratio")
    implied = sorted(p["implied_abs_move_total"] for p in pts if p["implied_abs_move_total"] is not None)
    realised = sorted(p["abs_realized"] for p in pts)
    put("ivr.median_implied", fpct(_median(implied), 1), "implied_vs_realised.json points: median implied |move|")
    put("ivr.median_realised", fpct(_median(realised), 1), "implied_vs_realised.json points: median |r0|")
    mean_r2 = sum(p["realized_ret_0"] ** 2 for p in pts) / len(pts)
    mean_iv = sum(p["implied_var_total"] for p in pts) / len(pts)
    put("ivr.var_ratio", fnum(mean_r2 / mean_iv, 2), "implied_vs_realised.json points: mean r0² / mean (E + σ_d²/252)")

    # ρ̄ (the kept prototype output)
    txt = d["rhobar_out"]
    put("rhobar", fnum(prototype_value(txt, "1. rho-bar"), 2), "research/prototypes/rhobar_crush.out.txt")
    put("rhobar.no_top10", fnum(prototype_value(txt, "rho-bar without the top 10 dates:"), 2),
        "research/prototypes/rhobar_crush.out.txt")
    put("rhobar.loo", fnum(prototype_value(txt, "all-firm leave-one-out factor:"), 3),
        "research/prototypes/rhobar_crush.out.txt")

    put("results.rows", fint(len(r)), "results.parquet row count")

    # Verdicts the tables print, from the data
    for h in ("H1", "H2", "H3", "H4", "H5", "H6", "H7"):
        ok = [x for x in tests["g1"]["calibrated"] if x["hypothesis"] == h][0]["pass"]
        put(f"{h.lower()}.g1_verdict", "pass" if ok else "**fail**", f"tests.json g1.calibrated[{h}].pass")
    rejected = [h for h in ("H1", "H2", "H3", "H4", "H5", "H6", "H7") if rows[h].p_holm <= 0.05]
    put("holm.rejected", " and ".join(rejected) if len(rejected) <= 2 else ", ".join(rejected),
        "results.parquet primary rows with p_holm ≤ 0.05")
    cross_check(d, rows)
    prose_check(d, rows)
    return out


def prose_check(d: dict, rows: dict) -> None:
    """The templates' hand-written sentences make qualitative claims about the numbers (a sign, a verdict, an
    interval holding 1). Each claim is checked here, so new data that contradicts a sentence fails --check instead of
    leaving the sentence wrong next to the right number."""
    tests, paths, ivr, r = d["tests"], d["event_paths"], d["implied_vs_realised"], d["results"]
    lo, hi = tests["g1"]["band"]
    g1 = {x["hypothesis"]: x for x in tests["g1"]["calibrated"]}
    ph = {h: rows[h].p_holm for h in rows}
    cut = one(r[(r.hypothesis == "H2") & (r.subgroup_key == "season_cut") & (r.family == "event_test")], "H2 cut")
    pg = r[r.measure == "holm_post_gate"]
    pg_h2 = one(pg[(pg.hypothesis == "H2") & (pg.subgroup_value == "all")], "post-gate H2").estimate
    pg_cut = one(pg[(pg.hypothesis == "H2") & (pg.subgroup_key == "season_cut")], "post-gate cut").estimate
    b = reg_term(r, "implied_realised", "b")
    sm = ivr["summary"]

    def m(day, sub="all"):
        return path_at(paths, day, subgroup=sub)

    claims = [
        ("G1: H1-H4 pass, H5-H7 fail", all(g1[h]["pass"] for h in ("H1", "H2", "H3", "H4"))
         and not any(g1[h]["pass"] for h in ("H5", "H6", "H7"))),
        ("G1: H2 and H3 conservative (below the band)", g1["H2"]["rejection_rate"] < lo
         and g1["H3"]["rejection_rate"] < lo),
        ("Holm: H1 and H2 rejected, H3-H7 not", ph["H1"] <= 0.05 and ph["H2"] <= 0.05
         and all(ph[h] > 0.05 for h in ("H3", "H4", "H5", "H6", "H7"))),
        ("H2's season cut not rejected; post-gate H2 and its cut rejected", cut.p_holm > 0.05 and pg_h2 <= 0.05
         and pg_cut <= 0.05),
        ("H2: the season count of the cut is one less", cut.n_clusters == rows["H2"].n_clusters - 1),
        ("H2 positive, on its floor (every season mean positive), its two-way t significant",
         rows["H2"].estimate > 0 and math.isclose(rows["H2"].p_value, 2 / 2 ** int(rows["H2"].n_clusters))
         and one(r[(r.hypothesis == "H2") & (r.statistic == "twoway_season_t") & (r.family == "event_test")
                   & (r.adjustment == "market")], "H2 two-way").p_value < 0.05),
        ("H1 negative and rejected", rows["H1"].estimate < 0 and rows["H1"].p_holm <= 0.05),
        ("E read at day -2 gives a larger b than at day -1", reg_term(r, "implied_realised_m2", "b").estimate
         > b.estimate),
        ("the primary sample inside the milestone-0 estimate of 330-360 events", 330 <= rows["H1"].n <= 360),
        ("the timing look-ups are only the four statuses the texts name (no ambiguous, no no_document)",
         d["sample_funnel"]["timing_status_counts"]["ambiguous"] == 0
         and d["sample_funnel"]["timing_status_counts"]["no_document"] == 0),
        ("rho-bar spread over most dates: over half the dates positive, still above 0.1 without the top 10",
         prototype_value(d["rhobar_out"], "share of dates with a positive cross-product:") > 0.5
         and prototype_value(d["rhobar_out"], "rho-bar without the top 10 dates:") > 0.1),
        ("H3, H4, H6 intervals hold 0", all(rows[h].ci_lo < 0 < rows[h].ci_hi for h in ("H3", "H4", "H6"))),
        ("H5 positive (a smaller fall), interval above 0", rows["H5"].estimate > 0 and rows["H5"].ci_lo > 0),
        ("H7: b's interval holds 1, b below 1", b.ci_lo < 1 < b.ci_hi and b.estimate < 1),
        ("exceed share below the benchmark, not significant", sm["share_exceed"] < sm["share_exceed_benchmark"]
         and sm["share_exceed_p"] > 0.05),
        ("median ratio below 1", sm["median_ratio"] < 1),
        ("almost every crush negative (over 95%)", test_row(tests, hypothesis="H1", statistic="gen_sign_z")
         ["estimate"] > 0.95),
        ("AMC crush larger than BMO's", test_row(tests, role="exploratory", subgroup_value="AMC",
                                                  measure="crush_cm30", sample="daily")["estimate"]
         < test_row(tests, role="exploratory", subgroup_value="BMO", measure="crush_cm30", sample="daily")["estimate"]),
        ("AMC run higher at day -1 than BMO", m(-1, "AMC")[0] > m(-1, "BMO")[0]),
        ("older samples' crush negative", all(test_row(tests, role="exploratory", measure="crush_cm30", sample=smp,
                                                        adjustment="market")["estimate"] < 0
                                               for smp in ("mixed", "coarse"))),
        ("path at -10 and -1 about the same (within 0.02, bands overlap)",
         abs(m(-10)[0] - m(-1)[0]) < 0.02 and m(-10)[1] < m(-1)[2] and m(-1)[1] < m(-10)[2]),
        ("slope negative (steeper, larger crush), q below 0.05", reg_term(r, "crush_drivers", "slope").estimate < 0
         and reg_term(r, "crush_drivers", "slope").q_bh < 0.05),
        ("the surprise does not survive the other measures (q > 0.05 each)",
         all(reg_term(r, mdl, t).q_bh > 0.05 for mdl, t in (("crush_sue", "abs_sue"), ("crush_disp", "abs_disp"),
                                                           ("crush_firm_fe", "abs_surprise")))),
        ("rho-bar above 0.2; the leave-one-out factor takes it near 0",
         prototype_value(d["rhobar_out"], "1. rho-bar") > 0.2
         and abs(prototype_value(d["rhobar_out"], "all-firm leave-one-out factor:")) < 0.05),
    ]
    wrong = [what for what, ok in claims if not ok]
    if wrong:
        raise ValueError("the data now contradict sentences in the templates; revise them:\n  " + "\n  ".join(wrong))


def _code(stat: str) -> str:
    """`stat` in code type; a trailing note in brackets stays plain: `twoway_date_t` (mean-adjusted twin)."""
    name, _, note = stat.partition(" (")
    return f"`{name}`" + (f" ({note}" if note else "")


def _median(xs: list[float]) -> float:
    n = len(xs)
    if n == 0:
        raise ValueError("median of nothing")
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def cross_check(d: dict, rows: dict) -> None:
    """Numbers held by two inputs must agree (to the JSON's rounding); a disagreement means a stale export."""
    tests, drv, ivr, meta, fun = d["tests"], d["drivers"], d["implied_vs_realised"], d["meta"], d["sample_funnel"]
    problems = []

    def same(what: str, a: float, b: float, tol: float) -> None:
        if not (abs(a - b) <= tol):
            problems.append(f"{what}: {a} against {b}")

    for h in ("H1", "H2", "H3", "H4"):
        t = test_row(tests, hypothesis=h, role="primary")
        same(f"{h} estimate results/tests.json", rows[h].estimate, t["estimate"], 5e-5)
        same(f"{h} p_holm results/tests.json", rows[h].p_holm, t["p_holm"], 5e-4 * max(t["p_holm"], 1e-30))
    terms = {(t["hypothesis"], t["role"]): t for m in drv["models"] for t in m["terms"] if t.get("hypothesis")}
    for h in ("H5", "H6"):
        t = terms[(h, "primary")]
        same(f"{h} estimate results/drivers.json", rows[h].estimate, t["coef"], 5e-6)
        same(f"{h} p_holm results/drivers.json", rows[h].p_holm, t["p_holm"], 5e-5)
        same(f"{h} G1 size tests.json/drivers.json", g1_rate(tests, h), t["g1_size"], 1e-9)
    reg = ivr["summary"]["regression"]
    same("H7 F results/implied_vs_realised.json", rows["H7"].stat, reg["wald_f"], 5e-5)
    same("H7 p_holm results/implied_vs_realised.json", rows["H7"].p_holm, reg["p_holm"], 5e-5)
    same("H7 G1 size tests.json/implied_vs_realised.json", g1_rate(tests, "H7"), reg["g1_rate"], 1e-9)
    b = reg_term(d["results"], "implied_realised", "b")
    same("H7 b results/implied_vs_realised.json", b.estimate, reg["b"], 5e-4)
    pg = drv["holm"]["post_gate"]["p_holm"]
    r = d["results"]
    for h in ("H1", "H2"):
        x = one(r[(r.measure == "holm_post_gate") & (r.hypothesis == h) & (r.subgroup_value == "all")], h)
        same(f"{h} post-gate results/drivers.json", x.estimate, pg[h], 5e-4 * pg[h])
    n_last = fun["steps"][-1]["n_events"]
    same("sample size meta.json/sample_funnel.json", meta["sample"]["n_events"], n_last, 0)
    same("sample size meta.json/H1 n", meta["sample"]["n_events"], rows["H1"].n, 0)
    tsc = fun["timing_status_counts"]
    same("look-ups done / timing statuses", fun["lookups"]["n_done"],
         sum(tsc[k] for k in ("confirmed", "corrected", "date_corrected", "inferred", "ambiguous", "no_document")), 0)
    # Gate G1: the export's rates and pass flags against results.parquet's calibrated rows and the band.
    hi = tests["g1"]["band"][1]
    for x in tests["g1"]["calibrated"]:
        h = x["hypothesis"]
        g = one(r[(r.measure == "g1:calibrated") & (r.hypothesis == h) & (r.role == "primary")], f"G1 {h}")
        same(f"{h} G1 rate results/tests.json", g.estimate, x["rejection_rate"], 1e-9)
        if g.statistic != x["statistic"]:
            problems.append(f"{h} G1 statistic: {g.statistic} against {x['statistic']}")
        if x["pass"] != (x["rejection_rate"] <= hi):
            problems.append(f"{h} G1 pass flag {x['pass']} against rate {x['rejection_rate']} and bar {hi}")
    if problems:
        raise ValueError("the inputs disagree:\n  " + "\n  ".join(problems))


# --- rendering ---------------------------------------------------------------------------------------------

def render(template: str, nums: dict[str, tuple[str, str]], where: str) -> str:
    missing = sorted({k for k in PLACEHOLDER.findall(template) if k not in nums})
    if missing:
        raise KeyError(f"{where}: unknown number(s) {', '.join(missing)}")
    text = PLACEHOLDER.sub(lambda m: nums[m.group(1)][0], template)
    if "{{" in text or "}}" in text:
        raise KeyError(f"{where}: a placeholder is left after rendering (unbalanced braces?)")
    return text


def block_markers(name: str) -> tuple[str, str]:
    return f"<!-- numbers:{name} -->", f"<!-- /numbers:{name} -->"


def splice(doc: str, name: str, body: str, where: str) -> str:
    begin, end = block_markers(name)
    if doc.count(begin) != 1 or doc.count(end) != 1:
        raise ValueError(f"{where}: needs exactly one '{begin}' and one '{end}'")
    i, j = doc.index(begin) + len(begin), doc.index(end)
    if j < i:
        raise ValueError(f"{where}: '{end}' comes before '{begin}'")
    return doc[:i] + "\n" + body.rstrip("\n") + "\n" + doc[j:]


TEMPLATE_NOTE = re.compile(r"\A<!-- template:.*?-->\n", re.S)
GENERATED_NOTE = (f"<!-- Generated by tools/report_numbers.py from {REPORT_TEMPLATE}: edit the template, not this "
                  "file. -->\n")


def rendered(root: Path) -> dict[str, str]:
    """Every output file's full expected text."""
    nums = numbers(load(root))
    tpl, n = TEMPLATE_NOTE.subn(GENERATED_NOTE, (root / REPORT_TEMPLATE).read_text())
    if n != 1:
        raise ValueError(f"{REPORT_TEMPLATE}: must start with a '<!-- template: ... -->' note")
    out = {REPORT_OUT: render(tpl, nums, REPORT_TEMPLATE)}
    for path, name in BLOCKS:
        doc = out.get(path, (root / path).read_text())
        tpl = f"{TEMPLATES}/{name}.md"
        out[path] = splice(doc, name, render((root / tpl).read_text(), nums, tpl), path)
    return out


def check_exports(root: Path, report_text: str) -> list[str]:
    """The PDF and DOCX must have been built from this Markdown and not changed since (build_report.py's stamp)."""
    stamp_path = root / EXPORTS_STAMP
    if not stamp_path.exists():
        return [f"no {EXPORTS_STAMP}: build the exports with tools/build_report.py"]
    stamp = json.loads(stamp_path.read_text())
    md_sha = hashlib.sha256(report_text.encode("utf-8")).hexdigest()
    problems = []
    for fmt in EXPORTS:
        entry = stamp.get(fmt)
        path = root / "docs/report" / f"earnings-vol-report.{fmt}"
        if entry is None or not path.exists():
            problems.append(f"the {fmt} export is missing")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            problems.append(f"the {fmt} export was changed after its build")
        elif entry["markdown_sha256"] != md_sha:
            problems.append(f"the {fmt} export was built from an older Markdown")
    return problems


def check_lookups_against_stage(root: Path) -> str:
    """Compare LOOKUPS_REQUIRED with the local stage report, when there is one (never in CI)."""
    base = Path(os.environ.get("VOL_DATA_DIR", Path.home() / "data/vol-projects")) / "earnings-vol-study/cache/stage"
    params_hash = load(root)["meta"]["provenance"]["params_hash"][:16]
    rep = base / params_hash / "events_report.json"
    if not rep.exists():
        return f"look-ups: {LOOKUPS_REQUIRED} pinned, not re-measured (no local {rep.name})"
    left = json.loads(rep.read_text())["lookup_violations"]["n"]
    done = load(root)["sample_funnel"]["lookups"]["n_done"]
    if left + done != LOOKUPS_REQUIRED:
        raise ValueError(f"look-ups: the stage report says {left} left + {done} done = {left + done}, "
                         f"not {LOOKUPS_REQUIRED}")
    return f"look-ups: {left} left + {done} done = {LOOKUPS_REQUIRED}, as pinned (local {rep.name})"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="compare the rendered files with the ones on disk")
    mode.add_argument("--list", action="store_true", help="print every number and its source")
    ap.add_argument("--root", type=Path, default=REPO, help="the repository root (default: this checkout)")
    args = ap.parse_args(argv)
    root = args.root.resolve()

    if args.list:
        for k, (v, src) in numbers(load(root)).items():
            print(f"{k:24} {v:28} {src}")
        return 0
    try:
        files = rendered(root)
        note = check_lookups_against_stage(root)
    except (KeyError, ValueError) as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1
    n_keys = len(numbers(load(root)))
    if args.check:
        stale = [p for p, text in files.items() if (root / p).read_text() != text]
        if stale:
            print(f"FAIL: stale: {', '.join(stale)} (run tools/report_numbers.py)", file=sys.stderr)
            return 1
        exports = check_exports(root, files[REPORT_OUT])
        if exports:
            print(f"FAIL: exports stale: {'; '.join(exports)} (run tools/build_report.py)", file=sys.stderr)
            return 1
        print(f"ok: {len(files)} file(s) match {n_keys} numbers from the committed data; the PDF and DOCX were "
              f"built from this Markdown; {note}")
        return 0
    for p, text in files.items():
        (root / p).write_text(text)
        print(f"wrote {p}")
    print(f"{n_keys} numbers; {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
