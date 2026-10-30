"""p10: the header mutants of tests/test_report_numbers.py (R01-R11, R05c), two of this review's own (X1, X2), and
the app mutants A1-A7 of app/src/lib/studyContent.test.ts, each applied to a SCRATCH COPY, its tests run, the file
restored and its SHA-256 compared with the original.

    python docs/validation/probes/m5/p10_mutants.py <scratch repo copy> <python> [py|app|all]

py: `<python> -m pytest -q -p no:cacheprovider tests/test_report_numbers.py` in the copy (baseline must pass).
app: `node_modules/.bin/vitest run src/lib/studyContent.test.ts src/lib/StudySections.test.tsx src/App.test.tsx`.
A mutant is KILLED when the run's exit code is not 0. Each replacement must match exactly once, or the mutant is
reported INVALID (not counted).
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

RN = "tools/report_numbers.py"
SC = "app/src/lib/studyContent.ts"
SS = "app/src/lib/StudySections.tsx"

PY = [
    ("R01 fnum writes an ASCII hyphen", RN, "    return _minus(s)\n\n\ndef fsigned", "    return s\n\n\ndef fsigned"),
    ("R02 fp: 3 sig digits below 0.01", RN, 'return f"{p:.2g}" if p < 0.01 else f"{p:.3g}"', 'return f"{p:.3g}"'),
    ("R03 fpct keeps one decimal", RN, "def fpct(x: float, nd: int = 2)", "def fpct(x: float, nd: int = 1)"),
    ("R04 --check compares the report only", RN,
     "stale = [p for p, text in files.items() if (root / p).read_text() != text]",
     "stale = [p for p, text in files.items() if p == REPORT_OUT and (root / p).read_text() != text]"),
    ("R05 render's unknown-key guard removed", RN,
     '        raise KeyError(f"{where}: unknown number(s) {\', \'.join(missing)}")', "        pass"),
    ("R05c guard removed and lookup tolerant", RN,
     '''    if missing:
        raise KeyError(f"{where}: unknown number(s) {', '.join(missing)}")
    return PLACEHOLDER.sub(lambda m: nums[m.group(1)][0], template)''',
     '''    return PLACEHOLDER.sub(lambda m: nums.get(m.group(1), (m.group(0),))[0], template)'''),
    ("R06 H1 from the mean-adjusted twin", RN,
     '    rows = {h: primary(r, h) for h in ("H1", "H2", "H3", "H4", "H5", "H6", "H7")}\n',
     '    rows = {h: primary(r, h) for h in ("H1", "H2", "H3", "H4", "H5", "H6", "H7")}\n'
     '    rows["H1"] = one(r[(r.hypothesis == "H1") & (r.statistic == "twoway_date_t") & (r.adjustment == "mean")], "twin")\n'),
    ("R07 lookups.left = required", RN, 'fint(LOOKUPS_REQUIRED - done)', 'fint(LOOKUPS_REQUIRED)'),
    ("R08 cross_check skips H5's Holm p", RN,
     '        same(f"{h} p_holm results/drivers.json", rows[h].p_holm, t["p_holm"], 5e-5)',
     '        if h != "H5":\n            same(f"{h} p_holm results/drivers.json", rows[h].p_holm, t["p_holm"], 5e-5)'),
    ("R09 prose_check skips H2's cut", RN, "cut.p_holm > 0.05 and pg_h2 <= 0.05", "True and pg_h2 <= 0.05"),
    ("R10 stage comparison skipped", RN, "    if left + done != LOOKUPS_REQUIRED:", "    if False:"),
    ("R11 pct_fall = -estimate", RN, "fpct(1 - math.exp(h1.estimate), 1)", "fpct(-h1.estimate, 1)"),
    ("X1 prose_check: b's interval-holds-1 claim dropped", RN,
     '("H7: b\'s interval holds 1, b below 1", b.ci_lo < 1 < b.ci_hi and b.estimate < 1)',
     '("H7: b\'s interval holds 1, b below 1", True)'),
    ("X2 cross_check: H7 F comparison dropped", RN,
     '    same("H7 F results/implied_vs_realised.json", rows["H7"].stat, reg["wald_f"], 5e-5)\n', ''),
]
APP = [
    ("A1 StudySections drops the pages line", SS,
     "            {m.pages.length > 0 && <span className=\"sub\">{` · pages: ${m.pages.join(', ')}`}</span>}\n", ""),
    ("A2 a page label misspelt", SC, "pages: ['Drivers', 'Implied vs realised']", "pages: ['Drivers', 'Implied vs Realised']"),
    ("A3 milestone 5 marked done", SC, "status: 'in progress', pages: [] }", "status: 'done', pages: [] }"),
    ("A4 milestone 5 removed", SC,
     "  { id: 5, title: 'Report and polish: the written report (a draft for the owner), screenshots and the README', status: 'in progress', pages: [] },\n", ""),
    ("A5 About says synthetic again", SC,
     "The 3D view draws the exported terrain file (each company’s mean abnormal log IV by event day).",
     "The 3D preview is a labelled synthetic shape, not data."),
    ("A6 3D view under two milestones", SC, "pages: ['IV measures'] }", "pages: ['IV measures', '3D view'] }"),
    ("A7 Heatmap under none", SC, "pages: ['Results', 'Crush paths', 'Heatmap', '3D view'] }",
     "pages: ['Results', 'Crush paths', '3D view'] }"),
]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run(cmd, cwd) -> tuple[int, str]:
    env = {**os.environ, "PYTHONPATH": str(Path(cwd) / "src") if (Path(cwd) / "src").exists() else ""}
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env, timeout=900)
    tail = [l for l in (p.stdout + p.stderr).splitlines() if l.strip()]
    summ = [l for l in tail if " passed" in l or " failed" in l or "Tests " in l or "error" in l.lower()][-2:]
    return p.returncode, " | ".join(s.strip()[:150] for s in summ)


def main() -> int:
    repo, py, which = Path(sys.argv[1]), sys.argv[2], (sys.argv[3] if len(sys.argv) > 3 else "all")
    suites = []
    if which in ("py", "all"):
        suites.append(("py", PY, [py, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_report_numbers.py"], repo))
    if which in ("app", "all"):
        suites.append(("app", APP, ["node_modules/.bin/vitest", "run", "src/lib/studyContent.test.ts",
                                    "src/lib/StudySections.test.tsx", "src/App.test.tsx"], repo / "app"))
    killed = total = 0
    for name, muts, cmd, cwd in suites:
        rc, s = run(cmd, cwd)
        print(f"[{name}] baseline rc {rc}: {s}")
        if rc != 0:
            print("baseline fails: stop")
            return 2
        for label, rel, old, new in muts:
            f = repo / rel
            orig, h0 = f.read_text(), sha(f)
            if orig.count(old) != 1:
                print(f"INVALID {label}: pattern found {orig.count(old)} times")
                continue
            f.write_text(orig.replace(old, new, 1))
            try:
                rc, s = run(cmd, cwd)
            finally:
                f.write_text(orig)
            ok = sha(f) == h0
            total += 1
            killed += rc != 0
            print(f"{'KILLED  ' if rc else 'SURVIVED'} {label}: rc {rc} ({s}); restore sha256 ok={ok}")
    print(f"SUMMARY killed {killed} of {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
