"""Contracts for the two shipped tracers.

The tracers are the first executable code this project ships into a user's
repository. Everything else under `templates/` is prose a host reads; these two
files run, and what they emit becomes the map. So they get the coverage prose
cannot have.

Three properties matter more than any individual heuristic, and they are what
this module is organized around:

**The ids must join.** A tracer's `id` for a function and a flow node's `id` for
the same function have to be the same string, or `/code-flow-quality`'s
subtraction — every catalogued id minus every reached id — silently reports the
whole repository as unreachable. `tests/test_node_ids.py` already implements the
rule once; this module asserts the tracers obey that implementation rather than
a paraphrase of it.

**Nothing may be invented.** A false edge is worse than a missing one: it puts a
call in a diagram that a reader will go looking for. Both tracers are therefore
asserted to *not* resolve the cases where they cannot know the answer —
`dict.get()`, `array.map()` — rather than only asserted to resolve the ones they
can.

**Two runs agree.** The map is built up across sessions, so a tracer that orders
its output by anything unstable would make every re-run look like a change.

The Node tracer is exercised from Python as well as from `test/tracer-typescript.test.js`,
because the envelope both tracers share is a cross-language contract and neither
language's suite can see both halves of it.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from .conftest import REPO_ROOT
from .test_node_ids import derive_id

PY_TRACER = ("templates", "shared", "tracers", "trace_python.py")
TS_TRACER = ("templates", "shared", "tracers", "trace_typescript.mjs")

# The keys both tracers must emit, whatever language they read. A consumer that
# has to ask which tracer wrote a file before it can read it is not a contract.
ENVELOPE_KEYS = (
    "schema", "tracer", "language", "idRule", "root", "detail", "files", "skipped",
    "functions", "components", "entryPoints", "ambiguousCalls", "externalCalls",
    "stats", "limits",
)

FUNCTION_KEYS = (
    "id", "name", "file", "line", "loc", "signature", "purpose", "role",
    "exported", "io", "calls",
)


def _run_python_tracer(repo_root: Path, target: Path, detail: str = "standard") -> dict:
    out = subprocess.run(
        [sys.executable, str(repo_root.joinpath(*PY_TRACER)), "--root", str(target), "--detail", detail],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(out.stdout)


def _run_node_tracer(repo_root: Path, target: Path, detail: str = "standard") -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    out = subprocess.run(
        [node, str(repo_root.joinpath(*TS_TRACER)), "--root", str(target), "--detail", detail],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(out.stdout)


# Module-scoped, and reading `REPO_ROOT` rather than the `repo_root` fixture:
# both tracers shell out, and re-running them once per test would pay that cost
# thirty times over for output that cannot differ between tests.
@pytest.fixture(scope="module")
def py_trace() -> dict:
    return _run_python_tracer(REPO_ROOT, REPO_ROOT / "tests" / "fixtures" / "py-app")


@pytest.fixture(scope="module")
def ts_trace() -> dict:
    return _run_node_tracer(REPO_ROOT, REPO_ROOT / "tests" / "fixtures" / "ts-app")


def _by_id(trace: dict) -> dict[str, dict]:
    return {fn["id"]: fn for fn in trace["functions"]}


def _edges(trace: dict) -> set[tuple[str, str]]:
    return {(fn["id"], call["to"]) for fn in trace["functions"] for call in fn["calls"]}


# --- the shared envelope ---------------------------------------------------


@pytest.mark.parametrize("which", ["python", "typescript"])
def test_both_tracers_emit_the_same_envelope(request, which: str) -> None:
    """One shape, two languages. A consumer that had to branch on `tracer`
    before it could read `functions` would make every future tracer a change to
    every consumer."""
    trace = request.getfixturevalue("py_trace" if which == "python" else "ts_trace")
    missing = [key for key in ENVELOPE_KEYS if key not in trace]
    assert not missing, f"{which} tracer omits envelope keys: {missing}"
    assert trace["schema"] == 1
    assert trace["idRule"] == "code-flow/v1"
    assert isinstance(trace["components"], list), (
        f"{which} tracer must emit `components` even when it finds none — an "
        f"absent key forces every consumer to branch on which tracer ran"
    )


@pytest.mark.parametrize("which", ["python", "typescript"])
def test_every_function_carries_the_inventory_fields(request, which: str) -> None:
    """These are the fields `/code-flow-map` copies straight into
    `inventory.json`. A tracer that omits one makes the map hand-fill it."""
    trace = request.getfixturevalue("py_trace" if which == "python" else "ts_trace")
    assert trace["functions"], f"{which} tracer found no functions in its fixture"
    for fn in trace["functions"]:
        missing = [key for key in FUNCTION_KEYS if key not in fn]
        assert not missing, f"{which}: {fn.get('id')} is missing {missing}"


@pytest.mark.parametrize("which", ["python", "typescript"])
def test_every_call_target_resolves_to_a_catalogued_function(request, which: str) -> None:
    """The map turns `calls` straight into edges, and the viewer refuses to
    render a flow whose edge points at a missing node. A dangling `to` here is
    that error, one step earlier."""
    trace = request.getfixturevalue("py_trace" if which == "python" else "ts_trace")
    known = set(_by_id(trace))
    dangling = [
        f"{fn['id']} -> {call['to']}"
        for fn in trace["functions"]
        for call in fn["calls"]
        if call["to"] not in known
    ]
    assert not dangling, f"{which}: calls point at unknown functions: {dangling}"


@pytest.mark.parametrize("which", ["python", "typescript"])
def test_every_call_declares_its_confidence(request, which: str) -> None:
    """`exact` and `heuristic` are the only two values, and both are meaningful.
    A tracer that emitted every edge as certain would be the confident-wrong
    output this whole design is arranged to avoid."""
    trace = request.getfixturevalue("py_trace" if which == "python" else "ts_trace")
    for fn in trace["functions"]:
        for call in fn["calls"]:
            assert call["confidence"] in ("exact", "heuristic"), (
                f"{which}: {fn['id']} -> {call['to']} has confidence {call['confidence']!r}"
            )


@pytest.mark.parametrize("which", ["python", "typescript"])
def test_every_entry_point_names_a_catalogued_symbol(request, which: str) -> None:
    """An entry point is where pass 2 starts a flow. One that names nothing the
    inventory carries is a flow that cannot be traced."""
    trace = request.getfixturevalue("py_trace" if which == "python" else "ts_trace")
    known = set(_by_id(trace)) | {c["id"] for c in trace["components"]}
    assert trace["entryPoints"], f"{which} tracer found no entry points in its fixture"
    for entry in trace["entryPoints"]:
        assert entry["id"] in known, f"{which}: entry point {entry['id']} is not catalogued"
        assert entry["kind"], f"{which}: entry point {entry['id']} has no kind"


@pytest.mark.parametrize("which", ["python", "typescript"])
def test_the_run_is_reproducible(request, repo_root: Path, which: str) -> None:
    """A map is built across sessions. A tracer whose output ordering depended on
    a dict's iteration order would make every re-run look like a change to every
    file it touched."""
    fixture = repo_root / "tests" / "fixtures" / ("py-app" if which == "python" else "ts-app")
    first = request.getfixturevalue("py_trace" if which == "python" else "ts_trace")
    second = (_run_python_tracer if which == "python" else _run_node_tracer)(repo_root, fixture)
    assert json.dumps(first, sort_keys=False) == json.dumps(second, sort_keys=False)


@pytest.mark.parametrize("which", ["python", "typescript"])
def test_ids_follow_the_documented_derivation(request, which: str) -> None:
    """The one property that makes a tracer usable at all: its ids are the map's
    ids. Checked against `tests/test_node_ids.py`'s implementation of the rule,
    not against a second copy of it written here."""
    trace = request.getfixturevalue("py_trace" if which == "python" else "ts_trace")
    wrong = []
    for fn in trace["functions"]:
        base = derive_id(fn["file"], fn["name"])
        if fn["id"] not in (base, f"{base}_l{fn['line']}"):
            wrong.append(f"{fn['id']} should be {base} (or {base}_l{fn['line']})")
    assert not wrong, f"{which}: ids do not follow the rule: " + "; ".join(wrong)


@pytest.mark.parametrize("which", ["python", "typescript"])
def test_snippets_follow_the_detail_flag(request, repo_root: Path, which: str) -> None:
    """`--detail` means the same thing here as it does in the map, because the
    map hands its own flag straight through."""
    fixture = repo_root / "tests" / "fixtures" / ("py-app" if which == "python" else "ts-app")
    runner = _run_python_tracer if which == "python" else _run_node_tracer
    thin = runner(repo_root, fixture, "thin")
    verbose = runner(repo_root, fixture, "verbose")
    assert all("snippet" not in fn for fn in thin["functions"]), (
        f"{which}: --detail thin still emitted snippets"
    )
    assert any("snippet" in fn for fn in verbose["functions"]), (
        f"{which}: --detail verbose emitted no snippets"
    )
    long_bodies = [fn for fn in verbose["functions"] if fn["loc"] > 3]
    assert long_bodies, "the fixture has no function long enough to test snippets"


@pytest.mark.parametrize("which", ["python", "typescript"])
def test_the_census_carries_a_size_and_a_hash(request, which: str) -> None:
    """`index.json`'s census is copied from here, and a staleness check with no
    hash is a staleness check that cannot fire."""
    trace = request.getfixturevalue("py_trace" if which == "python" else "ts_trace")
    assert trace["files"], f"{which} tracer recorded no files"
    for record in trace["files"]:
        # `size` is asserted non-negative rather than positive: an empty
        # `__init__.py` is a real, legitimately zero-byte source file, and
        # requiring a positive size here would make the fixture lie about what
        # a Python package looks like.
        assert isinstance(record["size"], int) and record["size"] >= 0
        assert record["hash"] and record["hash"].startswith("sha256:"), (
            f"{which}: {record['path']} has no usable hash"
        )
    assert any(record["size"] > 0 for record in trace["files"])


@pytest.mark.parametrize("which", ["python", "typescript"])
def test_limits_are_stated_rather_than_implied(request, which: str) -> None:
    """The output is read by a model that will otherwise present it as complete.
    `limits` is the sentence that stops "found" turning into "all"."""
    trace = request.getfixturevalue("py_trace" if which == "python" else "ts_trace")
    assert trace["limits"], f"{which} tracer states no limits"
    assert any("static" in limit.lower() for limit in trace["limits"])


# --- the Python tracer -----------------------------------------------------


def test_python_tracer_resolves_imports_and_self_calls(py_trace: dict) -> None:
    """The two resolutions that carry a Python call graph: a `from x import y`
    call, and a method reached through `self`."""
    edges = _edges(py_trace)
    assert ("app_web_login_view", "app_service_authenticate") in edges, (
        "a call through `from app.service import authenticate` was not resolved"
    )
    assert ("app_service_authenticate", "app_service_verify") in edges, (
        "a call to a module-level function in the same file was not resolved"
    )
    assert ("app_store_get_l10", "app_store_read") in edges, (
        "a `self._read()` call was not resolved"
    )


def test_python_tracer_resolves_a_constructor_bound_receiver(py_trace: dict) -> None:
    """`store = UserStore(...)` then `store.get(...)`. Without this the whole
    service layer of a typical Python application resolves to nothing."""
    calls = {c["to"]: c for c in _by_id(py_trace)["app_service_authenticate"]["calls"]}
    assert "app_store_get_l10" in calls, "a call through a constructor-bound name was lost"
    assert calls["app_store_get_l10"]["confidence"] == "exact", (
        "a constructor call names the class outright, so the method it reaches is "
        "resolved rather than guessed"
    )


def test_python_tracer_suffixes_same_named_methods_in_one_file(py_trace: dict) -> None:
    """Two classes in one file, both with a `get`. The suffix is what keeps
    their ids distinct — and it must come from the definition line, so the two
    do not swap identities when one of them moves."""
    ids = set(_by_id(py_trace))
    suffixed = sorted(i for i in ids if i.startswith("app_store_get_l"))
    assert len(suffixed) == 2, f"expected two suffixed `get` ids, got {suffixed}"
    for identifier in suffixed:
        assert _by_id(py_trace)[identifier]["line"] == int(identifier.rsplit("_l", 1)[1])


def test_python_tracer_never_invents_a_container_method_edge(py_trace: dict) -> None:
    """`self._read().get(user_id)` is a dict lookup. The repository also defines
    a method called `get`, and a unique-name fallback would happily connect the
    two — putting a call in the diagram that does not exist."""
    for source, target in _edges(py_trace):
        assert not (source.startswith("app_store_get") and target.startswith("app_store_get")), (
            f"{source} -> {target}: a dict `.get()` was resolved as a call to the "
            f"repository's own `get` method"
        )


def test_python_tracer_finds_both_kinds_of_entry_point(py_trace: dict) -> None:
    """A decorated route and a console script. Between them they cover how most
    Python repositories are entered."""
    kinds = {entry["id"]: entry["kind"] for entry in py_trace["entryPoints"]}
    assert kinds.get("app_web_login_view") == "http-route"
    assert kinds.get("app_web_main") == "cli-command"


def test_python_tracer_catalogues_tests_and_marks_them(py_trace: dict) -> None:
    """Catalogued, never skipped: excluding tests would make every helper only
    tests use look unreachable. Marked, so the quality command can tell
    "dead" from "kept alive by its own tests"."""
    roles = {fn["id"]: fn["role"] for fn in py_trace["functions"]}
    assert roles.get("tests_test_service_test_verify_rejects_empty") == "test"
    assert roles.get("app_service_verify") == "source"


def test_python_tracer_flags_io(py_trace: dict) -> None:
    """`io` is what the map turns into a node of kind `io`, and a flow diagram
    that never marks its side effects is a diagram of the wrong thing."""
    assert _by_id(py_trace)["app_store_read"]["io"] is True


def test_python_tracer_leaves_a_dead_candidate_unreached(py_trace: dict) -> None:
    """The YAGNI detector subtracts reached ids from catalogued ones. That only
    finds anything if an unreached function survives the trace as a node."""
    reached = {target for _, target in _edges(py_trace)}
    assert "app_store_unused_helper" in _by_id(py_trace)
    assert "app_store_unused_helper" not in reached


# --- the TypeScript tracer -------------------------------------------------


def _components(trace: dict) -> dict[str, dict]:
    return {component["id"]: component for component in trace["components"]}


def test_typescript_tracer_names_the_frameworks_it_found(ts_trace: dict) -> None:
    """One repository can be several front ends. The framework is decided per
    file, so a monorepo does not have to pick one."""
    assert set(ts_trace["frameworks"]["frontend"]) >= {"react", "vue", "angular"}
    assert "express" in ts_trace["frameworks"]["backend"]


def test_typescript_tracer_maps_the_angular_component_tree(ts_trace: dict) -> None:
    """Angular's tree is in its templates, not its imports: the parent names the
    child by selector. A tracer that only followed imports would report every
    Angular component as a leaf."""
    dashboard = _components(ts_trace)["src_angular_dashboard_component_dashboardcomponent"]
    assert dashboard["framework"] == "angular"
    assert dashboard["selector"] == "app-dashboard"
    assert dashboard["inputs"] == ["title"]
    assert dashboard["hooks"] == ["ngOnInit"]
    assert "src_angular_summary_component_summarycomponent" in dashboard["children"]


def test_typescript_tracer_maps_the_react_component_tree(ts_trace: dict) -> None:
    """React's tree is in its JSX, resolved through the file's imports — and the
    import here goes through a tsconfig `paths` alias in the sibling service, so
    this also covers alias resolution."""
    page = _components(ts_trace)["src_pages_userlistpage_userlistpage"]
    assert page["framework"] == "react"
    assert "src_components_usercard_usercard" in page["children"]
    assert "useUsers" in page["hooks"]
    card = _components(ts_trace)["src_components_usercard_usercard"]
    assert card["inputs"] == ["user", "onSelect"]


def test_typescript_tracer_maps_the_vue_component_tree(ts_trace: dict) -> None:
    """A `.vue` file is one component, and its children are in the template
    block — which is not JavaScript and would not survive a scanner that only
    read the `<script>`."""
    orders = _components(ts_trace)["src_vue_orderlist_orderlist"]
    assert orders["framework"] == "vue"
    assert orders["inputs"] == ["customerId", "compact"]
    assert "src_vue_orderrow_orderrow" in orders["children"]


def test_typescript_tracer_separates_hooks_from_components(ts_trace: dict) -> None:
    """A custom hook is where a component's behavior lives. Filed as a component
    it would distort the tree; filed as a plain function it would disappear."""
    hook = _components(ts_trace)["src_hooks_useusers_useusers"]
    assert hook["kind"] == "hook"


def test_typescript_tracer_resolves_a_path_alias(ts_trace: dict) -> None:
    """`@app/*` is a tsconfig alias. An unresolved alias is not one missing
    edge — it is every edge into that subtree."""
    assert ("src_components_usercard_usercard", "src_services_userservice_formatname") in _edges(ts_trace)


def test_typescript_tracer_resolves_injected_and_constructed_receivers(ts_trace: dict) -> None:
    """Angular constructor injection and `new UserService()`. Between them they
    are how a TypeScript service layer is reached at all."""
    edges = _edges(ts_trace)
    assert ("src_angular_dashboard_component_ngoninit", "src_angular_report_service_total") in edges
    assert ("src_api_server_getuser", "src_services_userservice_load") in edges


def test_typescript_tracer_finds_route_and_http_entry_points(ts_trace: dict) -> None:
    kinds = {entry["id"]: entry["kind"] for entry in ts_trace["entryPoints"]}
    assert kinds.get("src_api_server_getuser") == "http-route"
    assert kinds.get("src_pages_userlistpage_userlistpage") == "route"


def test_typescript_tracer_records_routes_with_their_paths(ts_trace: dict) -> None:
    routes = {route["component"]: route for route in ts_trace["routes"]}
    assert "src_pages_userlistpage_userlistpage" in routes
    assert routes["src_pages_userlistpage_userlistpage"]["path"].startswith("/")


def test_typescript_tracer_never_invents_an_array_method_edge(ts_trace: dict) -> None:
    """`users.map(...)` is `Array.prototype.map`. A unique-name fallback would
    connect it to whatever the repository calls `map`."""
    for _, target in _edges(ts_trace):
        assert not target.endswith("_map"), f"an array `.map()` resolved to {target}"


# --- what counts as a file worth reading -----------------------------------


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.mark.parametrize(
    "which,kept,ignored,marked",
    (
        (
            "python",
            ("distutils/core.py", "src/xmlbuilder.py", "src/target_helpers.py"),
            ("node_modules/pkg/mod.py", "dist/out.py", ".venv/lib/thing.py"),
            "src/schema_pb2.py",
        ),
        (
            "typescript",
            ("distutils/core.ts", "src/builder.ts", "src/targets.ts"),
            ("node_modules/pkg/index.ts", "dist/app.ts", "coverage/report.ts"),
            "src/app.min.ts",
        ),
    ),
)
def test_a_skip_reason_matches_a_path_segment_not_a_substring(
    repo_root: Path,
    tmp_path: Path,
    which: str,
    kept: tuple[str, ...],
    ignored: tuple[str, ...],
    marked: str,
) -> None:
    """Found by running the Python tracer over the standard library: `distutils/`
    and `xml/dom/xmlbuilder.py` were both reported as `generated`, because "dist"
    and "build" are substrings of ordinary words. Fifty-one real modules were
    absent from the catalog, each with a reason that looked entirely plausible.

    A wrongly skipped file is worse than an unskipped one. An unskipped vendored
    file is noise a reader can see; a wrongly skipped source file is a hole in the
    map that the map itself explains away.

    Three cases, because the tracers reach the same answer three ways: a real
    source file whose *name* merely contains a marker word is read; a file under a
    vendored or generated *directory* never is; and a file whose own name carries
    a generated marker is skipped with a reason. Only the last lands in `skipped`
    — a pruned directory is never walked, so it is absent rather than counted,
    which is what `.code-flow/tracers/README.md` says it is.
    """
    body = "def f():\n    return 1\n" if which == "python" else "export function f() { return 1; }\n"
    for rel in kept + ignored + (marked,):
        _write(tmp_path, rel, body)
    runner = _run_python_tracer if which == "python" else _run_node_tracer
    trace = runner(repo_root, tmp_path, "thin")

    scanned = {record["path"] for record in trace["files"]}
    for rel in kept:
        assert rel in scanned, f"{which}: {rel} was left out, but nothing about it is generated"
    for rel in ignored:
        assert rel not in scanned, f"{which}: {rel} was catalogued from a vendored or build directory"
    assert marked not in scanned, f"{which}: {marked} was catalogued despite its generated marker"
    assert {record["path"]: record["reason"] for record in trace["skipped"]}.get(marked) == "generated", (
        f"{which}: {marked} was left out without being reported as generated"
    )
