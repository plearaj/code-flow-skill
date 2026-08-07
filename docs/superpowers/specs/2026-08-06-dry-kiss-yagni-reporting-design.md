# Design: DRY/KISS/YAGNI Reporting and the `code-flow.*` Command Family

**Date:** 2026-08-06
**Status:** Approved design, pending implementation plan
**Target version:** 1.0.0 (major — breaking command rename)

## Summary

Add principle-based code quality reporting (DRY, KISS, YAGNI) to the Code Flow
skill, driven by a persisted map of the codebase rather than an ad-hoc scan.

This requires three things:

1. A whole-codebase mapping mode that produces a durable, machine-readable map.
2. A new analysis command that reads that map and reports violations.
3. A rename of the command surface into a `code-flow.*` family.

## Goals

- Report DRY, KISS, and YAGNI findings with concrete `file:line` evidence.
- Make the analysis trustworthy: state coverage honestly, and never present a
  judgement call as a verdict.
- Keep the existing per-feature flow documentation working unchanged.
- Stay parser-free and language-agnostic.

## Non-goals

- No automated fixes. The quality command reports; it does not edit code.
- No AST parsing, no language servers, no external analyzers.
- No inventory sharding. If a real repository makes `inventory.json`
  unmanageable, that is a follow-up informed by evidence, not a guess now.
- `code-flow.violations` is **reserved but not designed** here. Its scope will be
  defined after `code-flow.quality` ships.

## Background: why the architecture is shaped this way

The four chosen detectors do not all draw on the same data, and one of them
cannot work from flows at all.

Every function inside a flow map is by definition reached — being reached is what
put it in the flow. Detecting *unreached* code therefore requires a list of
functions that exists independently of the flows, so the unreached set can be
computed by subtraction. DRY duplicate-intent has the same blind spot: two copies
of a helper are only comparable if both were catalogued, even when only one sits
in a traced flow.

| Detector | Needs inventory | Needs flow graph |
|---|:--:|:--:|
| DRY — duplicate intent | yes | no |
| DRY — repeated call sequences | no | yes |
| KISS — complexity hotspots | no | yes |
| YAGNI — unreached code | yes | yes (the subtraction) |

Hence a two-pass map: a breadth pass that catalogues every function, and a trace
pass that follows call chains from entry points.

## Command surface (v1.0.0)

The skill installs a family of namespaced commands:

| Command | Purpose | Status |
|---|---|---|
| `code-flow.map` | Map a feature, or the whole codebase | Renamed from `code-flow` |
| `code-flow.quality` | DRY/KISS/YAGNI report from the map | New |
| `code-flow.violations` | Reserved | Not designed; not shipped in 1.0.0 |

### Invocation

```
code-flow.map user login                          # single feature (today's behavior)
code-flow.map --whole-code-base                   # full map, detail=standard
code-flow.map --whole-code-base --detail verbose  # full map, full function bodies
code-flow.quality                                 # analyze the map as-is
code-flow.quality --read-code                     # + verify findings against source
```

Flags are parsed by the assistant out of the command's arguments. The installer
CLI gains no new flags: it still only copies template files.

### Breaking change

`/code-flow` no longer exists; it becomes `/code-flow.map`. This is the reason for
the major version bump. The README must document the rename, and users upgrading
should delete the old `code-flow` command file — the installer writes new files
and does not remove the superseded one.

### Naming mechanism per host

Dotted command names are confirmed working, not assumed. GitHub Spec Kit ships
exactly this pattern, and its installed files were inspected on 2026-08-06:

| Host | File | Verified |
|---|---|---|
| Claude Code | `.claude/commands/code-flow.map.md` | Yes — `.claude/commands/speckit.analyze.md` observed |
| Gemini CLI | `.gemini/commands/code-flow.map.toml` | Yes — `.gemini/commands/speckit.analyze.toml` observed |
| Copilot | `.github/prompts/code-flow.map.prompt.md` | No local install available to inspect |

If a host rejects a dot, fall back to a dash (`code-flow-map`) rather than that
host's directory-based namespacing, so the command name reads the same
everywhere. Record any divergence in the README.

### Copilot uses prompt files

Copilot moves from appended prose in `.github/copilot-instructions.md` to prompt
files at `.github/prompts/<command>.prompt.md`. Prompt files are invocable, which
gives Copilot true parity with Claude and Gemini instead of ambient instructions
the model may or may not act on.

This also removes machinery rather than adding it: the idempotent-append logic
and its guard strings disappear from both installers, which become plain file
copies for all three hosts. That mattered more with each added capability —
ambient prose does not scale to three commands sharing one file.

