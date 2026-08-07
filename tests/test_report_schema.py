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
    """
    for finding in report["findings"]:
        assert finding["sites"], f"{finding['id']} has no sites"
        for site in finding["sites"]:
            assert site["file"] and not site["file"].startswith("/")
            assert "\\" not in site["file"], "paths use forward slashes"
            assert isinstance(site["line"], int) and site["line"] > 0
            assert site["symbol"]
            assert site["snippet"], f"{finding['id']} site missing a snippet"


def test_findings_are_ordered_by_severity_then_site_count(report: dict) -> None:
    keys = [
        (SEVERITY_RANK[f["severity"]], -len(f["sites"]))
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
    and never verdicts."""
    for finding in report["findings"]:
        if finding["detector"] == "unreached":
            assert "confirm before deleting" in finding["rationale"].lower()
            assert "delete " not in finding["suggestion"].lower()


def test_confidence_matches_read_code_mode(report: dict) -> None:
    """Task 4's verify step is all-or-nothing, not per-finding: with
    `--read-code`, every candidate is either confirmed (`verified`) or dropped
    outright — none stay `unverified`. Without the flag, every finding keeps
    `unverified`. A report can never legitimately mix the two values, so a
    fixture doing so would ship a self-contradicting example of the very rule
    this test guards, and the plan's enum-membership check alone would not
    catch it (`unverified` and `verified` are both individually permitted
    values)."""
    expected = "verified" if report["meta"]["readCode"] else "unverified"
    for finding in report["findings"]:
        assert finding["confidence"] == expected, (
            f"{finding['id']} is {finding['confidence']!r} but meta.readCode="
            f"{report['meta']['readCode']!r} implies every finding should be "
            f"{expected!r}"
        )
