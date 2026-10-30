"""p08 (claim 8): own mutants of milestone 4's code, on a SCRATCH COPY of the repository (the working tree is never
edited). Each mutant replaces one exact string in one file, runs the FULL Python suite (-m "not dolt", no -x, so
every failing test is listed), restores the file from bytes held in memory and checks its SHA-256. A kill only by
tests/test_notebooks_sync.py (notebook text vs src/) is NOTEBOOK-ONLY: the source text changed, no behaviour pinned.
A kill only by a test that reads a committed file without calling the mutated code cannot happen by construction
(the committed files are not rebuilt), so every KILLED below is a test that ran the mutated code.
Run: python docs/validation/probes/m4/p08_mutants.py <scratch_repo> <venv python> [first last]
"""
import hashlib
import subprocess
import sys
from pathlib import Path

REPO = Path(sys.argv[1])
PY = sys.argv[2]
LO, HI = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else (0, 10 ** 6)
REG, DRV, G1D, RUN, RES, RGS = ("src/earnings_vol/stats/regression.py", "src/earnings_vol/stats/drivers.py",
                                "src/earnings_vol/stats/g1_drivers.py", "src/earnings_vol/stats/run.py",
                                "src/earnings_vol/stats/results.py", "src/earnings_vol/panel/regressors.py")
MUTANTS = [
    # regression.py
    ("M01 CR1 factor without (N-1)/(N-K)", REG,
     'c = g / (g - 1) * (f["n"] - 1) / (f["n"] - f["k"])', "c = g / (g - 1)"),
    ("M02 two-way df from max(G) - 1", REG, '"df": float(min(ga, gb) - 1)}', '"df": float(max(ga, gb) - 1)}'),
    ("M03 Wald fallback takes the SMALLER-trace one-way block", REG,
     "key=lambda m: float(np.trace(m)))", "key=lambda m: -float(np.trace(m)))"),
    # drivers.py
    ("M04 exceed share keeps E <= 0 events", DRV,
     'keep = np.isfinite(r0) & np.isfinite(iam) & (ev["evar_m1"].to_numpy(float) > 0)',
     "keep = np.isfinite(r0) & np.isfinite(iam)"),
    ("M05 the mean-adjusted twin regresses the market-adjusted crush", DRV,
     "y = inputs.values(f, rows, spec.y, spec.adjustment)", 'y = inputs.values(f, rows, spec.y, "market")'),
    ("M06 shift_null ignores the null (b tested against 0)", DRV,
     't = (res["estimate"] - null) / res["se"]', 't = res["estimate"] / res["se"]'),
    ("M07 H7 primary role ignores the gate", DRV,
     'role = ("primary" if gate.get("H7", True) else "exploratory") if main else "exploratory"',
     'role = "primary" if main else "exploratory"'),
    # g1_drivers.py
    ("M08 G1 H5/H6 outcome NOT re-estimated (raw change, no beta/s re-estimate)", G1D,
     'A = est["e"][dd.rows, abnormal.col(0)]',
     "A = x[d.firm[dd.rows], d.sess[dd.rows, abnormal.col(0)]] - x[d.firm[dd.rows], d.sess[dd.rows, abnormal.col(-1)]]"),
    ("M09 calibrate_h7 rho correction with the wrong sign", G1D,
     "rho_raw * np.exp(tau ** 2 / 4.0)", "rho_raw * np.exp(-tau ** 2 / 4.0)"),
    ("M10 H7 firm multiplier without the mean-1 correction (null broken)", G1D,
     "m = np.exp(tau * rng.standard_normal(nf) - tau ** 2 / 2.0)", "m = np.exp(tau * rng.standard_normal(nf))"),
    ("M11 sig_firm centred on the event mean, not the firm mean", G1D,
     "grand = float(np.mean(list(means.values())))", "grand = float(log_s.mean())"),
    # run.py (wiring)
    ("M12 Holm family ignores the gate (H1-H7 binding)", RUN,
     'family = [h for h in st["holm_family"] if report["gate"].get(h, True)]', 'family = list(st["holm_family"])'),
    ("M13 driver rows get no mis-sized set (one-way rows not withheld)", RUN,
     'rows += drivers.driver_rows(f, dp, report["gate"], common, mis_sized)',
     'rows += drivers.driver_rows(f, dp, report["gate"], common, {})'),
    ("M14 the all-declared sensitivity runs over the binding family", RUN,
     'declared = results.holm_declared_rows(rows, report["primary"], list(st["holm_family"]), common)',
     'declared = results.holm_declared_rows(rows, report["primary"], family, common)'),
    ("M15 driver_design: firm scales not pinned (sig_firm zeroed)", RUN,
     'sigf, h7["x"], h7["date"]', 'sigf * 0.0, h7["x"], h7["date"]'),
    ("M16 driver_design: G1's H7 regressor from E at day -2", RUN,
     'h7 = drivers.h7_inputs(f, "evar_m1", float(dp["h7_floor"]))',
     'h7 = drivers.h7_inputs(f, "evar_m2", float(dp["h7_floor"]))'),
    ("M17 driver_report gate twice as lenient", RUN,
     '"gate": {h: bool(cal[h][cal[h]["_primary"]] <= hi)', '"gate": {h: bool(cal[h][cal[h]["_primary"]] <= 2 * hi)'),
    # results.py (wiring)
    ("M18 Holm drops a family member that has no primary row (instead of p = 1)", RES,
     'pv = {h: (prim[h]["p_value"] if h in prim else None) for h in family}',
     'pv = {h: prim[h]["p_value"] for h in family if h in prim}'),
    ("M19 all-declared sensitivity sees only primary rows", RES,
     'and r["statistic"] == declared.get(h) and r["role"] in ("primary", "exploratory")',
     'and r["statistic"] == declared.get(h) and r["role"] in ("primary",)'),
    ("M20 BH over event tests and regressions together", RES,
     'fam = [r for r in rows if r["family"] == family and r["role"] == "exploratory"',
     'fam = [r for r in rows if r["family"] in TESTED_FAMILIES and r["role"] == "exploratory"'),
    # regressors.py
    ("M21 SUE_hist history includes the current quarter (look-ahead)", RGS,
     "        use = prev[-n_prev:]", "        use = (prev + [values[eid]])[-n_prev:]"),
    ("M22 VIX tercile: a value on a cut point goes UP", RGS,
     "REGIMES[0] if v <= lo else (REGIMES[1] if v <= hi else REGIMES[2])",
     "REGIMES[0] if v < lo else (REGIMES[1] if v < hi else REGIMES[2])"),
    ("M23 SIZE scaled by the FIRST close in the file", RGS,
     'px.sort_values("date")["close"].iloc[-1]', 'px.sort_values("date")["close"].iloc[0]'),
    ("M24 price_ref at the POST session (look-ahead)", RGS,
     'for eid, pre in zip(event_iv["event_id"], event_iv["pre_session"]):',
     'for eid, pre in zip(event_iv["event_id"], event_iv["post_session"]):'),
    ("M25 |SURP| winsorised over all samples together", RGS,
     "absw = winsorise({k: abs(v) for k, v in surp.items()}, smp, ",
     'absw = winsorise({k: abs(v) for k, v in surp.items()}, {k: "all" for k in smp}, '),
]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


