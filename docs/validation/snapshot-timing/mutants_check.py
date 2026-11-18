"""Hand mutants of the snapshot-timing check (row 2 of the validation router): each must fail a test in
tests/test_snapshot_timing.py. The module is restored after each mutant and its SHA-256 checked at the end.

    uv run python -I docs/validation/snapshot-timing/mutants_check.py      # exit 0 when every mutant is caught
"""

import hashlib
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PY = sys.executable
F, T = "src/earnings_vol/stats/snapshot_timing.py", "tests/test_snapshot_timing.py"
M = [
    ("T1 classify: and -> or", 'off = s["gap_bp"] > GAP_BP and s["ratio"] > RATIO', 'off = s["gap_bp"] > GAP_BP or s["ratio"] > RATIO'),
    ("T2 classify: no late", 'return "late" if s["slope"] >= LATE_SLOPE else "off"', 'return "off"'),
    ("T3 classify: no unknown", '    if s["n"] < MIN_FIRMS:\n        return "unknown"\n', ""),
    ("T4 day_stats: slope sign", "slope = float(xc @ (g - g.mean()) / sxx)", "slope = float(-(xc @ (g - g.mean())) / sxx)"),
    ("T5 day_stats: ratio inverted", '"ratio": gap_bp / ret_bp if ret_bp > 0', '"ratio": ret_bp / gap_bp if gap_bp > 0'),
    ("C1 P allows off day +1", "lo, hi, need_close, need_usable = r.s_0, r.s_p1, [r.s_p1], [r.s_0]",
     "lo, hi, need_close, need_usable = r.s_0, r.s_p1, [], [r.s_0, r.s_p1]"),
    ("C2 O sign", '"y": ((xt - xa) - (xc - xt)) / 2.0', '"y": ((xt - xa) + (xc - xt)) / 2.0'),
    ("C3 crush A sign", 'return {P: -k["k0"] / n, A: -k["km1"] / n}', 'return {P: -k["k0"] / n, A: k["km1"] / n}'),
    ("C4 runup no baseline", 'return {A: k["km1"] / n, O: -k["s_sum"] / n}', 'return {A: k["km1"] / n}'),
    ("C5 tost <= alpha", 'if lo["p_up"] < alpha and hi["p_dn"] < alpha:', 'if lo["p_up"] <= alpha and hi["p_dn"] <= alpha:'),
    ("C6 gate ignored", 'return {h: ("UNCLEAR" if v == "SMALL" and rejected[series_of[h]] else v)',
     'return {h: (v if v == "SMALL" and rejected[series_of[h]] else v)'),
    ("C7 restricted fit sign", "bt = b - A @ R.T @ np.linalg.solve(R @ A @ R.T, R @ b - r)",
     "bt = b + A @ R.T @ np.linalg.solve(R @ A @ R.T, R @ b - r)"),
    ("C8 identity minus", 'vector(fit, {f"{series}.C:off0": 1.0, f"{series}.P:off0": 1.0})',
     'vector(fit, {f"{series}.C:off0": 1.0, f"{series}.P:off0": -1.0})'),
    ("C9 O allows off t-1", 'if a < first or cls(a) != "close"', 'if a < first or cls(a) not in USABLE'),
    ("C10 persist sign", 'return {O: (k["k10"] - k["s_sum"]) / n}', 'return {O: (k["s_sum"] - k["k10"]) / n}'),
    ("C11 sigma key ignored", 'k = r.event_id if key == "event_id" else r.firm', "k = r.firm"),
    ("C12 dm sign in P/A/C", '"dm": m1 - m0', '"dm": m0 - m1'),
    ("C13 WCR without the null", "        _, e = restricted(fit, w, c0)\n", "        e = fit[\"f\"][\"u\"]\n"),
    ("C14 p_up direction", '"p_up": float(np.mean(s >= stat))', '"p_up": float(np.mean(s <= stat))'),
    ("C15 lines swapped", 'return {"lo": (w, -line), "hi": (w, line)}', 'return {"lo": (w, line), "hi": (w, -line)}'),
    ("C16 interval sign", "row[f\"ci{int(lvl * 100)}\"] = [float(est[i] - hi_q * se[i]), float(est[i] - lo_q * se[i])]",
     "row[f\"ci{int(lvl * 100)}\"] = [float(est[i] + lo_q * se[i]), float(est[i] + hi_q * se[i])]"),
    ("C17 bootstrap U sign", 'U = v[:, :, None] * prep["C"][None] - np.einsum', 'U = v[:, :, None] * prep["C"][None] + np.einsum'),
    ("C18 weekday drop always", "        if np.linalg.matrix_rank(Xd) == k:\n", "        if True:\n"),
    ("C19 LARGE needs both sides", 'if lo["p_dn"] < alpha or hi["p_up"] < alpha:', 'if lo["p_dn"] < alpha and hi["p_up"] < alpha:'),
]

orig = (REPO / F).read_bytes()
sha = hashlib.sha256(orig).hexdigest()
bad = 0
for name, old, new in M:
    t = orig.decode()
    if t.count(old) != 1:
        print(f"SKIP     {name}: the target occurs {t.count(old)} times")
        bad += 1
        continue
    (REPO / F).write_text(t.replace(old, new))
    try:
        r = subprocess.run([PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", T], cwd=REPO, capture_output=True,
                           text=True)
    finally:
        (REPO / F).write_bytes(orig)
    bad += r.returncode == 0
    fails = [ln.split("::")[-1].split(" ")[0] for ln in r.stdout.splitlines() if ln.startswith("FAILED")]
    print(f"{'caught' if r.returncode else 'SURVIVED':8} {name}: {fails}")
ok = hashlib.sha256((REPO / F).read_bytes()).hexdigest() == sha
print("restored:", ok)
sys.exit(1 if bad or not ok else 0)
