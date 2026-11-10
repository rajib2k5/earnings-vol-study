"""Every measured number in the report, the README and the PR/FAQ, regenerated from the committed data.

    uv run --frozen python tools/report_numbers.py            # render the report and the README/PR-FAQ blocks
    uv run --frozen python tools/report_numbers.py --check    # exit 1 if a rendered file is stale or the data disagree
    uv run --frozen python tools/report_numbers.py --list     # print every number with its source

Inputs, all committed:

- ``data/derived/results.parquet`` (the primary, robustness and exploratory rows, Holm, the post-gate sensitivity);
- ``app/public/data/{meta,sample_funnel,iv_measures,tests,event_paths,drivers,implied_vs_realised}.json``;
- ``research/prototypes/rhobar_crush.out.txt``, the kept output of the milestone-4 ρ̄ prototype (its inputs are
  per-event VIX-adjusted values, which stay local, so ρ̄ cannot be recomputed from committed data);
- ``data/derived/vx_crosscheck.json``, the aggregates of the Cboe VX* cross-check (``tools/vx_crosscheck.py``; its
  inputs, the VX* files and ``volatility_history``, stay local, so it is read here, not recomputed).

Some look-up counts are not in the committed data. ADR 0002 §3 requires 473 look-ups (``LOOKUPS_REQUIRED``); the
events run counts them with the Yahoo gap flags, and one of those flags (``outside_flag_yf``) stays local. So do the
reasons the 42 still-open look-ups are open (``LOOKUPS_OPEN_BY_REASON``) and the 37 EDGAR labels that the price gap
questions (``LOOKUPS_GAP_QUESTIONED``). They are pinned here with their source (docs/validation/edgar-ledger.md §10,
``events_report.json`` of the EDGAR run) and, when the local stage report exists, ``--check`` compares each of them
with that report. How many look-ups each document resolved (``timing_source`` = ``press_release`` or ``edgar``) is
counted from the committed ``data/derived/events.parquet``.

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
# reasons) and, since SEC EDGAR is the timing source (params timing.edgar, 2026-11-09), why the open ones are open
# and how many EDGAR labels the price gap questions. Not derivable from committed data: the gap trigger also reads the
# local outside_flag_yf. Measured by `python -m earnings_vol.events.run` with timing.edgar true (events_report.json:
# lookup_violations.n = 42, edgar.outcome, edgar.pending_gap_checks); docs/validation/edgar-ledger.md §6 and §10.
LOOKUPS_REQUIRED = 473
LOOKUPS_OPEN_BY_REASON = {"no_8k": 26, "edgar_holiday": 11, "other_date": 4, "contradicts": 1}
LOOKUPS_GAP_QUESTIONED = 37
LOOKUPS_AUDIT = 50  # ADR 0002 §3, milestone 1: confirmed EDGAR labels to check against press releases (not run)
LOOKUPS_SOURCE = "docs/validation/edgar-ledger.md §6 (events_report.json in the local stage, EDGAR run)"
VX_FILE = "data/derived/vx_crosscheck.json"

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
    ("docs/milestones/05-report-and-polish.md", "milestone5-vx"),
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
        "vx": json.loads((root / VX_FILE).read_text()),
        "events_sha256": hashlib.sha256((root / "data/derived/events.parquet").read_bytes()).hexdigest(),
        **events_timing(pd.read_parquet(root / "data/derived/events.parquet",
                                        columns=["timing_source", "timing_status", "timing_raw", "sample"])),
    }


def events_timing(ev: pd.DataFrame) -> dict:
    """What events.parquet says about the timing labels: where they came from, and what is left `not_checked`.

    `not_checked_open_unlabelled` is the open required look-ups (ADR 0002 §3) that have no calendar label: a
    `not_checked` event with a NULL label that can enter a sample (`sample` is not `none`). The other open
    look-ups have a label, so they are `lookups.left` less this count.
    """
    nc = ev[ev["timing_status"] == "not_checked"]
    unlabelled = nc["timing_raw"].isna()
    return {"timing_source": ev["timing_source"].value_counts().to_dict(),
            "not_checked": int(len(nc)), "not_checked_unlabelled": int(unlabelled.sum()),
            "not_checked_open_unlabelled": int((unlabelled & (nc["sample"] != "none")).sum())}


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
    if d["not_checked"] != tsc["not_checked"]:
        raise ValueError(f"events.parquet has {d['not_checked']} not_checked events, sample_funnel.json "
                         f"{tsc['not_checked']}")
    put("timing.not_checked_unlabelled", fint(d["not_checked_unlabelled"]),
        "events.parquet: not_checked events with a NULL timing_raw")
    put("timing.not_checked_labelled", fint(d["not_checked"] - d["not_checked_unlabelled"]),
        "events.parquet: not_checked events with a timing_raw (they keep the calendar's label)")
    done = fun["lookups"]["n_done"]
    put("lookups.done", fint(done), "sample_funnel.json lookups.n_done")
    put("lookups.required", fint(LOOKUPS_REQUIRED), LOOKUPS_SOURCE)
    put("lookups.left", fint(LOOKUPS_REQUIRED - done), "lookups.required − lookups.done")
    put("lookups.left_unlabelled", fint(d["not_checked_open_unlabelled"]),
        "events.parquet: not_checked, NULL timing_raw, sample not none (open look-ups with no calendar label)")
    put("lookups.left_labelled", fint(LOOKUPS_REQUIRED - done - d["not_checked_open_unlabelled"]),
        "lookups.left − lookups.left_unlabelled (open look-ups that keep the calendar's label)")
    daily_open = {x["tercile"]: x["timing_status_counts"]["not_checked"] for x in fun["by_move_tercile"]
                  if x["sample"] == "daily"}
    if sorted(daily_open) != [1, 2, 3]:
        raise ValueError(f"sample_funnel.json by_move_tercile: daily terciles {sorted(daily_open)}")
    for t, n in sorted(daily_open.items()):
        put(f"funnel.daily_open.t{t}", fint(n), f"sample_funnel.json by_move_tercile[daily, {t}] not_checked")
    put("funnel.daily_open", fint(sum(daily_open.values())), "sample_funnel.json by_move_tercile[daily] not_checked")
    for src in ("press_release", "edgar"):
        put(f"lookups.{src}", fint(d["timing_source"].get(src, 0)), f"events.parquet timing_source == {src}")
    for why, n in LOOKUPS_OPEN_BY_REASON.items():
        put(f"lookups.open.{why}", fint(n), LOOKUPS_SOURCE)
    put("lookups.gap_questioned", fint(LOOKUPS_GAP_QUESTIONED), LOOKUPS_SOURCE)
    put("lookups.audit", fint(LOOKUPS_AUDIT), "ADR 0002 §3 (milestone 1 EDGAR check; not run)")
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

    vx_numbers(d["vx"], put)

    # Verdicts the tables print, from the data
    for h in ("H1", "H2", "H3", "H4", "H5", "H6", "H7"):
        ok = [x for x in tests["g1"]["calibrated"] if x["hypothesis"] == h][0]["pass"]
        put(f"{h.lower()}.g1_verdict", "pass" if ok else "**fail**", f"tests.json g1.calibrated[{h}].pass")
    rejected = [h for h in ("H1", "H2", "H3", "H4", "H5", "H6", "H7") if rows[h].p_holm <= 0.05]
    put("holm.rejected", " and ".join(rejected) if len(rejected) <= 2 else ", ".join(rejected),
        "results.parquet primary rows with p_holm ≤ 0.05")
    cross_check(d, rows)
    prose_check(d, rows)
    vx_prose_check(d["vx"], cm30_sessions=int(par["cm30_horizon_sessions"]))
    return out


def _verdict(v: str) -> str:
    """A bar's verdict as the tables print it: a fail in bold."""
    if v not in ("pass", "fail"):
        raise ValueError(f"a verdict must be pass or fail, got {v!r}")
    return "pass" if v == "pass" else "**fail**"


