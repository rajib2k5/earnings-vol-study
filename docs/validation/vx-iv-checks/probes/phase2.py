# =============================================================================
# phase2.py - The frozen phase-2 driver of the vx-iv-checks pre-registration
# (preregistration.md §8, §10; review item M6). Frozen on 2026-11-17, before
# any real-data value was read. Its only stub is the loader, load_panel in
# ../loader.py: outside probes/, not hashed; G2 records its SHA-256.
#
#   python -I phase2.py --selftest --out DIR
#       Synthetic panels only. Exercises the rules, the robustness rerun,
#       the aggregation, the outcome, the errors and the G4 comparison.
#   python -I phase2.py --gates G1,G2 --out DIR
#       Only the named gates (G3 reads the bytes of the real input files to
#       hash them; G4 needs the loader).
#   python -I phase2.py --out DIR [--reference] [--widen]
#       Phase 2: G1, G2, G3; then per name the loader, G4, every rule, the
#       robustness rerun; then the verdict table and the §10 outcome.
#       --reference: AAPL and AMZN as the descriptive reference of §11.1.
#       --widen: AAPL and AMZN as rules with k = 8 (§10, only after steps 1
#       and 2 of a fault were done by hand).
#
# OUTPUT (gate G5). DIR/aggregate.json holds aggregates only: per name and
# rule n, shares, bounds, verdicts and counts; no per-day value, no example.
# Full per-name results (with the dates of mismatching atoms) go to --local
# (default $VOL_DATA_DIR/earnings-vol-study/vx-iv-checks), never to the repo.
#
# A missing rule key, an unknown verdict, ref_p=None or a missing calendar
# list is an error, never a silent skip.
# =============================================================================

import argparse
import hashlib
import json
import math
import os
import pathlib
import re
import subprocess
import sys
import time
import types

for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = "1"

HERE = pathlib.Path(__file__).resolve().parent
FOLDER = HERE.parent                                   # docs/validation/vx-iv-checks
CLONE = HERE.parents[3]
sys.path[:0] = [str(CLONE / "src"), str(HERE)]

import earnings_vol  # noqa: E402

if not pathlib.Path(earnings_vol.__file__).resolve().is_relative_to(CLONE / "src"):
    sys.exit(f"earnings_vol imported from {earnings_vol.__file__}, not from {CLONE / 'src'}")

import exchange_calendars as xcals  # noqa: E402
import numpy as np  # noqa: E402
import yaml  # noqa: E402

import ivchecks  # noqa: E402
import ref_spec  # noqa: E402
import synth  # noqa: E402
import worlds  # noqa: E402
from earnings_vol.measures import chain, termstructure  # noqa: E402

