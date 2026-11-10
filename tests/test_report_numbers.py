"""tools/report_numbers.py: every measured number in the report, the README and the PR/FAQ comes from the data.

The expected strings below are worked out by hand from the committed inputs (the arithmetic is in the comments); none
is read from the code under test.

Mutations this module must catch (each applied by hand to tools/report_numbers.py, the module seen to fail, the file
restored and its SHA-256 compared):
  - R01 fnum writes an ASCII hyphen instead of the Unicode minus
  - R02 fp gives p-values below 0.01 three significant digits (0.00781 for H2's floor)
  - R03 fpct keeps one decimal (9.6% for H5's G1 size)
  - R04 --check compares the report only, not the README and PR/FAQ blocks
  - R05 render's unknown-key guard removed (a bare KeyError that names neither the template nor the key's role)
  - R05c the guard removed and the lookup made tolerant, so an unknown placeholder stays in the text
    (the lookup made tolerant with the guard kept is equivalent: the guard runs first)
  - R06 H1's estimate read from the mean-adjusted twin, not the market-adjusted primary
  - R07 lookups.left printed as the required count (473), not required minus done
  - R08 cross_check no longer compares H5's Holm p between results.parquet and drivers.json
  - R09 prose_check no longer checks that H2's season cut is not rejected
  - R10 the stage comparison of the pinned look-up count skipped (always "as pinned")
  - R11 h1.pct_fall computed as −estimate (19.9%) instead of 1 − exp(estimate)
Added after the milestone-5 review (docs/validation/m5-ledger.md, claims 2 and 10):
  - R12 the placeholder pattern back to lowercase keys only (a `{{H2.twoway_t}}` passes through unrendered)
  - R13 the G1 cross-check of tests.json's rates and pass flags against results.parquet and the band removed
  - R14 the H7 F cross-check (results.parquet against implied_vs_realised.json) removed (the review's X2)
  - R15 one prose claim made always true (the H2 sign and floor claim; the review's X1 on another claim)
  - R16 the claim "E at day −2 gives a larger b" made always true
  - R17 --check no longer looks at the PDF and DOCX stamp
  - R18 the realised day-0 range read from the params window (meta.json) instead of the events
Added with the Cboe VX* cross-check (2026-11-09; docs/validation/vx-ledger.md §4):
  - R19 the bar-i prose claim made always true
  - R20 the bar-iv timing-label prose claim made always true
  - R21 the maturity prose claim made always true
  - R22 the VX primary-sample size no longer compared with meta.json
  - R23 the VX events.parquet hash no longer compared with the committed file
  - R24a the pooled part of the longer-gap slope claim made always true
  - R24b the per-name part of the longer-gap slope claim made always true
Added with SEC EDGAR as the timing source (2026-11-09; docs/validation/edgar-ledger.md §10):
  - R25 lookups.edgar counted from timing_source == "press_release"
  - R26 the cross-check of look-ups done against press releases + EDGAR in events.parquet removed
  - R27 the stage comparison of the open look-ups by reason skipped
  - R28 the stage comparison of the gap-questioned EDGAR labels skipped
  - R29 the bar-iv prose claim (most events on a document's label) made always true
Added with the review fixes of 2026-11-09 (docs/validation/vx-ledger.md §9): each new VX* prose claim made always
true (R30-R40: ADR slope falsifier, correlation falsifier, crush-ratio falsifier, the sd-ratio claim, GS's yearly
step, the Monday snapshot calendar, Tuesday-to-Friday r, r without day-0 changes, the stepped slopes, the calendar-30
fit, the extrapolation shares); the open look-ups' label count (R41, events_timing counting `sample` none as open);
the stage report's null-label count no longer compared with events.parquet (R42).
"""

from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("report_numbers", REPO / "tools/report_numbers.py")
rn = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rn)

INPUTS = [
    "data/derived/results.parquet",
    "data/derived/events.parquet",
    "data/derived/vx_crosscheck.json",
    "research/prototypes/rhobar_crush.out.txt",
    "README.md",
    "docs/prfaq.md",
    "docs/milestones/05-report-and-polish.md",
    "docs/report/earnings-vol-report.md",
    "docs/report/earnings-vol-report.build.json",
    "docs/report/earnings-vol-report.pdf",
    "docs/report/earnings-vol-report.docx",
]


