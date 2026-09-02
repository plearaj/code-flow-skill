---
name: code-flow-map
description: Analyze and document the flow of a code feature, generating a markdown file and an interactive HTML page with flow diagrams and function reference tables.
argument-hint: "[functionality name] [--whole-code-base] [--detail thin|standard|verbose] [--output files|bundle|both] [--frontend auto|react|vue|angular|svelte|off] [--tracer auto|on|off]"
disable-model-invocation: true
---

## Code Flow — Documentation Generator

Analyze the codebase and generate flow documentation for the requested functionality.

### Before you write anything

Name the flow you are about to map and wait for the user to confirm it, unless their
own request already named it. This skill writes files under `Code_Flows/` and adds
docstrings to source files that lack them. Some hosts start a skill because a
conversation drifted near its description rather than because anyone asked for it,
and on those hosts this paragraph is the only thing standing between that drift and
an edit to the user's code.

### User Input

The user's request says what to map, and may carry five option flags —
`--whole-code-base`, `--detail thin|standard|verbose`, `--output files|bundle|both`,
`--frontend auto|react|vue|angular|svelte|off` and `--tracer auto|on|off`. Step 1
reads them.

### Instructions

#### 1. Identify the Target Flow

The user's request says what to document. Read it first for its option
flags. They are options, not part of the feature name — strip them out before you
derive any filename from what is left.

- `--whole-code-base` — map the whole repository instead of one feature. If it is
  present, skip the rest of this section and everything through step 7, and follow
  **Whole-Codebase Mode** at the end of this document instead.
- `--detail thin|standard|verbose` — how much evidence each catalogued function
  carries. Default `standard`. It only changes anything in whole-codebase mode; if
  it appears without `--whole-code-base`, accept it silently rather than erroring.
  If it appears with a value that is not one of those three, tell the user what you
  read, use `standard`, and carry on.
- `--output files|bundle|both` chooses which HTML gets written, default `files`.
  `files` writes `index.html`, one page per flow, and the quality report page,
  exactly as before. `both` adds `Code_Flows/code-flow.html`, a single
  self-contained page carrying every flow. `bundle` writes that page and no other
  HTML. If its value is not one of those three, say what you read, use `files`,
  and carry on. **`--output` never suppresses the JSON artifacts** —
  `index.json`, `<functionality_name>.json` and `inventory.json` are written in
  every mode, because `/code-flow-quality` reads them and a run that skipped
  them would break it silently. Unlike `--detail`, it changes behavior in both
  modes: in whole-codebase mode it governs the bundle exactly as it does here —
  see Whole-Codebase Mode's Pass 1 and Pass 2 for where that applies.
- `--frontend auto|react|vue|angular|svelte|off` — whether to map UI components
  as well as functions. Default `auto`: detect the frameworks this repository
  actually uses and map their components too. Naming one forces that framework;
  `off` maps functions only. **Frontend Component Mapping** below says what it
  changes. If its value is not one of those, say what you read, use `auto`, and
  carry on.
- `--tracer auto|on|off` — whether to run the installed static tracers before
  tracing anything. Default `auto`: run each tracer whose language this
  repository contains and whose interpreter this machine has, and read source
  yourself where none applies. `on` means say so and stop when no tracer could
  run, since a user who asked for a traced map would otherwise get a slower one
  silently. `off` never runs one. **Automated Tracing** below says what they
  produce and how far to trust it. If its value is not one of those three, say
  what you read, use `auto`, and carry on.

Everything from here through step 7 is **feature mode**, the default.

The remaining input describes the functionality to document. If it is empty,
analyze the project structure and suggest 3-5 key flows, then ask the user to pick
one.

Use the functionality name to derive the output filename. Convert to snake_case
(e.g., "user login" → `user_login.md`, "password reset" → `password_reset.md`).

#### 2. Discover Relevant Files and Functions

Find all code related to the target flow:
- Search for relevant files by name pattern
- Search for functions, classes, keywords, and entry points related to the flow
- Read discovered files to trace the call chain

If a tracer ran, start from its output instead of from search: find this flow's
entry function in `entryPoints[]` or `functions[]`, then walk `calls[]`
transitively to collect the flow. Read the source of every function you collect —
the tracer says what calls what, and you are describing what it does — and follow
`ambiguousCalls[]` by hand wherever the chain passes through one.

