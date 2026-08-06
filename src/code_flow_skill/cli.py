from __future__ import annotations

import argparse
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


def _read_template(*parts: str) -> str:
    return _template_root().joinpath(*parts).read_text(encoding="utf-8")


def _install_claude(target: Path) -> None:
    out = target / ".claude" / "commands" / "code-flow.map.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_read_template("claude", "code-flow.map.md"), encoding="utf-8")
    print(f"Installed Claude template: {out}")


def _install_gemini(target: Path) -> None:
    out = target / ".gemini" / "commands" / "code-flow.map.toml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_read_template("gemini", "code-flow.map.toml"), encoding="utf-8")
    print(f"Installed Gemini template: {out}")


def _install_viewer(target: Path) -> None:
    """Install the tool-agnostic interactive HTML viewer scaffold.

    Every command template references this file, so it is installed
    regardless of the selected tool.
    """
    out = target / ".code-flow" / "viewer.template.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_read_template("shared", "viewer.template.html"), encoding="utf-8")
    print(f"Installed interactive viewer template: {out}")


def _install_copilot(target: Path) -> None:
    out = target / ".github" / "copilot-instructions.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    snippet = _read_template("copilot", "code-flow.instructions.md").strip()
    existing = out.read_text(encoding="utf-8") if out.exists() else ""
    if "## Code Flow — Documentation Generator" in existing:
        print(f"Copilot Code Flow instructions already present: {out}")
        return
    merged = f"{existing.strip()}\n\n{snippet}\n" if existing.strip() else f"{snippet}\n"
    out.write_text(merged, encoding="utf-8")
    print(f"Appended Copilot Code Flow instructions: {out}")


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
