"""p11: licence scan of every tracked + untracked (not ignored) file, and the JSON rebuild (claims 10, 11).

  uv run python docs/validation/probes/m1/p11_licence_contract.py <scratch dir>

Prints paths relative to $REPO and the scratch dir as $SCRATCH.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[4]
SELF = "docs/validation/probes/m1/"


def main():
    scratch = Path(sys.argv[1]).resolve()
    files = [f for f in subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=REPO,
                                       capture_output=True, text=True, check=True).stdout.split("\n") if f]
    print("files scanned:", len(files))
    home = b"/" + b"home" + b"/"   # built in pieces so this file itself holds no home path
    pats = {"absolute home path": re.compile(re.escape(home) + rb"[a-z]|/Users/[A-Za-z]"),
            "secret-like token": re.compile(rb"ghp_[A-Za-z0-9]{20,}|github_pat_|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|xox[bp]-"),
            "gmail/personal": re.compile(rb"@(gmail|yahoo|outlook|hotmail|icloud)\.com", re.I),
            "Kaggle/OptionsDX": re.compile(rb"optionsdx|kaggle", re.I)}
    for name, rx in pats.items():
        hits = [f for f in files if (REPO / f).is_file() and not f.startswith(SELF) and rx.search((REPO / f).read_bytes())]
        print(f"{name}: {hits}")
    for f in sorted(x for x in files if x.endswith(".parquet")):
        cols = list(pd.read_parquet(REPO / f).columns)
        print(f"{f}: restricted-suffix columns {[c for c in cols if c.endswith(('_yf', '_cboe'))]}; "
              f"{len(cols)} columns")
    sec = pd.read_parquet(REPO / "data/derived/security.parquet")
    print("security.universe_rank: non-null", int(sec.universe_rank.notna().sum()), "(a Yahoo market-cap ordinal per firm);"
          " in_universe", int(sec.in_universe.sum()))

    out = scratch / "p11"
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, str(REPO / "tools/export_app_data.py"), "--out-dir", str(out)], check=True,
                   capture_output=True, cwd=REPO)
    for k in ("meta", "sample_funnel"):
        a, b = (REPO / f"app/public/data/{k}.json").read_bytes(), (out / f"{k}.json").read_bytes()
        ja, jb = json.loads(a), json.loads(b)
        diff = sorted(x for x in ja if ja[x] != jb[x])
        print(f"{k}.json: byte-identical={a == b}; differing envelope keys: {diff}; "
              f"source_commit={ja['source_commit']}")


if __name__ == "__main__":
    main()
