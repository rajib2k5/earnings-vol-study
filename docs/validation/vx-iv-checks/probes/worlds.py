# =============================================================================
# worlds.py - The synthetic worlds of the falsifier probes (run_probes.py),
# the bootstrap calibration (calib.py) and the phase-2 driver's self-test
# (phase2.py --selftest). One place, so the three cannot drift apart.
# Every world is a synth.SynthSpec; the seed is set by the caller.
# =============================================================================

import synth

# Vol 15%, strikes every 5 at spot 200 (2.5%), no random unlisting: a world where the strike grid matters.
LOWVOL = dict(sigma0=0.15, atm_step=5.0, p_strike_drop=0.0, p_leg_drop=0.0)
# No smile: the ATM w read from any bracket is the same, so a moved bracket adds almost no variance.
FLAT = dict(smile_b=0.0, smile_c=0.0)

SPECS = {
    "clean": {},
    "lowvol": LOWVOL,
    "lowvol_drop": {**LOWVOL, "atm_drop_n": 2, "atm_drop_prob": 0.5},
    "lowvol_filter": {**LOWVOL, "atm_filter_prob": 0.5},
    "flat": {**LOWVOL, **FLAT},
    # Filter switches that add (almost) nothing: the null filter world WITH switches (replaces the old P12).
    "flat_filter": {**LOWVOL, **FLAT, "atm_filter_n": 1, "atm_filter_prob": 0.25},
    # Faults that hit every expiry of a session at once (one draw per session, synth.fault_scope).
    "session_filter": {**LOWVOL, "fault_scope": "session", "atm_filter_prob": 0.15},
    "session_drop": {**LOWVOL, "fault_scope": "session", "atm_drop_n": 2, "atm_drop_prob": 0.12},
    "ts_slope": {"ts_slope": -0.4},
    "ts_slope_mild": {"ts_slope": -0.25},
    "monthly_bump": {"monthly_bump": 0.015},
    "fixed_grid": {"fixed_grid": True, "p_strike_drop": 0.0, "p_leg_drop": 0.0},
}

# The null world of each (c) rule, for calib.py: no planted fault, and switches of the rule's kind.
NULL_OF_RULE = {"forward": "clean", "roll_iv": "clean", "strike": "lowvol", "filter": "flat_filter"}


def spec(name: str, seed: int) -> synth.SynthSpec:
    return synth.SynthSpec(**SPECS[name], seed=seed)
