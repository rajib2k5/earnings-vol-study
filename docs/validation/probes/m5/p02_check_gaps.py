"""p02: edits that `tools/report_numbers.py --check` should catch, run on fresh scratch copies of its inputs.

    uv run --frozen --offline --no-sync python docs/validation/probes/m5/p02_check_gaps.py <scratch dir>

For each scenario: copy the inputs (as tests/test_report_numbers.py does), apply the edit, then
  1. `--check --root <copy>`  (the files on disk are now stale or contradicted: should fail),
  2. render (`--root <copy>`, no --check): the data path a maintainer takes after new data arrive,
  3. `--check --root <copy>` again,
and print the sentence the rendered files now contain. A scenario where step 2 succeeds and step 3 passes while the
printed sentence is false is a contradiction --check does not catch. S0 is the control (a stale number in a block).
The tool under test is run as a subprocess from the real repository (read-only); only the copies are written.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[4]
TOOL = REPO / "tools/report_numbers.py"
INPUTS = ["data/derived/results.parquet", "research/prototypes/rhobar_crush.out.txt", "README.md", "docs/prfaq.md",
          "docs/report/earnings-vol-report.md"]


def fresh(base: Path, name: str) -> Path:
    d = base / name
    if d.exists():
        shutil.rmtree(d)
    for rel in INPUTS:
        (d / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / rel, d / rel)
    shutil.copytree(REPO / "app/public/data", d / "app/public/data")
    shutil.copytree(REPO / "docs/report/templates", d / "docs/report/templates")
    return d


def run(root: Path, *args: str) -> tuple[int, str]:
    p = subprocess.run([sys.executable, str(TOOL), "--root", str(root), *args], capture_output=True, text=True,
                       env={"PATH": "/usr/bin:/bin", "VOL_DATA_DIR": str(root / "no-vol-data")})
    return p.returncode, (p.stdout + p.stderr).strip().splitlines()[-1][:160] if (p.stdout + p.stderr).strip() else ""


def edit_parquet(root: Path, mask, col: str, value) -> None:
    f = root / "data/derived/results.parquet"
    r = pd.read_parquet(f)
    i = r.index[mask(r)]
    assert len(i) >= 1, (col, len(i))
    r.loc[i, col] = value
    r.to_parquet(f)


def edit_json(root: Path, kind: str, fn) -> None:
    f = root / f"app/public/data/{kind}.json"
    env = json.loads(f.read_text())
    fn(env["data"])
    f.write_text(json.dumps(env))


def grep(root: Path, rel: str, pat: str) -> str:
    t = (root / rel).read_text()
    m = re.search(pat, t, re.S)
    return re.sub(r"\s+", " ", m.group(0))[:220] if m else f"(no match for {pat!r})"


def s0(d):
    """control: a stale number inside the README block"""
    f = d / "README.md"
    f.write_text(f.read_text().replace("| 347 | −0.199 | 5.8e−23", "| 347 | −0.198 | 5.8e−23", 1))
    return None


def s1(d):
    """H2's run-up turns negative (same floor p): "IV is high before the news", "every season mean is positive" """
    edit_parquet(d, lambda r: (r.hypothesis == "H2") & (r.adjustment == "market") & (r.family == "event_test"),
                 "estimate", -0.231896)
    edit_json(d, "tests", lambda x: [row.update(estimate=-0.2319) for row in x["rows"]
                                     if row["hypothesis"] == "H2" and row["adjustment"] == "market"])
    return ("docs/report/earnings-vol-report.md", r"\*\*IV is high before the news\.\*\*.{0,120}baseline\.")


def s2(d):
    """b at day -2 falls below b at day -1: "which may inflate E a little" becomes backwards"""
    edit_parquet(d, lambda r: (r.model_id == "implied_realised_m2") & (r.term == "b"), "estimate", 0.60)
    return ("docs/report/earnings-vol-report.md", r"With E read one session\s+earlier, b is .{0,120}a little\.")


