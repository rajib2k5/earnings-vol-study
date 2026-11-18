"""Post-run sensitivity of the snapshot-timing check (exploratory; NOT pre-registered; changes no verdict).

    .venv/bin/python -I docs/validation/snapshot-timing/post_run_sensitivity.py   # writes post_run_sensitivity.json

The adversarial pass after the run (ledger §4) raised two points, and this script reproduces them with the check's
own code on the same prepared inputs. It does not touch aggregate.json.

1. The direct plug-in. The check's shifts use the neighbour estimates of the level errors (b0 = -beta_P,
   b-1 = beta_A; plan §9). Block C estimates the same errors directly in the crush rows (b0 = beta_C0,
   b-1 = -beta_C1; plan §7, used only by the identity check of §8). Here the H1 and H4 shifts are recomputed with the
   direct estimates, with the same restricted bootstrap tests at +-line, the same draws and seed.
2. The small-sample factor. The stacked fit has one CR1 factor (n-1)/(n-k), set mostly by block O's rows. Its
   analytic se and t of an event-block combination are therefore smaller than a fit of the event blocks alone would
   give. The bootstrap p and intervals do not depend on that factor; the printed se and t do. Reported: the analytic
   t of each shift at -line, stacked and from a fit of that series' event blocks only.
"""

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

from earnings_vol import store
from earnings_vol.stats import snapshot_timing as stm

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
OUT = HERE / "post_run_sensitivity.json"


def tool(name: str):
    spec = importlib.util.spec_from_file_location(name, REPO / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def direct_weights(series: str, k: dict, n: int) -> dict:
    """Delta = [k0 b0 - km1 b-1] / n with b0 = beta_C0 and b-1 = -beta_C1 (block C, plan §7)."""
    return {f"{series}.C:off0": k["k0"] / n, f"{series}.C:offm1": k["km1"] / n}


def analytic_t(fit: dict, w: np.ndarray, c: float) -> float:
    est = float(w @ fit["f"]["b"])
    se = float(np.sqrt(w @ fit["cov"]["V"] @ w))
    return (est - c) / se


def main() -> int:
    stc = tool("snapshot_timing_check")
    x = stc.prepare()
    blocks, cnt = x["blocks"], x["counts"]
    fit = stm.stacked_fit(blocks)
    out = {"kind": "snapshot_timing_post_run_sensitivity", "exploratory": True, "code_commit": store.code_commit(),
           "reps": stc.BOOT_REPS, "seed": stc.BOOT_SEED, "direct": {}, "analytic_t_at_minus_line": {}}
    combos, tests = {}, {}
    for h, series in (("H1", "cm30"), ("H4", "sigma")):
        w = stm.vector(fit, direct_weights(series, cnt[h], cnt[h]["n"]))
        combos[f"direct {h}"] = w
        tests |= {f"{h} {side}": wc for side, wc in stm.line_tests(w, stc.LINES[h]).items()}
    boot = stm.wild_bootstrap(fit, combos, stc.BOOT_REPS, stc.BOOT_SEED)
    wcr = stm.wcr_bootstrap(fit, tests, {}, stc.BOOT_REPS, stc.BOOT_SEED)
    for h in ("H1", "H4"):
        b, lo, hi, L = boot["combos"][f"direct {h}"], wcr["tests"][f"{h} lo"], wcr["tests"][f"{h} hi"], stc.LINES[h]
        out["direct"][h] = {"estimate": stc.rnd(b["estimate"]), "ci90": [stc.rnd(v) for v in b["ci90"]],
                            "estimate_lines": stc.rnd(b["estimate"] / L, 3),
                            "ci90_lines": [stc.rnd(v / L, 3) for v in b["ci90"]],
                            "p_up_at_minus_line": stc.rnd(lo["p_up"]), "p_dn_at_plus_line": stc.rnd(hi["p_dn"]),
                            "rule_applied": stm.tost_verdict(lo, hi)}
    for h, (series, measure) in stc.SHIFT.items():
        weights = stm.shift_weights(series, measure, cnt[h], cnt[h]["n"])
        own = stm.stacked_fit({k: v for k, v in blocks.items()
                               if k.startswith(series + ".") and (k.endswith((".P", ".A", ".C"))
                                                                  or any(".O" in key for key in weights))})
        out["analytic_t_at_minus_line"][h] = {
            "stacked": stc.rnd(analytic_t(fit, stm.vector(fit, weights), -stc.LINES[h]), 3),
            "own_series_blocks": stc.rnd(analytic_t(own, stm.vector(own, weights), -stc.LINES[h]), 3),
            "blocks": sorted(own["n_rows"])}
    OUT.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(json.dumps(out, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
