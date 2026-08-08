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


# Both scaffolds are tool-agnostic: every command template references one of
# them, so both install regardless of --tool. This table and the one in
# bin/install.js must stay in step; the installed-file-set tests in both
# languages are what holds them there.
_SHARED_FILES = (
    ("viewer.template.html", "interactive viewer"),
    ("report.template.html", "quality report viewer"),
)


def _install_shared(target: Path) -> None:
    """Copy every tool-agnostic scaffold into ``target``.

    A plain copy, deliberately: ``shutil.copyfile`` preserves bytes, where a
    text-mode read/write round-trip would translate "\\n" to "\\r\\n" on
    Windows and silently corrupt every shipped template.
    """
    for name, label in _SHARED_FILES:
        out = target / ".code-flow" / name
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(_template_path("shared", name), out)
        print(f"Installed {label} template: {out}")


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


def _install_tool(target: Path, name: str) -> None:
    """Copy every template belonging to one host into ``target``.

    A plain copy, deliberately: ``shutil.copyfile`` preserves bytes, where a
    text-mode read/write round-trip would translate "\\n" to "\\r\\n" on
    Windows and silently corrupt every shipped template.
    """
    for src_parts, dst_parts in _TOOL_FILES[name]:
        out = target.joinpath(*dst_parts)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(_template_path(*src_parts), out)
        print(f"Installed {_TOOL_LABELS[name]} template: {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Install Code Flow skill templates")
    parser.add_argument("--target", default=".", help="Project directory to update")
    parser.add_argument(
        "--tool",
        default="all",
        choices=["claude", "gemini", "copilot", "all"],
        help="Template target to install",
    )
    args = parser.parse_args()

    target = Path(args.target).resolve()
    selected = ["claude", "gemini", "copilot"] if args.tool == "all" else [args.tool]

    for name in selected:
        _install_tool(target, name)

    _install_shared(target)


if __name__ == "__main__":
    main()
