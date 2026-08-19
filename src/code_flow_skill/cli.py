from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from importlib.resources import files


def _template_root() -> Path:
    """Return the directory holding the template trees.

    Prefers the packaged location (``code_flow_skill/templates``, placed there
    by hatchling force-include). Falls back to the repository's root
    ``templates/`` directory so the installer also works when run directly
    from a source checkout, where the packaged copy does not exist.
    """
    packaged = Path(str(files("code_flow_skill").joinpath("templates")))
    if packaged.is_dir():
        return packaged
    return Path(__file__).resolve().parents[2] / "templates"


def _template_path(*parts: str) -> Path:
    return _template_root().joinpath(*parts)


# Every scaffold here is tool-agnostic: every command template references one
# of them, so all of them install regardless of --tool. Names may carry a
# subdirectory (the tracers do), and are written under `.code-flow/` verbatim.
# This table and the one in bin/install.js must stay in step; the
# installed-file-set tests in both languages are what holds them there.
_SHARED_FILES = (
    ("viewer.template.html", "interactive viewer"),
    ("report.template.html", "quality report viewer"),
    ("index.template.html", "flow index"),
    ("theme.css", "your theme"),
    ("bundle.template.html", "bundled viewer"),
    ("tracers/_common.py", "shared tracer core"),
    ("tracers/trace_python.py", "Python tracer"),
    ("tracers/trace_typescript.mjs", "TypeScript tracer"),
    ("tracers/trace_rust.py", "Rust tracer"),
    ("tracers/trace_java.py", "Java tracer"),
    ("tracers/trace_c_family.py", "C/C++/Objective-C/C# tracer"),
    ("tracers/README.md", "tracer contract"),
)


def _install_shared(target: Path) -> None:
    """Copy every tool-agnostic scaffold into ``target``.

    A plain copy, deliberately: ``shutil.copyfile`` preserves bytes, where a
    text-mode read/write round-trip would translate "\\n" to "\\r\\n" on
    Windows and silently corrupt every shipped template.
    """
    for name, label in _SHARED_FILES:
        parts = name.split("/")
        out = target.joinpath(".code-flow", *parts)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(_template_path("shared", *parts), out)
        print(f"Installed {label} template: {out}")


# Every value --tool accepts. Not the same thing as `_TOOL_FILES` below: a host
# can be selectable without having files of its own. Copilot, Codex and
# Antigravity read `.agents/skills/` and nothing this installer writes
# elsewhere, so they appear here and not there.
_VALID_TOOLS = ("claude", "copilot", "codex", "antigravity", "gemini")

# The hosts that read `.agents/skills/`. Claude Code is deliberately absent:
# its documented skill locations are `~/.claude/skills/`, `.claude/skills/` and
# plugin directories, with no `.agents/` among them, so a Claude-only install
# that wrote there would leave four files nothing reads.
_AGENTS_HOSTS = frozenset({"copilot", "codex", "antigravity", "gemini"})

# Each host installs one file per command. This table and the one in
# bin/install.js must stay in step; the installed-file-set tests in both
# languages are what holds them there.
_TOOL_FILES = {
    "claude": (
        (("claude", "code-flow.map.md"), (".claude", "commands", "code-flow.map.md")),
        (("claude", "code-flow.quality.md"), (".claude", "commands", "code-flow.quality.md")),
    ),
    "gemini": (
        (("gemini", "code-flow.map.toml"), (".gemini", "commands", "code-flow.map.toml")),
        (("gemini", "code-flow.quality.toml"), (".gemini", "commands", "code-flow.quality.toml")),
    ),
    "copilot": (
        (
            ("copilot", "code-flow.map.prompt.md"),
            (".github", "prompts", "code-flow.map.prompt.md"),
        ),
        (
            ("copilot", "code-flow.quality.prompt.md"),
            (".github", "prompts", "code-flow.quality.prompt.md"),
        ),
    ),
}

_TOOL_LABELS = {"claude": "Claude", "gemini": "Gemini", "copilot": "Copilot"}

# One canonical SKILL.md per command, copied unchanged to every directory a host
# discovers skills from.
#
# `.agents/skills/` is the open standard's shared location — Copilot, both
# Antigravity surfaces, OpenAI Codex and the legacy Gemini CLI all read it — so
# it installs regardless of --tool, the way the .code-flow/ scaffolds do. It is
# also the entirety of Codex support: Codex discovers repository skills from
# $CWD/.agents/skills and $REPO_ROOT/.agents/skills and has no --tool value of
# its own. `.claude/skills/` has exactly one consumer no other path serves,
# Claude Code, so it rides on that selection instead; a `--tool gemini` install
# must still leave no `.claude/` behind. This table and the one in
# bin/install.js must stay in step; the installed-file-set tests in both
# languages hold them there.
_SKILL_NAMES = ("code-flow-map", "code-flow-quality")