Trace the full execution path — follow function calls from entry point through to the final output. Include every function that participates in the flow.

#### 3. Document Undocumented Functions

For each function in the flow that lacks a docstring:
1. Analyze the function to understand its purpose, parameters, and return value
2. Generate a clear, concise docstring
3. Add the docstring to the function

#### 4. Generate the Markdown Documentation

Create `Code_Flows/<functionality_name>.md` with these sections:

**4a. Flow Description**
A brief description of the flow's purpose and when/how it is triggered.

**4b. Flow Diagram**
A MermaidJS flowchart or sequence diagram. Every function in the flow MUST appear as a named node.

Example:

```mermaid
flowchart TD
    A[entry_function] --> B[process_data]
    B --> C[transform]
    C --> D[output_result]
```

**4c. Function List**
A bullet list of ALL function names that appear in the flow diagram.

**4d. Function Reference Table**
A table with every function's description and exact file location:

| Function | Description | File |
|----------|-------------|------|
| `entry_function` | Entry point that initializes the pipeline | `src/module/main.py:23` |
| `process_data` | Validates and preprocesses input data | `src/module/data.py:45` |

The **File** column MUST include the file path and line number in `file:line` format.

#### 5. Generate the Interactive HTML View

By default, **also** produce a self-contained interactive HTML page next to the markdown. It renders the same flow as a browsable graph: pan/zoom, click a node for its description + `file:line` + code snippet, search functions, and highlight a path. The page is a single file with everything inlined — it works by double-clicking, with no internet or build step.

**5a. Build the flow-data JSON.** Assemble ONE JSON object describing the same flow you diagrammed in step 4:

```json
{
  "meta": {
    "feature": "User Login",
    "slug": "user_login",
    "description": "<the same plain-language description from 4a>",
    "generated": "<today's date, YYYY-MM-DD>",
    "root": "<absolute path to the project root, forward slashes>",
    "tool": "code-flow"
  },
  "nodes": [
    { "id": "src_web_views_login_view", "label": "login_view()", "file": "src/web/views.py", "line": 12, "kind": "entry", "description": "HTTP handler for POST /login.", "snippet": "def login_view(request):\n    ..." }
  ],
  "edges": [
    { "from": "src_web_views_login_view", "to": "src_auth_service_authenticate_user", "kind": "call", "label": "", "back": false }
  ]
}
```

Rules — follow these exactly, or the page will refuse to render:

- One node per function in the diagram. **Every `edge.from` and `edge.to` MUST match a node `id`.**
- `id` is derived from the node's own `file` and function name, so that the same function always gets the same `id` in every flow and downstream tools can join flow nodes against a function catalog. Derive it exactly like this: **(1)** take the repo-relative `file` path and drop the extension from its **last segment only** — the final `.` in the filename and everything after it, so `src/v2.1/handler.py` → `src/v2.1/handler`, and a filename with no dot loses nothing; **(2)** append `_` followed by the function's **unqualified** name — `authenticate`, never `User.authenticate` — which is the same name a function catalog records for it; **(3)** lowercase the whole string, replace every remaining character outside `[a-z0-9_]` (path separators, dots, dashes, spaces, anything else) with `_`, collapse each run of `_` into a single `_`, and trim any leading or trailing `_`. Example: `src/web/views.py` + `login_view` → `src_web_views_login_view`. If **the file itself** derives that same id for more than one function — same-named methods on two classes, an overload, or *two different names that slug to one string*, which is what `__add__` and `add`, a `Builder` constructor and its `builder()` factory, or `~Widget` and `Widget` all do — append `_l` and the line number of each one's own definition keyword — the `def`, `function`, `func` or `fn` line itself, never a decorator, annotation or comment line above it: `src_jobs_worker_run_l31` and `src_jobs_worker_run_l88`. Suffix every one of them, including the first. If two of them are on the **same line**, the line cannot separate them, so append `_` and the position of each among that line's same-id definitions, counting from 1 in source order: `src_ui_panel_x_l7_1`, `src_ui_panel_x_l7_2`. Decide all of that from the file's own contents, never from which nodes happen to be in this flow: an `id` must not change depending on what else you mapped.
- Two **different files** can derive the same `id` — `src/service.cpp` and `src/service.hpp`, since the rule drops the extension, or `distutils/_msvccompiler.py` and `distutils/msvccompiler.py`, since the leading `_` becomes a separator and collapses into the one before it. Where that happens, and only for the ids both files actually derived, append `_f` and each file's position among those paths, sorted, counting from 1: `src_service_describe_f1` for `src/service.cpp` and `src_service_describe_f2` for `src/service.hpp`. Leave every other function in both files alone. This is the one part of the rule that looks outside a single file, because the collision is between two of them; it is also rare, so if you are applying it to more than a handful of ids, re-read the paths.
- `kind` on a **node** is one of `entry` | `step` | `external` | `io` | `component` (default `step`). `entry` = where the flow starts; `external` = a third-party/library boundary; `io` = a DB/network/file side effect; `component` = a UI component rather than a plain function. This drives node color.
- **Exactly one** node MUST have `kind: entry`. If the flow has several plausible roots — two HTTP handlers, say — pick the one the user asked about, make that the `entry`, and mark the others `step`.
- `kind` on an **edge** is one of `call` | `async` | `conditional` | `render` (default `call`). `render` is a parent component drawing a child. Set `"back": true` on any edge that closes a loop or recursion (points back to an ancestor) so it is drawn as a routed dashed curve.
- All file paths use **forward slashes**, repo-relative. `meta.root` is the absolute project root with forward slashes (used only to build editor links).
- `snippet` is optional — a short excerpt (up to ~40 lines). **Inside every `snippet` string, replace each `</` with `<\/`** (a literal `</script>` would terminate the data block). No trailing commas anywhere.

