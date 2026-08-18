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


def _root_block_props(text: str) -> set[str]:
    """Return every custom property name declared inside a `:root{...}` block.

    Matches by name only (`--foo` before its colon), never by value — several
    scaffolds intentionally disagree on the value of a handful of shared
    properties (`--shadow`'s dark alpha, `--bg-2`'s light shade), and this
    helper must not care.
    """
    match = re.search(r":root\{(.*?)\n\}", text, re.DOTALL)
    assert match, "no :root{...} block found"
    return set(re.findall(r"--[a-z0-9-]+(?=\s*:)", match.group(1)))


def test_theme_lists_every_property_any_scaffold_declares(repo_root: Path) -> None:
    """`theme.css` is documented (README, CHANGELOG) as the complete menu of
    colours the pages use. Nothing enforced that claim — a property could be
    added to a scaffold's `:root` block and never make it into the editable
    theme, which is exactly how `--high`/`--medium`/`--low` (the quality
    report's per-severity accents) and `--section`/`--section-ghost` (the index
    page's headings) went missing. This asserts presence only: the four
    scaffolds are allowed to disagree on a property's exact shade, but not on
    whether the property exists for a user to edit at all.
    """
    theme_css = (repo_root / "templates" / "shared" / "theme.css").read_text(encoding="utf-8")
    theme_props = set(re.findall(r"--[a-z0-9-]+(?=\s*:)", theme_css))

    for name in THEMED_SCAFFOLDS:
        text = (repo_root / "templates" / "shared" / name).read_text(encoding="utf-8")
        scaffold_props = _root_block_props(text)
        missing = scaffold_props - theme_props
        assert not missing, (
            f"{name} declares {sorted(missing)} in :root that theme.css never "
            f"mentions — the shipped theme is no longer the complete menu it is "
            f"documented as being"
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
