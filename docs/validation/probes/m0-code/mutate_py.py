"""C1.2 mutation probe for the Python side. Usage:
    python mutate_py.py <repo-COPY>        (never the real repo: files are rewritten)
Each mutant is one targeted textual change. For each: apply, run pytest in the copy,
record rc and the failing test ids, restore, and verify the file's sha256 is back.
A mutant with rc == 0 SURVIVED (no test noticed the code was broken).
"""
import hashlib
import re
import subprocess
import sys
from pathlib import Path

R = Path(sys.argv[1]).resolve()
CFG, CON = "src/earnings_vol/config.py", "src/earnings_vol/contract.py"
EXP, NBK = "tools/export_app_data.py", "tools/build_notebooks.py"

MUTANTS = [
    # (id, file, old, new)
    ("cfg-1 no expanduser", CFG, "DEFAULT_DATA_DIR)).expanduser()", "DEFAULT_DATA_DIR))"),
    ("cfg-2 default dir typo", CFG, '"~/data/vol-projects"', '"~/data/vol-project"'),
    ("cfg-3 dolt: dir check not .dolt", CFG, 'if not (path / ".dolt").is_dir():', "if not path.is_dir():"),
    ("cfg-4 raw_dir no mkdir", CFG, 'path = project_dir() / "raw"\n    path.mkdir(parents=True, exist_ok=True)', 'path = project_dir() / "raw"'),
    ("cfg-5 cache under data_dir", CFG, 'path = project_dir() / "cache"', 'path = data_dir() / "cache"'),
    ("cfg-6 project_dir creates folder", CFG, "    return data_dir() / PROJECT", "    p = data_dir() / PROJECT\n    p.mkdir(parents=True, exist_ok=True)\n    return p"),
    ("cfg-7 no clone hint", CFG, 'f"  cd {path.parent} && dolt clone post-no-preference/{name}\\n"', 'f"  cd {path.parent}\\n"'),
    ("con-1 drop source_commit key", CON, '        "source_commit": source_commit,\n', ""),
    ("con-2 no astimezone", CON, "utc = generated_at.astimezone(timezone.utc)", "utc = generated_at"),
    ("con-3 no naive check", CON, 'raise ValueError("generated_at must be timezone-aware (naive datetime given)")', "pass"),
    ("con-4 allow_nan=True", CON, "json.dumps(env, allow_nan=False", "json.dumps(env, allow_nan=True"),
    ("con-5 sort_keys=False", CON, "allow_nan=False, sort_keys=True", "allow_nan=False, sort_keys=False"),
    ("con-6 +00:00 instead of Z", CON, '"%Y-%m-%dT%H:%M:%SZ"', '"%Y-%m-%dT%H:%M:%S+00:00"'),
    ("con-7 only tzinfo None check", CON, "if generated_at.tzinfo is None or generated_at.utcoffset() is None:", "if generated_at.tzinfo is None:"),
    ("con-8 no trailing newline", CON, 'indent=2) + "\\n"', "indent=2)"),
    ("con-9 version bump", CON, 'SCHEMA_VERSION = "0.1.0"', 'SCHEMA_VERSION = "0.1.1"'),
    ("exp-1 milestone as string", EXP, '"milestone": 0,', '"milestone": "0",'),
    ("exp-2 CBOE committed", EXP, '"url": "https://www.cboe.com/",\n        "licence": "see source",\n        "committed": False,', '"url": "https://www.cboe.com/",\n        "licence": "see source",\n        "committed": True,'),
    ("exp-3 FileNotFoundError not caught", EXP, "except (subprocess.CalledProcessError, FileNotFoundError):", "except subprocess.CalledProcessError:"),
    ("exp-4 no parent mkdir", EXP, "    args.out.parent.mkdir(parents=True, exist_ok=True)\n", ""),
    ("exp-5 naive now()", EXP, "generated_at=datetime.now(timezone.utc)", "generated_at=datetime.now()"),
    ("exp-6 full hash not short", EXP, '["git", "rev-parse", "--short", "HEAD"]', '["git", "rev-parse", "HEAD"]'),
    ("exp-7 default out path wrong", EXP, 'DEFAULT_OUT = ROOT / "app" / "public" / "data" / "meta.json"', 'DEFAULT_OUT = ROOT / "app" / "public" / "meta.json"'),
    ("exp-8 DoltHub licence wrong", EXP, 'post-no-preference/earnings",\n        "licence": "CC BY-SA 4.0",', 'post-no-preference/earnings",\n        "licence": "CC BY 4.0",'),
    ("exp-9 earnings url wrong", EXP, '"url": "https://www.dolthub.com/repositories/post-no-preference/earnings"', '"url": "https://www.dolthub.com/repositories/post-no-preference/options"'),
    ("exp-10 git error -> empty string", EXP, '    except (subprocess.CalledProcessError, FileNotFoundError):\n        return "uncommitted"', '    except (subprocess.CalledProcessError, FileNotFoundError):\n        return ""'),
    ("nbk-1 random cell ids", NBK, '        cell["id"] = f"cell-{i:02d}"', "        pass"),
    ("nbk-2 check always True", NBK, 'return path.exists() and path.read_text(encoding="utf-8") == render()', "return True"),
    ("nbk-3 --check returns 0 on drift", NBK, "              file=sys.stderr)\n        return 1", "              file=sys.stderr)\n        return 0"),
    ("nbk-4 broken code cell", NBK, '"print(config.data_dir())\\n"', '"print(config.data_dirr())\\n"'),
    ("nbk-5 check ignores whitespace", NBK, 'path.read_text(encoding="utf-8") == render()', 'path.read_text(encoding="utf-8").strip() == render().strip()'),
    ("nbk-6 nbformat_minor 4", NBK, "nb.nbformat_minor = 5", "nb.nbformat_minor = 4"),
    ("nbk-7 drop newline normalisation", NBK, 'return text if text.endswith("\\n") else text + "\\n"', "return text"),
]

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    py = R / ".venv" / "bin" / "python"
    survivors = 0
    for mid, rel, old, new in MUTANTS:
        f = R / rel
        before = f.read_bytes()
        h0 = sha(f)
        text = before.decode()
        if text.count(old) != 1:
            print(f"PROBE_INVALID {mid}: pattern found {text.count(old)}x")
            continue
        f.write_text(text.replace(old, new), encoding="utf-8")
        try:
            p = subprocess.run([str(py), "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rf"],
                               cwd=R, capture_output=True, text=True, timeout=300)
        finally:
            f.write_bytes(before)
        assert sha(f) == h0, f"restore failed for {rel}"
        failed = sorted(set(re.findall(r"FAILED (\S+?)(?: - |$)", p.stdout, re.M)))
        tail = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else p.stderr.strip()[-200:]
        status = "KILLED " if p.returncode != 0 else "SURVIVED"
        survivors += p.returncode == 0
        print(f"{status} rc={p.returncode} {mid:38s} | {tail}")
        for t in failed:
            print(f"           - {t}")
    print(f"mutants={len(MUTANTS)} survivors={survivors}")

if __name__ == "__main__":
    main()
