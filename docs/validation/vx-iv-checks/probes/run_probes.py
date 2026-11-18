# =============================================================================
# run_probes.py - The falsifier probes of the vx-iv-checks pre-registration,
# on SYNTHETIC data only. Each rule must give its expected verdict on its
# world with no fault and must flag its planted fault.
#
# Run (from anywhere; -I is safe because this file puts the clone first):
#   ~/dev/earnings-vol-study/.venv/bin/python -I \
#       docs/validation/vx-iv-checks/probes/run_probes.py --out DIR [--seed N]
# DIR must be outside docs/validation/vx-iv-checks: this script never writes
# into the frozen folder. It writes DIR/run_probes.seedN.out (the printed
# report; its last line "elapsed: ..." is the only line that varies between
# runs) and DIR/run_probes.seedN.json (every result, no timing). The frozen
# copies in this folder were made by copying those files by hand; gate G2
# reruns into a scratch folder and compares (phase2.py).
#
# WHY THE PATH CODE BELOW
#   `python -I` ignores PYTHONPATH, so `PYTHONPATH=<clone>/src python -I`
#   imports the venv's editable install: the LIVE checkout, not this clone.
#   Measured on 2026-11-17: earnings_vol.__file__ was
#   ~/dev/earnings-vol-study/src/earnings_vol/__init__.py under that command.
#   This file inserts the clone's src first and stops if the import comes
#   from anywhere else.
#
# Exit status 0: every probe and every check gave its expected result.
# 1: at least one did not.
# =============================================================================

import argparse
import json
import os
import pathlib
import sys
import time

for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = "1"                      # one BLAS thread: the same sums in the same order, every run

HERE = pathlib.Path(__file__).resolve().parent
CLONE = HERE.parents[3]
sys.path[:0] = [str(CLONE / "src"), str(HERE)]

import earnings_vol  # noqa: E402

if not pathlib.Path(earnings_vol.__file__).resolve().is_relative_to(CLONE / "src"):
    sys.exit(f"earnings_vol imported from {earnings_vol.__file__}, not from {CLONE / 'src'}")

from contextlib import nullcontext  # noqa: E402
from dataclasses import replace  # noqa: E402

import exchange_calendars as xcals  # noqa: E402
import numpy as np  # noqa: E402
import yaml  # noqa: E402

import ivchecks  # noqa: E402
import mutants  # noqa: E402
import ref_spec  # noqa: E402
import synth  # noqa: E402
import worlds  # noqa: E402
from earnings_vol.measures import chain, termstructure  # noqa: E402

PARAMS = yaml.safe_load((CLONE / "params.yaml").read_text())
P = chain.AtomParams.from_params(PARAMS["iv"])
TP = termstructure.TermParams.from_params(PARAMS["iv"])
REF_P = ref_spec.load_params(CLONE / "params.yaml")
XNYS = [d.date() for d in xcals.get_calendar("XNYS", start="2024-01-01", end="2027-12-31").sessions]
COMMON_SD = 10e-4                             # the planted common forward error: 10 bp a session

# Every world draws its random numbers from streams keyed by (seed, purpose, session, expiry, strike)
# (synth._rng): a planted world and its control have the same market path and the same quote noise,
# so 1 - var(control changes) / var(planted changes) on the same observations is an independent
# measure (the "oracle") of the share that the planted fault adds.

