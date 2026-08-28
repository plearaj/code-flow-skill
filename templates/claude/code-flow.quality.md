---
description: Report DRY, KISS, YAGNI, SOLID and module-depth findings, plus violations of rules the project has already written down, from the persisted code-flow map, with file:line evidence and honest coverage.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Code Flow — Quality Report

Read the map this project has already written under `Code_Flows/` and report where
it shows duplicated intent, needless complexity, code that nothing reaches,
responsibilities and dependencies that sit wrong, and modules whose interface
costs a caller more than the implementation behind it hides.

This command **never edits source code.** `code-flow.map` adds missing docstrings
as it traces; this one writes documents and stops. Consolidating duplicates and
deleting suspected-dead code carry real blast radius, and that call is the user's.

### Instructions

Follow these steps exactly.

#### 1. Read the Arguments

The user's input (`$ARGUMENTS`) carries two optional flags:

- `--read-code` — after deriving candidate findings from the map, open the files
  those candidates cite and confirm each against current source. Off by default.
  It requires the source tree to be present and current, not merely the artifacts
  under `Code_Flows/`. It also decides two of step 3's detectors outright:
  open-closed and liskov-substitution cannot be settled from the map and do not
  run without it.
- `--rules [source ...]` — also check the map against rules this project has
  already written down. Off by default. A source is a path to a document, the
  word `auto`, or a rule written inline in quotes; several may be given,
  separated by spaces or commas, and `--rules` with no value means `auto`. Step 2
  loads them and step 3's last detector checks them. This is how a project's own
  standard — a `CLAUDE.md`, an `AGENTS.md`, a Spec Kit constitution, a team style
  guide — gets reported with the same evidence and the same honesty as DRY, KISS
  and YAGNI, instead of being a thing everyone agreed to and nobody checks.

There is no feature name to parse: this command analyzes the whole map. If the
input contains anything else, say what you read, ignore it, and carry on — do not
treat it as a filter, a path, or a flow name.

#### 2. Load the Map

Read three kinds of artifact, in this order. Each detector in step 3 draws on
some of them, and which ones are readable decides which detectors run. The rules
`--rules` names are a fourth kind, loaded at the end of this step.

1. `Code_Flows/index.json` — coverage, the file census, and the flow registry.
2. `Code_Flows/inventory.json` — the function catalog.
3. `Code_Flows/<slug>.json` — one per entry in the index's `flows` array.

However `/code-flow.map` was run, these three exist. **`--output` never suppresses the JSON artifacts** —
`index.json`, `<functionality_name>.json` and `inventory.json` are written in
every mode, including `bundle`, because this command depends on them.

**The gating rule, which governs everything below:** a detector that cannot
produce its required evidence does not run, and the report names it and says why.
Never substitute a weaker signal for a missing one — a finding derived from
evidence the map does not contain is exactly the confident-wrong finding that
costs more trust than a missing one.

**If `Code_Flows/index.json` is absent**, stop. Tell the user to run
`/code-flow.map` first. There is no map to analyze.

**If `Code_Flows/inventory.json` is absent**, stop. Tell the user to run
`/code-flow.map --whole-code-base` first. All but two of the detectors —
duplicate-intent and unreached among them — need the catalog and cannot run
without it. Do not fall back to reporting only the two that survive: most of the
detectors missing is not a degraded report, it is a different report, and one
whose meaning would change depending on how the user happened to build their map.

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
The other detectors are unaffected and still run.

**If `--read-code` was not passed**, skip the open-closed and
liskov-substitution detectors. These two are the only ones whose verdict is not
in the map at all: both are about what a body does — whether a selection among
variants is a conditional chain or a lookup, and whether an override honours what
its siblings promise — and a map records neither. It can say where to look, which
is what step 3 has it do, and where the inventory carries `overrides` it can even
say who the siblings are; what no map can say is whether one of them breaks the
promise. Record both as skipped and name the remedy: re-run with `--read-code`.

