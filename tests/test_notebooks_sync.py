# Tests for tools/build_notebooks.py. The notebooks on disk must be exactly what
# the builder makes from src/. If you change src/ or the builder and forget to
# run tools/build_notebooks.py, the first test fails.

import contextlib
import io

import nbformat
import pytest


@pytest.fixture
def builder(load_tool):
    return load_tool("build_notebooks")


def test_notebook_on_disk_is_in_sync(builder):
    assert builder.check(), "Run: uv run python tools/build_notebooks.py"


def test_every_notebook_is_built_and_checked(builder):
    assert list(builder.NOTEBOOKS) == ["00_scaffold_tour", "01_events", "02_iv_measures"]
    for name in builder.NOTEBOOKS:
        assert builder.check(builder.NOTEBOOK_DIR / f"{name}.ipynb", name), name


def test_modified_notebook_is_reported_out_of_sync(builder, tmp_path):
    # Start from the correct text. Change one character of one cell. The
    # check must notice it.
    good = tmp_path / "good.ipynb"
    good.write_text(builder.render(), encoding="utf-8")
    assert builder.check(good)

    bad = tmp_path / "bad.ipynb"
    bad.write_text(builder.render().replace("Scaffold tour", "Scaffold tour!"), encoding="utf-8")
    assert not builder.check(bad)


@pytest.mark.parametrize("newline", ["\r\n", "\r"], ids=["crlf", "lone-cr"])
def test_notebook_with_other_line_endings_is_reported_out_of_sync(builder, tmp_path, newline):
    # Same text, but every "\n" is written as "\r\n" (Windows) or "\r". Reading the
    # file as text would turn them back into "\n" and call it equal. The bytes
    # differ, so the check must say "out of sync".
    good_text = builder.render()
    assert "\r" not in good_text  # the build itself uses only "\n"
    path = tmp_path / "other_newlines.ipynb"
    path.write_bytes(good_text.replace("\n", newline).encode("utf-8"))
    assert path.read_text(encoding="utf-8") == good_text  # as text it looks identical
    assert not builder.check(path)


def test_missing_notebook_is_reported_out_of_sync(builder, tmp_path):
    assert not builder.check(tmp_path / "nope.ipynb")


