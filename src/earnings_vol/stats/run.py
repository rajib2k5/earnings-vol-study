# =============================================================================
# run.py — run_stats(): gate G1, then the `results` table (milestone 3).
#
# Run, in this order (the second refuses to start without the first):
#   uv run python -m earnings_vol.stats.run --g1     gate G1 only: calibrate on
#        the real baselines, simulate every design, write
#        cache/stage/<hash>/g1_report.json and print the verdicts
#   uv run python -m earnings_vol.stats.run          the results, with G1's
#        verdicts applied: cache/stage/<hash>/results.parquet + manifest,
#        data/derived/results.parquet, cache/stage/<hash>/results_report.json
#
# ADR 0005 §5: G1 runs before any H1-H4 result is computed, so a failed gate
# moves its hypothesis out of the confirmatory family before anyone has seen
# its p-value, and no substitute statistic is promoted after the fact.
#
# Reads the stage tables session, events, security, market_daily (ln VIX),
# event_window_obs and event_measures (with their local class-R columns).
# G1 uses `--workers` processes (default 20); each replication is seeded
# from params stats.g1_seed, the design's position and the replication's.
# H1-H3 are simulated on a cm30 series calibrated on the CRUSH set; H4 on a
# sigma_d series of its own, calibrated on the DSIGMA_D set (calibrate_on).
# The results run withholds the p-value of every robustness row G1 finds
# mis-sized (results.oversized) and adds H2's season-cut counterfactual.
# Second fix round: the wiring is in pure functions (g1_designs, rep_args,
# result_rows) that tests run on synthetic inputs; H4's second series is
# adjusted with the cm30 series' beta (g1.second_series); robustness rows near
# the bar are re-measured on g1.REMEASURE_REPS replications (g1.near_bar).
# =============================================================================

import os

# One BLAS thread per process: G1's workers otherwise each start a thread per core and the
# machine runs ~20x oversubscribed (the prototype h2h3_size_sim.py does the same). Set before
# numpy is first imported.
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse  # noqa: E402
import json  # noqa: E402
import multiprocessing as mp  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402

from earnings_vol import params as params_mod, schema, store
from earnings_vol.events.run import DERIVED, stage_dir
from earnings_vol.panel import abnormal
from earnings_vol.stats import g1, inputs, results

_STATE: dict = {}


def load(p) -> inputs.Frame:
    sd = stage_dir(p)
    t = {n: store.read_table(sd / f"{n}.parquet", schema.REGISTRY[n])
         for n in ("session", "events", "security", "market_daily", "event_window_obs", "event_measures")}
    return inputs.build_frame(t["events"], t["event_measures"], t["event_window_obs"], t["security"],
                              t["market_daily"], t["session"])


def calibrate_on(f: inputs.Frame, rows: np.ndarray, measure: str, st: dict) -> dict:
    """g1.calibrate() on the real pooled clean baselines of `rows`: the cm30 series and its
    CRUSH (measure "crush"), or the sigma_d series and DSIGMA_D (measure "dsigma_d", with the
    sigma_d scale of panel/window.py: the sd of the clean abnormal changes of ln sigma_d_iv)."""
    series = "sigma_d" if measure == "dsigma_d" else "cm30"
    e = inputs.clean_e(f, rows, series)
    if series == "cm30":
        s = f.ev["s_abn_cboe"].to_numpy(float)[rows]
        lv = f.aliv[rows]
    else:
        beta = f.ev["beta_vix_cboe"].to_numpy(float)[rows]
        with np.errstate(invalid="ignore", divide="ignore"):
            s = np.sqrt(np.nanvar(e, axis=1, ddof=1))
            lv = np.log(np.where(f.sigma_d[rows] > 0, f.sigma_d[rows], np.nan)) - beta[:, None] * f.M[rows]
    return g1.calibrate_from(e, s, lv, f.in_baseline[rows], f.sess[rows], f.ev["security_id"].to_numpy(object)[rows],
                             f.ev["gics_sector"].to_numpy(object)[rows], inputs.values(f, rows, measure, "market"),
                             int(st["rhat_max_lag"]), int(st["psd_grid"]), int(st["kp_min_shared"]))