def copy_inputs(dst: Path) -> Path:
    for rel in INPUTS:
        (dst / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / rel, dst / rel)
    shutil.copytree(REPO / "app/public/data", dst / "app/public/data")
    shutil.copytree(REPO / "docs/report/templates", dst / "docs/report/templates")
    return dst


@pytest.fixture
def root(tmp_path, monkeypatch):
    # No local stage under this VOL_DATA_DIR, so the look-up comparison is skipped unless a test plants one.
    monkeypatch.setenv("VOL_DATA_DIR", str(tmp_path / "no-vol-data"))
    return copy_inputs(tmp_path / "repo")


# --- formatting, by hand ---------------------------------------------------------------------------------

def test_number_formats():
    m = "−"
    assert rn.fnum(-0.19937650756744235, 3) == f"{m}0.199"
    assert rn.fnum(-0.0004, 3) == "0.000"  # no "−0.000"
    assert rn.fsigned(0.23189613281393837, 3) == "+0.232"
    assert rn.fsigned(-0.0014278, 4) == f"{m}0.0014"
    assert rn.fsci(5.800475891414017e-23) == f"5.8e{m}23"
    assert rn.fp(5.800475891414017e-23) == f"5.8e{m}23"
    assert rn.fp(4.0603331239898117e-22) == f"4.1e{m}22"
    assert rn.fp(0.0078125) == "0.0078"  # 2/2^8, two significant digits below 0.01
    assert rn.fp(0.046875) == "0.0469"  # 6 x 2/2^8
    assert rn.fp(0.078125) == "0.0781"
    assert rn.fp(0.7428194211386488) == "0.743"
    assert rn.fp(2.974267e-06) == f"3.0e{m}6"
    assert rn.fp(1.0) == "1"
    assert rn.fpct(0.0955) == "9.55%"
    assert rn.fpct(0.4006024, 1) == "40.1%"
    assert rn.fint(1353) == "1,353"
    with pytest.raises(ValueError):
        rn.fp(float("nan"))


def test_render_refuses_an_unknown_key_and_splice_needs_both_markers():
    with pytest.raises(KeyError, match=r"tpl: unknown number\(s\) nope"):
        rn.render("a {{nope}} b", {"h1.n": ("347", "src")}, "tpl")
    assert rn.render("n = {{ h1.n }}", {"h1.n": ("347", "src")}, "tpl") == "n = 347"
    with pytest.raises(KeyError, match="H2.twoway_t"):  # an upper-case key is a key too, never passed through
        rn.render("t = {{H2.twoway_t}}", {"h2.twoway_t": ("13.43", "src")}, "tpl")
    with pytest.raises(ValueError):
        rn.splice("text without markers", "readme-results", "body", "README.md")
    doc = "a\n<!-- numbers:x -->\nold\n<!-- /numbers:x -->\nb\n"
    assert rn.splice(doc, "x", "new", "f") == "a\n<!-- numbers:x -->\nnew\n<!-- /numbers:x -->\nb\n"


# --- the numbers from the committed data -------------------------------------------------------------------

