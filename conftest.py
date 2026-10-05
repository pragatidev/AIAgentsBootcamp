"""pytest reads this file before it walks the repo's folders.

The scripts at the top of labs/ are programs you run, not test files, but three of them end in
_test.py. A pytest run started outside the repo misses pytest.ini and would import them, and
importing a lab runs it: one calls your model, one rewrites files and starts pytest again. This
hook keeps pytest out of every script at the top of labs/, from any folder. The check folders
under labs/19_* hold real tests and are still collected, and so is everything pytest.ini names.
"""

from pathlib import Path

LABS = Path(__file__).resolve().parent / "labs"


def pytest_ignore_collect(collection_path, config):
    if collection_path.suffix == ".py" and collection_path.resolve().parent == LABS:
        return True
    return None