**If the flow registry is empty** — `index.json` lists no flows, or every one it
lists was unreadable — skip the three detectors defined over the flow graphs:
repeated-sequence, complexity-hotspot and unreached. All three read flow *nodes*:
one compares call chains across flows, one measures a node's fan-out and its
distance from an entry point, and the third subtracts every reached id from every
catalogued one. With no flows there are no nodes, and `unreached` in particular
would report the entire catalog as dead code — the most confidently wrong output
this command could produce. Record all three as skipped and name the remedy:
re-map with `/code-flow.map --whole-code-base`, which traces the flows the
inventory alone does not carry. A map built from a tracer's output without a
tracing pass is the ordinary way to arrive here, not a broken one.

**If no inventory entry carries `calls`**, skip the five detectors that walk the
call graph: single-responsibility, interface-segregation, dependency-cycle,
pass-through and internals-coupled-test. `calls` is a fact a tracer establishes,
not something to infer by reading, so a map built without one carries no module
graph for them to walk — and a graph guessed from file names and imports is
exactly the confident-wrong evidence the gating rule exists to prevent. Record
all five as skipped and name the remedy: re-map with `/code-flow.map
--whole-code-base --tracer on`. duplicate-intent, repeated-sequence,
complexity-hotspot, unreached and shallow-module read the inventory and the flow
graphs rather than `calls`, and still run.

**Load the rules, if `--rules` was passed.** Skip all of this when it was not:
an unrequested detector is not a gap, and it is never listed as skipped.

Resolve each source in turn. A source that names a readable file is a rule
document. A source that is not a readable path is an inline rule, taken as its own
single rule with the source `--rules`. `auto` means look for these, in this order,
and use every one that exists:

`CLAUDE.md`, `.claude/CLAUDE.md`, `AGENTS.md`, `GEMINI.md`,
`.github/copilot-instructions.md`, `.specify/memory/constitution.md`,
`memory/constitution.md`, `CONVENTIONS.md`, `.code-flow/rules.md`.

Read each document and split it into discrete rules. One rule is one statement a
reader could be shown a counter-example to. A heading, a rationale, an example and
a sentence of encouragement are not rules; a sentence saying what code must,
should or must never do is. Record for each:

- `ruleId` — `R-01`, `R-02`, in the order you read them, counting across all
  sources so no two rules share an id.
- `text` — the rule as written, quoted, not paraphrased. Never invent a rule, and
  never sharpen a soft one: a report that cites the project's own words is
  arguable; one that cites your summary of them is not.
- `source` — `file:line` of the sentence, or `--rules` for an inline rule.
- `severity` — from the rule's own wording, as a rule and not a judgement:
  `must`, `never`, `always`, `required`, `do not` mean `high`; `should`,
  `prefer`, `avoid`, `expected` mean `medium`; `consider`, `may`, `where
  possible`, `ideally` mean `low`. When the wording carries no such word, use
  `medium`.
- `checkable` — whether the map carries the evidence this rule needs. A rule
  about naming, file placement, layering, duplication, function size, docstring
  presence, dependency direction or what may call what is checkable against the
  inventory and the flow graphs. A rule about runtime behavior, review process,
  commit messages, dependency licences, CI configuration or the intent behind a
  design is not — the map has no evidence about any of it. When it is not, record
  why in one clause.

**Say what you did not check.** A rule marked not-checkable is reported as
not-checked in step 6, never as passing and never silently dropped. Reporting a
rule as clean because there was no evidence either way is the confident-wrong
outcome this whole command is arranged to avoid, and it is worse here than
anywhere else: the user asked specifically about that rule.

**If `--rules` was passed and no source could be read**, do not stop. Skip the
rule-violation detector, record it in `detectorsSkipped`, and name every path you
tried — every other detector is unaffected.

Note what is *not* a stop condition. `coverage.flowsTraced` below
`coverage.entryPointsFound` means the trace pass never finished, and that is
normal on a large repository. Analyze what was traced and let the banner in step 6
say how much that was.

