---
name: code-flow-violations
description: Check the code-flow map, and the source behind it, for violations of a rule you name -- one outside DRY, KISS, YAGNI, SOLID and module depth -- reporting every site with file:line evidence and saying plainly which rules could not be settled.
argument-hint: "<violation> [<violation> ...] [--no-read-code] [--severity high|medium|low]"
disable-model-invocation: true
---

## Code Flow — Violations

Check the map this project has already written under `Code_Flows/` for violations of
a rule **you** name: something this codebase is supposed to do that is not one of
the five principles `code-flow-quality` already checks. You say what the rule is;
this reports every place the code contradicts it, quotes your rule beside the
evidence, and says plainly where it could not tell.

`code-flow-quality --rules` checks written-down rules as one detector among
thirteen, as part of a sweep. This command exists for the other case: one
violation, or a few, that you want answered properly right now. So it reads
source by default rather than reporting your rule unanswerable, it gives every
rule a row whether it was violated, clean or unsettled, and it never reports a
rule as clean that it could not actually enumerate.

This skill **never edits source code.** It writes documents and stops.

### User Input

The user's request names the violations to check -- inline rules in quotes, paths
to rule documents, or `auto` -- and carries the optional `--no-read-code` and
`--severity` flags. Step 1 reads them.

### Instructions

Follow these steps exactly.

#### 1. Read the Arguments

The request names **the violations to check**, and carries two optional flags.

A violation is one of three things, and several may be given, separated by spaces
or commas:

- **A rule written inline, in quotes** — `"Validation belongs in src/auth/ and
  nowhere else"`. This is the ordinary case: a thing this codebase is supposed to
  do that nobody has written down anywhere a tool can read.
- **A path to a document** — every rule in it is loaded, the way `--rules` loads
  one.
- **`auto`** — look for these, in this order, and use every one that exists:
  `CLAUDE.md`, `.claude/CLAUDE.md`, `AGENTS.md`, `GEMINI.md`,
  `.github/copilot-instructions.md`, `.specify/memory/constitution.md`,
  `memory/constitution.md`, `CONVENTIONS.md`, `.code-flow/rules.md`.

**If the request names no violation, stop and say what the command needs.** Do not
fall back to `auto`, and do not pick a rule you think the project would want
checked. "Check the violation I care about" with no violation named is a request
that has not finished being made, and guessing at it produces a report about
something nobody asked for.

The flags:

- `--read-code` / `--no-read-code` — whether to open source files to settle a rule
  the map cannot settle. **On by default**, which is the opposite of the quality
  command's default and deliberate. There, `--read-code` widens a sweep that
  already has thirteen detectors' worth of results; here, the user named one
  thing and wants an answer about it, and "the map does not carry that evidence"
  is a poor answer when the files are sitting right there. `--no-read-code`
  restores map-only checking, for a repository too large to read or a checkout
  where the source is not present.
- `--severity high|medium|low` — the severity to give an inline rule whose wording
  carries no modal verb. Rules read from a document always take their severity
  from their own wording; this only fills the gap for a rule the user typed.
  Default `medium`.

#### 2. Load the Map

Read three artifacts, in this order:

1. `Code_Flows/index.json` — coverage, the file census, and the flow registry.
2. `Code_Flows/inventory.json` — the function catalog, and `components` where the
   map recorded a frontend.
3. `Code_Flows/<slug>.json` — one per entry in the index's `flows` array.

**If `index.json` is missing, stop.** Tell the user to run `/code-flow-map
--whole-code-base` first. This command checks a map; without one there is nothing
to check, and reading the repository from scratch here would be a different tool
wearing this one's name.

**If `inventory.json` is missing or does not parse, stop** and say so. The catalog
is what makes a violation checkable across a whole codebase rather than across
whichever files happened to be read: a rule of the form "every X must Y" needs the
set of all X, and the inventory is where that set lives.

**If a flow sidecar is missing or does not parse, skip that one flow**, count it,
and carry on. One unreadable flow is not a reason to abandon the other thirteen —
say how many in the report.

Never overwrite an artifact that does not parse. Report the path and what is wrong
with it, and let the user repair it.

#### 3. Read the Violations Into Rules

Turn what the user named into a numbered list of rules. One rule is one statement
a reader could be shown a counter-example to. A heading, a rationale, an example
and a sentence of encouragement are not rules; a sentence saying what code must,
should or must never do is.

Record for each:

- `ruleId` — `R-01`, `R-02`, in the order you read them, counting across every
  source so no two rules share an id.