CLONE_REV = "f5904a9"
NAMES = ("GOOGL", "GS", "IBM")
REFERENCE = ("AAPL", "AMZN")
K_MAIN, K_WIDEN = ivchecks.N_C_RULES, 8                 # 4 statistics x 3 names; x 2 names
VOL = pathlib.Path(os.environ.get("VOL_DATA_DIR", "~/data/vol-projects")).expanduser() / "earnings-vol-study"
STAGE = "cache/stage/74bed6f4b1281810"
CHAIN_DIR = "cache/dolt/options@msfqpodh24viv7prdqdan8517rkjp861/option_chain"
CHAIN_FILES, CHAIN_DIGEST = 82, "ba41a5ca5b99fd1c0bbc95fb57b40134c455933af0e451f575d8f780ae641cda"
INPUTS = {                                              # preregistration.md §13; paths under VOL
    f"{STAGE}/session_snapshot.parquet": "62243781b308bf010c1b7dc230271084c189250666de7475f5a71f0dffc13472",
    f"{STAGE}/market_daily.parquet": "82ed6a4df4244c85d92b56fe046c0612d9fc5af0ee64dda38b3a2dcccbdcc5a9",
    f"{STAGE}/events.parquet": "1e5b88ee1b25f6d237ffbcf876578fc3a2f6e6d3c91d5da469bbbc946b72fbfc",
    f"{STAGE}/security.parquet": "cd17dc2dfe98f1c4f724c99bfb28698eae77ff86354d7654093b9b610df974ff",
    f"{STAGE}/ticker_alias.parquet": "7bd15257b55c1b83303d04685ef3a07525dcbe3ed69d2907f600a39e21f77838",
    f"{STAGE}/session.parquet": "9ce8ddd766e1e4b904c706db5322d00b58481452cdf686c3fc68fd9d685fdb0a",
    f"{STAGE}/chain_expiry.parquet": "ce5a8e688a47230553dec8c088e64767b826aaa9011f8b3d071c6eb0d33af98f",
    f"{STAGE}/iv_daily.parquet": "68aa42a346fe748c2fffe09c6768460ebfff09a86ad2798eca88325cbb718bf0",
    "raw/yfinance/GOOGL.parquet": "3ece2b8aa616b21c2074ee65c852454fd28452a770c8207a68d6ef7bf1130b4f",
    "raw/yfinance/GS.parquet": "d9719bbcd8ac7d70ac84e69ed421bd213186b74d117b8047edb7db9f42de0d23",
    "raw/yfinance/IBM.parquet": "2abcf226d5cdc95ada442a2d7dc5a4275fe772206960bffc92ebc3fd52d69cbf",
    "raw/yfinance/AAPL.parquet": "47aa0597d62722be2b49fb873373f0c3d5d096277f06be4e019b958fd528b05b",
    "raw/yfinance/AMZN.parquet": "f39d61cce4e46c9bd0266615f08da9e38718488c9de224836eb4e975bf2dea53",
}
CLONE_INPUTS = {
    "params.yaml": "9cc10022ea2bf1b9be3638d5a69a5ff20c6cb4b6107ac98925216ed4f3722467",
    "data/derived/iv_daily.parquet": "68aa42a346fe748c2fffe09c6768460ebfff09a86ad2798eca88325cbb718bf0",
}
# G4: columns the checks never read and the loader cannot reproduce by construction. ivchecks.atom and
# ivchecks.day_row pass the session as the snapshot date; on an `ok` session the stage has the same value
# unless the snapshot was taken on another date, which the checks do not use.
G4_SKIP = {"snapshot_date"}

PARAMS = yaml.safe_load((CLONE / "params.yaml").read_text())
P = chain.AtomParams.from_params(PARAMS["iv"])
TP = termstructure.TermParams.from_params(PARAMS["iv"])
REF_P = ref_spec.load_params(CLONE / "params.yaml")


def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def xnys_list(start="2019-01-02", end="2031-12-31"):
    return [d.date() for d in xcals.get_calendar("XNYS", start=start, end=end).sessions]


# --- G1 to G4 -----------------------------------------------------------------------------------

class GateFailed(RuntimeError):
    pass


def env_freeze_text() -> str:
    """The venv as `name==version` lines (importlib.metadata, the same list pip freeze reads), sorted, with
    the Python version first. env.freeze.txt is this text, written on 2026-11-17."""
    import importlib.metadata as md
    import platform
    pk = {}
    for d in md.distributions():
        n = (d.metadata["Name"] or "").lower().replace("_", "-")
        if n:
            pk[n] = d.version
    return f"python=={platform.python_version()}\n" + "".join(f"{n}=={v}\n" for n, v in sorted(pk.items()))


def gate_g1() -> list:
    """earnings_vol from the clone's src; the clone at f5904a9 with src and params.yaml unchanged; the venv as
    frozen in env.freeze.txt."""
    out = [f"earnings_vol from {earnings_vol.__file__}"]
    rev = subprocess.run(["git", "-C", str(CLONE), "rev-parse", "HEAD"], capture_output=True, text=True,
                         check=True).stdout.strip()
    if not rev.startswith(CLONE_REV):
        raise GateFailed(f"G1: clone at {rev}, not {CLONE_REV}")
    st = subprocess.run(["git", "-C", str(CLONE), "status", "--porcelain", "--", "src", "params.yaml"],
                        capture_output=True, text=True, check=True).stdout
    if st.strip():
        raise GateFailed(f"G1: src or params.yaml changed in the clone:\n{st}")
    env = env_freeze_text()
    frozen = (HERE / "env.freeze.txt").read_text()
    if env != frozen:
        diff = sorted(set(env.splitlines()) ^ set(frozen.splitlines()))
        raise GateFailed(f"G1: the venv differs from env.freeze.txt: {diff[:10]}")
    out.append(f"clone {rev[:12]}, src and params.yaml clean, venv = env.freeze.txt "
               f"({hashlib.sha256(env.encode()).hexdigest()[:16]}...)")
    return out


