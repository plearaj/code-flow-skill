"""The node `id` derivation rule, made executable.

`id` is prose in three prompt templates, which means nothing checks that the
rule is followed — including by this repository's own example artifacts. This
module implements the rule once and asserts the examples obey it, so a change
to the rule that the examples contradict fails the suite instead of shipping.
"""
from __future__ import annotations

import json
import re
from pathlib import Path


def derive_id(file: str, name: str) -> str:
    """Return the `id` for a function named ``name`` defined in ``file``.

    Mirrors the rule stated in every map template: drop the extension from the
    path's last segment only, append the unqualified function name, lowercase,
    replace every character outside ``[a-z0-9_]`` with ``_``, collapse runs, and
    trim. The same-name-in-one-file collision suffix (``_l<line>``) is not
    applied here — it depends on the *file's* contents, which a pure path/name
    function cannot see.
    """
    head, _, last = file.rpartition("/")
    stem = last.rpartition(".")[0] or last
    combined = f"{head}/{stem}_{name}" if head else f"{stem}_{name}"
    slug = re.sub(r"[^a-z0-9_]+", "_", combined.lower())
    return slug.strip("_")


def test_derive_id_matches_the_documented_example() -> None:
    assert derive_id("src/web/views.py", "login_view") == "src_web_views_login_view"


def test_derive_id_drops_the_extension_from_the_last_segment_only() -> None:
    assert derive_id("src/v2.1/handler.py", "run") == "src_v2_1_handler_run"


def test_derive_id_keeps_a_dotless_filename_whole() -> None:
    assert derive_id("bin/entrypoint", "main") == "bin_entrypoint_main"


def test_sample_flow_node_ids_follow_the_rule(repo_root: Path) -> None:
    """The shipped example must obey the rule the templates state.

    `label` is the display form (`login_view()`); the function name is that with
    the trailing parens stripped.
    """
    flow = json.loads((repo_root / "examples" / "sample-flow.json").read_text(encoding="utf-8"))
    wrong = []
    for node in flow["nodes"]:
        name = node["label"].removesuffix("()")
        expected = derive_id(node["file"], name)
        if node["id"] != expected:
            wrong.append(f"{node['id']} should be {expected}")
    assert not wrong, "sample-flow.json node ids do not follow the derivation rule: " + "; ".join(wrong)


def test_sample_flow_edges_resolve_to_nodes(repo_root: Path) -> None:
    """Every edge endpoint must name a node that exists.

    The templates state this as a hard rule and the viewer enforces it at load
    time with an error card. Renaming node ids without renaming both endpoints
    of every edge is the exact way to break it.
    """
    flow = json.loads((repo_root / "examples" / "sample-flow.json").read_text(encoding="utf-8"))
    ids = {node["id"] for node in flow["nodes"]}
    dangling = [
        f"{edge['from']} -> {edge['to']}"
        for edge in flow["edges"]
        if edge["from"] not in ids or edge["to"] not in ids
    ]
    assert not dangling, "edges reference missing nodes: " + "; ".join(dangling)
