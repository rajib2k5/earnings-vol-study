"""p02: does a pure SELECT rewrite a Dolt store (claim 1c), and does guard() see writes (claim 1b)?

  uv run python docs/validation/probes/m1/p02_select_writes_and_guard.py <scratch dir>

Never runs dolt in $VOL_DATA_DIR/dolthub/*. Works on:
  (i)  a throw-away `dolt init` repository in <scratch>/t (private DOLT_ROOT_PATH, metrics off);
  (ii) a `cp -a` copy of the project's earnings MIRROR in <scratch>/mirror_copy.
The command is the one the milestone page names: dolt sql -r csv -q "SELECT HASHOF('HEAD')".
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from earnings_vol import config
from earnings_vol.ingest import dolt


def sha_tree(repo: Path) -> dict:
    out = {}
    for p in sorted((repo / ".dolt").rglob("*")):
        if p.is_file():
            out[str(p.relative_to(repo / ".dolt"))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def env_for(scratch: Path) -> dict:
    root = scratch / "dolt_root"
    (root / ".dolt").mkdir(parents=True, exist_ok=True)
    (root / ".dolt" / "config_global.json").write_text(json.dumps(
        {"metrics.disabled": "true", "user.name": "probe", "user.email": "probe@localhost"}))
    return {**os.environ, "DOLT_ROOT_PATH": str(root), "DOLT_DISABLE_EVENT_FLUSH": "1"}


def select_probe(repo: Path, env: dict, label: str):
    s0, h0 = dolt.stat_fingerprint(repo), sha_tree(repo)
    r = subprocess.run(["dolt", "sql", "-r", "csv", "-q", "SELECT HASHOF('HEAD')"], cwd=repo, env=env,
                       capture_output=True, text=True)
    s1, h1 = dolt.stat_fingerprint(repo), sha_tree(repo)
    print(f"[{label}] rc={r.returncode} stdout={r.stdout.strip()[:60]!r}")
    print(f"[{label}] stat-changed: {dolt.diff_fingerprints(s0, s1)}")
    print(f"[{label}] bytes-changed (sha256, every file): {sorted(k for k in h0.keys() | h1.keys() if h0.get(k) != h1.get(k))}")
    return s0, s1


def main():
    scratch = Path(sys.argv[1]).resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    env = env_for(scratch)

    # (i) throw-away repository
    t = scratch / "t"
    if t.exists():
        shutil.rmtree(t)
    t.mkdir()
    run = lambda *a: subprocess.run(["dolt", *a], cwd=t, env=env, check=True, capture_output=True)  # noqa: E731
    run("init")
    run("sql", "-q", "CREATE TABLE x (d date primary key, v decimal(5,4)); INSERT INTO x VALUES ('2025-10-30', 0.2678)")
    run("add", ".")
    run("commit", "-m", "fixture")
    select_probe(t, env, "throwaway")

    # (ii) a copy of the earnings mirror (never the shared clone)
    src = config.cache_dir() / "dolt_mirror" / "earnings"
    dst = scratch / "mirror_copy"
    if dst.exists():
        shutil.rmtree(dst)
    subprocess.run(["cp", "-a", str(src), str(dst)], check=True)
    select_probe(dst, env, "mirror-copy")

    # (1b) guard() with the throw-away repo as the "shared" clone: a SELECT inside must raise.
    for lbl, body in [("SELECT inside guard", lambda: subprocess.run(
            ["dolt", "sql", "-r", "csv", "-q", "SELECT 1"], cwd=t, env=env, capture_output=True)),
            ("nothing inside guard", lambda: None)]:
        try:
            with dolt.guard(t, dst):
                body()
            print(f"[guard] {lbl}: no error")
        except dolt.DoltWriteError as e:
            print(f"[guard] {lbl}: DoltWriteError: {str(e)[:120]}")

    # (1b) mirror content changes: a hashed file and an unhashed (size-only) file, same size.
    def same_size_flip(p: Path):
        b = bytearray(p.read_bytes())
        b[-1] ^= 0x01
        p.write_bytes(bytes(b))

    for rel in ("noms/manifest", next(str(p.relative_to(dst / ".dolt")) for p in sorted((dst / ".dolt" / "noms").iterdir())
                                      if p.is_file() and len(p.name) == 32 and not p.name.startswith("vvvv"))):
        f = dst / ".dolt" / rel
        orig = f.read_bytes()
        try:
            with dolt.guard(t, dst):
                same_size_flip(f)
            print(f"[guard] same-size byte flip in mirror {rel}: NOT DETECTED")
        except dolt.DoltWriteError as e:
            print(f"[guard] same-size byte flip in mirror {rel}: DoltWriteError ({'mirror' in str(e)})")
        finally:
            f.write_bytes(orig)

    # What is hashed and what is only sized in the real mirror?
    cf = dolt.content_fingerprint(dst)
    print("[content_fingerprint] hashed:", sorted(k for k, v in cf.items() if v[1]))
    print("[content_fingerprint] size-only:", sorted(k for k, v in cf.items() if not v[1]))
    shutil.rmtree(dst)


if __name__ == "__main__":
    main()