#### 3. Run the Detectors

Ten detectors, two more when `--read-code` was passed, and one more when
`--rules` was. Step 2's gating rule has already decided which of them run; run
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
- A `role` of `source` reached by no flow and by no test file is `unreached`, and
  carries `reachedBy: "none"`: a dead-code candidate.
- A `role` of `source` reached only from test files is `production-unreached`, and
  carries `reachedBy: "tests"`. Phrase it "kept alive only by its own tests";
  never rate it `high` — otherwise `medium`.

Severity is `high` only when the entry is `unreached`, is not `exported`, and is
not test-only. Anything whose `exported` is true is capped at `low`, because a
public API surface has callers this repository cannot see.

**SOLID's five, and where each one's evidence comes from.** Three of them —
single-responsibility, interface-segregation and dependency-inversion — are
settled by the call graph, and their detectors follow immediately. The other two
are not, and they are not dropped for it: open-closed and liskov-substitution
report under `--read-code`, from candidates the map can locate and only source
can confirm. Detectors k and l are those, and step 2 gates them off when the flag
was not passed.

Nothing here reads a rule from a name. A dispatch table, a registry and a
polymorphic call are all correct answers to the problem open-closed describes,
and the map cannot tell any of them from a conditional chain — which is exactly
why those two detectors wait for the source rather than guessing from the graph.

**e. single-responsibility (SOLID).** A module here is a file. For each file with
at least 3 catalogued `source` functions, count `dependencies` — the distinct
other files its functions call into — and `dependents`, the distinct files
calling in. Severity is `high` when `dependencies` is at least 10, `medium` when
it is at least 6; below 6 is not a finding. Cite the file's own functions that
reach into the most distinct other files, up to 5 of them. This is the
module-level counterpart to complexity-hotspot's per-function fan-out, and it is
a proxy for "more than one reason to change" rather than a proof of one, and the
rationale says so.

**f. interface-segregation (SOLID).** For each file exporting at least 4 `source`
functions, take each consumer — a file whose functions call into it — and the set
of exported symbols that consumer actually uses. It is a finding when the module
has at least 2 consumers and no single consumer uses more than half the exported
surface: one interface is standing where its clients want several. Severity is
`high` when the module exports at least 8 and the widest consumer uses a quarter
or fewer of them; otherwise `medium`. Cite up to 5 of the exported functions,
the least-called first, and name the consumers in the rationale.

**g. dependency-cycle (SOLID).** Walk the module graph — files as nodes, a call
from a function in one file to a function in another as an edge — and find every
cycle. Two files that call each other, or a longer ring, is a finding. Severity
is `high` when the cycle spans at least 3 files or crosses top-level directories;
otherwise `medium`. Cite one site per file in the cycle: the function whose call
carries the edge onward. This is the half of dependency inversion a call graph
can establish. The other half — whether a dependency points at an abstraction or
at a concretion — it cannot, and the usual remedy for a cycle is to invert one of
its edges behind an interface, which is why it reports under SOLID.

**Deep modules.** The three detectors below weigh interface cost against hidden
functionality: a module earns its keep when it hides more than it asks a caller
to learn. They report shape, never intent, and a small module that is small
because its job is small is not a finding — the thresholds sit where they do so
that it does not become one.

**h. shallow-module (DEPTH).** For each file with at least 3 catalogued `source`
functions, take `interface` — its count of exported functions — and `hiddenLoc`,
the summed `loc` of every function in it. It is a finding when `interface` is at
least 3 and `hiddenLoc` divided by `interface` is under 10: fewer than ten lines
of implementation hidden per symbol the caller has to learn. Severity is `high`
when `interface` is at least 6 and that ratio is under 6; otherwise `medium`.
Cite up to 5 of the exported functions themselves. This detector reads only
`exported` and `loc`, so it runs on any map that carries an inventory.

