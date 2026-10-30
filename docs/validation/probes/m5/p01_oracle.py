"""p01: an independent oracle for every generated number in the report, the README blocks and the PR/FAQ blocks.

Does NOT import tools/report_numbers.py. Each value is selected from results.parquet / app JSON / the kept rho-bar
output with this file's own filters, and formatted with this file's own Decimal rounding (ROUND_HALF_EVEN on the
exact binary value). The rendered files are aligned with their templates (literal text must match exactly), so each
placeholder's rendered string is compared with the oracle's string for that placeholder, and its context is printed
for a by-eye check that the right number sits in the right sentence.

    uv run --frozen --offline --no-sync python docs/validation/probes/m5/p01_oracle.py [--root R] [--falsify]

--falsify: the oracle reads H1 from the mean-adjusted twin (a wrong row); the run must then report mismatches (rc 1).
Prints counts, per-key results and contexts. Never prints a per-event value or a VIX value.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

import pandas as pd

M = "−"


# ---- own formatting -----------------------------------------------------------------------------------------
def q(x: float, nd: int) -> str:
    d = Decimal(x).quantize(Decimal(1).scaleb(-nd), rounding=ROUND_HALF_EVEN)
    s = format(d, "f")
    if Decimal(s) == 0:
        s = s.lstrip("-")
    return s.replace("-", M)


def sg(x: float, nd: int) -> str:
    s = q(x, nd)
    if s.startswith(M) or Decimal(s.replace(M, "-")) == 0:
        return s
    return "+" + s


def sig(x: float, n: int) -> str:
    """n significant digits, trailing zeros dropped (the convention seen in the docs: 0.75, 0.0469)."""
    if x == 0:
        return "0"
    e = math.floor(math.log10(abs(x)))
    d = Decimal(x).quantize(Decimal(1).scaleb(e - n + 1), rounding=ROUND_HALF_EVEN)
    s = format(d, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def sci(x: float, n: int = 2) -> str:
    e = math.floor(math.log10(abs(x)))
    mant = Decimal(x).scaleb(-e).quantize(Decimal(1).scaleb(-(n - 1)), rounding=ROUND_HALF_EVEN)
    if abs(mant) >= 10:
        e += 1
        mant = Decimal(x).scaleb(-e).quantize(Decimal(1).scaleb(-(n - 1)), rounding=ROUND_HALF_EVEN)
    return f"{mant}e{e}".replace("-", M)


def pv(p: float) -> str:
    if p >= 0.9995:
        return "1"
    if p < 1e-3:
        return sci(p, 2)
    if p < 0.01:
        return sig(p, 2)
    return sig(p, 3)


def pct(x: float, nd: int = 2) -> str:
    return q(100 * x, nd) + "%"


def ci(lo, hi, nd):
    return f"[{q(lo, nd)}, {q(hi, nd)}]"


def comma(n) -> str:
    return f"{int(n):,}"


# ---- own selection ------------------------------------------------------------------------------------------
def oracle(root: Path, falsify: bool) -> dict[str, str]:
    r = pd.read_parquet(root / "data/derived/results.parquet")
    J = {k: json.loads((root / f"app/public/data/{k}.json").read_text()) for k in
         ("meta", "sample_funnel", "iv_measures", "tests", "event_paths", "drivers", "implied_vs_realised")}
    D = {k: v["data"] for k, v in J.items()}
    rho = (root / "research/prototypes/rhobar_crush.out.txt").read_text()
    o: dict[str, str] = {}

    def row(**f):
        x = r
        for k, v in f.items():
            x = x[x[k] == v] if not (isinstance(v, float) and math.isnan(v)) else x[x[k].isna()]
        assert len(x) == 1, (f, len(x))
        return x.iloc[0]

    ev = dict(family="event_test", sample="daily", subgroup_key="all")
    H = {
        "H1": row(**ev, hypothesis="H1", statistic="twoway_date_t", adjustment="mean" if falsify else "market",
                  role="robustness" if falsify else "primary"),
        "H2": row(**ev, hypothesis="H2", statistic="rad_season_p", adjustment="market", role="primary"),
        "H3": row(**ev, hypothesis="H3", statistic="twoway_season_t", adjustment="market", role="primary"),
        "H4": row(**ev, hypothesis="H4", statistic="twoway_date_t", adjustment="market", role="primary"),
        "H5": row(family="regression", model_id="crush_drivers", term="abs_surprise", statistic="twoway_date_t",
                  adjustment="market", sample="daily", role="primary"),
        "H6": row(family="regression", model_id="crush_drivers", term="ln_sigma_d", statistic="twoway_date_t",
                  adjustment="market", sample="daily", role="primary"),
        "H7": row(family="regression", model_id="implied_realised", term="a=0,b=1", statistic="twoway_date_wald",
                  sample="daily", role="primary"),
    }
    meta = D["meta"]
    o["sample.n_events"] = comma(meta["sample"]["n_events"])
    o["sample.n_companies"] = comma(len({e["ticker"] for e in D["event_paths"]["per_event"]}))
    o["sample.day0_from"] = min(e["day0"] for e in D["event_paths"]["per_event"])
    o["sample.day0_to"] = max(e["day0"] for e in D["event_paths"]["per_event"])
    o["meta.schema_version"] = J["meta"]["schema_version"]
    o["meta.source_commit"] = J["meta"]["source_commit"]
    o["meta.params_hash"] = meta["provenance"]["params_hash"][:16]
    o["meta.dolt_earnings"] = meta["provenance"]["dolt_commits"]["earnings"]
    o["meta.dolt_options"] = meta["provenance"]["dolt_commits"]["options"]
    b0, b1 = meta["params"]["baseline"]
    o["params.baseline"] = f"[{M}{abs(b0)}, {M}{abs(b1)}]"
    w0, w1 = meta["params"]["event_window"]
    o["params.window"] = f"[{M}{abs(w0)}, +{w1}]"
    o["params.cm30_sessions"] = str(meta["params"]["cm30_horizon_sessions"])

    fun = D["sample_funnel"]
    prev = None
    for s in fun["steps"]:
        o[f"funnel.{s['step']}"] = comma(s["n_events"])
        rem = 0 if prev is None else prev - s["n_events"]
        assert rem == s["n_removed"], (s["step"], rem, s["n_removed"])
        o[f"funnel.{s['step']}.removed"] = comma(rem)
        prev = s["n_events"]
    for s in fun["by_sample"]:
        o[f"events.{s['sample']}"] = comma(s["n_events"])
    for k, v in fun["timing_status_counts"].items():
        o[f"timing.{k}"] = comma(v)
    done = sum(v for k, v in fun["timing_status_counts"].items() if k != "not_checked")
    o["lookups.done"] = comma(done)
    o["lookups.required"] = "473"  # pinned; checked separately against the local stage report and milestone 1 §6
    o["lookups.left"] = comma(473 - done)
    o["evar.nonpositive"] = comma(fun["evar_nonpositive"]["n"])

    # G1
    T, DR, IVR = D["tests"], D["drivers"], D["implied_vs_realised"]
    o["g1.band_lo"], o["g1.band_hi"] = pct(T["g1"]["band"][0]), pct(T["g1"]["band"][1])
    o["g1.reps"] = comma(T["g1"]["reps"])
    g1r = r[(r.measure == "g1:calibrated")]
    for h in ("H1", "H2", "H3", "H4", "H5", "H6", "H7"):
        st = H[h].statistic if not (falsify and h == "H1") else "twoway_date_t"
        x = g1r[(g1r.hypothesis == h) & (g1r.statistic == st)]
        if len(x) != 1:  # fall back to the JSON (the statistic key may carry a suffix in results)
            rate = [c for c in T["g1"]["calibrated"] if c["hypothesis"] == h][0]["rejection_rate"]
        else:
            rate = float(x.iloc[0].estimate)
        o[f"{h.lower()}.g1"] = pct(rate)
        ok = rate <= T["g1"]["band"][1]
        o[f"{h.lower()}.g1_verdict"] = "pass" if ok else "**fail**"
    for h in ("H1", "H2", "H3", "H4"):
        o[f"{h.lower()}.power80"] = q([p for p in T["g1"]["power"] if p["hypothesis"] == h][0]["detectable_80"], 3)
    for h in ("H5", "H6"):
        o[f"{h.lower()}.power80"] = q([p for p in DR["g1"]["power"] if p["hypothesis"] == h][0]["detectable_80"], 3)
    for h, st in (("H5", "cluster_date_t"), ("H6", "cluster_date_t"), ("H7", "cluster_date_wald")):
        o[f"{h.lower()}.g1_oneway"] = pct([c for c in DR["g1"]["calibrated"]
                                           if c["hypothesis"] == h and c["statistic"] == st][0]["rejection_rate"])

    # Holm, own
    o["holm.m"] = str(len(T["holm"]["family"]))
    ps = {h: H[h].p_value for h in H}

    def holm(pmap):
        items = sorted(pmap.items(), key=lambda kv: kv[1])
        m, out, run = len(items), {}, 0.0
        for i, (h, p) in enumerate(items):
            run = max(run, min(1.0, (m - i) * p))
            out[h] = run
        return out

    hp = holm(ps)
    for h in H:
        k = h.lower()
        x = H[h]
        o[f"{k}.n"] = comma(x.n)
        o[f"{k}.p"] = pv(x.p_value)
        o[f"{k}.p_holm"] = pv(hp[h])
        o[f"{k}.statistic"] = x.statistic
        if not math.isnan(x.n_clusters):
            o[f"{k}.g_time"] = comma(x.n_clusters)
        if not math.isnan(x.n_clusters_firm):
            o[f"{k}.g_firm"] = comma(x.n_clusters_firm)
        if h != "H7":
            o[f"{k}.est"] = sg(x.estimate, 3)
            o[f"{k}.est4"] = sg(x.estimate, 4)
            if not math.isnan(x.se):
                o[f"{k}.se"] = q(x.se, 4)
                o[f"{k}.t"] = q(x.stat, 2)
                o[f"{k}.ci"] = ci(x.ci_lo, x.ci_hi, 3)
    o["h1.fall"] = q(-H["H1"].estimate, 3)
    o["h1.fall4"] = q(-H["H1"].estimate, 4)
    o["h1.df"] = comma(min(H["H1"].n_clusters, H["H1"].n_clusters_firm) - 1)
    o["h1.pct_fall"] = pct(1 - math.exp(H["H1"].estimate), 1)
    o["h3.df"] = comma(min(H["H3"].n_clusters, H["H3"].n_clusters_firm) - 1)
    o["h7.f"] = q(H["H7"].stat, 2)
    o["h7.df_num"] = comma(H["H7"].df_num)
    o["h7.df"] = comma(min(H["H7"].n_clusters, H["H7"].n_clusters_firm) - 1)

    cut = row(family="event_test", hypothesis="H2", subgroup_key="season_cut", adjustment="market")
    o["h2.cut_g"] = comma(cut.n_clusters)
    o["h2.cut_p"] = pv(2 / 2 ** int(cut.n_clusters))
    o["h2.cut_p_holm"] = pv(holm({**ps, "H2": 2 / 2 ** int(cut.n_clusters)})["H2"])
    tw = row(**ev, hypothesis="H2", statistic="twoway_season_t", adjustment="market", role="robustness")
    o["h2.twoway_t"] = q(tw.stat, 2)
    o["h2.twoway_p"] = pv(tw.p_value)
    o["h2.floor_g"] = comma(H["H2"].n_clusters)
    pg = holm({h: ps[h] for h in ("H1", "H2", "H3", "H4")})
    o["postgate.h1"], o["postgate.h2"] = pv(pg["H1"]), pv(pg["H2"])
    o["postgate.h2_cut"] = pv(holm({"H1": ps["H1"], "H2": 2 / 2 ** int(cut.n_clusters), "H3": ps["H3"],
                                    "H4": ps["H4"]})["H2"])

    def term(model, t, stat="twoway_date_t"):
        return row(family="regression", model_id=model, term=t, statistic=stat, sample="daily")

    b, a = term("implied_realised", "b"), term("implied_realised", "a")
    o["h7.b"], o["h7.b3"], o["h7.b_ci"] = q(b.estimate, 2), q(b.estimate, 3), ci(b.ci_lo, b.ci_hi, 2)
    o["h7.b_p"], o["h7.a"], o["h7.a_p"] = pv(b.p_value), q(a.estimate, 5), pv(a.p_value)
    b2 = term("implied_realised_m2", "b")
    o["h7.m2_b"], o["h7.m2_n"] = q(b2.estimate, 2), comma(b2.n)
    o["h7.m2_p"] = pv(term("implied_realised_m2", "a=0,b=1", "twoway_date_wald").p_value)
    o["drivers.r2"] = q(row(family="regression", model_id="crush_drivers", statistic="r2", sample="daily").estimate, 3)
    sl, sz = term("crush_drivers", "slope"), term("crush_drivers", "size")
    o["slope.est"], o["slope.p"], o["slope.q"] = sg(sl.estimate, 3), pv(sl.p_value), q(sl.q_bh, 4)
    o["size.est"], o["size.q"] = sg(sz.estimate, 3), pv(sz.q_bh)
    for key, model, t in (("sue", "crush_sue", "abs_sue"), ("disp", "crush_disp", "abs_disp"),
                          ("firmfe", "crush_firm_fe", "abs_surprise")):
        x = term(model, t)
        o[f"surprise.{key}"], o[f"surprise.{key}_q"] = sg(x.estimate, 3), pv(x.q_bh)
    o["slope.dsigma"] = sg(row(family="regression", model_id="dsigma_d_drivers", term="slope",
                               statistic="twoway_date_t").estimate, 3)

    o["h1.twin"] = sg(row(**ev, hypothesis="H1", statistic="twoway_date_t", adjustment="mean").estimate, 3)
    o["h1.share_below"] = pct(row(**ev, hypothesis="H1", statistic="gen_sign_z").estimate, 1)
    ex = dict(family="event_test", role="exploratory", statistic="twoway_date_t")
    for key, f in (("amc", dict(measure="crush_cm30", sample="daily", subgroup_value="AMC")),
                   ("bmo", dict(measure="crush_cm30", sample="daily", subgroup_value="BMO")),
                   ("front", dict(measure="crush_front_fixed", sample="daily")),
                   ("coarse", dict(measure="crush_cm30", sample="coarse", adjustment="market")),
                   ("mixed", dict(measure="crush_cm30", sample="mixed", adjustment="market"))):
        x = row(**ex, **f)
        o[f"crush.{key}"], o[f"crush.{key}_n"] = sg(x.estimate, 3), comma(x.n)
    o["crush.front_fall"] = q(-row(**ex, measure="crush_front_fixed", sample="daily").estimate, 3)

    # withheld: own count over the three JSON files
    wh = set()
    for x in T["rows"]:
        if x["role"] == "robustness" and x["p_value"] is None and x["g1_size"] is not None:
            wh.add((x["hypothesis"], x["statistic"]))
    for mdl in DR["models"]:
        for t in mdl["terms"]:
            if t.get("role") == "robustness" and t.get("p_value") is None and t.get("g1_size") is not None:
                wh.add((t["hypothesis"], t["statistic"] + (" (mean-adjusted twin)" if mdl["adjustment"] == "mean" else "")))
    if IVR["summary"]["regression"]["wald_p_one_way"] is None:
        wh.add(("H7", "cluster_date_wald"))
    o["withheld.n"] = comma(len(wh))
    by = {}
    for h, s in sorted(wh):
        nm, _, note = s.partition(" (")
        by.setdefault(h, []).append(f"`{nm}`" + (f" ({note}" if note else ""))
    o["withheld.list"] = "; ".join(f"{h}: " + ", ".join(v) for h, v in by.items())

    P = D["event_paths"]
    for day, key in ((-10, "m10"), (-1, "m1"), (0, "d0"), (1, "p1"), (5, "p5"), (10, "p10")):
        s = [x for x in P["series"] if x["adjustment"] == "market" and x["subgroup_value"] == "all"][0]
        i = P["rel_days"].index(day)
        o[f"path.{key}"] = sg(s["mean"][i], 3)
        o[f"path.{key}_ci"] = ci(s["ci_lo"][i], s["ci_hi"][i], 3)
    for sub in ("AMC", "BMO"):
        s = [x for x in P["series"] if x["adjustment"] == "market" and x["subgroup_value"] == sub][0]
        o[f"path.{sub.lower()}_m1"] = sg(s["mean"][P["rel_days"].index(-1)], 3)

    iv = D["iv_measures"]
    o["iv.crush_median"] = sg(iv["crush"]["quantiles"]["p50"], 3)
    o["iv.crush_p10"] = sg(iv["crush"]["quantiles"]["p10"], 3)
    o["iv.crush_p90"] = sg(iv["crush"]["quantiles"]["p90"], 3)
    for k in ("p50", "p10", "p90"):
        o[{"p50": "iv.move_median", "p10": "iv.move_p10", "p90": "iv.move_p90"}[k]] = pct(iv["implied_move"]["quantiles"][k], 1)
    o["iv.move_n"] = comma(iv["implied_move"]["n"])

    pts = IVR["points"]
    pos = [p for p in pts if p["implied_abs_move_total"] is not None]
    o["ivr.n"] = comma(len(pts))
    o["ivr.n_pos"] = comma(len(pos))
    o["ivr.n_nonpos"] = comma(len(pts) - len(pos))
    share = sum(p["abs_realized"] > p["implied_abs_move_total"] for p in pos) / len(pos)
    o["ivr.share"] = pct(share, 1)
    o["ivr.benchmark"] = pct(2 * (1 - __import__("scipy.stats").stats.norm.cdf(math.sqrt(2 / math.pi))), 1)
    o["ivr.share_p"] = pv(row(family="regression", term="exceed_share").p_value)
    import statistics
    o["ivr.median_ratio"] = q(statistics.median(p["abs_realized"] / p["implied_abs_move_total"] for p in pos), 2)
    o["ivr.median_implied"] = pct(statistics.median(p["implied_abs_move_total"] for p in pos), 1)
    o["ivr.median_realised"] = pct(statistics.median(p["abs_realized"] for p in pts), 1)
    o["ivr.var_ratio"] = q(sum(p["realized_ret_0"] ** 2 for p in pts) / sum(p["implied_var_total"] for p in pts), 2)

    def grab(label):
        return float(re.search(re.escape(label) + r"\s*(-?\d+\.\d+)", rho).group(1))
    o["rhobar"] = q(grab("1. rho-bar"), 2)
    o["rhobar.no_top10"] = q(grab("rho-bar without the top 10 dates:"), 2)
    o["rhobar.loo"] = q(grab("all-firm leave-one-out factor:"), 3)
    o["results.rows"] = comma(len(r))
    rej = [h for h in H if hp[h] <= 0.05]
    o["holm.rejected"] = " and ".join(rej) if len(rej) == 2 else ", ".join(rej)
    return o


# ---- alignment -------------------------------------------------------------------------------------------------
PH = re.compile(r"\{\{\s*([a-z0-9_.]+)\s*\}\}")


def align(template: str, rendered: str, where: str):
    parts = PH.split(template)
    lits, keys = parts[0::2], parts[1::2]
    def grp(k):  # an interval is one bracketed group, so its inner ", " cannot be taken for template text
        return r"(\[[^\]\n]*\])" if k.endswith("ci") else "(.*?)"
    pat = "".join(re.escape(l) + (grp(keys[i]) if i < len(keys) else "") for i, l in enumerate(lits))
    m = re.fullmatch(pat, rendered, re.S)
    if not m:
        raise SystemExit(f"ALIGN FAIL {where}: the literal text of the template does not match the rendered file")
    out = []
    pos_lit = 0
    for i, k in enumerate(keys):
        s, e = m.span(i + 1)
        ctx = rendered[max(0, s - 60):s].replace("\n", " ") + "⟦" + m.group(i + 1) + "⟧" + rendered[e:e + 30].replace("\n", " ")
        out.append((k, m.group(i + 1), ctx))
    return out


def block(doc: str, name: str) -> str:
    b, e = f"<!-- numbers:{name} -->\n", f"\n<!-- /numbers:{name} -->"
    assert doc.count(b) == 1 and doc.count(e) == 1, name
    return doc[doc.index(b) + len(b):doc.index(e)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[4])
    ap.add_argument("--falsify", action="store_true")
    ap.add_argument("--contexts", action="store_true")
    a = ap.parse_args()
    root = a.root
    o = oracle(root, a.falsify)
    tpl = (root / "docs/report/templates/earnings-vol-report.md").read_text()
    tpl = tpl[tpl.index("-->\n") + 4:]  # the template note (two lines)
    rep = (root / "docs/report/earnings-vol-report.md").read_text().split("\n", 1)[1]
    jobs = [("report", tpl, rep)]
    readme, prfaq = (root / "README.md").read_text(), (root / "docs/prfaq.md").read_text()
    for name, doc in (("readme-summary", readme), ("readme-results", readme), ("prfaq-headline", prfaq),
                      ("prfaq-measured", prfaq)):
        t = (root / f"docs/report/templates/{name}.md").read_text().rstrip("\n")
        jobs.append((name, t, block(doc, name)))
    n = bad = 0
    keys_seen = set()
    for where, t, rd in jobs:
        for k, got, ctx in align(t, rd, where):
            n += 1
            keys_seen.add(k)
            want = o.get(k)
            ok = want == got
            bad += not ok
            if not ok or a.contexts:
                print(f"{'OK ' if ok else 'BAD'} {where:15} {k:22} got={got!r:14} want={want!r:14} | {ctx}")
    print(f"placeholders checked: {n}; distinct keys: {len(keys_seen)}; mismatches: {bad}")
    missing = sorted(k for k in keys_seen if k not in o)
    print(f"keys without an oracle value: {missing}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