def _sums() -> dict:
    """probes/SHA256SUMS: `<sha256>  <path relative to the vx-iv-checks folder>` per frozen file. Its own
    SHA-256 is written in preregistration.md §13 on the line that starts with 'SHA256SUMS'."""
    text = (HERE / "SHA256SUMS").read_text()
    m = re.search(r"^\| `probes/SHA256SUMS` \| `([0-9a-f]{64})` \|", (FOLDER / "preregistration.md").read_text(),
                  re.M)
    if m is None:
        raise GateFailed("G2: preregistration.md has no SHA256SUMS row in §13")
    if hashlib.sha256(text.encode()).hexdigest() != m.group(1):
        raise GateFailed("G2: probes/SHA256SUMS does not match the hash in preregistration.md")
    out = {}
    for line in text.splitlines():
        h, rel = line.split("  ", 1)
        out[rel] = h
    return out


def _strip_elapsed(text: str) -> list:
    return [x for x in text.splitlines() if not x.startswith("elapsed:")]


def gate_g2(out_dir: pathlib.Path) -> list:
    """Every frozen file matches SHA256SUMS; a rerun of run_probes.py (seed 1) into out_dir/g2 exits 0 and
    reproduces probes/run_probes.seed1.out line for line (except the `elapsed:` line) and
    probes/run_probes.seed1.json byte for byte. Also records the SHA-256 of the loader this run uses
    (../loader.py, not frozen); nothing checks it."""
    sums = _sums()
    bad = [rel for rel, h in sums.items() if sha256_file(FOLDER / rel) != h]
    if bad:
        raise GateFailed(f"G2: changed since frozen: {bad}")
    listed = {str(p.relative_to(FOLDER)) for p in HERE.iterdir() if p.is_file() and p.name != "SHA256SUMS"}
    if listed - set(sums):
        raise GateFailed(f"G2: files in probes/ that are not frozen: {sorted(listed - set(sums))}")
    g2 = out_dir / "g2"
    r = subprocess.run([sys.executable, "-I", str(HERE / "run_probes.py"), "--out", str(g2), "--seed", "1"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise GateFailed(f"G2: run_probes.py exited {r.returncode}:\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    if _strip_elapsed((g2 / "run_probes.seed1.out").read_text()) != _strip_elapsed(
            (HERE / "run_probes.seed1.out").read_text()):
        raise GateFailed("G2: the rerun's report differs from probes/run_probes.seed1.out")
    if (g2 / "run_probes.seed1.json").read_bytes() != (HERE / "run_probes.seed1.json").read_bytes():
        raise GateFailed("G2: the rerun's results differ from probes/run_probes.seed1.json")
    return [f"{len(sums)} frozen files match; run_probes.py seed 1 reproduced (exit 0)",
            f"loader.py SHA-256 {LOADER_SHA256} (recorded, not checked)"]


def chain_digest(folder: pathlib.Path) -> tuple:
    """sha256 of the text `sha256sum $(ls *.parquet | sort)` prints, and the number of files."""
    names = sorted(p.name for p in folder.glob("*.parquet"))
    text = "".join(f"{sha256_file(folder / n)}  {n}\n" for n in names)
    return hashlib.sha256(text.encode()).hexdigest(), len(names)


def gate_g3() -> list:
    """The bytes of every input match §13. Reads bytes only; no value."""
    bad = [rel for rel, h in INPUTS.items() if sha256_file(VOL / rel) != h]
    bad += [rel for rel, h in CLONE_INPUTS.items() if sha256_file(CLONE / rel) != h]
    d, n = chain_digest(VOL / CHAIN_DIR)
    if (d, n) != (CHAIN_DIGEST, CHAIN_FILES):
        bad.append(f"{CHAIN_DIR} ({n} files)")
    if bad:
        raise GateFailed(f"G3: inputs differ from §13: {bad}")
    return [f"{len(INPUTS) + len(CLONE_INPUTS)} input files and the {n} option-chain files match"]


def _same(x, y) -> bool:
    nx = x is None or (isinstance(x, float) and math.isnan(x)) or (x != x)
    ny = y is None or (isinstance(y, float) and math.isnan(y)) or (y != y)
    if nx or ny:
        return nx and ny
    if hasattr(x, "item"):
        x = x.item()
    if hasattr(y, "item"):
        y = y.item()
    return x == y


def compare_rows(mine: list, staged: list, key: tuple) -> dict:
    """Every column of `staged` (rows as dicts) against `mine`, matched on `key`, except G4_SKIP. Exact: the
    same value, or null on both sides (None, NaN and NaT are all null). Returns {problem: count}; empty = equal."""
    out = {}
    km = {tuple(r[k] for k in key): r for r in mine}
    ks = {tuple(r[k] for k in key): r for r in staged}
    if len(km) != len(mine) or len(ks) != len(staged):
        out["duplicate_key"] = (len(mine) - len(km)) + (len(staged) - len(ks))
    if set(km) - set(ks):
        out["rows_only_in_loader"] = len(set(km) - set(ks))
    if set(ks) - set(km):
        out["rows_only_in_stage"] = len(set(ks) - set(km))
    for k in set(km) & set(ks):
        a, b = km[k], ks[k]
        for col in b:
            if col in G4_SKIP:
                continue
            if col not in a:
                out[f"missing_column:{col}"] = out.get(f"missing_column:{col}", 0) + 1
            elif not _same(a[col], b[col]):
                out[col] = out.get(col, 0) + 1
    return out


def gate_g4(name, panel, cache, staged_chain: list, staged_daily: list) -> list:
    """The loader's panel, run through the package's own path (ivchecks.Cache), reproduces every field of
    the staged chain_expiry and iv_daily rows of the name on every `ok` session. staged_*: the stage's rows
    of the name as dicts (pandas DataFrame.to_dict('records') of chain_expiry.parquet / iv_daily.parquet)."""
    ok = [d for d in panel.days if panel.status.get(d) == "ok"]
    okset = set(ok)
    mine_c = [r for d in ok for r in cache.atoms(d).values() if r is not None]
    mine_d = [cache.day(d) for d in ok]
    sc = [r for r in staged_chain if r["session_date"] in okset]
    sd = [r for r in staged_daily if r["session_date"] in okset]
    pc = compare_rows(mine_c, sc, ("session_date", "expiration"))
    pd_ = compare_rows(mine_d, sd, ("session_date",))
    if pc or pd_:
        raise GateFailed(f"G4 {name}: chain_expiry {pc}; iv_daily {pd_}")
    return [f"G4 {name}: {len(sc)} chain_expiry rows and {len(sd)} iv_daily rows on {len(ok)} ok sessions equal"]


# --- the loader (the only stub) -----------------------------------------------------------------
# It lives in ../loader.py, outside probes/, so writing it does not change a hashed file (G2). Its bytes
# are read once, hashed, and those same bytes are run, so the SHA-256 that G2 records is the loader used.

LOADER_PATH = FOLDER / "loader.py"
_LOADER_SRC = LOADER_PATH.read_bytes()
LOADER_SHA256 = hashlib.sha256(_LOADER_SRC).hexdigest()
loader = types.ModuleType("vx_iv_loader")
loader.__file__ = str(LOADER_PATH)
sys.modules["vx_iv_loader"] = loader
exec(compile(_LOADER_SRC, str(LOADER_PATH), "exec"), loader.__dict__)


# --- rules, aggregation, outcome ----------------------------------------------------------------

def run_one(panel, xnys, k_rules):
    """The rules (block 20, seed 20261117) and the robustness rerun (block 60, seed 20261118; reported,
    does not decide) for one name."""
    n = len(panel.days)
    res = ivchecks.run_name(panel, P, TP, REF_P, xnys, ivchecks.block_counts(n), k_rules=k_rules)
    rob = ivchecks.run_name(panel, P, TP, REF_P, xnys,
                            ivchecks.block_counts(n, block=ivchecks.ROBUST_BLOCK, seed=ivchecks.SEED + 1),
                            k_rules=k_rules, with_truth=False, with_diff=False, with_common=False)
    return res, rob


def verdicts_of(res: dict) -> dict:
    out = {}
    for rule in ivchecks.RULES_ALL:
        if rule not in res or "verdict" not in res[rule]:
            raise KeyError(f"rule {rule!r} is missing from the result")
        out[rule] = res[rule]["verdict"]
    return out


KNOWN = {"MATCH", "MISMATCH", "FAULT", "NO FAULT", "UNCLEAR"}


def outcome(per_name: dict) -> str:
    """§10: FAULT if any MISMATCH or FAULT; else UNCLEAR if any UNCLEAR; else NO FAULT."""
    heads = [ivchecks._head(v) for vs in per_name.values() for v in vs.values()]
    unknown = set(heads) - KNOWN
    if unknown or not heads:
        raise ValueError(f"unknown or no verdicts: {sorted(unknown)}")
    if {"FAULT", "MISMATCH"} & set(heads):
        return "FAULT"
    if "UNCLEAR" in heads:
        return "UNCLEAR"
    return "NO FAULT"


AGG_KEYS = ("n", "n_group", "n_base", "share", "lo", "hi", "lo_raw", "hi_raw", "boot_sd", "inflate",
            "upper_bound", "no_clean_ref_share", "dropped", "sigma_f_bp", "sigma_c_bp", "n_pairs", "verdict",
            "verdict_clean", "excluded", "median_abs_bp", "median_signed_bp", "worst", "mismatches", "tags",
            "untagged", "unspecified", "accepted_alternatives", "parts", "lag1_cm30_blind_iv")


def aggregates(res: dict) -> dict:
    """The public part of one name's results: every rule and descriptive number, aggregates only (G5)."""
    out = {"n_changes": res["n_changes"], "excluded": res["excluded"]}
    for k, v in res.items():
        if k.startswith("_") or not isinstance(v, dict) or "verdict" not in v:
            continue
        x = {kk: vv for kk, vv in v.items() if kk in AGG_KEYS}
        if k == "diff":
            x["n"] = v["n"]
        if k == "truth":
            x["n"] = v["n"]
        if "any_ref" in v:
            x["any_ref"] = {kk: vv for kk, vv in v["any_ref"].items() if kk in AGG_KEYS}
        out[k] = x
    return out


def _dump(obj) -> str:
    return json.dumps(obj, indent=1, default=str, sort_keys=True) + "\n"


def phase2(out_dir, local_dir, reference, widen) -> int:
    report = []
    for g in (gate_g1, lambda: gate_g2(out_dir), gate_g3):
        report += g()
    xnys = xnys_list()
    agg, verdicts, robust = {}, {}, {}
    sets = [("rule", NAMES, K_MAIN)]
    if reference:
        sets.append(("descriptive reference", REFERENCE, K_MAIN))
    if widen:
        sets.append(("widening", REFERENCE, K_WIDEN))
    for label, names, k in sets:
        for name in names:
            panel, staged_chain, staged_daily = loader.load_panel(name)
            cache = ivchecks.Cache(panel, P, TP)
            report += gate_g4(name, panel, cache, staged_chain, staged_daily)
            res, rob = run_one(panel, xnys, k)
            tag = f"{label}:{name}"
            (local_dir / f"{tag.replace(' ', '_').replace(':', '_')}.json").write_text(
                _dump({"rules": {k_: v for k_, v in res.items() if not k_.startswith("_")},
                       "robust": {k_: v for k_, v in rob.items() if not k_.startswith("_")}}))
            agg[tag] = {"rules": aggregates(res), "robust": aggregates(rob)}
            verdicts[tag] = verdicts_of(res)
            robust[tag] = {r: rob[r]["verdict"] for r in ivchecks.RULES_C}
    main = {t: v for t, v in verdicts.items() if t.startswith("rule:")}
    result = {"outcome": outcome(main), "verdicts": verdicts, "robust_block60_seed20261118": robust,
              "widening_outcome": outcome({t: v for t, v in verdicts.items() if t.startswith("widening:")})
              if widen else None, "gates": report, "loader_sha256": LOADER_SHA256, "aggregates": agg}
    (out_dir / "aggregate.json").write_text(_dump(result))
    print("\n".join(report))
    for t, v in verdicts.items():
        print(f"{t:32} " + "  ".join(f"{r} {v[r]}" for r in ivchecks.RULES_ALL))
    print(f"OUTCOME (§10): {result['outcome']}")
    return 0


# --- self-test on synthetic panels ----------------------------------------------------------------

def selftest(out_dir) -> int:
    xnys = xnys_list()
    checks = []

    def check(name, cond, detail=""):
        checks.append((name, bool(cond), detail))
        print(f"{'ok   ' if cond else 'WRONG'} {name} {detail}", flush=True)

    panels = {w: synth.make_panel(worlds.spec(w, 1)) for w in ("clean", "lowvol", "monthly_bump")}
    runs = {w: run_one(p, xnys, K_MAIN) for w, p in panels.items()}
    v = {f"rule:{w}": verdicts_of(r[0]) for w, r in runs.items()}
    check("no fault on clean and lowvol", outcome({k: v[k] for k in ("rule:clean", "rule:lowvol")}) == "NO FAULT",
          str({k: v[k] for k in ("rule:clean", "rule:lowvol")}))
    check("fault when monthly_bump is added", outcome(v) == "FAULT", str(v["rule:monthly_bump"]))
    check("robustness rerun has every (c) rule", all("verdict" in runs["clean"][1][r] for r in ivchecks.RULES_C))
    bad = dict(runs["clean"][0])
    bad.pop("truth")
    try:
        verdicts_of(bad)
        check("a missing rule key is an error", False)
    except KeyError as e:
        check("a missing rule key is an error", True, str(e))
    try:
        outcome({"x": {"forward": "MAYBE"}})
        check("an unknown verdict is an error", False)
    except ValueError as e:
        check("an unknown verdict is an error", True, str(e))
    for kw, label in (({"ref_p": None}, "ref_p=None"), ({"xnys": None}, "xnys=None")):
        args = {"ref_p": REF_P, "xnys": xnys, **kw}
        try:
            ivchecks.run_name(panels["clean"], P, TP, args["ref_p"], args["xnys"])
            check(f"{label} is an error", False)
        except ValueError as e:
            check(f"{label} is an error", True, str(e)[:60])
    try:
        loader.load_panel("GOOGL")
        check("the loader is a stub", False)
    except NotImplementedError:
        check("the loader is a stub", True)
    # G4's comparison: the panel against its own rows, then with one value moved, one row dropped.
    p = panels["clean"]
    cache = ivchecks.Cache(p, P, TP)
    ok = [d for d in p.days if p.status.get(d) == "ok"]
    rows_c = [dict(r) for d in ok for r in cache.atoms(d).values() if r is not None]
    rows_d = [dict(cache.day(d)) for d in ok]
    check("G4 passes on identical rows", gate_g4("SYN", p, cache, rows_c, rows_d))
    moved = [dict(r) for r in rows_c]
    i = next(j for j, r in enumerate(moved) if r["w_atm"] is not None)
    moved[i]["w_atm"] = math.nextafter(moved[i]["w_atm"], 1.0)
    for label, sc, sd in (("one w_atm moved by one ulp", moved, rows_d), ("one chain row missing", rows_c[1:], rows_d),
                          ("one cm30_blind_iv set to null", rows_c,
                           [{**r, "cm30_blind_iv": None} if j == 5 else r for j, r in enumerate(rows_d)])):
        try:
            gate_g4("SYN", p, cache, sc, sd)
            check(f"G4 fails: {label}", False)
        except GateFailed as e:
            check(f"G4 fails: {label}", True, str(e)[:100])
    pub = _dump({"aggregates": {w: aggregates(r[0]) for w, r in runs.items()}})
    check("aggregate output holds no example and no per-day key", '"examples"' not in pub and '"_y_' not in pub)
    (out_dir / "selftest.aggregate.json").write_text(pub)
    n_bad = sum(not c[1] for c in checks)
    print(f"selftest: {len(checks) - n_bad} of {len(checks)} checks as expected")
    return 0 if n_bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=pathlib.Path)
    ap.add_argument("--local", type=pathlib.Path, default=VOL / "vx-iv-checks")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--gates", default=None, help="comma list of G1, G2, G3: run only these")
    ap.add_argument("--reference", action="store_true")
    ap.add_argument("--widen", action="store_true")
    ap.add_argument("--env-freeze", action="store_true", help="write OUT/env.freeze.txt and stop")
    a = ap.parse_args()
    out_dir = a.out.resolve()
    if out_dir.is_relative_to(FOLDER):
        sys.exit(f"--out {out_dir} is inside the frozen folder {FOLDER}; write elsewhere")
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    if a.env_freeze:
        (out_dir / "env.freeze.txt").write_text(env_freeze_text())
        return 0
    try:
        if a.selftest:
            rc = selftest(out_dir)
        elif a.gates:
            gates = {"G1": gate_g1, "G2": lambda: gate_g2(out_dir), "G3": gate_g3}
            for g in a.gates.split(","):
                print("\n".join(gates[g.strip()]()))
            rc = 0
        else:
            a.local.mkdir(parents=True, exist_ok=True)
            rc = phase2(out_dir, a.local, a.reference, a.widen)
    except GateFailed as e:
        print(f"STOP: {e}")
        rc = 2
    print(f"elapsed: {time.monotonic() - t0:.0f} s")
    return rc


if __name__ == "__main__":
    sys.exit(main())