def _join(items: list[str]) -> str:
    """'A', 'A and B', 'A, B and C'."""
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _sd_ratio(y: dict) -> float:
    """sd(dln VX) / sd(dln ours) from bar ii's two slopes: forward × (1 / reverse) = (sd ratio)²."""
    return math.sqrt(y["slope"] * y["reverse_slope_reciprocal"])


def _vx_rows(vxd: dict) -> tuple[list[str], dict, dict, dict]:
    names = [x["security_id"] for x in vxd["names"]]
    b1 = {**vxd["bar_i"]["per_name"], "pooled": vxd["bar_i"]["pooled"]}
    return names, b1, vxd["bar_ii"]["per_name"], vxd["bar_iii"]["per_name"]


def vx_numbers(vxd: dict, put) -> None:
    """The Cboe VX* cross-check (data/derived/vx_crosscheck.json): bars i-iv, the lags, §5."""
    src = VX_FILE
    names, b1, b2, b3 = _vx_rows(vxd)
    index = {x["security_id"]: x["vx_index"] for x in vxd["names"]}
    for nm in names + ["pooled"]:
        k = nm.lower()
        if nm != "pooled":
            put(f"vx.{k}.index", index[nm], f"{src} names")
        x = b1[nm]
        put(f"vx.{k}.n", fint(x["n"]), f"{src} bar_i {nm} n")
        put(f"vx.{k}.r", fnum(x["r"], 3), f"{src} bar_i {nm} r")
        put(f"vx.{k}.r_ci", fci(x["block20"]["lo"], x["block20"]["hi"], 3), f"{src} bar_i {nm} block20")
        put(f"vx.{k}.i", _verdict(x["verdict"]), f"{src} bar_i {nm} verdict")
        y = b2[nm]
        put(f"vx.{k}.slope", fnum(y["slope"], 2), f"{src} bar_ii {nm} slope")
        put(f"vx.{k}.slope_ci", fci(y["block20"]["slope"]["lo"], y["block20"]["slope"]["hi"], 2),
            f"{src} bar_ii {nm} block20 slope")
        put(f"vx.{k}.rev", fnum(y["reverse_slope_reciprocal"], 2), f"{src} bar_ii {nm} 1 / reverse slope")
        if nm != "pooled":
            z = b3[nm]
            put(f"vx.{k}.spread", fnum(z["median_spread"], 2), f"{src} bar_iii {nm} median_spread")
            put(f"vx.{k}.maxdev", fnum(z["max_abs_dev"], 2), f"{src} bar_iii {nm} max_abs_dev")
            put(f"vx.{k}.iii", _verdict(z["verdict"]), f"{src} bar_iii {nm} verdict")
    put("vx.pooled.r_ci60", fci(b1["pooled"]["block60"]["lo"], b1["pooled"]["block60"]["hi"], 3),
        f"{src} bar_i pooled block60")
    shares = [b3[nm]["share_above"] for nm in names]
    put("vx.above_min", fpct(min(shares), 0), f"{src} bar_iii share_above, smallest")
    put("vx.above_max", fpct(max(shares), 0), f"{src} bar_iii share_above, largest")
    put("vx.maxdev_max", fnum(max(b3[nm]["max_abs_dev"] for nm in names), 2), f"{src} bar_iii max_abs_dev, largest")
    put("vx.rev_min", fnum(min(b2[nm]["reverse_slope_reciprocal"] for nm in names), 2),
        f"{src} bar_ii 1 / reverse slope, smallest name")
    put("vx.rev_max", fnum(max(b2[nm]["reverse_slope_reciprocal"] for nm in names), 2),
        f"{src} bar_ii 1 / reverse slope, largest name")
    put("vx.tolerance", fnum(vxd["bar_iii"]["tolerance_vol_points"], 1), f"{src} bar_iii tolerance_vol_points")
    put("vx.window_from", vxd["window"]["first"], f"{src} window.first")
    put("vx.window_to", vxd["window"]["last"], f"{src} window.last")
    put("vx.reps", fint(vxd["bootstrap"]["reps"]), f"{src} bootstrap.reps")
    put("vx.block", fint(vxd["bootstrap"]["primary_block"]), f"{src} bootstrap.primary_block")
    put("vx.block60", fint(vxd["bootstrap"]["blocks"][1]), f"{src} bootstrap.blocks[1]")
    fetched = sorted({m["fetched_utc"][:10] for m in vxd["inputs"]["cboe"].values()})
    if len(fetched) != 1:
        raise ValueError(f"the VX* files were fetched on several days: {fetched}")
    put("vx.fetched", fetched[0], f"{src} inputs.cboe fetched_utc (date)")
    iv = vxd["bar_iv"]
    put("vx.iv.n", fint(iv["n"]), f"{src} bar_iv n")
    put("vx.iv.ratio", fnum(iv["ratio"], 2), f"{src} bar_iv ratio")
    put("vx.iv.ci", fci(iv["events_bootstrap"]["lo"], iv["events_bootstrap"]["hi"], 2), f"{src} bar_iv events_bootstrap")
    put("vx.iv.verdict", _verdict(iv["verdict"]), f"{src} bar_iv verdict")
    tsc_iv = iv["events"]["timing_status_counts"]
    put("vx.iv.not_checked", fint(tsc_iv.get("not_checked", 0)), f"{src} bar_iv events timing_status_counts.not_checked")
    put("vx.iv.documented", fint(iv["events"]["n_events_five_names"] - tsc_iv.get("not_checked", 0)),
        f"{src} bar_iv events n_events_five_names − timing_status_counts.not_checked")
    per_name = iv["events"]["n_by_name"].values()
    put("vx.iv.per_name_min", fint(min(per_name)), f"{src} bar_iv events n_by_name, smallest")
    put("vx.iv.per_name_max", fint(max(per_name)), f"{src} bar_iv events n_by_name, largest")
    put("vx.i_fails", fint(sum(b1[nm]["verdict"] == "fail" for nm in names)), f"{src} bar_i names failing")
    put("vx.ii_below", fint(sum(b2[nm]["slope"] < vxd["bar_ii"]["exploratory_adr_band"]["band"][0] for nm in names)),
        f"{src} bar_ii names with a slope below the ADR band (exploratory)")
    lags = vxd["alignment_falsifier"]["lags"]
    put("vx.lag.m1", fsigned(lags["-1"]["r"], 3), f"{src} alignment_falsifier lag -1 r")
    put("vx.lag.p1", fsigned(lags["+1"]["r"], 3), f"{src} alignment_falsifier lag +1 r")
    sec = vxd["secondary"]["pooled"]
    put("vx.sec.r", fnum(sec["r"], 3), f"{src} secondary pooled r")
    put("vx.sec.r_ci", fci(sec["block20"]["r"]["lo"], sec["block20"]["r"]["hi"], 3), f"{src} secondary pooled block20 r")
    put("vx.sec.n", fint(sec["n"]), f"{src} secondary pooled n")
    put("vx.sec.slope", fnum(sec["slope"], 2), f"{src} secondary pooled slope")
    put("vx.sec.rev", fnum(sec["reverse_slope_reciprocal"], 2), f"{src} secondary pooled 1 / reverse slope")
    put("vx.sec.rev_ci", fci(sec["block20"]["reverse_slope_reciprocal"]["lo"],
                             sec["block20"]["reverse_slope_reciprocal"]["hi"], 2),
        f"{src} secondary pooled block20 1 / reverse slope")
    vh = vxd["volatility_history"]
    rv, ro = vh["iv_current_vs_vx"]["r_primary_changes"]["pooled"], vh["iv_current_vs_ours"]["r_primary_changes"]["pooled"]
    put("vh.r_vx", fnum(rv["r"], 3), f"{src} volatility_history iv_current_vs_vx pooled r")
    put("vh.r_vx_ci", fci(rv["block20"]["lo"], rv["block20"]["hi"], 3), f"{src} volatility_history iv_current_vs_vx")
    put("vh.r_ours", fnum(ro["r"], 3), f"{src} volatility_history iv_current_vs_ours pooled r")
    sv = vh["iv_current_vs_vx"]["spread_vx_minus_iv_current"]["pooled"]
    so = vh["iv_current_vs_ours"]["spread_iv_current_minus_ours"]["pooled"]
    put("vh.spread_vx", fnum(sv["median_spread"], 2), f"{src} volatility_history spread VX − iv_current pooled")
    put("vh.spread_ours", fnum(so["median_spread"], 2), f"{src} volatility_history spread iv_current − ours pooled")
    mat = vh["maturity"]
    ident = mat["identification"]
    put("vh.maturity", fint(ident["horizon"]) if ident["status"] == "identified" else "UNRESOLVED",
        f"{src} volatility_history maturity identification")
    put("vh.maturity_med", fnum(mat["median_abs_diff_vol_points"][str(ident["argmin"])], 2),
        f"{src} volatility_history maturity median_abs_diff at the argmin")
    put("vh.maturity_days", fint(mat["n_common_days"]), f"{src} volatility_history maturity n_common_days")
    put("vh.horizons", ", ".join(str(h) for h in mat["horizons"]), f"{src} volatility_history maturity horizons")
    put("vh.longest", ", ".join(str(h) for h in mat["not_measurable"]), f"{src} maturity not_measurable")

    # Bar ii read against ADR 0003's own band, and why [forward, 1 / reverse] cannot test the slope
    band = vxd["bar_ii"]["exploratory_adr_band"]["band"]
    below = [nm for nm in names if b2[nm]["slope"] < band[0]]
    put("vx.ii_below_names", _join(below), f"{src} bar_ii names with a slope below the ADR band")
    put("vx.ii_band", f"[{fnum(band[0], 1)}, {fnum(band[1], 1)}]", f"{src} bar_ii exploratory_adr_band.band")
    put("vx.ii_band_lo", fnum(band[0], 1), f"{src} bar_ii exploratory_adr_band.band[0]")
    put("vx.pooled.sd", fnum(_sd_ratio(b2["pooled"]), 2),
        f"{src} bar_ii pooled sqrt(slope × 1 / reverse slope) = sd(dln VX) / sd(dln ours)")
    sds = [_sd_ratio(b2[nm]) for nm in names]
    put("vx.sd_min", fnum(min(sds), 2), f"{src} bar_ii sd ratio, smallest name")
    put("vx.sd_max", fnum(max(sds), 2), f"{src} bar_ii sd ratio, largest name")

    # Bar iii: the yearly medians of GS (the step the rule's all-years median hides)
    yrs = b3["GS"]["years"]
    early = [yrs[y]["median_spread"] for y in ("2020", "2021", "2022")]
    late = [yrs[y]["median_spread"] for y in ("2023", "2024", "2025", "2026")]
    put("vx.gs.early_lo", fnum(min(early), 1), f"{src} bar_iii GS years 2020-2022 median_spread, smallest")
    put("vx.gs.early_hi", fnum(max(early), 1), f"{src} bar_iii GS years 2020-2022 median_spread, largest")
    put("vx.gs.late_lo", fnum(min(late), 1), f"{src} bar_iii GS years 2023-2026 median_spread, smallest")
    put("vx.gs.late_hi", fnum(max(late), 1), f"{src} bar_iii GS years 2023-2026 median_spread, largest")
    put("vx.gs.step", fnum(sum(early) / len(early) - sum(late) / len(late), 1),
        f"{src} bar_iii GS mean of the 2020-2022 medians less the mean of the 2023-2026 medians")

    # Exploratory, not pre-registered (ledger §9)
    ex = vxd["exploratory"]
    cal = ex["snapshot_calendar"]
    put("vx.cal.era_from", cal["daily_era_from"], f"{src} exploratory snapshot_calendar.daily_era_from")
    put("vx.cal.end_monday", fint(cal["n_end_monday"]), f"{src} exploratory snapshot_calendar n_end_monday")
    put("vx.cal.end_monday_share", fpct(cal["n_end_monday"] / cal["n"], 0),
        f"{src} exploratory snapshot_calendar n_end_monday / n")
    put("vx.cal.early", fint(cal["n_before_era"]), f"{src} exploratory snapshot_calendar n_before_era")
    put("vx.cal.early_monday", fint(cal["n_before_era_end_monday"]),
        f"{src} exploratory snapshot_calendar n_before_era_end_monday")
    for key, what in (("mon_vx", "mean_dln_vx_end_monday"), ("mon_ours", "mean_dln_ours_end_monday"),
                      ("oth_vx", "mean_dln_vx_other"), ("oth_ours", "mean_dln_ours_other")):
        put(f"vx.cal.{key}", fsigned(cal[what], 4), f"{src} exploratory snapshot_calendar {what}")
    for part, label in (("bar_i_tue_to_fri", "tf"), ("bar_i_without_day0", "d0")):
        for nm in names + ["pooled"]:
            x = ex[part][nm]
            put(f"vx.{label}.{nm.lower()}.n", fint(x["n"]), f"{src} exploratory {part} {nm} n")
            put(f"vx.{label}.{nm.lower()}.r", fnum(x["r"], 3), f"{src} exploratory {part} {nm} r")
            put(f"vx.{label}.{nm.lower()}.r_ci", fci(x["r_block20"]["lo"], x["r_block20"]["hi"], 3),
                f"{src} exploratory {part} {nm} r_block20")
    put("vx.d0.dropped", fint(ex["bar_i_without_day0"]["n_dropped"]), f"{src} exploratory bar_i_without_day0 n_dropped")
    for k, by in ex["stepped_changes"]["by_k"].items():
        for nm in names + ["pooled"]:
            put(f"vx.step{k}.{nm.lower()}.n", fint(by[nm]["n"]), f"{src} exploratory stepped_changes k={k} {nm} n")
            put(f"vx.step{k}.{nm.lower()}.slope", fnum(by[nm]["slope"], 3),
                f"{src} exploratory stepped_changes k={k} {nm} slope")
            put(f"vx.step{k}.{nm.lower()}.rev", fnum(by[nm]["reverse_slope_reciprocal"], 3),
                f"{src} exploratory stepped_changes k={k} {nm} 1 / reverse slope")

    # iv_current read as 30 calendar days, and how far the horizons were extrapolated (exploratory)
    c30 = mat["calendar_30"]
    put("vh.cal.n", fint(c30["n_days_same"]), f"{src} maturity calendar_30 n_days_same")
    put("vh.cal.med", fnum(c30["median_abs_diff_same_days"]["calendar_30"], 3),
        f"{src} maturity calendar_30 median_abs_diff_same_days.calendar_30")
    put("vh.cal.med21", fnum(c30["median_abs_diff_same_days"]["sessions_21"], 3),
        f"{src} maturity calendar_30 median_abs_diff_same_days.sessions_21")
    put("vh.cal.r", fnum(c30["change_correlation"]["calendar_30"]["r"], 3),
        f"{src} maturity calendar_30 change_correlation.calendar_30")
    put("vh.cal.r21", fnum(c30["change_correlation"]["sessions_21"]["r"], 3),
        f"{src} maturity calendar_30 change_correlation.sessions_21")
    ext = mat["extrapolated"]["by_horizon"]
    put("vh.extrap.max", fint(mat["max_extrap_sessions"]), f"{src} maturity max_extrap_sessions")
    put("vh.extrap.h42", fint(ext["42"]["n_beyond_last_expiry"]), f"{src} maturity extrapolated 42 n_beyond_last_expiry")
    put("vh.extrap.h42_n", fint(ext["42"]["n_days"]), f"{src} maturity extrapolated 42 n_days")
    put("vh.extrap.h10", fint(ext["10"]["n_before_first_expiry"]),
        f"{src} maturity extrapolated 10 n_before_first_expiry")
    put("vh.extrap.h10_n", fint(ext["10"]["n_days"]), f"{src} maturity extrapolated 10 n_days")