# (run id, world, code mutant, parameter drift for the package, rules to run, what is planted)
# rules: "a" = rule (a), "t" = synthetic truth, "c" = the common-mode descriptive.
RUNS = [
    ("clean", "clean", None, None, "atc",
     "nothing (2.5 grid at spot 200, 5% of strikes and 2% of legs unlisted at random; BMO and AMC events)"),
    ("fwd3", "clean", None, {"forward_strikes": 3}, "a", "params drift: forward from 3 strikes, params.yaml says 4"),
    ("minmid", "clean", None, {"min_mid": 0.10}, "a", "params drift: quote filter min mid 0.10, params.yaml says 0.05"),
    ("bracket", "clean", None, {"bracket_max_sd": 0.1}, "a",
     "params drift: bracket width limit 0.1 sd (as if 1.5 w were compared, not 1.5 sqrt(w))"),
    ("wrongpair", "clean", lambda s: mutants.interp_wrong_pair(), None, "a",
     "code: interpolate takes the shortest expiry <= 21"),
    ("fwdrev", "clean", lambda s: mutants.fwd_reversed(), None, "", "code: forward from the 4 LARGEST |C - P|"),
    ("fwdrev1", "clean", lambda s: mutants.fwd_reversed_one(), None, "", "code: forward from the 1 LARGEST |C - P|"),
    ("tau1", "clean", lambda s: mutants.tau_plus_one(), None, "t", "code: tau counts the snapshot session"),
    ("spans0", "clean", lambda s: mutants.spans_from_day0(), None, "at",
     "code: an expiry spans only from day 0 on (an AMC announcement-day expiry becomes clean)"),
    ("fwdcommon", "clean", lambda s: mutants.fwd_common(COMMON_SD, s), None, "c",
     "code: a forward error of 10 bp common to every expiry of a session"),
    ("lowvol", "lowvol", None, None, "c", "nothing (control: vol 15%, 5 grid at spot 200 = 2.5%, no random unlisting)"),
    ("lowvol_drop", "lowvol_drop", None, None, "",
     "data: the 2 strikes nearest F unlisted on 50% of (session, expiry), lowvol world"),
    ("lowvol_filt", "lowvol_filter", None, None, "",
     "data: the OTM legs of the 2 strikes nearest F fail the quote filter on 50% of (session, expiry), lowvol world"),
    ("flat", "flat", None, None, "", "nothing (control: lowvol world with no smile)"),
    ("flat_filt", "flat_filter", None, None, "",
     "data: the OTM leg of the strike nearest F fails the filter on 25% of (session, expiry), no smile: switches "
     "that add almost nothing"),
    ("sess_filt", "session_filter", None, None, "",
     "data: the OTM legs of the 2 strikes nearest F fail the filter on 15% of SESSIONS, every expiry at once"),
    ("sess_drop", "session_drop", None, None, "",
     "data: the 2 strikes nearest F unlisted on 12% of SESSIONS, every expiry at once"),
    ("ts_slope", "ts_slope", None, None, "", "data: diffusive vol term structure (tau/21)^-0.4, not flat"),
    ("ts_mild", "ts_slope_mild", None, None, "", "data: diffusive vol term structure (tau/21)^-0.25 (power note)"),
    ("mbump", "monthly_bump", None, None, "", "data: monthly expiries 1.5 vol points above the weeklies"),
    ("twoshort", "clean", lambda s: mutants.interp_two_shortest(), None, "a",
     "code: interpolate through the two shortest expiries"),
    ("fixedgrid", "fixed_grid", None, None, "", "nothing (no strike is ever listed or unlisted)"),
]

