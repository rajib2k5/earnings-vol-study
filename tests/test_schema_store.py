# Tests for src/earnings_vol/schema.py (the registry and its licence rule),
# store.py (the checked writer) and params.py.
#
# Mutations this module must catch (applied by hand, each seen to fail):
#   - a registry value column with a _yf suffix but class F (the R <=> suffix test)
#   - write_derived keeping class-R columns
#   - write_derived dropping a class-R column named in keep_restricted (milestone 2)
#   - committed_schema keeping every class-R column of a table that names one in keep_restricted
#   - Table accepting a keep_restricted name that is not a class-R column
#   - validate() not checking enum members
#   - params_hash computed from the raw YAML text (comments would change it)

from datetime import date, datetime, timezone

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest

from earnings_vol import params, schema, store
from earnings_vol.schema import C, Table


def test_class_r_exactly_when_suffixed_over_every_value_column():
    # data model §2.1: over value columns (keys excluded) a column is class R
    # exactly when it ends in _yf or _cboe. Both directions are checked.
    for table in schema.REGISTRY.values():
        for col in table.value_columns():
            assert (col.licence == "R") == schema.has_restricted_suffix(col.name), (table.name, col.name)


def test_the_restricted_columns_are_the_ones_the_data_model_lists():
    assert schema.MARKET_DAILY.restricted() == ("vix_close_cboe", "ln_vix_cboe")
    assert set(schema.TIMING_CHECK.restricted()) == set(schema.TIMING_CHECK.names) - {"event_id"}
    for name in ("security", "ticker_alias", "session", "events", "eps", "session_snapshot", "iv_daily", "event_iv"):
        assert schema.REGISTRY[name].restricted() == (), name
        assert schema.REGISTRY[name].committed, name
    # Local only: market_daily (VIX) and chain_expiry (about 190k rows; its DF is a FRED value).
    assert not schema.MARKET_DAILY.committed and not schema.CHAIN_EXPIRY.committed
    # Owner decision of 2026-10-29: the one class-R column committed is timing_check's gap verdict.
    committed_r = {t.name: t.keep_restricted for t in schema.REGISTRY.values() if t.keep_restricted}
    assert committed_r == {"timing_check": ("gap_verdict_yf",)}
    assert store.committed_schema(schema.TIMING_CHECK).names == ("event_id", "gap_verdict_yf")


def test_enums_never_have_a_null_member():
    for table in schema.REGISTRY.values():
        for col in table.columns:
            assert all(v not in (None, "", "NULL", "<NULL>") for v in col.enum), (table.name, col.name)


def test_registry_refuses_malformed_columns():
    with pytest.raises(ValueError):
        C("x", "datetime")
    with pytest.raises(ValueError):
        C("x", "string", licence="Q")
    with pytest.raises(ValueError):
        C("x", "enum")              # an enum needs its values


T = Table("demo", (C("id", "string", key=True), C("d", "date32", nullable=True), C("n", "int16", nullable=True),
                   C("x", "float64"), C("e", "enum", enum=("a", "b")), C("v_yf", "float64", licence="R"),
                   C("flag", "bool")), committed=True)


def demo(**over):
    df = pd.DataFrame({"id": ["k1", "k2"], "d": [date(2025, 1, 2), None], "n": [3, None], "x": [0.5, 1.5],
                       "e": ["a", "b"], "v_yf": [1.0, 2.0], "flag": [True, False]})
    for k, v in over.items():
        df[k] = pd.Series(v, dtype=object)
    df["n"] = pd.Series(over.get("n", [3, None]), dtype=object)
    return df


def test_validate_accepts_a_good_table():
    store.validate(demo(), T)


@pytest.mark.parametrize("over, message", [
    ({"e": ["a", "c"]}, "not in"),                       # unknown enum value
    ({"x": [0.5, np.nan]}, "NOT NULL"),                  # null in a NOT NULL float
    ({"x": [0.5, np.inf]}, "not float64"),               # infinity is never a value
    ({"n": [3, 2**15]}, "outside int16"),
    ({"n": [3.0, None]}, "not int16"),                   # a float where an int belongs
    ({"d": [datetime(2025, 1, 2, 9, 30), None]}, "not date32"),   # a datetime would lose its time
    ({"id": ["k1", "k1"]}, "not unique"),
    ({"flag": [1, 0]}, "not bool"),
])
def test_validate_names_the_broken_rule(over, message):
    with pytest.raises(store.SchemaError, match=message):
        store.validate(demo(**over), T)


