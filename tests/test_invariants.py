# Tests for invariants.py: the results invariant on the reference distribution (data model
# §3.13; ADR 0005 §5, G1's reference-distribution check), and that store.validate runs it on
# every write.
#
# Mutations this module must catch (applied by hand, each seen to fail):
#   - the rule-2 check removed (a normal p-value on a t row, statsmodels' use_t=False, passes)
#   - df checked against max(n_clusters, n_clusters_firm) - 1 for a two-way row
#   - the CI multiplier compared with 1.96 instead of t_{df, 0.975}
#   - a Wald row accepted without its numerator df
#   - schema.RESULTS without its invariant (store.write_table accepts a broken row)
# Added at milestone 4 (H7's Wald rows; each applied to a scratch copy, seen to fail, the file
# restored and its SHA-256 checked):
#   - twoway_date_wald left out of the clustered rows (its df not checked against the clusters)
#   - a Wald row's p checked against the t tail (is_t not excluding Wald rows)
#   - cluster_date_wald treated as two-way (df from min of the cluster counts)

import math

import pytest
from scipy import stats

from earnings_vol import invariants, schema, store
from earnings_vol.stats import results


def good_row(**kw):
    # A two-way date x firm row: n_clusters 3, n_clusters_firm 2 -> df = min(3, 2) - 1 = 1.
    # t = 0.2 / 0.25 = 0.8; p = 1 - 2 atan(0.8)/pi (Cauchy) = 0.570..; CI 0.2 +- tan(0.475 pi) * 0.25.
    q = math.tan(0.475 * math.pi)
    r = dict(family="event_test", hypothesis="H1", role="primary", measure="crush_cm30",
             statistic="twoway_date_t", sample="daily", subgroup_key="all", subgroup_value="all",
             adjustment="market", n=4, n_clusters=3, n_clusters_firm=2, df=1.0, estimate=0.2, se=0.25, stat=0.8,
             p_value=1 - 2 * math.atan(0.8) / math.pi, ci_lo=0.2 - q * 0.25, ci_hi=0.2 + q * 0.25,
             params_hash="h", code_commit="c")
    r.update(kw)
    return results.row(**r)


def test_a_correct_row_passes():
    assert invariants.row_problems(good_row()) == []


@pytest.mark.parametrize("change, message", [
    (dict(p_value=2 * stats.norm.sf(0.8)), "two-sided t_1.0 tail"),                        # use_t=False
    (dict(df=2.0, p_value=2 * stats.t.sf(0.8, 2)), "min(n_clusters, n_clusters_firm) - 1"),
    (dict(ci_lo=0.2 - 1.96 * 0.25, ci_hi=0.2 + 1.96 * 0.25), "t_1.0,0.975"),
    (dict(statistic="cluster_date_t", n_clusters_firm=None), "n_clusters - 1"),        # one-way: df must be 2
])
def test_a_broken_row_names_its_rule(change, message):
    probs = invariants.row_problems(good_row(**change))
    assert probs and any(message in p for p in probs), probs


def test_normal_wald_and_rad_rows():
    z = good_row(statistic="patell_z", df=None, se=None, ci_lo=None, ci_hi=None, n_clusters=None,
                 n_clusters_firm=None, stat=1.5, p_value=2 * stats.norm.sf(1.5))
    assert invariants.row_problems(z) == []
    assert invariants.row_problems(dict(z, p_value=2 * stats.t.sf(1.5, 3)))
    w = good_row(statistic="wald", family="regression", n_clusters=None, n_clusters_firm=None, df=40.0, se=None,
                 ci_lo=None, ci_hi=None, stat=3.0, p_value=stats.f.sf(3.0, 2, 40))
    assert any("numerator df" in p for p in invariants.row_problems(w))
    assert invariants.row_problems(dict(w, df_num=2.0)) == []
    rad = good_row(statistic="rad_season_p", df=None, se=None, ci_lo=None, ci_hi=None, n_clusters=7,
                   n_clusters_firm=None, p_value=0.01)
    assert any("floor" in p for p in invariants.row_problems(rad))          # 0.01 < 2/128
    assert invariants.row_problems(dict(rad, p_value=2 / 128)) == []
    # Validation rows (G1's rates) are not tests and are skipped.
    assert invariants.row_problems(dict(good_row(p_value=0.5), family="validation")) == []


def test_the_writer_refuses_a_results_table_that_breaks_it(tmp_path):
    ok = results.frame([good_row()])
    store.write_table(ok, schema.RESULTS, tmp_path / "r.parquet", params_hash="h", dolt_commits={})
    bad = results.frame([good_row(p_value=2 * stats.norm.sf(0.8))])
    with pytest.raises(store.SchemaError, match="two-sided t_1.0 tail"):
        store.write_table(bad, schema.RESULTS, tmp_path / "r2.parquet", params_hash="h", dolt_commits={})
    with pytest.raises(store.SchemaError):
        store.write_derived(bad, schema.RESULTS, tmp_path)


def wald_row(**kw):
    # H7's two-way Wald: n_clusters 30 (dates), n_clusters_firm 12 -> df = 11; F = 3.0 on (2, 11).
    r = dict(family="regression", hypothesis="H7", role="primary", measure="r0_squared",
             statistic="twoway_date_wald", sample="daily", subgroup_key="all", subgroup_value="all",
             adjustment="none", model_id="implied_realised", term="a=0,b=1", n=100, n_clusters=30,
             n_clusters_firm=12, df=11.0, df_num=2.0, stat=3.0, p_value=stats.f.sf(3.0, 2, 11),
             params_hash="h", code_commit="c")
    r.update(kw)
    return results.row(**r)


def test_wald_rows_of_h7():
    assert invariants.row_problems(wald_row()) == []
    # df from the clusters: 29 is the date count - 1, wrong for a two-way row.
    bad = invariants.row_problems(wald_row(df=29.0, p_value=stats.f.sf(3.0, 2, 29)))
    assert any("min(n_clusters, n_clusters_firm) - 1 = 11" in p for p in bad)
    # A chi-square p (statsmodels' default use_t=False) breaks the F rule.
    assert any("F(2.0, 11.0)" in p for p in invariants.row_problems(wald_row(p_value=stats.chi2.sf(6.0, 2))))
    # The one-way date Wald: df = n_clusters - 1 = 29.
    one = wald_row(statistic="cluster_date_wald", n_clusters_firm=None, df=29.0, p_value=stats.f.sf(3.0, 2, 29))
    assert invariants.row_problems(one) == []
    assert invariants.row_problems(dict(one, df=11.0, p_value=stats.f.sf(3.0, 2, 11)))
    assert any("cluster counts" in p for p in invariants.row_problems(wald_row(n_clusters_firm=None)))
    # A withheld row (no p-value) passes; a regression coefficient row is a clustered t.
    assert invariants.row_problems(wald_row(statistic="cluster_date_wald", n_clusters_firm=None, df=29.0,
                                            p_value=None)) == []
    coef = good_row(family="regression", hypothesis="H5", model_id="crush_drivers", term="abs_surprise")
    assert invariants.row_problems(coef) == []