def s3(d):
    """the sample grows to 365: "inside the draft's 330-360" """
    edit_json(d, "meta", lambda x: x["sample"].update(n_events=365))
    def fun(x):
        x["steps"][-1]["n_events"] = 365
        x["steps"][-1]["n_removed"] = x["steps"][-2]["n_events"] - 365
    edit_json(d, "sample_funnel", fun)
    edit_parquet(d, lambda r: (r.hypothesis == "H1") & (r.role == "primary") & (r.family == "event_test"), "n", 365)
    return ("docs/prfaq.md", r"Confirmed as predicted: the sample size \(.{0,60}\)")


def s4(d):
    """tests.json says H1's G1 rate is 7.00% (above the 6.30% bar) but keeps pass: true; results.parquet: 4.60%"""
    edit_json(d, "tests", lambda x: [c.update(rejection_rate=0.07) for c in x["g1"]["calibrated"] if c["hypothesis"] == "H1"])
    return ("docs/report/earnings-vol-report.md", r"\| Primary rejects under the null.{0,200}\n\| Verdict \| \S+")


def s5(d):
    """one look-up turns ambiguous: the list "16 confirmed, 2 corrected, 1 ..., 1 inferred" no longer sums to 20"""
    edit_json(d, "sample_funnel", lambda x: x["timing_status_counts"].update(confirmed=15, ambiguous=1))
    return ("docs/report/earnings-vol-report.md", r"\*\*Timing labels\.\*\* .{0,170}inferred\)\.")


def s6(d):
    """a placeholder typo with a capital letter: "an unknown key is an error, so a template cannot render with a hole" """
    f = d / "docs/report/templates/readme-results.md"
    f.write_text(f.read_text().replace("(two-way t {{h2.twoway_t}})", "(two-way t {{H2.twoway_t}})", 1))
    return ("README.md", r"two-way t \S+\)")


def s7(d):
    """rho-bar without the top 10 dates drops to 0.02: "spread over most dates" is then false """
    f = d / "research/prototypes/rhobar_crush.out.txt"
    f.write_text(f.read_text().replace("rho-bar without the top 10 dates: 0.1920", "rho-bar without the top 10 dates: 0.0200"))
    return ("docs/report/earnings-vol-report.md", r"It is spread over most dates \(.{0,40}\)")


def s8(d):
    """the two-way season t that says "the direction is not in doubt" becomes 1.20 (p 0.27)"""
    m = lambda r: (r.hypothesis == "H2") & (r.statistic == "twoway_season_t") & (r.adjustment == "market")
    edit_parquet(d, m, "stat", 1.20)
    edit_parquet(d, m, "p_value", 0.27)
    return ("docs/report/earnings-vol-report.md", r"The direction is not in doubt: .{0,90}\(p [^)]*\)")


def main() -> int:
    base = Path(sys.argv[1])
    base.mkdir(parents=True, exist_ok=True)
    uncaught = 0
    for name, fn in [("S0", s0), ("S1", s1), ("S2", s2), ("S3", s3), ("S4", s4), ("S5", s5), ("S6", s6), ("S7", s7),
                     ("S8", s8)]:
        d = fresh(base, name)
        where = fn(d)
        rc1, out1 = run(d, "--check")
        print(f"{name} {fn.__doc__ or ''}")
        print(f"   1. --check on the edited copy: rc {rc1}  {out1}")
        if where is None:
            continue
        rc2, out2 = run(d)
        rc3, out3 = run(d, "--check")
        print(f"   2. render: rc {rc2}  {out2}")
        print(f"   3. --check after render: rc {rc3}  {out3}")
        print(f"   rendered text now: {grep(d, *where)}")
        if rc2 == 0 and rc3 == 0:
            uncaught += 1
    print(f"scenarios whose contradicted sentence renders and passes --check: {uncaught} of 8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
