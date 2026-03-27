from __future__ import annotations

import argparse
from pathlib import Path

from importlib.resources import files


def _read_template(*parts: str) -> str:
    template = files("code_flow_skill").joinpath("templates", *parts)
    return template.read_text(encoding="utf-8")


def _install_claude(target: Path) -> None:
    out = target / ".claude" / "commands" / "code-flow.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_read_template("claude", "code-flow.md"), encoding="utf-8")
    print(f"Installed Claude template: {out}")


def _install_gemini(target: Path) -> None:
    out = target / ".gemini" / "commands" / "code-flow.toml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_read_template("gemini", "code-flow.toml"), encoding="utf-8")
    print(f"Installed Gemini template: {out}")


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


if __name__ == "__main__":
    main()
