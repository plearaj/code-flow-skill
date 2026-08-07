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
