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
   The other three detectors are unaffected and still run.
   `coverage.flowsTraced` below `coverage.entryPointsFound` is **not** a stop
   condition; it is a partial trace pass, which is normal on a large repository.
3. **Run the detectors.** Four of them; step 2's gating rule already decided which
   run. Every severity is a **rule**, not a judgement — apply the number, and if a
   finding does not clear a threshold it is not a finding at all.
   - **duplicate-intent (DRY)** — cluster catalogued functions that do the same
     work under different names or places. Compare `purpose` and `signature`
     across the whole inventory, and `snippet` wherever the map carries one.
     `high` at 3 sites, or when the duplicated code totals at least 40 lines;
     otherwise `medium`. Cite every site with its snippet.
   - **repeated-sequence (DRY)** — chains of at least 3 consecutive calls appearing
     in at least 2 flows. `high` at that threshold; shorter or rarer is not a
     finding. Cite the shared subpath and every flow `slug` it appears in.
   - **complexity-hotspot (KISS)** — per node, fan-out (outbound edges) and depth
     (distance from that flow's `entry`). `high` at fan-out 8, depth 6, or `loc`
     120; otherwise `medium`. Cite the metric that tripped and its value.
   - **unreached (YAGNI)** — subtract: every inventory `id` appearing as a node
     `id` in any flow is reached, and the join is exact because the map derives
     both by the same rule, so do not match on names. A `role` of `test` is never
     a finding. A `role` of `source` reached by no flow and no test is `unreached`.
     A `role` of `source` reached only from test files is `production-unreached` —
     phrase it "kept alive only by its own tests"; never rate it `high`, otherwise
     `medium`. `high` only when `unreached`, not `exported`, and not test-only;
     anything whose `exported` is true is capped at `low`, because a public API
     surface has callers this repository cannot see.

   **unreached is a candidate, never a verdict.** Tracing is search and reading,
   not a compiler's view: it cannot see reflection, `getattr`, dependency
   injection, framework hooks, decorator registration, or entry points declared in
   configuration. Phrase each as "not reached by any of the N mapped flows —
   confirm before deleting", N being the flows actually analyzed. The report never
   instructs deletion.

   **One cluster, one finding** — several `sites` on one finding, never one finding
   per pair. Three copies of a helper is one finding with three sites.

   Emit each finding in this shape:

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

   `principle` is `DRY`, `KISS` or `YAGNI`; `severity` is `high`, `medium` or
   `low`; `confidence` is `unverified` unless step 4 verified it; `effort` is
   `small`, `medium` or `large`. `id` is the principle, a hyphen, and a two-digit
   counter restarting per principle in emission order. Ids must be stable within
   the run — the markdown and the JSON cross-reference each other by them.

   Three detectors carry evidence those fields have no home for. Add exactly
   these, and nothing else: `repeated-sequence` adds `flows` (the array of flow
   `slug`s the chain appears in); `complexity-hotspot` adds `metric` (`fan-out`,
   `depth` or `loc`) and `value`; `unreached` adds `exported`, copied from the
   inventory entry.
4. **Verify against source.** Two things, and their order matters.
   - **Check staleness.** For every file cited by a candidate finding, compare its
     current content against the `hash` recorded in `index.json`'s `files` array,
     and count how many mapped files no longer match — that count goes in the step 6
     banner. Staleness is **never a reason to stop the command**; there is no
     threshold, because any threshold would be a number this design cannot justify.
   - **Verify, if `--read-code` was passed.** This verifies candidates and is **not
     a second scan of the repository** — do not re-scan, since scanning everything
     again would duplicate the cost of mapping and not fit on a large codebase.
     Open **only the files the candidate findings cite**, confirm or drop each
     against real current source, set surviving candidates' `confidence` to
     `verified` and **correct their sites' `line` numbers to where the code is
     now** — `file` stays forward-slash and repo-relative, exactly as the map
     recorded it — and drop the rest. Without the flag every finding stays
     `unverified`.
   - **Drop what is left stale and unverified.** Verify first, then drop: any
     finding still `unverified` whose `sites` cite a file whose `hash` no longer
     matches is dropped and counted for the banner, because its `file:line`
     evidence is known wrong and `file:line` evidence is this report's whole
     currency. A `verified` finding is **never** dropped for staleness — it was
     confirmed against the very change that made the file stale, so dropping it
     would discard the best evidence in the report. Under `--read-code` the dropped
     count is usually zero.
