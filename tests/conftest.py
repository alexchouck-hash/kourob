"""Shared fixtures.

DEFAULTS.md: no network in unit tests; model calls are mocked through the runner's
`local` adapter.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src" / "kourob"


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def src_root() -> Path:
    return SRC


@pytest.fixture
def node_dir(tmp_path: Path) -> Path:
    """An empty directory a node can be initialised into."""
    d = tmp_path / "demo"
    d.mkdir()
    return d
