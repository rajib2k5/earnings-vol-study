"""p01: has anything written into the shared Dolt clones? (claim 1a)

Stat only: never runs dolt, never opens a file in the clone for writing.

  uv run python docs/validation/probes/m1/p01_shared_clone_stat.py snapshot <out.json>
  uv run python docs/validation/probes/m1/p01_shared_clone_stat.py compare <before.json>

`snapshot` prints the newest mtimes and saves the stat fingerprint (path, size,
mtime_ns) of every entry under each clone's .dolt/. `compare` diffs the current
fingerprint against a saved one.
"""
import json
import sys
from datetime import datetime, timezone

from earnings_vol import config
from earnings_vol.ingest import dolt

M0_COMMIT = datetime(2026, 10, 28, 19, 44, 27, tzinfo=timezone.utc)  # 3636e98, 14:44:27 -0500


def fp():
    return {r: dolt.stat_fingerprint(config.dolt_repo(r)) for r in ("earnings", "options")}


def main():
    cmd, path = sys.argv[1], sys.argv[2]
    now = fp()
    if cmd == "snapshot":
        for repo, f in now.items():
            newest = sorted(f.items(), key=lambda kv: kv[1][1], reverse=True)[:4]
            for rel, (size, ns) in newest:
                t = datetime.fromtimestamp(ns / 1e9, timezone.utc)
                print(f"{repo:9s} {t.isoformat()} after_M0_commit={t > M0_COMMIT} {size:>6} {rel}")
            print(f"{repo:9s} entries={len(f)}")
        with open(path, "w") as fh:
            json.dump({r: {k: list(v) for k, v in f.items()} for r, f in now.items()}, fh)
    else:
        before = json.load(open(path))
        for repo in now:
            b = {k: tuple(v) for k, v in before[repo].items()}
            print(repo, "changed:", dolt.diff_fingerprints(b, now[repo]))


if __name__ == "__main__":
    main()
