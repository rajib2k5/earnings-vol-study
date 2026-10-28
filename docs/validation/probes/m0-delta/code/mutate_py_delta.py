"""M0 delta review, claims 8a / 8b / 8c: Python mutation probe.

Usage:
    python mutate_py_delta.py <repo-COPY> [id-prefix ...]

NEVER point this at the real repository: files are rewritten (and restored).
The copy needs its own venv (`uv sync --frozen` inside the copy) so that the
package under test is the copy's src/, not the real one.

Each mutant is one targeted textual change. For each: apply, run pytest in the
copy, record rc and the failing test ids, restore, and verify the file's sha256
is back. rc == 0 means the mutant SURVIVED (no test noticed).
Optional id prefixes (e.g. "exp" "con") run only the mutants whose id starts
with one of them.
"""
import hashlib
import re
import subprocess
import sys
from pathlib import Path

R = Path(sys.argv[1]).resolve()
ONLY = sys.argv[2:]
CON = "src/earnings_vol/contract.py"
EXP = "tools/export_app_data.py"
NBK = "tools/build_notebooks.py"

MUTANTS = [
    # --- 8a: the four exporter mutants that survived the first review -------
    ("exp-6 full hash not short", EXP,
     '["git", "rev-parse", "--short", "HEAD"]', '["git", "rev-parse", "HEAD"]'),
    ("exp-7 default out path wrong", EXP,
     'DEFAULT_OUT = ROOT / "app" / "public" / "data" / "meta.json"',
     'DEFAULT_OUT = ROOT / "app" / "public" / "meta.json"'),
    ("exp-8 DoltHub licence CC BY 4.0", EXP,
     'post-no-preference/earnings",\n        "licence": "CC BY-SA 4.0",',
     'post-no-preference/earnings",\n        "licence": "CC BY 4.0",'),
    ("exp-9 earnings url -> options repo", EXP,
     '"url": "https://www.dolthub.com/repositories/post-no-preference/earnings"',
     '"url": "https://www.dolthub.com/repositories/post-no-preference/options"'),
    # --- 8a: new exporter mutants on DATA_SOURCES / DATA_LICENCE -------------
    ("exp-11 drop attribution field", EXP,
     '    "attribution": (\n', '    "_attribution": (\n'),
    ("exp-12 options url -> earnings repo", EXP,
     '"url": "https://www.dolthub.com/repositories/post-no-preference/options"',
     '"url": "https://www.dolthub.com/repositories/post-no-preference/earnings"'),
    ("exp-13 applies_to names CBOE not options", EXP,
     '        "DoltHub post-no-preference/earnings",\n        "DoltHub post-no-preference/options",\n    ],',
     '        "DoltHub post-no-preference/earnings",\n        "CBOE single-stock VIX indices",\n    ],'),
    ("exp-14 licence url by/4.0 (not by-sa)", EXP,
     '"url": "https://creativecommons.org/licenses/by-sa/4.0/"',
     '"url": "https://creativecommons.org/licenses/by/4.0/"'),
    ("exp-15 drop Yahoo source", EXP,
     '    {\n        "name": "Yahoo Finance prices (via yfinance)",\n        "uses": "daily prices",\n'
     '        "url": "https://finance.yahoo.com/",\n        "licence": "see source",\n'
     '        "committed": False,\n    },\n', ""),
    ("exp-16 attribution drops ShareAlike", EXP,
     '"Attribution-ShareAlike 4.0 International (CC BY-SA 4.0). Changes: "',
     '"Attribution 4.0 International (CC BY-SA 4.0). Changes: "'),
    ("exp-17 data_licence key missing in meta", EXP,
     '        "data_licence": DATA_LICENCE,\n', ""),
    ("exp-18 short hash 'or' fallback dropped", EXP,
     'return result.stdout.strip() or "uncommitted"', "return result.stdout.strip()"),
    # --- 8b: build_notebooks back to the text comparison ---------------------
    ("nbk-r text compare (pre-fix)", NBK,
     'return path.exists() and path.read_bytes() == render().encode("utf-8")',
     'return path.exists() and path.read_text(encoding="utf-8") == render()'),
    ("nbk-r2 bytes compare after CRLF->LF normalise", NBK,
     'return path.exists() and path.read_bytes() == render().encode("utf-8")',
     'return path.exists() and path.read_bytes().replace(b"\\r\\n", b"\\n") == render().encode("utf-8")'),
    # --- 8c: contract boundary and type checks -------------------------------
    ("con-b1 > becomes >=", CON, "if abs(number) > MAX_SAFE_INT:", "if abs(number) >= MAX_SAFE_INT:"),
    ("con-b2 MAX_SAFE_INT = 2**53", CON, "MAX_SAFE_INT = 2**53 - 1", "MAX_SAFE_INT = 2**53"),
    ("con-b3 MAX_SAFE_INT = 2**53 - 2", CON, "MAX_SAFE_INT = 2**53 - 1", "MAX_SAFE_INT = 2**53 - 2"),
    ("con-b4 no abs (negatives unchecked)", CON, "if abs(number) > MAX_SAFE_INT:", "if number > MAX_SAFE_INT:"),
    ("con-b5 parse_int check removed", CON, "json.loads(text, parse_int=_check_safe_int)", "json.loads(text)"),
    ("con-b6 MAX_SAFE_INT = 2**63 - 1", CON, "MAX_SAFE_INT = 2**53 - 1", "MAX_SAFE_INT = 2**63 - 1"),
    ("con-t1 kind type check removed", CON,
     "if not isinstance(kind, str) or not kind:", "if False:"),
    ("con-t2 kind empty allowed", CON,
     "if not isinstance(kind, str) or not kind:", "if not isinstance(kind, str):"),
    ("con-t3 source_commit check removed", CON,
     "if not isinstance(source_commit, str) or not source_commit:", "if False:"),
    ("con-t4 source_commit empty allowed", CON,
     "if not isinstance(source_commit, str) or not source_commit:", "if not isinstance(source_commit, str):"),
    ("con-t5 data check removed", CON, "if not isinstance(data, dict):", "if False:"),
    ("con-t6 data may be list", CON, "if not isinstance(data, dict):", "if not isinstance(data, (dict, list)):"),
    ("con-t7 TypeError -> ValueError (kind)", CON,
     'raise TypeError(f"kind must be a non-empty str', 'raise ValueError(f"kind must be a non-empty str'),
    # --- 10b: the mutation counts quoted in the milestone doc, section 2.5 ---------
    ("doc-A no astimezone (doc: 3 failed, 67 passed)", CON,
     "utc = generated_at.astimezone(timezone.utc)", "utc = generated_at"),
    ("doc-B allow_nan=True (doc: 4 failed, 66 passed)", CON,
     "json.dumps(env, allow_nan=False", "json.dumps(env, allow_nan=True"),
    ("doc-C1 check = exists (doc: 4 failed, 66 passed)", NBK,
     'return path.exists() and path.read_bytes() == render().encode("utf-8")', "return path.exists()"),
    ("doc-C2 text compare (doc: 2 failed, 68 passed)", NBK,
     'return path.exists() and path.read_bytes() == render().encode("utf-8")',
     'return path.exists() and path.read_text(encoding="utf-8") == render()'),
    ("doc-C3 no fixed ids (doc: 5 failed, 65 passed)", NBK,
     '    for i, cell in enumerate(nb.cells):\n        cell["id"] = f"cell-{i:02d}"\n', ""),
    ("doc-C4 cell text edited (doc: 1 failed, 69 passed)", NBK,
     '"## 1. Where the data lives\\n"', '"## 1. Where the data is\\n"'),
]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    py = R / ".venv" / "bin" / "python"
    survivors = 0
    for mid, rel, old, new in MUTANTS:
        if ONLY and not any(mid.startswith(o) for o in ONLY):
            continue
        f = R / rel
        before = f.read_bytes()
        h0 = sha(f)
        text = before.decode()
        if text.count(old) != 1:
            print(f"PROBE_INVALID {mid}: pattern found {text.count(old)}x")
            continue
        f.write_text(text.replace(old, new, 1), encoding="utf-8")
        try:
            p = subprocess.run([str(py), "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rf"],
                               cwd=R, capture_output=True, text=True, timeout=600)
        finally:
            f.write_bytes(before)
        assert sha(f) == h0, f"restore failed for {rel}"
        failed = sorted(set(re.findall(r"^FAILED (\S+?)(?: - |$)", p.stdout, re.M)))
        tail = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else p.stderr.strip()[-200:]
        status = "KILLED  " if p.returncode != 0 else "SURVIVED"
        survivors += p.returncode == 0
        print(f"{status} rc={p.returncode} {mid:44s} | {tail}")
        for t in failed:
            print(f"           killed by: {t}")
    print(f"survivors: {survivors}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