`templates/copilot/code-flow.instructions.md` is deleted.

## Artifacts

All artifacts live under `Code_Flows/`.

```
Code_Flows/
  index.json            small: meta, coverage, file hashes, flow registry
  inventory.json        the function catalog
  <flow>.json           per-flow nodes + edges (new sidecar)
  <flow>.md             per-flow document (unchanged)
  <flow>.html           per-flow interactive viewer (unchanged)
  quality-report.md     the report
  quality-report.html   the report viewer
```

Report files are named for the report, not the command, so the future
`code-flow.violations` command can add `violations-report.*` alongside without
renaming anything.

`index.json` is kept separate from `inventory.json` so that coverage can be read
cheaply, and reported honestly, even when the inventory is large.

### `index.json`

```json
{
  "meta": {
    "root": "C:/Users/example/project",
    "generated": "2026-08-06",
    "mode": "whole-code-base",
    "detail": "standard",
    "schema": 1
  },
  "coverage": {
    "filesScanned": 214,
    "filesSkipped": 12,
    "skipReason": { "vendored": 9, "unparsed": 3 },
    "functionsCatalogued": 1180,
    "entryPointsFound": 17,
    "flowsTraced": 14
  },
  "files": [
    { "path": "src/auth/validators.py", "size": 4210, "hash": "sha256:9f2a1c" }
  ],
  "flows": [
    { "slug": "user_login", "title": "User Login", "file": "user_login.json",
      "entry": "src_web_views_login_view", "nodes": 9 }
  ]
}
```

`files[].hash` is a short content hash. It exists so `code-flow.quality` can warn
that the map is stale ("6 files changed since mapping") without reading source.

`mode` is `whole-code-base` or `feature`. `coverage.flowsTraced` less than
`coverage.entryPointsFound` means the trace pass is incomplete.

### `inventory.json`

```json
{
  "schema": 1,
  "functions": [
    {
      "id": "src_auth_validators_validate_email",
      "name": "validate_email",
      "file": "src/auth/validators.py",
      "line": 12,
      "loc": 14,
      "signature": "validate_email(value: str) -> bool",
      "purpose": "Return True if value looks like an email address.",
      "role": "source",
      "exported": false,
      "snippet": "def validate_email(value):\n    ..."
    }
  ]
}
```

- `id` is derived from `file` + `name`, normalized to `[a-z0-9_]`. Flow nodes
  carry the same `id`, and that join is how `inventory − reachable` is computed.
- `role` is `source` or `test`.
- `exported` marks public API surface and caps YAGNI severity (see below). It is
  a per-language heuristic, not a proof: the `export` keyword in JS/TS, absence
  of a leading underscore plus `__all__` membership in Python, capitalization in
  Go. When the language or convention is unclear, default to `true`, because the
  cost of wrongly assuming private is a false dead-code finding.
- `snippet` presence is governed by `--detail`.

### `--detail` levels

A single three-valued flag, rather than separate `--thin`/`--verbose` booleans,
which would leave `--thin --verbose` undefined.

| Level | Inventory entry carries | Intended use |
|---|---|---|
| `thin` | signature, purpose, `loc`; no snippet | Very large repos; pair with `--read-code` |
| `standard` (default) | + snippet capped at ~20 lines | The balanced default |
| `verbose` | + full body, uncapped | Small/medium repos; self-contained artifacts |

At `standard`, snippets are skipped for functions of 3 lines or fewer, since a
trivial accessor contributes nothing to duplicate detection.

Two combinations are worth documenting for users: `thin` with `--read-code`
(small artifacts, evidence fetched on demand), and `verbose` alone (fully
self-contained, analyzable without the source tree present).

### Per-flow sidecar

`<flow>.json` contains the same `nodes`/`edges` object already embedded in the
generated HTML. The duplication is deliberate: the HTML is a presentation format,
and parsing data back out of it would couple `code-flow.quality` to the viewer's
markup.

## `code-flow.map`

### Feature mode (default)

Unchanged from current behavior, with one addition: it also writes the
`<flow>.json` sidecar and registers the flow in `index.json`, creating both files
if absent. Existing users see no behavioral change beyond the extra files.

### Whole-codebase mode

**Pass 1 — breadth (inventory).** Walk the repository honoring `.gitignore` plus
a default exclude list (`node_modules`, `.venv`, `dist`, `build`, vendored
directories, lockfiles, minified assets). Catalogue every function and method
into `inventory.json`. Record each scanned file's size and hash into
`index.json`. This pass traces nothing.

