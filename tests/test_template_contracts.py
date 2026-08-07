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


def test_viewer_scaffold_has_exactly_one_token(repo_root: Path) -> None:
    text = (repo_root / "templates" / "shared" / "viewer.template.html").read_text(
        encoding="utf-8"
    )
    assert text.count("__FLOW_DATA__") == 1


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

DETECTOR_NAMES = (
    "duplicate-intent",
    "repeated-sequence",
    "complexity-hotspot",
    "unreached",
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


def _detector_header_pattern(detector: str) -> re.Pattern[str]:
    """Match ``detector`` where it *introduces its own rule paragraph* —
    immediately followed by its principle in parentheses (Claude/Gemini:
    "**a. duplicate-intent (DRY).**"; Copilot: "- **duplicate-intent
    (DRY)**").

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
    return re.compile(re.escape(detector) + r"\s*\(", re.IGNORECASE)


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_names_all_four_detectors(
    repo_root: Path, host: str, name: str
) -> None:
    region = _detectors_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    for detector in DETECTOR_NAMES:
        assert _detector_header_pattern(detector).search(region), (
            f"{host} detector step does not introduce {detector} with its principle"
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
    for field in ("flows", "metric", "value", "exported"):
        assert _field_reference(field).search(region), (
            f"{host} never names the evidence field {field!r}"
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

# Marks the start of the *next* section (Claude/Gemini: "#### 5. Write";
# Copilot: "5. **Write"). Needed because "verified" and "stale" both recur in
# the step 6 banner text.
_VERIFY_END = re.compile(r"\n(?:#### 5\.|5\.\s*\*\*Write)")


def _verify_region(text: str) -> str:
    return _section_region(text, _VERIFY_START, _VERIFY_END)


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
