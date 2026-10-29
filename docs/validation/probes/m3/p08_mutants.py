"""p08: own mutants on a SCRATCH COPY of the repository (claim 8). The working tree is never edited.

Each mutant replaces one exact string in one file of <scratch_repo>/src, runs the eight new test modules,
records killed (pytest rc != 0) or SURVIVED, restores the file from bytes held in memory and checks
its SHA-256. Run:
  python docs/validation/probes/m3/p08_mutants.py <scratch_repo> <venv python>
"""
import hashlib
import subprocess
import sys
from pathlib import Path

REPO = Path(sys.argv[1])
PY = sys.argv[2]
TESTS = ["tests/test_clustering.py", "tests/test_eventtests.py", "tests/test_panel.py", "tests/test_ramp_identity.py",
         "tests/test_multiple.py", "tests/test_g1.py", "tests/test_invariants.py", "tests/test_event_views.py"]
C, E, A, W, M, G = ("src/earnings_vol/stats/clustering.py", "src/earnings_vol/stats/eventtests.py",
                    "src/earnings_vol/panel/abnormal.py", "src/earnings_vol/panel/window.py",
                    "src/earnings_vol/stats/multiple.py", "src/earnings_vol/stats/g1.py")
MUTANTS = [
    ("M01 CR1 residuals not demeaned", C, "s = np.bincount(gi, A - A.mean(), g)", "s = np.bincount(gi, A, g)"),
    ("M02 rad t* variance not re-centred per sign vector", C,
     "var = g / (g - 1) * ((ss - ng[None, :] * m[:, None]) ** 2).sum(1) / n ** 2",
     "var = g / (g - 1) * (ss ** 2).sum(1) / n ** 2"),
    ("M03 merge the LAST small season first", C, "k = small[0]", "k = small[-1]"),
    ("M04 sign test pooled share <= 0", E, "p = float((pooled < 0).mean())", "p = float((pooled <= 0).mean())"),
    ("M05 kp_ow sector fallback ignored", E, "filled = np.where(ok, rho, np.where(same, m_sec, m_all))",
     "filled = np.where(ok, rho, np.where(same, m_all, m_all))"),
    ("M06 span weight read at the START of the span", A,
     "return [(walk[k - 1], walk[k], n_before[walk[k]] / b.size) for k in range(1, len(walk))]",
     "return [(walk[k - 1], walk[k], n_before[walk[k - 1]] / b.size) for k in range(1, len(walk))]"),
    ("M07 Bartlett taper 1 - k/L instead of 1 - k/(L+1)", A,
     "taper = rho * (1.0 - np.arange(1, rho.size + 1) / (rho.size + 1))",
     "taper = rho * (1.0 - np.arange(1, rho.size + 1) / rho.size)"),
    ("M08 coarse change may span a null_iv session", W,
     'all(p.reason[i, j] == "not_observed" for j in range(a + 1, c)))',
     'all(p.reason[i, j] in ("not_observed", "null_iv") for j in range(a + 1, c)))'),
    ("M09 coarse PERSIST tries h+1 before h-1", W, "cands = [h] if not coarse else [h, h - 1, h + 1]",
     "cands = [h] if not coarse else [h, h + 1, h - 1]"),
    ("M10 daily PERSIST may fall back to +-1", W, "targets[f\"persist_{h}\"] = None if beyond else _target_col(p, i, h, coarse)",
     "targets[f\"persist_{h}\"] = None if beyond else _target_col(p, i, h, True)"),
    ("M11 BH q-values not capped at 1", M, "    running = 1.0\n    for rank in range(m - 1, -1, -1):",
     "    running = np.inf\n    for rank in range(m - 1, -1, -1):"),
    ("M12 G1 uses the TRUE beta, not a re-estimated one", G,
     "beta = np.array([betas[f][0] for f in d.firm], float)", "beta = d.beta_true[d.firm]"),
    ("M13 G1 AR without the Kendall correction", G, "return num / den_raw, L, min(1.0, (L * ph + 1) / (L - 3))",
     "return num / den_raw, L, min(1.0, ph)"),
    ("M14 G1 firm effect sd without the sampling-variance correction", G,
     "firm_fx = float(np.sqrt(max(0.0, fm.var(ddof=1) - fv.mean())))", "firm_fx = float(np.sqrt(max(0.0, fm.var(ddof=1))))"),
    ("M15 G1 DGP drops the day-0 jumps", G, "    if jk:\n        for fi in range(nf):", "    if False:\n        for fi in range(nf):"),
    ("M16 G1 band at 99% one-sided (0.99) instead of 99.5%", G,
     "stats.binom.ppf(0.995, reps, alpha) / reps", "stats.binom.ppf(0.99, reps, alpha) / reps"),
]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


killed = 0
for name, rel, old, new in MUTANTS:
    f = REPO / rel
    orig = f.read_bytes()
    h0 = sha(f)
    text = orig.decode()
    if text.count(old) != 1:
        print(f"{name}: PROBE_INVALID (anchor found {text.count(old)} times)")
        continue
    f.write_text(text.replace(old, new))
    try:
        r = subprocess.run([PY, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *TESTS], cwd=REPO,
                           env={"PYTHONPATH": str(REPO / "src"), "PATH": "/usr/bin:/bin", "HOME": str(Path.home())},
                           capture_output=True, text=True, timeout=900)
        last = [ln for ln in r.stdout.splitlines() if ln.strip()][-1] if r.stdout.strip() else r.stderr[-200:]
        failed = [ln.split(" ")[1] for ln in r.stdout.splitlines() if ln.startswith("FAILED")]
    finally:
        f.write_bytes(orig)
    ok = sha(f) == h0
    status = "KILLED" if r.returncode != 0 else "SURVIVED"
    killed += r.returncode != 0
    print(f"{name} [{rel.split('/')[-1]}]: {status} rc={r.returncode} {failed[:2]} | {last[:90]} | restored sha256 ok={ok}")
print(f"SUMMARY killed {killed} of {len(MUTANTS)}")