**i. pass-through (DEPTH).** A pass-through function does nothing except hand its
arguments to one other function. It is a finding when a `source` function has
exactly 1 outbound call, a `loc` of 5 or fewer, and a parameter count equal to
its callee's — read both from `signature`. Group them by file: one finding per
module, one site per pass-through in it. Severity is `high` when a module holds
at least 3, otherwise `medium`. A function that transforms, validates, defaults
or renames its arguments on the way through is doing work and is not a
pass-through; where the map carries a `snippet`, use it to tell the two apart.

**j. internals-coupled-test (DEPTH).** A test that reaches past a module's
interface into its internals freezes the implementation that module was supposed
to stay free to change. It is a finding when a `test`-role function calls a
`source` function whose `exported` is false, in a file that exports at least one
function — there was an interface to test through, and the test went around it.
Group by the module reached into: one finding per module, one site per test
function. Severity is `high` when at least 5 distinct test functions reach in or
at least 3 distinct internals are reached; otherwise `medium`. `exported` is the
map's per-language heuristic and it defaults to `true` wherever the convention is
unclear, so this detector under-reports rather than over-reports — say so in the
rationale, and never read an empty result here as tests being well-behaved.

**Open-closed and Liskov, in two steps.** Each of the two detectors below emits
a *candidate* from the map and leaves the verdict to step 4b. The map narrows the
search to a handful of functions; the source decides. A candidate step 4b does
not confirm is dropped there like any other, and because step 2 gates both
detectors off without `--read-code`, neither can ever reach the report
unconfirmed: alone among the detectors, every finding they produce is `verified`.

**k. open-closed (SOLID).** Look for a variant family: at least 3 catalogued
`source` functions whose unqualified names agree once one token differs
(`render_pdf`, `render_html`, `render_csv`; `handle_visa`, `handle_amex`), with
equal parameter counts, and at least one function that calls 3 or more of them
directly. That caller is the candidate — the place a new variant would have to
edit. Cite it as the first site and the family members after it. Severity is
`high` when the caller selects among at least 5 variants, `medium` at 3 or 4.

Step 4b decides. Open the caller and read how it selects: a chain of conditionals
on a type, a kind, a string or an enum confirms the candidate, because adding a
variant means editing that function. A lookup table, a registry, a dispatch dict,
a match on an exhaustive sum type the compiler checks, or a polymorphic call
drops it — those are the shapes that are already open to extension, and reporting
one is worse than reporting nothing.

**l. liskov-substitution (SOLID).** Look for an override family. There are two
ways to find one, and which is available depends on the map.

**Stated, from `overrides`.** Where the inventory entries carry `overrides`, the
family is read rather than guessed: its members are the catalogued `source`
functions that name the same declaration — the same `Supertype.member` string.
Two members is a family, and no caller has to be found to establish it, because
the source already said these functions implement one thing. Set `familyFrom` to
`overrides` and `family` to that declaration.

**Guessed, from names.** For functions that carry no `overrides` — a map built
without a tracer has none at all, and even a traced map has none where the
declaration is outside the repository or has no body the tracer could
catalogue — fall back to the shape the map can still see: at least 2 catalogued
`source` functions sharing an unqualified `name` and a parameter count, in
different files. Where the map carries `calls`, also require at least one caller
reaching 2 or more of them; that is the cheapest way to drop a name collision
before step 4b has to open anything. Where it does not, every such group is a
candidate and step 4b's first check does the same work by reading. Set
`familyFrom` to `name` and `family` to the shared name.

A function belongs to one family, not two: the stated families are formed first,
and only the functions left over are eligible for a guessed one. A map may
produce both kinds at once — a traced Java package beside an untraced C++ one is
one repository with two answers — and each finding says which kind it is, so a
reader can weigh a stated family differently from a guessed one instead of
having to assume.

