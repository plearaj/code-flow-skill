"""Assertions about template content.

Templates are prompt text, not code, so these tests check that the
instructions a template gives still mention the artifacts it is required to
produce. They catch silent drift between the spec and the prompts.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

MAP_TEMPLATES = (
    ("claude", "code-flow.map.md"),
    ("gemini", "code-flow.map.toml"),
    ("copilot", "code-flow.map.prompt.md"),
)


@pytest.mark.parametrize("host,name", MAP_TEMPLATES)
def test_map_template_requires_json_sidecar(repo_root: Path, host: str, name: str) -> None:
    text = (repo_root / "templates" / host / name).read_text(encoding="utf-8")
    assert "<functionality_name>.json" in text


@pytest.mark.parametrize("host,name", MAP_TEMPLATES)
def test_map_template_requires_index(repo_root: Path, host: str, name: str) -> None:
    text = (repo_root / "templates" / host / name).read_text(encoding="utf-8")
    assert "index.json" in text


INDEX_FIELD_NAMES = (
    "slug",
    "title",
    "file",
    "entry",
    "nodes",
    "coverage",
    "flowsTraced",
    "schema",
    "mode",
)

# Marks the start of the Step 6 "write the machine-readable artifacts"
# instructions in every host (Claude/Gemini: "#### 6. Write the
# Machine-Readable Artifacts"; Copilot: "**Write the machine-readable
# artifacts.**"). Matched case-insensitively so it doesn't care which of
# those two casings a host uses.
_INDEX_SECTION_START = re.compile(r"machine-readable artifacts", re.IGNORECASE)

# Marks the start of the *next* section/item after Step 6, in every host
# (Claude/Gemini: "#### 7. Finalize"; Copilot: "7. **Report..."). Used as
# the end boundary so the scoped region can't run past Step 6 into
# unrelated text.
_INDEX_SECTION_END = re.compile(r"\n(?:#### 7\.|7\.\s*\*\*Report)")


def _field_reference(field: str) -> re.Pattern[str]:
    """Match a *reference to the field named ``field``*, not the bare word.

    A plain substring search is vacuous for several of these names, because
    the same letters occur in ordinary prose inside the same region: `file`
    appears in "written as a plain file", "These files are the contract" and
    "rewriting the file would silently discard...", and `entry` appears in
    "add or replace the entry for this flow". Deleting the bullet that
    actually derives `file` would leave those prose hits behind and the
    assertion would still pass.

    Every real reference in every host is delimited: the field is either
    JSON-quoted (`"file": "user_login.json"`), wrapped in a markdown code
    span (`` `file` ``), or dotted onto its parent (``coverage.flowsTraced``,
    ``meta.mode``). Requiring one of those three leading delimiters, plus a
    word boundary after the name, keeps the prose occurrences out.
    """
    return re.compile(r"[`\".]" + re.escape(field) + r"\b")


def _section_region(text: str, start: re.Pattern[str], end: re.Pattern[str]) -> str:
    """Return the slice of ``text`` from the first ``start`` match to the next
    ``end`` match (or to the end of the text if ``end`` never matches).

    Region scoping is what keeps these content assertions from being vacuous:
    a bare substring search over a whole template passes on incidental prose
    elsewhere in the file, so deleting the rule under test would not fail.
    """
    start_match = start.search(text)
    assert start_match, f"template has no section matching {start.pattern!r}"
    begin = start_match.start()
    end_match = end.search(text, begin)
    return text[begin : end_match.start() if end_match else len(text)]


def _index_instructions_region(text: str) -> str:
    """Return only the slice of a map template that gives the Step 6
    index/sidecar instructions.

    `slug`, `entry`, and `nodes` are not unique to Step 6 — they also show
    up incidentally elsewhere in every template (the flow-data JSON's own
    `nodes` array, the node `kind` enum's `entry` value, `meta.slug` in the
    step 5a example). A bare substring search over the whole template would
    pass even if the Step 6 bullets describing the index entry were deleted
    entirely, because those other occurrences would still be there. Scoping
    to the region between the machine-readable-artifacts heading and the
    next section closes that hole.
    """
    return _section_region(text, _INDEX_SECTION_START, _INDEX_SECTION_END)


@pytest.mark.parametrize("host,name", MAP_TEMPLATES)
def test_map_template_names_index_fields(repo_root: Path, host: str, name: str) -> None:
    """Each host's Step 6 instructions must at least name every field the
    index/sidecar contract requires.

    Field names are stable identifiers, not prose, so this check is robust
    across the hosts' different voices. What it catches: a host dropping a
    field from its Step 6 instructions. What it does NOT catch: a host that
    names a field but omits the rule for how to derive or preserve its
    value (e.g. this test passes as long as `entry` is referenced somewhere
    in the Step 6 region, even if that region never says which node's `id`
    to use for it). That class of divergence — a present-but-underspecified
    field — is caught only by review, not by this test.
    """
    text = (repo_root / "templates" / host / name).read_text(encoding="utf-8")
    region = _index_instructions_region(text)
    for field in INDEX_FIELD_NAMES:
        assert _field_reference(field).search(region), (
            f"{host}/{name} Step 6 instructions are missing the '{field}' field name"
        )


@pytest.mark.parametrize("host,name", MAP_TEMPLATES)
def test_map_step6_preserves_the_whole_codebase_marker(
    repo_root: Path, host: str, name: str
) -> None:
    """Step 6 must not overwrite a whole-codebase `meta.mode`/`meta.detail`.

    Step 6 is the only step that writes `meta`, and whole-codebase mode's pass 2
    reuses it verbatim for every entry point it traces. A step 6 that sets
    `meta.mode` to `feature` unconditionally therefore rewrites the marker pass 1
    wrote, and the finished whole-repository map claims to be a single-feature
    one — corrupting the exact field phase 3 reads to decide what it is looking
    at. `meta.detail` rides along on the same bug wherever a host enumerates the
    meta block as a closed list.

    Keyed on the literal `whole-code-base` inside the Step 6 region. That string
    has no other reason to appear there: step 6 is feature mode's own step, and
    every other mention of the mode in these templates lives in step 1's
    cross-reference or in the mode section itself, both outside this region. The
    weaker check next door — `mode` appearing in `INDEX_FIELD_NAMES` — passed
    with this bug present, because the buggy text named the field too.

    What it does NOT catch: a host that mentions `whole-code-base` in step 6 but
    states the rule backwards, or that preserves `mode` while still clobbering
    `detail`. Only review sees that.
    """
    text = (repo_root / "templates" / host / name).read_text(encoding="utf-8")
    region = _index_instructions_region(text)
    assert "whole-code-base" in region, (
        f"{host}/{name} Step 6 never mentions 'whole-code-base': it must say to "
        f"leave meta.mode and meta.detail alone when the index is already a "
        f"whole-codebase map"
    )


# --- Phase 2: whole-codebase mode -----------------------------------------

# Anchored on the *heading*, not the words. Every host also mentions
# "Whole-Codebase Mode" inline in step 1, where it tells the reader to jump to
# the section — and that reference comes first in the file. A loose pattern
# would start the region at that cross-reference, swallowing all of feature
# mode and making every assertion scoped to this region vacuous.
_MODE_SECTION_START = re.compile(r"^#{2,3} +Whole-[Cc]odebase +[Mm]ode *$", re.MULTILINE)


# `thin`, `standard` and `verbose` are searched for as the single token
# `thin|standard|verbose`, the form every host writes them in. Searched
# separately they would be vacuous: "standard" and "thin" already occur inside
# ordinary words and prose elsewhere in these templates.
WHOLE_CODEBASE_FLAGS = ("--whole-code-base", "--detail", "thin|standard|verbose")

# Step 1 — where the flags are actually parsed — in every host: Claude and
# Gemini open it with the heading "#### 1. Identify the Target Flow", Copilot
# with the numbered item "1. **Read the request for option flags first.**".
_STEP1_START = re.compile(r"^(?:#### 1\.|1\. \*\*)", re.MULTILINE)

# Step 2's opening in every host ("#### 2. Discover..." / "2. **Discover..."),
# used as the end boundary so the step 1 region cannot run on into the mode
# section, where the flags are named again.
_STEP1_END = re.compile(r"^(?:#### 2\.|2\. \*\*)", re.MULTILINE)


@pytest.mark.parametrize("host,name", MAP_TEMPLATES)
def test_map_template_documents_the_mode_flags(repo_root: Path, host: str, name: str) -> None:
    """Every host must document both option flags and all three detail levels
    *in step 1*, where its instructions actually parse them.

    These are the user-facing surface of phase 2. A host that omits `--detail`
    silently gives its users a different command from the other two.

    Scoped to step 1's own region rather than searched over the whole file.
    Unscoped, this assertion was satisfied by coincidence: `--whole-code-base`
    and `--detail` both recur in the whole-codebase-mode section further down,
    so deleting a host's entire step 1 flag-parsing block left two of the three
    tokens green, and only `thin|standard|verbose` failed — and only because
    that exact token happens to appear nowhere else. Scoping makes the deletion
    fail deliberately instead of by luck.

    What it does NOT catch: a step 1 that names all three tokens but gives the
    wrong rule for them (e.g. the wrong default, or the wrong fallback for an
    unrecognized `--detail` value). That is review's job, not this test's.
    """
    text = (repo_root / "templates" / host / name).read_text(encoding="utf-8")
    region = _section_region(text, _STEP1_START, _STEP1_END)
    for flag in WHOLE_CODEBASE_FLAGS:
        assert flag in region, f"{host}/{name} step 1 never mentions {flag}"


@pytest.mark.parametrize("host,name", MAP_TEMPLATES)
def test_map_template_has_a_whole_codebase_section(repo_root: Path, host: str, name: str) -> None:
    text = (repo_root / "templates" / host / name).read_text(encoding="utf-8")
    assert _MODE_SECTION_START.search(text), f"{host}/{name} has no whole-codebase mode section"


INVENTORY_FIELD_NAMES = (
    "id",
    "name",
    "file",
    "line",
    "loc",
    "signature",
    "purpose",
    "role",
    "exported",
    "snippet",
)

# Pass 1's own heading, not the mode heading. The mode section opens with
# Task 2's never-edit-source paragraph, which references `purpose` — so a
# region starting at the mode heading satisfies the `purpose` assertion with
# prose that has nothing to do with pass 1's rules.
_PASS1_START = re.compile(r"^#{3,4} +Pass 1\b", re.MULTILINE)

# The trace pass heading, used as the end boundary of the inventory region so
# pass 1's assertions cannot be satisfied by text that belongs to pass 2.
# Heading-anchored for the same reason as the mode heading: pass 1's own prose
# says "belong to pass 2", and a loose pattern would end the inventory region
# at that sentence instead of at the section it names.
_PASS2_START = re.compile(r"^#{3,4} +Pass 2\b", re.MULTILINE)


def _inventory_region(text: str) -> str:
    return _section_region(text, _PASS1_START, _PASS2_START)


@pytest.mark.parametrize("host,name", MAP_TEMPLATES)
def test_map_template_names_inventory_fields(repo_root: Path, host: str, name: str) -> None:
    """Pass 1's instructions must name every field an inventory entry carries.

    Scoped to the region between the Pass 1 heading and the Pass 2 heading —
    not the wider whole-codebase-mode heading. `file`, `line` and `name` all
    occur throughout the feature-mode half of every template, so an unscoped
    search would pass even with the inventory instructions deleted outright.
    Anchoring on Pass 1's own heading (rather than the mode heading) matters
    specifically for `purpose`: the mode section opens with Task 2's
    never-edit-source paragraph, which already references `` `purpose` `` in
    prose that has nothing to do with pass 1's own rule for the field — a
    region starting any earlier would let that unrelated reference satisfy
    the assertion even if pass 1's own `purpose` bullet were deleted.
    """
    text = (repo_root / "templates" / host / name).read_text(encoding="utf-8")
    region = _inventory_region(text)
    for field in INVENTORY_FIELD_NAMES:
        assert _field_reference(field).search(region), (
            f"{host}/{name} pass 1 instructions are missing the '{field}' field name"
        )


@pytest.mark.parametrize("host,name", MAP_TEMPLATES)
def test_map_template_requires_inventory_file(repo_root: Path, host: str, name: str) -> None:
    text = (repo_root / "templates" / host / name).read_text(encoding="utf-8")
    assert "inventory.json" in _inventory_region(text)


@pytest.mark.parametrize("host,name", MAP_TEMPLATES)
def test_map_template_catalogues_tests_rather_than_skipping_them(
    repo_root: Path, host: str, name: str
) -> None:
    """Test files must be catalogued with role "test", never excluded.

    Excluding them makes every test-only helper look unreachable, which
    produces a large class of false dead-code findings in phase 3. This is the
    single rule whose omission would quietly poison the next phase, so it gets
    its own assertion rather than riding on the `role` field-name check.
    """
    region = _inventory_region(
        (repo_root / "templates" / host / name).read_text(encoding="utf-8")
    )
    assert '"test"' in region or "`test`" in region, (
        f"{host}/{name} pass 1 never assigns the test role"
    )


def _iter_template_files(repo_root: Path) -> list[Path]:
    """Every file the installer ships from templates/, recursively."""
    return sorted(p for p in (repo_root / "templates").rglob("*") if p.is_file())


def test_shipped_templates_have_no_crlf(repo_root: Path) -> None:
    """Every file under templates/ must use bare LF line endings on disk.

    `.gitattributes` normalizes the git *index* to LF (`* text=auto eol=lf`),
    but neither `npm publish` nor `uv build` packs the index — both pack the
    *working tree*, per the comment in `.gitattributes`. On Windows, a tool
    that opens one of these files in text mode and writes it back (e.g.
    `Path.write_text()` with its default `newline=None`) silently translates
    `\n` to `\r\n`. That corrupts the working-tree copy without `git status`
    ever flagging it, because git compares *normalized* content. A release
    cut from a working tree in that state would ship CRLF templates to every
    consumer — this happened during phase 2 development and was caught only
    by manually inspecting bytes, not by any test.

    Checked at the byte level, not via `Path.read_text()`: reading with
    universal-newline translation silently normalizes CRLF back to `\n`, so
    a text-mode read would pass even against a fully CRLF file on disk.
    """
    offenders = [
        str(path.relative_to(repo_root))
        for path in _iter_template_files(repo_root)
        if b"\r\n" in path.read_bytes()
    ]
    assert not offenders, (
        "templates/ files with CRLF line endings (must be bare LF): "
        + ", ".join(offenders)
    )


COVERAGE_FIELD_NAMES = (
    "filesScanned",
    "filesSkipped",
    "skipReason",
    "functionsCatalogued",
    "entryPointsFound",
    "flowsTraced",
)


@pytest.mark.parametrize("host,name", MAP_TEMPLATES)
def test_map_template_names_every_coverage_field(repo_root: Path, host: str, name: str) -> None:
    """Whole-codebase mode must account for all six coverage fields.

    Phase 3 decides how much of the map it can trust from these numbers, and
    `flowsTraced` below `entryPointsFound` is how a partial run stays visible
    rather than passing for a complete one.
    """
    text = (repo_root / "templates" / host / name).read_text(encoding="utf-8")
    region = _section_region(text, _MODE_SECTION_START, re.compile(r"\Z"))
    for field in COVERAGE_FIELD_NAMES:
        assert _field_reference(field).search(region), (
            f"{host}/{name} whole-codebase mode never mentions '{field}'"
        )


@pytest.mark.parametrize("host,name", MAP_TEMPLATES)
def test_map_template_skips_already_registered_flows(
    repo_root: Path, host: str, name: str
) -> None:
    """Re-running must skip flows already in index.json.

    Without this, a repository too large for one session can never finish: each
    run redoes the flows the previous run completed.

    Keyed on the literal clause "do not re-trace" rather than on the words
    "already" and "skip", both of which occur elsewhere in the same region
    ("every entry point not already mapped", "skip step 3") and would leave
    this assertion green with the resume rule deleted. The cost of keying on a
    phrase is that rewording the rule breaks the test; the failure message
    below says exactly which phrase is expected, and all three hosts are
    required to carry it verbatim.
    """
    region = _section_region(
        (repo_root / "templates" / host / name).read_text(encoding="utf-8"),
        _PASS2_START,
        re.compile(r"\Z"),
    )
    assert "do not re-trace" in region.lower(), (
        f"{host}/{name} pass 2 is missing the resume rule: its instructions for "
        f"an already-registered flow must say 'do not re-trace'"
    )


# --- Phase 3a: quality command ---------------------------------------------

QUALITY_TEMPLATES = (
    ("claude", "code-flow.quality.md"),
    ("gemini", "code-flow.quality.toml"),
    ("copilot", "code-flow.quality.prompt.md"),
)

# Marks the start of the "load the map" instructions in every host
# (Claude/Gemini: "#### 2. Load the Map"; Copilot: "2. **Load the map.**").
_LOAD_START = re.compile(r"load the map", re.IGNORECASE)

# Marks the start of the *next* section after it, in every host
# (Claude/Gemini: "#### 3. Run the Detectors"; Copilot: "3. **Run the
# detectors.**"). Used as the end boundary so the scoped region cannot run
# past step 2 into the detector text, where "inventory.json" and "skipped"
# both legitimately appear again.
_LOAD_END = re.compile(r"\n(?:#### 3\.|3\.\s*\*\*Run the detectors)")


def _load_region(text: str) -> str:
    return _section_region(text, _LOAD_START, _LOAD_END)


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_reads_all_three_artifact_kinds(
    repo_root: Path, host: str, name: str
) -> None:
    """Every detector's input comes from one of these three, so the load step
    must name all three. A template that forgot `<slug>.json` would produce a
    report with two detectors silently missing."""
    region = _load_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    for artifact in ("index.json", "inventory.json", "<slug>.json"):
        assert artifact in region, f"{host} load step does not name {artifact}"


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_stops_when_the_index_is_absent(
    repo_root: Path, host: str, name: str
) -> None:
    """No index means there is no map at all, so the remedy is the plain map
    command — not the whole-code-base one, which is the inventory's remedy."""
    region = _load_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert re.search(
        r"`(?:Code_Flows/)?index\.json`\s+is absent.{0,60}?\bstop\b",
        region,
        re.IGNORECASE | re.DOTALL,
    ), f"{host} does not say to stop when the index is absent"
    assert re.search(
        r"`(?:Code_Flows/)?index\.json`\s+is absent.{0,120}?`/code-flow\.map`",
        region,
        re.IGNORECASE | re.DOTALL,
    ), f"{host} does not name /code-flow.map as the remedy for an absent index"


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_stops_when_inventory_is_absent(
    repo_root: Path, host: str, name: str
) -> None:
    """A missing inventory takes two of four detectors with it, so the command
    stops rather than emitting a report whose meaning depends on how the user
    happened to build their map. The remedy must be named, not implied."""
    region = _load_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert re.search(
        r"`(?:Code_Flows/)?inventory\.json`\s+is absent.{0,60}?\bstop\b",
        region,
        re.IGNORECASE | re.DOTALL,
    ), f"{host} does not say to stop when the inventory is absent"
    assert re.search(
        r"`(?:Code_Flows/)?inventory\.json`\s+is absent.{0,160}?`/code-flow\.map\s+--whole-code-base`",
        region,
        re.IGNORECASE | re.DOTALL,
    ), f"{host} does not name the whole-code-base remedy for an absent inventory"
    assert re.search(
        r"duplicate-intent\s+and\s+unreached", region, re.IGNORECASE
    ), f"{host} does not say which detectors the missing catalog takes with it"


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_refuses_to_overwrite_unparsable_artifacts(
    repo_root: Path, host: str, name: str
) -> None:
    """Mirrors the rule the map command already follows for index.json."""
    region = _load_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert re.search(
        r"does not\s+parse as JSON.{0,260}?do not overwrite.{0,80}?never\s+writes",
        region,
        re.IGNORECASE | re.DOTALL,
    ), f"{host} does not couple the parse failure to the do-not-overwrite rule"


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_skips_duplicate_intent_on_thin_maps(
    repo_root: Path, host: str, name: str
) -> None:
    """A thin map carries no snippets, so duplicate-intent has no evidence to
    cite. Both remedies must be named — the flag and the re-map."""
    region = _load_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert "duplicate-intent" in region
    assert "--read-code" in region
    assert re.search(r"--detail\s+standard", region)


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_survives_one_bad_flow_file(
    repo_root: Path, host: str, name: str
) -> None:
    """One unreadable flow is a coverage fact, not a stop condition — the other
    flows are still analyzable."""
    region = _load_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert re.search(r"skip that flow|skip it and", region, re.IGNORECASE)


