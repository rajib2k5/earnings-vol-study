# =============================================================================
# calib.py - Is the block bootstrap as wide as the real spread? (pre-
# registration §6 and §16, review finding 4, item M4.) SYNTHETIC data only.
#
# For each (c) rule, its null world (worlds.NULL_OF_RULE: no planted fault)
# is built with 48 seeds (101 to 148, not the probe seeds 1 to 3). On each
# seed the rule's point share and its bootstrap sd (the sd of the 10,000
# replicates) are recorded, with blocks of 20 sessions (the rule) and of 60
# (the robustness rerun). Then
#     ratio = sd of the point over the seeds / mean bootstrap sd.
# A ratio above 1 means the bootstrap is too narrow: the seed-to-seed spread
# of the point is the real sampling spread of the statistic in that world.
# ivchecks.INFLATE[rule] is set to max(1, ratio), rounded UP to 0.05, over
# the clean- and any-reference versions of the strike and filter rules.
# The ratio is itself an estimate from 48 seeds (relative standard error
# about 1/sqrt(2 x 47) = 10%); it is used as measured, not tuned. A
# first run on 16 seeds gave a forward ratio of 0.92, while seeds 1 to 12
# (the reviewer's set) give 1.71: the ratio is noisy, hence 48 seeds.
#
# Run: <venv>/bin/python -I .../probes/calib.py --out DIR   (DIR outside
# this folder; the frozen copies calib.out and calib.json are then copied in
# by hand). Python's -I is safe: the clone's src is inserted and asserted.
# =============================================================================

import argparse
import json
import math
import os
import pathlib
import sys
import time

for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = "1"

HERE = pathlib.Path(__file__).resolve().parent
CLONE = HERE.parents[3]
sys.path[:0] = [str(CLONE / "src"), str(HERE)]

import earnings_vol  # noqa: E402

if not pathlib.Path(earnings_vol.__file__).resolve().is_relative_to(CLONE / "src"):
    sys.exit(f"earnings_vol imported from {earnings_vol.__file__}, not from {CLONE / 'src'}")

from concurrent.futures import ProcessPoolExecutor  # noqa: E402

import numpy as np  # noqa: E402
import yaml  # noqa: E402

import ivchecks  # noqa: E402
import synth  # noqa: E402
import worlds  # noqa: E402
from earnings_vol.measures import chain, termstructure  # noqa: E402

PARAMS = yaml.safe_load((CLONE / "params.yaml").read_text())
P = chain.AtomParams.from_params(PARAMS["iv"])
TP = termstructure.TermParams.from_params(PARAMS["iv"])
SEEDS = list(range(101, 149))
BLOCKS = (ivchecks.BLOCK, ivchecks.ROBUST_BLOCK)


def one(job):
    world, seed = job
    panel = synth.make_panel(worlds.spec(world, seed))
    out = {}
    for block in BLOCKS:
        counts = ivchecks.block_counts(len(panel.days), block=block)
        r = ivchecks.run_name(panel, P, TP, None, None, counts, with_truth=False, with_diff=False, with_common=False)
        for rule, w in worlds.NULL_OF_RULE.items():
            if w != world:
                continue
            versions = {"": r[rule]}
            if "any_ref" in r[rule]:
                versions = {"clean": r[rule], "any": r[rule]["any_ref"]}
            for ref, x in versions.items():
                out[(rule, ref, block)] = (x["share"], x["boot_sd"], x["n"], x.get("n_group"), x["verdict"])
    return world, seed, out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=pathlib.Path)
    a = ap.parse_args()
    out_dir = a.out.resolve()
    if out_dir.is_relative_to(HERE.parent):
        sys.exit(f"--out {out_dir} is inside the frozen folder {HERE.parent}; write elsewhere")
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    jobs = [(w, s) for w in sorted(set(worlds.NULL_OF_RULE.values())) for s in SEEDS]
    with ProcessPoolExecutor(max_workers=min(8, os.cpu_count() or 1)) as ex:
        res = list(ex.map(one, jobs))
    rows = {}
    for world, seed, out in res:
        for key, val in out.items():
            rows.setdefault(key, []).append((seed,) + val)
    lines = [f"calib.py: {len(SEEDS)} seeds {SEEDS[0]}..{SEEDS[-1]}; ratio = sd(point over seeds) / mean bootstrap sd",
             f"{'rule':8} {'ref':6} {'block':>5} {'seeds':>5} {'mean point':>10} {'sd point':>9} {'mean boot sd':>12} "
             f"{'ratio':>6}  verdicts"]
    summary, inflate = {}, {}
    for (rule, ref, block), v in sorted(rows.items()):
        pts = np.array([x[1] for x in v], float)
        sds = np.array([x[2] for x in v], float)
        ok = np.isfinite(pts) & np.isfinite(sds)
        ratio = float(np.std(pts[ok], ddof=1) / np.mean(sds[ok])) if ok.sum() > 2 else math.nan
        verdicts = {}
        for x in v:
            verdicts[x[5]] = verdicts.get(x[5], 0) + 1
        summary[f"{rule}|{ref}|{block}"] = {"seeds": int(ok.sum()), "mean_point": float(np.mean(pts[ok])),
                                             "sd_point": float(np.std(pts[ok], ddof=1)),
                                             "mean_boot_sd": float(np.mean(sds[ok])), "ratio": ratio,
                                             "verdicts": verdicts}
        lines.append(f"{rule:8} {ref or '-':6} {block:5d} {ok.sum():5d} {np.mean(pts[ok]):+10.4f} "
                     f"{np.std(pts[ok], ddof=1):9.4f} {np.mean(sds[ok]):12.4f} {ratio:6.2f}  {verdicts}")
        if block == ivchecks.BLOCK:
            inflate[rule] = max(inflate.get(rule, 1.0), ratio)
    inflate = {k: max(1.0, math.ceil(v * 20.0 - 1e-9) / 20.0) for k, v in sorted(inflate.items())}
    lines.append(f"INFLATE (block {ivchecks.BLOCK}, max over references, rounded up to 0.05, at least 1): {inflate}")
    lines.append(f"ivchecks.INFLATE as frozen: {ivchecks.INFLATE}   match: {inflate == ivchecks.INFLATE}")
    text = "\n".join(lines) + "\n"
    print(text, end="")
    (out_dir / "calib.out").write_text(text)
    (out_dir / "calib.json").write_text(json.dumps({"summary": summary, "inflate": inflate}, indent=1,
                                                   sort_keys=True) + "\n")
    print(f"elapsed: {time.monotonic() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
