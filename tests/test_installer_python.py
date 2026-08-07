"""Installer file-placement tests for the Python CLI."""
from __future__ import annotations

from pathlib import Path

# The exact set ``--tool all`` must produce — nothing missing, nothing extra.
# Both installers (this one and bin/install.js) are asserted against the same
# literal list, which is what keeps them in lockstep.
EXPECTED_ALL = [
    ".claude/commands/code-flow.map.md",
    ".code-flow/viewer.template.html",
    ".gemini/commands/code-flow.map.toml",
    ".github/prompts/code-flow.map.prompt.md",
]


def _installed_paths(root: Path) -> list[str]:
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())


def test_tool_all_installs_exactly_the_expected_file_set(
    tmp_path: Path, run_python_installer
) -> None:
    run_python_installer(tmp_path, tool="all")
    assert _installed_paths(tmp_path) == EXPECTED_ALL


def test_installs_viewer_scaffold(tmp_path: Path, run_python_installer) -> None:
    run_python_installer(tmp_path)
    viewer = tmp_path / ".code-flow" / "viewer.template.html"
    assert viewer.is_file()
    assert "__FLOW_DATA__" in viewer.read_text(encoding="utf-8")


def test_tool_selection_installs_only_that_tool(tmp_path: Path, run_python_installer) -> None:
    run_python_installer(tmp_path, tool="gemini")
    assert not (tmp_path / ".claude").exists()
    assert (tmp_path / ".gemini").is_dir()


def test_installs_claude_map_command(tmp_path: Path, run_python_installer) -> None:
    run_python_installer(tmp_path, tool="claude")
    assert (tmp_path / ".claude" / "commands" / "code-flow.map.md").is_file()
    assert not (tmp_path / ".claude" / "commands" / "code-flow.md").exists()


def test_installs_gemini_map_command(tmp_path: Path, run_python_installer) -> None:
    run_python_installer(tmp_path, tool="gemini")
    assert (tmp_path / ".gemini" / "commands" / "code-flow.map.toml").is_file()
    assert not (tmp_path / ".gemini" / "commands" / "code-flow.toml").exists()


def test_installs_copilot_prompt_file(tmp_path: Path, run_python_installer) -> None:
    run_python_installer(tmp_path, tool="copilot")
    assert (tmp_path / ".github" / "prompts" / "code-flow.map.prompt.md").is_file()


def test_copilot_install_does_not_touch_instructions_file(
    tmp_path: Path, run_python_installer
) -> None:
    instructions = tmp_path / ".github" / "copilot-instructions.md"
    instructions.parent.mkdir(parents=True)
    instructions.write_text("# My own notes\n", encoding="utf-8")

    run_python_installer(tmp_path, tool="copilot")

    assert instructions.read_text(encoding="utf-8") == "# My own notes\n"


def test_install_is_repeatable(tmp_path: Path, run_python_installer) -> None:
    run_python_installer(tmp_path)
    first = {
        p.relative_to(tmp_path).as_posix(): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file()
    }
    run_python_installer(tmp_path)
    second = {
        p.relative_to(tmp_path).as_posix(): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file()
    }
    assert first == second


def test_installed_files_are_byte_identical_to_their_templates(
    tmp_path: Path, repo_root: Path, run_python_installer
) -> None:
    """The installer must be a plain copy: no text-mode read/write round-trip
    may alter line endings or any other byte of the source template (this is
    what silently broke on Windows, where Path.write_text() translates "\\n"
    to "\\r\\n")."""
    run_python_installer(tmp_path)

    installed_to_source = {
        tmp_path / ".claude" / "commands" / "code-flow.map.md":
            repo_root / "templates" / "claude" / "code-flow.map.md",
        tmp_path / ".gemini" / "commands" / "code-flow.map.toml":
            repo_root / "templates" / "gemini" / "code-flow.map.toml",
        tmp_path / ".github" / "prompts" / "code-flow.map.prompt.md":
            repo_root / "templates" / "copilot" / "code-flow.map.prompt.md",
        tmp_path / ".code-flow" / "viewer.template.html":
            repo_root / "templates" / "shared" / "viewer.template.html",
    }

    for installed, source in installed_to_source.items():
        assert installed.read_bytes() == source.read_bytes(), (
            f"{installed} is not byte-identical to its source template {source}"
        )