# Marks the start of the detector instructions in every host (Claude/Gemini:
# "#### 3. Run the Detectors"; Copilot: "3. **Run the detectors.**").
_DETECTORS_START = re.compile(r"run the detectors", re.IGNORECASE)

# Marks the start of the *next* section (Claude/Gemini: "#### 4. ..."; Copilot:
# "4. **..."). Scoping matters here: "snippet", "severity" and "sites" all
# appear again in the step 5/6 output instructions, so an unscoped search
# would pass even with the detector rules deleted.
#
# The Copilot alternative is deliberately title-agnostic (`4\.\s*\*\*`, not
# `4\.\s*\*\*Verify`). A title-locked pattern only works until Task 4 titles
# Copilot's step 4 something other than "Verify" — at which point this anchor
# would stop matching, `_section_region` would fall back to end-of-text, and
# the detectors region would silently swallow steps 4-6. Every assertion in
# this file would keep passing against that much larger haystack, which is
# exactly the vacuity region-scoping exists to prevent. Do not re-tighten
# this to a specific title.
_DETECTORS_END = re.compile(r"\n(?:#### 4\.|4\.\s*\*\*)")

# Each detector paired with the principle it reports under. The pairing is the
# contract, not the name: a template that renamed `complexity-hotspot`'s
# principle to `DRY` would still name all four detectors, and every suite would
# stay green. Verified against all three templates, not assumed.
DETECTOR_PRINCIPLES = (
    ("duplicate-intent", "DRY"),
    ("repeated-sequence", "DRY"),
    ("complexity-hotspot", "KISS"),
    ("unreached", "YAGNI"),
)

