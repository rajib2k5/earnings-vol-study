#!/usr/bin/env python3
"""usage: falsify.py <id> <repo-relative file> <old> <new> <probe.py>
Applies ONE exact-string mutation to the real file, runs the probe in the sandbox, restores the original bytes and
verifies SHA-256 equality.  Prints a record (verbatim probe output included)."""
import hashlib, subprocess, sys, tempfile, pathlib
mid, rel, old, new, probe = sys.argv[1:6]
repo = pathlib.Path("/home/rajib2k5/dev/earnings-vol-study")
f = repo / rel
orig = f.read_bytes()
h0 = hashlib.sha256(orig).hexdigest()
assert orig.decode().count(old) == 1, f"old string occurs {orig.decode().count(old)} times"
here = repo / "docs/validation/edgar-egv/probes"
try:
    f.write_bytes(orig.decode().replace(old, new).encode())
    with tempfile.TemporaryDirectory(dir="/tmp/claude-1000/-home-rajib2k5-dev/9fcceee1-9f95-4cb4-9f87-030ec5521894/scratchpad") as pfx:
        r = subprocess.run([str(here / "run_probe.sh"), probe, pfx + "/pc"], capture_output=True, text=True)
finally:
    f.write_bytes(orig)
h1 = hashlib.sha256(f.read_bytes()).hexdigest()
print(f"mutant:        {mid}")
print(f"file:          {rel}")
print(f"mutation:      {old!r}  ->  {new!r}")
print(f"probe:         {probe}")
print(f"sha256 before: {h0}")
print(f"sha256 after:  {h1}   restored_identical={h0 == h1}")
print(f"falsifier_rc:  {r.returncode}")
print("--- stdout (tail) ---"); print("\n".join(r.stdout.splitlines()[-12:]))
print("--- stderr ---"); print(r.stderr)
sys.exit(0 if h0 == h1 else 7)
