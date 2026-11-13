"""Lab 13_01_05 (Lecture 28.6), the wiki resource template and the decline prompt typed by the student, read in process."""

import runpy
from pathlib import Path

from tests.fixtures.lab_copy import lab_copy

LAB = Path(__file__).resolve().parents[1] / "labs" / "13_01_05_resources_and_prompts.py"
CHECK = (
    "    if not path.is_relative_to(WIKI_DIR.resolve()) or not path.is_file():\n"
    '        raise ResourceError(f"no wiki page named {page!r}")\n'
)
TEMPLATE = '@lab.resource("dataflow://wiki/{page}")'
CONFIG_FIRST_LINE = '"""The only place a model id lives.'


def _run(path: Path, capsys) -> list[str]:
    runpy.run_path(str(path), run_name="__main__")
    return capsys.readouterr().out.splitlines()


def test_lists_reads_and_renders(capsys):
    out = _run(LAB, capsys)
    assert "resources ['dataflow://policy/returns']" in out
    assert "templates ['dataflow://wiki/{page}']" in out
    assert "prompts [('decline_refund', ['order_id', 'reason'])]" in out
    assert "policy_first_line # DataFlow return policy" in out
    assert "wiki shipping.md first_line # DataFlow shipping" in out
    assert "prompt role user" in out
    assert "prompt text We cannot refund order DF-1001. Reason: outside the 30 day window." in out
    assert "system_prompt | # DataFlow return policy" in out


def test_an_escaping_or_missing_name_is_refused(capsys):
    out = _run(LAB, capsys)
    assert "wiki missing.md refused MCPError no wiki page named 'missing.md'" in out
    assert "wiki escape refused MCPError Resource not found: 'dataflow://wiki/..%2F..%2Fconfig.py'" in out
    assert "direct escape refused no wiki page named '../../config.py'" in out


def test_without_the_check_the_direct_call_escapes_and_fastmcp_still_screens(capsys, tmp_path):
    copy = lab_copy(LAB, tmp_path, CHECK, "")
    out = _run(copy, capsys)
    assert "direct escape read " + CONFIG_FIRST_LINE in out
    assert "wiki escape refused MCPError Resource not found: 'dataflow://wiki/..%2F..%2Fconfig.py'" in out
    missing = next(line for line in out if line.startswith("wiki missing.md refused"))
    assert "No such file or directory" in missing and "wiki" in missing


def test_without_the_check_or_the_screen_the_read_escapes_over_mcp(capsys, tmp_path):
    copy = lab_copy(LAB, tmp_path, CHECK, "")
    copy = lab_copy(copy, tmp_path, TEMPLATE, TEMPLATE[:-1] + ", security=None)")
    out = _run(copy, capsys)
    assert "wiki escape read " + CONFIG_FIRST_LINE in out