FINDING_FIELD_NAMES = (
    "id",
    "principle",
    "detector",
    "severity",
    "confidence",
    "title",
    "rationale",
    "sites",
    "suggestion",
    "effort",
)

SITE_FIELD_NAMES = ("file", "line", "symbol", "snippet")


def _flatten(text: str) -> str:
    """Contract tests assert what a rule says, not how it wraps. Collapsing
    whitespace lets a paragraph reflow — including a reflow a formatter does
    on its own — without turning the suite red for no reason."""
    return re.sub(r"\s+", " ", text)


def _detectors_region(text: str) -> str:
    return _flatten(_section_region(text, _DETECTORS_START, _DETECTORS_END))


def _detector_header_pattern(detector: str, principle: str) -> re.Pattern[str]:
    """Match ``detector`` where it *introduces its own rule paragraph* —
    immediately followed by ``principle`` in parentheses (Claude/Gemini:
    "**a. duplicate-intent (DRY).**"; Copilot: "- **duplicate-intent
    (DRY)**").

    The principle is part of the pattern, not decoration. An earlier form
    matched only ``detector`` followed by ``(`` and claimed in its docstring
    and failure message to verify the detector's principle — so
    ``complexity-hotspot (DRY)`` would have passed every suite, and the
    detector-to-principle mapping was untested anywhere in the repository.

    A bare substring search (`detector in region`, as the plan's own draft of
    this test used) is vacuous for exactly one of the four names:
    `duplicate-intent` is also the `detector` value in the finding-shape JSON
    example that follows all four rules (`"detector": "duplicate-intent"`).
    Deleting the entire duplicate-intent rule paragraph would still leave that
    JSON example behind, and a bare substring check would still pass. The
    other three names never recur in the JSON example, so only this one name
    was actually vacuous — but the fix applies uniformly. Requiring the name
    to be immediately followed by `(` (its principle) matches only the rule
    header: the JSON example's next character after the value is a comma, and
    the per-detector evidence-field bullets never put a `(` directly after the
    bare detector name either.
    """
    return re.compile(re.escape(detector) + r"\s*\(" + re.escape(principle), re.IGNORECASE)


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_names_all_four_detectors(
    repo_root: Path, host: str, name: str
) -> None:
    region = _detectors_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    for detector, principle in DETECTOR_PRINCIPLES:
        assert _detector_header_pattern(detector, principle).search(region), (
            f"{host} detector step does not introduce {detector} under {principle}"
        )


# Each threshold, tied to the concept it governs. A bare number search would
# be vacuous — "8" and "6" and "2" all occur incidentally in a region this
# size — so every pattern requires the number adjacent to what it measures.
# The patterns are deliberately loose about the words *between* number and
# concept, because Claude/Gemini say "fan-out is at least 8" where Copilot's
# numbered-list register says "at fan-out 8", and both are correct.
SEVERITY_THRESHOLDS = (
    r"3 sites",
    r"40 (?:duplicated )?lines",
    r"3 consecutive calls",
    r"2 (?:different )?flows",
    r"fan-out.{0,20}\b8\b",
    r"depth.{0,20}\b6\b",
    r"`loc`.{0,20}\b120\b",
)


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_states_every_severity_threshold(
    repo_root: Path, host: str, name: str
) -> None:
    """Severity is rule-based, not impressionistic. A template that dropped a
    threshold would leave the assistant to invent one, and findings would drift
    toward medium. Every number from the design must survive in every host."""
    region = _detectors_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    for pattern in SEVERITY_THRESHOLDS:
        assert re.search(pattern, region), f"{host} is missing threshold {pattern!r}"


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_names_every_finding_field(
    repo_root: Path, host: str, name: str
) -> None:
    region = _detectors_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    for field in FINDING_FIELD_NAMES:
        assert _field_reference(field).search(region), (
            f"{host} detector step never references the finding field {field!r}"
        )


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_names_every_site_field(
    repo_root: Path, host: str, name: str
) -> None:
    """`FINDING_FIELD_NAMES` only covers the ten top-level finding fields;
    `sites` is itself an array of objects with fields of their own. Deleting
    that inner object from the finding-shape example — the site's `file`,
    `line`, `symbol` and `snippet` — would go unnoticed without this."""
    region = _detectors_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    for field in SITE_FIELD_NAMES:
        assert _field_reference(field).search(region), (
            f"{host} detector step never references the site field {field!r}"
        )


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_names_the_per_detector_evidence_fields(
    repo_root: Path, host: str, name: str
) -> None:
    """Three detectors are told to cite evidence the core schema has no home
    for — flow slugs, the metric that tripped and its value, export status. If
    the schema does not name those fields, each run invents its own key for
    them and the report JSON stops being a stable shape."""
    region = _detectors_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    for field in ("flows", "metric", "value", "exported", "reachedBy"):
        assert _field_reference(field).search(region), (
            f"{host} never names the evidence field {field!r}"
        )


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_gives_unreached_its_reached_by_values(
    repo_root: Path, host: str, name: str
) -> None:
    """`unreached` and `production-unreached` are materially different outcomes
    with different severity rules, and both emit `detector: "unreached"`. Before
    `reachedBy`, the distinction survived only in `title`/`rationale` prose — so
    nothing could assert it and phase 3b's viewer could not render it. The field
    has exactly two values, and both must be named where the detector's evidence
    fields are defined; naming the field without its enum would let each run
    invent its own spelling of "reached only by tests".

    Anchored by proximity from `reachedBy` to both values, and separately by
    proximity from `production-unreached` to `"tests"`, since it is that
    equivalence — not the bare presence of the field — that the JSON has to
    carry.
    """
    region = _detectors_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert re.search(r'`reachedBy`.{0,120}`"none"`.{0,120}`"tests"`', region), (
        f"{host} names `reachedBy` without both of its two values"
    )
    assert re.search(r'`"tests"`.{0,120}`production-unreached`', region), (
        f'{host} never ties `reachedBy: "tests"` to production-unreached'
    )


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_defers_id_numbering_to_step_5(
    repo_root: Path, host: str, name: str
) -> None:
    """Step 3 defines the id *format*; step 4 then drops findings. If step 3 also
    assigned the counter, a run that legitimately drops `DRY-02` would ship
    `DRY-01, DRY-03` — and `tests/test_report_schema.py` requires contiguity. The
    format stays here, the numbering moves to step 5 (asserted separately over
    the output region), and step 3 must say so or the two steps both look
    authoritative.

    Keyed on the literal clause rather than on "step 5", which appears elsewhere
    in this region ("`confidence` is `unverified` unless step 4 verified the
    finding" is the neighbouring sentence, and other cross-references abound).
    """
    region = _detectors_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert re.search(r"counter is assigned in step 5, after step 4's drops", region), (
        f"{host} step 3 does not defer the id counter to step 5"
    )


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_enumerates_the_id_counter(
    repo_root: Path, host: str, name: str
) -> None:
    """`DRY-01, DRY-02, KISS-01, YAGNI-01` is the clearest statement of "restarts
    per principle" in the whole document — the rule's prose alone reads as a
    single global counter to at least one reader in three. Copilot stated the
    rule without the enumeration; all three hosts now carry it.

    The full four-item sequence is required, not just `DRY-01`: that token alone
    also appears in the finding-shape JSON example a few lines above, so a
    single-token check would stay green with the enumeration deleted.
    """
    region = _detectors_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert "`DRY-01`, `DRY-02`, `KISS-01`, `YAGNI-01`" in region, (
        f"{host} states the per-principle id rule without enumerating it"
    )


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_separates_test_only_reachability(
    repo_root: Path, host: str, name: str
) -> None:
    """Excluding tests would make every test-only helper look dead. The design
    splits the outcome in two rather than collapsing it."""
    region = _detectors_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert "production-unreached" in region
    assert "kept alive only by its own tests" in region


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_defaults_production_unreached_to_medium(
    repo_root: Path, host: str, name: str
) -> None:
    """Every other detector closes its severity rule with an explicit
    "otherwise `medium`" default; `production-unreached` said only "never
    `high`", leaving a non-exported entry as "medium or low" with no rule
    choosing between them — impressionistic, which the severity model
    forbids. Anchored on "never rate it `high`" immediately followed by the
    `medium` default, not on a bare "otherwise `medium`" search: that phrase
    already appears twice more in this region, once per other detector, so
    an unscoped search would pass even with this specific default deleted."""
    region = _detectors_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert re.search(r"never rate it `high`.{0,20}otherwise `medium`", region), (
        f"{host} never defaults a non-exported production-unreached finding to medium"
    )


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_caps_exported_and_never_instructs_deletion(
    repo_root: Path, host: str, name: str
) -> None:
    """Parser-free tracing cannot see dynamic dispatch, so unreached is a
    candidate and never a verdict."""
    region = _detectors_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert "confirm before deleting" in region
    assert re.search(r"`exported`.{0,120}\blow\b", region, re.IGNORECASE | re.DOTALL)
    assert re.search(r"never instructs? deletion|do not tell the user to delete", region, re.IGNORECASE)


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_clusters_rather_than_pairs(
    repo_root: Path, host: str, name: str
) -> None:
    """Three copies of one helper is one finding with three sites, not three
    pairwise findings. Without this rule a 5-site cluster becomes 10 findings."""
    region = _detectors_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert re.search(r"never (one finding )?per pair|not pairwise", region, re.IGNORECASE)