def test_key_numbers_from_the_committed_data():
    nums = {k: v for k, (v, _) in rn.numbers(rn.load(REPO)).items()}
    m = "−"
    # results.parquet, H1 primary (market-adjusted twoway_date_t): estimate -0.19938, p 5.80e-23, p_holm 4.06e-22.
    assert nums["h1.est"] == f"{m}0.199" and nums["h1.fall"] == "0.199"
    assert nums["h1.p"] == f"5.8e{m}23" and nums["h1.p_holm"] == f"4.1e{m}22"
    # 1 - exp(-0.199377) = 1 - 0.81924 = 0.18076 -> 18.1%
    assert nums["h1.pct_fall"] == "18.1%"
    # 473 required (pinned), 431 done (sample_funnel.json: 421 confirmed + 2 corrected + 1 date_corrected
    # + 7 inferred) -> 42 left; events.parquet timing_source: 20 press_release, 411 edgar (20 + 411 = 431)
    assert (nums["lookups.required"], nums["lookups.done"], nums["lookups.left"]) == ("473", "431", "42")
    assert (nums["lookups.press_release"], nums["lookups.edgar"]) == ("20", "411")
    # Open by reason (pinned; edgar-ledger.md §6): 26 + 11 + 4 + 1 = 42
    assert [nums[f"lookups.open.{k}"] for k in ("no_8k", "edgar_holiday", "other_date", "contradicts")] == [
        "26", "11", "4", "1"]
    assert (nums["lookups.gap_questioned"], nums["lookups.audit"]) == ("37", "50")
    # 922 not_checked events (events.parquet): 892 with a calendar label, 30 with none. Of the 42 open look-ups, 23 are
    # not_checked, NULL-labelled events that can enter a sample (the stage report's by_reason null_label is 23): 42 - 23 = 19
    assert (nums["timing.not_checked"], nums["timing.not_checked_labelled"], nums["timing.not_checked_unlabelled"]) == (
        "922", "892", "30")
    assert (nums["lookups.left_labelled"], nums["lookups.left_unlabelled"]) == ("19", "23")
    # The daily sample's not_checked events by move tercile (sample_funnel.json by_move_tercile): 8 + 5 + 0 = 13
    assert [nums[f"funnel.daily_open.t{t}"] for t in (1, 2, 3)] == ["8", "5", "0"] and nums["funnel.daily_open"] == "13"
    # vx_crosscheck.json, exploratory: 1,515 of 3,697 changes end on a Monday (41%); 1,005 of 1,111 before 2024-09-03
    assert (nums["vx.cal.end_monday"], nums["vx.pooled.n"], nums["vx.cal.end_monday_share"]) == ("1,515", "3,697", "41%")
    assert (nums["vx.cal.early_monday"], nums["vx.cal.early"], nums["vx.cal.era_from"]) == ("1,005", "1,111", "2024-09-03")
    assert (nums["vx.cal.mon_vx"], nums["vx.cal.mon_ours"]) == ("+0.0173", f"{m}0.0053")
    assert (nums["vx.tf.googl.r"], nums["vx.tf.pooled.r"], nums["vx.tf.ibm.r"]) == ("0.814", "0.826", "0.765")
    assert (nums["vx.d0.dropped"], nums["vx.d0.pooled.r"], nums["vx.d0.ibm.r"]) == ("43", "0.747", "0.558")
    assert (nums["vx.step10.pooled.slope"], nums["vx.step10.pooled.rev"]) == ("0.939", "1.011")
    assert (nums["vx.step21.ibm.slope"], nums["vx.step21.ibm.rev"]) == ("0.895", "0.941")
    # Bar ii against the ADR's band: slopes 0.77, 0.79, 0.66 below 0.8; sd ratio sqrt(0.7674 * 1.2299) = 0.97
    assert (nums["vx.ii_below"], nums["vx.ii_below_names"], nums["vx.pooled.sd"]) == ("3", "GOOGL, GS and IBM", "0.97")
    # GS's yearly medians: 2020-22 3.825, 4.105, 4.103; 2023-26 2.060, 1.712, 2.122, 1.764; step 4.011 - 1.9145 = 2.1
    assert [nums[f"vx.gs.{k}"] for k in ("early_lo", "early_hi", "late_lo", "late_hi", "step")] == [
        "3.8", "4.1", "1.7", "2.1", "2.1"]
    # iv_current at 30 calendar days against 21 sessions (same 5,959 days), and the extrapolated shares
    assert (nums["vh.cal.med"], nums["vh.cal.med21"], nums["vh.cal.n"]) == ("0.327", "0.606", "5,959")
    assert (nums["vh.extrap.h42"], nums["vh.extrap.h42_n"], nums["vh.extrap.h10"], nums["vh.extrap.h10_n"]) == (
        "4,160", "5,413", "2,334", "5,964")
    # Bar iv's 34 events: 32 confirmed, 2 not_checked (vx_crosscheck.json)
    assert (nums["vx.iv.documented"], nums["vx.iv.not_checked"]) == ("32", "2")
    # G1 calibrated rejection rates in tests.json: 0.0955, 0.081, 0.1615
    assert (nums["h5.g1"], nums["h6.g1"], nums["h7.g1"]) == ("9.55%", "8.10%", "16.15%")
    # H2: 8 seasons, floor 2/2^8; the cut has 7 seasons, floor 2/2^7 = 0.015625, Holm 0.078125
    assert (nums["h2.floor_g"], nums["h2.p"], nums["h2.cut_g"], nums["h2.cut_p_holm"]) == ("8", "0.0078", "7", "0.0781")
    # The binding family's verdicts
    assert nums["holm.rejected"] == "H1 and H2"
    assert nums["h5.g1_verdict"] == "**fail**" and nums["h1.g1_verdict"] == "pass"