Either way, it is a candidate when at least one member looks like it refuses or
narrows what the others do: a `loc` of 3 or fewer, or a `snippet` whose body
raises a not-implemented error, returns a constant unconditionally, or does
nothing. Cite each member that looks that way. Severity is `high` when at least 2
members do, `medium` at 1.

Step 4b decides this one too, and it has more to check than the other. Open the
members and confirm three things: they really do share a supertype or interface
rather than a name; a caller really does hold one through that shared type; and
the member really does weaken the contract — throwing where its siblings return,
ignoring an argument they honour, returning a sentinel they never return, or
demanding a precondition they do not. All three or it is dropped. Two unrelated
`save` methods in unrelated classes are the false positive this detector is most
exposed to, and the first check is what removes it.

For a stated family the first check is already settled — the tracer read `impl
Trait for Type`, `extends` or `implements` off the source itself, and named a
supertype only where that supertype really declares the member — so step 4b
confirms the other two and nothing else. That is the whole gain from the field:
the check that was doing the most work to remove false positives is the one it
makes unnecessary. Confirm it again for a guessed family, where nothing has
established it.

**m. rule-violation (RULES).** Runs only when step 2 loaded at least one rule.
For each rule marked `checkable`, search the inventory and the flow graphs for
evidence that contradicts it, and cite that evidence the way every other detector
does: `file`, `line`, `symbol`, snippet where the map carries one. Severity is
the rule's own severity from step 2 — the rule's wording decided it, not you.

**One rule, one finding.** Every site that breaks the same rule belongs to that
rule's finding, however many there are. Fifteen files breaking a naming rule is
one finding with fifteen sites.

A rule with no violating site is not a finding. It is reported as checked and
clean, in the banner — which is the only place a reader can tell "checked, clean"
apart from "never checked".

Cite the rule as well as the code. Every finding here carries `rule` (the rule's
text, quoted from step 2), `ruleId` and `ruleSource`, so a reader can go and read
the sentence the finding rests on. A rule-violation finding whose evidence is
your reading of the project's intent rather than its written words is not a
finding — drop it.

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

`principle` is `DRY`, `KISS`, `YAGNI`, `SOLID`, `DEPTH` or `RULES`. `severity`
is `high`, `medium` or `low`. `confidence` is `unverified` unless step 4 verified
the finding. `effort` is `small`, `medium` or `large`. `id` is the principle, a
hyphen, and a two-digit counter that restarts per principle: `DRY-01`, `DRY-02`,
`KISS-01`, `YAGNI-01`, `RULES-01`, `SOLID-01`, `DEPTH-01`.
**The counter is assigned in step 5, after step 4's drops** — not here — so do not
number findings as you emit them, and read the `DRY-01` above as the shape rather
than as a number already spent. Once assigned, ids are stable within the run,
because the markdown and the JSON cross-reference each other by them.

Most detectors carry evidence the fields above have no home for. Add exactly
these, and nothing else — `module` is always the file path, forward-slash and
repo-relative like every other path in this report:

- `repeated-sequence` adds `flows` — the array of flow `slug`s the chain appears in.
- `complexity-hotspot` adds `metric` (`fan-out`, `depth` or `loc`) and `value`.
- `unreached` adds `exported`, copied from the inventory entry, and `reachedBy`,
  whose only two values are `"none"` (reached by nothing) and `"tests"` (reached
  only by test-role callers, which is what `production-unreached` means).
- `rule-violation` adds `rule` — the rule's text, quoted — plus `ruleId` and
  `ruleSource`, the `file:line` it was read from.
- `single-responsibility` adds `module`, plus `dependencies` and `dependents` —
  the two counts, not the file lists.
- `interface-segregation` adds `module`, `exports` (its count of exported
  functions), `consumers` (the count of files calling in) and
  `widestConsumerUse` (how many of those exports the widest consumer uses).
- `dependency-cycle` adds `cycle` — the file paths in the order the calls run,
  the first repeated at the end so the ring closes.
