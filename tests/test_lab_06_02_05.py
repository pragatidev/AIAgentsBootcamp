"""Lab 06.02.05 (11.5), the student's route test typed in the lab. The lab only ever uses the scripted model. Its last
line starts pytest on tests/test_dataflow_routes.py, which the suite runs itself, so here that call is recorded,
not made."""

import runpy
import subprocess
from pathlib import Path

import pytest

from tests.fixtures.fake_model import FakeChatModel
from tests.fixtures.lg_r1 import lab_copy_dataflow

LAB = Path(__file__).resolve().parents[1] / "labs" / "06_02_05_test_routes.py"
STRONG = (
    '        assert out["route"] == route, (ticket, out["route"])\n'
    "        assert key in out, (ticket, sorted(out))\n"
    '        assert words in out["reply"], (ticket, out["reply"])\n'
)
WEAK = '        assert out["reply"]\n'


@pytest.fixture
def pytest_call(monkeypatch):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    return calls


def test_strong_test_passes_right_and_fails_wrong(pytest_call, capsys):
    lab = runpy.run_path(str(LAB), run_name="__main__")
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "model none: every test here uses the scripted FakeChatModel"
    assert out[-3] == "PASS test_routes_are_right, right routes"
    assert out[-2] == "FAIL test_routes_are_right, every ticket sent to escalate ('Where is order DF-1001?', 'escalate')"
    assert out[-1] == "pytest_exit 0"
    argv, kwargs = pytest_call[-1]
    assert argv[1:] == ["-m", "pytest", "tests/test_dataflow_routes.py", "-q"]
    lab["test_routes_are_right"]()
    with pytest.raises(AssertionError):
        lab["test_routes_are_right"](make_model=lambda route: FakeChatModel(route="escalate"))


def test_weak_assertion_passes_on_a_wrong_route(pytest_call, tmp_path, capsys):
    broken = lab_copy_dataflow(LAB, tmp_path, STRONG, WEAK)
    lab = runpy.run_path(str(broken), run_name="__main__")
    out = capsys.readouterr().out.splitlines()
    assert out[-3:-1] == ["PASS test_routes_are_right, right routes", "PASS test_routes_are_right, every ticket sent to escalate"]
    lab["test_routes_are_right"](make_model=lambda route: FakeChatModel(route="policy"))
