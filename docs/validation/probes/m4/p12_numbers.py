"""p12 (claim 12): numbers printed in docs/milestones/04-drivers.md §6 and README vs data/derived/results.parquet and
the stage G1 report. A printed number matches when it equals the data rounded to the printed precision (half-up
and half-even both accepted). Run: uv run --frozen --no-sync python docs/validation/probes/m4/p12_numbers.py"""
import json
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal

import pandas as pd

from earnings_vol import params
from earnings_vol.events.run import stage_dir

r = pd.read_parquet("data/derived/results.parquet")
g1 = json.loads((stage_dir(params.load()) / "g1_report.json").read_text())
rows = []


def get(model, term, stat="twoway_date_t", sample="daily", adj="market", role=None, col="estimate"):
    x = r[(r["model_id"] == model) & (r["term"] == term) & (r["statistic"] == stat) & (r["sample"] == sample)
          & (r["adjustment"] == adj)]
    if role:
        x = x[x["role"] == role]
    assert len(x) == 1, (model, term, stat, sample, adj, role, len(x))
    return float(x[col].iloc[0])


def check(label, printed: str, value: float, scale=1.0):
    s = printed.replace("−", "-").replace("+", "")
    mant = s.split("e")[0]
    dp = len(mant.split(".")[1]) if "." in mant else 0
    v = value * scale
    if "e" in s:
        exp = int(s.split("e")[1])
        q = Decimal(repr(v / 10 ** exp))
        ok = any(str(q.quantize(Decimal(10) ** -dp, rounding=m)) == mant for m in (ROUND_HALF_UP, ROUND_HALF_EVEN))
    else:
        q = Decimal(repr(v))
        ok = any(float(q.quantize(Decimal(10) ** -dp, rounding=m)) == float(s) for m in (ROUND_HALF_UP, ROUND_HALF_EVEN))
    rows.append(ok)
    print(f"{'ok  ' if ok else 'MISS'} {label}: printed {printed}, data {value:.6g}")