- `shallow-module` adds `module`, `interface` and `hiddenLoc`.
- `pass-through` adds `module`.
- `internals-coupled-test` adds `module` — the file reached into — and
  `internals`, the array of non-exported names the tests called.
- `open-closed` adds `variants` — the family's names — and `switchPoint`, the
  `file:line` of the function that selects among them.
- `liskov-substitution` adds `family` — the declaration the members share, which
  is the `Supertype.member` string for a stated family and the shared unqualified
  name for a guessed one — `familyFrom`, which is `overrides` or `name` and says
  which of those two it is, and `weakened`, the member names step 4b confirmed
  narrow the contract, qualified where the bare name would not tell two of them
  apart.

#### 4. Verify Against Source

Three things happen here, and their order matters.

**a. Check staleness.** Two scopes, and they are not the same set. Never report
one as the other.

`filesChanged` is a **whole-census** number: compare every entry in `index.json`'s
`files` array against that file's current content, and count how many no longer
match. Hashes only, no analysis, so it stays cheap even on a large map — and it is
this number the banner in step 6 reports, because a reader told "6 files have
changed" takes that as a fact about the map, not about whichever handful of files
some finding happened to cite.

The **cited-file subset** — every file cited by any candidate finding — is what
the drop rule below drops on: a finding is dropped only when one of its own sites
cites a changed file, and the census count never drops anything by itself.

A file that cannot be read at all, whatever the reason, counts as changed in both
scopes. A cited file with no entry in `index.json`'s `files` array has no recorded
hash to compare against, so it counts as changed in neither: it is outside the
census, and it does not make its finding stale.

Staleness is **never a reason to stop the command**. There is no threshold — any
threshold would be a number this design cannot justify.

**b. Verify, if `--read-code` was passed.** This verifies candidates; it is **not
a second scan of the repository**. Do not re-scan: scanning everything again would
duplicate the cost of mapping and would not fit on a large codebase, which is the
reason the map is persisted in the first place.

1. Open **only the files the candidate findings cite**. Nothing else.
2. Confirm or drop each candidate against real current source.
3. For each candidate that survives, set its `confidence` to `verified` and
   **correct its sites' `line` numbers to where the code is now** — `file` stays
   forward-slash and repo-relative, exactly as the map recorded it.
4. A candidate emitted with no `snippet` on its sites — which is what a thin map
   produces — takes its sites' snippets from the source read here. This widens
   nothing: these are the files this step already opened.
5. For each candidate that does not survive, drop it.
6. An open-closed or liskov-substitution candidate is confirmed against the
   test its own rule in step 3 states — the selection structure for one, the
   three checks for the other, less whichever of the three `overrides` already
   settled — and dropped when it fails. These two exist only under this flag, so
   a candidate this step cannot settle is dropped rather than carried: there is
   no unverified form of either to fall back on.
7. A candidate whose cited file cannot be opened at all — deleted, or unreadable
   — is neither confirmed nor dropped here: it keeps `confidence: "unverified"`
   and falls through to the staleness rule below.

Without `--read-code`, every finding keeps `confidence: "unverified"`.

**c. Drop what is left stale and unverified.** Verify first, then drop. Any
finding still marked `unverified` whose `sites` cite a file whose `hash` no longer
matches is dropped, and counted for the banner — the whole finding, not just that
site. A finding is only as trustworthy as its weakest citation, so one stale site
among several drops all of it. Its `file:line` evidence is known to be wrong, and
`file:line` evidence is the whole currency of this report.

A `verified` finding is never dropped for staleness. `--read-code` read current
source, so such a finding was confirmed against the very change that made the file
stale — dropping it would discard the best evidence in the report. This is what
the flag buys: it turns staleness from a reason to discard findings into a reason
to re-check them, and under `--read-code` the dropped count is usually zero.

#### 5. Write the Report Data

Write `Code_Flows/quality-report.json` first. It is the data; step 6's markdown is
one rendering of it, and writing the markdown first would make them two
independent transcriptions free to disagree.