def design_and_calibration(f: inputs.Frame, st: dict) -> tuple[g1.Design, dict, g1.Design, dict]:
    """The G1 designs (the union of the four primary event sets) and the calibrated DGPs:
    (cm30 design, its calibration on the CRUSH set, sigma_d design, its calibration on the
    DSIGMA_D set). The sigma_d design differs only in its usable mask (a sigma_d_iv)."""
    sets_f = {h: inputs.event_set(f, m, "daily") for h, m in g1.TESTS.items()}
    sets_f["H1"] = sets_f["H1"][np.isfinite(inputs.values(f, sets_f["H1"], "crush", "market"))]
    union = np.unique(np.concatenate(list(sets_f.values())))
    pos = {r: k for k, r in enumerate(union)}
    ev = f.ev.iloc[union]
    firms = sorted(set(ev["security_id"]))
    fidx = {s: k for k, s in enumerate(firms)}
    sectors = sorted(set(ev["gics_sector"]))
    firm_sector = np.array([sectors.index(ev.loc[ev["security_id"] == s, "gics_sector"].iloc[0]) for s in firms])
    beta = {s: b for s, b in zip(ev["security_id"], ev["beta_vix_cboe"])}
    span = np.arange(int(f.sess[union].min()), int(f.sess[union].max()) + 1)
    vix_by = {int(t): m for t, m in zip(f.sess[union].ravel(), f.M[union].ravel())}
    vix = np.array([vix_by.get(int(t), np.nan) for t in span])
    d0 = f.sess[union, abnormal.col(0)]

    def design(usable):
        return g1.build_design(firms, firm_sector, f.sess[union], usable, f.in_baseline[union],
                               np.array([fidx[s] for s in ev["security_id"]]), d0, d0,
                               ev["season"].to_numpy(object), np.array([sectors.index(s) for s in ev["gics_sector"]]),
                               {h: np.array([pos[r] for r in rows]) for h, rows in sets_f.items()},
                               np.array([beta[s] for s in firms]), float(np.nanstd(np.diff(vix), ddof=1)),
                               int(st["rhat_max_lag"]))

    des = design(f.usable[union])
    des_sd = design(np.isfinite(f.sigma_d[union]))
    # Calibration on the primary sample (the CRUSH set: eligible_crush, daily), and for H4 on
    # its own set and series.
    cal = calibrate_on(f, sets_f["H1"], "crush", st)
    cal["measured"]["beta_median"] = float(np.median([beta[c] for c in firms]))
    cal["measured"]["dm_sd"] = des.dm_sd
    cal_sd = calibrate_on(f, sets_f["H4"], "dsigma_d", st)
    return des, cal, des_sd, cal_sd


def g1_designs(cal: dict, cal_sd: dict, st: dict) -> tuple[dict, dict, list]:
    """(designs, designs_sd, plan): the DGP parameters of every G1 design for the cm30 series
    (H1-H3) and for H4's sigma_d series, and the run plan [(design, robust rows?, sets key)].
    Pure. The calibrated design is the calibration's parameters as estimated, its sig0 included
    (the stress designs keep the prototype's scale g1.SIG0); H4's series uses its own sigma_d
    calibration wherever the cm30 one is used (the calibrated design and the crush power shifts)."""
    designs = {"calibrated": dict(cal["params"])}
    designs.update({k: {kk: vv for kk, vv in v.items() if not kk.startswith("_")} for k, v in g1.STRESS.items()})
    # H4's series: the same stress designs, and its own calibration where the cm30 one is used.
    designs_sd = dict(designs, calibrated=dict(cal_sd["params"]))
    plan = [(name, True, "unbalanced" if g1.STRESS.get(name, {}).get("_unbalanced") else "all") for name in designs]
    for mu in st["g1_power_shifts"]:
        designs[f"power_crush:{mu}"] = dict(cal["params"], mu=float(mu), shift_on="crush")
        designs[f"power_ramp:{mu}"] = dict(cal["params"], mu=float(mu), shift_on="ramp")
        designs_sd[f"power_crush:{mu}"] = dict(cal_sd["params"], mu=float(mu), shift_on="crush")
        plan += [(f"power_crush:{mu}", False, "crush"), (f"power_ramp:{mu}", False, "ramp")]
    return designs, designs_sd, plan