# --- Phase 3a: quality command, step 4 (verify against source) -------------

# Marks the start of the verification instructions (Claude/Gemini: "#### 4.
# Verify Against Source"; Copilot: "4. **Verify against source.**").
_VERIFY_START = re.compile(r"verify against source", re.IGNORECASE)

# Marks the start of the *next* section (Claude/Gemini: "#### 5. ..."; Copilot:
# "5. **..."). Needed because "verified" and "stale" both recur in the step 6
# banner text.
#
# The Copilot alternative is deliberately title-agnostic (`5\.\s*\*\*`, not
# `5\.\s*\*\*Write`), for the same reason `_DETECTORS_END` above is: a
# title-locked pattern only works until Task 5's review retitles Copilot's
# step 5 (Task 3's own step was amended twice in review). At that point this
# anchor would stop matching, `_section_region` would fall back to
# end-of-text, and the verify region would silently swallow steps 5-6 —
# exactly the vacuity region-scoping exists to prevent. Do not re-tighten
# this to a specific title.
_VERIFY_END = re.compile(r"\n(?:#### 5\.|5\.\s*\*\*)")


def _verify_region(text: str) -> str:
    """Flattened for the same reason `_detectors_region` is: these assertions
    check what a rule says, not how it wraps, and several of this region's
    phrases ("not a second scan", "forward-slash") are short enough to land
    on a line break in the shipped templates. `not a second scan` already
    does — see `test_quality_template_verifies_only_cited_files`'s history."""
    return _flatten(_section_region(text, _VERIFY_START, _VERIFY_END))


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_verifies_only_cited_files(
    repo_root: Path, host: str, name: str
) -> None:
    """--read-code verifies candidates; it does not re-scan the repository.
    Re-scanning would duplicate the cost of mapping and not fit on a large
    codebase, which is the whole reason the map is persisted."""
    region = _verify_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert re.search(r"only the files", region, re.IGNORECASE)
    assert re.search(r"not a second scan|do not re-?scan", region, re.IGNORECASE)


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_marks_confidence_both_ways(
    repo_root: Path, host: str, name: str
) -> None:
    """A schema field with only one of its two values ever named is not a
    schema.

    Strengthened from the plan's `"verified" in region`: the substring
    `verified` is contained inside `unverified` (u-n-**verified**), so a bare
    substring check would already be satisfied by the *default* value alone —
    it would still pass even if the template never named what a *confirmed*
    finding is set to. `\\bverified\\b` requires a standalone occurrence,
    which `unverified` never produces (there is no word boundary between the
    `n` and the `v`), so this only matches where the template actually names
    the confirmed value.
    """
    region = _verify_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert re.search(r"\bverified\b", region), (
        f"{host} verify step never names the standalone 'verified' confidence "
        f"value (only 'unverified', which contains it as a substring)"
    )
    assert "unverified" in region


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_drops_only_unverified_stale_findings(
    repo_root: Path, host: str, name: str
) -> None:
    """The order is verify-then-drop. --read-code reads current source, so a
    finding it confirms was checked against the very change that made the file
    stale; dropping it afterwards would discard the best evidence in the
    report."""
    region = _verify_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert re.search(r"unverified", region)
    assert re.search(r"hash", region, re.IGNORECASE)
    assert re.search(r"verify first|before dropping|then drop", region, re.IGNORECASE)


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_drops_the_whole_finding_on_one_stale_site(
    repo_root: Path, host: str, name: str
) -> None:
    """A cluster finding can cite several `sites` across several files. The
    drop rule above never said whether one stale site drops just that site or
    the whole finding — for a DRY cluster with 3 sites, that ambiguity is the
    difference between a finding silently losing evidence and a finding being
    dropped outright. The design intent is the latter: a finding is only as
    trustworthy as its weakest citation, so one stale site drops all of it.
    Keyed on the literal phrase `weakest citation`, since it is the only place
    in this region that states which of the two readings applies."""
    region = _verify_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert re.search(r"weakest citation", region, re.IGNORECASE), (
        f"{host} does not say a stale site drops the whole finding, not just that site"
    )


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_corrects_line_numbers_on_verified_findings(
    repo_root: Path, host: str, name: str
) -> None:
    """A finding kept through a file change must cite where the code is now,
    not where the map recorded it.

    Also checks the forward-slash / repo-relative path rule is restated here:
    this is the one step that rewrites a site's `line` after the map first
    wrote it, so it is the one place a corrected `file` could silently drift
    from the global path convention if the rule went unstated."""
    region = _verify_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert re.search(r"correct.{0,40}line", region, re.IGNORECASE | re.DOTALL)
    assert re.search(r"forward.slash", region, re.IGNORECASE)


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_never_stops_on_staleness(
    repo_root: Path, host: str, name: str
) -> None:
    """There is no staleness threshold, because any threshold would be a number
    the design cannot justify."""
    region = _verify_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert re.search(r"never a reason to stop|does not stop the command", region, re.IGNORECASE)


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_treats_unreadable_files_as_changed(
    repo_root: Path, host: str, name: str
) -> None:
    """Step 4a's hash comparison only detects staleness for a file it can
    still read. A deleted cited file trivially fails any hash comparison, but
    one that merely can't be *read* — a permission error, a binary or
    encoding failure — is unchanged on disk: its hash still matches, so
    without this rule 4a would never flag it, 4c would never fire, and the
    candidate would survive into the report `unverified` under `--read-code`
    forever. That would make the "usually zero" dropped-count hedge in this
    same step (and the identical claim in the README) false for that whole
    sub-case, not just rare.

    Anchored to the hash-comparison sentence itself via proximity between
    "cannot be read" and "changed", not a bare keyword search: `hash` and
    `changed`/`change` both recur several times in this region (the
    comparison itself, the drop rule, the "what made the file stale" aside),
    so an unscoped substring check for either word alone would stay green
    even with this rule deleted outright.
    """
    region = _verify_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert re.search(r"cannot be read.{0,60}changed", region, re.IGNORECASE | re.DOTALL), (
        f"{host} never states that a cited file which cannot be read at all "
        f"counts as changed for the staleness comparison"
    )


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_counts_step_4s_own_parts(
    repo_root: Path, host: str, name: str
) -> None:
    """Step 4 opens by saying how many things happen in it, then lists them. It
    said "two" and listed three (staleness, verify, drop). This is prompt text an
    assistant parses literally, and a miscount is exactly the shape of defect
    that produces a silently skipped step — the third one.

    Both halves are asserted: the stated count, and the three parts it counts.
    Asserting the count alone would pass on a template that said "three" and
    listed two.
    """
    region = _verify_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert re.search(r"\bThree things\b", region), (
        f"{host} step 4 does not open by counting its three parts"
    )
    for part in ("check staleness", "verify", "drop what is left stale"):
        assert re.search(re.escape(part), region, re.IGNORECASE), (
            f"{host} step 4 is missing the {part!r} part it counts"
        )


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_computes_files_changed_over_the_whole_census(
    repo_root: Path, host: str, name: str
) -> None:
    """`filesChanged` is bannered as "how many mapped files have changed since
    mapping", and the parent design says it exists so the command can warn that
    the map is stale ("6 files changed since mapping"). Scoped to the cited files
    only, that banner under-reports staleness on a command whose headline claim
    is honest coverage: nobody reading "6 files have changed" against a 400-file
    map guesses only the 8 cited files were checked.

    Both scopes must be stated, because the whole defect was that one was
    silently standing in for the other. The second assertion is what fails if the
    census scope is ever narrowed back to the cited subset.
    """
    region = _verify_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert re.search(
        # `\W{0,4}` spans the bold markers every host wraps "whole-census" in.
        r"`filesChanged`.{0,40}whole-census\W{0,4}number.{0,60}"
        r"every entry in `index\.json`'s `files` array",
        region,
    ), f"{host} does not compute filesChanged over the whole file census"
    assert re.search(
        r"cited-file subset.{0,140}drop rule below drops on", region
    ), f"{host} does not keep the cited-file subset as what the drop rule uses"


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_handles_a_cited_file_absent_from_the_census(
    repo_root: Path, host: str, name: str
) -> None:
    """Step 4a compares a cited file against "the `hash` recorded for it in
    `index.json`'s `files` array" — and the surrounding rules are exhaustive
    about every other branch, so the one case with no such record read as an
    oversight rather than a decision. A file the census never recorded is not
    evidence of change, so it counts as changed in neither scope."""
    region = _verify_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert re.search(
        r"no entry in `index\.json`'s `files` array.{0,200}changed in neither",
        region,
    ), f"{host} never says what to do with a cited file the census does not record"


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_fills_missing_snippets_from_the_verified_read(
    repo_root: Path, host: str, name: str
) -> None:
    """`--read-code` is named in step 2 as one of the two remedies for a thin
    map, but until this rule existed no step supplied the snippet it promised.
    Trace it: with `--read-code` on a thin map, duplicate-intent is not skipped,
    so step 3a runs and is told to "cite every site, with its snippet" against an
    inventory that carries none. Step 4b's other actions are confirm, drop, set
    `confidence`, correct `line` — none of which fills a snippet in — and 4b's
    "not a second scan" rule forbids widening the read to find one.

    So step 4b takes the snippets from the files it is already opening. Keyed on
    the phrase that states it; a bare `snippet` search would match step 3's
    citation rule quoted elsewhere and the thin-map gate's reference to the field.
    """
    region = _verify_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert re.search(
        r"no `snippet` on its sites.{0,120}thin map.{0,120}"
        r"takes its sites' snippets from the source read here",
        region,
    ), f"{host} step 4b never fills in the snippets a thin map could not supply"


