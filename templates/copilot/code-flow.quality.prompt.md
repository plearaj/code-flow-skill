---
agent: agent
description: Report DRY, KISS, YAGNI, SOLID and module-depth findings, plus violations of rules the project has already written down, from the persisted code-flow map, with file:line evidence and honest coverage.
---

Read the map this project has already written under `Code_Flows/` and report where
it shows duplicated intent, needless complexity, code that nothing reaches,
responsibilities and dependencies that sit wrong, and modules whose interface
costs a caller more than the implementation behind it hides.

This command **never edits source code.** `code-flow.map` adds missing docstrings
as it traces; this one writes documents and stops. Consolidating duplicates and
deleting suspected-dead code carry real blast radius, and that call is the user's.

Follow these steps exactly:

1. **Read the arguments.** Two optional flags. `--read-code` — after deriving
   candidate findings from the map, open the files those candidates cite and
   confirm each against current source. Off by default. It requires the source
   tree to be present and current, not merely the artifacts under `Code_Flows/`.
   It also decides two of step 3's detectors outright: open-closed and
   liskov-substitution have no evidence in the map and do not run without it.
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
   and unreached among others need the catalog, and reporting only the two that
   survive would make the report mean something different depending on how the user
   built their map.
   If either file exists but does not parse as JSON, **stop**, report the path and
   the problem, and do not overwrite it — this command never writes those files. If
   a `<slug>.json` named in the registry is missing or does not parse, do **not**
   stop: skip that flow, count it, and report the count with the coverage banner in
   step 6. If `meta.detail` is `thin` and `--read-code` was not passed, skip the
   duplicate-intent detector — a thin map carries no `snippet` and that detector
   cannot cite the evidence its findings require — and name both remedies: re-run
   with `--read-code`, or re-map with `/code-flow.map --whole-code-base --detail standard`.
   The other detectors are unaffected and still run. If `--read-code` was not
   passed, skip the open-closed and liskov-substitution detectors: these two are
   the only ones whose evidence is not in the map at all — the map records what
   calls what, and both are about what a body does, whether a selection among
   variants is a conditional chain or a lookup and whether an override honours what
   its siblings promise. The map can say where to look, which is what step 3 has it
   do, but only source can settle either. Record both as skipped and name the
   remedy: re-run with `--read-code`. If no inventory entry carries
   `calls`, skip the five detectors that walk the call graph — single-responsibility,
   interface-segregation, dependency-cycle, pass-through and internals-coupled-test.
   `calls` is a fact a tracer establishes, not something to infer by reading, so a
   map built without one carries no module graph for them to walk, and a graph
   guessed from file names and imports is exactly the confident-wrong evidence the
   gating rule exists to prevent. Record all five as skipped and name the remedy:
   re-map with `/code-flow.map --whole-code-base --tracer on`. duplicate-intent,
   repeated-sequence, complexity-hotspot, unreached and shallow-module read the
   inventory and the flow graphs rather than `calls`, and still run.
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
3. **Run the detectors.** Ten of them, two more when `--read-code` was passed and one more when `--rules` was; step 2's gating rule already decided which
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

   **SOLID's five, and where each one's evidence comes from.** Three of them —
   single-responsibility, interface-segregation and dependency-inversion — are settled
   by the call graph, and their detectors follow immediately. The other two are not,
   and they are not dropped for it: open-closed and liskov-substitution report under
   `--read-code`, from candidates the map can locate and only source can confirm; step
   2 gates them off when the flag was not passed. Nothing here reads a rule from a
   name — a dispatch table, a registry and a polymorphic call are all correct answers
   to the problem open-closed describes, and the map cannot tell any of them from a
   conditional chain, which is exactly why those two wait for the source.
   - **single-responsibility (SOLID)** — a module here is a file. For each file with
     at least 3 catalogued `source` functions, count `dependencies` (the distinct
     other files its functions call into) and `dependents` (the distinct files
     calling in). `high` when `dependencies` is at least 10, `medium` at 6; below 6
     is not a finding. Cite the file's own functions reaching into the most distinct
     other files, up to 5. This is the module-level counterpart to
     complexity-hotspot's per-function fan-out, and a proxy for "more than one
     reason to change" rather than a proof of one, and the rationale says so.
   - **interface-segregation (SOLID)** — for each file exporting at least 4 `source`
     functions, take each consumer (a file whose functions call into it) and the set
     of exported symbols that consumer actually uses. A finding when the module has
     at least 2 consumers and no single consumer uses more than half the exported
     surface: one interface standing where its clients want several. `high` when the
     module exports at least 8 and the widest consumer uses a quarter or fewer;
     otherwise `medium`. Cite up to 5 of the exported functions, the least-called
     first, and name the consumers in the rationale.
   - **dependency-cycle (SOLID)** — walk the module graph (files as nodes, a call
     from a function in one file to a function in another as an edge) and find every
     cycle. Two files calling each other, or a longer ring, is a finding. `high` when
     the cycle spans at least 3 files or crosses top-level directories; otherwise
     `medium`. Cite one site per file: the function whose call carries the edge
     onward. This is the half of dependency inversion a call graph can establish; the
     other half — whether a dependency points at an abstraction or a concretion — it
     cannot, and the usual remedy for a cycle is to invert one of its edges behind an
     interface, which is why it reports under SOLID.

   **Deep modules.** The three below weigh interface cost against hidden
   functionality: a module earns its keep when it hides more than it asks a caller to
   learn. They report shape, never intent, and a small module that is small because
   its job is small is not a finding — the thresholds sit where they do so that it
   does not become one.
   - **shallow-module (DEPTH)** — for each file with at least 3 catalogued `source`
     functions, take `interface` (its count of exported functions) and `hiddenLoc`
     (the summed `loc` of every function in it). A finding when `interface` is at
     least 3 and `hiddenLoc` divided by `interface` is under 10: fewer than ten lines
     of implementation hidden per symbol the caller has to learn. `high` when
     `interface` is at least 6 and that ratio is under 6; otherwise `medium`. Cite
     up to 5 of the exported functions themselves. This one reads only `exported`
     and `loc`, so it runs on any map that carries an inventory.
   - **pass-through (DEPTH)** — a pass-through function does nothing except hand its
     arguments to one other function. A finding when a `source` function has exactly
     1 outbound call, a `loc` of 5 or fewer, and a parameter count equal to its
     callee's, both read from `signature`. Group by file: one finding per module, one
     site per pass-through in it. `high` when a module holds at least 3, otherwise
     `medium`. A function that transforms, validates, defaults or renames its
     arguments on the way through is doing work and is not a pass-through; where the
     map carries a `snippet`, use it to tell the two apart.
   - **internals-coupled-test (DEPTH)** — a test that reaches past a module's
     interface into its internals freezes the implementation that module was supposed
     to stay free to change. A finding when a `test`-role function calls a `source`
     function whose `exported` is false, in a file that exports at least one function
     — there was an interface to test through, and the test went around it. Group by
     the module reached into: one finding per module, one site per test function.
     `high` when at least 5 distinct test functions reach in or at least 3 distinct
     internals are reached; otherwise `medium`. `exported` is the map's per-language
     heuristic and defaults to `true` wherever the convention is unclear, so this one
     under-reports rather than over-reports — say so in the rationale, and never read
     an empty result here as tests being well-behaved.

   **Open-closed and Liskov, in two steps.** Each of the two below emits a
   *candidate* from the map and leaves the verdict to step 4's verify pass. The map
   narrows the search to a handful of functions; the source decides. A candidate the
   verify pass does not confirm is dropped there like any other, and because step 2
   gates both off without `--read-code`, neither can reach the report unconfirmed:
   alone among the detectors, every finding they produce is `verified`.
   - **open-closed (SOLID)** — look for a variant family: at least 3 catalogued
     `source` functions whose unqualified names agree once one token differs
     (`render_pdf`, `render_html`, `render_csv`), with equal parameter counts, and at
     least one function calling 3 or more of them directly. That caller is the
     candidate — the place a new variant would have to edit. Cite it first and the
     family after it. `high` when the caller selects among at least 5 variants,
     `medium` at 3 or 4. The verify pass decides: a chain of conditionals on a type, a
     kind, a string or an enum confirms it, because adding a variant means editing
     that function; a lookup table, a registry, a dispatch dict, a match on an
     exhaustive sum type the compiler checks, or a polymorphic call drops it — those
     are already open to extension, and reporting one is worse than reporting nothing.
   - **liskov-substitution (SOLID)** — look for an override family: at least 2
     catalogued `source` functions sharing an unqualified `name` and a parameter
     count, in different files, with at least one caller reaching 2 or more of them,
     which is what makes the family polymorphic rather than a name collision. A
     candidate when at least one member looks like it refuses or narrows what the
     others do: a `loc` of 3 or fewer, or a `snippet` whose body raises a
     not-implemented error, returns a constant unconditionally, or does nothing. Cite
     each member that looks that way. `high` when at least 2 members do, `medium` at
     1. The verify pass confirms three things: they really share a supertype or
     interface rather than a name; a caller really holds one through that shared type;
     and the member really weakens the contract — throwing where its siblings return,
     ignoring an argument they honour, returning a sentinel they never return, or
     demanding a precondition they do not. All three or it is dropped. Two unrelated
     `save` methods in unrelated classes are the false positive this one is most
     exposed to, and the first check is what removes it.

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

   `principle` is `DRY`, `KISS`, `YAGNI`, `SOLID`, `DEPTH` or `RULES`; `severity`
   is `high`, `medium` or `low`; `confidence` is `unverified` unless step 4 verified
   it; `effort` is `small`, `medium` or `large`. `id` is the principle, a hyphen, and
   a two-digit counter restarting per principle: `DRY-01`, `DRY-02`, `KISS-01`,
   `YAGNI-01`, `RULES-01`, `SOLID-01`, `DEPTH-01`.
   **The counter is assigned in step 5, after step 4's drops** — not here — so do
   not number findings as you emit them, and read the `DRY-01` above as the shape
   rather than as a number already spent. Once assigned, ids are stable within
   the run — the markdown and the JSON cross-reference each other by them.

   Most detectors carry evidence those fields have no home for. Add exactly
   these, and nothing else — `module` is always the file path, forward-slash and
   repo-relative like every other path in this report. `repeated-sequence` adds
   `flows` (the array of flow `slug`s the chain appears in); `complexity-hotspot`
   adds `metric` (`fan-out`, `depth` or `loc`) and `value`; `unreached` adds
   `exported`, copied from the inventory entry, and `reachedBy`, whose only two
   values are `"none"` (reached by nothing) and `"tests"` (reached only by test-role
   callers, which is what `production-unreached` means); `rule-violation` adds `rule`
   (the text, quoted), `ruleId` and `ruleSource`; `single-responsibility` adds
   `module`, `dependencies` and `dependents`; `interface-segregation` adds `module`,
   `exports`, `consumers` and `widestConsumerUse`; `dependency-cycle` adds `cycle`,
   the file paths in the order the calls run with the first repeated at the end so
   the ring closes; `shallow-module` adds `module`, `interface` and `hiddenLoc`;
   `pass-through` adds `module`; `internals-coupled-test` adds `module` (the file
   reached into) and `internals`, the array of non-exported names the tests called;
   `open-closed` adds `variants` (the family's names) and `switchPoint`, the
   `file:line` of the function selecting among them; and `liskov-substitution` adds
   `family` (the shared unqualified name) and `weakened`, the member names the
   verify pass confirmed narrow the contract, qualified where the bare name would
   not tell two of them apart.
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
     An open-closed or liskov-substitution candidate is confirmed against the test
     its own rule in step 3 states — the selection structure for one, the three
     checks for the other — and dropped when it fails; these two exist only under
     this flag, so a candidate this step cannot settle is dropped rather than
     carried, since there is no unverified form of either to fall back on.
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
   empty array when none was.

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
   the one thing this detector must never imply. **The SOLID group says which of the
   five it checked:** where step 6 groups findings by principle, the `SOLID` group
   opens with one sentence naming open-closed and Liskov substitution and saying
   whether they were checked — under `--read-code` they were, from source; without it
   they were not, and the sentence names `--read-code` as the remedy. Write that
   sentence even when SOLID produced no findings, and write it in the summary when
   the group is absent entirely; three principles reported and two never mentioned
   reads as five principles clean.
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
