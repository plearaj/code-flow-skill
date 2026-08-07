# Design: Phase 3 — `code-flow.quality` Reporting

**Date:** 2026-08-07
**Status:** Approved design, pending implementation plan
**Target versions:** 1.2.0 (phase 3a), 1.3.0 (phase 3b)
**Extends:** [`2026-08-06-dry-kiss-yagni-reporting-design.md`](2026-08-06-dry-kiss-yagni-reporting-design.md)

## Purpose of this document

The parent design approved `code-flow.quality` in full: the four detectors, their
severity thresholds, the finding schema, `--read-code`, the honesty rules, and
both report outputs. None of that is reopened here.

This addendum records what the parent left unsettled, and splits the phase. It is
a delta, not a replacement — where the two documents overlap, the parent governs.

## Phase split

The parent treats phase 3 as one unit. It is roughly twice phase 2: three new
command templates of prompt prose, a report viewer of real HTML, CSS and
JavaScript, installer changes in two languages, and new tests in three
categories. Those halves are different kinds of work and review differently, and
the first is useful without the second.

### Phase 3a — the quality command (1.2.0)

- `templates/claude/code-flow.quality.md`
- `templates/gemini/code-flow.quality.toml`
- `templates/copilot/code-flow.quality.prompt.md`
- Installer changes in `bin/install.js` and `src/code_flow_skill/cli.py`
- The four detectors and `--read-code`
- Outputs: `Code_Flows/quality-report.md` and `Code_Flows/quality-report.json`
- `examples/sample-report.json`

### Phase 3b — the report viewer (1.3.0)

- `templates/shared/report.template.html`, carrying exactly one
  `__REPORT_DATA__` token
- `Code_Flows/quality-report.html`, added to the quality command in all three
  hosts
- Installer changes to copy the new scaffold into `.code-flow/`
- Viewer-validation tests, which do not exist today for either scaffold

Both phases are additive within 1.x. Neither carries a breaking change.

### Installers are in scope, unlike phase 2

Phase 2 touched no installer code, because it changed only what the assistant is
told to produce. Phase 3 adds files to install, so both installers change. They
remain plain file copies — `--tool` semantics are unchanged, and each host simply
gains one more command file, plus one more shared scaffold in 3b. The two
installers' file lists must stay in step, and the installed-file-set tests in
both languages are what holds them there.

## `quality-report.json` is a first-class artifact

The parent's artifact listing names `quality-report.md` and
`quality-report.html`, but not the JSON between them — while simultaneously
specifying a `report.template.html` filled by substituting "the report JSON" into
a `__REPORT_DATA__` token. The JSON was always implied; it was never listed.

List it. `Code_Flows/quality-report.json` holds the ordered findings, the coverage
banner data, and the staleness counts, and it is written **before** the markdown,
which is rendered from it. This mirrors the map side, where `<flow>.json` is the
data and the `.md` and `.html` are two presentations of it.

It is also what makes the phase split clean: 3a produces the data and one
rendering of it; 3b adds a second rendering and changes nothing about the
analysis.

## Preconditions: the gating rule

The parent specifies which data each detector needs but not what happens when
that data is absent. One rule covers every case:

> A detector that cannot produce its required evidence does not run, and the
> report names it and says why.

Two situations trigger it, and they resolve differently because one leaves a
usable report and the other does not.

### Missing inventory — the command stops

A user who has only ever run feature mode has `index.json` and some
`<flow>.json` files but no `inventory.json`. Two of the four detectors —
duplicate-intent and unreached — cannot run at all.

`code-flow.quality` stops, reports that `Code_Flows/inventory.json` is absent,
and tells the user to run `/code-flow.map --whole-code-base` first.

Running the two flow-based detectors anyway was considered and rejected. Half the
detectors missing is not a degraded report; it is a different report, and one
whose meaning changes depending on how the user happened to build their map. A
command whose output means one thing is worth more than a command that always
produces something.

### Thin map without `--read-code` — one detector is skipped

At `--detail thin` the inventory carries no snippets. duplicate-intent then has
only signatures, purposes and line counts, which is not enough: the finding
schema requires snippet evidence per site, and name-level similarity is exactly
the confident-wrong finding the parent warns costs more trust than a missing one.

duplicate-intent is skipped. The other three detectors run, and the report states
that duplicate-intent was skipped because a thin map carries no snippets, naming
both remedies — re-run with `--read-code`, or re-map at `--detail standard`.

This is the reading the parent intended when it said to pair `thin` with
`--read-code`; it just never said what happens to someone who does not.

## Staleness: report, banner, and drop the affected findings

The parent requires that staleness be surfaced and says the report states how
many files changed. That is necessary but not sufficient: a finding whose cited
sites live in a changed file carries `file:line` evidence that is known to be
wrong, and `file:line` evidence is the report's entire currency.

