---
description: Report DRY, KISS and YAGNI findings from the persisted code-flow map, with file:line evidence and honest coverage.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Code Flow — Quality Report

Read the map this project has already written under `Code_Flows/` and report where
it shows duplicated intent, needless complexity, and code that nothing reaches.

This command **never edits source code.** `code-flow.map` adds missing docstrings
as it traces; this one writes documents and stops. Consolidating duplicates and
deleting suspected-dead code carry real blast radius, and that call is the user's.

### Instructions

Follow these steps exactly.

#### 1. Read the Arguments

The user's input (`$ARGUMENTS`) carries at most one flag:

- `--read-code` — after deriving candidate findings from the map, open the files
  those candidates cite and confirm each against current source. Off by default.
  It requires the source tree to be present and current, not merely the artifacts
  under `Code_Flows/`.

There is no feature name to parse: this command analyzes the whole map. If the
input contains anything else, say what you read, ignore it, and carry on — do not
treat it as a filter, a path, or a flow name.

#### 2. Load the Map

Read three kinds of artifact, in this order. Each detector in step 3 draws on
some of them, and which ones are readable decides which detectors run.

1. `Code_Flows/index.json` — coverage, the file census, and the flow registry.
2. `Code_Flows/inventory.json` — the function catalog.
3. `Code_Flows/<slug>.json` — one per entry in the index's `flows` array.

**The gating rule, which governs everything below:** a detector that cannot
produce its required evidence does not run, and the report names it and says why.
Never substitute a weaker signal for a missing one — a finding derived from
evidence the map does not contain is exactly the confident-wrong finding that
costs more trust than a missing one.

**If `Code_Flows/index.json` is absent**, stop. Tell the user to run
`/code-flow.map` first. There is no map to analyze.

**If `Code_Flows/inventory.json` is absent**, stop. Tell the user to run
`/code-flow.map --whole-code-base` first. Two of the four detectors —
duplicate-intent and unreached — need the catalog and cannot run without it. Do
not fall back to reporting only the other two: half the detectors missing is not
a degraded report, it is a different report, and one whose meaning would change
depending on how the user happened to build their map.

**If `Code_Flows/index.json` or `Code_Flows/inventory.json` exists but does not
parse as JSON**, stop. Report the file path and what is wrong with it, and let the
user repair or delete it. Do not overwrite either file — this command never
writes them, and a file it cannot parse is a file it cannot analyze.

**If a `Code_Flows/<slug>.json` named in the registry is missing or does not
parse**, do not stop. Skip that flow, count it, and report the count with the
coverage banner in step 6. The other flows are still analyzable, and one bad
sidecar is a fact about the map rather than a reason to abandon it.

**If `meta.detail` is `thin` and the user did not pass `--read-code`**, skip the
duplicate-intent detector. A thin map carries no `snippet`, so that detector has
only names, signatures and line counts — not enough to cite the evidence its
findings require. Record it as skipped and name both remedies: re-run with
`--read-code`, or re-map with `/code-flow.map --whole-code-base --detail standard`.
The other three detectors are unaffected and still run.

Note what is *not* a stop condition. `coverage.flowsTraced` below
`coverage.entryPointsFound` means the trace pass never finished, and that is
normal on a large repository. Analyze what was traced and let the banner in step 6
say how much that was.

#### 3. Run the Detectors

Four detectors. Step 2's gating rule has already decided which of them run; run
those, and only those.

Every severity below is a **rule**, not a judgement. Apply the number. If a
finding does not clear a threshold, it is not a finding of lower severity — it is
not a finding.

**a. duplicate-intent (DRY).** Cluster catalogued functions that do the same work
under different names or in different places. Compare `purpose` and `signature`
across the whole inventory, and `snippet` wherever the map carries one. Severity
is `high` when a cluster has at least 3 sites, or when the duplicated code totals
at least 40 lines; otherwise `medium`. Cite every site, with its snippet.

**b. repeated-sequence (DRY).** Across the flow graphs, find chains of at least
3 consecutive calls that appear in at least 2 different flows. Severity is `high`
at that threshold; a shorter chain, or one appearing in only 1 flow, is not a
finding. Cite the shared subpath and the `slug` of every flow it appears in.

**c. complexity-hotspot (KISS).** For each node across the flow graphs, take its
fan-out (its count of outbound edges) and its depth (its distance from that flow's
`entry` node). Severity is `high` when fan-out is at least 8, or depth is at least
6, or the function's `loc` is at least 120; otherwise `medium`. Cite the metric
that tripped and its value.

**d. unreached (YAGNI).** Subtract. Every inventory `id` that appears as a node
`id` in any flow is reached; what remains is not. The join is exact — the map
derives both ids by the same rule — so do not match on names. Then split what
remains by `role`:

- A `role` of `test` is never a finding. A test helper reached only by tests is
  doing its job.
- A `role` of `source` reached by no flow and by no test file is `unreached`: a
  dead-code candidate.
- A `role` of `source` reached only from test files is `production-unreached`.
  Phrase it "kept alive only by its own tests"; never rate it `high` —
  otherwise `medium`.

Severity is `high` only when the entry is `unreached`, is not `exported`, and is
not test-only. Anything whose `exported` is true is capped at `low`, because a
public API surface has callers this repository cannot see.

**unreached is a candidate, never a verdict.** Tracing here is search and reading,
not a compiler's view: it cannot see reflection, `getattr`, dependency injection,
framework hooks, decorator registration, or entry points declared in
configuration. Phrase every one of these findings as "not reached by any of the N
mapped flows — confirm before deleting", with N the number of flows actually
analyzed. The report never instructs deletion.

**One cluster, one finding.** Sites belonging to the same cluster produce a single
finding carrying several `sites` — never one finding per pair. Three copies of a
helper is one finding with three sites, not three findings.

**Emit each finding in this shape:**

```json
{
  "id": "DRY-01",
  "principle": "DRY",
  "detector": "duplicate-intent",
  "severity": "high",
  "confidence": "unverified",
  "title": "Email validation implemented in 3 places",
  "rationale": "Three functions independently validate email format with equivalent logic.",
  "sites": [
    { "file": "src/auth/validators.py", "line": 12, "symbol": "validate_email",
      "snippet": "def validate_email(value):\n    ..." }
  ],
  "suggestion": "Consolidate into one helper and have the other two call it.",
  "effort": "small"
}
```

`principle` is `DRY`, `KISS` or `YAGNI`. `severity` is `high`, `medium` or `low`.
`confidence` is `unverified` unless step 4 verified the finding. `effort` is
`small`, `medium` or `large`. `id` is the principle, a hyphen, and a two-digit
counter that restarts per principle in emission order: `DRY-01`, `DRY-02`,
`KISS-01`, `YAGNI-01`. Ids must be stable within the run, because the markdown and
the JSON cross-reference each other by them.

Three detectors carry evidence the fields above have no home for. Add exactly
these, and nothing else:

- `repeated-sequence` adds `flows` — the array of flow `slug`s the chain appears in.
- `complexity-hotspot` adds `metric` (`fan-out`, `depth` or `loc`) and `value`.
- `unreached` adds `exported`, copied from the inventory entry.