# --- Phase 3a: quality command, steps 5-6 (write the two reports) ----------

# Marks the start of the output instructions (Claude/Gemini: "#### 5. Write
# the Report Data"; Copilot: "5. **Write the report data.**"). Runs to the
# end of the template, so no end anchor is needed — but one is supplied
# anyway so a future step 7 cannot silently widen the region.
_OUTPUT_START = re.compile(r"write the report data", re.IGNORECASE)
_OUTPUT_END = re.compile(r"\n(?:#### 7\.|7\.\s*\*\*)")

REPORT_FIELD_NAMES = ("schema", "meta", "coverage", "findings")


def _output_region(text: str) -> str:
    """Flattened for the same reason `_detectors_region` and `_verify_region`
    are: these assertions check what a rule says, not how it wraps, and the
    proximity windows below are measured against the flattened text."""
    return _flatten(_section_region(text, _OUTPUT_START, _OUTPUT_END))


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_writes_both_artifacts(
    repo_root: Path, host: str, name: str
) -> None:
    region = _output_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert "quality-report.json" in region
    assert "quality-report.md" in region


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_writes_json_before_markdown(
    repo_root: Path, host: str, name: str
) -> None:
    """The JSON is the data and the markdown is one rendering of it. Writing
    the markdown first would make them two independent transcriptions that can
    disagree — and phase 3b adds a third rendering off the same JSON."""
    region = _output_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert region.index("quality-report.json") < region.index("quality-report.md")


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_names_every_report_field(
    repo_root: Path, host: str, name: str
) -> None:
    region = _output_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    for field in REPORT_FIELD_NAMES:
        assert _field_reference(field).search(region), (
            f"{host} output step never references the report field {field!r}"
        )


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_leads_with_coverage(
    repo_root: Path, host: str, name: str
) -> None:
    """Honesty rule 2: a clean section under partial coverage means clean
    within what was mapped, and the document must say so in words. Coverage
    also has to *lead* — "Coverage leads the report" is a global constraint —
    so this test also pins the leading position, not just the honesty phrase.

    Two things worth being explicit about, from review:

    1. The literal phrase `clean within what was mapped` is unique to the
       partial-coverage sentence in this region, so it alone gates the first
       assertion below — deleting that sentence fails this test regardless
       of what else survives.
    2. The `flowsTraced` / `entryPointsFound` checks use `_field_reference`,
       but that is *not* a strengthening over a bare `re.search`: both
       tokens are quote-delimited in step 5's JSON schema example
       (`"flowsTraced": 14`, `"entryPointsFound": 17`), so `_field_reference`
       matches that example exactly as a bare substring search would have.
       An earlier version of this docstring claimed swapping to
       `_field_reference` fixed a vacuousness gap here; it did not — review
       caught that the claim was false. These two checks remain confirmatory
       only (the fields are named somewhere), not load-bearing.

    What *was* an unguarded gap: nothing pinned "coverage leads". Replacing
    "Lead with coverage" / "the first thing under the title" with, say,
    "Include a banner stating:" left every other assertion in this suite
    green, because `_BANNER_ANCHOR` (used by the banner-contents test below)
    anchors on the sentence's *middle* ("entry points were traced"), not its
    opening mandate. The third assertion below closes that gap by requiring
    the literal leading-position phrase.
    """
    region = _output_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert "clean within what was mapped" in region
    assert _field_reference("flowsTraced").search(region)
    assert _field_reference("entryPointsFound").search(region)
    assert re.search(r"first thing under the title", region, re.IGNORECASE), (
        f"{host} never states that the banner is the first thing under the title"
    )


# The banner-describing sentence opens identically in every host: "how many
# of `entryPointsFound` entry points were traced (`flowsTraced`)". Used below
# as a proximity anchor instead of the bare field names, because
# `filesChanged`, `findingsDropped`, `detectorsSkipped` and `flowsUnreadable`
# all also appear as JSON keys in step 5's schema example, earlier in this
# same region — a bare `_field_reference` search for them would stay green
# even if the banner sentence itself (the rule this test guards) were deleted
# outright, since the JSON keys are a separate concern from whether the
# markdown banner narrates them. The banner narrates them in English, not by
# field name, so the assertions below match that English phrasing, anchored
# to the sentence that must contain all four.
_BANNER_ANCHOR = r"entry points were traced \(`flowsTraced`\)"


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_banners_skips_and_drops(
    repo_root: Path, host: str, name: str
) -> None:
    """Everything the gating rule and the drop-rule suppressed has to surface,
    or the report reads as complete when it is not."""
    region = _output_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    for phrase in (
        "flows were unreadable",
        "files have changed",
        "findings were dropped",
        "detectors were skipped",
    ):
        assert re.search(_BANNER_ANCHOR + r".{0,300}" + phrase, region, re.IGNORECASE), (
            f"{host} banner sentence omits {phrase!r}"
        )


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_banners_the_census_scope_and_the_skip_reason(
    repo_root: Path, host: str, name: str
) -> None:
    """Two things the banner sentence names but does not pin down on its own.

    The changed-file count: step 4a now computes it over the whole census, and
    the banner has to say which set it is counting, or "6 files have changed"
    reads as whichever set the reader assumes.

    The skip reason: step 6 requires the banner say which detectors were skipped
    **and why**, but `detectorsSkipped` in the JSON holds only names — and step 5
    says the markdown is rendered from that JSON with nothing contradicting it.
    Rather than widen the schema, the reason is restated from the step 2 rule
    that gated the detector off. Whichever resolution is chosen, all three hosts
    must state the same one, so this pins the chosen one.
    """
    region = _output_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert re.search(
        r"changed-file count is step 4's whole file census, not its cited-file subset",
        region,
    ), f"{host} banner does not say the changed-file count is the whole census"
    assert re.search(
        r"`detectorsSkipped` carries names only.{0,120}"
        r"restate it from the step 2 rule that gated the detector off",
        region,
    ), f"{host} banner does not say where the skip reason comes from"


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_orders_findings_deterministically(
    repo_root: Path, host: str, name: str
) -> None:
    region = _output_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert re.search(r"severity.{0,80}site count.{0,80}principle", region, re.IGNORECASE | re.DOTALL)


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_assigns_ids_after_the_drops(
    repo_root: Path, host: str, name: str
) -> None:
    """The counterpart to `test_quality_template_defers_id_numbering_to_step_5`:
    step 3 has to hand the numbering off, and step 5 has to accept it. Assigning
    ids here, after step 4's drops and in the documented order, is what makes the
    per-principle counter contiguous — which is what
    `tests/test_report_schema.py::test_finding_ids_restart_per_principle_as_a_contiguous_counter`
    requires and what no template previously stated.

    "no gaps" is asserted alongside the assignment clause, because the assignment
    alone does not say the counter is dense: a step 5 that assigned ids in order
    while still honouring numbers step 3 had already spent would satisfy the
    first half and still ship `DRY-01, DRY-03`.
    """
    region = _output_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert re.search(
        r"Assign the `id` counters here.{0,120}after step 4's drops.{0,200}no gaps",
        region,
    ), f"{host} step 5 does not assign the id counters after step 4's drops"


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_reports_when_there_are_no_findings(
    repo_root: Path, host: str, name: str
) -> None:
    """An empty report is a real report, not a skipped one — and never a clean
    bill of health.

    Strengthened from the plan's independent `"no findings" in region` /
    `"clean bill of health" in region` checks: `clean bill of health` occurs
    *twice* in every host — once in the partial-coverage honesty sentence,
    once in this no-findings caveat ("...rather than implying a clean bill
    of health") — and the partial-coverage sentence precedes the no-findings
    paragraph in every host's document order. Two independent substring
    checks therefore stay green even if the no-findings caveat itself is
    deleted outright: `no findings` still matches ("Say there were no
    findings, ..."), and `clean bill of health` still matches the earlier,
    unrelated occurrence. A forward proximity window from `no findings` can
    only reach the caveat's own occurrence (the later one), not the earlier
    sentence that precedes `no findings` in the text — so deleting just the
    caveat now fails this test.
    """
    region = _output_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert re.search(r"no findings.{0,300}clean bill of health", region, re.IGNORECASE), (
        f"{host} no-findings paragraph does not restate 'clean bill of health' near 'no findings'"
    )


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_says_catalogued_never_all(
    repo_root: Path, host: str, name: str
) -> None:
    """Discovery was Glob/Grep/Read, not an AST walk, so the map is
    best-effort and the report must never claim completeness. This is a
    global constraint on the report this step writes, so it belongs here
    rather than waiting for Task 6's fixture to imply it indirectly."""
    region = _output_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert re.search(r'"catalogued".{0,120}never.{0,10}"all"', region, re.IGNORECASE | re.DOTALL), (
        f"{host} never says 'catalogued', never 'all'"
    )


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_never_writes_source(
    repo_root: Path, host: str, name: str
) -> None:
    """Checked over the whole template, not a region: this rule belongs
    everywhere and its absence anywhere is the defect."""
    text = (repo_root / "templates" / host / name).read_text(encoding="utf-8")
    assert re.search(r"never edits source code", text, re.IGNORECASE)