- `text` — the rule as written, quoted, not paraphrased. **Never invent a rule,
  and never sharpen a soft one.** A report that cites the user's own words is
  arguable; one that cites your tightening of them is not, and the user cannot
  tell which they are reading.
- `source` — `file:line` for a rule read from a document, or `inline` for one the
  user typed.
- `severity` — from the rule's own wording: `must`, `never`, `always`, `required`,
  `do not` mean `high`; `should`, `prefer`, `avoid`, `expected` mean `medium`;
  `consider`, `may`, `where possible`, `ideally` mean `low`. When the wording
  carries no such word, use `--severity`, which defaults to `medium`.
- `scope` — the files the rule is about, as the rule itself states them: a path, a
  directory, a language, a role (`source` or `test`), or `all` where it names
  none. Take this from the rule's words, never from a guess about intent.

#### 4. Decide How Each Rule Can Be Settled

Before checking anything, say for each rule which evidence would settle it. This
is the step that decides what the rest of the run does, and it is recorded in the
report so a reader can disagree with it.

- **`map`** — the inventory and the flow graphs carry the evidence. Naming, file
  placement, layering, function size, docstring presence, duplication, dependency
  direction, what may call what, which component renders which, and whether a test
  reaches a module's internals are all facts the map already holds.
- **`source`** — the map does not carry it but the files do. The contents of a
  function, a specific API or import, a literal, a comment convention, an
  annotation, a string, an error message, the shape of a signature. Needs
  `--read-code`.
- **`neither`** — no artifact this command can read decides it. Runtime behaviour,
  review process, commit messages, dependency licences, CI configuration,
  performance, and the intent behind a design. Record why in one clause.

**A rule settled by `source` while `--no-read-code` is in force is not settled.**
Record it as not checked, and name the flag as the reason — not the rule, and not
the map.

**Name the files before you open them.** For a `source` rule, derive the candidate
set from the map: the inventory's files, filtered by the rule's own `scope`. That
bounds the reading by the catalog rather than by a walk of the tree, and it makes
the number knowable in advance. **If that set is larger than you can read in this
session, say so with the number and check what you can** — then record the rule as
partially checked, naming how many of how many files were read. A rule checked
against 40 of 900 files that is reported as clean is the worst outcome this
command can produce.

#### 5. Check Each Rule

For every rule that step 4 settled, search its evidence for sites that contradict
it.

**One rule, one finding.** Every site that breaks the same rule belongs to that
rule's finding, however many there are. Fifteen files breaking a naming rule is
one finding with fifteen sites, never fifteen findings.

**Cite what a reader can go and look at.** Each site carries `file`, `line`,
`symbol` where the violation belongs to a named function or component, and a
`snippet` where you have one. A site whose evidence is your reading of the
project's intent rather than something visible at that line is not a site — drop
it.

**Absence is not evidence.** For a rule of the form "every X must Y", a site is an
X that does not Y — which means you have to be able to enumerate X. If you cannot
enumerate X from the map or from the files you read, the rule is **not settled**,
and reporting it clean would be a claim you did not check. Say which half you
could not establish.

**A rule with no violating site is checked and clean.** Record it that way, by
name. This is the whole reason every rule gets a row in step 7's report: on a
report that lists only violations, a rule that passed and a rule that was never
looked at produce exactly the same silence, and the user asked specifically about
these rules.

Severity is the rule's own, from step 3. Do not raise it because a rule has many
sites, and do not lower it because you think the rule is fussy: the count is
already in the report, and the rule's wording is the user's judgement, not yours.

#### 6. Verify and Drop What Is Stale

`index.json` records each mapped file's `size` and `hash`. Compare them against
the files now.

- **A site in a file that has not changed** stands as it is.
- **A site in a file that has changed since mapping** is re-read and confirmed
  when `--read-code` is in force, and dropped when it is not. Count every drop.
- **A site whose `file:line` no longer holds what the finding says it holds** is
  dropped, whichever way it was found. A citation that does not survive being
  followed is worse than no citation.

Count the drops and the changed files, and put both in the report. A run over a
map that has gone stale is still worth reporting — a reader just has to be told
how stale.

#### 7. Write the Report Data

Write `Code_Flows/violations-report.json` first. It is the data; step 8's markdown
and HTML are two renderings of it, and writing a rendering first would let them
disagree.