def test_events_timing_counts_labels_and_the_open_events_without_one():
    # Made-up events: not_checked with a label x2, not_checked without one in a sample x2 and outside every sample x1,
    # and a confirmed one without a label (resolved by EDGAR, so not counted).
    ev = pd.DataFrame({
        "timing_source": ["calendar", "calendar", None, None, None, "edgar"],
        "timing_status": ["not_checked"] * 5 + ["inferred"],
        "timing_raw": ["BMO", "AMC", None, None, None, None],
        "sample": ["daily", "coarse", "coarse", "daily", "none", "coarse"]})
    got = rn.events_timing(ev)
    assert (got["not_checked"], got["not_checked_unlabelled"], got["not_checked_open_unlabelled"]) == (5, 3, 2)
    assert got["timing_source"] == {"calendar": 2, "edgar": 1}


def test_check_passes_on_the_committed_files():
    assert rn.main(["--check"]) == 0


# --- --check fails when a rendered file or the data change ----------------------------------------------

@pytest.mark.parametrize("rel, old, new", [
    ("docs/report/earnings-vol-report.md", "falls by 0.199 log points", "falls by 0.198 log points"),
    ("README.md", "| H5 | Does a bigger earnings surprise", "| H5 | Does a larger earnings surprise"),
    ("docs/prfaq.md", "431 of 473 required look-ups done", "432 of 473 required look-ups done"),
])
def test_check_fails_when_a_rendered_file_was_edited(root, capsys, rel, old, new):
    path = root / rel
    text = path.read_text()
    assert old in text
    path.write_text(text.replace(old, new, 1))
    assert rn.main(["--check", "--root", str(root)]) == 1
    assert f"stale: {rel}" in capsys.readouterr().err


def test_new_data_are_rendered_and_make_the_old_files_stale(root, capsys):
    # Move H1's estimate from -0.19938 to -0.21 in both inputs that hold it (results.parquet, tests.json).
    res = pd.read_parquet(root / "data/derived/results.parquet")
    i = res.index[(res.hypothesis == "H1") & (res.role == "primary") & (res.family == "event_test")]
    assert len(i) == 1
    res.loc[i, "estimate"] = -0.21
    res.to_parquet(root / "data/derived/results.parquet")
    tj = root / "app/public/data/tests.json"
    env = json.loads(tj.read_text())
    [row] = [x for x in env["data"]["rows"] if x["hypothesis"] == "H1" and x["role"] == "primary"]
    row["estimate"] = -0.21
    tj.write_text(json.dumps(env))

    assert rn.main(["--check", "--root", str(root)]) == 1
    assert "stale: docs/report/earnings-vol-report.md" in capsys.readouterr().err
    assert rn.main(["--root", str(root)]) == 0
    report = (root / "docs/report/earnings-vol-report.md").read_text()
    # -0.21 -> "−0.210"; the fall 0.210; 1 - exp(-0.21) = 1 - 0.81058 = 0.18942 -> 18.9%
    assert "falls by 0.210 log points on average" in report
    assert "about 18.9%" in report
    assert "| H1 | How much does the 30-day IV fall from day −1 to day 0? | 347 | −0.210 |" in (root / "README.md").read_text()
    # The Markdown is now current, but the PDF and DOCX were built from the old one.
    capsys.readouterr()
    assert rn.main(["--check", "--root", str(root)]) == 1
    err = capsys.readouterr().err
    assert "exports stale" in err and "the pdf export was built from an older Markdown" in err


