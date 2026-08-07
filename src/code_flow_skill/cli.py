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


def _install_claude(target: Path) -> None:
    out = target / ".claude" / "commands" / "code-flow.map.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(_template_path("claude", "code-flow.map.md"), out)
    print(f"Installed Claude template: {out}")


def _install_gemini(target: Path) -> None:
    out = target / ".gemini" / "commands" / "code-flow.map.toml"
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(_template_path("gemini", "code-flow.map.toml"), out)
    print(f"Installed Gemini template: {out}")


def _install_viewer(target: Path) -> None:
    """Install the tool-agnostic interactive HTML viewer scaffold.

    Every command template references this file, so it is installed
    regardless of the selected tool.
    """
    out = target / ".code-flow" / "viewer.template.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(_template_path("shared", "viewer.template.html"), out)
    print(f"Installed interactive viewer template: {out}")


def _install_copilot(target: Path) -> None:
    out = target / ".github" / "prompts" / "code-flow.map.prompt.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(_template_path("copilot", "code-flow.map.prompt.md"), out)
    print(f"Installed Copilot prompt: {out}")


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
        if name == "claude":
            _install_claude(target)
        elif name == "gemini":
            _install_gemini(target)
        else:
            _install_copilot(target)

    _install_viewer(target)


if __name__ == "__main__":
    main()