# --- Phase 3b: the quality command's third rendering -----------------------


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_writes_the_html_last(repo_root: Path, host: str, name: str) -> None:
    """The JSON is the data and both renderings come from it. Naming the HTML
    before the JSON would invite writing them as independent transcriptions.

    Strengthened from the plan's draft, which compared the HTML against the
    JSON alone. The design's decision 3 fixes the written order as
    `json -> md -> html` ("the HTML is named after the markdown"), and a
    JSON-only comparison is satisfied by an HTML paragraph placed anywhere
    after step 5's opening sentence -- including between the JSON and the
    markdown, which is the one ordering that decision rules out. Both hops are
    pinned, so that placement fails.
    """
    region = _output_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    j = region.index("quality-report.json")
    m = region.index("quality-report.md")
    h = region.index("quality-report.html")
    assert j < h, f"{host} names the HTML before the JSON it renders from"
    assert m < h, (
        f"{host} names the HTML before the markdown; the written order is json, md, html"
    )


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_names_the_report_scaffold(repo_root: Path, host: str, name: str) -> None:
    """The command fills a scaffold the installer placed; if it does not name the
    path, the assistant will invent a viewer instead of using the shipped one.

    Strengthened from the plan's draft, which asked only that the token appear
    within 200 characters of the path, in any relationship at all -- a sentence
    saying the scaffold arrives with `__REPORT_DATA__` already filled in would
    have satisfied it. What the rule actually requires is the *action*: replace
    that one token, and only it. Keyed on the clause that states it.
    """
    region = _output_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert re.search(
        r"\.code-flow/report\.template\.html.{0,120}?"
        r"replace\s+its\s+single\s+`__REPORT_DATA__`\s+token",
        region, re.IGNORECASE | re.DOTALL,
    ), f"{host} does not tie the scaffold to its token"


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_states_the_html_escaping_rule(
    repo_root: Path, host: str, name: str
) -> None:
    """Findings carry source snippets, which contain `</`. Substituted raw into a
    script block that ends the block early and the page renders as text.

    Strengthened from the plan's draft, `</.{0,120}?escape`. That pattern is
    satisfied by any `</` within 120 characters of any inflection of "escape",
    which the rule's own consequence clause supplies on its own: deleting the
    instruction ("Escape every literal `</` ... as `<\\/`") while keeping the
    explanation ("an unescaped `</` closes the script block early") leaves the
    draft green with the actionable half gone. This pins both halves and the
    replacement text between them, so neither can be deleted alone.
    """
    region = _output_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert re.search(
        r"[Ee]scape every literal `</`.{0,40}?as `<\\/`.{0,300}?"
        r"unescaped `</` closes the script block early",
        region, re.DOTALL,
    ), f"{host} does not state the </ escaping rule"


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_states_the_three_files_never_contradict(
    repo_root: Path, host: str, name: str
) -> None:
    """`quality-report.json`, `.md` and `.html` are three renderings of one
    document, and this rule is what keeps a future edit to just one of them
    from being read as a spec change instead of a bug.

    `tests/test_host_parity.py` only diffs Claude against Gemini, so it
    structurally cannot see Copilot drift -- this project's recurring failure
    is a rule present in two hosts and absent from the third. Before this
    test, that rule's only guard in Copilot was a human read that expires the
    moment this branch merges.

    The wording is not byte-identical across hosts: Claude and Gemini say
    "All three files are renderings of the same data"; Copilot's own register
    says "All three files render the same data". The pattern is written
    around that difference -- anchored on "All three files" and "none may
    contradict another" with a loose gap for "same data" between them -- so it
    does not require reflowing Copilot's prose to match Claude's, only that
    every host state the same rule.

    "All three files" is unique to this sentence in every host (the only other
    "three ..." phrase in this step is "report all three file paths to the
    user", which does not start with "All"), so this is not satisfied by
    incidental prose elsewhere in the output region.
    """
    region = _output_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert re.search(r"All three files\b.{0,40}same data.{0,30}none may contradict another", region), (
        f"{host} never states that the three report files are renderings of the same data "
        f"that must not contradict one another"
    )


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_degrades_gracefully_without_the_scaffold(
    repo_root: Path, host: str, name: str
) -> None:
    """The other half of the step-6 rule pair introduced alongside the test
    above: if `.code-flow/report.template.html` cannot be read, the command
    still writes the JSON and the markdown rather than stopping.

    Same parity gap as the test above -- `test_host_parity.py` cannot see
    Copilot, so this rule's only guard there was a human read. The lead-in
    clause differs by host (Claude/Gemini: "If you cannot read the scaffold";
    Copilot: "If the scaffold cannot be read"), so the pattern matches either
    phrasing rather than reflowing one host's prose to match the other's. The
    consequence clause that follows -- "a missing viewer is a missing
    convenience, not a missing report" -- is byte-identical in all three hosts
    and anchors the assertion to the specific degradation rule rather than to
    any other sentence that happens to contain "cannot" or "missing".
    """
    region = _output_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert re.search(
        r"cannot (?:read the scaffold|be read),? say so and write the other two"
        r".{0,10}a missing viewer is a missing convenience, not a missing report",
        region,
    ), (
        f"{host} does not say the command still writes the JSON and markdown "
        f"when the report scaffold cannot be read"
    )


# --- Phase 3b: the two viewer scaffolds ------------------------------------

SCAFFOLDS = (
    ("index.template.html", "__INDEX_DATA__"),
    ("viewer.template.html", "__FLOW_DATA__"),
    ("report.template.html", "__REPORT_DATA__"),
)

# The one URL either scaffold is allowed to contain. An XML namespace is an
# opaque identifier, not a network reference: no browser ever dereferences it,
# and `document.createElementNS` needs the literal string to build SVG nodes.
# The flow viewer carries it twice (the `xmlns` attribute and `SVGNS`), so the
# blanket "no http(s) anywhere" check the plan drafted cannot be applied as
# written -- it fails on a file that is already fully offline. Excising exactly
# this string and then applying the blanket check keeps the rule sharp: any
# other remote reference, including one whose host merely contains "w3.org",
# still fails.
_XML_NAMESPACE = "http://www.w3.org/2000/svg"


