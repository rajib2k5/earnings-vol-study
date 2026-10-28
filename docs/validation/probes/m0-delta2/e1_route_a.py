"""Delta-2 probe e1 (claim 1): does ADR 0002's route-(a) table reproduce, and what does the re-read assume?

Part A. Re-runs research/prototypes/route_a_vs_b.py at --nu=3 and --nu=1e9 (same interpreter, no edits) and
byte-compares the concatenated stdout with research/prototypes/route_a_vs_b.out.txt. Then checks every number that
ADR 0002 :361-368 (route table), :384-387 (re-read counts) and :405-408 (coarse selection) quotes against the
re-run output. Also runs docs/validation/probes/m0-delta/d4_default_gap_selection.py at --nu=3 and checks that its C0
control line equals route_a_vs_b's to the last digit (the ADR says it does).

Part B. The sim assumes "the re-read is right" (route_a_vs_b.py:111). ADR 0002 :349 says the re-read "can only fix
misreadings". Here the re-read errs too: (i) an independent 1% misread on every re-read; (ii) a primed re-reader who,
on a gap contradiction of a CORRECT label, adopts the gap's side 10% of the time. Falsifier: with the re-read always
right the extension must reproduce the ADR's 0.85 / 0.67 / 0.11 (t3).

Run from the repository root: .venv/bin/python docs/validation/probes/m0-delta2/e1_route_a.py
"""
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
SIM = ROOT / "research/prototypes/route_a_vs_b.py"
OUT = ROOT / "research/prototypes/route_a_vs_b.out.txt"
D4 = ROOT / "docs/validation/probes/m0-delta/d4_default_gap_selection.py"
fails = []

# ---------- Part A ----------
runs = [subprocess.run([sys.executable, str(SIM), f"--nu={nu}"], capture_output=True, text=True, cwd=ROOT)
        for nu in ("3", "1e9")]
for r in runs:
    assert r.returncode == 0, r.stderr
fresh = runs[0].stdout + "\n=========\n" + runs[1].stdout + "\n=========\n"
committed = OUT.read_text()
same = fresh.strip() == committed.strip()
if not same:  # tolerate only separator/whitespace differences
    same = re.sub(r"\s+", " ", fresh.replace("=========", "")).strip() == \
        re.sub(r"\s+", " ", committed.replace("=========", "")).strip()
print("A1 re-run equals route_a_vs_b.out.txt:", same)
if not same:
    fails.append("A1")


def block(text, header_prefix):
    i = text.index(header_prefix)
    return text[i:text.index("\n\n", i) if "\n\n" in text[i:] else len(text)]


def triple(blk, measure):
    line = next(l for l in blk.splitlines() if measure in l and "wrong day 0" in l)
    return re.findall(r"(\d+\.\d+)%", line)[:3]


def lookups(blk):
    return re.search(r"look-ups per sample ([\d.]+)", blk).group(1)


t3, nrm = runs[0].stdout, runs[1].stdout
checks = [
    # (description, text, block header, measure, expected triple or None, expected look-ups or None)
    ("C0 t3 true", t3, "[C0 no check]", "true |J|", ["2.96", "3.01", "3.01"], None),
    ("(a) 1% misread no re-read t3", t3, "[ROUTE (a): not found 0%, misread 1%, gap-triggered re-read off]", "true |J|",
     ["0.99", "1.02", "1.01"], "365.0"),
    ("(a) 1% misread re-read t3", t3, "[ROUTE (a): not found 0%, misread 1%, gap-triggered re-read on]", "true |J|",
     ["0.85", "0.67", "0.11"], "387.6"),
    ("(a) 1% misread re-read normal", nrm, "[ROUTE (a): not found 0%, misread 1%, gap-triggered re-read on]",
     "true |J|", ["0.94", "0.83", "0.23"], "367.8"),
    ("(a) 5% nf 1% misread re-read t3", t3, "[ROUTE (a): not found 5%, misread 1%, gap-triggered re-read on]",
     "true |J|", ["0.95", "0.81", "0.26"], "386.4"),
    ("(a) 5% nf 1% misread re-read normal", nrm, "[ROUTE (a): not found 5%, misread 1%, gap-triggered re-read on]",
     "true |J|", ["1.05", "0.93", "0.37"], "367.6"),
    ("(a) perfect t3", t3, "[ROUTE (a): not found 0%, misread 0%, gap-triggered re-read off]", "true |J|",
     ["0.00", "0.00", "0.00"], "365.0"),
    ("coarse R1 t3", t3, "[DEFAULT R1", "true |J|", ["2.51", "1.96", "0.35"], None),
    ("coarse R1 normal", nrm, "[DEFAULT R1", "true |J|", ["3.04", "2.56", "0.70"], None),
    ("C0 t3 on max(|gB|,|gA|)", t3, "[C0 no check]", "max(|gB|,|gA|)", ["2.97", "3.05", "2.96"], None),
    ("R1 t3 on max(|gB|,|gA|)", t3, "[DEFAULT R1", "max(|gB|,|gA|)", ["2.62", "1.90", "0.31"], None),
]
for desc, txt, hdr, meas, exp, lk in checks:
    b = block(txt, hdr)
    got = triple(b, meas)
    ok = got == exp and (lk is None or lookups(b) == lk)
    print(f"A2 {desc:38s} ADR {exp} {lk or '':6s} run {got} {lookups(b):6s} -> {'OK' if ok else 'MISMATCH'}")
    if not ok:
        fails.append(desc)
