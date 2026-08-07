---
mode: agent
description: Report DRY, KISS and YAGNI findings from the persisted code-flow map, with file:line evidence and honest coverage.
---

Read the map this project has already written under `Code_Flows/` and report where
it shows duplicated intent, needless complexity, and code that nothing reaches.

This command **never edits source code.** `code-flow.map` adds missing docstrings
as it traces; this one writes documents and stops. Consolidating duplicates and
deleting suspected-dead code carry real blast radius, and that call is the user's.

Follow these steps exactly:

1. **Read the arguments.** At most one flag: `--read-code` — after deriving
   candidate findings from the map, open the files those candidates cite and
   confirm each against current source. Off by default. It requires the source
   tree to be present and current, not merely the artifacts under `Code_Flows/`.
   There is no feature name to parse: this command analyzes the whole map. If the
   input contains anything else, say what you read, ignore it, and carry on — do
   not treat it as a filter, a path, or a flow name.
2. **Load the map.** Read `Code_Flows/index.json` (coverage, file census, flow
   registry), then `Code_Flows/inventory.json` (the function catalog), then each
   `Code_Flows/<slug>.json` named in the index's `flows` array. **The gating rule,
   which governs everything below:** a detector that cannot produce its required
   evidence does not run, and the report names it and says why — never substitute
   a weaker signal for a missing one. If `index.json` is absent, **stop** and tell
   the user to run `/code-flow.map` first. If `inventory.json` is absent, **stop**
   and tell the user to run `/code-flow.map --whole-code-base` first: duplicate-intent
   and unreached both need the catalog, and reporting only the other two would make
   the report mean something different depending on how the user built their map.
   If either file exists but does not parse as JSON, **stop**, report the path and
   the problem, and do not overwrite it — this command never writes those files. If
   a `<slug>.json` named in the registry is missing or does not parse, do **not**
   stop: skip that flow, count it, and report the count with the coverage banner in
   step 6. If `meta.detail` is `thin` and `--read-code` was not passed, skip the
   duplicate-intent detector — a thin map carries no `snippet` and that detector
   cannot cite the evidence its findings require — and name both remedies: re-run
   with `--read-code`, or re-map with `/code-flow.map --whole-code-base --detail standard`.
   `coverage.flowsTraced` below `coverage.entryPointsFound` is **not** a stop
   condition; it is a partial trace pass, which is normal on a large repository.