def test_validate_refuses_other_columns():
    with pytest.raises(store.SchemaError, match="columns"):
        store.validate(demo().drop(columns=["flag"]), T)


def test_write_and_read_round_trip_with_manifest(tmp_path):
    path = tmp_path / "stage" / "demo.parquet"
    when = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
    store.write_table(demo(), T, path, params_hash="h" * 64, dolt_commits={"earnings": "c"}, now=when)
    back = store.read_table(path, T)
    assert back["d"].tolist() == [date(2025, 1, 2), None] and back["n"].tolist() == [3, None]
    assert back["e"].tolist() == ["a", "b"]
    man = store.manifest_path(path).read_text()
    assert '"rows": 2' in man and '"written_utc": "2026-10-29T12:00:00Z"' in man and '"params_hash": "hhhh' in man
    # The enum is stored dictionary-encoded, as ADR 0001 §2 says.
    assert str(pq.read_schema(path).field("e").type).startswith("dictionary")


def test_write_derived_drops_class_r_and_gives_the_same_bytes_twice(tmp_path):
    out = store.write_derived(demo(), T, tmp_path / "a")
    names = pq.read_schema(out).names
    assert "v_yf" not in names and names == ["id", "d", "n", "x", "e", "flag"]
    again = store.write_derived(demo(), T, tmp_path / "b")
    assert out.read_bytes() == again.read_bytes()


def test_write_derived_keeps_only_the_named_class_r_columns(tmp_path):
    t = Table("demo_r", (C("id", "string", key=True), C("v_yf", "float64", licence="R"),
                         C("w_cboe", "float64", licence="R")), committed=True, keep_restricted=("v_yf",))
    out = store.write_derived(pd.DataFrame({"id": ["k1"], "v_yf": [1.0], "w_cboe": [2.0]}), t, tmp_path)
    assert pq.read_schema(out).names == ["id", "v_yf"]


def test_keep_restricted_must_name_class_r_columns_of_a_committed_table():
    with pytest.raises(ValueError, match="not class-R"):
        Table("x", (C("id", "string", key=True), C("v", "float64")), committed=True, keep_restricted=("v",))
    with pytest.raises(ValueError, match="committed table"):
        Table("x", (C("id", "string", key=True), C("v_yf", "float64", licence="R")), committed=False,
              keep_restricted=("v_yf",))


def test_write_derived_refuses_local_tables_and_stray_suffixes(tmp_path):
    with pytest.raises(store.SchemaError, match="local only"):
        store.committable(pd.DataFrame(), schema.MARKET_DAILY)
    stray = Table("stray", (C("id", "string", key=True), C("gap_yf", "float64", licence="F")), committed=True)
    with pytest.raises(store.SchemaError, match="not class R"):
        store.committable(pd.DataFrame({"id": ["a"], "gap_yf": [1.0]}), stray)


def test_params_hash_ignores_comments_and_order_but_not_values(tmp_path):
    a = tmp_path / "a.yaml"
    b = tmp_path / "b.yaml"
    c = tmp_path / "c.yaml"
    a.write_text("x: 1\ny: [1, 2]\n")
    b.write_text("# a comment\ny: [1, 2]\nx: 1\n")
    c.write_text("x: 2\ny: [1, 2]\n")
    pa_, pb, pc = params.load(a), params.load(b), params.load(c)
    assert pa_.params_hash == pb.params_hash != pc.params_hash
    # sha256 of '{"x":1,"y":[1,2]}' (the canonical JSON), computed independently:
    import hashlib
    assert pa_.params_hash == hashlib.sha256(b'{"x":1,"y":[1,2]}').hexdigest()
    with pytest.raises(TypeError):
        pa_.raw["x"] = 3                                 # the parsed mapping is read-only


def test_project_params_load_and_match_the_adrs():
    p = params.load()
    assert p.date_range("samples", "daily") == (date(2024, 12, 5), date(2026, 10, 26))   # ADR 0004 §5
    assert list(p["windows"]["baseline"]) == [-60, -22] and list(p["windows"]["exclusion_zone"]) == [-21, 10]
    assert p.day("timing", "lookup_from") == date(2024, 9, 11)
    assert len(p.params_hash) == 64