P = "crush_drivers"
check("H5 estimate", "+0.0132", get(P, "abs_surprise", role="exploratory"))
check("H5 se", "0.0050", get(P, "abs_surprise", role="exploratory", col="se"))
check("H5 t", "2.67", get(P, "abs_surprise", role="exploratory", col="stat"))
check("H5 p", "0.0102", get(P, "abs_surprise", role="exploratory", col="p_value"))
check("H5 CI lo", "0.0033", get(P, "abs_surprise", role="exploratory", col="ci_lo"))
check("H5 CI hi", "0.0232", get(P, "abs_surprise", role="exploratory", col="ci_hi"))
check("H5 one-way se", "0.0040", get(P, "abs_surprise", "cluster_date_t", col="se"))
check("H5 one-way t", "3.32", get(P, "abs_surprise", "cluster_date_t", col="stat"))
check("H5 twin estimate", "+0.0121", get(P, "abs_surprise", adj="mean"))
check("H6 estimate", "-0.0014", get(P, "ln_sigma_d", role="exploratory"))
check("H6 se", "0.0108", get(P, "ln_sigma_d", role="exploratory", col="se"))
check("H6 p", "0.895", get(P, "ln_sigma_d", role="exploratory", col="p_value"))
check("H6 twin t", "-0.39", get(P, "ln_sigma_d", adj="mean", col="stat"))
sl = r[(r["model_id"] == P) & (r["term"] == "slope") & (r["sample"] == "daily")]
check("SLOPE estimate (README -0.032)", "-0.032", float(sl["estimate"].iloc[0]))
check("SLOPE estimate (§6.3 -0.0317)", "-0.0317", float(sl["estimate"].iloc[0]))
check("SLOPE t", "-4.52", float(sl["stat"].iloc[0]))
check("SLOPE p", "3.9e-5", float(sl["p_value"].iloc[0]))
check("SLOPE BH q", "0.0007", float(sl["q_bh"].iloc[0]))
check("SIZE estimate", "+0.0129", get(P, "size"))
check("SIZE q", "0.18", get(P, "size", col="q_bh"))
check("R2 primary", "0.427", float(r[(r["model_id"] == P) & (r["statistic"] == "r2") & (r["sample"] == "daily")]["estimate"].iloc[0]))
check("cm30 variant surprise", "+0.0139", get("crush_prior_cm30", "abs_surprise"))
check("cm30 variant surprise q", "0.034", get("crush_prior_cm30", "abs_surprise", col="q_bh"))
check("cm30 variant ln cm30", "-0.0077", get("crush_prior_cm30", "ln_cm30"))
check("SUE variant", "+0.0021", get("crush_sue", "abs_sue"))
check("SUE variant q", "0.76", get("crush_sue", "abs_sue", col="q_bh"))
check("SUE n", "339", get("crush_sue", "abs_sue", col="n"))
check("disp variant", "+0.0029", get("crush_disp", "abs_disp"))
check("disp n", "344", get("crush_disp", "abs_disp", col="n"))
check("firm FE surprise", "+0.0076", get("crush_firm_fe", "abs_surprise"))
check("firm FE ln sigma_d q", "0.071", get("crush_firm_fe", "ln_sigma_d", col="q_bh"))
check("firm FE size", "+0.0507", get("crush_firm_fe", "size"))
check("VIX x mid", "+0.0029", get("crush_vix", "abs_surprise_x_mid"))
check("VIX x high", "-0.0010", get("crush_vix", "abs_surprise_x_high"))
check("VIX size q", "0.019", get("crush_vix", "size", col="q_bh"))
check("DSIGMA_D slope", "+0.0813", get("dsigma_d_drivers", "slope"))
check("DSIGMA_D slope t", "8.15", get("dsigma_d_drivers", "slope", col="stat"))
check("DSIGMA_D slope q", "7.6e-9", get("dsigma_d_drivers", "slope", col="q_bh"))
check("DSIGMA_D n", "262", get("dsigma_d_drivers", "slope", col="n"))
check("coarse slope", "-0.0848", get(P, "slope", sample="coarse"))
check("coarse slope q", "2.6e-6", get(P, "slope", sample="coarse", col="q_bh"))
check("coarse n", "110", get(P, "slope", sample="coarse", col="n"))
check("coarse dates", "81", get(P, "slope", sample="coarse", col="n_clusters"))
check("H7 b CI hi", "1.069", get("implied_realised", "b", adj="none", col="ci_hi"))
check("H7 a", "0.00083", get("implied_realised", "a", adj="none"))
check("H7 m2 b", "0.922", get("implied_realised_m2", "b", adj="none"))
check("H7 m2 F", "0.20", get("implied_realised_m2", "a=0,b=1", "twoway_date_wald", adj="none", col="stat"))
check("H7 m2 p", "0.822", get("implied_realised_m2", "a=0,b=1", "twoway_date_wald", adj="none", col="p_value"))
c7 = g1["calibration_h7"]
check("H7 calibration kurtosis", "5.62", c7["measured"]["kurtosis"])
check("H7 calibration nu", "6.29", c7["params"]["nu"])
check("H7 calibration same-date raw", "-0.056", c7["measured"]["rho_d_raw"])
check("H6 power at 0.05", "94.0", g1["power"]["H6"]["power"][3], 100)
check("H5 80% power at", "0.026", g1["power"]["H5"]["detectable_80"])
check("H6 80% power at", "0.042", g1["power"]["H6"]["detectable_80"])
check("D4 H6 rate", "6.30", g1["rates"]["D4"]["H6"]["twoway_date_t"], 100)
check("H7 one-way rate", "17.00", g1["rates"]["calibrated"]["H7"]["cluster_date_wald"], 100)
fam = r["family"].value_counts().to_dict()
print("rows", len(r), fam, "(printed: 929; event_test 45, regression 62, descriptive 133, validation 689)")
rows.append(len(r) == 929 and fam == {"validation": 689, "descriptive": 133, "regression": 62, "event_test": 45})
ex = r[(r["family"] == "regression") & (r["role"] == "exploratory") & r["p_value"].notna()]
print("exploratory regression tests with a p:", ex.groupby("sample").size().to_dict(), "(printed: 42 daily, 4 coarse)")
rows.append(ex.groupby("sample").size().to_dict() == {"daily": 42, "coarse": 4})
print(f"MATCH {sum(rows)} of {len(rows)}")
