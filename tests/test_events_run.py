# The wiring of src/earnings_vol/events/run.py: build() on a tiny hand-made
# world (one company, five calendar rows, four EPS periods), in memory, with no
# cache, no network and no vendor value. The unit tests elsewhere check each
# function; these check that build() calls them, in order, with the
# parameters (delta review, mutant M-c and claim 1a).
#
# Mutations this module must catch (applied by hand, each seen to fail):
#   - the check_sample_ranges call deleted from build() (the delta review's M-c)
#   - build() passing duplicate_days=0 (the duplicate row is matched again)
#   - build() passing window_start="month_start" instead of the parameter

from datetime import date

import pandas as pd
import pytest
import yaml

from earnings_vol import params as params_mod
from earnings_vol.events import run, timing

# A made-up company, BRK.B-shaped (ADR 0002 note 3): a Friday row with no label beside
# the real Saturday release, and Saturday releases otherwise.
CAL = pd.DataFrame({
    "act_symbol": ["XYZ"] * 5,
    "date": [date(2024, 8, 3), date(2024, 11, 1), date(2024, 11, 2), date(2025, 2, 22), date(2025, 5, 3)],
    "when": ["Before market open", None, "Before market open", "Before market open", "Before market open"],
}, dtype=object)
# Made-up EPS values.
HIST = pd.DataFrame({"act_symbol": ["XYZ"] * 4,
                     "period_end_date": [date(2024, 6, 30), date(2024, 9, 30), date(2024, 12, 31), date(2025, 3, 31)],
                     "reported": [1.0, 1.5, 2.0, 2.5], "estimate": [1.25, 1.25, 1.75, 2.25]})


def inputs() -> dict:
    selection = pd.DataFrame({"security_id": ["XYZ"], "name": ["Made-up Co"], "gics_sector": ["Financials"],
                              "gics_sub_industry": ["Made-up"], "cik": ["123"], "in_universe": [True],
                              "cboe_vx_index": [None]})
    return {
        "commits": {"earnings": "e" * 32, "options": "o" * 32},
        "selection": selection,
        "calendar": CAL,
        "eps_history": HIST,
        "eps_estimate": pd.DataFrame(columns=["date", "act_symbol", "period", "period_end_date", "consensus",
                                              "count", "high", "low"]),
        # One made-up bill rate before the first session; no VIX at all.
        "dtb3": pd.DataFrame({"date": [date(2015, 12, 31)], "value": [1.0]}),
        "vix": pd.DataFrame({"date": pd.Series([], dtype=object), "value": pd.Series([], dtype="float64")}),
        "checks_text": ",".join(timing.CHECK_COLUMNS) + "\n",
    }


def no_prices(_symbol):
    return pd.DataFrame({"date": [], "open": [], "close": [], "dividends": []})


def params_with(tmp_path, changes: dict):
    raw = yaml.safe_load(params_mod.DEFAULT_PATH.read_text(encoding="utf-8"))
    for (section, key), value in changes.items():
        raw[section][key] = value
    path = tmp_path / "params.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return params_mod.load(path)


@pytest.fixture(scope="module")
def built():
    return run.build(params_mod.load(), inputs(), no_prices)


def test_build_marks_the_duplicate_row_and_links_the_release(built):
    ev = built["events"].set_index("event_id")
    assert ev.loc["XYZ:2024-11-01", "exclusion_reason"] == "duplicate_row"
    assert ev.loc["XYZ:2024-11-01", "fiscal_period_end"] is None
    assert ev.loc["XYZ:2024-11-02", "fiscal_period_end"] == date(2024, 9, 30)
    eps = built["eps"].set_index("fiscal_period_end")
    # Lags: 08-03 - 06-30 = 34; 11-02 - 09-30 = 33 (not 32, the duplicate's); 02-22 - 12-31 = 53;
    # 05-03 - 03-31 = 33.
    assert eps["event_id"].to_dict() == {date(2024, 6, 30): "XYZ:2024-08-03", date(2024, 9, 30): "XYZ:2024-11-02",
                                         date(2024, 12, 31): "XYZ:2025-02-22", date(2025, 3, 31): "XYZ:2025-05-03"}
    assert eps["lag_days"].tolist() == [34, 33, 53, 33]


def test_build_stops_on_sample_ranges_with_a_gap(tmp_path):
    # The gap the milestone-1 review found: coarse ending 2024-09-09 leaves 09-10 and 09-11 in no sample.
    p = params_with(tmp_path, {("samples", "coarse"): ["2020-04-01", "2024-09-09"]})
    with pytest.raises(ValueError, match="not contiguous"):
        run.build(p, inputs(), no_prices)


def test_build_uses_the_window_parameter(tmp_path):
    # With a fixed window of +40 .. +100 days, the Saturday releases 33-34 days after their
    # periods cannot be linked: the parameter, not a constant, decides.
    p = params_with(tmp_path, {("eps_match", "window_start"): 40})
    eps = run.build(p, inputs(), no_prices)["eps"].set_index("fiscal_period_end")
    assert eps.loc[date(2024, 12, 31), "event_id"] == "XYZ:2025-02-22"
    assert eps.loc[date(2024, 9, 30), "event_id"] is None