**Pass 2 — trace (flows).** Discover entry points — HTTP routes and handlers, CLI
commands, `main()`, event and queue handlers, exported public API, scheduled jobs
— and trace each call chain using the existing flow procedure, emitting
`<slug>.json`, `<slug>.md`, and `<slug>.html` per flow and registering each in
`index.json`.

### Test handling

Test files are catalogued with `"role": "test"`, not excluded. Excluding them
would make every test-only helper look unreachable and produce a large class of
false YAGNI findings. Reachability therefore yields two distinct outcomes:

- **unreached** — reached by no flow and no test; a genuine dead-code candidate.
- **production-unreached** — reached only from test files; reported separately,
  phrased as "kept alive only by its own tests", never rated HIGH.

### Bounding and idempotency

Pass 2 is the expensive pass and may exceed a single session on a large
repository. Therefore:

- The run is idempotent: re-running skips flows already registered in
  `index.json`, so a large repository can be mapped across several sessions.
- `coverage` always records what was actually done, never what was intended.
- A partial pass 2 is not an error. It is recorded and surfaced downstream.

### Honesty about completeness

Discovery is Glob/Grep/Read, not an AST walk. The catalog is best-effort, and
reports must say "catalogued", never "all".

## `code-flow.quality`

Reads `index.json`, then `inventory.json`, then each `<flow>.json`.

### Detectors

| Detector | Principle | HIGH when | Evidence cited |
|---|---|---|---|
| duplicate-intent | DRY | ≥3 sites, or ≥40 duplicated LOC | Side-by-side snippets, every site |
| repeated-sequence | DRY | Chain of ≥3 calls in ≥2 flows | The shared subpath, flow slugs |
| complexity-hotspot | KISS | fan-out ≥8, or depth ≥6, or `loc` ≥120 | The metric and its value |
| unreached | YAGNI | Unreached, not exported, not test-only | Zero inbound edges across N flows |

Severity is rule-based rather than impressionistic, so findings do not all drift
toward "medium". Sites belonging to one cluster produce a single finding with
several sites, never pairwise findings.

### Finding schema

