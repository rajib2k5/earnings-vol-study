# Tests for tools/build_notebooks.py. The notebook on disk must be exactly what
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
    path = tmp_path / "nb.ipynb"
    monkeypatch.setattr(builder, "NOTEBOOK_PATH", path)

    # Nothing on disk yet: out of sync, exit code 1, and a clear message.
    assert builder.main(["--check"]) == 1
    assert "OUT OF SYNC" in capsys.readouterr().err

    # Build it, and now the check passes with exit code 0.
    assert builder.main([]) == 0
    assert path.read_text(encoding="utf-8") == builder.render()
    assert builder.main(["--check"]) == 0
    assert "OK" in capsys.readouterr().out

    # Edit it by hand: out of sync again.
    path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")
    assert builder.main(["--check"]) == 1


def test_build_is_deterministic(builder):
    assert builder.render() == builder.render()


def test_notebook_has_no_outputs_and_fixed_ids_and_metadata(builder):
    nb = nbformat.reads(builder.render(), as_version=4)
    assert (nb.nbformat, nb.nbformat_minor) == (4, 5)
    assert nb.metadata["kernelspec"]["name"] == "python3"
    # 7 cells: ids cell-00 .. cell-06, in order.
    assert [c["id"] for c in nb.cells] == [f"cell-{i:02d}" for i in range(len(nb.cells))]
    for cell in nb.cells:
        if cell.cell_type == "code":
            assert cell.outputs == []
            assert cell.execution_count is None


def test_notebook_code_cells_run(builder, monkeypatch, tmp_path):
    # Run the code cells of the freshly built notebook (the sync test above
    # says the file on disk is the same), one after another in one shared
    # namespace (like a kernel), and read what they print.
    monkeypatch.setenv("VOL_DATA_DIR", str(tmp_path))
    nb = nbformat.reads(builder.render(), as_version=4)
    namespace = {}
    printed = []
    for cell in nb.cells:
        if cell.cell_type != "code":
            continue
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exec(compile(cell.source, cell["id"], "exec"), namespace)
        printed.append(buffer.getvalue())

    # Cell 1: data_dir() prints the folder that we set.
    assert printed[0].strip() == str(tmp_path)
    # Cell 2: 14:00 at +02:00 is 12:00 UTC.
    assert '"generated_at": "2026-10-27T12:00:00Z"' in printed[1]
    # Cell 3: getsource prints the function, starting with its "def" line.
    assert printed[2].startswith("def envelope(")