# (probe id, rule, run id, result key, expected). Null probes (no fault) must clear on every seed.
PROBES = [
    ("P01", "(a) differential", "clean", "diff", "MATCH"),
    ("P02", "(a) differential", "fwd3", "diff", "MISMATCH"),
    ("P03", "(a) differential", "minmid", "diff", "MISMATCH"),
    ("P04", "(a) differential", "bracket", "diff", "MISMATCH"),
    ("P05", "(a) differential", "wrongpair", "diff", "MISMATCH"),
    ("P06", "(b) forward vs close", "clean", "yahoo", "NO FAULT"),
    ("P07", "(b) forward vs close", "fwdrev1", "yahoo", "FAULT"),
    ("P08", "(b) synthetic truth", "clean", "truth", "NO FAULT"),
    ("P09", "(b) synthetic truth", "tau1", "truth", "FAULT"),
    ("P10", "(c) forward share", "clean", "forward", "NO FAULT"),
    ("P11", "(c) forward share", "fwdrev", "forward", "FAULT"),
    ("P12", "(c) filter share", "flat_filt", "filter", "NO FAULT"),
    ("P13", "(c) filter share", "lowvol_filt", "filter", "FAULT"),
    ("P14", "(c) strike share", "lowvol", "strike", "NO FAULT"),
    ("P15", "(c) strike share", "lowvol_drop", "strike", "FAULT"),
    ("P16", "(c) roll share cm30_iv", "clean", "roll_iv", "NO FAULT"),
    # P17 must not clear its fault: its share comes from ~4 changes where the method switches from
    # two_component to interp_spanning near an event (preregistration.md §9).
    ("P17", "(c) roll share cm30_iv", "ts_slope", "roll_iv", "NOT NO FAULT"),
    ("P18", "(c) roll share cm30_iv", "mbump", "roll_iv", "FAULT"),
    # P19, P20: a fault on every expiry of a session leaves no clean reference; the any-reference guard
    # must stop a NO FAULT (preregistration.md §6, review finding 6).
    ("P19", "(c) filter share", "sess_filt", "filter", "NOT NO FAULT"),
    ("P20", "(c) strike share", "sess_drop", "strike", "NOT NO FAULT"),
    ("P21", "(b) synthetic truth", "spans0", "truth", "FAULT"),
    ("P22", "(a) differential", "spans0", "diff", "MISMATCH"),
]
NULLS = ("P01", "P06", "P08", "P10", "P12", "P14", "P16")

# (probe, planted run, control run, observations, condition on the oracle or None)
ORACLES = [
    ("P11", "fwdrev", "clean", "_y_fixed", None),
    ("P12", "flat_filt", "flat", "_y_strike", "< 0.05"),
    ("P13", "lowvol_filt", "lowvol", "_y_strike", None),
    ("P15", "lowvol_drop", "lowvol", "_y_strike", None),
    ("P17", "ts_slope", "clean", "_y_roll_iv", None),
    ("P18", "mbump", "clean", "_y_roll_iv", None),
    ("P19", "sess_filt", "lowvol", "_y_strike", ">= 0.10"),
    ("P20", "sess_drop", "lowvol", "_y_strike", ">= 0.10"),
]


def oracle(planted: dict, control: dict) -> tuple:
    keys = sorted(set(planted) & set(control))
    yp = [planted[k] for k in keys]
    yc = [control[k] for k in keys]
    return 1.0 - float(np.var(yc, ddof=1) / np.var(yp, ddof=1)), len(keys)


