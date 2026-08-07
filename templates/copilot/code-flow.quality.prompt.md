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
     banner. A file that cannot be read at all, whatever the reason, counts as
     changed for this comparison. Staleness is **never a reason to stop the
     command**; there is no threshold, because any threshold would be a number this
     design cannot justify.
   - **Verify, if `--read-code` was passed.** This verifies candidates and is **not
     a second scan of the repository** — do not re-scan, since scanning everything
     again would duplicate the cost of mapping and not fit on a large codebase.
     Open **only the files the candidate findings cite**, confirm or drop each
     against real current source, set surviving candidates' `confidence` to
     `verified` and **correct their sites' `line` numbers to where the code is
     now** — `file` stays forward-slash and repo-relative, exactly as the map
     recorded it — and drop the rest. A candidate whose cited file cannot be
     opened at all — deleted, or unreadable — is neither confirmed nor dropped
     here: it keeps `confidence: "unverified"` and falls through to the
     staleness rule below. Without the flag every finding stays `unverified`.
   - **Drop what is left stale and unverified.** Verify first, then drop: any
     finding still `unverified` whose `sites` cite a file whose `hash` no longer
     matches is dropped and counted for the banner — the whole finding, not just
     that site, since a finding is only as trustworthy as its weakest citation and
     one stale site among several drops all of it. Its `file:line` evidence is
     known wrong and `file:line` evidence is this report's whole currency. A
     `verified` finding is **never** dropped for staleness — it was
     confirmed against the very change that made the file stale, so dropping it
     would discard the best evidence in the report. Under `--read-code` the dropped
     count is usually zero.
5. **Write the report data.** Write `Code_Flows/quality-report.json` **first** — it
   is the data, and step 6's markdown is one rendering of it; writing the markdown
   first would make them two independent transcriptions free to disagree. Order
   `findings` by `severity` descending (`high`, `medium`, `low`), then site count
   descending, then `principle` alphabetically — the order the step 3 ids must
   already reflect within each principle.

   ```json
   {
     "schema": 1,
     "meta": { "root": "C:/Users/example/project", "generated": "2026-08-07",
               "readCode": false, "mapGenerated": "2026-08-06",
               "mapMode": "whole-code-base", "mapDetail": "standard" },
     "coverage": { "flowsTraced": 14, "entryPointsFound": 17,
                   "functionsCatalogued": 1180, "flowsUnreadable": 0,
                   "filesChanged": 6, "findingsDropped": 2,
                   "detectorsSkipped": ["duplicate-intent"] },
     "findings": []
   }
   ```

   `meta.root` is the one absolute path; every path inside `findings` is
   repo-relative with forward slashes. `mapGenerated`, `mapMode` and `mapDetail`
   are copied from the map's own `index.json` `meta`, so the report records which
   map it read. `detectorsSkipped` lists the detectors step 2 gated off, and is an
   empty array when all four ran.

6. **Write the report.** Render `Code_Flows/quality-report.md` from that JSON;
   nothing in it may contradict that file. **Lead with coverage — a requirement,
   not a formatting preference:** the first thing under the title states how many
   of `entryPointsFound` entry points were traced (`flowsTraced`), how many
   functions were catalogued, how many flows were unreadable, how many mapped files
   have changed since mapping, how many findings were dropped as stale, and which
   detectors were skipped and why. If `flowsTraced` is below `entryPointsFound`,
   say in words that the map is partial and that everything below is **clean within
   what was mapped** — never a clean bill of health for the repository. Then a
   summary count by principle and severity, then findings grouped by principle,
   each rendering `id`, `title`, `severity`, `confidence`, `rationale`, a sites
   table of `file:line` and `symbol`, `suggestion`, and `effort`. **If there are no
   findings, still write the report:** say so and repeat the coverage banner
   immediately after, because an empty report under partial coverage means the
   mapped portion was clean and must not imply a clean bill of health. Say
   **"catalogued"**, never "all" — the map came from search and reading, not an AST
   walk. Finally, report both file paths to the user with the coverage numbers and
   the count of findings by severity.