```json
{
  "id": "DRY-01",
  "principle": "DRY",
  "detector": "duplicate-intent",
  "severity": "high",
  "confidence": "verified",
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

`confidence` is `verified` only when `--read-code` confirmed the finding against
current source; otherwise `unverified`. Findings are ordered by severity
descending, then site count descending, then principle. Ids are stable within a
run so the markdown and HTML cross-reference each other.

### `--read-code`

Verification of candidates, not a second scan of the repository. Scanning
everything again would duplicate the cost of mapping and would not fit on a large
codebase.

```
1. Read the map and derive candidate findings.
2. Open only the files those candidates cite.
3. Confirm or drop each candidate against real current source.
4. Report, marking each finding verified or unverified.
```

This is the feature's main defense against false positives. DRY duplicate-intent
and KISS hotspots are judgement calls, and a confident wrong finding costs more
trust than a missing one.

With `--read-code`, the command requires the source tree to be present and
current, not merely the artifacts. This is documented as a property of the flag.

### Honesty rules

These are requirements, not style preferences. They are where this class of
report normally fails.

1. **Unreached is a candidate, never a verdict.** Parser-free tracing cannot see
   dynamic dispatch: reflection, `getattr`, dependency injection, framework
   hooks, decorator registration, entry points declared in configuration. YAGNI
   findings are phrased "not reached by any of the N mapped flows — confirm
   before deleting". Anything marked `exported` is capped at LOW. The report
   never instructs deletion.
2. **Coverage leads the report.** If pass 2 traced 14 of 17 entry points, the top
   of the report says so. A clean DRY section under partial coverage means "clean
   within what was mapped", and the document must say that in words rather than
   implying a clean bill of health.
3. **Staleness is surfaced.** If `files[].hash` no longer matches, the report
   says how many files changed since mapping.

### No writes

`code-flow.quality` produces documents only. This differs deliberately from
`code-flow.map`, which does edit source (it adds missing docstrings).
Consolidating duplicates and deleting suspected-dead code carry real blast
radius, so this command reports and stops.

## Outputs

### `quality-report.md`

Coverage and staleness banner, then summary counts by principle and severity,
then findings grouped by principle. Each finding renders its id, title, severity,
confidence, rationale, sites table, suggestion, and effort.

### `quality-report.html`

A second scaffold, `report.template.html`, using the mechanism already proven by
the flow viewer: installed into `.code-flow/`, containing exactly one
`__REPORT_DATA__` token, filled by substituting the report JSON, and
self-validating into an explicit error card rather than a blank page.

Capabilities: filter by principle, severity, and confidence; click a finding to
see its sites with snippets; `file:line` links out to the editor; findings citing
a flow link to that flow's existing HTML page.

## Repository change: remove the template mirror

`templates/` and `src/code_flow_skill/templates/` currently hold byte-identical
copies of all four template files. npm packages the first, Python packaging the
second. There is no sync script and no drift check; they match today only through
manual discipline. This was verified on 2026-08-06: all four files diff clean.

After this change each host has one file per command, plus two shared scaffolds:
two Claude commands, two Gemini commands, two Copilot prompt files,
`viewer.template.html`, and `report.template.html`. That raises the duplication
from 4 mirrored files to 8, in the very tool that is shipping DRY detection.

**Resolution:** delete the `src/code_flow_skill/templates/` mirror and make root
`templates/` the single source, letting hatchling place it into the wheel:

```toml
[tool.hatch.build.targets.wheel.force-include]
"templates" = "code_flow_skill/templates"
```

`cli.py` reads templates through `importlib.resources`, which continues to work
unchanged because the files still land at `code_flow_skill/templates/` inside the
built wheel. Implementation must verify the built wheel actually contains them
and that `uvx` installation still resolves them.

**Fallback if force-include proves unworkable:** keep both trees, add a
`sync-templates` script, and add a CI check that fails on drift. This polices the
duplication instead of removing it and is strictly worse, but better than relying
on discipline.

## Installer changes

Both installers simplify to the same shape, and their template lists must stay in
step:

- Every host is now a plain file copy: one file per command into that host's
  command directory, plus both shared scaffolds into `.code-flow/`.
- The Copilot special case is deleted — no read-modify-write, no guard strings,
  no idempotency logic. Copying a prompt file is idempotent by construction.
- `--tool` semantics are unchanged.

This is a net reduction in installer code despite doubling the number of
installed files.

## Testing

The repository currently has no tests. The detectors run inside an AI assistant
and cannot be unit tested conventionally, but the mechanical surface can be, and
should be:

- **Installer smoke tests**, npm and Python: install into a temporary directory,
  assert every expected file lands for each `--tool` value, and assert a second
  run over an existing install is a no-op producing identical bytes.
- **Template contract tests:** `report.template.html` contains exactly one
  `__REPORT_DATA__` token; `viewer.template.html` contains exactly one
  `__FLOW_DATA__` token; each command template names the artifacts it must write.
- **Viewer validation tests:** substitute malformed JSON, and a finding citing a
  missing flow, and assert the error card path triggers rather than a blank page.
- **Fixture example:** add `examples/sample-report.json`, mirroring the existing
  `examples/sample-flow.json`, so the report viewer can be opened and inspected
  without running an analysis.

## Implementation phasing

This is one coherent feature but a large one, and it should not land as a single
change. Three phases, each independently verifiable:

1. **Foundation** — rename to `code-flow.map`, remove the template mirror, emit
   the `<flow>.json` sidecar and `index.json` from feature mode, add installer
   smoke tests. Ships working software; no new analysis yet.
2. **Whole-codebase mapping** — `--whole-code-base`, `--detail`, `inventory.json`,
   file hashes, test roles, idempotent re-runs.
3. **Quality reporting** — `code-flow.quality`, the four detectors,
   `--read-code` verification, `report.template.html`, and both report outputs.

Phase 1 carries the breaking change, so the major version bump happens there and
phases 2 and 3 are additive within 1.x.

## Migration

- Version 1.0.0.
- `/code-flow` becomes `/code-flow.map`. Users must remove the superseded command
  file; the installer does not delete it.
- Copilot users must delete the `## Code Flow — Documentation Generator` section
  from `.github/copilot-instructions.md` by hand. The installer will not edit
  that file any more, so a stale section would otherwise linger and contradict
  the new prompt files. The README must call this out explicitly.
- Artifacts are additive. An existing `Code_Flows/` directory from 0.2.0 keeps
  working; `index.json` and `inventory.json` are created on the next map run, and
  flows mapped before 1.0.0 have no `.json` sidecar until re-mapped.
- `code-flow.quality` degrades honestly against a partial or legacy map: it
  reports what coverage it has and states what is missing.

## Open items

1. Copilot prompt-file naming (`.github/prompts/<command>.prompt.md`) is taken
   from GitHub Spec Kit's convention but was not verifiable against a local
   install. Confirm during phase 1; fall back to a dash if a dot is rejected.
2. `force-include` packaging must be verified against a built wheel and a `uvx`
   install.
3. `code-flow.violations` is reserved. Its design follows after
   `code-flow.quality` ships.