def rep_args(state: dict, name: str, seed: int, robust: bool, sets_key: str) -> tuple:
    """The g1.replicate() arguments of one replication of design `name` on the event sets
    state["sets"][sets_key]: H1-H3 on the cm30 design, and H4 (when in the sets) as the second
    series, on the sigma_d design with the sigma_d parameters of the same design name. Pure."""
    sets = state["sets"][sets_key]
    main = {h: r for h, r in sets.items() if h != "H4"}
    second = (state["design_sd"], state["designs_sd"][name], {"H4": sets["H4"]}) if "H4" in sets else None
    return (state["design"], state["designs"][name], main, seed, state["alpha"], state["st"], robust, second)


def _rep(args):
    name, seed, robust, sets_key = args
    return g1.replicate(rep_args(_STATE, name, seed, robust, sets_key))


def remeasure_plan(near: dict, sets: dict, seed0: int) -> tuple[dict, list]:
    """(sets, tasks) of the re-measure block (g1.near_bar's {test: [statistic]}): g1.REMEASURE_REPS
    replications of the calibrated design, robust rows on, on the event sets of the near-bar tests
    only, seeded from block g1.REMEASURE_BLOCK of the run's seed stride (fresh: the main run uses
    blocks 1 .. number of designs). Pure."""
    block = [("calibrated", seed0 + 1_000_003 * g1.REMEASURE_BLOCK + r, True, "remeasure")
             for r in range(g1.REMEASURE_REPS)]
    return {h: sets[h] for h in near}, block


