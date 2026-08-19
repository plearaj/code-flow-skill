"""The generated pages have to survive being shared.

A code flow is worth having because you can send it to somebody. The scaffolds
are already single self-contained files for that reason -- no CDN, no fetch, no
sibling assets -- and this file covers the part of "shareable" that is not about
loading: several corporate mail and chat gateways quarantine an HTML attachment
whose SVG carries an in-document `url(#id)` reference, because that is the shape
of a known class of SVG attack. The flow viewer used to reach its arrowheads
that way, and the file could not be sent through Teams. It now draws them.

The rule is stricter than the bug: no scaffold may reference anything by
`url(#...)`, for arrowheads or for gradients, filters, clip paths or masks
somebody adds later. Every one of those has a form that does not need an id.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

SCAFFOLDS = (
    "viewer.template.html",
    "report.template.html",
    "index.template.html",
    "bundle.template.html",
)

# The two scaffolds that draw a flow graph, and so need an arrowhead.
FLOW_SCAFFOLDS = ("viewer.template.html", "bundle.template.html")


def _read(repo_root: Path, name: str) -> str:
    return (repo_root / "templates" / "shared" / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("name", SCAFFOLDS)
def test_scaffold_references_nothing_by_fragment_id(repo_root: Path, name: str) -> None:
    """`url(#...)` is the signature that got a shared flow quarantined."""
    hits = re.findall(r"url\(\s*#[^)]*\)", _read(repo_root, name))
    assert hits == [], (
        f"{name} refers to {hits} by fragment id. A scanner reads that as the "
        "SVG-with-internal-reference shape and quarantines the file, which is "
        "how the flow viewer became unshareable through Teams. Draw the thing "
        "per element instead, the way the edge arrowheads are drawn."
    )


@pytest.mark.parametrize("name", SCAFFOLDS)
def test_scaffold_defines_no_referenceable_svg_elements(repo_root: Path, name: str) -> None:
    """An element only reachable by id is either unused or reached by url(#...).

    Asserting on the definitions as well as the references keeps a half-finished
    change -- a marker added back, its reference not yet written -- from passing.
    """
    text = _read(repo_root, name)
    for tag in ("<marker", "<linearGradient", "<radialGradient", "<clipPath", "<mask", "<filter"):
        assert tag not in text, (
            f"{name} defines {tag}>, which is only usable through url(#id). "
            "See test_scaffold_references_nothing_by_fragment_id."
        )


@pytest.mark.parametrize("name", FLOW_SCAFFOLDS)
def test_flow_scaffold_draws_its_own_arrowheads(repo_root: Path, name: str) -> None:
    """The replacement has to actually be there, or edges lose their direction.

    Without an arrowhead a call graph stops saying which way a call goes, which
    is most of what it is for -- so `url(#ar)` being gone is only half the claim.
    """
    text = _read(repo_root, name)
    assert re.search(r"var ARROW = \"M[-\d. LZz]+\";", text), (
        f"{name} must define the ARROW path its edges end in"
    )
    assert text.count('"class": "ah"') == 1, (
        f"{name} must draw exactly one arrowhead per edge"
    )
    assert re.search(r"\.edge path\.ah\{[^}]*fill:", text), (
        f"{name} must give the arrowhead a fill, since it is filled rather than stroked"
    )


@pytest.mark.parametrize("name", FLOW_SCAFFOLDS)
def test_every_edge_geometry_carries_a_tip(repo_root: Path, name: str) -> None:
    """`anchors` returns where an edge ends; each return must say which way.

    A branch that returns `d` without `tip` renders an arrowhead at
    `translate(undefined,undefined)`, which SVG drops silently -- one edge shape
    loses its arrow and nothing errors. There are four branches: forward and
    back, each left-to-right and top-down.
    """
    text = _read(repo_root, name)
    body = text[text.index("function anchors("):]
    body = body[: body.index("function modHue(")]
    assert body.count("return {") == 4, f"{name}: anchors() should have four branches"
    assert body.count("tip: {") == 4, (
        f"{name}: every branch of anchors() must report a tip, or that edge shape "
        "renders without an arrowhead and nothing complains"
    )
