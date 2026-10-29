"""p10: numbers in docs/milestones/03-event-study.md §6, README and DATA.md against the committed
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
chk("H1 est", -0.1991, r.estimate, 5e-5); chk("H1 se", 0.0113, r.se, 5e-5); chk("H1 t", -17.70, r.stat, 5e-3)
chk("H1 df", 49, r.df, 0); chk("H1 p", 6.35e-23, r.p_value, 5e-26); chk("H1 p_holm", 4.44e-22, r.p_holm, 5e-25)
chk("H1 ci_lo", -0.2217, r.ci_lo, 5e-5); chk("H1 ci_hi", -0.1765, r.ci_hi, 5e-5)
chk("H1 n", 347, r.n, 0); chk("H1 G date", 172, r.n_clusters, 0); chk("H1 G firm", 50, r.n_clusters_firm, 0)
r = get("H2", "rad_season_p", role="primary")
chk("H2 est", 0.2314, r.estimate, 5e-5); chk("H2 p", 0.0078, r.p_value, 5e-5); chk("H2 p_holm", 0.0469, r.p_holm, 5e-5)
chk("H2 stat (one-way t)", 17.28, r.stat, 5e-3); chk("H2 G", 8, r.n_clusters, 0); chk("H2 n", 356, r.n, 0)
r = get("H3", "twoway_season_t", role="primary")
chk("H3 est", 0.0089, r.estimate, 5e-5); chk("H3 se", 0.0216, r.se, 5e-5); chk("H3 t", 0.41, r.stat, 5e-3)
chk("H3 p", 0.696, r.p_value, 5e-4); chk("H3 ci_lo", -0.0441, r.ci_lo, 5e-5); chk("H3 ci_hi", 0.0618, r.ci_hi, 5e-5)
r = get("H4", "twoway_date_t", role="primary")
chk("H4 est", 0.0034, r.estimate, 5e-5); chk("H4 se", 0.0114, r.se, 5e-5); chk("H4 p", 0.764, r.p_value, 5e-4)
chk("H4 G date", 134, r.n_clusters, 0); chk("H4 G firm", 47, r.n_clusters_firm, 0)
r = get("H1", "twoway_date_t", adj="mean"); chk("H1 twin est", -0.2009, r.estimate, 5e-5); chk("H1 twin t", -17.65, r.stat, 5e-3)
r = get("H1", "cluster_date_t"); chk("H1 one-way t", -30.88, r.stat, 5e-3); chk("H1 one-way se (6.5)", 0.0064, r.se, 5e-5)
chk("H1 kp_ow_t", -22.0, get("H1", "kp_ow_t").stat, 0.05); chk("H1 kpp_t", -22.6, get("H1", "kpp_t").stat, 0.05)
chk("H1 bmp_t", -29.2, get("H1", "bmp_t").stat, 0.05); chk("H1 patell", -78.5, get("H1", "patell_z").stat, 0.05)
chk("H1 sign share below 0", 0.986, get("H1", "gen_sign_z").estimate, 5e-4)
r = get("H2", "twoway_season_t"); chk("H2 two-way t", 13.82, r.stat, 5e-3); chk("H2 two-way se (6.5)", 0.0167, r.se, 5e-5)
chk("H2 one-way se (6.5)", 0.0134, get("H2", "cluster_season_t").se, 5e-5)
chk("H3 one-way se (6.5)", 0.0224, get("H3", "cluster_season_t").se, 5e-5)
chk("H2 twin est", 0.2333, get("H2", "rad_season_p", adj="mean").estimate, 5e-5)
r = get("H3", "twoway_season_t", adj="mean"); chk("H3 twin est", 0.0030, r.estimate, 5e-5); chk("H3 twin t", 0.09, r.stat, 5e-3)
x = ev[(ev.subgroup_value == "AMC") & (ev.measure == "crush_cm30")].iloc[0]; chk("AMC crush", -0.230, x.estimate, 5e-4); chk("AMC n", 182, x.n, 0)
x = ev[(ev.subgroup_value == "BMO") & (ev.measure == "crush_cm30")].iloc[0]; chk("BMO crush", -0.165, x.estimate, 5e-4); chk("BMO n", 165, x.n, 0)
x = ev[(ev["sample"] == "coarse") & (ev.measure == "crush_cm30") & (ev.adjustment == "market")].iloc[0]
chk("coarse crush", -0.190, x.estimate, 5e-4); chk("coarse n", 110, x.n, 0)
p = R[(R.family == "descriptive") & (R.adjustment == "market") & (R.subgroup_value == "all")]
for rel, est in ((-10, 0.236), (-1, 0.231), (0, 0.032), (10, 0.008)):
    chk(f"path day {rel}", est, p[p.rel_day == rel].estimate.iloc[0], 5e-4)
pw = {d["hypothesis"]: d for d in T["g1"]["power"]}
for h, v in (("H1", 0.035), ("H2", 0.083), ("H3", 0.107), ("H4", 0.039)):
    chk(f"{h} 80%-power shift", v, pw[h]["detectable_80"], 5e-4)
cal = {c["hypothesis"]: c["rejection_rate"] for c in T["g1"]["calibrated"]}
for h, v in (("H1", 0.046), ("H2", 0.0065), ("H3", 0.0055), ("H4", 0.0475)):
    chk(f"{h} calibrated G1 rate", v, cal[h], 5e-5)
V = R[R.family == "validation"]


def g(design, h, st):
    q = V[(V.measure == f"g1:{design}") & (V.hypothesis == h) & (V.statistic == st)]
    return float(q.estimate.iloc[0])


for st, v in (("cluster_date_t", 0.241), ("bmp_t", 0.261), ("kp_ow_t", 0.157), ("kpp_t", 0.158),
              ("patell_z", 0.690), ("gen_sign_z", 0.209), ("rank_t", 0.388)):
    chk(f"11 calibrated H1 {st}", v, g("calibrated", "H1", st), 6e-4)
chk("stress D2+drift0.0015 H2 rad", 0.080, g("D2+drift0.0015", "H2", "rad_season_p"), 5e-5)
chk("stress common_ar0.9 H1", 0.177, g("D2+common_ar0.9", "H1", "twoway_date_t"), 5e-5)
chk("stress D3 H3", 0.068, g("D3", "H3", "twoway_season_t"), 5e-5)
chk("date-cluster mutant H2", 0.197, g("calibrated", "H2", "date_cluster_t"), 5e-5)
cav = [c for c in T["caveats"] if "oversized" in c]
print("11 caveat:", cav[0] if cav else None)
over = V[(V.measure == "g1:calibrated") & (V.role == "robustness") & (V.estimate > 0.063) & (V.statistic != "date_cluster_t")]
print("11 rows above 6.30% in the G1 table:", sorted(f"{a} {b} {c:.4f}" for a, b, c in zip(over.hypothesis, over.statistic, over.estimate)))
named = set(re.findall(r"(H\d) (\w+) ", cav[0])) if cav else set()
print("11 rows above the band not named in the caveat:", sorted({(a, b) for a, b in zip(over.hypothesis, over.statistic)} - named))
print(f"SUMMARY {sum(checks)} of {len(checks)} numbers equal")