Order the `findings` array by `severity` descending (`high`, `medium`, `low`),
then by site count descending, then by `principle` alphabetically. **Assign the
`id` counters here**, walking that order, after step 4's drops — a finding step 4
dropped never consumed a number, so each principle's counter reads `01`, `02`,
`03` with no gaps.

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

`rules` is every rule step 2 loaded, checkable or not, each with the `reason` it
could not be checked where that applies — an empty array when `--rules` was not
passed. The three `rules*` counts describe that array, and a reader can reconcile
them against it. `meta.root` is the one absolute path in the file; every path
inside `findings` is repo-relative with forward slashes. `mapGenerated`, `mapMode` and `mapDetail`
are copied from the map's own `index.json` `meta`, so the report records which map
it read. `detectorsSkipped` lists detector names step 2 gated off, and is an empty
array when none was.

#### 6. Write the Report

Render `Code_Flows/quality-report.md` from the JSON you just wrote. Nothing in it
may contradict that file.

**Lead with coverage — this is a requirement, not a formatting preference.** The
first thing under the title is a banner stating: how many of `entryPointsFound`
entry points were traced (`flowsTraced`), how many functions were catalogued, how
many flows were unreadable, how many mapped files have changed since mapping, how
many findings were dropped as stale, and which detectors were skipped and why.

When `--rules` was passed, the banner also states how many rules were loaded,
how many were checked, and how many could not be — naming each of those and its
reason. A rule the report never mentions reads as a rule that passed, which is
the one thing this detector must never imply.

**The SOLID group says which of the five it checked.** Where step 6 groups
findings by principle, the `SOLID` group opens with one sentence naming
open-closed and Liskov substitution and saying whether they were checked: under
`--read-code` they were, from source; without it they were not, and the sentence
names `--read-code` as the remedy. Write that sentence even when SOLID produced
no findings, and write it in the summary when the group is absent entirely. Three
principles reported and two never mentioned reads as five principles clean, which
is the one thing this section must not imply.

The changed-file count is step 4's whole file census, not its cited-file subset; say
"of the N files the map recorded" so no reader takes it for the smaller number.
`detectorsSkipped` carries names only — the reason is not in the JSON — so restate
it from the step 2 rule that gated the detector off: for duplicate-intent on a
thin map, that a thin map carries no `snippet`. A detector named without its
reason does not satisfy this banner.

If `flowsTraced` is below `entryPointsFound`, say in words that the map is partial
and that every section below is **clean within what was mapped** — never a clean
bill of health for the repository.

Then a summary count by principle and severity. Then the findings grouped by
principle, each rendering its `id`, `title`, `severity`, `confidence`, `rationale`,
a sites table of `file:line` and `symbol`, its `suggestion`, and its `effort`.

**If there are no findings, still write the report.** Say there were no findings,
and repeat the coverage banner immediately after — an empty report under partial
coverage means the mapped portion was clean, and the document must say that rather
than implying a clean bill of health.

Say **"catalogued"**, never "all". The map came from search and reading, not an
AST walk, so it is best-effort and the report must never claim completeness.

Last, write `Code_Flows/quality-report.html`. Read `.code-flow/report.template.html`
and replace its single `__REPORT_DATA__` token with the exact JSON you just wrote.
Also replace its `__THEME_CSS__` token with the contents of `.code-flow/theme.css`,
or an empty string if that file does not exist or cannot be read. Change nothing
else in the scaffold.

Escape every literal `</` inside the JSON as `<\/` before substituting. Findings
carry source snippets, and an unescaped `</` closes the script block early — the
page then renders as plain text with no error to explain why.

All three files are renderings of the same data and none may contradict another. If
you cannot read the scaffold, say so and write the other two; a missing viewer is a
missing convenience, not a missing report.

Finally, report all three file paths to the user, along with the coverage numbers and
the count of findings by severity.
