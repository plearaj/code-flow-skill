"""Shared fixtures for the installer test suite.

The installer is imported in-process rather than shelled out to, so that a
failure surfaces as a Python traceback instead of a non-zero exit code.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def run_python_installer(monkeypatch) -> Callable[..., None]:
    """Return a callable that runs the Python installer against a target dir."""
    from code_flow_skill import cli

    def _run(target: Path, tool: str = "all") -> None:
        monkeypatch.setattr(
            sys, "argv", ["code-flow-skill", "--target", str(target), "--tool", tool]
        )
        cli.main()

    return _run
