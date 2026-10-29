"""p10 (ADJUSTED in the fix round: expected values moved to the fixed milestone page, plus checks for F1, F6, F7).
p10: numbers in docs/milestones/03-event-study.md §6, README and DATA.md against the committed
results.parquet and app/public/data/tests.json (claims 10, 11). Aggregates only.
Run: uv run --frozen --no-sync python docs/validation/probes/m3/p10_numbers.py
"""
import json
import re

import pandas as pd

R = pd.read_parquet("data/derived/results.parquet")
T = json.load(open("app/public/data/tests.json"))["data"]
ev = R[R.family == "event_test"]


def get(h=None, st=None, adj="market", role=None, measure=None, sample="daily", sub="all"):
    q = ev[(ev.adjustment == adj) & (ev["sample"] == sample) & (ev.subgroup_value == sub)]
    if h:
        q = q[q.hypothesis == h]
    if st:
        q = q[q.statistic == st]
    if role:
        q = q[q.role == role]
    if measure:
        q = q[q.measure == measure]
    assert len(q) == 1, (h, st, adj, role, measure, sample, sub, len(q))
    return q.iloc[0]


checks = []


def chk(label, claimed, actual, tol):
    ok = abs(float(claimed) - float(actual)) <= tol
    checks.append(ok)
    print(f"{'OK ' if ok else 'BAD'} {label}: doc {claimed} vs data {actual:.6g}")


r = get("H1", "twoway_date_t", role="primary")
chk("H1 est", -0.1994, r.estimate, 5e-5); chk("H1 se", 0.0112, r.se, 5e-5); chk("H1 t", -17.73, r.stat, 5e-3)
chk("H1 df", 49, r.df, 0); chk("H1 p", 5.80e-23, r.p_value, 5e-26); chk("H1 p_holm", 4.06e-22, r.p_holm, 5e-25)
chk("H1 ci_lo", -0.2220, r.ci_lo, 5e-5); chk("H1 ci_hi", -0.1768, r.ci_hi, 5e-5)
chk("H1 n", 347, r.n, 0); chk("H1 G date", 172, r.n_clusters, 0); chk("H1 G firm", 50, r.n_clusters_firm, 0)
r = get("H2", "rad_season_p", role="primary")
chk("H2 est", 0.2319, r.estimate, 5e-5); chk("H2 p", 0.0078, r.p_value, 5e-5); chk("H2 p_holm", 0.0469, r.p_holm, 5e-5)
chk("H2 stat (one-way t)", 16.51, r.stat, 5e-3); chk("H2 G", 8, r.n_clusters, 0); chk("H2 n", 356, r.n, 0)
r = get("H3", "twoway_season_t", role="primary")
chk("H3 est", 0.0080, r.estimate, 5e-5); chk("H3 se", 0.0233, r.se, 5e-5); chk("H3 t", 0.34, r.stat, 5e-3)
chk("H3 p", 0.743, r.p_value, 5e-4); chk("H3 ci_lo", -0.0491, r.ci_lo, 5e-5); chk("H3 ci_hi", 0.0651, r.ci_hi, 5e-5)
r = get("H4", "twoway_date_t", role="primary")
chk("H4 est", 0.0031, r.estimate, 5e-5); chk("H4 se", 0.0112, r.se, 5e-5); chk("H4 p", 0.782, r.p_value, 5e-4)
chk("H4 G date", 134, r.n_clusters, 0); chk("H4 G firm", 47, r.n_clusters_firm, 0)
r = get("H1", "twoway_date_t", adj="mean"); chk("H1 twin est", -0.2009, r.estimate, 5e-5); chk("H1 twin t", -17.65, r.stat, 5e-3)
r = get("H1", "cluster_date_t"); chk("H1 one-way t", -31.24, r.stat, 5e-3); chk("H1 one-way se (6.5)", 0.0064, r.se, 5e-5)
chk("H1 kp_ow_t", -22.4, get("H1", "kp_ow_t").stat, 0.05); chk("H1 kpp_t", -23.0, get("H1", "kpp_t").stat, 0.05)
chk("H1 bmp_t", -29.5, get("H1", "bmp_t").stat, 0.05); chk("H1 patell", -79.1, get("H1", "patell_z").stat, 0.05)
chk("H1 sign share below 0", 0.991, get("H1", "gen_sign_z").estimate, 5e-4)
r = get("H2", "twoway_season_t"); chk("H2 two-way t", 13.43, r.stat, 5e-3); chk("H2 two-way se (6.5)", 0.0173, r.se, 5e-5)
chk("H2 one-way se (6.5)", 0.0140, get("H2", "cluster_season_t").se, 5e-5)
chk("H3 one-way se (6.5)", 0.0241, get("H3", "cluster_season_t").se, 5e-5)
chk("H2 twin est", 0.2333, get("H2", "rad_season_p", adj="mean").estimate, 5e-5)
r = get("H3", "twoway_season_t", adj="mean"); chk("H3 twin est", 0.0030, r.estimate, 5e-5); chk("H3 twin t", 0.09, r.stat, 5e-3)
x = ev[(ev.subgroup_value == "AMC") & (ev.measure == "crush_cm30")].iloc[0]; chk("AMC crush", -0.230, x.estimate, 5e-4); chk("AMC n", 182, x.n, 0)
x = ev[(ev.subgroup_value == "BMO") & (ev.measure == "crush_cm30")].iloc[0]; chk("BMO crush", -0.165, x.estimate, 5e-4); chk("BMO n", 165, x.n, 0)
x = ev[(ev["sample"] == "coarse") & (ev.measure == "crush_cm30") & (ev.adjustment == "market")].iloc[0]
chk("coarse crush", -0.190, x.estimate, 5e-4); chk("coarse n", 110, x.n, 0)
p = R[(R.family == "descriptive") & (R.adjustment == "market") & (R.subgroup_value == "all")]
for rel, est in ((-10, 0.239), (-1, 0.232), (0, 0.033), (10, 0.007)):
    chk(f"path day {rel}", est, p[p.rel_day == rel].estimate.iloc[0], 5e-4)