rr = sorted(float(lookups(block(txt, h))) - 365 for txt in (t3, nrm) for h in
            [f"[ROUTE (a): not found {f}, misread {m}, gap-triggered re-read on]" for f in ("0%", "5%")
             for m in ("0%", "1%")])
print("A3 re-reads per 365 events, all re-read-on rows (ADR :386 says 1.6-2.8 normal, 20.0-22.6 t3):",
      [round(x, 1) for x in rr])

d4 = subprocess.run([sys.executable, str(D4), "--nu=3"], capture_output=True, text=True, cwd=ROOT)
c0_d4 = next((l for l in d4.stdout.splitlines() if "wrong day 0" in l or "C0" in l), "")
print("A4 d4 --nu=3 rc", d4.returncode, "| first C0-ish line:", c0_d4.strip()[:150])
print("   d4 lines mentioning C0:")
for l in d4.stdout.splitlines():
    if "C0" in l:
        print("     ", l.strip()[:160])

# ---------- Part B: re-read errors (same world as route_a_vs_b.py, nu = 3) ----------
NU = 3.0
R, n = 2000, 365
P_ERR, P_NULL = 0.03, 0.011
rng = np.random.default_rng(20261028)
N = R * n
t_scale = 1 / np.sqrt(NU / (NU - 2))


def tdraw(*shape):
    return rng.standard_t(NU, size=shape) * t_scale


true_amc = rng.random(N) < 0.5
k = np.exp(rng.normal(np.log(2.5), 0.8, N))
J = rng.normal(0, 1, N) * k
scale = np.median(np.abs(tdraw(N, 39)), axis=1)
g = tdraw(N, 8)
g[np.arange(N), np.where(true_amc, 4, 3)] += J
z = np.abs(g) / scale[:, None]
zB, zA = z[:, 3], z[:, 4]
mx = np.maximum(zB, zA)
others = np.delete(z, [3, 4], axis=1).max(axis=1)
lab = np.where(rng.random(N) < P_ERR, ~true_amc, true_amc).astype(int)
is_null = rng.random(N) < P_NULL
lab = np.where(is_null, -1, lab)
nearby = (others >= 6) & (others >= 3 * mx)
truth = true_amc.astype(int)
u_found = rng.random(N)
u_misread = rng.random(N)
_ = rng.normal(0, 0.04, N)
u_re = np.random.default_rng(7).random(N)  # extra, independent stream for the re-read's own error


def contra_of(label):
    zL = np.where(label == 1, zA, zB)
    zO = np.where(label == 1, zB, zA)
    return (label >= 0) & (zO >= 4) & (zO >= 3 * zL)


xs = np.abs(J).reshape(R, n)
terc = ((xs.argsort(1).argsort(1)) * 3 // n).ravel()


def wrong_by_terc(used):
    w = used != truth
    return [round(100 * w[terc == t].mean(), 2) for t in range(3)]


found = np.ones(N, bool)
misread = u_misread < 0.01
pr = np.where(misread, 1 - truth, truth)
trig = contra_of(pr) | nearby
print("\nB  route (a), all found, 1% misread, t3 gaps; re-reads per 365:", round(trig.sum() / R, 1),
      "of which on a correct label:", round((trig & ~misread).sum() / R, 1))
right = np.where(trig, truth, pr)
print("B0 re-read always right (falsifier, ADR 0.85/0.67/0.11):", wrong_by_terc(right))
if wrong_by_terc(right) != [0.85, 0.67, 0.11]:
    fails.append("B0")
ind = np.where(trig, np.where(u_re < 0.01, 1 - truth, truth), pr)
print("B1 re-read has its own 1% misread:                      ", wrong_by_terc(ind))
primed = np.where(trig & ~misread & (u_re < 0.10), 1 - truth, np.where(trig, truth, pr))
print("B2 primed: 10% of gap-contradicted correct labels flip: ", wrong_by_terc(primed))
print("\nRESULT:", "PASS (reproduced)" if not fails else f"FAIL {fails}")
sys.exit(1 if fails else 0)