def test_the_sample_dates_are_the_events_range_and_the_window_apart():
    nums = {k: v for k, (v, _) in rn.numbers(rn.load(REPO)).items()}
    # params.yaml's daily window is 2024-12-05 to 2026-10-26; the 347 events' day 0 run from 2024-12-10 to 2026-10-22
    # (the earliest and latest day0 in event_paths.json per_event).
    assert (nums["sample.day0_from"], nums["sample.day0_to"]) == ("2024-12-05", "2026-10-26")
    assert (nums["sample.first_day0"], nums["sample.last_day0"]) == ("2024-12-10", "2026-10-22")


@pytest.mark.parametrize("change, expect", [
    ("pdf_bytes", "the pdf export was changed after its build"),
    ("no_docx", "the docx export is missing"),
    ("no_stamp", "no docs/report/earnings-vol-report.build.json"),
])
def test_check_fails_when_an_export_is_missing_or_changed(root, capsys, change, expect):
    d = root / "docs/report"
    if change == "pdf_bytes":
        (d / "earnings-vol-report.pdf").write_bytes((d / "earnings-vol-report.pdf").read_bytes() + b"\n")
    elif change == "no_docx":
        (d / "earnings-vol-report.docx").unlink()
    else:
        (d / "earnings-vol-report.build.json").unlink()
    assert rn.main(["--check", "--root", str(root)]) == 1
    assert expect in capsys.readouterr().err


def _edit_results(root, where, column, value):
    res = pd.read_parquet(root / "data/derived/results.parquet")
    i = res.index[where(res)]
    assert len(i) == 1
    res.loc[i, column] = value
    res.to_parquet(root / "data/derived/results.parquet")


def _edit_json(root, kind, fn):
    path = root / "app/public/data" / f"{kind}.json"
    env = json.loads(path.read_text())
    fn(env["data"])
    path.write_text(json.dumps(env))


def _edit_vx(root, fn):
    path = root / "data/derived/vx_crosscheck.json"
    doc = json.loads(path.read_text())
    fn(doc)
    path.write_text(json.dumps(doc))


def _edit_events_source(root, old, new):
    # One event's timing_source changed (made up), so events.parquet no longer matches the funnel's look-up count.
    path = root / "data/derived/events.parquet"
    ev = pd.read_parquet(path)
    src = ev["timing_source"].astype(object)
    src[src.index[src == old][0]] = new
    ev["timing_source"] = src
    ev.to_parquet(path)


def _g1(data, h):
    return [x for x in data["g1"]["calibrated"] if x["hypothesis"] == h][0]


def _flip_h2(root):
    # H2's estimate made negative in both inputs that hold it, so only the sentence ("IV sits ... above") is wrong.
    _edit_results(root, lambda x: (x.hypothesis == "H2") & (x.role == "primary") & (x.family == "event_test"),
                  "estimate", -0.2319)
    _edit_json(root, "tests", lambda d: [x.update(estimate=-0.2319) for x in d["rows"]
                                         if x["hypothesis"] == "H2" and x["role"] == "primary"])


