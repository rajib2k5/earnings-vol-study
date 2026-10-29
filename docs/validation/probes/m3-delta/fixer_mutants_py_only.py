"""Mutation check of every test added for the milestone-3 review fixes. Runs on a SCRATCH COPY
of the repository: each mutant replaces one exact string (or rewrites one committed parquet
cell), runs the named tests, expects a failure, restores the file from bytes held in memory and
checks its SHA-256. Usage: python my_mutants.py <scratch_repo> <venv python>"""
import hashlib, subprocess, sys
from pathlib import Path
import pandas as pd

REPO, PY = Path(sys.argv[1]), sys.argv[2]
W, G, R, M, E, V, EV = ("src/earnings_vol/panel/window.py", "src/earnings_vol/stats/g1.py",
                        "src/earnings_vol/stats/results.py", "src/earnings_vol/stats/multiple.py",
                        "src/earnings_vol/stats/eventtests.py", "src/earnings_vol/export/event_views.py",
                        "src/earnings_vol/stats/clustering.py")
TG, TP, TM, TE, TV = "tests/test_g1.py", "tests/test_panel.py", "tests/test_multiple.py", "tests/test_eventtests.py", "tests/test_event_views.py"
RT, RP = "app/src/lib/results.ts", "app/src/lib/ResultsPage.tsx"
APP_R, APP_P = "src/lib/results.test.ts", "src/lib/ResultsPage.test.tsx"
CODE = [
    ("F2 beta pools failing baselines too", W, "dX, dM, clean & base_ok[:, None])", "dX, dM, clean)", "py", [f"{TP}::test_beta_pools_only_baselines_that_pass_the_minimum"]),
    ("sig0 without the change-variance factor", G, "log_s_by_firm])) / np.sqrt(2 / (1 + phi) + 2 * noise2))", "log_s_by_firm])))", "py", [f"{TG}::test_calibrate_round_trip_recovers_the_scale"]),
    ("generate ignores sig0", G, 'sig = p.get("sig0", SIG0) * np.exp', "sig = SIG0 * np.exp", "py", [f"{TG}::test_generate_uses_the_calibrated_scale"]),
    ("oversized >= instead of >", R, "and name != \"date_cluster_t\" and rate > hi:", "and name != \"date_cluster_t\" and rate >= hi:", "py", [f"{TG}::test_oversized_and_withhold"]),
    ("oversized keeps date_cluster_t", R, "and name != \"date_cluster_t\" and rate > hi:", "and rate > hi:", "py", [f"{TG}::test_oversized_and_withhold"]),
    ("withhold keeps the interval", R, "return dict(r, p_value=None, ci_lo=None, ci_hi=None)", "return dict(r, p_value=None)", "py", [f"{TG}::test_oversized_and_withhold"]),
    ("season cut merges the first two seasons", R, "cut[cut == keys[-1]] = keys[-2]", "cut[cut == keys[0]] = keys[1]", "py", [f"{TG}::test_season_cut_rows_merge_the_last_season_into_the_one_before"]),
    ("season cut Holm keeps the reported p", R, "pv[h] = res[name][\"p_value\"]", "pv[h] = r[\"p_value\"]", "py", [f"{TG}::test_season_cut_rows_merge_the_last_season_into_the_one_before"]),
    ("holm/bh accept anything", M, "if np.isnan(pv).any() or (pv < 0).any() or (pv > 1).any():", "if False:", "py", [f"{TM}::test_holm_and_bh_refuse_what_is_not_a_probability"]),
    ("kp_ow r not clamped", E, "return max(0.0, float((nu[iu] * filled[iu]).mean()))", "return float((nu[iu] * filled[iu]).mean())", "py", [f"{TE}::test_kp_ow_rbar_is_clamped_at_zero"]),
    ("tests.json g1_size dropped", V, "drops its p-value. The estimate stands.\", _r(rate))", "drops its p-value. The estimate stands.\", None)", "py", [f"{TV}::test_withheld_rows_and_the_season_cut_get_notes"]),
    ("tests.json counterfactual verdict flipped", V, "verdict = \"not rejected\" if c[\"p_holm\"] > alpha else \"rejected\"", "verdict = \"not rejected\" if c[\"p_holm\"] < alpha else \"rejected\"", "py", [f"{TV}::test_withheld_rows_and_the_season_cut_get_notes"]),
    ("tests.json season labels swapped", V, "last, _, prev = c[\"subgroup_value\"].partition(\"_into_\")", "prev, _, last = c[\"subgroup_value\"].partition(\"_into_\")", "py", [f"{TV}::test_withheld_rows_and_the_season_cut_get_notes"]),
    ("tests.json oversized caveat empty", V, "    oversized = ([f\"Gate G1's", "    over = []\n    oversized = ([f\"Gate G1's", "py", [f"{TV}::test_tests_view_g1_verdicts_power_and_rounding"]),
]

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def run(kind, tests):
    if kind == "py":
        return subprocess.run([PY, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *tests], cwd=REPO,
                              env={"PYTHONPATH": str(REPO / "src"), "PATH": "/usr/bin:/bin", "HOME": str(Path.home())},
                              capture_output=True, text=True, timeout=900)
    return subprocess.run(["npx", "vitest", "run", *tests], cwd=REPO / "app", capture_output=True, text=True, timeout=900)