pw = {d["hypothesis"]: d for d in T["g1"]["power"]}
for h, v in (("H1", 0.036), ("H2", 0.102), ("H3", 0.121), ("H4", 0.036)):
    chk(f"{h} 80%-power shift", v, pw[h]["detectable_80"], 6e-4)   # tests.json holds it at 4 dp
cal = {c["hypothesis"]: c["rejection_rate"] for c in T["g1"]["calibrated"]}
for h, v in (("H1", 0.0445), ("H2", 0.0040), ("H3", 0.0050), ("H4", 0.0475)):
    chk(f"{h} calibrated G1 rate", v, cal[h], 5e-5)
V = R[R.family == "validation"]


def g(design, h, st):
    q = V[(V.measure == f"g1:{design}") & (V.hypothesis == h) & (V.statistic == st)]
    return float(q.estimate.iloc[0])


for st, v in (("cluster_date_t", 0.2275), ("bmp_t", 0.2420), ("kp_ow_t", 0.1435), ("kpp_t", 0.1440),
              ("patell_z", 0.6670), ("gen_sign_z", 0.1975), ("rank_t", 0.3720)):
    chk(f"11 calibrated H1 {st}", v, g("calibrated", "H1", st), 6e-4)
chk("stress D2+drift0.0015 H2 rad", 0.080, g("D2+drift0.0015", "H2", "rad_season_p"), 5e-5)
chk("stress common_ar0.9 H1", 0.177, g("D2+common_ar0.9", "H1", "twoway_date_t"), 5e-5)
chk("stress D3 H3", 0.068, g("D3", "H3", "twoway_season_t"), 5e-5)
chk("date-cluster mutant H2", 0.2055, g("calibrated", "H2", "date_cluster_t"), 5e-5)
chk("date-cluster mutant H3", 0.2280, g("calibrated", "H3", "date_cluster_t"), 5e-5)
chk("11 calibrated H4 gen_sign_z", 0.0645, g("calibrated", "H4", "gen_sign_z"), 5e-5)
chk("11 calibrated H4 rank_t", 0.1395, g("calibrated", "H4", "rank_t"), 5e-5)
chk("stress lag1 0.02 H4 (F7 row)", 0.0530, g("D2+lag1_0.02", "H4", "twoway_date_t"), 5e-5)
chk("stress lag1 0.05 H4 (F7 row)", 0.0695, g("D2+lag1_0.05", "H4", "twoway_date_t"), 5e-5)
# F1: the G = 7 counterfactual of H2
cut = ev[ev.subgroup_key == "season_cut"].iloc[0]
chk("F1 H2 G=7 p", 0.0156, cut.p_value, 5e-5); chk("F1 H2 G=7 p_holm", 0.0938, cut.p_holm, 5.1e-5); chk("F1 G", 7, cut.n_clusters, 0)
# F6: the nine withheld rows
wh = ev[(ev.role == "robustness") & ev.p_value.isna() & (ev.subgroup_value == "all")]
print("F6 withheld:", sorted(f"{a} {b}" for a, b in zip(wh.hypothesis, wh.statistic)))
chk("F6 withheld rows", 9, len(wh), 0)
# F7: baseline minimum, 7 of 366 (committed event_measures + events)
em = pd.read_parquet("data/derived/event_measures.parquet").merge(pd.read_parquet("data/derived/events.parquet")[["event_id", "sample", "exclusion_reason"]], on="event_id")
d = em[(em["sample"] == "daily") & em.exclusion_reason.isna()]
fail = ((d.baseline_n < 20) | (d.baseline_n_changes < 15))
chk("F7 daily events with window rows", 366, len(d), 0); chk("F7 failing the minimum", 7, int(fail.sum()), 0)
chk("6.5 beta median", 0.309, float(R[(R.measure == "g1_calibration:measured") & (R.statistic == "beta_median")].estimate.iloc[0]), 5e-4)
chk("mean vs market crush %", 0.78, 100 * abs(get("H1", "twoway_date_t", adj="mean").estimate - get("H1", "twoway_date_t").estimate) / abs(get("H1", "twoway_date_t").estimate), 5e-3)
# README's H1-H4 table
md = open("README.md").read()
for txt, val, tol in (("| −0.199 | 5.8e−23 | 4.1e−22 |", None, None),):
    pass