# Each edit makes the inputs disagree with each other, or the data contradict a hand-written sentence. --check must
# name the check that caught it.
CROSS_AND_PROSE = [
    ("H7 F", lambda r: _edit_json(r, "implied_vs_realised", lambda d: d["summary"]["regression"].update(wald_f=1.5)),
     "H7 F results/implied_vs_realised.json"),
    ("G1 rate", lambda r: _edit_json(r, "tests", lambda d: _g1(d, "H1").update(rejection_rate=0.07)),
     "H1 G1 rate results/tests.json"),
    ("G1 flag", lambda r: _edit_json(r, "tests", lambda d: _g1(d, "H5").update(**{"pass": True})),
     "H5 G1 pass flag"),
    ("H2 sign", lambda r: _flip_h2(r), "H2 positive, on its floor"),
    ("b at day -2", lambda r: _edit_results(r, lambda x: (x.model_id == "implied_realised_m2") & (x.term == "b")
                                            & (x.role == "exploratory"), "estimate", 0.60),
     "E read at day -2 gives a larger b"),
    ("timing statuses", lambda r: _edit_json(r, "sample_funnel", lambda d: d["timing_status_counts"].update(
        confirmed=d["timing_status_counts"]["confirmed"] - 1, ambiguous=1)), "no ambiguous, no no_document"),
    ("look-ups by source", lambda r: _edit_events_source(r, "edgar", "calendar"),
     "look-ups done / press releases + EDGAR (events.parquet)"),
    # The Cboe VX* cross-check (data/derived/vx_crosscheck.json); the edited values are made up.
    ("VX bar i", lambda r: _edit_vx(r, lambda d: d["bar_i"]["per_name"]["GOOGL"].update(r=0.9, verdict="pass")),
     "VX bar i fails for GOOGL, IBM and the pooled sample"),
    ("VX timing", lambda r: _edit_vx(r, lambda d: d["bar_iv"]["events"].update(
        timing_status_counts={"not_checked": d["bar_iv"]["events"]["n_events_five_names"]})),
     "most events of the five names rest on a document's timing label"),
    ("VX maturity", lambda r: _edit_vx(r, lambda d: d["volatility_history"]["maturity"]["identification"].update(
        status="UNRESOLVED", horizon=None)), "maturity identified at 21 sessions"),
    ("VX sample", lambda r: _edit_vx(r, lambda d: d["bar_iv"]["events"].update(n_primary_sample=1)),
     "VX bar iv's primary sample / meta.json sample size"),
    ("VX events", lambda r: _edit_vx(r, lambda d: d["inputs"].update(events_sha256="0" * 64)),
     "VX cross-check events.parquet 000000000000 against the committed"),
    ("VX secondary name", lambda r: _edit_vx(r, lambda d: d["secondary"]["AAPL"].update(reverse_slope_reciprocal=1.05)),
     "VX secondary: the pooled slope below 1"),
    ("VX secondary pooled", lambda r: _edit_vx(r, lambda d: d["secondary"]["pooled"]["block20"][
        "reverse_slope_reciprocal"].update(lo=0.99)), "VX secondary: the pooled slope below 1"),
    # The review fixes of 2026-11-09: the ADR's own falsifiers, and the exploratory readings (made-up edits)
    ("VX ADR slope falsifier", lambda r: _edit_vx(r, lambda d: d["bar_ii"]["per_name"]["GS"].update(slope=0.85)),
     "ADR 0003's slope falsifier is met"),
    ("VX ADR correlation falsifier", lambda r: _edit_vx(r, lambda d: [d["bar_i"]["per_name"][nm].update(verdict="fail")
                                                                      for nm in ("AAPL", "AMZN")]),
     "ADR 0003's correlation falsifier is not met"),
    ("VX ADR crush falsifier", lambda r: _edit_vx(r, lambda d: d["bar_iv"].update(ratio=0.7)),
     "ADR 0003's crush-ratio falsifier is not met"),
    ("VX sd ratio", lambda r: _edit_vx(r, lambda d: d["bar_ii"]["per_name"]["pooled"].update(slope=0.5)),
     "the two series' daily changes have nearly the same sd"),
    ("VX GS step", lambda r: _edit_vx(r, lambda d: d["bar_iii"]["per_name"]["GS"]["years"]["2022"].update(
        median_spread=2.0)), "GS's yearly medians step"),
    ("VX Monday", lambda r: _edit_vx(r, lambda d: d["exploratory"]["snapshot_calendar"].update(
        n_end_monday=d["exploratory"]["snapshot_calendar"]["n"])), "changes ending on a Monday are a minority"),
    ("VX Tue-Fri", lambda r: _edit_vx(r, lambda d: d["exploratory"]["bar_i_tue_to_fri"]["IBM"].update(r=0.9)),
     "on Tuesday-to-Friday changes r is above 0.8"),
    ("VX day 0", lambda r: _edit_vx(r, lambda d: d["exploratory"]["bar_i_without_day0"]["pooled"].update(r=0.9)),
     "without the changes that end on a day 0"),
    ("VX stepped", lambda r: _edit_vx(r, lambda d: d["exploratory"]["stepped_changes"]["by_k"]["10"]["IBM"].update(
        slope=0.99)), "the pooled forward slope of non-overlapping changes rises"),
    ("VX calendar 30", lambda r: _edit_vx(r, lambda d: d["volatility_history"]["maturity"]["calendar_30"][
        "median_abs_diff_same_days"].update(calendar_30=0.7)), "iv_current read as 30 calendar days"),
    ("VX extrapolated", lambda r: _edit_vx(r, lambda d: d["volatility_history"]["maturity"]["extrapolated"][
        "by_horizon"]["42"].update(n_beyond_last_expiry=10)), "most 42-session values lie beyond the last listed expiry"),
]


