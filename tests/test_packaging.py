"""Tests that the built wheel actually carries the template files."""
from __future__ import annotations

import json
import re
import subprocess
import zipfile
from pathlib import Path

EXPECTED_IN_WHEEL = (
    "code_flow_skill/templates/claude/code-flow.map.md",
    "code_flow_skill/templates/claude/code-flow.quality.md",
    "code_flow_skill/templates/gemini/code-flow.map.toml",
    "code_flow_skill/templates/gemini/code-flow.quality.toml",
    "code_flow_skill/templates/copilot/code-flow.map.prompt.md",
    "code_flow_skill/templates/copilot/code-flow.quality.prompt.md",
    "code_flow_skill/templates/shared/viewer.template.html",
    "code_flow_skill/templates/shared/report.template.html",
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


def test_readme_files_written_table_lists_exactly_the_installed_set(repo_root: Path) -> None:
    """The README's "Files written" table is the canonical answer to "what does
    this put in my repo", and it drifted: it still listed the three
    `code-flow.map.*` paths after the installer began writing six plus the
    viewer. Nothing caught it, because no test read the README.

    Compared against `EXPECTED_ALL` — the same set both installers' own tests
    assert — rather than a second hand-written list, so there is exactly one
    place to update when the installed set changes.

    Scoped to the table's own rows (lines beginning with `|`), not the whole
    section: the prose under the table names `.code-flow/viewer.template.html`
    again, so an unscoped search would pass with that row deleted.
    """
    from .test_installer_python import EXPECTED_ALL

    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    section = re.search(r"\n## Files written\n(.*?)(?=\n## )", readme, re.DOTALL)
    assert section is not None, "README has no '## Files written' section"
    rows = [line for line in section.group(1).splitlines() if line.startswith("|")]
    listed = sorted(
        set(re.findall(r"`((?:\.[\w.-]+)/[^`]+)`", "\n".join(rows)))
    )
    assert listed == sorted(EXPECTED_ALL), (
        "README 'Files written' table does not match the installed file set:\n"
        f"  README:    {listed}\n"
        f"  installer: {sorted(EXPECTED_ALL)}"
    )


def test_package_versions_match_and_are_1_3_0(repo_root: Path) -> None:
    npm_version = json.loads((repo_root / "package.json").read_text(encoding="utf-8"))["version"]
    pyproject = (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"', pyproject, re.MULTILINE)
    assert match is not None, "no version found in pyproject.toml"
    assert npm_version == match.group(1) == "1.3.0"