def _scaffold(repo_root: Path, name: str) -> str:
    return (repo_root / "templates" / "shared" / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("name,token", SCAFFOLDS)
def test_scaffold_has_exactly_one_token(repo_root: Path, name: str, token: str) -> None:
    """More than one token means the installer's replacement would fill some and
    not others; none means it fills nothing and the page shows the token check."""
    assert _scaffold(repo_root, name).count(token) == 1


@pytest.mark.parametrize("name,token", SCAFFOLDS)
def test_scaffold_is_self_contained(repo_root: Path, name: str, token: str) -> None:
    """Both scaffolds must render from a file:// URL with no network. An external
    reference would leave a user staring at an unstyled or empty page offline."""
    text = _scaffold(repo_root, name)
    assert not re.search(r"<script[^>]+\bsrc\s*=", text), f"{name} loads an external script"
    assert not re.search(
        r"""<link[^>]+\brel\s*=\s*["']stylesheet""", text
    ), f"{name} loads an external stylesheet"
    assert "@import" not in text, f"{name} pulls in an external stylesheet with @import"
    offline = text.replace(_XML_NAMESPACE, "")
    assert "https://" not in offline and "http://" not in offline, (
        f"{name} references a remote URL"
    )


@pytest.mark.parametrize("name,token", SCAFFOLDS)
def test_scaffold_marks_its_validator_with_sentinels(
    repo_root: Path, name: str, token: str
) -> None:
    """test/viewer-validation.test.js lifts the block between these markers. If a
    scaffold loses them the harness cannot reach its validator at all."""
    text = _scaffold(repo_root, name)
    assert text.count("/* ==== validate:start ==== */") == 1
    assert text.count("/* ==== validate:end ==== */") == 1


@pytest.mark.parametrize("name,token", SCAFFOLDS)
def test_scaffold_wires_a_failed_validation_to_fail(repo_root: Path, name: str, token: str) -> None:
    """`validate()`'s verdict must actually gate the render. Mutation-confirmed
    gap: changing the call site's `if (!v.ok) { ... }` to `if (false) { ... }`
    left both `test_template_contracts.py` and `test/viewer-validation.test.js`
    green, because the Node harness only ever calls `validate()` directly and
    asserts its return value -- it never touches the line that reads that
    return value back in the scaffold. Nothing in either suite verified the
    verdict was honored at all.

    Pinned as one flattened, whitespace-tolerant sequence -- `if (!v.ok)`, the
    opening brace, the `fail(v.title, v.lines);` call, `return;`, the closing
    brace -- so that changing any link in that chain (swapping the condition,
    dropping the `return`, calling `fail` with the wrong arguments) fails this
    test. Whitespace is tolerated rather than pinned literally because the two
    scaffolds already format the same line differently (`){ fail` in the flow
    viewer, `) { fail` in the report viewer) and that formatting difference
    carries no meaning.

    Scoped to the text after the `validate:end` sentinel, not the whole file:
    `if (!v.ok)` only ever appears once in either scaffold, but scoping keeps
    this test honest about which half of the file it is pinning -- the call
    site, not `validate()` itself, which is covered separately by
    `test/viewer-validation.test.js`.
    """
    text = _scaffold(repo_root, name)
    render = _flatten(text[text.index("/* ==== validate:end ==== */") :])
    assert re.search(
        r"if\s*\(!v\.ok\)\s*\{\s*fail\(v\.title,\s*v\.lines\);\s*return;\s*\}", render
    ), f"{name} does not wire a failed validate() verdict to fail() and a return"


@pytest.mark.parametrize("name,token", SCAFFOLDS)
def test_scaffold_shares_one_theme_key(repo_root: Path, name: str, token: str) -> None:
    """The two artifacts sit side by side in `Code_Flows/`, so a user who puts one
    in dark mode expects the other to follow. That only happens if both write the
    same `localStorage` key, and a typo in either is invisible until someone opens
    both. Pinned to the literal key rather than to "localStorage is used"."""
    assert "codeflow-theme" in _scaffold(repo_root, name), (
        f"{name} does not use the shared theme key"
    )


def test_report_viewer_leads_with_coverage(repo_root: Path) -> None:
    """The same rule the markdown obeys. A prettier rendering makes over-reading
    easier, so the caveat has to be the first thing on screen, not a footnote.

    Four assertions, where the plan's draft had one.

    The draft compared first occurrences over the *whole file*, and in this
    scaffold the first occurrence of each name is its CSS rule, not its render
    call. So the draft assertion is really about stylesheet order: moving the
    banner's render call below the findings list, which is exactly the defect it
    is named for, leaves it green as long as the two CSS blocks stay put. The
    second assertion re-runs the comparison over the render code alone (the text
    after the validator's end sentinel), where the order of the two names is the
    order the DOM is built in.

    The third pins "not collapsible", which position alone does not: a banner
    wrapped in a `<details>` still precedes the findings list while being shut by
    default. It is deliberately broader than the rule it names -- it forbids
    disclosure widgets anywhere in the file -- because there is no cheap textual
    way to scope it to the banner, and this scaffold has no other use for one.
    It matches the tag name after a quote as well as after `<`: every element on
    this page is built with `document.createElement`, so a collapsible banner
    would be written `el("details", "coverage-banner")` and a check for literal
    `<details` markup would never see it. Mutation-confirmed -- the markup-only
    form of this assertion stayed green against exactly that change.

    The fourth pins the partial-coverage wording. `flowsTraced` below
    `entryPointsFound` is the case the whole banner exists for, and nothing else
    in this suite requires the viewer to say so in words: the phrase "clean
    within what was mapped" is also carried by the no-findings screen, so the
    no-findings test stays green even with the partial branch deleted outright.

    What none of them catches: CSS that renders the banner off-screen or at zero
    height. Only the manual browser check sees that.
    """
    text = _scaffold(repo_root, "report.template.html")
    assert text.index("coverage-banner") < text.index("findings-list"), (
        "the coverage banner must come before the findings"
    )
    render = text[text.index("/* ==== validate:end ==== */") :]
    assert render.index("coverage-banner") < render.index("findings-list"), (
        "the coverage banner must be rendered into the page before the findings list"
    )
    assert not re.search(r"""["'<]details\b""", text, re.IGNORECASE), (
        "the coverage banner must not be collapsible"
    )
    assert re.search(r"The map is partial", text), (
        "when flowsTraced is below entryPointsFound the banner must say so in words"
    )


def test_report_viewer_never_claims_completeness(repo_root: Path) -> None:
    """'catalogued, never all' binds the viewer exactly as it binds the report.

    The bare-word check is the plan's; the third assertion is added because the
    bare word is nearly vacuous on its own -- `functionsCatalogued` is a field
    name the renderer has to mention anyway, so a viewer whose banner read "1180
    functions found" would still pass a case-insensitive substring search for
    "catalogued". Requiring the word next to the noun it qualifies ties the
    assertion to the claim the banner actually makes.
    """
    text = _scaffold(repo_root, "report.template.html")
    assert "catalogued" in text
    assert not re.search(r"\ball files\b|\ball functions\b", text, re.IGNORECASE)
    assert re.search(r"functions catalogued", text), (
        "the coverage banner must say 'functions catalogued', not 'functions found'"
    )


def test_report_viewer_states_the_no_findings_caveat(repo_root: Path) -> None:
    """The most dangerous screen in the product. An empty findings array means
    'clean within what was mapped', and the viewer must say so in words rather
    than rendering an empty state that reads as a pass.

    The third assertion is added to the plan's two. The words can be exactly
    right and the screen still read as a pass if a checkmark sits above them --
    which is precisely what a designer reaches for on an empty state. There is
    no glyph in either scaffold's legitimate vocabulary that this forbids: the
    theme toggle is a half-circle, and every other affordance is a word.
    """
    text = _scaffold(repo_root, "report.template.html")
    assert re.search(r"clean within what was mapped", text, re.IGNORECASE)
    assert re.search(
        r"no findings.{0,400}clean bill of health", text, re.IGNORECASE | re.DOTALL
    )
    for glyph in ("✓", "✔", "✅", "☑"):
        assert glyph not in text, "a checkmark on the no-findings screen reads as a pass"


def test_report_viewer_never_instructs_deletion(repo_root: Path) -> None:
    """`unreached` is a candidate, never a verdict, so the viewer offers no delete
    affordance and no copy that reads as an instruction to remove code.

    Both assertions are strengthened from the plan's draft.

    The 'candidate' half was a bare substring search, which the word "candidate"
    anywhere in the file satisfies -- including in a comment, and including if
    the `unreached` copy itself were rewritten as a verdict. Proximity to
    `unreached` alone is not enough either: the note's own CSS class is
    `candidate-note`, and mutation-testing confirmed that rewriting the copy to
    "An unreached function is dead code" left a proximity-only assertion green,
    satisfied by the class name a few characters away. So the claim is what is
    pinned -- candidate *and* never a verdict, adjacent -- which no class name
    can supply. `re.search` scans every occurrence, not just the first, so the
    `unreached` inside the validator's detector enum does not fix the window.

    The 'no affordance' half matched only `>Delete`, a label in literal markup.
    But this scaffold builds every control in JS and sets labels with
    `textContent`, so a genuine delete button would be written
    `el("button", null, "Delete")` and the drafted regex would never see it.
    Admitting a leading quote as well as `>` covers the form this file would
    actually take. The trailing `\\b` keeps `classList.remove(` and
    `removeChild(` out (both follow a dot, not a quote) and keeps past-tense
    prose like "removed" out too.
    """
    text = _scaffold(repo_root, "report.template.html")
    assert re.search(
        r"unreached\b.{0,140}candidate\b.{0,40}never a verdict",
        text,
        re.IGNORECASE | re.DOTALL,
    ), "the copy describing unreached findings must call them candidates, never verdicts"
    assert not re.search(r"""["'>]\s*(delete|remove)\b""", text, re.IGNORECASE), (
        "no delete affordance: the viewer never offers to remove code"
    )


def test_report_viewer_filters_but_never_reorders(repo_root: Path) -> None:
    """Findings render in the JSON's order, full stop. The analysis already
    ordered them by severity, then site count, then principle; a viewer that
    reordered would make two renderings of one file disagree about which finding
    comes first, and the markdown and the HTML would stop matching.

    Filtering is in scope and is asserted present, so this test fails in both
    directions: it fails if the filters are dropped, and it fails if any
    reordering -- a `.sort(`/`.reverse(` call, their non-mutating ES2023
    counterparts `.toSorted(`/`.toReversed(`, or a sort/reverse control -- is
    added.

    The reordering half is keyed on whole words rather than on `.sort(` alone,
    so it catches a control (an `id` or a button label) as well as the call.
    That makes it stricter than the rule strictly requires: the scaffold
    cannot mention any of these words even in a comment.

    `\bsort\b` alone -- the original form of this assertion -- is mutation-
    confirmed insufficient: `findings.slice().reverse().forEach(...)` renders
    findings back-to-front and left that pattern green, because `\bsort\b`
    never considers "reverse" at all, and `\b` also blocks it from matching
    "sorted" (there is no word boundary between the "t" and the "e") or
    "toSorted"/"toReversed" (no boundary inside either name). This pattern
    lists each form as its own alternative so the word-boundary check applies
    to the whole token, not just a prefix of it.

    That closes the specific escape that was found, not every conceivable one:
    a hand-rolled reordering that reads and rewrites `findings` by index
    without calling any of these six names would still slip past a text
    search. Only review catches that.
    """
    text = _scaffold(repo_root, "report.template.html")
    assert "filter-severity" in text, "the severity filter is required"
    assert "filter-principle" in text, "the principle filter is required"
    assert not re.search(
        r"\b(?:sort|sorted|reverse|reversed|toSorted|toReversed)\b", text, re.IGNORECASE
    ), (
        "the viewer must render findings in the JSON's order and offer no reordering control"
    )


def test_report_viewer_renders_report_data_as_text_not_markup(repo_root: Path) -> None:
    """Snippets are source code from the analyzed repository. A snippet
    containing `</script>` or an `onerror` attribute must land on the page as
    characters, never as markup -- the substitution that fills this file already
    has a `</` trap, and an `innerHTML` render path would turn it into a second
    one.

    `innerHTML` is permitted in exactly one form, `innerHTML = ""`, which the
    error card uses to clear itself before rebuilding. Every other sink is
    banned outright rather than inspected, because none of them has a benign
    form here.

    What this does NOT catch: a value assigned through a DOM property that
    parses markup indirectly, or a `setAttribute("href", ...)` carrying a
    `javascript:` URL. Review's job, not this test's.
    """
    text = _scaffold(repo_root, "report.template.html")
    for use in re.findall(r"innerHTML[^;\n]*", text):
        assert re.fullmatch(r'innerHTML\s*=\s*""', use.strip()), (
            f"innerHTML may only be used to clear an element, found: {use.strip()!r}"
        )
    for sink in ("insertAdjacentHTML", "outerHTML", "document.write", "createContextualFragment"):
        assert sink not in text, f"{sink} would interpret a snippet as markup"


def test_report_viewer_grid_columns_cannot_be_sized_by_their_widest_item(repo_root: Path) -> None:
    """Found by the 2026-08-08 manual browser pass, which is the only check that
    can see it: `.findings-list` and `ul.sites` are grid containers, and grid
    items keep `min-width:auto`. Without an explicit `minmax(0,...)` the single
    column is sized to the widest item's *min-content* width -- so one long
    snippet line anywhere in the report sets the width of EVERY card. On a real
    report that meant 1264px cards inside an 840px column, including cards with
    no snippet at all, and a horizontal scrollbar below roughly 1650px.

    `ul.sites pre{overflow:auto}` does not save it: the column grows instead of
    the `<pre>` scrolling.

    Pinned per selector rather than as a blanket rule over every `display:grid`,
    because the layout grids in these files are content-sized on purpose.
    """
    text = _scaffold(repo_root, "report.template.html")
    for selector in (r"\.findings-list", r"ul\.sites"):
        rule = re.search(selector + r"\{([^}]*)\}", text)
        assert rule is not None, f"no {selector} rule found in report.template.html"
        body = rule.group(1)
        assert "display:grid" in body.replace(" ", ""), (
            f"{selector} is no longer a grid -- this test guards the grid sizing "
            f"and must be revisited, not deleted"
        )
        assert re.search(r"grid-template-columns:\s*minmax\(\s*0\s*,", body), (
            f"{selector} is a grid without minmax(0,...); one long snippet line "
            f"will set the width of every card and overflow the document"
        )


def test_report_viewer_shows_a_skipped_detector_with_its_reason(repo_root: Path) -> None:
    """A detector that did not run is a hole in the report, and a hole named
    without its cause reads as a detail rather than as a limit on what the
    findings below can mean.

    `detectorsSkipped` carries names only -- the quality templates say so
    explicitly and tell the markdown to restate the reason from the step 2
    gating rule. The viewer renders the same JSON, so it has to do the same
    thing: hold the reason itself. Both halves are required, because a viewer
    that knew duplicate-intent's reason and rendered nothing at all for an
    unrecognised name would silently hide the very thing this rule exists for.
    """
    text = _scaffold(repo_root, "report.template.html")
    assert re.search(r"duplicate-intent.{0,240}snippet", text, re.DOTALL), (
        "the viewer must restate why duplicate-intent was gated off: a thin map has no snippets"
    )
    assert re.search(r"reason[^\n]{0,60}not recorded", text, re.IGNORECASE), (
        "a detector whose reason the viewer does not know must still say so, not be hidden"
    )


def test_flow_index_token_cannot_render_as_visible_text(repo_root: Path) -> None:
    """`__FLOW_INDEX__` is optional. The map command fills it, but every host is
    told to leave it alone when `index.json` is missing or unparseable — so an
    unreplaced placeholder is a supported outcome, not a bug, and it must be
    impossible to see. It is safe only because it sits inside a
    `<script type="application/json">` block, which browsers never render;
    anywhere else in the document it would print raw on every flow page. Pinned
    to that containment rather than to the token merely existing."""
    text = _scaffold(repo_root, "viewer.template.html")
    assert text.count("__FLOW_INDEX__") == 1, "the optional index token must appear exactly once"
    holder = re.search(
        r'<script[^>]+type="application/json"[^>]*id="flow-index"[^>]*>\s*__FLOW_INDEX__\s*</script>',
        text,
    )
    assert holder is not None, (
        "__FLOW_INDEX__ must sit alone inside its application/json script block; "
        "outside one, an unreplaced token renders as visible text on every flow page"
    )


def test_every_scaffold_offers_a_way_back_to_the_index(repo_root: Path) -> None:
    """A landing page that pages cannot return to is a one-way trip. The link is
    plain markup in both viewers, so nothing else in the suite would notice it
    disappearing during a restyle."""
    for name in ("viewer.template.html", "report.template.html"):
        text = _flatten(_scaffold(repo_root, name))
        assert re.search(r'href\s*=\s*"index\.html"', text), (
            f"{name} has no link back to index.html"
        )


@pytest.mark.parametrize("host,name", MAP_TEMPLATES)
def test_map_step6_writes_the_index_page(repo_root: Path, host: str, name: str) -> None:
    """Writing `index.json` and writing `index.html` are one step, not two.

    The scaffold ships to `.code-flow/` whether or not anything fills it, so
    without this the index page installs and stays inert — which is exactly the
    state this repository was in before the wiring landed. Scoped to the Step 6
    region for the usual reason: `index.html` is named in the viewers' back-link
    prose and in the README, so an unscoped search would pass with the
    instruction deleted.
    """
    text = (repo_root / "templates" / host / name).read_text(encoding="utf-8")
    region = _index_instructions_region(text)
    assert "index.html" in region, (
        f"{host}/{name} Step 6 never says to write index.html, so the registry "
        "would be updated with no page rendering it"
    )


@pytest.mark.parametrize("host,name", MAP_TEMPLATES)
def test_map_template_fills_the_index_scaffold(repo_root: Path, host: str, name: str) -> None:
    """Naming `index.html` is not the same as saying how to build it.

    The page is only self-contained because it is the shipped scaffold with one
    token substituted. A host that said "write index.html" without naming the
    template or the token would invite a hand-rolled page — which is how the
    single-file, no-network guarantee gets lost. Both names are unique to this
    instruction, so no region scoping is needed.
    """
    text = (repo_root / "templates" / host / name).read_text(encoding="utf-8")
    assert ".code-flow/index.template.html" in text, (
        f"{host}/{name} never tells the assistant to read the installed index scaffold"
    )
    assert "__INDEX_DATA__" in text, (
        f"{host}/{name} never names the token the registry is substituted into"
    )


@pytest.mark.parametrize("host,name", MAP_TEMPLATES)
def test_map_template_fills_the_flow_switcher_token(
    repo_root: Path, host: str, name: str
) -> None:
    """The flow viewer carries a second token, and only the map command can fill
    it. Nothing else in the suite ties the two ends together: the scaffold test
    above proves the token is safely contained when unreplaced, which is a
    passing state for a template no host ever fills."""
    text = (repo_root / "templates" / host / name).read_text(encoding="utf-8")
    assert "__FLOW_INDEX__" in text, (
        f"{host}/{name} never mentions __FLOW_INDEX__, so the flow switcher would "
        "be dead markup on every generated page"
    )


# --- Phase 5: --output and theme inlining -----------------------------------


@pytest.mark.parametrize("host,name", MAP_TEMPLATES)
def test_map_template_documents_the_output_flag(repo_root: Path, host: str, name: str) -> None:
    """`--output` is parsed in step 1 with the other flags, so it must be stated
    there — not only in whatever section describes the bundle.

    Scoped to step 1's own region for the same reason
    `test_map_template_documents_the_mode_flags` is: unscoped, the token would
    be satisfied by the bundle section further down, and deleting the flag from
    the place it is actually read would leave the assertion green.
    """
    text = (repo_root / "templates" / host / name).read_text(encoding="utf-8")
    region = _section_region(text, _STEP1_START, _STEP1_END)
    assert "files|bundle|both" in region, f"{host}/{name} step 1 never mentions --output"


@pytest.mark.parametrize("host,name", MAP_TEMPLATES + QUALITY_TEMPLATES)
def test_template_always_writes_the_json_artifacts(
    repo_root: Path, host: str, name: str
) -> None:
    """`--output bundle` suppresses pages, never data.

    `/code-flow.quality` reads `index.json`, `inventory.json` and the per-flow
    sidecars; a mode that skipped them would break it silently, and nothing else
    in this repository couples the two commands tightly enough to notice.
    Keyed on the literal clause every host must carry.
    """
    text = (repo_root / "templates" / host / name).read_text(encoding="utf-8")
    assert "never suppresses the JSON" in text, (
        f"{host}/{name} does not state that --output never suppresses the JSON artifacts"
    )


@pytest.mark.parametrize("host,name", MAP_TEMPLATES + QUALITY_TEMPLATES)
def test_template_inlines_the_theme(repo_root: Path, host: str, name: str) -> None:
    """Every page-writing step must fill `__THEME_CSS__`, and must not fail when
    `.code-flow/theme.css` is absent — an absent theme is the default state, not
    an error."""
    text = (repo_root / "templates" / host / name).read_text(encoding="utf-8")
    assert "__THEME_CSS__" in text, f"{host}/{name} never fills the theme token"
    assert re.search(r"theme\.css.{0,200}(does not exist|is absent|missing)", text, re.S), (
        f"{host}/{name} does not say what to do when theme.css is absent"
    )


# Marks the start of step 6d, "The bundle" — the step that writes
# `Code_Flows/code-flow.html` — in every host (Claude/Gemini:
# "**6d. The bundle.**"; Copilot: the "### The bundle" heading).
_BUNDLE_START = re.compile(r"\*\*6d\. The bundle\.\*\*|^### The bundle\s*$", re.MULTILINE)

# Marks the start of the *next* section after step 6d, in every host
# (Claude/Gemini: "#### 7. Finalize"; Copilot: "### Output Location"). Used as
# the end boundary so the region cannot run past 6d into unrelated text.
_BUNDLE_END = re.compile(r"\n(?:#### 7\.|### Output Location)")


def _bundle_region(text: str) -> str:
    return _section_region(text, _BUNDLE_START, _BUNDLE_END)


@pytest.mark.parametrize("host,name", MAP_TEMPLATES)
def test_map_template_inlines_the_theme_in_the_bundle_step(
    repo_root: Path, host: str, name: str
) -> None:
    """`test_template_inlines_the_theme` above is a whole-file check, and the
    theme-fallback sentence is independently restated three times in every map
    template — 5b, 6c, and 6d. That makes the whole-file check satisfiable by
    5b's or 6c's copy alone: deleting the sentence from 6d specifically — the
    bundle step, this task's own newest and least-reviewed addition — leaves
    the whole-file assertion green, so an unthemed bundle page could ship with
    no test failure to flag it.

    This companion assertion scopes to the 6d/bundle region specifically, the
    same way `test_map_template_documents_the_output_flag` scopes to step 1,
    so the bundle step's own copy of the rule has its own guard.
    """
    text = (repo_root / "templates" / host / name).read_text(encoding="utf-8")
    region = _bundle_region(text)
    assert "__THEME_CSS__" in region, (
        f"{host}/{name} step 6d (the bundle) never fills the theme token"
    )
    assert re.search(r"theme\.css.{0,200}(does not exist|is absent|missing)", region, re.S), (
        f"{host}/{name} step 6d (the bundle) does not say what to do when "
        f"theme.css is absent"
    )