def _run_block(workers: int, tasks: list) -> dict:
    """g1.rates() over the replications of `tasks`, in a fresh pool forked from _STATE."""
    with mp.get_context("fork").Pool(workers) as pool:
        return g1.rates(pool.map(_rep, tasks, chunksize=max(1, len(tasks) // (4 * workers))))


def run_g1(p, workers: int) -> dict:
    st = p["stats"]
    f = load(p)
    t0 = time.monotonic()
    des, cal, des_sd, cal_sd = design_and_calibration(f, st)
    reps, seed0, alpha = int(st["g1_reps"]), int(st["g1_seed"]), float(st["alpha"])
    designs, designs_sd, plan = g1_designs(cal, cal_sd, st)
    sets = {"all": des.sets, "unbalanced": {h: g1.unbalanced_subset(des, r, st) for h, r in des.sets.items()},
            "crush": {h: des.sets[h] for h in ("H1", "H4")}, "ramp": {h: des.sets[h] for h in ("H2", "H3")}}
    _STATE.update(design=des, designs=designs, design_sd=des_sd, designs_sd=designs_sd, sets=sets, alpha=alpha,
                  st=dict(st))
    out_rates = {}
    ctx = mp.get_context("fork")
    with ctx.Pool(workers) as pool:
        for di, (name, robust, key) in enumerate(plan):
            tasks = [(name, seed0 + 1_000_003 * (di + 1) + r, robust, key) for r in range(reps)]
            res = pool.map(_rep, tasks, chunksize=max(1, reps // (4 * workers)))
            out_rates[name] = g1.rates(res)
            print(f"[{time.monotonic() - t0:6.0f}s] {name}: " + "; ".join(
                f"{h} {r['_primary']} {100 * r[r['_primary']]:.2f}%" for h, r in out_rates[name].items()),
                flush=True)
    lo, hi = g1.binom_band(reps, alpha)
    cal_rates = out_rates["calibrated"]
    # ADR 0005 §4 (dated note, second fix round): robustness statistics near the bar are re-measured
    # on g1.REMEASURE_REPS fresh replications of the calibrated design (results.oversized decides).
    near = g1.near_bar(cal_rates, reps, alpha)
    remeasured = None
    if near:
        _STATE["sets"]["remeasure"], block = remeasure_plan(near, des.sets, seed0)
        rr = _run_block(workers, block)
        remeasured = {"reps": g1.REMEASURE_REPS, "seed_block": g1.REMEASURE_BLOCK,
                      "rates": {h: {k: rr[h][k] for k in near[h]} for h in near}}
        print(f"[{time.monotonic() - t0:6.0f}s] re-measured on {g1.REMEASURE_REPS}: " + "; ".join(
            f"{h} {k} {100 * v:.2f}%" for h, by in remeasured["rates"].items() for k, v in by.items()), flush=True)
    gate = {h: bool(cal_rates[h][cal_rates[h]["_primary"]] <= hi) for h in g1.TESTS}
    power = {}
    for h, kind in (("H1", "crush"), ("H4", "crush"), ("H2", "ramp"), ("H3", "ramp")):
        shifts = [float(mu) for mu in st["g1_power_shifts"]]
        pw = [out_rates[f"power_{kind}:{mu}"][h][out_rates[f"power_{kind}:{mu}"][h]["_primary"]]
              for mu in st["g1_power_shifts"]]
        power[h] = {"shifts": shifts, "power": pw, "detectable_80": g1.detectable_shift(shifts, pw)}
    return {"params_hash": p.params_hash, "reps": reps, "alpha": alpha, "band": [lo, hi], "gate": gate,
            "primary": {h: cal_rates[h]["_primary"] for h in g1.TESTS}, "rates": out_rates, "power": power,
            "remeasured": remeasured,
            "calibration": cal, "calibration_sigma_d": cal_sd,
            "n_events": {h: int(r.size) for h, r in des.sets.items()},
            "n_events_union": int(des.firm.size), "n_firms": len(des.firms), "seconds": round(time.monotonic() - t0)}


def result_rows(f: inputs.Frame, st: dict, report: dict, common: dict) -> tuple[list[dict], dict]:
    """Every `results` row from the stats Frame and gate G1's report, and the Holm summary. Pure:
    the wiring of the results run (G1's verdicts -> the roles, the withheld mis-sized robustness
    rows, Holm over the family after the gate, H2's season-cut counterfactual, BH, the paths and
    G1's own rows), kept out of run_results() so that a test can run it on a synthetic Frame."""
    mis_sized = results.oversized(report, float(st["alpha"]))
    rows = results.event_test_rows(f, st, report["gate"], common, mis_sized)
    family = [h for h in st["holm_family"] if report["gate"].get(h, True)]
    holm = results.apply_holm(rows, family)
    rows += results.season_cut_rows(f, st, rows, family, common)
    results.apply_bh(rows)
    rows += results.path_rows(f, st, common)
    g1_report = dict(report, n_events=report["n_events_union"])
    rows += results.g1_rows(g1_report, common)
    return rows, {"holm_family": family, "holm": holm}


def run_results(p, report: dict) -> tuple:
    st = p["stats"]
    f = load(p)
    common = {"params_hash": p.params_hash, "code_commit": store.code_commit()}
    rows, summary = result_rows(f, st, report, common)
    df = results.frame(rows)
    return df, dict(summary, rows=int(len(df)), by_family=df["family"].value_counts().sort_index().to_dict())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--g1", action="store_true", help="run gate G1 only")
    ap.add_argument("--workers", type=int, default=20)
    args = ap.parse_args(argv)
    p = params_mod.load()
    sd = stage_dir(p)
    g1_path = sd / "g1_report.json"
    if args.g1:
        rep = run_g1(p, args.workers)
        g1_path.write_text(json.dumps(rep, indent=2, sort_keys=True) + "\n")
        print(json.dumps({k: rep[k] for k in ("band", "gate", "primary", "power", "n_events", "seconds")}, indent=2))
        return 0
    if not g1_path.exists():
        raise SystemExit(f"run gate G1 first: uv run python -m earnings_vol.stats.run --g1 (no {g1_path})")
    rep = json.loads(g1_path.read_text())
    if rep["params_hash"] != p.params_hash:
        raise SystemExit("g1_report.json was made with other parameters: run --g1 again")
    df, summary = run_results(p, rep)
    store.write_table(df, schema.RESULTS, sd / "results.parquet", params_hash=p.params_hash,
                      dolt_commits={"options": p["dolt"]["options_commit"], "earnings": p["dolt"]["earnings_commit"]})
    store.write_derived(df, schema.RESULTS, DERIVED)
    (sd / "results_report.json").write_text(json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
