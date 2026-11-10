"""Hand mutants for the Cboe VX* cross-check's tests (docs/validation/vx-ledger.md §4).

    .venv/bin/python docs/validation/probes/vx/mutants.py <scratch folder>

Copies the working tree (without .venv and app/node_modules) to <scratch folder>/repo, runs each test module once
unmutated (it must pass), then for each mutant: applies it to the copy, runs the module that pins it with
PYTHONPATH=<copy>/src (the venv's editable install would otherwise load the real tree), expects a failure, restores
the file and compares its SHA-256 with the original. Nothing in the real tree is written.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]

STATS = "src/earnings_vol/stats/vx_crosscheck.py"
CBOE = "src/earnings_vol/ingest/cboe.py"
LIC = "tools/licensing/check_data_files.py"
RN = "tools/report_numbers.py"
T_STATS, T_CBOE, T_LIC, T_RN = ("tests/test_vx_crosscheck.py", "tests/test_ingest_cboe.py",
                                "tests/test_repo_data_files.py", "tests/test_report_numbers.py")

# (id, file, test module, [(old, new), ...]); each old string must occur exactly once
MUTANTS = [
    ("V01", STATS, T_STATS, [('            raise ValueError(f"{d} is not a session of the grid")', "            continue")]),
    ("V02", STATS, T_STATS, [("        out[:-lag] = v[lag:]", "        out[lag:] = v[:-lag]")]),
    ("V03", STATS, T_STATS, [("& (a > 0) & (b > 0)", "& (a >= 0) & (b >= 0)")]),
    ("V04", STATS, T_STATS, [('changes[changes["gap"] == 1]', 'changes[changes["gap"] <= 2]')]),
    ("V05", STATS, T_STATS, [("rng.integers(0, n - block + 1, size=(reps, nb))", "rng.integers(0, n, size=(reps, nb))"),
                             ("idx = (s[:, :, None] + np.arange(block))", "idx = ((s[:, :, None] + np.arange(block)) % n)")]),
    ("V06", STATS, T_STATS, [(".reshape(len(s), nb * block)[:, :n]", ".reshape(len(s), nb * block)")]),
    ("V07", STATS, T_STATS, [('"slope": vxy / vxx', '"slope": vxy / vyy')]),
    ("V08", STATS, T_STATS, [("    out = (vs[j1] + vs[j2]) / 2", "    out = vs[j1]")]),
    ("V09", STATS, T_STATS, [("        med = weighted_median(s, wc)", "        med = (wc * s).sum(axis=1) / wc.sum(axis=1)")]),
    ("V10", STATS, T_STATS, [('    return float(np.mean(d_vx)) / den if den != 0 else float("nan")',
                              "    return float(np.mean(np.asarray(d_vx) / np.asarray(d_ours)))")]),
    ("V11", STATS, T_STATS, [('return "pass" if r > BAR_I_MIN_R else "fail"', 'return "pass" if r >= BAR_I_MIN_R else "fail"')]),
    ("V12", STATS, T_STATS, [("BAR_IV_RANGE = (0.8, 1.2)", "BAR_IV_RANGE = (0.8, 1.25)")]),
    ("V13", STATS, T_STATS, [("if k != 0 and r_by_lag[k] > r_by_lag[0]", "if k != 0 and r_by_lag[k] >= r_by_lag[0]")]),
    ("V14", STATS, T_STATS, [("termstructure.interpolate(expiries, horizon, max_extrap)",
                              "termstructure.interpolate(expiries, horizon, 10**6)"),
                             ("elif len(expiries) == 1 and abs(horizon - expiries[0].tau) <= max_extrap:",
                              "elif len(expiries) == 1:")]),
    ("V15", STATS, T_STATS, [("    if best in (measurable[0], measurable[-1]):", "    if best == measurable[0]:")]),
    ("V16", STATS, T_STATS, [("    fin = v[np.isfinite(v)]", "    fin = v")]),
    ("V17", STATS, T_STATS, [("a[idx].mean(axis=1) / den", "den / a[idx].mean(axis=1)")]),
    ("V18", STATS, T_STATS, [('return "pass" if max_abs_dev <= tolerance else "fail"',
                              'return "pass" if max_abs_dev < tolerance else "fail"')]),
    ("V19", STATS, T_STATS, [("    if left == 0:", "    if left < n:")]),
    ("C01", CBOE, T_CBOE, [("    if symbol not in SYMBOLS:", "    if False:")]),
    ("C02", CBOE, T_CBOE, [("    return resp is None or resp.status_code == 429 or resp.status_code >= 500",
                            "    return True")]),
    ("C03", CBOE, T_CBOE, [("for attempt in range(1 + MAX_RETRIES):", "for attempt in range(2 + MAX_RETRIES):"),
                           ("or attempt == MAX_RETRIES:", "or attempt == MAX_RETRIES + 1:"),
                           ("sleep(RETRY_WAIT_SECONDS[attempt])", "sleep(RETRY_WAIT_SECONDS[min(attempt, 1)])")]),
    ("C04", CBOE, T_CBOE, [('    if out["date"].duplicated().any():',
                            '    out = out.drop_duplicates("date")\n    if False:')]),
    ("C05", CBOE, T_CBOE, [('"%m/%d/%Y"', '"%d/%m/%Y"')]),
    # the address is built from chr(64), so no e-mail address is written in this file
    ("C06", CBOE, T_CBOE, [('USER_AGENT = "earnings-vol-study/0.5 (research; +https://github.com/rajib2k5/earnings-vol-study)"',
                            'USER_AGENT = "earnings-vol-study/0.5 (research; +https://github.com/rajib2k5/earnings-vol-study)'
                            ' owner" + chr(64) + "example.invalid"')]),
    ("L01", LIC, T_LIC, [("            out += [f\"{path}: {p}\" for p in aggregate_shape_problems(doc, "
                          "AGGREGATE_JSON[path[len(DERIVED_DIR):]])]", "            out += []")]),
    ("L02", LIC, T_LIC, [("            if len(x) > AGG_MAX_LIST:", "            if False:")]),
    ("L03", LIC, T_LIC, [("            if dated:", "            if False:")]),
    ("L04", LIC, T_LIC, [("    if numbers > AGG_MAX_NUMBERS:", "    if False:")]),
    ("R19", RN, T_RN, [('         fails_i == ["GOOGL", "IBM", "pooled"]),', "         True),")]),
    ("R20", RN, T_RN, [('         iv["events"]["timing_status_counts"] == {"not_checked": iv["events"]["n_events_five_names"]}),',
                        "         True),")]),
    ("R21", RN, T_RN, [('         vh["maturity"]["identification"]["status"] == "identified"\n'
                        '         and vh["maturity"]["identification"]["horizon"] == 21 == cm30_sessions),',
                        "         True),")]),
    ("R22", RN, T_RN, [('    same("VX bar iv\'s primary sample / meta.json sample size",',
                        '    (lambda *a: None)("VX bar iv\'s primary sample / meta.json sample size",')]),
    ("R23", RN, T_RN, [('    if vxd["inputs"]["events_sha256"] != d["events_sha256"]:', "    if False:")]),
    ("R24a", RN, T_RN, [('         vxd["secondary"]["pooled"]["slope"] < 1 < vxd["secondary"]["pooled"]["block20"]'
                         '["reverse_slope_reciprocal"]["lo"]\n', "         True\n")]),
    ("R24b", RN, T_RN, [('         and {nm for nm in names if vxd["secondary"][nm]["reverse_slope_reciprocal"] < 1} == '
                         '{"AAPL", "AMZN"}\n', "         and True\n")]),
]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run(copy: Path, test: str) -> int:
    env = {**os.environ, "PYTHONPATH": str(copy / "src")}
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", test],
                       cwd=copy, env=env, capture_output=True, text=True)
    return r.returncode


def main() -> int:
    copy = Path(sys.argv[1]).resolve() / "repo"
    subprocess.run(["rsync", "-a", "--delete", "--exclude", ".venv", "--exclude", "app/node_modules",
                    f"{REPO}/", f"{copy}/"], check=True)
    for test in sorted({m[2] for m in MUTANTS}):
        code = run(copy, test)
        print(f"baseline {test}: exit {code}")
        if code != 0:
            print("FAIL: the unmutated module does not pass")
            return 1
    killed = 0
    for mid, rel, test, edits in MUTANTS:
        path = copy / rel
        before, text = sha(path), path.read_text()
        new = text
        for old, rep in edits:
            if new.count(old) != 1:
                print(f"{mid}: the mutant's text occurs {new.count(old)} times in {rel}; not applied")
                return 1
            new = new.replace(old, rep)
        path.write_text(new)
        code = run(copy, test)
        path.write_text(text)
        ok = sha(path) == before
        killed += code != 0
        print(f"{mid} {rel} -> {test}: exit {code} ({'killed' if code else 'SURVIVED'}); restore sha256 ok={ok}")
        if not ok:
            return 1
    print(f"{killed} of {len(MUTANTS)} killed")
    return 0 if killed == len(MUTANTS) else 1


if __name__ == "__main__":
    sys.exit(main())
