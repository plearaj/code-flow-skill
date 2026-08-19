---
agent: agent
description: Report DRY, KISS and YAGNI findings, plus violations of rules the project has already written down, from the persisted code-flow map, with file:line evidence and honest coverage.
---

Read the map this project has already written under `Code_Flows/` and report where
it shows duplicated intent, needless complexity, and code that nothing reaches.

This command **never edits source code.** `code-flow.map` adds missing docstrings
as it traces; this one writes documents and stops. Consolidating duplicates and
deleting suspected-dead code carry real blast radius, and that call is the user's.

Follow these steps exactly:

1. **Read the arguments.** Two optional flags. `--read-code` — after deriving
   candidate findings from the map, open the files those candidates cite and
   confirm each against current source. Off by default. It requires the source
   tree to be present and current, not merely the artifacts under `Code_Flows/`.
   `--rules [source ...]` — also check the map against rules this project has
   already written down. Off by default. A source is a path to a document, the
   word `auto`, or a rule written inline in quotes; several may be given,
   separated by spaces or commas, and `--rules` with no value means `auto`. Step 2
   loads them and step 3's fifth detector checks them. This is how a project's own
   standard — a `CLAUDE.md`, an `AGENTS.md`, a Spec Kit constitution, a team style
   guide — gets reported with the same evidence and the same honesty as DRY, KISS
   and YAGNI, instead of being a thing everyone agreed to and nobody checks.
   There is no feature name to parse: this command analyzes the whole map. If the
   input contains anything else, say what you read, ignore it, and carry on — do
   not treat it as a filter, a path, or a flow name.
2. **Load the map.** Read `Code_Flows/index.json` (coverage, file census, flow
   registry), then `Code_Flows/inventory.json` (the function catalog), then each
   `Code_Flows/<slug>.json` named in the index's `flows` array. However
   `/code-flow.map` was run, these three exist: **`--output` never suppresses the JSON artifacts** —
   `index.json`, `<functionality_name>.json` and `inventory.json` are written
   in every mode, including `bundle`, because this command depends on them.
   **The gating rule,
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

   **Load the rules, if `--rules` was passed** — skip all of this when it was not:
   an unrequested detector is not a gap, and it is never listed as skipped. A
   source that names a readable file is a rule document; one that is not a
   readable path is an inline rule. `auto` means look for these, in order, and use
   every one that exists: `CLAUDE.md`, `.claude/CLAUDE.md`, `AGENTS.md`,
   `GEMINI.md`, `.github/copilot-instructions.md`,
   `.specify/memory/constitution.md`, `memory/constitution.md`, `CONVENTIONS.md`,
   `.code-flow/rules.md`. Split each document into discrete rules — one rule is one
   statement a reader could be shown a counter-example to; a heading, a rationale
   or an example is not one — and record for each a `ruleId` (`R-01`, `R-02`,
   counting across all sources), its `text` quoted rather than paraphrased, its
   `source` as `file:line`, its `severity` from its own wording (`must`, `never`,
   `always`, `required`, `do not` mean `high`; `should`, `prefer`, `avoid`,
   `expected` mean `medium`; `consider`, `may`, `where possible`, `ideally` mean
   `low`; no such word means `medium`), and whether it is `checkable` — whether the
   map carries the evidence it needs. Naming, file placement, layering,
   duplication, function size, docstring presence, dependency direction and what
   may call what are checkable against the inventory and the flow graphs; runtime
   behavior, review process, commit messages, dependency licences, CI
   configuration and the intent behind a design are not, and each of those records
   why in one clause. **Say what you did not check:** a not-checkable rule is
   reported as not-checked in step 6, never as passing and never silently dropped.
   If `--rules` was passed and no source could be read, do **not** stop: skip the
   rule-violation detector, record it in `detectorsSkipped`, and name every path
   you tried.
3. **Run the detectors.** Four of them, and a fifth when `--rules` was passed; step 2's gating rule already decided which
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
     a finding. A `role` of `source` reached by no flow and no test is `unreached`,
     and carries `reachedBy: "none"`. A `role` of `source` reached only from test
     files is `production-unreached`, and carries `reachedBy: "tests"` —
     phrase it "kept alive only by its own tests"; never rate it `high`, otherwise
     `medium`. `high` only when `unreached`, not `exported`, and not test-only;
     anything whose `exported` is true is capped at `low`, because a public API
     surface has callers this repository cannot see.

   - **rule-violation (RULES)** — runs only when step 2 loaded at least one rule.
     For each rule marked `checkable`, search the inventory and the flow graphs for
     evidence that contradicts it, and cite that evidence as every other detector
     does: `file`, `line`, `symbol`, snippet where the map carries one. Severity is
     the rule's own severity from step 2 — its wording decided it, not you. One
     rule is one finding, however many sites break it. A rule with no violating
     site is not a finding: it is reported as checked and clean in the banner,
     which is the only place a reader can tell "checked, clean" from "never
     checked". Every finding here carries `rule` (the text, quoted), `ruleId` and
     `ruleSource`, so a reader can go and read the sentence it rests on; a finding
     resting on your reading of the project's intent rather than its written words
     is not a finding — drop it.

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
   counter restarting per principle: `DRY-01`, `DRY-02`, `KISS-01`, `YAGNI-01`.
   **The counter is assigned in step 5, after step 4's drops** — not here — so do
   not number findings as you emit them, and read the `DRY-01` above as the shape
   rather than as a number already spent. Once assigned, ids are stable within
   the run — the markdown and the JSON cross-reference each other by them.

   Three detectors carry evidence those fields have no home for. Add exactly
   these, and nothing else: `repeated-sequence` adds `flows` (the array of flow
   `slug`s the chain appears in); `complexity-hotspot` adds `metric` (`fan-out`,
   `depth` or `loc`) and `value`; `unreached` adds `exported`, copied from the
   inventory entry, and `reachedBy`, whose only two values are `"none"` (reached
   by nothing) and `"tests"` (reached only by test-role callers, which is what
   `production-unreached` means).
