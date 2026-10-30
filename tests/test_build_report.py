# Tests for tools/build_report.py's link rewriting: the PDF is rendered from a local file, so a relative link
# would become a file:// path on the build machine (found by the milestone-5 verifier: five such links).
#
# Mutations this module must catch (each applied to a scratch copy, the test seen to fail, the file restored and
# its SHA-256 checked):
#   - public_href returning a relative href unchanged
#   - public_href joining the href to the repository root instead of docs/report/
#   - public_href rewriting an https:// or #anchor link

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("build_report", REPO / "tools/build_report.py")
br = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(br)


def test_a_relative_link_points_at_the_public_repository():
    assert br.public_href("../../DATA.md") == br.PUBLIC_BLOB + "DATA.md"
    assert br.public_href("../adr/0002-day-zero-convention.md") == br.PUBLIC_BLOB + "docs/adr/0002-day-zero-convention.md"


def test_absolute_and_anchor_links_are_kept():
    assert br.public_href("https://example.org/x") == "https://example.org/x"
    assert br.public_href("#results") == "#results"