**5b. Fill the template.** Read `.code-flow/viewer.template.html`. Write `Code_Flows/<functionality_name>.html` as an **exact copy** of that template with three tokens replaced and nothing else changed. `__FLOW_DATA__` becomes the JSON object from 5a. `__FLOW_INDEX__` becomes the `flows` array as it will stand after step 6b — read `Code_Flows/index.json` now, apply this flow's entry to a copy of its `flows` array, and use that; it drives the page's flow switcher. If `index.json` is missing or does not parse, leave `__FLOW_INDEX__` exactly as you found it: the page then hides the switcher and keeps its link to the index, which is the right behavior for a registry that is not there. `__THEME_CSS__` becomes the contents of `.code-flow/theme.css`, or an empty string if that file does not exist or cannot be read. The page self-validates on load: if the JSON is malformed or an edge points at a missing node, it shows a specific error card instead of a blank page — read it and fix the JSON.

**5c. Fallback if the template is missing.** If `.code-flow/viewer.template.html` does not exist (the skill was only partially installed), write this minimal page to `Code_Flows/<functionality_name>.html` instead, then tell the user to reinstall `code-flow` for the full interactive viewer:

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title><FEATURE> — Flow</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
<style>body{font-family:system-ui,sans-serif;margin:2rem;max-width:60rem}
.banner{background:#fff3cd;border:1px solid #e0c060;padding:.5rem .75rem;border-radius:6px}</style>
</head>
<body>
<p class="banner">Reduced interactive mode — reinstall <code>code-flow</code> for the full interactive viewer.</p>
<h1><FEATURE> — Flow</h1>
<pre class="mermaid">
<!-- paste the SAME mermaid source from step 4b here -->
</pre>
<script>mermaid.initialize({ startOnLoad: true });</script>
</body>
</html>
```

#### 6. Write the Machine-Readable Artifacts

These files are the contract consumed by `code-flow-quality`. They are not
optional, and they are not derived by parsing the generated HTML.

**6a. The flow sidecar.** Write `Code_Flows/<functionality_name>.json` containing
exactly the JSON object you built in step 5a — the same `meta`, `nodes`, and
`edges`. This is the same data embedded in the HTML page, written as a plain file
so downstream tools never have to parse markup.

**6b. The index.** Create or update `Code_Flows/index.json`. If it does not exist,
create it with this shape. If it does exist, read it, add or replace the entry for
this flow in `flows` (matching on `slug`), and write it back — preserving every
other entry and any existing `coverage` values you did not compute. If it exists
but does not parse as JSON, **stop**: do not overwrite it and do not regenerate
it. Report the file path and what is wrong with it to the user, and let them
repair or delete it — rewriting the file would silently discard the registry of
every flow mapped before this one.

```json
{
  "meta": { "root": "<absolute project root, forward slashes>",
            "generated": "<today, YYYY-MM-DD>", "mode": "feature", "schema": 1 },
  "coverage": { "flowsTraced": 1 },
  "flows": [
    { "slug": "user_login", "title": "User Login", "file": "user_login.json",
      "entry": "src_web_views_login_view", "nodes": 9 }
  ]
}
```

- `slug` is the snake_case functionality name. `title` is `meta.feature` from
  the sidecar's JSON object (step 5a). `file` is the sidecar's filename,
  relative to `Code_Flows/` — a bare filename, not a path.
- `entry` is the `id` of the one node whose `kind` is `entry` — step 5a requires
  exactly one.
- `nodes` is the count of entries in the flow's `nodes` array.
- `coverage.flowsTraced` is the length of `flows` after your update.
- Set `meta.mode` to `feature` — **unless the file already has
  `"mode": "whole-code-base"`, in which case leave `meta.mode` and `meta.detail`
  exactly as you found them.** Whole-codebase mode reuses this step, and rewriting
  the marker there would leave a whole-repository map claiming to be a
  single-feature one.

**6c. The index page.** `index.json` is the data; `Code_Flows/index.html` is how a
person reads it. Read `.code-flow/index.template.html` and write
`Code_Flows/index.html` as an **exact copy** of that template with two tokens
replaced. `__INDEX_DATA__` becomes the registry object you just wrote in 6b.
`__THEME_CSS__` becomes the contents of `.code-flow/theme.css`, or an empty
string if that file does not exist or cannot be read. Change nothing else in the
template. Inside every string value, replace each `</` with `<\/`, exactly as in
step 5a.

Do this **every time you write `index.json`** — here, and in whole-codebase mode's
pass 1. The two files are one artifact in two forms, and an `index.html` carried
over from an earlier run advertises a registry that no longer exists.

A flow page's switcher lists the registry as it stood when that page was written,
so a page written earlier does not know about flows mapped later. `index.html` is
rebuilt from the registry every run and is always current, which is why every page
links back to it.

If `.code-flow/index.template.html` does not exist (the skill was only partially
installed), skip `index.html`, leave any existing one untouched, and tell the user
to reinstall `code-flow` for the flow index. There is no fallback page here: the
registry is already readable as `index.json`, and a hand-built substitute would be
one more file to keep in step with it.

**6d. The bundle.** If `--output` is `bundle` or `both`, read
`.code-flow/bundle.template.html` and write `Code_Flows/code-flow.html` as an
**exact copy** with two tokens replaced. `__BUNDLE_DATA__` becomes `{"index": <the
object you just wrote to index.json>, "flows": [<the full JSON object for every
flow in the registry, read back from its sidecar>], "report": <the object in
Code_Flows/quality-report.json if that file exists and parses, otherwise null>}`.
`__THEME_CSS__` becomes the contents of `.code-flow/theme.css`, or an empty string
if that file does not exist or cannot be read — an absent theme is the normal
case and is never an error. Inside every string value, replace each `</` with
`<\/`, exactly as in step 5a.

Rebuild it from the sidecars every time, never by editing an existing bundle: the
JSON is the data and this page is one rendering of it, so a bundle is always
current by construction. If a sidecar is missing or does not parse, leave that
flow out, and say which and why in your step 7 report.

If `.code-flow/bundle.template.html` does not exist, say so and skip the bundle.
There is no fallback page here.

#### 7. Finalize

- Create the `Code_Flows/` directory if it doesn't exist
- Write `Code_Flows/<functionality_name>.md`, `.html`, and `.json`, plus `index.json`
  and `index.html`
- If `--output` was `bundle` or `both` and the bundle was written, also report
  `Code_Flows/code-flow.html`
- Report the markdown and HTML paths to the user, name `Code_Flows/index.html` as
  the page that lists every mapped flow, and mention that the JSON artifacts were
  updated

## Automated Tracing

Reading a repository function by function is what leaves a large map
half-finished. The installed tracers do that reading in one pass, and they are
the difference between a hundred flows traced in one session and ten.

Run them unless `--tracer off`. Nothing below depends on their being there: when
no tracer applies, every step still works by reading source, only slower.

### Which tracer, and how

`.code-flow/tracers/` holds one tracer per supported language. Run the ones whose
language this repository contains:

| Language | Command |
|---|---|
| Python | `python .code-flow/tracers/trace_python.py --root . --detail <detail> --out Code_Flows/trace-python.json` |
| TypeScript, JavaScript | `node .code-flow/tracers/trace_typescript.mjs --root . --detail <detail> --out Code_Flows/trace-typescript.json` |
| Rust | `python .code-flow/tracers/trace_rust.py --root . --detail <detail> --out Code_Flows/trace-rust.json` |
| Java | `python .code-flow/tracers/trace_java.py --root . --detail <detail> --out Code_Flows/trace-java.json` |
| C, C++, Objective-C, C# | `python .code-flow/tracers/trace_c_family.py --root . --detail <detail> --out Code_Flows/trace-c.json` |

Pass the `--detail` value the user passed you, so one flag governs snippet size
everywhere. A repository written in several of these languages runs several
tracers, into one file each; nothing merges them, and everything else here reads
them as one catalog. Every tracer but the TypeScript one runs under Python, so a
machine with a Python interpreter can trace four of the five.

A tracer that is missing, exits non-zero, or needs an interpreter this machine
does not have is not an error under `--tracer auto`: say which one did not run
and why, and carry on reading source for that language.

`.code-flow/tracers/README.md` documents the output in full. What matters here:

- `functions[]` — one entry per function, already shaped like an inventory entry:
  the same `id` rule, and the same `role`, `exported`, `owner`, `overrides`,
  `loc`, `signature`, `purpose` and `snippet` fields.
- `functions[].calls[]` — the call graph. `to` is another function's `id`, and
  `confidence` is `exact` or `heuristic`.
- `entryPoints[]` — where execution enters: routes, CLI commands, jobs, handlers,
  mounted applications. Each names an `id` and a `kind`.
- `components[]` and `routes[]` — the UI half, empty for a language with no UI.
- `ambiguousCalls[]` — the calls the tracer refused to guess, with their
  candidates. `externalCalls[]` — the ones that leave the repository. `limits` —
  what it cannot see at all.

### How far to trust it

A tracer is evidence, not the map. Three rules:

1. **Read the source of anything you describe.** A `purpose` the tracer inferred
   is where a flow description starts, not what it says.
2. **An `exact` call is a fact; a `heuristic` call is a claim.** Confirm a
   heuristic edge against the source before you draw it, and drop it when the
   source disagrees.
3. **What the tracer could not resolve is still there.** `ambiguousCalls` and
   `limits` name real calls, so a chain that passes through one is unfinished
   rather than finished. Follow it by reading, and say in your report where you
   could not.

Never present a traced map as complete. Say **catalogued** and **found**, never
"all" — a tracer is static analysis, and it sees no more of reflection, dynamic
dispatch or configuration-declared routes than search does.

## Frontend Component Mapping

A repository with a UI is two graphs, not one. Functions call functions;
components render components; the two meet where a handler or a hook calls into
the rest of the system. Mapping only the calls leaves the half of the system a
user actually touches undocumented.

This applies unless `--frontend off`, and only to the frameworks the repository
really uses — decided from `package.json` dependencies, then the config files
present, then the file extensions on disk. Under `--frontend auto` detect them;
when the user named one, use that one and say so if the repository disagrees.

### What a component is, per framework

| Framework | A component is | Its children come from | Its inputs are |
|---|---|---|---|
| React, Preact, Solid | a capitalized function or class that returns markup | the JSX tags in its body, resolved through the file's imports | destructured props, or the props type |
| Vue | a `.vue` file, or an options object carrying a `template` | the tags in its `<template>` block | `defineProps`, or the `props` option |
| Angular | a class decorated `@Component` | the selectors its template uses, inline or in `templateUrl` | `@Input()` members |
| Svelte | a `.svelte` file | the capitalized tags in its markup | `export let` declarations |

Record alongside each one: its outputs — `@Output()`s, emits, or callback props;
its lifecycle hooks and effects; the hooks, composables, stores or services it
depends on; and the route that reaches it, if any.

A custom hook, a composable and an injectable service are none of them
components, and filing them as components distorts the tree. Give them their own
`kind` — `hook`, `service`, `store` — and keep them in the graph, because that is
where a component's behavior actually lives.

### What to write

Components are catalogued in `inventory.json` by pass 1's step 1.2b, and drawn in
flows as nodes of `kind: "component"` joined by edges of `kind: "render"`.
Everything else about a flow is unchanged: one node per thing, ids by the same
rule, `file:line` on every node.

A UI flow is worth its own flow when it starts at a route or at a mounted
application root. Trace it as any other flow is traced — route, page component,
the components it renders, the hooks and handlers those call, and on into the
services and requests they reach — so that one flow shows a click arriving at the
server.

Where a tracer ran it has already done this: `components[]` carries each
component with its `children`, `inputs`, `outputs` and `hooks`, and `routes[]`
pairs a path with the component it renders.

## Whole-Codebase Mode

Reached only when the user passed `--whole-code-base`. Two passes: catalogue what
exists, then trace how it runs. The passes are separate because they answer
different questions and because the second one is far more expensive than the first.

**This mode never edits source files.** Feature mode adds docstrings as it goes
(step 3); at repository scale that would be a sweeping unrequested rewrite, so here
you only read. Report undocumented functions in the inventory's `purpose` field
instead — inferred from the body when there is no docstring.

### Pass 1 — Breadth: catalogue what exists

This pass traces nothing. It records what is there.

**1.1 Choose the files to scan.** Walk the repository from the project root,
honoring `.gitignore`. Skip in addition: `node_modules`, `.venv`, `venv`, `dist`,
`build`, `target`, `vendor`, `third_party`; lockfiles (`package-lock.json`,
`yarn.lock`, `uv.lock`, `poetry.lock`, `Cargo.lock`, `go.sum`); minified or
generated assets (`*.min.js`, `*.min.css`, `*.map`); and anything binary. Count every skip and attribute it to exactly one reason: `vendored` for code you
did not write (`node_modules`, `vendor`, `third_party`); `generated` for build
output and machine-written files (`dist`, `build`, `target`, lockfiles, minified
assets); `binary` for anything that is not text; `unparsed` for a file you opened
but could not read structure from. A `.gitignore` match is not itself a reason —
give the file the reason that fits what it is. If two fit, use the one listed
first here, so two runs over the same repository produce the same counts.

If a tracer ran, its `files[]` and `skipped[]` arrays are this census already —
same paths, same sizes, same hashes, same four skip reasons. Take them, and add
only what no tracer covered: a second language, and any file a tracer could not
parse.

**1.2 Catalogue the functions.** Write `Code_Flows/inventory.json` with one entry
per function or method you find:

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
      "calls": [
        { "to": "src_auth_normalize_normalize", "confidence": "exact" }
      ],
      "snippet": "def validate_email(value):\n    ..."
    }
  ]
}
```

- `id` — derived exactly as in step 5a, from the same `file` and unqualified
  `name`. This is the whole point of the pass: a flow node and the inventory entry
  for the same function carry the same `id`, and that join is what lets a later
  command compute which catalogued functions no flow ever reaches.
- `name` — the function's **unqualified** name, the same form the `id` rule uses:
  `send`, never `EmailGateway.send`.
- `line` — the line of the function's own definition keyword, never a decorator or
  comment above it. `loc` — its length in lines, definition line through last line
  inclusive.
- `nesting` — how deeply control flow nests inside the body: an `if` inside a `for`
  inside a `while` is 3, and a function whose statements all sit at the top of it
  is 0. Only blocks a control keyword opens count, so an object literal, a struct
  initialiser and a nested class are not levels; a nested function ends the count,
  because it is catalogued in its own right with its own. Present when a tracer
  produced it. Never confuse it with a function's distance from an entry point:
  that is a property of where the function sits, not of how it is written.
- `signature` — the declaration as written, on one line, without the body.
- `purpose` — one sentence. Use the docstring if there is one; otherwise infer it
  from the body. Do not edit the source file to add one.
- `role` — `"test"` if the file is a test (a `test_*`/`*_test`/`*.test.*`/`*.spec.*`
  name, or a `tests/`, `test/`, `spec/`, `__tests__/` directory), `"source"`
  otherwise. **Catalogue tests, never skip them.** Excluding them would make every
  helper that only tests use look unreachable.
- `exported` — whether the function is public API. A per-language heuristic, not a
  proof: the `export` keyword in JS/TS, a name without a leading underscore (and
  `__all__` membership where a module defines it) in Python, an initial capital in
  Go. **When the language or the convention is unclear, use `true`** — wrongly
  calling something private produces a false dead-code claim later, which is the
  more expensive mistake.
- `owner` — the unqualified name of the type that declares the function: a class,
  struct, trait, `impl` target, interface or `@implementation`. Omit it for a free
  function, as in the example above. Present when a tracer produced it, absent
  otherwise.
- `overrides` — the supertype declarations this function overrides, nearest first,
  each written `Supertype.member`, or `Supertype::member` where the language spells
  it that way. Like `calls`, a fact a tracer establishes rather than something to
  infer by reading: each tracer reads the relationship its own language states —
  `impl Trait for Type`, `extends`, `implements`, a base-class list — and names a
  supertype only where that supertype really declares the member, so a subclass
  method the parent never declared is not an override of anything. A supertype
  outside the repository is not named at all. It is a name rather than an `id`
  because half the declarations that matter — a Java interface method, a C++ pure
  virtual, an Objective-C protocol selector — have no body and so are never
  catalogued; where the declaration is catalogued, `owner` and `name` find it.
- `calls` — the functions this one calls, each an `id` in this same catalog and
  a `confidence` of `exact` or `heuristic`. Present when a tracer produced it,
  absent otherwise: it is a fact the tracer establishes, not something to infer
  by reading. It is also what makes pass 2 a graph walk instead of a second
  reading of the whole repository, which is the difference between finishing a
  large map and abandoning one.
- `snippet` — governed by `--detail`:

| `--detail` | `snippet` |
|---|---|
| `thin` | omit it entirely |
| `standard` (default) | include, capped at ~20 lines; omit for functions of 3 lines or fewer, since a trivial accessor tells a duplicate-detector nothing |
| `verbose` | include the full body, uncapped |

  Inside every `snippet`, replace each `</` with `<\/`, exactly as in step 5a.

If a tracer ran, this catalog is its `functions[]` array: copy `id`, `name`,
`file`, `line`, `loc`, `nesting`, `signature`, `purpose`, `role`, `exported`,
`owner`, `overrides`, `calls` and `snippet` straight across rather than deriving them
again. Read source only for
the entries you are about to describe in a flow, and for anything the tracer's
`limits` say it could not see. Catalogue what the tracer found *and* what it
says it missed; never report the first as if it were both.

**1.2b Catalogue the components.** Skip this if `--frontend off`, or if the
repository has no UI. Otherwise add a `components` array to the same
`inventory.json`, one entry per component, hook, store or service — see
**Frontend Component Mapping** for what counts as which, per framework:

```json
{
  "schema": 1,
  "functions": [],
  "components": [
    {
      "id": "src_pages_userlistpage_userlistpage",
      "name": "UserListPage",
      "file": "src/pages/UserListPage.tsx",
      "line": 6,
      "framework": "react",
      "kind": "page",
      "selector": null,
      "inputs": ["userId"],
      "outputs": ["onSelect"],
      "hooks": ["useUsers", "useEffect"],
      "children": ["src_components_usercard_usercard"],
      "exported": true
    }
  ]
}
```

- `id` — derived by the same rule as a function's, from the component's own
  `file` and unqualified name, so a component that is also a function (React,
  Vue, Svelte) carries one `id` in both arrays rather than two identities.
- `framework` — `react`, `vue`, `angular`, `svelte`, `solid` or `preact`,
  decided per file rather than per repository: a monorepo with an Angular admin
  app and a React storefront is one repository with two answers.
- `kind` — `component`, `page`, `layout`, `hook`, `service`, `store`,
  `directive`, `pipe` or `module`.
- `selector` — the Angular selector, or `null` where the framework has none.
- `inputs`, `outputs` — props and events, in the framework's own terms.
- `hooks` — lifecycle hooks, effects and the composables or services it depends on.
- `children` — the `id` of every component this one renders. This is the tree.

If a tracer ran, this is its `components[]` array, copied across, and its
`routes[]` array pairs a path with the component it renders.

**1.3 Record the file census.** In `Code_Flows/index.json`, set `meta.mode` to
`"whole-code-base"` and `meta.detail` to the level you used, then record one entry
per scanned file and the breadth half of `coverage`:

```json
{
  "meta": { "root": "<absolute project root, forward slashes>",
            "generated": "<today, YYYY-MM-DD>", "mode": "whole-code-base",
            "detail": "standard", "schema": 1 },
  "coverage": { "filesScanned": 214, "filesSkipped": 12,
                "skipReason": { "vendored": 9, "unparsed": 3 },
                "functionsCatalogued": 1180 },
  "files": [
    { "path": "src/auth/validators.py", "size": 4210, "hash": "sha256:9f2a1c" }
  ],
  "flows": []
}
```

The `flows` array and the rest of `coverage` belong to pass 2 — preserve whatever
is already there, and preserve every `coverage` value you did not compute. The
same rule as feature mode applies: if `index.json` exists but does not parse,
**stop**, report it, and do not overwrite it.

Step 6c applies here too: having written `index.json`, rewrite `Code_Flows/index.html`
from it. After pass 1 that page shows the census and says plainly that no flows have
been traced yet — which is what a half-finished map should look like. **Step 6d
applies here too**, on the same condition: if `--output` is `bundle` or `both`,
rebuild `Code_Flows/code-flow.html` from the census now — `flows` will be empty
until pass 2 traces some, which is a correct rendering of a half-finished map, not
an error.

`filesScanned` and `functionsCatalogued` describe the whole catalog, including files
carried forward unchanged from an earlier run — not only what this session re-read.
They are facts about the map, not about the session.

`hash` lets a later command warn that the map is stale without re-reading source.
Compute it with whatever the environment provides — `sha256sum <file>`,
`Get-FileHash -Algorithm SHA256 <file>`, or `certutil -hashfile <file> SHA256` —
and record `sha256:` followed by the first 6 hex characters. **If you cannot run
commands here, set `"hash": null` for every file and say so in your final report.
Never invent a hash value**; `size` alone still catches most edits.

**1.4 Resuming.** If `files` already lists a path whose `size` and `hash` are
unchanged, keep that file's existing `functions` entries and move on rather than
re-reading it. A repository too large to catalogue in one session is finished by
running the command again.

Before trusting `files[]`, read `Code_Flows/inventory.json`. If it is missing, or
exists but does not parse, ignore the census entirely and catalogue every file from
scratch — a census without a readable inventory would carry forward entries that are
no longer there, and the counts would describe a catalog that does not exist.

### Pass 2 — Trace: map the flows

**2.1 Find the entry points.** An entry point is where execution enters the system
from outside it: HTTP routes and their handlers, CLI commands and subcommands,
`main()`, event and queue handlers, scheduled jobs, and the exported public API.
Use the inventory you just built — `exported` is a strong hint — plus the framework
conventions the repository actually uses (route decorators, a router table, an
`argv` parser, a job registry).

If a tracer ran, `entryPoints[]` is this list: take it, and add anything the
conventions above show it missed. Its `routes[]` are entry points too — a route
is where a user enters the system.

Record how many you found as `coverage.entryPointsFound` **before you trace any of
them**. Recording it first is what makes an unfinished run visible: `flowsTraced`
below `entryPointsFound` means the map is partial.

**2.2 Trace each one.** For every entry point not already mapped, run feature mode's
steps 2, 4, 5 and 6 exactly as written, treating that entry point as the requested
flow — but **skip step 3**: this mode does not edit source.

Where the inventory carries `calls`, step 2 is a walk of that graph from the entry
point rather than a fresh read of the repository: the nodes are the functions you
reach, the edges are the calls you walked, and the reading you do is of the
functions you are about to describe. That is what makes tracing every entry point
in one pass possible; without it, a repository of any size runs out of room
part-way through and has to be finished by re-running. Each flow produces its
own `Code_Flows/<slug>.md`, `.html` and `.json`, and its own entry in `index.json`'s
`flows` array. Derive the slug from the entry point's own name.

Step 6 must leave `meta.mode` at `whole-code-base` and `meta.detail` as pass 1 set
them — it is the only step here that writes `meta`, and this mode depends on those
two values surviving every flow you trace.

**2.3 Skip what is already mapped.** Before tracing, check `index.json`'s `flows`
for that slug. If it is already there, skip it and move on — do not re-trace and do
not overwrite its files. This is what lets a repository be mapped across several
sessions: run the command again and it picks up where it stopped.

**2.4 Stop honestly.** A partial pass 2 is not an error. If you run out of room,
stop cleanly after finishing the flow you are on, leave `index.json` consistent, and
tell the user how many of the entry points you traced and that re-running continues
from there. Set `coverage.flowsTraced` to the length of `flows` — what you actually
did, never what you intended.

**2.5 Report.** Tell the user: the counts from `coverage`, where the artifacts are,
and — if `flowsTraced` is below `entryPointsFound` — that the map is partial and how
to finish it. Say **catalogued**, never "all": this discovery is search and reading,
not a compiler's view of the code, so it is best-effort by construction.
