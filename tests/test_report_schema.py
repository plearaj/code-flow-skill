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

PRINCIPLES = {"DRY", "KISS", "YAGNI"}
SEVERITIES = {"high", "medium", "low"}
CONFIDENCES = {"verified", "unverified"}
EFFORTS = {"small", "medium", "large"}
DETECTORS = {
    "duplicate-intent",
    "repeated-sequence",
    "complexity-hotspot",
    "unreached",
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

# Step 3: "Three detectors carry evidence the fields above have no home for.
# Add exactly these, and nothing else." Each detector not listed here
# (duplicate-intent) adds none.
EVIDENCE_FIELDS_BY_DETECTOR = {
    "duplicate-intent": frozenset(),
    "repeated-sequence": frozenset({"flows"}),
    "complexity-hotspot": frozenset({"metric", "value"}),
    "unreached": frozenset({"exported"}),
}
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

_ID = re.compile(r"^(DRY|KISS|YAGNI)-\d{2}$")


@pytest.fixture
def report(repo_root: Path) -> dict:
    return json.loads((repo_root / "examples" / "sample-report.json").read_text(encoding="utf-8"))


def test_report_has_the_four_top_level_keys(report: dict) -> None:
    assert set(report) == {"schema", "meta", "coverage", "findings"}
    assert report["schema"] == 1


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
    """
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
            assert site["snippet"], f"{finding['id']} site missing a snippet"


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
