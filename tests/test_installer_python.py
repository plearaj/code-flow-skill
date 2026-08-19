"""Installer file-placement tests for the Python CLI."""
from __future__ import annotations

from pathlib import Path

import pytest

# Every path this installer can write — nothing missing, nothing extra. Both
# installers (this one and bin/install.js) are asserted against the same literal
# list, which is what keeps them in lockstep. This is also the set the README's
# "Files written" table must match, since that table answers "what *can* end up
# in my repo", not "what happened in your project".
_SHARED = [
    ".code-flow/bundle.template.html",
    ".code-flow/index.template.html",
    ".code-flow/report.template.html",
    ".code-flow/theme.css",
    ".code-flow/tracers/README.md",
    ".code-flow/tracers/trace_python.py",
    ".code-flow/tracers/trace_typescript.mjs",
    ".code-flow/viewer.template.html",
]
_CLAUDE = [
    ".claude/commands/code-flow.map.md",
    ".claude/commands/code-flow.quality.md",
    ".claude/skills/code-flow-map/SKILL.md",
    ".claude/skills/code-flow-quality/SKILL.md",
]
_AGENTS = [
    ".agents/skills/code-flow-map/SKILL.md",
    ".agents/skills/code-flow-map/agents/openai.yaml",
    ".agents/skills/code-flow-quality/SKILL.md",
    ".agents/skills/code-flow-quality/agents/openai.yaml",
]
_GEMINI = [
    ".gemini/commands/code-flow.map.toml",
    ".gemini/commands/code-flow.quality.toml",
]
_COPILOT = [
    ".github/prompts/code-flow.map.prompt.md",
    ".github/prompts/code-flow.quality.prompt.md",
]

# One row per --tool value. This is the contract the two installers are held
# to, and the identical table lives in test/install.test.js.
EXPECTED_BY_TOOL = {
    "claude": sorted(_CLAUDE + _SHARED),
    "copilot": sorted(_AGENTS + _COPILOT + _SHARED),
    "codex": sorted(_AGENTS + _SHARED),
    "antigravity": sorted(_AGENTS + _SHARED),
    "gemini": sorted(_AGENTS + _GEMINI + _SHARED),
}

EXPECTED_ALL = sorted(_CLAUDE + _AGENTS + _GEMINI + _COPILOT + _SHARED)
EXPECTED_WITHOUT_GEMINI = [p for p in EXPECTED_ALL if not p.startswith(".gemini/")]


def _installed_paths(root: Path) -> list[str]:
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())


def test_tool_all_skips_gemini_when_the_project_shows_no_sign_of_it(
    tmp_path: Path, run_python_installer
) -> None:
    """Gemini CLI was retired for individual users on 2026-06-18 and Antigravity
    does not read `.gemini/commands/`, so writing those two files into every
    project would leave a dead directory in almost all of them."""
    run_python_installer(tmp_path, tool="all")
    assert _installed_paths(tmp_path) == EXPECTED_WITHOUT_GEMINI


def test_tool_all_installs_gemini_when_the_project_already_uses_it(
    tmp_path: Path, run_python_installer
) -> None:
    """The licence remnant is real — Code Assist Standard and Enterprise keep
    Gemini CLI — so a project that already has `.gemini/` must still get the
    TOML commands without anyone passing a flag."""
    (tmp_path / ".gemini").mkdir()
    run_python_installer(tmp_path, tool="all")
    assert _installed_paths(tmp_path) == EXPECTED_ALL


def test_explicit_gemini_selection_overrules_the_heuristic(
    tmp_path: Path, run_python_installer
) -> None:
    """A detector that can silently overrule an explicit `--tool gemini` is worse
    than no detector: it would leave a user who said exactly what they wanted
    with nothing installed and no obvious reason why."""
    run_python_installer(tmp_path, tool="gemini")
    assert (tmp_path / ".gemini" / "commands" / "code-flow.map.toml").is_file()
    assert (tmp_path / ".gemini" / "commands" / "code-flow.quality.toml").is_file()