killed = 0
done = 0
for i, (name, rel, old, new) in enumerate(MUTANTS):
    if not LO <= i <= HI:
        continue
    done += 1
    f = REPO / rel
    orig = f.read_bytes()
    h0 = sha(f)
    text = orig.decode()
    if text.count(old) != 1:
        print(f"{name}: PROBE_INVALID (anchor found {text.count(old)} times)", flush=True)
        continue
    f.write_text(text.replace(old, new))
    try:
        r = subprocess.run([PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-m", "not dolt"], cwd=REPO,
                           env={"PYTHONPATH": str(REPO / "src"), "PATH": "/usr/bin:/bin", "HOME": str(Path.home()),
                                "VOL_DATA_DIR": str(Path.home() / "data" / "vol-projects")},
                           capture_output=True, text=True, timeout=1800)
        last = [ln for ln in r.stdout.splitlines() if ln.strip()][-1] if r.stdout.strip() else r.stderr[-200:]
        failed = [ln.split(" ")[1] for ln in r.stdout.splitlines() if ln.startswith("FAILED") or ln.startswith("ERROR")]
    finally:
        f.write_bytes(orig)
    ok = sha(f) == h0
    real = [t for t in failed if not t.startswith("tests/test_notebooks_sync.py")]
    status = "KILLED" if real else ("NOTEBOOK-ONLY" if failed else ("SURVIVED" if r.returncode == 0 else f"rc={r.returncode}"))
    killed += bool(real)
    print(f"{name} [{rel.split('/')[-1]}]: {status} {failed} | {last[:80]} | restored sha256 ok={ok}", flush=True)
print(f"SUMMARY killed by a behavioural test {killed} of {done}")