4. **Verify against source.** Three things, and their order matters.
   - **Check staleness.** Two scopes, and they are not the same set; never report
     one as the other. `filesChanged` is a **whole-census** number: compare every
     entry in `index.json`'s `files` array against that file's current content, and
     count how many no longer match. Hashes only, no analysis, so it stays cheap
     even on a large map — and it is this number the step 6 banner reports, because
     a reader told "6 files have changed" takes that as a fact about the map, not
     about whichever handful of files some finding happened to cite. The
     **cited-file subset** — every file cited by any candidate finding — is what
     the drop rule below drops on: a finding is dropped only when one of its own
     sites cites a changed file, and the census count never drops anything by
     itself. A file that cannot be read at all, whatever the reason, counts as
     changed in both scopes. A cited file with no entry in `index.json`'s `files`
     array has no recorded hash to compare against, so it counts as changed in
     neither: it is outside the census, and it does not make its finding stale.
     Staleness is **never a reason to stop the command**; there is no threshold,
     because any threshold would be a number this design cannot justify.
   - **Verify, if `--read-code` was passed.** This verifies candidates and is **not
     a second scan of the repository** — do not re-scan, since scanning everything
     again would duplicate the cost of mapping and not fit on a large codebase.
     Open **only the files the candidate findings cite**, confirm or drop each
     against real current source, set surviving candidates' `confidence` to
     `verified` and **correct their sites' `line` numbers to where the code is
     now** — `file` stays forward-slash and repo-relative, exactly as the map
     recorded it — and drop the rest. A candidate emitted with no `snippet` on its
     sites — which is what a thin map produces — takes its sites' snippets from
     the source read here; this widens nothing, since these are the files this
     step already opened. A candidate whose cited file cannot be opened at all —
     deleted, or unreadable — is neither confirmed nor dropped here: it keeps
     `confidence: "unverified"` and falls through to the staleness rule below.
     Without the flag every finding stays `unverified`.
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
   descending, then `principle` alphabetically. **Assign the `id` counters here**,
   walking that order, after step 4's drops — a finding step 4 dropped never
   consumed a number, so each principle's counter reads `01`, `02`, `03` with no
   gaps.

   ```json
   {
     "schema": 1,
     "meta": { "root": "C:/Users/example/project", "generated": "2026-08-07",
               "readCode": false, "mapGenerated": "2026-08-06",
               "mapMode": "whole-code-base", "mapDetail": "standard" },
     "coverage": { "flowsTraced": 14, "entryPointsFound": 17,
                   "functionsCatalogued": 1180, "flowsUnreadable": 0,
                   "filesChanged": 6, "findingsDropped": 2,
                   "detectorsSkipped": ["duplicate-intent"],
                   "rulesLoaded": 12, "rulesChecked": 9,
                   "rulesNotCheckable": 3 },
     "rules": [
       { "ruleId": "R-01", "text": "Every public function must carry a docstring.",
         "source": "CLAUDE.md:14", "severity": "high", "checkable": true,
         "reason": "" }
     ],
     "findings": []
   }
   ```

   `rules` is every rule step 2 loaded, checkable or not, each with the `reason`
   it could not be checked where that applies — an empty array when `--rules` was
   not passed — and the three `rules*` counts describe that array.
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
   detectors were skipped and why. The changed-file count is step 4's whole file
   census, not its cited-file subset; say "of the N files the map recorded" so no
   reader takes it for the smaller number. `detectorsSkipped` carries names only —
   the reason is not in the JSON — so restate it from the step 2 rule that gated
   the detector off: for duplicate-intent on a thin map, that a thin map carries no
   `snippet`. A detector named without its reason does not satisfy this banner.
   When `--rules` was passed the banner also states how many rules were loaded,
   how many were checked, and how many could not be — naming each of those and its
   reason. A rule the report never mentions reads as a rule that passed, which is
   the one thing this detector must never imply.
   If `flowsTraced` is below `entryPointsFound`,
   say in words that the map is partial and that everything below is **clean within
   what was mapped** — never a clean bill of health for the repository. Then a
   summary count by principle and severity, then findings grouped by principle,
   each rendering `id`, `title`, `severity`, `confidence`, `rationale`, a sites
   table of `file:line` and `symbol`, `suggestion`, and `effort`. **If there are no
   findings, still write the report:** say so and repeat the coverage banner
   immediately after, because an empty report under partial coverage means the
   mapped portion was clean and must not imply a clean bill of health. Say
   **"catalogued"**, never "all" — the map came from search and reading, not an AST
   walk.

   Last, write `Code_Flows/quality-report.html`: read `.code-flow/report.template.html`
   and replace its single `__REPORT_DATA__` token with the exact JSON you just wrote,
   and its `__THEME_CSS__` token with the contents of `.code-flow/theme.css`, or an
   empty string if that file does not exist or cannot be read, changing nothing else.
   Escape every literal `</` in that JSON as `<\/` first —
   findings carry source snippets, and an unescaped `</` closes the script block early,
   leaving the page rendered as plain text with nothing to explain why. All three files
   render the same data and none may contradict another. If the scaffold cannot be read,
   say so and write the other two: a missing viewer is a missing convenience, not a
   missing report.

   Finally, report all three file paths to the user with the coverage numbers and
   the count of findings by severity.