```json
{
  "schema": 1,
  "meta": { "root": "C:/Users/example/project", "generated": "2026-09-02",
            "kind": "violations", "readCode": true, "mapGenerated": "2026-09-01",
            "mapMode": "whole-code-base", "mapDetail": "standard" },
  "coverage": { "rulesLoaded": 3, "rulesChecked": 2, "rulesNotCheckable": 1,
                "filesRead": 41, "filesChanged": 2, "findingsDropped": 0,
                "functionsCatalogued": 1180, "flowsTraced": 14,
                "entryPointsFound": 17, "flowsUnreadable": 0,
                "detectorsSkipped": [] },
  "rules": [
    { "ruleId": "R-01", "text": "Validation belongs in src/auth/ and nowhere else.",
      "source": "inline", "severity": "high", "scope": "all",
      "settledBy": "map", "checkable": true, "reason": "",
      "filesRead": 0, "filesInScope": 0, "status": "violated", "sites": 3 }
  ],
  "findings": [
    { "id": "RULES-01", "principle": "RULES", "detector": "rule-violation",
      "severity": "high", "confidence": "verified",
      "title": "Validation outside src/auth/",
      "rationale": "Three functions validate request input outside the one directory the rule names.",
      "rule": "Validation belongs in src/auth/ and nowhere else.",
      "ruleId": "R-01", "ruleSource": "inline",
      "sites": [ { "file": "src/api/handlers.py", "line": 88,
                   "symbol": "validate_payload", "snippet": "" } ],
      "suggestion": "Move these three into src/auth/ and call them from the handlers.",
      "effort": "medium" }
  ]
}
```

Every finding is a `rule-violation` finding in the shape the quality report
defines, field for field: `id`, `principle` (always `RULES` here), `detector`
(always `rule-violation`), `severity`, `confidence`, `title`, `rationale`,
`sites`, `suggestion`, `effort`, plus `rule`, `ruleId` and `ruleSource`. That is
not a coincidence to be tidied up later -- it is what lets both documents render
through the same page and read the same way. `confidence` is `verified` for a
site step 6 confirmed against current source and `unverified` for one settled
from the map alone.

`meta.kind` is `"violations"` — the shared report scaffold reads it to know that
this document checked rules rather than the five principles, and names only what
this run actually checked. Omitting it would make the page claim that twelve
detectors ran and found nothing.

`rules` carries **every rule loaded**, violated or not, with `status` one of
`violated`, `clean`, `partial` or `not-checked`, and `reason` filled in for
anything but `violated` and `clean`. `filesRead` and `filesInScope` are what make
a `partial` honest. `findings` carries one entry per violated rule, in the finding
shape the quality report uses, so the two documents render through the same page
and a reader learns one layout rather than two.

Order `findings` by `severity` descending, then by site count descending, then by
`ruleId`. Assign the `id` counters walking that order, after step 6's drops, so
they read `RULES-01`, `RULES-02` with no gaps.

`meta.root` is the one absolute path in the file; every path inside `rules` and
`findings` is repo-relative with forward slashes.

#### 8. Write the Report

**8a. The markdown.** Render `Code_Flows/violations-report.md` from the JSON you
just wrote. Nothing in it may contradict that file.

Lead with the **rule ledger** — this is a requirement, not a formatting
preference. Before any finding, one row per rule: its id, its text, where it came
from, its severity, and its status in words — "3 sites", "checked, clean", "not
checked: needs source and `--no-read-code` was passed", "partially checked: 40 of
900 files read". A reader who stops after the ledger should already know what was
and was not established.

Then the findings, in the order step 7 fixed, each with its rule quoted above its
sites.

Then the coverage: how many rules were loaded, checked and not checked; how many
files were read; how many mapped files have changed since the map was written; how
many sites were dropped as stale; and how many flows could not be read.

**8b. The page.** Read `.code-flow/report.template.html` and write
`Code_Flows/violations-report.html` as an **exact copy** of that template with two
tokens replaced. `__REPORT_DATA__` becomes the JSON object from step 7.
`__THEME_CSS__` becomes the contents of `.code-flow/theme.css`, or an empty string
if that file does not exist or cannot be read. Change nothing else. Inside every
string value, replace each `</` with `<\/` — a literal `</script>` would terminate
the data block.

If `.code-flow/report.template.html` does not exist, say so, skip the page, and
tell the user to reinstall `code-flow`. The JSON and the markdown are already
written and are the report; the page is a third rendering, not the deliverable.

Finally, report all three file paths to the user, with the rule ledger's headline:
how many rules were checked, how many were violated, and how many could not be
settled.
