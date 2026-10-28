import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def load_tool():
    """Import a script from tools/ by name, e.g. load_tool("export_app_data").

    tools/ is a folder of scripts, not a package, so "import" does not find it.
    We load the file by its path instead. We get a fresh module each time.
    """
    def load(name: str):
        spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    return load
