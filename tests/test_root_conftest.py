"""The root conftest.py keeps pytest out of the lab scripts, even from the folder above the repo."""

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _root_conftest():
    spec = importlib.util.spec_from_file_location("bootcamp_root_conftest", ROOT / "conftest.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_lab_scripts_are_ignored_and_check_tests_are_not():
    hook = _root_conftest().pytest_ignore_collect
    for name in ("06_01_04_invoke_and_test.py", "07_03_05_miss_to_test.py", "10_03_02_load_test.py"):
        assert (ROOT / "labs" / name).is_file()
        assert hook(ROOT / "labs" / name, None) is True
    for path in (
        ROOT / "labs" / "19_dataflow" / "starter" / "check" / "test_desk.py",
        ROOT / "tests" / "test_smoke.py",
        ROOT / "labs",
    ):
        assert hook(path, None) is None


def test_run_from_the_folder_above_never_imports_a_lab_script(tmp_path):
    repo = tmp_path / "above" / "AIAgentsBootcamp"
    (repo / "labs" / "19_demo" / "check").mkdir(parents=True)
    shutil.copy(ROOT / "conftest.py", repo / "conftest.py")
    marker = tmp_path / "lab_was_imported.txt"
    (repo / "labs" / "99_01_01_calls_a_model_test.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('yes', encoding='utf-8')\n\n"
        "def test_never_runs():\n    assert False\n",
        encoding="utf-8",
    )
    (repo / "labs" / "19_demo" / "check" / "test_check.py").write_text(
        "def test_check_folder_still_collected():\n    assert True\n", encoding="utf-8"
    )
    run = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=tmp_path / "above",
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    assert not marker.exists(), run.stdout
    assert run.returncode == 0, run.stdout + run.stderr
    assert "1 passed" in run.stdout
