"""The quality report's finding schema, made executable.

The schema is prose in three prompt templates, which means nothing checks that
anything obeys it — including the fixture this repository ships. This module
implements the constraints once and asserts the fixture meets them, so a change
to the schema that the fixture contradicts fails the suite instead of shipping.

This is the same move `tests/test_node_ids.py` makes for the node `id` rule,
and for the same reason: a contract that lives only in prompt prose is a
contract nothing enforces.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

PRINCIPLES = {"DRY", "KISS", "YAGNI", "SOLID", "DEPTH", "RULES"}
SEVERITIES = {"high", "medium", "low"}
CONFIDENCES = {"verified", "unverified"}
EFFORTS = {"small", "medium", "large"}
DETECTORS = {
    "duplicate-intent",
    "repeated-sequence",
    "complexity-hotspot",
    "unreached",
    "rule-violation",
    "single-responsibility",
    "interface-segregation",
    "dependency-cycle",
    "shallow-module",
    "pass-through",
    "internals-coupled-test",
    "open-closed",
    "liskov-substitution",
}
SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}

# The ten fields every finding carries, taken from the "Emit each finding in
# this shape" JSON example in step 3 of every host template — identical to
# `FINDING_FIELD_NAMES` in `tests/test_template_contracts.py`.
REQUIRED_FIELDS = {
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
}

# Step 3: "Most detectors carry evidence the fields above have no home for.
# Add exactly these, and nothing else." Each detector whose entry is empty
# (duplicate-intent) adds none.
EVIDENCE_FIELDS_BY_DETECTOR = {
    "duplicate-intent": frozenset(),
    # `variants` and `occurrences` carry the collapse: every chain sharing a pair
    # of endpoints is one finding, so the row has to say how many chains it
    # stands for or four restatements of one fact read as one fact. Both are
    # unconditional — a group of one carries its single interior and a count of
    # 1, so no reader has to tell a missing field from a count of one.
    "repeated-sequence": frozenset({"flows", "variants", "occurrences"}),
    # `alsoTripped` carries the thresholds this function exceeded besides the one
    # in `metric`. The three are joined by `or`, so a function can trip all of
    # them and is then the worst function in the report — one thing to simplify
    # at one `file:line`, not three findings. Unconditional: an empty array says
    # "tripped once", which a missing field cannot.
    "complexity-hotspot": frozenset({"metric", "value", "alsoTripped"}),
    # `reachedBy` is what gives `production-unreached` a home in the JSON. Both
    # outcomes emit `detector: "unreached"` with different severity rules, and
    # before this field the distinction survived only in `title`/`rationale`
    # prose — unassertable here, and unrenderable by the phase 3b viewer that
    # will consume this same JSON.
    "unreached": frozenset({"exported", "reachedBy"}),
    # A rule-violation finding rests on a sentence somebody wrote down, so it
    # carries that sentence and where it came from. Without `rule` and
    # `ruleSource` a reader cannot tell a real violation from a misreading of
    # the rule, which is the failure mode this detector is most exposed to.
    "rule-violation": frozenset({"rule", "ruleId", "ruleSource"}),
    # The SOLID and DEPTH detectors each claim something about a whole file, so
    # each carries the file (`module`) and the numbers its own threshold was
    # applied to. Without them a reader can see the cited functions but not the
    # measurement the finding rests on, which is the same gap `metric`/`value`
    # closed for complexity-hotspot.
    "single-responsibility": frozenset({"module", "dependencies", "dependents"}),
    "interface-segregation": frozenset(
        {"module", "exports", "consumers", "widestConsumerUse"}
    ),
    # `cycle` is the ring itself. It is the one piece of evidence that cannot be
    # reconstructed from the sites: the sites say which functions carry the
    # edges, not what order the edges close in.
    # `cycle` is one ring; `cycleCount` says how many the component holds. A knot
    # of five mutually-reaching modules contains dozens of simple cycles and one
    # problem, so the finding is per strongly connected component and the count
    # is what tells a reader the cited ring is an exemplar rather than the whole
    # of it.
    "dependency-cycle": frozenset({"cycle", "cycleCount"}),
    "shallow-module": frozenset({"module", "interface", "hiddenLoc"}),
    "pass-through": frozenset({"module"}),
    "internals-coupled-test": frozenset({"module", "internals"}),
    # The two detectors whose evidence is never in the map. `switchPoint` is the
    # place a new variant has to edit, and `weakened` is the subset of the family
    # the verify pass actually confirmed narrows the contract — not the whole
    # family, which is why it is a field of its own rather than a slice of
    # `sites`.
    "open-closed": frozenset({"variants", "switchPoint"}),
    "liskov-substitution": frozenset({"family", "familyFrom", "weakened"}),
}

# Step 3: `reachedBy` has exactly two values. `"tests"` is the
# `production-unreached` case.
REACHED_BY = {"none", "tests"}
ALL_EVIDENCE_FIELDS = frozenset.union(*EVIDENCE_FIELDS_BY_DETECTOR.values())

# Whole-word only, per review: "deleting", "removal" or "delete_export()" are
# not required to match, but a bare "Delete." or "Remove the caller" must.
_INSTRUCTS_DELETION = re.compile(r"\b(delete|remove|drop)\b", re.IGNORECASE)

# A Windows drive-letter absolute path ("C:/..." or "C:\\..."). `meta.root` is
# the one absolute path the schema permits; every `sites[].file` must be
# repo-relative, and on the project's own development platform (Windows) a
# drive-letter path is the realistic shape of a violation — a leading "/"
# check alone would miss it entirely.
_DRIVE_LETTER_PATH = re.compile(r"^[a-zA-Z]:[\\/]")

_ID = re.compile(r"^(DRY|KISS|YAGNI|SOLID|DEPTH|RULES)-\d{2}$")


# Every example report this repository ships. The fixture below is
# parametrized over all of them, so each test in this module runs once per
# file.
#
# Two fixtures, not one, and they are deliberately complementary. With only
# `sample-report.json` (`readCode: true`, every finding `verified`,
# `detectorsSkipped: []`, `mapDetail: "standard"`),
# `test_confidence_is_never_verified_without_read_code` was guarded by
# `if not report["meta"]["readCode"]` and its **entire body never executed** —
# the second dead assertion found in this phase. `sample-report-unverified.json`
# is the mirror state: a thin map read without `--read-code`, which is exactly
# the state step 2 describes when it skips duplicate-intent, so its
# `detectorsSkipped` and `mapDetail` are consistent with each other and with
# that rule. It also closes the enum-coverage gap the first fixture left:
# `confidence: "unverified"`, `severity: "medium"`, `effort: "large"`,
# a non-empty `detectorsSkipped`, and both `reachedBy` values.
REPORT_FIXTURES = ("sample-report.json", "sample-report-unverified.json")


@pytest.fixture(params=REPORT_FIXTURES)
def report(request: pytest.FixtureRequest, repo_root: Path) -> dict:
    return json.loads(
        (repo_root / "examples" / request.param).read_text(encoding="utf-8")
    )


def test_report_has_the_five_top_level_keys(report: dict) -> None:
    """`rules` is present in every report, empty when `--rules` was not passed.
    Emitting it unconditionally is what stops a consumer having to know how the
    command was invoked before it can read the file."""
    assert set(report) == {"schema", "meta", "coverage", "findings", "rules"}
    assert report["schema"] == 1


def test_meta_carries_exactly_the_fields_step_5_names(report: dict) -> None:
    """`coverage`'s key set was asserted exactly; `meta`'s was not asserted at
    all, so deleting `mapGenerated`, `mapMode` and `mapDetail` from a fixture
    left the whole suite green — and those three are precisely the fields step 5
    says exist "so the report records which map it read"."""
    assert set(report["meta"]) == {
        "root",
        "generated",
        "readCode",
        "mapGenerated",
        "mapMode",
        "mapDetail",
    }


def test_meta_root_is_the_one_absolute_path(report: dict) -> None:
    """The Global Constraint reads "`meta.root` is the one absolute path". Only
    half of it was covered: `_DRIVE_LETTER_PATH` guarded `sites[].file` against
    being absolute, but nothing required `root` itself to *be* absolute. A
    fixture with `"root": "."` satisfied every other test in this module."""
    root = report["meta"]["root"]
    assert _DRIVE_LETTER_PATH.match(root) or root.startswith("/"), (
        f"meta.root {root!r} is not an absolute path"
    )


def test_coverage_carries_every_banner_number(report: dict) -> None:
    """Step 6's banner renders each of these. A fixture missing one would let a
    template drop it without any test noticing."""
    assert set(report["coverage"]) == {
        "flowsTraced",
        "entryPointsFound",
        "functionsCatalogued",
        "flowsUnreadable",
        "filesChanged",
        "findingsDropped",
        "detectorsSkipped",
        "rulesLoaded",
        "rulesChecked",
        "rulesNotCheckable",
    }


def test_findings_use_only_permitted_enum_values(report: dict) -> None:
    for finding in report["findings"]:
        assert finding["principle"] in PRINCIPLES
        assert finding["detector"] in DETECTORS
        assert finding["severity"] in SEVERITIES
        assert finding["confidence"] in CONFIDENCES
        assert finding["effort"] in EFFORTS


def test_finding_ids_match_their_principle_and_are_unique(report: dict) -> None:
    seen = set()
    for finding in report["findings"]:
        assert _ID.match(finding["id"]), f"malformed id {finding['id']!r}"
        assert finding["id"].split("-")[0] == finding["principle"]
        assert finding["id"] not in seen, f"duplicate id {finding['id']!r}"
        seen.add(finding["id"])


def test_finding_ids_restart_per_principle_as_a_contiguous_counter(report: dict) -> None:
    """Step 3: 'a two-digit counter that restarts per principle in emission
    order: DRY-01, DRY-02, KISS-01, YAGNI-01.' Format and uniqueness alone
    (the previous test) would pass `DRY-01, DRY-03`: nothing checked that the
    counter has no gaps, only that no two findings collide. This walks the
    findings in document order and requires each principle's own counter to
    read 1, 2, 3, ... with no skips."""
    counters: dict[str, int] = {}
    for finding in report["findings"]:
        principle = finding["principle"]
        suffix = int(finding["id"].split("-")[1])
        expected = counters.get(principle, 0) + 1
        assert suffix == expected, (
            f"{finding['id']}: expected counter {expected} for {principle}, "
            f"found {suffix} (a gap or an out-of-order restart)"
        )
        counters[principle] = suffix


def test_every_finding_carries_at_least_one_site(report: dict) -> None:
    """A finding without a site cites no evidence, and file:line evidence is
    the whole currency of this report.

    Every field the templates' shape example puts on a site — `file`, `line`,
    `symbol` and `snippet` — is checked here, not just the three the plan's
    draft of this test named. `snippet` is the one that draft omitted: a site
    missing it still satisfies "cites a location", but not the evidentiary
    bar the templates actually set (every site field is named as required by
    `test_quality_template_names_every_site_field` in
    `tests/test_template_contracts.py`), so a fixture with a snippet-less site
    would pass the loose form and still violate the schema.

    `file` is also checked against a Windows drive-letter absolute path, not
    just a leading `/` — the plan's draft form would pass a site citing
    `meta.root` itself as its file, which is exactly the shape a real
    violation would take on this project's own (Windows) development
    platform.

    `snippet` is required *conditionally*, and the condition is a rule rather
    than a convenience. A `thin` map carries no snippets at all, so a report
    written from one without `--read-code` has none to cite; step 4b's rule
    (added in this wave) says a candidate emitted without a snippet takes its
    sites' snippets from the source read there, so `--read-code` restores them
    and a `standard`/`verbose` map had them from the map. Both branches below
    execute: `sample-report.json` takes the first, `sample-report-unverified.json`
    the second.
    """
    snippets_available = report["meta"]["mapDetail"] != "thin" or report["meta"]["readCode"]
    for finding in report["findings"]:
        assert finding["sites"], f"{finding['id']} has no sites"
        for site in finding["sites"]:
            assert site["file"] and not site["file"].startswith("/")
            assert "\\" not in site["file"], "paths use forward slashes"
            assert not _DRIVE_LETTER_PATH.match(site["file"]), (
                f"{finding['id']} site {site['file']!r} is an absolute path; "
                "sites must be repo-relative"
            )
            assert isinstance(site["line"], int) and site["line"] > 0
            assert site["symbol"]
            if snippets_available:
                assert site["snippet"], f"{finding['id']} site missing a snippet"
            else:
                assert "snippet" not in site, (
                    f"{finding['id']} site carries a snippet, but this report was "
                    f"written from a thin map without --read-code, which has none"
                )


def test_findings_are_ordered_by_severity_then_site_count_then_principle(report: dict) -> None:
    """Step 5: order by severity descending, then site count descending, then
    `principle` alphabetically. The plan's draft key omitted `principle`
    entirely, which is vacuous for the third tiebreak: two findings tied on
    severity and site count compare equal under a two-field key regardless of
    which one is listed first, so a fixture (or a future one) placing a
    `KISS` finding ahead of an equally-ranked `DRY` finding would still pass."""
    keys = [
        (SEVERITY_RANK[f["severity"]], -len(f["sites"]), f["principle"])
        for f in report["findings"]
    ]
    assert keys == sorted(keys), "findings are not in the documented order"


def test_exported_unreached_findings_are_capped_at_low(report: dict) -> None:
    """A public API surface has callers this repository cannot see, so an
    exported symbol never reaches high severity."""
    for finding in report["findings"]:
        if finding["detector"] == "unreached" and finding.get("exported"):
            assert finding["severity"] == "low"


def test_reached_by_tests_findings_are_never_high(report: dict) -> None:
    """Step 3d: a `source` function reached only from test files is
    `production-unreached` — "kept alive only by its own tests" — and is never
    rated `high`, because something does reach it. `reachedBy: "tests"` is what
    carries that outcome in the JSON: both outcomes emit
    `detector: "unreached"`, so without this field the distinction lived only in
    prose and this rule could not be asserted at all.

    The value enum is checked here too. `reachedBy` has exactly two values, and
    a third would mean each run inventing its own spelling of the same state.
    """
    for finding in report["findings"]:
        if finding["detector"] != "unreached":
            continue
        assert finding["reachedBy"] in REACHED_BY, (
            f"{finding['id']} has reachedBy {finding['reachedBy']!r}, "
            f"expected one of {sorted(REACHED_BY)}"
        )
        if finding["reachedBy"] == "tests":
            assert finding["severity"] != "high", (
                f"{finding['id']} is reached by tests but rated high; "
                f"production-unreached is never high"
            )


def test_unreached_findings_never_instruct_deletion(report: dict) -> None:
    """Parser-free tracing cannot see dynamic dispatch, so these are candidates
    and never verdicts.

    Checks whole-word `delete`, `remove` and `drop` rather than the substring
    `"delete "` (trailing space and all) the plan's draft used: that form
    admits `"Delete."` (no trailing space), and never considered `"remove"`
    or `"drop"` as synonyms for the same instruction at all.
    """
    for finding in report["findings"]:
        if finding["detector"] == "unreached":
            assert "confirm before deleting" in finding["rationale"].lower()
            assert not _INSTRUCTS_DELETION.search(finding["suggestion"]), (
                f"{finding['id']} suggestion instructs deletion: "
                f"{finding['suggestion']!r}"
            )


def test_confidence_is_never_verified_without_read_code(report: dict) -> None:
    """Step 4b: without `--read-code`, every finding keeps `confidence:
    "unverified"` — a finding cannot be `verified` unless the flag ran and
    confirmed it. This is one-directional only. The reverse does not hold:
    step 4b also has a branch (added after Task 6 review) for a candidate
    whose cited file cannot be reopened at all, deleted or unreadable, which
    stays `unverified` even under `readCode: true` and falls through to be
    dropped as stale by step 4c — that is what makes `findingsDropped`
    meaningfully nonzero under `--read-code` (step 4's own text hedges "under
    `--read-code` the dropped count is usually zero", not always). So this
    test does not assert the converse ("readCode true implies every finding
    is verified"); an earlier version of this module did, and it was wrong.
    """
    if not report["meta"]["readCode"]:
        for finding in report["findings"]:
            assert finding["confidence"] != "verified", (
                f"{finding['id']} is verified but meta.readCode is false"
            )


def test_findings_carry_every_required_field(report: dict) -> None:
    """`title` was previously referenced by no test at all — deleting it from
    every finding and from the fixture left the whole suite green. This checks
    all ten schema fields (`REQUIRED_FIELDS`) are present on every finding,
    not just the handful individual tests happen to read."""
    for finding in report["findings"]:
        missing = REQUIRED_FIELDS - set(finding)
        assert not missing, f"{finding.get('id')} is missing fields {missing}"


def test_findings_carry_exactly_their_detectors_evidence_fields(report: dict) -> None:
    """Step 3: 'Add exactly these, and nothing else.' Previously `exported`
    was read with `.get()` (so a missing `exported` on an `unreached` finding
    would silently pass) and `flows`/`metric`/`value` were never referenced by
    any test at all — deleting `"flows"` from the `repeated-sequence` finding
    left the suite green. This requires each finding to carry precisely the
    evidence fields its own detector adds, and none of another detector's."""
    for finding in report["findings"]:
        detector = finding["detector"]
        required = EVIDENCE_FIELDS_BY_DETECTOR[detector]
        present = set(finding) & ALL_EVIDENCE_FIELDS
        assert present == required, (
            f"{finding['id']} ({detector}) carries evidence fields {sorted(present)}, "
            f"expected exactly {sorted(required)}"
        )


# --- the rules array -------------------------------------------------------


RULE_FIELDS = {"ruleId", "text", "source", "severity", "checkable", "reason"}


def test_every_loaded_rule_carries_the_fields_step_2_records(report: dict) -> None:
    """A rule the report cannot show is a rule the reader has to take on trust,
    and this detector's whole claim is that it cites the project's own words."""
    for rule in report["rules"]:
        assert set(rule) == RULE_FIELDS, f"{rule.get('ruleId')} has fields {sorted(rule)}"
        assert rule["text"].strip(), f"{rule['ruleId']} has no text"
        assert rule["severity"] in SEVERITIES
        assert isinstance(rule["checkable"], bool)


def test_a_rule_that_could_not_be_checked_says_why(report: dict) -> None:
    """Step 2: a not-checkable rule is reported as not-checked, never as
    passing. A reason-less one is indistinguishable from a clean one."""
    for rule in report["rules"]:
        if not rule["checkable"]:
            assert rule["reason"].strip(), (
                f"{rule['ruleId']} is not checkable but gives no reason, so the "
                f"report cannot tell a reader why it was not checked"
            )


def test_the_rule_counts_reconcile_with_the_rules_array(report: dict) -> None:
    """Three numbers in the banner, one array they describe. A banner that
    disagrees with its own evidence is worse than no banner."""
    coverage = report["coverage"]
    rules = report["rules"]
    assert coverage["rulesLoaded"] == len(rules)
    assert coverage["rulesChecked"] == sum(1 for rule in rules if rule["checkable"])
    assert coverage["rulesNotCheckable"] == sum(1 for rule in rules if not rule["checkable"])


def test_every_rule_violation_finding_cites_a_loaded_rule(report: dict) -> None:
    """`ruleId` is the join between a finding and the sentence it rests on. A
    finding naming a rule the report never loaded is a finding whose evidence
    the reader cannot reach — and the most likely way to produce one is to
    invent the rule, which step 3 forbids outright."""
    loaded = {rule["ruleId"] for rule in report["rules"]}
    for finding in report["findings"]:
        if finding["detector"] != "rule-violation":
            continue
        assert finding["ruleId"] in loaded, (
            f"{finding['id']} cites {finding['ruleId']}, which is not in `rules`"
        )
        cited = next(rule for rule in report["rules"] if rule["ruleId"] == finding["ruleId"])
        assert finding["rule"] == cited["text"], (
            f"{finding['id']} quotes the rule differently from `rules` — the "
            f"finding must carry the rule as loaded, not a paraphrase of it"
        )
        assert finding["ruleSource"] == cited["source"]
        assert finding["severity"] == cited["severity"], (
            f"{finding['id']} rates {finding['severity']} where its rule is "
            f"{cited['severity']}: the rule's wording decides the severity"
        )