killed = total = 0
ONLY = sys.argv[3] if len(sys.argv) > 3 else None
for name, rel, old, new, kind, tests in (CODE if ONLY != "data" else []):
    if ONLY not in (None, "data") and ONLY not in name:
        continue
    f = REPO / rel; orig = f.read_bytes(); h0 = sha(f); text = orig.decode()
    if text.count(old) != 1:
        print(f"{name}: INVALID anchor x{text.count(old)}"); continue
    f.write_text(text.replace(old, new))
    try:
        r = run(kind, tests)
    finally:
        f.write_bytes(orig)
    total += 1; killed += r.returncode != 0
    tail = [ln for ln in (r.stdout + r.stderr).splitlines() if ln.strip()][-1][:80]
    print(f"{name} [{rel.split('/')[-1]}]: {'KILLED' if r.returncode else 'SURVIVED'} | {tail} | restored sha256 ok={sha(f) == h0}")

# Data mutants on the committed results.parquet of the scratch copy.
RES = REPO / "data/derived/results.parquet"
def data_mutant(name, edit, test):
    global killed, total
    orig = RES.read_bytes(); h0 = sha(RES)
    import pyarrow as pa, pyarrow.parquet as pq
    t = pq.read_table(RES)
    df = t.to_pandas()
    col, rows, value = edit(df)                      # one column, the rows to change, the new value
    vals = t.column(col).to_pylist()
    for i in rows:
        vals[i] = value
    k = t.schema.get_field_index(col)
    t = t.set_column(k, t.schema.field(k), pa.array(vals, type=t.schema.field(k).type))
    pq.write_table(t, RES)
    try:
        r = run("py", [test])
    finally:
        RES.write_bytes(orig)
    total += 1; killed += r.returncode != 0
    tail = [ln for ln in (r.stdout + r.stderr).splitlines() if ln.strip()][-1][:80]
    print(f"{name} [results.parquet]: {'KILLED' if r.returncode else 'SURVIVED'} | {tail} | restored sha256 ok={sha(RES) == h0}")

from scipy import stats
def give_bmp_its_p(df):
    k = ((df.family == "event_test") & (df.hypothesis == "H1") & (df.statistic == "bmp_t") & (df.adjustment == "market")).to_numpy().nonzero()[0]
    return "p_value", list(k), float(2 * stats.t.sf(abs(df.loc[k[0], "stat"]), df.loc[k[0], "df"]))
def cut_holm_as_reported(df):
    return "p_holm", list((df.subgroup_key == "season_cut").to_numpy().nonzero()[0]), 0.046875
if ONLY in (None, "data"):
  data_mutant("data: an oversized row keeps its p-value", give_bmp_its_p, f"{TG}::test_the_committed_rows_withhold_exactly_the_oversized_statistics")
  data_mutant("data: the season-cut Holm p is the reported one", cut_holm_as_reported, f"{TG}::test_the_committed_season_cut_row_is_the_holm_counterfactual")
print(f"SUMMARY killed {killed} of {total}")