def test_skipping_gemini_says_so_and_says_how_to_get_it(
    tmp_path: Path, run_python_installer, capsys
) -> None:
    """A silent omission is indistinguishable from a broken install. The notice
    must name what was skipped and the exact flag that installs it."""
    run_python_installer(tmp_path, tool="all")
    out = capsys.readouterr().out
    assert "Skipped the Gemini CLI templates" in out
    assert "--tool gemini" in out


def test_no_skip_notice_when_gemini_is_actually_installed(
    tmp_path: Path, run_python_installer, capsys
) -> None:
    """The inverse of the test above: a notice that always printed would satisfy
    it while telling Gemini users their templates were skipped when they were
    not."""
    (tmp_path / ".gemini").mkdir()
    run_python_installer(tmp_path, tool="all")
    assert "Skipped" not in capsys.readouterr().out


def test_installs_viewer_scaffold(tmp_path: Path, run_python_installer) -> None:
    run_python_installer(tmp_path)
    viewer = tmp_path / ".code-flow" / "viewer.template.html"
    assert viewer.is_file()
    assert "__FLOW_DATA__" in viewer.read_text(encoding="utf-8")


def test_all_shared_files_are_installed_regardless_of_tool(
    tmp_path: Path, run_python_installer
) -> None:
    """The four scaffolds and the theme are tool-agnostic: every command
    template references one of the scaffolds and every scaffold inlines the
    theme, so selecting a single host must still install all five."""
    run_python_installer(tmp_path, tool="claude")
    for name in (
        "viewer.template.html",
        "report.template.html",
        "index.template.html",
        "bundle.template.html",
        "theme.css",
    ):
        assert (tmp_path / ".code-flow" / name).is_file(), f"{name} was not installed"


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


def test_installs_claude_quality_command(tmp_path: Path, run_python_installer) -> None:
    run_python_installer(tmp_path, tool="claude")
    assert (tmp_path / ".claude" / "commands" / "code-flow.quality.md").is_file()


def test_installs_gemini_quality_command(tmp_path: Path, run_python_installer) -> None:
    run_python_installer(tmp_path, tool="gemini")
    assert (tmp_path / ".gemini" / "commands" / "code-flow.quality.toml").is_file()


