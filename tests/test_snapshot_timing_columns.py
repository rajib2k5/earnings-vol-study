"""tools/snapshot_timing_columns.py: the H5-H7 columns of the snapshot-timing check (preregistration.md §11).

The oracle is metamorphic: dropping a set of events through the column the tool uses must give the same fit as
dropping the same events through another column of the same model (the outcome, or E for H7), and a fit on the
events that remain. Hand mutants, each caught by a test here (2026-11-18, 5 of 5): `without` drops ~drop; `without`
writes into the caller's Frame; `without` returns the Frame unchanged; `reproduces` ignores the estimate; H7's p tests
b = 0.
"""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from test_stats_wiring import DP, synthetic_frame

from earnings_vol.stats import drivers, regression

W = tuple(DP["surprise_winsor"])
SPEC = importlib.util.spec_from_file_location(
    "snapshot_timing_columns", Path(__file__).resolve().parents[1] / "tools/snapshot_timing_columns.py")
stc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stc)


@pytest.fixture(scope="module")
def frame():
    return synthetic_frame()


def drop_mask(f, every: int = 4) -> np.ndarray:
    d = np.zeros(len(f.ev), bool)
    d[::every] = True
    return d


def test_without_sets_only_the_dropped_rows_missing_and_leaves_the_frame_alone(frame):
    before = frame.ev["abs_surprise_scaled_w"].to_numpy(float).copy()
    d = drop_mask(frame)
    f2 = stc.without(frame, d, "abs_surprise_scaled_w")
    v = f2.ev["abs_surprise_scaled_w"].to_numpy(float)
    assert np.isnan(v[d]).all()
    assert v[~d] == pytest.approx(before[~d])
    assert frame.ev["abs_surprise_scaled_w"].to_numpy(float) == pytest.approx(before)   # the caller's Frame
    with pytest.raises(ValueError, match="shape"):
        stc.without(frame, d[:-1], "abs_surprise_scaled_w")


def test_a_crush_column_is_the_primary_model_refit_on_the_events_that_remain(frame):
    d = drop_mask(frame)
    got = stc.crush_cells(stc.without(frame, d, stc.DROP_VIA["crush"]), W)
    # The same events dropped through the outcome instead of the regressor: the same model, the same fit.
    via_y = stc.crush_cells(stc.without(frame, d, "crush_cboe"), W)
    full = stc.crush_cells(frame, W)
    for h in ("H5", "H6"):
        assert got[h]["n"] == full[h]["n"] - int(d.sum())
        for k in ("estimate", "se", "ci_lo", "ci_hi", "p"):
            assert got[h][k] == pytest.approx(via_y[h][k], abs=1e-12)
        assert got[h]["estimate"] != pytest.approx(full[h]["estimate"], abs=1e-9)
    # ... and the regressors are re-standardised on the remaining events.
    m = drivers.model_inputs(stc.without(frame, d, stc.DROP_VIA["crush"]), drivers.PRIMARY, W)
    assert m["X"][:, 1].std(ddof=1) == pytest.approx(1.0)
    assert not np.isin(np.flatnonzero(d), m["rows"]).any()


def test_an_h7_column_drops_its_events_and_tests_b_against_1(frame):
    d = drop_mask(frame, 3)
    got = stc.h7_cell(stc.without(frame, d, stc.DROP_VIA["h7"]))
    via_e = stc.h7_cell(stc.without(frame, d, "evar_m1"))
    for k in ("estimate", "se", "ci_lo", "ci_hi", "p", "wald_F", "wald_p"):
        assert got[k] == pytest.approx(via_e[k], abs=1e-12)
    m = drivers.h7_inputs(stc.without(frame, d, stc.DROP_VIA["h7"]))
    fit, cov = drivers.fit_model(m, True)
    t = regression.coef_test(fit, cov, 1)
    assert got["n"] == m["rows"].size
    assert got["estimate"] == pytest.approx(t["estimate"], abs=1e-6)
    from scipy import stats
    assert got["p"] == pytest.approx(2 * stats.t.sf(abs((t["estimate"] - 1) / t["se"]), t["df"]), abs=1e-6)


def test_reproduces_names_every_field_that_differs():
    pub = {"H5": pd.Series({"estimate": 0.0135, "se": 0.0049, "ci_lo": 0.0037, "ci_hi": 0.0233, "n": 349})}
    same = {"H5": {"estimate": 0.0135, "se": 0.0049, "ci_lo": 0.0037, "ci_hi": 0.0233, "n": 349}}
    assert stc.reproduces(same, pub) == []
    off = {"H5": dict(same["H5"], estimate=0.0136, n=348)}
    bad = stc.reproduces(off, pub)
    assert len(bad) == 2 and bad[0].startswith("H5 estimate") and bad[1].startswith("H5 n")
