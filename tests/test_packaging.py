"""Tests that the built wheel actually carries the template files."""
from __future__ import annotations

import json
import re
import subprocess
import zipfile
from pathlib import Path

EXPECTED_IN_WHEEL = (
    "code_flow_skill/templates/claude/code-flow.map.md",
    "code_flow_skill/templates/gemini/code-flow.map.toml",
    "code_flow_skill/templates/copilot/code-flow.map.prompt.md",
    "code_flow_skill/templates/shared/viewer.template.html",
)


def test_wheel_contains_templates(tmp_path: Path, repo_root: Path) -> None:
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(tmp_path)],
        cwd=repo_root,
        check=True,
        capture_output=True,
    )
    wheels = list(tmp_path.glob("*.whl"))
    assert len(wheels) == 1, f"expected exactly one wheel, got {wheels}"
    with zipfile.ZipFile(wheels[0]) as archive:
        names = archive.namelist()
    missing = [expected for expected in EXPECTED_IN_WHEEL if expected not in names]
    assert not missing, f"wheel is missing template files: {missing}"


def test_source_mirror_is_gone(repo_root: Path) -> None:
    assert not (repo_root / "src" / "code_flow_skill" / "templates").exists()


def test_package_versions_match_and_are_1_0_0(repo_root: Path) -> None:
    npm_version = json.loads((repo_root / "package.json").read_text(encoding="utf-8"))["version"]
    pyproject = (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"', pyproject, re.MULTILINE)
    assert match is not None, "no version found in pyproject.toml"
    assert npm_version == match.group(1) == "1.0.0"
