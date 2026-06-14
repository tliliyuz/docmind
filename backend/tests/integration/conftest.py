"""自动为 integration/ 下所有测试添加 integration marker"""
from pathlib import Path

import pytest

_INTEGRATION_DIR = Path(__file__).resolve().parent


def pytest_collection_modifyitems(items):
    for item in items:
        if _INTEGRATION_DIR in Path(item.fspath).resolve().parents:
            item.add_marker(pytest.mark.integration)
