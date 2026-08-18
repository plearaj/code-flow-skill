"""The theme token, and the file that fills it.

Theming is the one feature in this project with no failure signal: a user's CSS
is inlined verbatim into a generated page, nothing validates it, and a page that
renders wrong looks exactly like a page that renders right until someone opens
it. These tests cover the parts that *are* checkable — that the token exists,
that it sits where later declarations win, and that the shipped file cannot
silently break the light/dark toggle.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

THEMED_SCAFFOLDS = (
    "viewer.template.html",
    "report.template.html",
    "index.template.html",
    "bundle.template.html",
)


@pytest.mark.parametrize("name", THEMED_SCAFFOLDS)
def test_scaffold_carries_the_theme_token(repo_root: Path, name: str) -> None:
    text = (repo_root / "templates" / "shared" / name).read_text(encoding="utf-8")
    assert text.count("__THEME_CSS__") == 1, (
        f"{name} must carry exactly one __THEME_CSS__ token"
    )


@pytest.mark.parametrize("name", THEMED_SCAFFOLDS)
def test_theme_token_comes_after_both_palettes(repo_root: Path, name: str) -> None:
    """The token must sit after the `[data-theme="light"]` block.

    `:root` and `[data-theme="light"]` have equal CSS specificity, so whichever
    is declared last wins. A token placed before the light block would let the
    built-in light palette override the user's colours in light mode only —
    a theme that works until you press the toggle, which is worse than one that
    does not work at all.
    """
    text = (repo_root / "templates" / "shared" / name).read_text(encoding="utf-8")
    root = text.index(":root{")
    light = text.index('[data-theme="light"]{')
    token = text.index("__THEME_CSS__")
    assert root < light < token, (
        f"{name}: __THEME_CSS__ must come after both the :root and "
        f'[data-theme="light"] blocks, so user declarations win in both modes'
    )


def test_shipped_theme_declares_both_palettes(repo_root: Path) -> None:
    """The shipped file must show both blocks, not just `:root`.

    A user who edits a `:root`-only file gets their colours in dark mode and
    their colours in light mode — the toggle appears dead. Shipping both blocks
    pre-filled makes the working shape the default shape.
    """
    css = (repo_root / "templates" / "shared" / "theme.css").read_text(encoding="utf-8")
    assert re.search(r"^:root\s*\{", css, re.MULTILINE), "theme.css has no :root block"
    assert re.search(r'^\[data-theme="light"\]\s*\{', css, re.MULTILINE), (
        "theme.css has no [data-theme=\"light\"] block, so editing it would "
        "break the light/dark toggle"
    )


def test_shipped_theme_is_inert(repo_root: Path) -> None:
    """Every declaration in the shipped file must be commented out.

    The installer overwrites `.code-flow/` templates on every run. If the shipped
    theme carried live declarations, a re-install would be indistinguishable from
    a theme edit, and anyone who had customised their copy would silently lose it
    on upgrade. Shipped inert, the file is a documented menu; the user opts in by
    uncommenting.
    """
    css = (repo_root / "templates" / "shared" / "theme.css").read_text(encoding="utf-8")
    live = [
        line
        for line in css.splitlines()
        if re.match(r"\s*--[a-z-]+\s*:", line) and not line.lstrip().startswith("/*")
    ]
    assert not live, f"theme.css ships live declarations: {live[:3]}"