def vx_prose_check(vxd: dict, cm30_sessions: int) -> None:
    """The hand-written sentences about the VX* cross-check (report §3.2 and §7, README, PR/FAQ, milestone 5)."""
    names, b1, b2, b3 = _vx_rows(vxd)
    fails_i = sorted(nm for nm in names + ["pooled"] if b1[nm]["verdict"] == "fail")
    iv, lags = vxd["bar_iv"], vxd["alignment_falsifier"]
    vh = vxd["volatility_history"]
    r_vx = vh["iv_current_vs_vx"]["r_primary_changes"]["pooled"]
    ex, steps, c30, ext = vxd["exploratory"], vxd["exploratory"]["stepped_changes"]["by_k"], vh["maturity"]["calendar_30"], \
        vh["maturity"]["extrapolated"]["by_horizon"]
    below_slope = sorted(nm for nm in names if b2[nm]["slope"] < vxd["bar_ii"]["exploratory_adr_band"]["band"][0])
    claims = [
        ("VX bar i fails for GOOGL, IBM and the pooled sample, passes for AAPL, AMZN and GS",
         fails_i == ["GOOGL", "IBM", "pooled"]),
        ("VX bar ii: every slope below 1 and no 95% interval (block 20) holds 1",
         all(b2[nm]["slope"] < 1 and not b2[nm]["bar_ii_interval_holds_1"]["block20"] for nm in names + ["pooled"])),
        ("VX bar ii: the reverse regression's reciprocal is above 1 for every name and pooled",
         all(b2[nm]["reverse_slope_reciprocal"] > 1 for nm in names + ["pooled"])),
        ("VX bar i: only IBM's interval lies wholly below 0.8; the other names' and the pooled interval hold 0.8",
         [nm for nm in names + ["pooled"] if b1[nm]["block20"]["hi"] < vxd["bar_i"]["bar"]] == ["IBM"]
         and all(b1[nm]["block20"]["lo"] <= vxd["bar_i"]["bar"] <= b1[nm]["block20"]["hi"]
                 for nm in names + ["pooled"] if nm != "IBM")),
        ("VX bar ii (exploratory ADR band): AAPL and AMZN inside [0.8, 1.2], GOOGL, GS and IBM below it",
         vxd["bar_ii"]["exploratory_adr_band"]["band"] == [0.8, 1.2]
         and {nm for nm in names if vxd["bar_ii"]["exploratory_adr_band"]["slope_in_band"][nm]} == {"AAPL", "AMZN"}
         and all(b2[nm]["slope"] < 0.8 for nm in ("GOOGL", "GS", "IBM"))),
        ("VX bar iii passes for all five names, with Cboe above ours on most days and in the median",
         all(b3[nm]["verdict"] == "pass" and b3[nm]["share_above"] > 0.5 and b3[nm]["median_spread"] > 0
             for nm in names)),
        ("VX bar iv: the event-bootstrap interval lies below 1", iv["events_bootstrap"]["hi"] < 1),
        ("VX bar iv passes (provisional)", iv["verdict"] == "pass"),
        ("VX bar iv: most events of the five names rest on a document's timing label, a few on the "
         "calendar's",
         0 < iv["events"]["timing_status_counts"].get("not_checked", 0) < iv["events"]["n_events_five_names"] / 2),
        ("VX lags: lag 0 has the highest pooled correlation", lags["lags_above_lag0"] == []
         and lags["highest_lag"] == 0),
        ("VX lags: one session either side is near 0 (|r| < 0.1)",
         abs(lags["lags"]["-1"]["r"]) < 0.1 and abs(lags["lags"]["+1"]["r"]) < 0.1),
        ("VX secondary changes correlate more than the one-session changes (pooled)",
         vxd["secondary"]["pooled"]["r"] > b1["pooled"]["r"]),
        ("VX secondary: the pooled slope below 1 and its 1 / reverse slope above 1 (its interval too), a narrower pair "
         "than the one-session changes'; for AAPL and "
         "AMZN alone the 1 / reverse slope is below 1 with an interval that holds 1",
         vxd["secondary"]["pooled"]["slope"] < 1 < vxd["secondary"]["pooled"]["block20"]["reverse_slope_reciprocal"]["lo"]
         and (vxd["secondary"]["pooled"]["reverse_slope_reciprocal"] - vxd["secondary"]["pooled"]["slope"]
              < b2["pooled"]["reverse_slope_reciprocal"] - b2["pooled"]["slope"])
         and {nm for nm in names if vxd["secondary"][nm]["reverse_slope_reciprocal"] < 1} == {"AAPL", "AMZN"}
         and all(vxd["secondary"][nm]["block20"]["reverse_slope_reciprocal"]["lo"] <= 1
                 <= vxd["secondary"][nm]["block20"]["reverse_slope_reciprocal"]["hi"] for nm in ("AAPL", "AMZN"))),
        ("volatility_history: maturity identified at 21 sessions, the 30-day IV's horizon",
         vh["maturity"]["identification"]["status"] == "identified"
         and vh["maturity"]["identification"]["horizon"] == 21 == cm30_sessions),
        ("VX ADR 0003's slope falsifier is met: GOOGL, GS and IBM (3 of 5, most) have a slope below 0.8",
         below_slope == ["GOOGL", "GS", "IBM"] and 2 * len(below_slope) > len(names)),
        ("VX ADR 0003's correlation falsifier is not met: only 2 of 5 names have r below 0.8",
         2 * sum(b1[nm]["verdict"] == "fail" for nm in names) < len(names)),
        ("VX ADR 0003's crush-ratio falsifier is not met: the ratio lies inside [0.8, 1.2]",
         vxd["bar_ii"]["exploratory_adr_band"]["band"][0] <= iv["ratio"] <= vxd["bar_ii"]["exploratory_adr_band"]["band"][1]),
        ("VX bar ii: the two series' daily changes have nearly the same sd (ratio 0.9 to 1.0 for every name and "
         "pooled), so [forward, 1 / reverse] brackets 1 by construction",
         all(0.9 <= _sd_ratio(b2[nm]) <= 1.0 and b2[nm]["slope"] <= _sd_ratio(b2[nm]) <= b2[nm]["reverse_slope_reciprocal"]
             for nm in names + ["pooled"])),
        ("VX bar iii: GS's yearly medians step from 3.5-4.2 (2020-22) to 1.6-2.2 (2023-26); the all-days median "
         "lies between the two levels, so the rule (within 2.0) passes",
         all(3.5 < b3["GS"]["years"][y]["median_spread"] < 4.2 for y in ("2020", "2021", "2022"))
         and all(1.6 < b3["GS"]["years"][y]["median_spread"] < 2.2 for y in ("2023", "2024", "2025", "2026"))
         and max(b3["GS"]["years"][y]["median_spread"] for y in ("2023", "2024", "2025", "2026"))
         < b3["GS"]["median_spread"]
         < min(b3["GS"]["years"][y]["median_spread"] for y in ("2020", "2021", "2022"))
         and b3["GS"]["verdict"] == "pass"),
        ("VX exploratory: changes ending on a Monday are a minority overall but nearly all (over 85%) before the "
         "daily era, and the index rises on them while ours falls",
         2 * ex["snapshot_calendar"]["n_end_monday"] < ex["snapshot_calendar"]["n"]
         and ex["snapshot_calendar"]["n_before_era_end_monday"] > 0.85 * ex["snapshot_calendar"]["n_before_era"]
         and ex["snapshot_calendar"]["mean_dln_vx_end_monday"] > 0 > ex["snapshot_calendar"]["mean_dln_ours_end_monday"]),
        ("VX exploratory: on Tuesday-to-Friday changes r is above 0.8 for GOOGL and the pooled sample, below it for "
         "IBM; the pooled and GOOGL's r are above their all-changes r",
         ex["bar_i_tue_to_fri"]["GOOGL"]["r"] > 0.8 and ex["bar_i_tue_to_fri"]["pooled"]["r"] > 0.8
         and ex["bar_i_tue_to_fri"]["IBM"]["r"] < 0.8
         and all(ex["bar_i_tue_to_fri"][nm]["r"] > b1[nm]["r"] for nm in ("GOOGL", "pooled"))),
        ("VX exploratory: without the changes that end on a day 0, r falls for every name and the pooled sample is "
         "below 0.8; IBM's is the lowest",
         all(ex["bar_i_without_day0"][nm]["r"] < b1[nm]["r"] for nm in names + ["pooled"])
         and ex["bar_i_without_day0"]["pooled"]["r"] < 0.8
         and min(names, key=lambda nm: ex["bar_i_without_day0"][nm]["r"]) == "IBM"),
        ("VX exploratory: the pooled forward slope of non-overlapping changes rises with the horizon "
         "(k = 1, 10, 21) to above 0.9; IBM's stays below 0.95 and is the lowest at k = 10 and 21, every other "
         "name is at 0.94 or more",
         steps["1"]["pooled"]["slope"] < steps["10"]["pooled"]["slope"] < steps["21"]["pooled"]["slope"]
         and steps["10"]["pooled"]["slope"] > 0.9
         and all(steps[k]["IBM"]["slope"] < 0.95 and min(names, key=lambda nm: steps[k][nm]["slope"]) == "IBM"
                 and all(steps[k][nm]["slope"] >= 0.94 for nm in names if nm != "IBM") for k in ("10", "21"))),
        ("VX exploratory: with iv_current read as 30 calendar days the median |difference| is smaller and the "
         "change correlation higher than at 21 sessions (same days)",
         c30["median_abs_diff_same_days"]["calendar_30"] < c30["median_abs_diff_same_days"]["sessions_21"]
         and c30["change_correlation"]["calendar_30"]["r"] > c30["change_correlation"]["sessions_21"]["r"]),
        ("volatility_history: most 42-session values lie beyond the last listed expiry, about 4 in 10 10-session "
         "values before the first, and under 1% of the 21-session values are extrapolated",
         ext["42"]["n_beyond_last_expiry"] > 0.5 * ext["42"]["n_days"]
         and ext["10"]["n_before_first_expiry"] > 0.3 * ext["10"]["n_days"]
         and (ext["21"]["n_beyond_last_expiry"] + ext["21"]["n_before_first_expiry"]) < 0.01 * ext["21"]["n_days"]),
        ("volatility_history: no value at 63 sessions on any day", vh["maturity"]["not_measurable"] == [63]),
        ("volatility_history: the minimum is not at an edge of the measurable horizons",
         min(vh["maturity"]["identification"]["measurable"]) < vh["maturity"]["identification"]["argmin"]
         < max(vh["maturity"]["identification"]["measurable"])),
        ("volatility_history: iv_current's pooled r with VX above ours, the intervals overlapping",
         r_vx["r"] > b1["pooled"]["r"] and r_vx["block20"]["lo"] < b1["pooled"]["block20"]["hi"]),
        ("volatility_history: iv_current sits above ours in the median, VX above iv_current",
         vh["iv_current_vs_ours"]["spread_iv_current_minus_ours"]["pooled"]["median_spread"] > 0
         and vh["iv_current_vs_vx"]["spread_vx_minus_iv_current"]["pooled"]["median_spread"] > 0),
    ]
    wrong = [what for what, ok in claims if not ok]
    if wrong:
        raise ValueError("the data now contradict sentences in the templates; revise them:\n  " + "\n  ".join(wrong))


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
    same("look-ups done / press releases + EDGAR (events.parquet)", fun["lookups"]["n_done"],
         d["timing_source"].get("press_release", 0) + d["timing_source"].get("edgar", 0), 0)
    same("look-ups open / pinned reasons", LOOKUPS_REQUIRED - fun["lookups"]["n_done"],
         sum(LOOKUPS_OPEN_BY_REASON.values()), 0)
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
    # The VX* cross-check was computed from the same committed data and the same pinned commits.
    vxd = d["vx"]
    same("VX bar iv's primary sample / meta.json sample size", vxd["bar_iv"]["events"]["n_primary_sample"],
         meta["sample"]["n_events"], 0)
    for what, a, b in (("options commit", vxd["inputs"]["options_commit"], meta["provenance"]["dolt_commits"]["options"]),
                       ("params hash", vxd["inputs"]["params_hash"][:16], meta["provenance"]["params_hash"][:16])):
        if a != b:
            problems.append(f"VX cross-check {what} {a} against meta.json {b}")
    # Bar iv rests on the events' day 0: new timing labels (a new events.parquet) need a re-run of the cross-check.
    if vxd["inputs"]["events_sha256"] != d["events_sha256"]:
        problems.append(f"VX cross-check events.parquet {vxd['inputs']['events_sha256'][:12]} against the committed "
                        f"{d['events_sha256'][:12]}: re-run tools/vx_crosscheck.py")
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
    """Compare the pinned look-up counts with the local stage report, when there is one (never in CI)."""
    base = Path(os.environ.get("VOL_DATA_DIR", Path.home() / "data/vol-projects")) / "earnings-vol-study/cache/stage"
    params_hash = load(root)["meta"]["provenance"]["params_hash"][:16]
    rep = base / params_hash / "events_report.json"
    if not rep.exists():
        return f"look-ups: {LOOKUPS_REQUIRED} pinned, not re-measured (no local {rep.name})"
    stage = json.loads(rep.read_text())
    left = stage["lookup_violations"]["n"]
    done = load(root)["sample_funnel"]["lookups"]["n_done"]
    if left + done != LOOKUPS_REQUIRED:
        raise ValueError(f"look-ups: the stage report says {left} left + {done} done = {left + done}, "
                         f"not {LOOKUPS_REQUIRED}")
    ed = stage.get("edgar") or {}
    if not ed.get("on"):
        raise ValueError("look-ups: the stage report has no EDGAR run (params timing.edgar), but the pins are from one")
    open_by = {k: v for k, v in ed["outcome"].items() if k not in ("confirmed", "inferred", "press_release")}
    if open_by != LOOKUPS_OPEN_BY_REASON:
        raise ValueError(f"look-ups: the stage report's open look-ups are {open_by}, not {LOOKUPS_OPEN_BY_REASON}")
    null_open = stage["lookup_violations"]["by_reason"].get("null_label", 0)
    if null_open != load(root)["not_checked_open_unlabelled"]:
        raise ValueError(f"look-ups: the stage report has {null_open} open look-ups with a NULL label, "
                         f"events.parquet {load(root)['not_checked_open_unlabelled']}")
    if ed["pending_gap_checks"] != LOOKUPS_GAP_QUESTIONED:
        raise ValueError(f"look-ups: the stage report's gap-questioned EDGAR labels are {ed['pending_gap_checks']}, "
                         f"not {LOOKUPS_GAP_QUESTIONED}")
    return (f"look-ups: {left} left + {done} done = {LOOKUPS_REQUIRED}; open by reason and "
            f"{LOOKUPS_GAP_QUESTIONED} gap-questioned, as pinned (local {rep.name})")


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