@pytest.mark.parametrize("name, edit, expect", CROSS_AND_PROSE, ids=[c[0] for c in CROSS_AND_PROSE])
def test_disagreeing_or_contradicting_data_fail_the_check(root, capsys, name, edit, expect):
    edit(root)
    assert rn.main(["--check", "--root", str(root)]) == 1
    assert expect in capsys.readouterr().err


def test_inputs_that_disagree_fail_the_check(root, capsys):
    dj = root / "app/public/data/drivers.json"
    env = json.loads(dj.read_text())
    for model in env["data"]["models"]:
        for term in model["terms"]:
            if term.get("hypothesis") == "H5" and term.get("role") == "primary":
                term["p_holm"] = 0.04  # results.parquet says 0.0511
    dj.write_text(json.dumps(env))
    assert rn.main(["--check", "--root", str(root)]) == 1
    assert "H5 p_holm results/drivers.json" in capsys.readouterr().err


def test_data_that_contradict_a_sentence_fail_the_check(root, capsys):
    # The texts say H2's 7-season counterfactual is not rejected (Holm 0.0781). Make it 0.04.
    res = pd.read_parquet(root / "data/derived/results.parquet")
    i = res.index[(res.hypothesis == "H2") & (res.subgroup_key == "season_cut") & (res.family == "event_test")]
    res.loc[i, "p_holm"] = 0.04
    res.to_parquet(root / "data/derived/results.parquet")
    assert rn.main(["--check", "--root", str(root)]) == 1
    assert "H2's season cut not rejected" in capsys.readouterr().err


def test_the_pinned_lookup_count_is_compared_with_a_local_stage_report(root, tmp_path, monkeypatch, capsys):
    vol = tmp_path / "vol"
    meta = json.loads((root / "app/public/data/meta.json").read_text())
    stage = vol / "earnings-vol-study/cache/stage" / meta["data"]["provenance"]["params_hash"][:16]
    stage.mkdir(parents=True)
    monkeypatch.setenv("VOL_DATA_DIR", str(vol))

    def report(n=42, outcome=None, pending=37, on=True, null_label=23):
        # A stage report of an EDGAR run, written by hand: 405 confirmed + 6 inferred + 20 press releases, and the
        # 42 open ones by reason (26 + 11 + 4 + 1).
        out = {"confirmed": 405, "inferred": 6, "press_release": 20, "no_8k": 26, "edgar_holiday": 11,
               "other_date": 4, "contradicts": 1} if outcome is None else outcome
        rep = {"lookup_violations": {"n": n, "by_reason": {"daily_or_mixed_era": 21, "null_label": null_label}},
               "edgar": {"on": on, "outcome": out, "pending_gap_checks": pending}}
        (stage / "events_report.json").write_text(json.dumps(rep))

    report()
    assert rn.main(["--check", "--root", str(root)]) == 0
    assert "42 left + 431 done = 473; open by reason and 37 gap-questioned, as pinned" in capsys.readouterr().out
    report(n=41)  # 41 + 431 = 472
    assert rn.main(["--check", "--root", str(root)]) == 1
    assert "not 473" in capsys.readouterr().err
    report(outcome={"confirmed": 405, "inferred": 6, "press_release": 20, "no_8k": 25, "edgar_holiday": 12,
                    "other_date": 4, "contradicts": 1})  # the same total, another split
    assert rn.main(["--check", "--root", str(root)]) == 1
    assert "open look-ups are" in capsys.readouterr().err
    report(pending=36)
    assert rn.main(["--check", "--root", str(root)]) == 1
    assert "gap-questioned EDGAR labels are 36" in capsys.readouterr().err
    report(null_label=22)
    assert rn.main(["--check", "--root", str(root)]) == 1
    assert "22 open look-ups with a NULL label, events.parquet 23" in capsys.readouterr().err
    report(on=False)
    assert rn.main(["--check", "--root", str(root)]) == 1
    assert "no EDGAR run" in capsys.readouterr().err