def _iv(r):
    return f"{r['share']:+.3f} [{r['lo']:+.3f}, {r['hi']:+.3f}]"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=pathlib.Path)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    out_dir = a.out.resolve()
    if out_dir.is_relative_to(HERE.parent):
        sys.exit(f"--out {out_dir} is inside the frozen folder {HERE.parent}; write elsewhere")
    out_dir.mkdir(parents=True, exist_ok=True)
    seed = a.seed
    t0 = time.monotonic()
    lines = []

    def say(s=""):
        lines.append(s)
        print(s, flush=True)

    counts = ivchecks.block_counts(worlds.spec("clean", seed).n_sessions)
    panels = {w: synth.make_panel(worlds.spec(w, seed)) for w in sorted({r[1] for r in RUNS})}
    results = {}
    for rid, world, mut, drift, rules, what in RUNS:
        p = replace(P, **drift) if drift else P
        with (mut(seed) if mut else nullcontext()):
            results[rid] = ivchecks.run_name(panels[world], p, TP, REF_P, XNYS, counts, with_truth="t" in rules,
                                             with_diff="a" in rules, with_common="c" in rules)
        results[rid]["planted"] = what

    ok_all = True
    say(f"seed {seed}; INFLATE {ivchecks.INFLATE}")
    say(f"{'probe':5} {'rule':24} {'run':11} {'expected':12} {'got':40} result  detail")
    for pid, rule, rid, key, expected in PROBES:
        r = results[rid][key]
        got = r["verdict"]
        good = ivchecks._head(got) != "NO FAULT" if expected == "NOT NO FAULT" else got == expected
        ok_all &= good
        if key == "diff":
            detail = (f"untagged {r['untagged']}, unspecified {r['unspecified']}, fields {r['mismatches'] or 0}, "
                      f"tags {r['tags'] or 0}, accepted {r['accepted_alternatives'] or 0}; n {r['n']}")
        elif key == "yahoo":
            detail = f"median |d| {r['median_abs_bp']:.2f} bp [{r['lo']:.2f}, {r['hi']:.2f}] n {r['n']}"
        elif key == "truth":
            detail = "worst |error| " + ", ".join(f"{k} {v:.1e}" for k, v in r["worst"].items()) + f"; n {r['n']}"
        else:
            detail = f"share {_iv(r)} n {r['n']}"
            if key == "forward":
                detail += f" dropped {r['dropped']} sigma_f {r['sigma_f_bp']:.2f} bp"
            else:
                detail += f" group {r['n_group']} base {r['n_base']}"
                if "any_ref" in r:
                    x = r["any_ref"]
                    detail += f"; any-ref {_iv(x)} n {x['n']} group {x['n_group']} base {x['n_base']} {x['verdict']}"
        say(f"{pid:5} {rule:24} {rid:11} {expected:12} {got:40} {'ok' if good else 'WRONG':6}  {detail}")
    say(f"null probes {', '.join(NULLS)}: all clear: "
        f"{all(results[r][k]['verdict'] in ('MATCH', 'NO FAULT') for p_, _, r, k, _ in PROBES if p_ in NULLS)}")

    say()
    say("Oracle share of each planted (c) fault: 1 - var(control changes)/var(planted changes), same observations")
    for pid, rp, rc, key, cond in ORACLES:
        o, n = oracle(results[rp][key], results[rc][key])
        good = True if cond is None else (o < 0.05 if cond == "< 0.05" else o >= 0.10)
        ok_all &= good
        say(f"  {pid} {rp:11} vs {rc:7}: oracle {o:+.3f} (n {n})" +
            (f"  must be {cond}: {'ok' if good else 'WRONG'}" if cond else ""))

    say()
    m1 = results["fixedgrid"]["listing"]["n_group"] == 0
    say(f"M1 no strike is ever unlisted -> no 'listing' switch: {'ok' if m1 else 'WRONG'} "
        f"({results['fixedgrid']['listing']['n_group']} listing switches)")
    f12 = results["flat_filt"]["filter"]
    nv = min(f12["n_group"], f12["any_ref"]["n_group"]) >= ivchecks.MIN_GROUP
    say(f"P12 is not vacuous: filter switches, clean {f12['n_group']}, any {f12['any_ref']['n_group']} "
        f">= {ivchecks.MIN_GROUP}: {'ok' if nv else 'WRONG'}")
    ok_all &= m1 and nv

    say()
    say("Every (c) share by run, point [lo, hi] (lo: one-sided Bonferroni 0.05/12; hi: one-sided 95%; both widened\n"
        "by INFLATE); forward, filter, strike and roll_iv are the rules; the rest are descriptive:")
    keys = ("forward", "filter", "strike", "roll_iv", "listing", "other", "roll_blind")
    say(f"{'run':11} " + " ".join(f"{k:>25}" for k in keys))
    for rid in results:
        say(f"{rid:11} " + " ".join(f"{_iv(results[rid][k]):>25}" for k in keys))
    say()
    say("Any-reference versions of filter and strike (the guard of §6):")
    for rid in results:
        say(f"{rid:11} filter {_iv(results[rid]['filter']['any_ref']):>25} {results[rid]['filter']['any_ref']['verdict']:30}"
            f" strike {_iv(results[rid]['strike']['any_ref']):>25} {results[rid]['strike']['any_ref']['verdict']}")
    say()
    say("Descriptive (§11), 30-day level: forward share of cm30_iv and cm30_blind_iv (same draws), -2 rho1 (95%),\n"
        "strike switches seen in cm30_blind_iv, and the blind residual line (sum, joint bootstrap, 95%):")
    keys2 = ("forward_cm30_iv", "forward_cm30_blind_iv", "lag1_cm30_iv", "lag1_cm30_blind_iv", "strike_cm30_blind_iv",
             "blind_sum")
    say(f"{'run':11} " + " ".join(f"{k:>25}" for k in keys2))
    for rid in results:
        cells = [_iv(results[rid][k]) if "lo" in results[rid][k] else "n/a" for k in keys2]
        say(f"{rid:11} " + " ".join(f"{c:>25}" for c in cells))
    say()
    say("Common-mode forward (descriptive, an UPPER BOUND: sigma_c^2 = var(forward-vs-close d)/2):")
    for rid in ("clean", "lowvol", "fwdcommon"):
        r = results[rid]
        say(f"  {rid:10} sigma_c {r['common_forward']['sigma_c_bp']:.2f} bp (sigma_f {r['forward']['sigma_f_bp']:.2f})"
            f": fixed {_iv(r['common_forward'])}, cm30_iv {_iv(r['common_forward_cm30_iv'])}, "
            f"cm30_blind_iv {_iv(r['common_forward_cm30_blind_iv'])}")
    oc = {k: oracle(results["fwdcommon"][k], results["clean"][k])[0] for k in ("_y_fixed", "_y_strike", "_y_blind")}
    fc = results["fwdcommon"]
    say(f"  fwdcommon oracle: fixed {oc['_y_fixed']:+.3f}, strike observations {oc['_y_strike']:+.3f}, "
        f"cm30_blind_iv {oc['_y_blind']:+.3f}; the forward rule reads {_iv(fc['forward'])} {fc['forward']['verdict']}, "
        f"the strike rule {_iv(fc['strike'])} {fc['strike']['verdict']}, forward vs close "
        f"{fc['yahoo']['median_abs_bp']:.2f} bp {fc['yahoo']['verdict']}")
    say()
    for rid in ("clean", "ts_slope", "mbump"):
        r = results[rid]
        say(f"roll, {rid}: switch changes cm30_iv {r['roll_iv']['n_group']} of {r['roll_iv']['n']} "
            f"(excluded {r['roll_iv']['excluded']}), blind {r['roll_blind']['n_group']} of {r['roll_blind']['n']}; "
            f"sample {r['n_changes']} changes, excluded {r['excluded']}")
    say("Power notes (not probes): forward vs close, 4-strike reversed forward: median |d| "
        f"{results['fwdrev']['yahoo']['median_abs_bp']:.2f} bp, verdict {results['fwdrev']['yahoo']['verdict']}; "
        f"its (c) forward share {results['fwdrev']['forward']['share']:.3f} ({results['fwdrev']['forward']['verdict']}). "
        f"Roll, term structure (tau/21)^-0.25: {_iv(results['ts_mild']['roll_iv'])} "
        f"{results['ts_mild']['roll_iv']['verdict']}, oracle "
        f"{oracle(results['ts_mild']['_y_roll_iv'], results['clean']['_y_roll_iv'])[0]:+.3f}. "
        f"Two-shortest mutant: roll_iv {results['twoshort']['roll_iv']['verdict']}, "
        f"(a) {results['twoshort']['diff']['verdict']}.")
    say(f"\nall probes as expected: {ok_all}")
    out = {rid: {k: v for k, v in r.items() if not k.startswith("_")} for rid, r in results.items()}
    (out_dir / f"run_probes.seed{seed}.json").write_text(json.dumps(out, indent=1, default=str, sort_keys=True) + "\n")
    el = f"elapsed: {time.monotonic() - t0:.0f} s"
    print(el)
    (out_dir / f"run_probes.seed{seed}.out").write_text("\n".join(lines + [el]) + "\n")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