def test_main_check_exit_codes(builder, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(builder, "NOTEBOOK_DIR", tmp_path)
    path = tmp_path / "01_events.ipynb"

    # Nothing on disk yet: out of sync, exit code 1, and a clear message.
    assert builder.main(["--check"]) == 1
    assert "OUT OF SYNC" in capsys.readouterr().err

    # Build them, and now the check passes with exit code 0.
    assert builder.main([]) == 0
    assert path.read_text(encoding="utf-8") == builder.render("01_events")
    assert builder.main(["--check"]) == 0
    assert "OK" in capsys.readouterr().out

    # Edit one by hand: out of sync again, and the message names it.
    path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")
    assert builder.main(["--check"]) == 1
    assert "01_events" in capsys.readouterr().err


@pytest.mark.parametrize("name", ["00_scaffold_tour", "01_events", "02_iv_measures"])
def test_build_is_deterministic(builder, name):
    assert builder.render(name) == builder.render(name)


@pytest.mark.parametrize("name, n_cells", [("00_scaffold_tour", 7), ("01_events", 7), ("02_iv_measures", 11)])
def test_notebook_has_no_outputs_and_fixed_ids_and_metadata(builder, name, n_cells):
    nb = nbformat.reads(builder.render(name), as_version=4)
    assert (nb.nbformat, nb.nbformat_minor) == (4, 5)
    assert nb.metadata["kernelspec"]["name"] == "python3"
    # ids cell-00, cell-01, ... in order.
    assert [c["id"] for c in nb.cells] == [f"cell-{i:02d}" for i in range(n_cells)]
    for cell in nb.cells:
        if cell.cell_type == "code":
            assert cell.outputs == []
            assert cell.execution_count is None


def run_cells(builder, name):
    """Run the code cells of a freshly built notebook (the sync test says the file
    on disk is the same), one after another in one shared namespace (like a
    kernel), and return what each prints."""
    nb = nbformat.reads(builder.render(name), as_version=4)
    namespace = {}
    printed = []
    for cell in nb.cells:
        if cell.cell_type != "code":
            continue
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exec(compile(cell.source, cell["id"], "exec"), namespace)
        printed.append(buffer.getvalue())
    return printed


def test_events_notebook_cells_run(builder, monkeypatch, tmp_path):
    monkeypatch.setenv("VOL_DATA_DIR", str(tmp_path))   # it must not need the cache
    printed = run_cells(builder, "01_events")
    lines = printed[0].splitlines()
    # ADR 0002 §2: AAPL AMC 10-30 -> day -1 10-30, day 0 10-31; GOOGL as BMO vs AMC.
    assert lines[0] == "2025-10-30 AMC -> day -1 2025-10-30  day 0 2025-10-31"
    assert lines[1] == "2024-10-29 BMO -> day -1 2024-10-28  day 0 2024-10-29"
    assert lines[2] == "2024-10-29 AMC -> day -1 2024-10-29  day 0 2024-10-30"
    assert lines[3] == "2025-05-03 None -> day -1 2025-05-02  day 0 2025-05-05"
    assert printed[1].splitlines() == ["2024-11-30 Q1 matched", "2025-02-28 None orphan", "2025-05-31 Q3 matched",
                                       "2025-08-31 Q4 matched"]
    # The funnel from the committed tables: its first line is the calendar count.
    assert "Calendar events of the 50 companies" in printed[2].splitlines()[0]
    assert "'not_checked'" in printed[2]
    # The survivorship caveat is printed with the counts (milestone-1 review, claim 14).
    assert any(line.startswith("Caveat: Survivorship:") for line in printed[2].splitlines())


def test_iv_notebook_cells_run(builder, monkeypatch, tmp_path):
    monkeypatch.setenv("VOL_DATA_DIR", str(tmp_path))   # it must not need the cache
    printed = run_cells(builder, "02_iv_measures")
    # Black-76: F 100, K 110, w 0.04, DF 0.99 -> 4.249091 (tests/test_iv_atom.py works it by hand).
    assert printed[0].splitlines() == ["call 4.249091", "w back from the price 0.0400000000",
                                       "a call above Black76(w = 4) has no root: None"]
    # The clock: 11 and 20 sessions (Thanksgiving closed), 15 and 29 calendar days.
    assert printed[1].splitlines() == ["2025-10-30 -> 2025-11-14 11 sessions, 15 calendar days",
                                       "2025-10-30 -> 2025-11-28 20 sessions, 29 calendar days"]
    # ADR 0003's oracle and its calendar-clock contrast.
    assert printed[2].splitlines()[0] == "E = 0.00088284, sigma_d^2 = 2.3667e-04 per session"
    assert "implied move sqrt(E) = 2.9713%" in printed[2] and "E = 0.00120404" in printed[2]
    # The leak: clean-only 0.2245 against blind 0.2340 (tests/test_termstructure.py works both).
    assert printed[3].strip() == "extrap_clean cm30 0.2245, blind 0.2340"
    # The committed event_iv has the AAPL event (read from data/derived, not the cache).
    assert printed[4].startswith("E 0.000")


def test_notebook_code_cells_run(builder, monkeypatch, tmp_path):
    monkeypatch.setenv("VOL_DATA_DIR", str(tmp_path))
    printed = run_cells(builder, "00_scaffold_tour")

    # Cell 1: data_dir() prints the folder that we set.
    assert printed[0].strip() == str(tmp_path)
    # Cell 2: 14:00 at +02:00 is 12:00 UTC.
    assert '"generated_at": "2026-10-27T12:00:00Z"' in printed[1]
    # Cell 3: getsource prints the function, starting with its "def" line.
    assert printed[2].startswith("def envelope(")