So:

1. Staleness never stops the command. There is no threshold, because any
   threshold would be a number the design cannot justify.
2. The count of changed files is bannered at the top, alongside coverage.
3. An **unverified** finding with a cited site in a file whose hash no longer
   matches is dropped, and the count of dropped findings is bannered with the
   rest.

Findings on unchanged files are unaffected and still sound.

### Staleness interacts with `--read-code`, and verification wins

The drop rule applies to unverified findings only. `--read-code` opens current
source, so a finding it confirms has been checked against the very change that
made the file stale — dropping it afterwards would discard the best evidence in
the report.

So the order matters, and it is: verify first, then drop. With `--read-code`, a
candidate citing a changed file is re-read like any other; if it survives it is
marked `verified`, its `file:line` sites are corrected to current source, and it
is kept. If it does not survive, it was going to be dropped anyway.

The banner still reports how many files changed, because that is a fact about the
map the reader should know either way. But under `--read-code` the dropped-finding
count will typically be zero, and that is the flag working as intended: it turns
staleness from a reason to discard findings into a reason to re-check them.

## Data flow

```
read index.json
  → stop if inventory.json is absent
  → read inventory.json
  → read each <flow>.json registered in the index
  → compare files[].hash against current source
  → derive candidate findings per detector, honoring the gating rule
  → with --read-code: open only the files those candidates cite,
    confirm or drop each against current source, correcting file:line
  → drop any still-unverified finding citing a changed file
  → order by severity desc, site count desc, principle
  → write quality-report.json, then render quality-report.md from it
```

## Error handling

| Condition | Behavior |
|---|---|
| `index.json` missing | Stop; tell the user to run `/code-flow.map` first |
| `index.json` malformed | Stop; do not overwrite it; report the path and the problem |
| `inventory.json` missing | Stop; point at `/code-flow.map --whole-code-base` |
| `inventory.json` malformed | Stop; do not overwrite it; report the path and the problem |
| A `<flow>.json` missing or malformed | Skip that flow, count it, surface it in coverage; continue |
| No findings | Write a real report saying so, scoped to coverage |

The "stop, do not overwrite" rule for malformed registry files is not new — the
map command already follows it for `index.json`, on the grounds that rewriting
the file would silently discard every flow mapped before this run. The quality
command never writes those files at all, so for it the rule is simply that a file
it cannot parse is a file it cannot analyze.

The empty-findings case matters more than it looks. A report with no findings
under partial coverage means "clean within what was mapped", and the document
says that in words. It never implies a clean bill of health.

## No writes to source

Unchanged from the parent, and worth restating because it is the sharpest
difference between the two commands: `code-flow.map` edits source (it adds
missing docstrings); `code-flow.quality` produces documents only. Consolidating
duplicates and deleting suspected-dead code carry real blast radius, so this
command reports and stops.

## Testing

Three categories, all mechanical. The detectors themselves run inside an AI
assistant and cannot be unit tested — the same limitation phases 1 and 2
disclosed, unchanged here.

**Installer file-set tests.** Both languages, extended to assert the quality
command lands for each `--tool` value, and that a second run over an existing
install is a no-op producing identical bytes.

**Template contract tests.** Each quality template names all four detectors,
their severity thresholds, both output paths, both gating rules, and the honesty
phrasings. These use the generalized region helper phase 2 added, so assertions
anchor to a template section rather than the whole file.

**Fixture test.** `examples/sample-report.json` ships as a fixture and a test
asserts it obeys the finding schema — the same move `tests/test_node_ids.py`
makes for `sample-flow.json`, and for the same reason: a schema that lives only
in prompt prose is a schema nothing checks.

**Viewer validation (3b).** Substitute malformed JSON, and a finding citing a
missing flow, and assert the error card path triggers rather than a blank page.
This machinery does not exist today — `viewer.template.html` has only a
token-count contract test — so 3b builds it, and should retrofit it to the flow
viewer while it is there.

### Host parity for the new templates

Phase 2 inherited a 27-line Claude/Gemini divergence it could reduce but not
remove, because the two hosts genuinely differ on tool names, fence width, and
non-ASCII characters. The quality templates are new files with no such history.

Their baseline is measured in 3a's first task and held for every task after, and
it should start at or near zero: divergence is permitted only where one of those
three established classes forces it, and nowhere else. Copilot says the same
things in its own numbered-list register, as always.

Phase 1 lost four review rounds to host drift and phase 2 lost none. The
difference was writing each rule once as canonical text and applying it to three
hosts, rather than drafting per-host blocks. Phase 3 does the same.

## Deferred

`code-flow.violations` remains reserved and undesigned. The parent defers its
scope until `code-flow.quality` ships, and shipping has not happened yet.
