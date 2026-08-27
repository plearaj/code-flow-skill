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
RUST_TRACER = ("templates", "shared", "tracers", "trace_rust.py")
JAVA_TRACER = ("templates", "shared", "tracers", "trace_java.py")
C_TRACER = ("templates", "shared", "tracers", "trace_c_family.py")

# The keys every tracer must emit, whatever language it reads. A consumer that
# has to ask which tracer wrote a file before it can read it is not a contract.
ENVELOPE_KEYS = (
    "schema", "tracer", "language", "idRule", "root", "detail", "files", "skipped",
    "functions", "components", "routes", "entryPoints", "ambiguousCalls",
    "externalCalls", "stats", "limits",
)

# Every tracer, its fixture repository, and the fixture that runs it. The shared
# contracts below are parametrized over this, so a tracer added later is held to
# them by adding one line rather than by being trusted.
TRACERS = {
    "python": "py_trace",
    "typescript": "ts_trace",
    "rust": "rust_trace",
    "java": "java_trace",
    "c-family": "c_trace",
}
FIXTURE_DIRS = {
    "python": "py-app",
    "typescript": "ts-app",
    "rust": "rust-app",
    "java": "java-app",
    "c-family": "c-app",
}
ALL_TRACERS = sorted(TRACERS)

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