def test_selecting_one_tool_installs_both_of_its_commands(
    tmp_path: Path, run_python_installer
) -> None:
    run_python_installer(tmp_path, tool="copilot")
    prompts = tmp_path / ".github" / "prompts"
    assert (prompts / "code-flow.map.prompt.md").is_file()
    assert (prompts / "code-flow.quality.prompt.md").is_file()
    assert not (tmp_path / ".claude").exists()
    assert not (tmp_path / ".gemini").exists()


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
    to "\\r\\n").

    `.gemini/` is created first so that `--tool all` installs the TOML commands
    too: the byte-for-byte guarantee applies to every template the installer can
    write, including the ones a default install now skips.
    """
    (tmp_path / ".gemini").mkdir()
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
        tmp_path / ".code-flow" / "report.template.html":
            repo_root / "templates" / "shared" / "report.template.html",
        tmp_path / ".code-flow" / "bundle.template.html":
            repo_root / "templates" / "shared" / "bundle.template.html",
        tmp_path / ".claude" / "commands" / "code-flow.quality.md":
            repo_root / "templates" / "claude" / "code-flow.quality.md",
        tmp_path / ".gemini" / "commands" / "code-flow.quality.toml":
            repo_root / "templates" / "gemini" / "code-flow.quality.toml",
        tmp_path / ".github" / "prompts" / "code-flow.quality.prompt.md":
            repo_root / "templates" / "copilot" / "code-flow.quality.prompt.md",
        tmp_path / ".claude" / "skills" / "code-flow-map" / "SKILL.md":
            repo_root / "templates" / "shared" / "code-flow-map" / "SKILL.md",
        tmp_path / ".agents" / "skills" / "code-flow-map" / "SKILL.md":
            repo_root / "templates" / "shared" / "code-flow-map" / "SKILL.md",
        tmp_path / ".agents" / "skills" / "code-flow-map" / "agents" / "openai.yaml":
            repo_root / "templates" / "shared" / "code-flow-map" / "agents" / "openai.yaml",
        tmp_path / ".claude" / "skills" / "code-flow-quality" / "SKILL.md":
            repo_root / "templates" / "shared" / "code-flow-quality" / "SKILL.md",
        tmp_path / ".agents" / "skills" / "code-flow-quality" / "SKILL.md":
            repo_root / "templates" / "shared" / "code-flow-quality" / "SKILL.md",
        tmp_path / ".agents" / "skills" / "code-flow-quality" / "agents" / "openai.yaml":
            repo_root / "templates" / "shared" / "code-flow-quality" / "agents" / "openai.yaml",
    }

    for installed, source in installed_to_source.items():
        assert installed.read_bytes() == source.read_bytes(), (
            f"{installed} is not byte-identical to its source template {source}"
        )


def test_agent_skills_install_for_a_host_that_reads_them(
    tmp_path: Path, run_python_installer
) -> None:
    """`.agents/skills/` is the open standard's shared location — Copilot, both
    Antigravity surfaces, Codex and the legacy Gemini CLI all read it. Copilot
    reads it in addition to its own prompt files, so selecting it must still
    install `.agents/skills/` alongside them."""
    run_python_installer(tmp_path, tool="copilot")
    for name in ("code-flow-map", "code-flow-quality"):
        assert (tmp_path / ".agents" / "skills" / name / "SKILL.md").is_file(), (
            f".agents/skills/{name}/SKILL.md was not installed"
        )


def test_claude_skills_ride_on_the_claude_selection(
    tmp_path: Path, run_python_installer
) -> None:
    """Claude Code is the only consumer of `.claude/skills/` that no other path
    serves, so it follows the `claude` selection rather than installing
    unconditionally. A `--tool gemini` install must still leave no `.claude/`
    behind — the same promise `test_tool_selection_installs_only_that_tool`
    makes about the command files."""
    run_python_installer(tmp_path, tool="gemini")
    assert (tmp_path / ".agents" / "skills" / "code-flow-map" / "SKILL.md").is_file()
    assert not (tmp_path / ".claude").exists()


def test_claude_selection_installs_only_the_claude_skill_root(
    tmp_path: Path, run_python_installer
) -> None:
    """Claude Code does not read `.agents/skills/` — its documented skill
    locations are `~/.claude/skills/`, `.claude/skills/` and plugin
    directories — so `--tool claude` must not write it."""
    run_python_installer(tmp_path, tool="claude")
    for name in ("code-flow-map", "code-flow-quality"):
        assert (tmp_path / ".claude" / "skills" / name / "SKILL.md").is_file(), (
            f".claude/skills/{name}/SKILL.md was not installed"
        )
    assert not (tmp_path / ".agents").exists()


@pytest.mark.parametrize("tool", sorted(EXPECTED_BY_TOOL))
def test_each_tool_installs_exactly_its_own_set(
    tmp_path: Path, run_python_installer, tool: str
) -> None:
    """Every --tool value writes exactly what that host reads, and nothing else.

    The rows that matter most are `claude`, which must write no
    `.agents/skills/` because Claude Code does not read it, and `codex` /
    `antigravity`, which exist only so those two hosts can be named — before
    this, `.agents/skills/` installed unconditionally because there was no way
    to ask for them.
    """
    run_python_installer(tmp_path, tool=tool)
    assert _installed_paths(tmp_path) == EXPECTED_BY_TOOL[tool]
