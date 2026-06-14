"""自动为 unit/ 下所有测试添加 unit marker"""
from pathlib import Path

import pytest

_UNIT_DIR = Path(__file__).resolve().parent


def pytest_collection_modifyitems(items):
    for item in items:
        if _UNIT_DIR in Path(item.fspath).resolve().parents:
            item.add_marker(pytest.mark.unit)
