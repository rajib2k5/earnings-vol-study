# p04 — Hand mutants for tests/test_edgar_timing.py, run on a scratch copy of the tree so the
# shared working tree is never mutated. Each: apply, run the named tests, expect a
# failure, restore, compare SHA-256 with the original.
# Run: .venv/bin/python docs/validation/probes/edgar/p04_mutants.py   (copies src, tests, data/manual and
# params.yaml to a temporary folder; PYTHONPATH points there, so the editable install is not used)
import hashlib, os, shutil, subprocess, sys, tempfile
from pathlib import Path

REPO = Path("/home/rajib2k5/dev/earnings-vol-study")
W = Path(tempfile.mkdtemp(prefix="edgar-mutants-"))
for d in ("src", "tests", "data/manual"):
    shutil.copytree(REPO / d, W / d, ignore=shutil.ignore_patterns("__pycache__"))
for f in ("params.yaml", "pyproject.toml"):
    shutil.copy2(REPO / f, W / f)

E, T, R = "src/earnings_vol/ingest/edgar.py", "src/earnings_vol/events/timing.py", "src/earnings_vol/events/run.py"
TF = "tests/test_edgar_timing.py"
MUT = [
    ("M1", E, "since - timedelta(days=PAGE_MARGIN_DAYS)", "since", [f"{TF}::test_pages_needed_reaches_back_to_since_with_a_margin"]),
    ("M2", E, "if seen[acc] != row:", "if False:", [f"{TF}::test_merge_filings_keeps_each_accession_once_and_refuses_two_readings"]),
    ("M3", E, "    m = merge_filings(doc, pages)\n    out = []", "    m = merge_filings(doc, [])\n    out = []", [f"{TF}::test_an_8k_only_in_an_extra_page_is_found"]),
    ("M4", E, 'pages = [json.loads((base / n).read_text(encoding="utf-8")) for n in pages_needed(doc, since)]', "pages = []", [f"{TF}::test_fetch_all_caches_the_pages_and_read_cached_needs_no_network"]),
    ("M5", E, '    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)', '    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=NY)', [f"{TF}::test_acceptance_time_is_a_utc_instant_across_daylight_saving"]),
    ("M6", E, "if not isinstance(value, str) or not _ACCEPTANCE.fullmatch(value):", "if not isinstance(value, str):", [f"{TF}::test_parse_acceptance_refuses_any_other_format"]),
    ("M7", E, "if date(year + 1, 1, 1).weekday() == 5:", "if False:", [f"{TF}::test_edgar_holidays_include_new_years_eve_and_the_measured_closures"]),
    ("M8", E, "holidays = set().union(*(edgar_holidays(y) for y in {d.year for d in window}))", "holidays = edgar_holidays(announce.year)", [f"{TF}::test_the_holiday_window_crosses_the_year"]),
    ("M9", E, "elif len(readings) > 1:", "elif False:", [f"{TF}::test_two_8ks_in_the_window_that_read_differently_are_not_read"]),
    ("M10", T, "elif timing_raw == label:", "elif True:", [f"{TF}::test_resolve_edgar_status_table"]),
    ("M11", T, 'elif reading["ny_date"] != announce:', "elif False:", [f"{TF}::test_resolve_edgar_status_table"]),
    ("M12", E, "    for cik in ciks:\n        doc, pages = read_cached(cik, raw_dir, since)", "    for cik in ciks[:1]:\n        doc, pages = read_cached(cik, raw_dir, since)", [f"{TF}::test_predecessor_ciks_are_read_with_the_current_one"]),
    ("M13", R, "scope = edgar_scope(viol, checks)", "scope = set()", [f"{TF}::test_build_with_edgar_resolves_only_what_the_rule_allows"]),
    ("M14", R, 'return {v["event_id"] for v in viol} | pr', 'return {v["event_id"] for v in viol}', [f"{TF}::test_build_with_edgar_resolves_only_what_the_rule_allows"]),
    ("M15", E, '"cik": f"{int(cik):010d}", "requests_this_run"', '"cik": f"{int(cik):010d}", "ua": user_agent(), "requests_this_run"', [f"{TF}::test_the_fetch_record_never_holds_the_user_agent"]),
    ("M16", R, 'edgar_on = bool(t.get("edgar", False))', "edgar_on = True", [f"{TF}::test_build_without_edgar_never_reads_it"]),
    ("M17", E, "out = {columbus, vet} | {d for d in EDGAR_CLOSED_MEASURED if d.year == year}", "out = {columbus, vet}", ["tests/test_ingest_sources.py::test_edgar_holidays", f"{TF}::test_edgar_holidays_include_new_years_eve_and_the_measured_closures"]),
]
env = dict(os.environ, PYTHONPATH=str(W / "src"))
env.pop("SEC_EDGAR_USER_AGENT", None)
py = str(REPO / ".venv/bin/python")
# Which earnings_vol is imported?
print(subprocess.run([py, "-c", "import earnings_vol, sys; print(earnings_vol.__file__)"], cwd=W, env=env,
                     capture_output=True, text=True).stdout.strip())
base = subprocess.run([py, "-m", "pytest", "-q", "-p", "no:cacheprovider", TF, "tests/test_ingest_sources.py"], cwd=W, env=env,
                      capture_output=True, text=True)
print("baseline:", base.stdout.strip().splitlines()[-1])
for mid, f, old, new, tests in MUT:
    path = W / f
    orig = path.read_bytes()
    h0 = hashlib.sha256(orig).hexdigest()
    s = orig.decode()
    assert s.count(old) == 1, (mid, s.count(old))
    path.write_text(s.replace(old, new))
    r = subprocess.run([py, "-m", "pytest", "-q", "-p", "no:cacheprovider", *tests], cwd=W, env=env,
                       capture_output=True, text=True)
    last = r.stdout.strip().splitlines()[-1]
    path.write_bytes(orig)
    h1 = hashlib.sha256(path.read_bytes()).hexdigest()
    print(f"{mid:4s} rc {r.returncode} {'KILLED' if r.returncode != 0 else 'SURVIVED'}  {last}  restored sha256 {'ok' if h0 == h1 else 'MISMATCH'} {h1[:12]}")
# The scratch copy equals the repo's files after all restores:
for f in (E, T, R, TF, "tests/test_ingest_sources.py"):
    a = hashlib.sha256((REPO / f).read_bytes()).hexdigest(); b = hashlib.sha256((W / f).read_bytes()).hexdigest()
    print("final", f, "same as repo:", a == b, a[:12])
shutil.rmtree(W)