rows = {h: get(h, st) for h, st in (("H1", "twoway_date_t"), ("H2", "rad_season_p"), ("H3", "twoway_season_t"), ("H4", "twoway_date_t"))}
for h, est, p_, ph in (("H1", -0.199, 5.8e-23, 4.1e-22), ("H2", 0.232, 0.0078, 0.047), ("H3", 0.008, 0.74, 1.0), ("H4", 0.003, 0.78, 1.0)):
    chk(f"README {h} est", est, rows[h].estimate, 5e-4); chk(f"README {h} p", p_, rows[h].p_value, 0.0125 * p_); chk(f"README {h} p_holm", ph, rows[h].p_holm, 0.0125 * ph)   # 2 significant figures
chk("README H2 G=7 holm", 0.094, cut.p_holm, 5e-4)
for snippet in ("| 347 | −0.199 | 5.8e−23 | 4.1e−22 |", "| 356 | +0.232 | 0.0078 (randomisation floor, G = 8) | 0.047; **with G = 7: 0.094, not rejected** |", "| 329 | +0.008 | 0.74 | 1 |", "| 262 | +0.003 | 0.78 | 1 |"):
    ok = snippet in md; checks.append(ok); print(f"{'OK ' if ok else 'BAD'} README row text: {snippet}")
cav = [c for c in T["caveats"] if "oversized" in c]
print("11 caveat:", cav[0] if cav else None)
over = V[(V.measure == "g1:calibrated") & (V.role == "robustness") & (V.estimate > 0.063) & (V.statistic != "date_cluster_t")]
print("11 rows above 6.30% in the G1 table:", sorted(f"{a} {b} {c:.4f}" for a, b, c in zip(over.hypothesis, over.statistic, over.estimate)))
named = set(re.findall(r"(H\d) (\w+) ", cav[0])) if cav else set()
print("11 rows above the band not named in the caveat:", sorted({(a, b) for a, b in zip(over.hypothesis, over.statistic)} - named))
print(f"SUMMARY {sum(checks)} of {len(checks)} numbers equal")
