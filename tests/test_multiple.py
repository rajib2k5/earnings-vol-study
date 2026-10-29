# Tests for stats/multiple.py (ADR 0005 §4): Holm over the declared seven-hypothesis family,
# with untested hypotheses entered as p = 1, and BH q-values.
#
# Mutations this module must catch (applied by hand, each seen to fail):
#   - Holm without the running maximum (step-down monotonicity lost)
#   - Holm multiplying by m - rank + 1 off by one (m - rank)
#   - an untested hypothesis left out of m instead of entering as p = 1
#   - BH without the running minimum from the top
#
# Added after the milestone-3 review (each seen to fail on a scratch copy, file restored and its
# SHA-256 checked; [p08 Mxx] = the review's probe docs/validation/probes/m3/p08_mutants.py,
# [fix] = the fix round's script, milestone page §9):
#   - holm() and bh() accepting a NaN, a negative or a p above 1 [fix]
# Not killable, and argued equivalent [p08 M11]: BH's running minimum starting at +inf instead
# of 1. For p in [0, 1] the top rank sets it to p_(m) <= 1 either way (0 of 100,000 random
# vectors differ), and both functions now refuse anything outside [0, 1].

import numpy as np
import pytest
from statsmodels.stats.multitest import multipletests

from earnings_vol.stats import multiple


def test_holm_hand_worked_with_three_untested():
    # m = 7: H1 0.001, H2 0.02, H3 0.004, H4 0.03, H5-H7 untested (p = 1).
    # Sorted: 0.001 (x7 = 0.007), 0.004 (x6 = 0.024), 0.02 (x5 = 0.1), 0.03 (x4 = 0.12), then
    # 1, 1, 1 (min(1, 3), ...) -> 1. Running max: 0.007, 0.024, 0.1, 0.12, 1, 1, 1.
    got = multiple.holm({"H1": 0.001, "H2": 0.02, "H3": 0.004, "H4": 0.03, "H5": None, "H6": None, "H7": None})
    assert got == pytest.approx({"H1": 0.007, "H2": 0.1, "H3": 0.024, "H4": 0.12, "H5": 1, "H6": 1, "H7": 1})
    # Dropping the untested three (m = 4) would give H1 0.004: smaller, so not a valid bound.
    assert multiple.holm({"H1": 0.001, "H2": 0.02, "H3": 0.004, "H4": 0.03})["H1"] == pytest.approx(0.004)


def test_holm_matches_statsmodels_and_the_adr_floor_example():
    rng = np.random.default_rng(5)
    for _ in range(50):
        p = rng.uniform(0, 0.2, 7)
        ours = multiple.holm({f"H{i}": v for i, v in enumerate(p)})
        assert list(ours.values()) == pytest.approx(multipletests(p, method="holm")[1].tolist(), abs=1e-15)
    # ADR 0005 §2f: rad_season_p's floor 2/128 = 0.015625 passes Holm only after four smaller
    # p-values: with four, its adjusted p is 3 * 0.015625 = 0.046875 (<= 0.05); with three,
    # 4 * 0.015625 = 0.0625.
    four = multiple.holm({"a": 0.001, "b": 0.001, "c": 0.001, "d": 0.001, "r": 2 / 128, "f": 0.9, "g": 0.9})
    three = multiple.holm({"a": 0.001, "b": 0.001, "c": 0.001, "d": 0.9, "r": 2 / 128, "f": 0.9, "g": 0.9})
    assert four["r"] == pytest.approx(0.046875) and three["r"] == pytest.approx(0.0625)


def test_an_untested_hypothesis_at_one_is_an_upper_bound():
    # The adjusted p of H1-H4 never grows when an untested p drops below 1: so the milestone-3
    # Holm p-values are upper bounds of what milestone 4 will compute.
    rng = np.random.default_rng(7)
    for _ in range(200):
        known = rng.uniform(0, 0.1, 4)
        base = multiple.holm({**{f"H{i}": known[i] for i in range(4)}, "H5": None, "H6": None, "H7": None})
        later = multiple.holm({**{f"H{i}": known[i] for i in range(4)},
                               **{f"H{i}": v for i, v in zip((5, 6, 7), rng.uniform(0, 1, 3))}})
        assert all(later[f"H{i}"] <= base[f"H{i}"] + 1e-15 for i in range(4))


def test_bh_hand_worked():
    # m = 4, p = 0.01, 0.04, 0.03, 0.5. Sorted 0.01 (x4/1 = 0.04), 0.03 (x4/2 = 0.06),
    # 0.04 (x4/3 = 0.0533), 0.5 (x4/4 = 0.5); running min from the top: 0.5, 0.0533, 0.0533, 0.04.
    q = multiple.bh([0.01, 0.04, 0.03, 0.5])
    assert q == pytest.approx([0.04, 4 * 0.04 / 3, 4 * 0.04 / 3, 0.5])
    assert q == pytest.approx(multipletests([0.01, 0.04, 0.03, 0.5], method="fdr_bh")[1].tolist())


def test_holm_and_bh_refuse_what_is_not_a_probability():
    # Both caps at 1 rest on p-values in [0, 1]; a NaN, a negative or a p above 1 is a bug upstream.
    for bad in ([0.5, float("nan")], [0.5, -0.01], [0.5, 1.0000001]):
        with pytest.raises(ValueError, match="from 0 to 1"):
            multiple.bh(bad)
        with pytest.raises(ValueError, match="from 0 to 1"):
            multiple.holm(dict(zip("ab", bad)))
    assert multiple.bh([1.0, 0.0]) == [1.0, 0.0] and multiple.holm({"a": None, "b": 1.0}) == {"a": 1.0, "b": 1.0}