# What one installed skill is made of, per destination. SKILL.md goes to every
# discovery root. `agents/openai.yaml` carries the implicit-invocation policy for
# Codex alone, and Codex reads only `.agents/skills/`, so shipping it under
# `.claude/skills/` would be a file no host there reads — Claude Code and Copilot
# both take that policy from SKILL.md's frontmatter instead.
_SKILL_FILES = ("SKILL.md",)
_AGENTS_SKILL_FILES = ("SKILL.md", "agents/openai.yaml")


def _install_skills(target: Path, root: str, files: tuple[str, ...]) -> None:
    """Copy both skills into one discovery root.

    A plain copy, deliberately: ``shutil.copyfile`` preserves bytes, where a
    text-mode read/write round-trip would translate "\\n" to "\\r\\n" on Windows
    and silently corrupt every shipped template.
    """
    for name in _SKILL_NAMES:
        for rel in files:
            parts = rel.split("/")
            out = target.joinpath(root, "skills", name, *parts)
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(_template_path("shared", name, *parts), out)
            print(f"Installed skill file: {out}")


def _install_tool(target: Path, name: str) -> None:
    """Copy every template belonging to one host into ``target``.

    A plain copy, deliberately: ``shutil.copyfile`` preserves bytes, where a
    text-mode read/write round-trip would translate "\\n" to "\\r\\n" on
    Windows and silently corrupt every shipped template.
    """
    # A host with no table entry is served entirely by `.agents/skills/`.
    for src_parts, dst_parts in _TOOL_FILES.get(name, ()):
        out = target.joinpath(*dst_parts)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(_template_path(*src_parts), out)
        print(f"Installed {_TOOL_LABELS[name]} template: {out}")


def _gemini_is_in_use(target: Path) -> bool:
    """Whether this project shows a sign of Gemini CLI.

    Gemini CLI stopped serving free, Pro, Ultra and individual Code Assist users
    on 2026-06-18. Its successor, Antigravity, does not read ``.gemini/commands/``
    at all — it reads the same skill paths the other hosts do. The TOML commands
    still matter to Gemini Code Assist Standard/Enterprise licence holders and to
    paid API-key users, so they still ship; installing them into every project
    would just leave a dead directory in the overwhelming majority of them.

    The signal is the *target's own* ``.gemini/`` directory. Both Antigravity
    surfaces keep their workspace files under ``.agents/``, and their globals
    under ``~/.gemini/antigravity/`` and ``~/.gemini/antigravity-cli/`` — so a
    project-level ``.gemini/`` is specific to Gemini CLI in a way that
    ``~/.gemini/`` is emphatically not. Checking the home directory would
    misfire on every Antigravity user.
    """
    return (target / ".gemini").exists()


_SKIPPED_GEMINI_NOTICE = """
Skipped the Gemini CLI templates: no .gemini/ directory in {target}.
Gemini CLI was retired for individual users on 2026-06-18, and Antigravity
reads the same skill paths as the other hosts. If you use Gemini CLI on a
Code Assist Standard or Enterprise licence, install them with:

  code-flow-skill --tool gemini
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Install Code Flow skill templates")
    parser.add_argument("--target", default=".", help="Project directory to update")
    parser.add_argument(
        "--tool",
        default="all",
        choices=[*_VALID_TOOLS, "all"],
        help="Template target to install",
    )
    args = parser.parse_args()

    target = Path(args.target).resolve()

    # `--tool gemini` is an explicit request and always installs. A heuristic
    # must never overrule someone who said exactly what they wanted.
    skipped_gemini = False
    if args.tool != "all":
        selected = [args.tool]
    elif _gemini_is_in_use(target):
        # Every valid tool. Derived from _VALID_TOOLS rather than hand-typed:
        # codex and antigravity own no files of their own (see _TOOL_FILES
        # above), so a second hardcoded list here would be a literal that
        # nothing observable — not the installed files, not stdout — could
        # distinguish from ["claude", "copilot"]. Deriving from _VALID_TOOLS
        # closes that gap by construction instead of relying on an assertion
        # to catch it.
        selected = list(_VALID_TOOLS)
    else:
        # Every valid tool except gemini, for the same reason.
        selected = [name for name in _VALID_TOOLS if name != "gemini"]
        skipped_gemini = True

    for name in selected:
        _install_tool(target, name)

    if "claude" in selected:
        _install_skills(target, ".claude", _SKILL_FILES)
    if _AGENTS_HOSTS.intersection(selected):
        _install_skills(target, ".agents", _AGENTS_SKILL_FILES)

    if skipped_gemini:
        # Say what was skipped and how to get it. A silent omission would look
        # identical to a broken install to anyone who does use Gemini CLI.
        print(_SKIPPED_GEMINI_NOTICE.format(target=target))

    _install_shared(target)


if __name__ == "__main__":
    main()