def _run_script(script, repo_root: Path, target: Path, detail: str = "standard") -> dict:
    out = subprocess.run(
        [sys.executable, str(repo_root.joinpath(*script)), "--root", str(target), "--detail", detail],
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


@pytest.fixture(scope="module")
def rust_trace() -> dict:
    return _run_script(RUST_TRACER, REPO_ROOT, REPO_ROOT / "tests" / "fixtures" / "rust-app")


@pytest.fixture(scope="module")
def java_trace() -> dict:
    return _run_script(JAVA_TRACER, REPO_ROOT, REPO_ROOT / "tests" / "fixtures" / "java-app")


@pytest.fixture(scope="module")
def c_trace() -> dict:
    return _run_script(C_TRACER, REPO_ROOT, REPO_ROOT / "tests" / "fixtures" / "c-app")


def _trace(request, which: str) -> dict:
    return request.getfixturevalue(TRACERS[which])


SCRIPTS = {"python": PY_TRACER, "rust": RUST_TRACER, "java": JAVA_TRACER, "c-family": C_TRACER}


def _rerun_in(repo_root: Path, which: str, target: Path, detail: str = "standard") -> dict:
    if which == "typescript":
        return _run_node_tracer(repo_root, target, detail)
    return _run_script(SCRIPTS[which], repo_root, target, detail)


def _rerun(repo_root: Path, which: str, detail: str = "standard") -> dict:
    return _rerun_in(repo_root, which, repo_root / "tests" / "fixtures" / FIXTURE_DIRS[which], detail)


def _by_id(trace: dict) -> dict[str, dict]:
    return {fn["id"]: fn for fn in trace["functions"]}


def _edges(trace: dict) -> set[tuple[str, str]]:
    return {(fn["id"], call["to"]) for fn in trace["functions"] for call in fn["calls"]}


# --- the shared envelope ---------------------------------------------------


@pytest.mark.parametrize("which", ALL_TRACERS)
def test_both_tracers_emit_the_same_envelope(request, which: str) -> None:
    """One shape, two languages. A consumer that had to branch on `tracer`
    before it could read `functions` would make every future tracer a change to
    every consumer."""
    trace = _trace(request, which)
    missing = [key for key in ENVELOPE_KEYS if key not in trace]
    assert not missing, f"{which} tracer omits envelope keys: {missing}"
    assert trace["schema"] == 1
    assert trace["idRule"] == "code-flow/v1"
    assert isinstance(trace["components"], list), (
        f"{which} tracer must emit `components` even when it finds none — an "
        f"absent key forces every consumer to branch on which tracer ran"
    )


@pytest.mark.parametrize("which", ALL_TRACERS)
def test_every_function_carries_the_inventory_fields(request, which: str) -> None:
    """These are the fields `/code-flow-map` copies straight into
    `inventory.json`. A tracer that omits one makes the map hand-fill it."""
    trace = _trace(request, which)
    assert trace["functions"], f"{which} tracer found no functions in its fixture"
    for fn in trace["functions"]:
        missing = [key for key in FUNCTION_KEYS if key not in fn]
        assert not missing, f"{which}: {fn.get('id')} is missing {missing}"


@pytest.mark.parametrize("which", ALL_TRACERS)
def test_every_call_target_resolves_to_a_catalogued_function(request, which: str) -> None:
    """The map turns `calls` straight into edges, and the viewer refuses to
    render a flow whose edge points at a missing node. A dangling `to` here is
    that error, one step earlier."""
    trace = _trace(request, which)
    known = set(_by_id(trace))
    dangling = [
        f"{fn['id']} -> {call['to']}"
        for fn in trace["functions"]
        for call in fn["calls"]
        if call["to"] not in known
    ]
    assert not dangling, f"{which}: calls point at unknown functions: {dangling}"


@pytest.mark.parametrize("which", ALL_TRACERS)
def test_every_call_declares_its_confidence(request, which: str) -> None:
    """`exact` and `heuristic` are the only two values, and both are meaningful.
    A tracer that emitted every edge as certain would be the confident-wrong
    output this whole design is arranged to avoid."""
    trace = _trace(request, which)
    for fn in trace["functions"]:
        for call in fn["calls"]:
            assert call["confidence"] in ("exact", "heuristic"), (
                f"{which}: {fn['id']} -> {call['to']} has confidence {call['confidence']!r}"
            )


@pytest.mark.parametrize("which", ALL_TRACERS)
def test_every_entry_point_names_a_catalogued_symbol(request, which: str) -> None:
    """An entry point is where pass 2 starts a flow. One that names nothing the
    inventory carries is a flow that cannot be traced."""
    trace = _trace(request, which)
    known = set(_by_id(trace)) | {c["id"] for c in trace["components"]}
    assert trace["entryPoints"], f"{which} tracer found no entry points in its fixture"
    for entry in trace["entryPoints"]:
        assert entry["id"] in known, f"{which}: entry point {entry['id']} is not catalogued"
        assert entry["kind"], f"{which}: entry point {entry['id']} has no kind"


@pytest.mark.parametrize("which", ALL_TRACERS)
def test_the_run_is_reproducible(request, repo_root: Path, which: str) -> None:
    """A map is built across sessions. A tracer whose output ordering depended on
    a dict's iteration order would make every re-run look like a change to every
    file it touched."""
    first = _trace(request, which)
    second = _rerun(repo_root, which)
    assert json.dumps(first, sort_keys=False) == json.dumps(second, sort_keys=False)


@pytest.mark.parametrize("which", ALL_TRACERS)
def test_ids_follow_the_documented_derivation(request, which: str) -> None:
    """The one property that makes a tracer usable at all: its ids are the map's
    ids. Checked against `tests/test_node_ids.py`'s implementation of the rule,
    not against a second copy of it written here."""
    trace = _trace(request, which)
    wrong = []
    for fn in trace["functions"]:
        base = derive_id(fn["file"], fn["name"])
        if fn["id"] not in (base, f"{base}_l{fn['line']}"):
            wrong.append(f"{fn['id']} should be {base} (or {base}_l{fn['line']})")
    assert not wrong, f"{which}: ids do not follow the rule: " + "; ".join(wrong)


@pytest.mark.parametrize("which", ALL_TRACERS)
def test_snippets_follow_the_detail_flag(request, repo_root: Path, which: str) -> None:
    """`--detail` means the same thing here as it does in the map, because the
    map hands its own flag straight through."""
    thin = _rerun(repo_root, which, "thin")
    verbose = _rerun(repo_root, which, "verbose")
    assert all("snippet" not in fn for fn in thin["functions"]), (
        f"{which}: --detail thin still emitted snippets"
    )
    assert any("snippet" in fn for fn in verbose["functions"]), (
        f"{which}: --detail verbose emitted no snippets"
    )
    long_bodies = [fn for fn in verbose["functions"] if fn["loc"] > 3]
    assert long_bodies, "the fixture has no function long enough to test snippets"


@pytest.mark.parametrize("which", ALL_TRACERS)
def test_the_census_carries_a_size_and_a_hash(request, which: str) -> None:
    """`index.json`'s census is copied from here, and a staleness check with no
    hash is a staleness check that cannot fire."""
    trace = _trace(request, which)
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


@pytest.mark.parametrize("which", ALL_TRACERS)
def test_limits_are_stated_rather_than_implied(request, which: str) -> None:
    """The output is read by a model that will otherwise present it as complete.
    `limits` is the sentence that stops "found" turning into "all"."""
    trace = _trace(request, which)
    assert trace["limits"], f"{which} tracer states no limits"
    assert any("static" in limit.lower() for limit in trace["limits"])


# --- owner and overrides ---------------------------------------------------
#
# `overrides` is the field the quality command's Liskov detector forms a family
# from, so what it must never do is name a relationship the source does not
# state. These assertions are written from that direction: one per tracer for
# the family it does find, and shared ones for everything it must not invent.

# The override family each fixture is built around: the declaration, and the two
# members that name it. One per tracer, so a tracer that stops reading its
# language's inheritance is caught by the tracer's own case rather than by a
# shared assertion that could pass on somebody else's evidence.
OVERRIDE_FAMILIES = {
    "python": ("UserStore.get", {"app_store_get_l22", "app_service_get"}),
    "typescript": ("UserService.load", {"src_services_cachinguserservice_load"}),
    "rust": ("Describe::describe", {"src_store_describe_l62", "src_store_describe_l68"}),
    "java": (
        "Describable.describe",
        {"src_main_java_com_demo_userservice_describe",
         "src_main_java_com_demo_userstore_describe"},
    ),
    "c-family": ("Describable::describe", {"src_service_describe"}),
}


@pytest.mark.parametrize("which", ALL_TRACERS)
def test_overrides_names_the_declaration_the_source_states(request, which: str) -> None:
    """Each tracer finds its language's inheritance, spelled its language's way.

    Five languages state the relationship five ways -- `impl Trait for Type`,
    `implements`, `extends`, a base-class list, a `: public Base` -- and this is
    the assertion that each tracer reads its own rather than a paraphrase of
    Java's.
    """
    trace = _trace(request, which)
    declaration, members = OVERRIDE_FAMILIES[which]
    found = {
        fn["id"] for fn in trace["functions"] if declaration in fn.get("overrides", [])
    }
    assert found == members, (
        f"{which}: {declaration} should be named by {sorted(members)}, "
        f"got {sorted(found)}"
    )


@pytest.mark.parametrize("which", ALL_TRACERS)
def test_every_override_is_well_formed(request, which: str) -> None:
    """`Supertype.member`, where `member` is this function's own name and
    `Supertype` is not the type it already belongs to.

    A consumer forms a family by grouping on this string, so a malformed one is
    not a cosmetic problem: it either splits a real family or joins two.
    """
    trace = _trace(request, which)
    wrong = []
    for fn in trace["functions"]:
        for declaration in fn.get("overrides", []):
            separator = "::" if "::" in declaration else "."
            supertype, _, member = declaration.rpartition(separator)
            if member != fn["name"] or not supertype:
                wrong.append(f"{fn['id']} names {declaration!r}")
            elif supertype == fn.get("owner"):
                wrong.append(f"{fn['id']} claims to override its own type")
    assert not wrong, f"{which}: " + "; ".join(wrong)


# One method per fixture that its type inherits nothing for: the class extends
# or implements something, and this particular member is its own. Naming an
# override here would be the field's characteristic failure -- reading the
# heritage clause and stopping there, without checking that the supertype
# really declares the member.
INHERITS_NOTHING = {
    "python": "app_store_warm",
    "typescript": "src_services_cachinguserservice_prime",
    "rust": "src_store_get_l38",
    "java": "src_main_java_com_demo_adminuserstore_findadmin",
    "c-family": "src_service_authenticate",
}


@pytest.mark.parametrize("which", ALL_TRACERS)
def test_extending_something_does_not_make_every_method_an_override(
    request, which: str
) -> None:
    """A subclass of a class is not an override of all of it."""
    trace = _trace(request, which)
    target = INHERITS_NOTHING[which]
    functions = _by_id(trace)
    assert target in functions, f"{which} fixture no longer defines {target}"
    assert functions[target].get("overrides") is None, (
        f"{which}: {target} was reported as overriding "
        f"{functions[target].get('overrides')}, which its type never declares"
    )


# Java is absent by construction: every method belongs to a type, so there is no
# free function for this to be true of. Listing it here rather than skipping it
# inside the test keeps that a stated fact about the language instead of a
# fixture that happens to have none.
HAS_FREE_FUNCTIONS = ("c-family", "python", "rust", "typescript")


@pytest.mark.parametrize("which", HAS_FREE_FUNCTIONS)
def test_a_free_function_carries_no_owner_and_no_overrides(request, which: str) -> None:
    """`owner` is how a consumer tells a method from a function without parsing
    `qualname`, which only works if a free function really does omit it."""
    trace = _trace(request, which)
    free = [fn for fn in trace["functions"] if "owner" not in fn]
    assert free, f"{which} fixture has no free function to check"
    assert all("overrides" not in fn for fn in free), (
        f"{which}: a function belonging to no type was given an override"
    )


def test_python_tracer_resolves_a_base_class_through_an_import(py_trace: dict) -> None:
    """The half of Python inheritance a same-file walk cannot see.

    `AuditedUserStore` lives in `app/service.py` and extends a class imported
    from `app/store.py`, so naming its override means resolving the import the
    way a call through one is resolved. `CachingUserStore` in the same fixture
    covers the same-file half.
    """
    functions = _by_id(py_trace)
    assert functions["app_service_get"]["overrides"] == ["UserStore.get"], (
        "a base class reached through `from app.store import UserStore` was not resolved"
    )
    assert functions["app_store_get_l22"]["overrides"] == ["UserStore.get"]
    assert functions["app_store_get_l10"].get("overrides") is None, (
        "the base class's own method was given an override of itself"
    )


def test_rust_tracer_reads_an_override_off_the_impl_header(rust_trace: dict) -> None:
    """Rust's required trait methods have no body and so are never catalogued.
    The relationship is still stated -- by `impl Describe for UserStore` -- and
    reading it off the header rather than by finding a declaration is what lets
    this tracer name the family that a body-driven lookup would miss."""
    functions = _by_id(rust_trace)
    assert functions["src_store_describe_l62"]["overrides"] == ["Describe::describe"], (
        "the trait `Describe` declares `describe` without a body, so a tracer that "
        "looked for a declaration to point at would have found nothing"
    )


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


# --- the Rust tracer -------------------------------------------------------


def test_rust_tracer_resolves_a_use_import_and_a_same_file_call(rust_trace: dict) -> None:
    """The two resolutions that carry a Rust call graph: a call to a name a `use`
    brought into scope, and a call to a free function beside it."""
    edges = _edges(rust_trace)
    assert ("src_main_main", "src_service_authenticate") in edges, (
        "a call through `use crate::service::authenticate` was not resolved"
    )
    assert ("src_service_authenticate", "src_service_verify") in edges, (
        "a call to a free function in the same module was not resolved"
    )


def test_rust_tracer_resolves_a_constructor_bound_receiver(rust_trace: dict) -> None:
    """`let store = UserStore::new(..)` then `store.get(..)`. Without this the
    service layer of a typical Rust application resolves to nothing."""
    calls = {c["to"]: c for c in _by_id(rust_trace)["src_service_authenticate"]["calls"]}
    assert "src_store_get_l38" in calls, "a call through a constructor-bound name was lost"
    assert calls["src_store_get_l38"]["confidence"] == "exact", (
        "`UserStore::new` names the type outright, so the method it reaches is resolved "
        "rather than guessed"
    )


def test_rust_tracer_resolves_a_struct_field_receiver(rust_trace: dict) -> None:
    """`self.cache.get(..)` inside `UserStore` reaches `Cache::get`, not the
    `get` in the same impl block that is one character closer."""
    assert ("src_store_get_l38", "src_store_get_l23") in _edges(rust_trace)


def test_rust_tracer_never_invents_a_container_method_edge(rust_trace: dict) -> None:
    """`raw.get(user_id)` is a HashMap lookup. The repository defines two methods
    called `get`, and a unique-name fallback would connect it to one of them."""
    read_calls = _by_id(rust_trace)["src_store_read"]["calls"]
    assert read_calls == [], f"`read` should reach nothing, it reaches {read_calls}"
    for source, target in _edges(rust_trace):
        assert not (source == "src_store_read"), "a HashMap `.get()` became an edge"


def test_rust_tracer_leaves_dyn_dispatch_ambiguous(rust_trace: dict) -> None:
    """`item.describe()` on a `&dyn Describe` reaches whichever impl was passed,
    which is not a fact about the text. Two impls, so two candidates and no edge —
    the case the tracer exists to *not* get confidently wrong."""
    ambiguous = {a["from"]: a for a in rust_trace["ambiguousCalls"]}
    assert "src_service_describe_any" in ambiguous, (
        "a call through `&dyn Trait` with two impls was resolved to one of them"
    )
    assert len(ambiguous["src_service_describe_any"]["candidates"]) == 2
    assert _by_id(rust_trace)["src_service_describe_any"]["calls"] == []


def test_rust_tracer_resolves_a_trait_impl_on_a_named_type(rust_trace: dict) -> None:
    """The other half of the same story: `store.describe()` on a `&UserStore` has
    exactly one answer, so it gets an edge."""
    assert ("src_service_describe_store", "src_store_describe_l62") in _edges(rust_trace)


def test_rust_tracer_finds_attribute_and_binary_entry_points(rust_trace: dict) -> None:
    kinds = {entry["id"]: entry for entry in rust_trace["entryPoints"]}
    assert kinds["src_web_show_user"]["kind"] == "http-route"
    assert kinds["src_web_show_user"]["detail"] == "GET /users/{id}", (
        "the route's verb and path come from the attribute, and are what make the "
        "entry point worth listing"
    )
    assert kinds["src_main_main"]["kind"] == "cli-command"


def test_rust_tracer_marks_a_cfg_test_module_as_tests(rust_trace: dict) -> None:
    """A `#[cfg(test)] mod tests` is test code even though its file is not."""
    assert _by_id(rust_trace)["src_service_verifies_a_matching_password"]["role"] == "test"
    assert _by_id(rust_trace)["src_service_authenticate"]["role"] == "source"


def test_rust_tracer_reads_past_a_nested_comment_and_a_lifetime(rust_trace: dict) -> None:
    """Two things that swallow the rest of a file when read naively: a nested
    block comment, and a `'a` lifetime read as an unterminated character literal.
    Both sit above `read`, so `read` being catalogued is the assertion."""
    catalogued = set(_by_id(rust_trace))
    assert "src_store_shorter" in catalogued, "a lifetime was read as a character literal"
    assert "src_store_read" in catalogued, "a nested block comment swallowed the rest of the file"


# --- the Java tracer -------------------------------------------------------


def test_java_tracer_resolves_a_field_typed_receiver(java_trace: dict) -> None:
    """`private final UserStore store;` then `store.find(..)`. Fields are where a
    Java service keeps its collaborators, so this is most of the call graph."""
    edges = _edges(java_trace)
    assert (
        "src_main_java_com_demo_userservice_authenticate",
        "src_main_java_com_demo_userstore_find",
    ) in edges


def test_java_tracer_follows_an_extends_chain(java_trace: dict) -> None:
    """`AdminUserStore extends UserStore` and calls `find` unqualified."""
    assert (
        "src_main_java_com_demo_adminuserstore_findadmin",
        "src_main_java_com_demo_userstore_find",
    ) in _edges(java_trace)


def test_java_tracer_resolves_an_interface_call_to_the_interface(java_trace: dict) -> None:
    """`Describable item` calling `describe()` reaches the declaration it is
    written against. Which implementation runs is the container's decision, and
    guessing at one of the two would be a call the reader cannot find."""
    edges = _edges(java_trace)
    assert (
        "src_main_java_com_demo_report_describeall",
        "src_main_java_com_demo_describable_describe",
    ) in edges
    assert not any(
        source == "src_main_java_com_demo_report_describeall" and target.endswith("_describe")
        and "describable" not in target
        for source, target in edges
    ), "a call through an interface was resolved to an implementation"


def test_java_tracer_leaves_an_overloaded_call_ambiguous(java_trace: dict) -> None:
    """Two `verify` methods differing only in arity. Overloads are distinguished
    by line, not by parameter types, so the honest answer is both candidates."""
    ambiguous = [a for a in java_trace["ambiguousCalls"] if a["name"] == "verify"]
    assert ambiguous, "a call to an overloaded method was resolved to one overload"
    assert len(ambiguous[0]["candidates"]) == 2
    suffixed = sorted(i for i in _by_id(java_trace) if "_verify_l" in i)
    assert len(suffixed) == 2, f"expected two suffixed `verify` ids, got {suffixed}"


def test_java_tracer_resolves_a_constructor(java_trace: dict) -> None:
    assert (
        "src_main_java_com_demo_app_main",
        "src_main_java_com_demo_userservice_userservice",
    ) in _edges(java_trace)


def test_java_tracer_never_invents_a_map_get_edge(java_trace: dict) -> None:
    """`records.get(userId)` is a Map lookup, on a receiver whose type is a JDK
    class. Nothing in the repository may be joined to it."""
    assert _by_id(java_trace)["src_main_java_com_demo_userstore_find"]["calls"] == []


def test_java_tracer_finds_annotation_and_main_entry_points(java_trace: dict) -> None:
    entries = {entry["id"]: entry for entry in java_trace["entryPoints"]}
    controller = "src_main_java_com_demo_usercontroller_show"
    assert entries[controller]["kind"] == "http-route"
    assert entries[controller]["detail"] == "GET /users/{id}"
    assert entries["src_main_java_com_demo_app_main"]["kind"] == "cli-command"


def test_java_tracer_reads_past_a_brace_inside_a_string(java_trace: dict) -> None:
    """`UserStore` opens with a field holding `"{ \"id\": \"%s\" }"`. Read as
    code, that brace closes the class and everything below it disappears."""
    catalogued = set(_by_id(java_trace))
    assert "src_main_java_com_demo_userstore_find" in catalogued
    assert "src_main_java_com_demo_userstore_describe" in catalogued


def test_java_tracer_marks_test_classes(java_trace: dict) -> None:
    tests = [fn for fn in java_trace["functions"] if fn["role"] == "test"]
    assert [fn["name"] for fn in tests] == ["authenticatesAMatchingPassword"]


# --- the C-family tracer ---------------------------------------------------


def test_c_tracer_reads_all_four_dialects(c_trace: dict) -> None:
    """One tracer, four languages, one catalog — a repository that mixes C and
    Objective-C, or C# and generated C, is read once rather than partly."""
    assert c_trace["dialects"] == ["c", "cpp", "csharp", "objc"]


def test_c_tracer_resolves_a_call_through_an_included_header(c_trace: dict) -> None:
    """The resolution that makes a C call graph possible at all. `main.c` calls
    `store_find`, declared in `store.h`, defined in `store.c` — three files, and
    the `#include` is the evidence joining them."""
    calls = {c["to"]: c for c in _by_id(c_trace)["src_main_main"]["calls"]}
    assert "src_store_store_find" in calls
    assert calls["src_store_store_find"]["confidence"] == "exact", (
        "a header declaration is evidence, not a guess"
    )
    assert "src_store_store_init" in calls


def test_c_tracer_resolves_a_same_file_static_helper(c_trace: dict) -> None:
    """And marks it unexported: file-scope `static` is the one negative signal C
    gives that really does mean "not visible outside this file"."""
    assert ("src_store_store_find", "src_store_read_record") in _edges(c_trace)
    assert _by_id(c_trace)["src_store_read_record"]["exported"] is False
    assert _by_id(c_trace)["src_store_store_find"]["exported"] is True


def test_c_tracer_catalogues_a_cpp_constructor_and_an_out_of_class_method(c_trace: dict) -> None:
    """A constructor has no return type, so nothing precedes its name to
    recognize it by; its member initializer list then puts two more braces in
    front of its body. Both are why it is the declaration most often missed."""
    functions = _by_id(c_trace)
    assert "src_service_userservice" in functions, "a C++ constructor was not catalogued"
    assert functions["src_service_authenticate"]["qualname"] == "UserService::authenticate"
    assert ("src_service_authenticate", "src_service_describe") in _edges(c_trace)


def test_c_tracer_reads_a_cpp_call_into_c(c_trace: dict) -> None:
    """C++ calling a C function through the same header the C file uses."""
    assert ("src_service_authenticate", "src_store_store_find") in _edges(c_trace)


def test_c_tracer_resolves_a_csharp_field_and_an_expression_body(c_trace: dict) -> None:
    edges = _edges(c_trace)
    assert ("src_report_list", "src_report_all") in edges
    assert ("src_report_total", "src_report_all") in edges, (
        "an expression-bodied member (`=> store.All().Count`) has a body too"
    )


def test_c_tracer_names_objc_methods_by_selector(c_trace: dict) -> None:
    """A message send names a whole selector and nothing less, so a method's name
    has to be the whole selector for the two to match."""
    functions = _by_id(c_trace)
    assert functions["src_userbox_recordforuser"]["qualname"] == "UserBox::recordForUser:"
    assert ("src_userbox_recordforuser", "src_userbox_normalize") in _edges(c_trace), (
        "`[self normalize:userId]` was not resolved"
    )


def test_c_tracer_takes_objc_visibility_from_the_interface(c_trace: dict) -> None:
    """`@interface` is in the header and `@implementation` in the source, so
    deciding this per file marks every public method private."""
    functions = _by_id(c_trace)
    assert functions["src_userbox_recordforuser"]["exported"] is True
    assert functions["src_userbox_normalize"]["exported"] is False


def test_c_tracer_takes_a_purpose_from_the_declaration(c_trace: dict) -> None:
    """In C, C++ and Objective-C the prose lives on the declaration in the header
    and the definition carries none. Reading only definitions would report every
    function in the repository as undocumented."""
    functions = _by_id(c_trace)
    assert functions["src_store_store_find"]["purpose"].startswith("Looks a user record up")
    assert functions["src_service_authenticate"]["purpose"].startswith("Authenticates a user")
    assert functions["src_userbox_recordforuser"]["purpose"].startswith("Returns the record")


def test_c_tracer_finds_a_csharp_route_and_a_c_main(c_trace: dict) -> None:
    entries = {entry["id"]: entry for entry in c_trace["entryPoints"]}
    assert entries["src_report_list"]["kind"] == "http-route"
    assert entries["src_report_list"]["detail"] == "GET /reports"
    assert entries["src_main_main"]["kind"] == "cli-command"


def test_c_tracer_declines_a_dot_m_file_that_is_not_objective_c(
    repo_root: Path, tmp_path: Path
) -> None:
    """`.m` is Objective-C here and MATLAB elsewhere. Reading a MATLAB script with
    a C parser produces confident nonsense, so the file is reported as unread —
    which is a thing the report can say, unlike a wrong answer."""
    _write(tmp_path, "analysis.m", "function y = analysis(x)\n  y = x .^ 2;\nend\n")
    _write(tmp_path, "Box.m", "#import \"Box.h\"\n@implementation Box\n- (int)value { return 1; }\n@end\n")
    trace = _run_script(C_TRACER, repo_root, tmp_path, "thin")

    assert {r["path"] for r in trace["files"]} == {"Box.m"}
    assert {r["path"]: r["reason"] for r in trace["skipped"]} == {"analysis.m": "unparsed"}


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
        (
            "rust",
            ("distutils/core.rs", "src/builder.rs", "src/targets.rs"),
            ("vendor/pkg/lib.rs", "target/debug/out.rs", ".venv/thing.rs"),
            "src/schema.generated.rs",
        ),
        (
            "java",
            ("distutils/Core.java", "src/Builder.java", "src/Targets.java"),
            ("build/gen/Out.java", "node_modules/pkg/A.java", "vendor/lib/B.java"),
            "src/Schema.g.java",
        ),
        (
            "c-family",
            ("distutils/core.c", "src/builder.cpp", "src/targets.cs"),
            ("vendor/pkg/a.c", "build/out.c", "third_party/lib.cpp"),
            "src/schema.pb.c",
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
    bodies = {
        "python": "def f():\n    return 1\n",
        "typescript": "export function f() { return 1; }\n",
        "rust": "pub fn f() -> i32 {\n    1\n}\n",
        "java": "public class Sample {\n    public int f() {\n        return 1;\n    }\n}\n",
        "c-family": "int f(void) {\n    return 1;\n}\n",
    }
    for rel in kept + ignored + (marked,):
        _write(tmp_path, rel, bodies[which])
    trace = _rerun_in(repo_root, which, tmp_path, "thin")

    scanned = {record["path"] for record in trace["files"]}
    for rel in kept:
        assert rel in scanned, f"{which}: {rel} was left out, but nothing about it is generated"
    for rel in ignored:
        assert rel not in scanned, f"{which}: {rel} was catalogued from a vendored or build directory"
    assert marked not in scanned, f"{which}: {marked} was catalogued despite its generated marker"
    assert {record["path"]: record["reason"] for record in trace["skipped"]}.get(marked) == "generated", (
        f"{which}: {marked} was left out without being reported as generated"
    )
