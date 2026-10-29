# The ramp identity of ADR 0005 §1 ("Exactness, and gaps"): ALIV_t equals the weighted sum of
# span changes from min B to t, weight n(o_k)/|B| on the change into usable session o_k, where
# n(o) counts the baseline sessions before o. panel/abnormal.py's span_changes() builds the
# walk; ALIV comes straight from the levels (abnormal.aliv). They must agree to 1e-12 on every
# case the ADR lists.
#
# Mutations this module must catch (applied by hand, each seen to fail; the ADR's three):
#   - one-session changes across a gap (a change into o_k from o_k - 1, which may be missing)
#   - the weight n/(|B| - 1) instead of n/|B|
#   - a walk that starts after min B (the change out of min B dropped)
#   - (one more) n counting the baseline sessions up to and including o_k
#
# Added after the milestone-3 review (each seen to fail on a scratch copy, file restored and its
# SHA-256 checked; [p08 Mxx] = the review's probe docs/validation/probes/m3/p08_mutants.py,
# [fix] = the fix round's script, milestone page §9):
#   - the span weight read at the span's start instead of its end [p08 M06]

import numpy as np
import pytest

from earnings_vol.panel import abnormal

W = 40   # columns 0 .. 39; the target is column 35 in every case


def check(in_b: np.ndarray, usable: np.ndarray, target: int, beta: float, seed: int) -> float:
    rng = np.random.default_rng(seed)
    x = np.cumsum(rng.normal(0, 0.03, W))
    m = np.cumsum(rng.normal(0, 0.07, W))
    x = np.where(usable, x, np.nan)
    al, _ = abnormal.aliv(x[None], m[None], in_b[None], np.array([beta]))
    walk = abnormal.span_changes(in_b, usable, target)
    return abs(abnormal.span_value(walk, x, m, beta) - al[0, target])


def case(baseline: range, unobserved=(), zone=()) -> tuple[np.ndarray, np.ndarray]:
    usable = np.ones(W, bool)
    usable[list(unobserved)] = False
    in_b = np.zeros(W, bool)
    in_b[[t for t in baseline if usable[t] and t not in zone]] = True
    return in_b, usable


CASES = {
    # B = 0..20 with an excluded zone 8..11 inside it (a hole: observed, not in B)
    "hole": case(range(0, 21), zone=range(8, 12)),
    # three unobserved sessions inside (min B, t]: two in the baseline, one after it
    "three_unobserved": case(range(0, 21), unobserved=(5, 13, 28)),
    # Mon/Wed/Fri: only every 5-day week's sessions 0, 2, 4 observed
    "mon_wed_fri": case(range(0, 21), unobserved=[t for t in range(W) if t % 5 in (1, 3) and t != 35]),
    # an unobserved session at t - 1
    "missing_t_minus_1": case(range(0, 21), unobserved=(34,)),
    # a gap at min B + 1 (second review)
    "gap_after_min_b": case(range(0, 21), unobserved=(1,)),
    # an unobserved session inside an excluded zone (second review)
    "unobserved_in_zone": case(range(0, 21), unobserved=(9,), zone=range(8, 12)),
}


@pytest.mark.parametrize("name", sorted(CASES))
@pytest.mark.parametrize("beta", [0.0, 0.4])
def test_span_sum_equals_aliv(name, beta):
    in_b, usable = CASES[name]
    for seed in range(5):
        assert check(in_b, usable, 35, beta, seed) < 1e-12, (name, seed)


def test_the_three_mutants_are_far_from_the_tolerance():
    # The review measured 4.0e-4 to 2.1e-2 for the three mutants of the header, so a 1e-12
    # tolerance can tell them apart. Measured here on the hole and gap cases, each mutant
    # computed by hand from the same data: every one is off by more than 1e-6.
    rng = np.random.default_rng(3)
    x = np.cumsum(rng.normal(0, 0.03, W))
    for name in ("hole", "three_unobserved", "missing_t_minus_1"):
        in_b, usable = CASES[name]
        xx = np.where(usable, x, np.nan)
        truth = xx[35] - xx[in_b].mean()
        b = np.flatnonzero(in_b)
        n_before = np.cumsum(in_b) - in_b
        walk = [c for c in range(b[0], 36) if usable[c]]
        # weight n/(|B| - 1)
        wrong_w = sum(n_before[walk[k]] / (b.size - 1) * (xx[walk[k]] - xx[walk[k - 1]]) for k in range(1, len(walk)))
        # walk from the first usable session after min B
        late = sum(n_before[walk[k]] / b.size * (xx[walk[k]] - xx[walk[k - 1]]) for k in range(2, len(walk)))
        assert abs(wrong_w - truth) > 1e-6 and abs(late - truth) > 1e-6, name
    # one-session changes across a gap cannot even be formed: the change into session 35
    # from 34 is NaN when 34 is missing.
    in_b, usable = CASES["missing_t_minus_1"]
    assert np.isnan(np.where(usable, x, np.nan)[35] - np.where(usable, x, np.nan)[34])


def test_header_worked_example():
    # abnormal.py header: B = {0, 1, 3}, usable {0, 1, 3, 4, 6}, t = 6 (2 and 5 unobserved).
    # Changes 0->1 (n = 1), 1->3 (n = 2), 3->4 (n = 3), 4->6 (n = 3) over |B| = 3:
    # weights 1/3, 2/3, 1, 1. With x = 0, 1, ., 4, 2, ., 5:
    #   1/3 * 1 + 2/3 * 3 + 1 * (-2) + 1 * 3 = 10/3 = 5 - mean(0, 1, 4) = 5 - 5/3.
    in_b = np.array([1, 1, 0, 1, 0, 0, 0], bool)
    usable = np.array([1, 1, 0, 1, 1, 0, 1], bool)
    walk = abnormal.span_changes(in_b, usable, 6)
    assert [(s, e) for s, e, _ in walk] == [(0, 1), (1, 3), (3, 4), (4, 6)]
    assert [w for _, _, w in walk] == pytest.approx([1 / 3, 2 / 3, 1, 1])
    x = np.array([0, 1, np.nan, 4, 2, np.nan, 5], float)
    assert abnormal.span_value(walk, x, np.zeros(7), 0.0) == pytest.approx(10 / 3, abs=1e-12)
    # On the one-session grid a span change puts its weight on every column it spans:
    # 1->3 on columns 2 and 3, 4->6 on 5 and 6.
    assert abnormal.grid_weights(walk, 7).tolist() == pytest.approx([0, 1 / 3, 2 / 3, 2 / 3, 1, 1, 1])


def test_a_zone_session_inside_the_walk_keeps_the_weight_of_the_gap():
    # The same, but session 2 observed and in another event's zone (usable, not in B). The walk
    # now passes through it: 1->2 and 2->3, both with n = 2, so x_2 cancels:
    # 2/3 (x_2 - 1) + 2/3 (4 - x_2) = 2/3 * 3, whatever x_2 is (here 7).
    in_b = np.array([1, 1, 0, 1, 0, 0, 0], bool)
    usable = np.array([1, 1, 1, 1, 1, 0, 1], bool)
    walk = abnormal.span_changes(in_b, usable, 6)
    assert [(s, e) for s, e, _ in walk] == [(0, 1), (1, 2), (2, 3), (3, 4), (4, 6)]
    x = np.array([0, 1, 7, 4, 2, np.nan, 5], float)
    assert abnormal.span_value(walk, x, np.zeros(7), 0.0) == pytest.approx(10 / 3, abs=1e-12)
