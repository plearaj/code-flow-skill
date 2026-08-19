---
agent: agent
description: Analyze and document the flow of a code feature, generating a markdown file and an interactive HTML page with flow diagrams and function reference tables.
---

Analyze the codebase and document the execution flow of the requested functionality (e.g., "the user login flow").

Follow these steps exactly:

1. **Read the request for option flags first.** `--whole-code-base` maps the whole repository instead of one feature — if it is there, ignore steps 2-7 and follow "Whole-codebase mode" at the end of this prompt. `--detail thin|standard|verbose` sets how much evidence each catalogued function carries, default `standard`; it only matters in whole-codebase mode, so accept it silently otherwise, and if its value is not one of those three, say what you read, use `standard`, and carry on. `--output files|bundle|both` chooses which HTML gets written, default `files`: `files` writes `index.html`, one page per flow, and the quality report page, exactly as before; `both` adds `Code_Flows/code-flow.html`, a single self-contained page carrying every flow; `bundle` writes that page and no other HTML. If its value is not one of those three, say what you read, use `files`, and carry on. **`--output` never suppresses the JSON artifacts** — `index.json`, `<functionality_name>.json` and `inventory.json` are written in every mode, because `/code-flow.quality` reads them and a run that skipped them would break it silently. Unlike `--detail`, `--output` changes behavior in both modes: in whole-codebase mode it governs the bundle exactly as it does here — see "Whole-codebase mode" below, Pass 1 and Pass 2, for where that applies. `--frontend auto|react|vue|angular|svelte|off` says whether to map UI components as well as functions, default `auto`: detect the frameworks this repository actually uses and map their components too; naming one forces that framework, `off` maps functions only — see "Frontend component mapping" below. `--tracer auto|on|off` says whether to run the installed static tracers before tracing anything, default `auto`: run each tracer whose language this repository contains and whose interpreter this machine has, and read source yourself where none applies; `on` means say so and stop when no tracer could run, `off` never runs one — see "Automated tracing" below. For either, if the value is not one of those, say what you read, use the default, and carry on. Flags are options, not part of the feature name — strip them out. Then **identify the target flow** from what is left and derive a snake_case filename (e.g. "user login" → `user_login.md`). If no functionality was named, analyze the project structure, suggest 3-5 key flows, and ask the user to pick one before going any further. Steps 2-7 are feature mode, the default.
2. **Discover relevant files and functions** — if a tracer ran, start from its output rather than from search: find this flow's entry function in `entryPoints[]` or `functions[]`, walk `calls[]` transitively to collect the flow, read the source of every function you collect, and follow `ambiguousCalls[]` by hand wherever the chain passes through one. Otherwise search by file patterns and grep for keywords, then trace the call chain. Trace the full execution path from entry point through to the final output, and include every function that participates in the flow.
3. **Document undocumented functions** — add docstrings to any function in the flow that lacks one.
4. **Generate `Code_Flows/<functionality_name>.md`** containing:
   - Flow description
   - MermaidJS flow diagram (every function as a named node)
   - Bullet list of all function names in the flow
   - Function reference table with columns: Function, Description, File (`file:line` format)
5. **Generate `Code_Flows/<functionality_name>.html`** — an interactive, self-contained page of the same flow (see below).
6. **Write the machine-readable artifacts.** These are the contract consumed by `code-flow.quality`; they are not optional. Write `Code_Flows/<functionality_name>.json` containing exactly the flow-data JSON object used in step 5. Then create or update `Code_Flows/index.json`, adding or replacing this flow's entry in its `flows` array (matched on `slug`) while preserving all other entries — and any `coverage` values you did not compute this run. If `Code_Flows/index.json` exists but does not parse as JSON, **stop**: do not overwrite it and do not regenerate it. Report the file path and what is wrong with it to the user and let them repair or delete it — rewriting the file would silently discard the registry of every flow mapped before this one. Each entry holds `slug`, `title`, `file`, `entry`, and `nodes`: `title` is `meta.feature` from the sidecar's JSON object (step 5), `file` is the sidecar's filename relative to `Code_Flows/` (a bare filename, not a path), `entry` is the `id` of the one node whose `kind` is `entry` (exactly one node has it), and `nodes` is the count of entries in the flow's `nodes` array. The file also carries `meta` (`root`, `generated`, `mode`, `detail`, `schema: 1`) and `coverage.flowsTraced`, set to the length of `flows` after your update. Set `meta.mode` to `"feature"` — **unless the file already has `"mode": "whole-code-base"`, in which case leave `meta.mode` and `meta.detail` exactly as you found them.** Whole-codebase mode reuses this step, and rewriting the marker there would leave a whole-repository map claiming to be a single-feature one. Then write `Code_Flows/index.html` from the registry you just wrote — see **The index page** below. Do that **every time you write `index.json`**: the two are one artifact in two forms, and an `index.html` carried over from an earlier run advertises a registry that no longer exists.
7. **Report the markdown and HTML paths** to the user, name `Code_Flows/index.html` as the page that lists every mapped flow, mention that the JSON artifacts were updated, and — if `--output` was `bundle` or `both` and the bundle was written — also report `Code_Flows/code-flow.html`.

### Interactive HTML view

By default, also produce a self-contained interactive HTML page next to the markdown — a browsable graph (pan/zoom, click a node for its description + `file:line` + code snippet, search, path highlight). It is a single file with everything inlined and works by double-clicking, with no internet or build step.

**a. Build the flow-data JSON** — one object describing the same flow:

```json
{
  "meta": {
    "feature": "User Login",
    "slug": "user_login",
    "description": "<same plain-language description as the markdown>",
    "generated": "<today's date, YYYY-MM-DD>",
    "root": "<absolute project root, forward slashes>",
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

Rules (follow exactly or the page refuses to render):
- One node per function. **Every `edge.from`/`edge.to` MUST match a node `id`.**
- `id` is derived from the node's own `file` and function name, so that the same function always gets the same `id` in every flow and downstream tools can join flow nodes against a function catalog. Derive it exactly like this: **(1)** take the repo-relative `file` path and drop the extension from its **last segment only** — the final `.` in the filename and everything after it, so `src/v2.1/handler.py` → `src/v2.1/handler`, and a filename with no dot loses nothing; **(2)** append `_` followed by the function's **unqualified** name — `authenticate`, never `User.authenticate` — which is the same name a function catalog records for it; **(3)** lowercase the whole string, replace every remaining character outside `[a-z0-9_]` (path separators, dots, dashes, spaces, anything else) with `_`, collapse each run of `_` into a single `_`, and trim any leading or trailing `_`. Example: `src/web/views.py` + `login_view` → `src_web_views_login_view`. If **the file itself** defines more than one function with that name — same-named methods on two classes, or an overload — append `_l` and the line number of the function's own definition keyword — the `def`, `function`, `func` or `fn` line itself, never a decorator, annotation or comment line above it: `src_jobs_worker_run_l31` and `src_jobs_worker_run_l88`. Decide that from the file's own contents, never from which nodes happen to be in this flow: an `id` must not change depending on what else you mapped.
- Node `kind` ∈ `entry` | `step` | `external` | `io` | `component` (default `step`). `entry` = where the flow starts; `external` = a third-party/library boundary; `io` = a DB/network/file side effect; `component` = a UI component rather than a plain function. This drives node color. **Exactly one** node MUST have `kind: entry`; if the flow has several plausible roots, pick the one the user asked about and mark the rest `step`. Edge `kind` ∈ `call` | `async` | `conditional` | `render` (default `call`); `render` is a parent component drawing a child. Set `"back": true` on edges that close a loop/recursion.
- File paths use **forward slashes**, repo-relative; `meta.root` is the absolute root, forward slashes.
- `snippet` is optional (≤ ~40 lines). **Replace each `</` with `<\/` inside every snippet.** No trailing commas.

**b. Fill the template** — read `.code-flow/viewer.template.html` and write `Code_Flows/<functionality_name>.html` as an exact copy with three tokens replaced and nothing else changed. `__FLOW_DATA__` becomes the JSON. `__FLOW_INDEX__` becomes the `flows` array as it will stand after step 6 — read `Code_Flows/index.json` now, apply this flow's entry to a copy of its `flows` array, and use that; it drives the page's flow switcher. If `index.json` is missing or does not parse, leave `__FLOW_INDEX__` exactly as you found it: the page then hides the switcher and keeps its link to the index, which is right for a registry that is not there. `__THEME_CSS__` becomes the contents of `.code-flow/theme.css`, or an empty string if that file does not exist or cannot be read. The page self-validates and shows a specific error card (not a blank page) if the JSON is malformed or an edge is dangling.

**c. Fallback** — if `.code-flow/viewer.template.html` is missing (the skill was only partially installed), write this minimal page to `Code_Flows/<functionality_name>.html` instead, then tell the user to reinstall `code-flow` for the full interactive viewer:

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
<!-- paste the SAME mermaid source from the markdown diagram here -->
</pre>
<script>mermaid.initialize({ startOnLoad: true });</script>
</body>
</html>
```

### The index page

`index.json` is the data; `Code_Flows/index.html` is how a person reads it. Read `.code-flow/index.template.html` and write `Code_Flows/index.html` as an exact copy with two tokens replaced. `__INDEX_DATA__` becomes the registry object you just wrote. `__THEME_CSS__` becomes the contents of `.code-flow/theme.css`, or an empty string if that file does not exist or cannot be read. Change nothing else. Inside every string value, replace each `</` with `<\/`, exactly as in a snippet.

A flow page's switcher lists the registry as it stood when that page was written, so a page written earlier does not know about flows mapped later. `index.html` is rebuilt from the registry every run and is always current, which is why every page links back to it.

If `.code-flow/index.template.html` is missing (the skill was only partially installed), skip `index.html`, leave any existing one untouched, and tell the user to reinstall `code-flow` for the flow index. There is no fallback page here: the registry is already readable as `index.json`, and a hand-built substitute would be one more file to keep in step with it.

### The bundle

If `--output` is `bundle` or `both`, read `.code-flow/bundle.template.html` and write `Code_Flows/code-flow.html` as an exact copy with two tokens replaced. `__BUNDLE_DATA__` becomes `{"index": <the object you just wrote to index.json>, "flows": [<the full JSON object for every flow in the registry, read back from its sidecar>], "report": <the object in Code_Flows/quality-report.json if that file exists and parses, otherwise null>}`. `__THEME_CSS__` becomes the contents of `.code-flow/theme.css`, or an empty string if that file does not exist or cannot be read — an absent theme is the normal case and is never an error. Inside every string value, replace each `</` with `<\/`, exactly as in a snippet.

Rebuild it from the sidecars every time, never by editing an existing bundle: the JSON is the data and this page is one rendering of it, so a bundle is always current by construction. If a sidecar is missing or does not parse, leave that flow out, and say which and why in your final report.

If `.code-flow/bundle.template.html` does not exist, say so and skip the bundle. There is no fallback page here.

### Output Location

All outputs go in `Code_Flows/` at the project root — create that directory if it does not exist. Which HTML pages get written depends on `--output` (step 1): the markdown document, the flow sidecar, and the index registry are never optional; the per-flow interactive page and `index.html` are written unless `--output` is `bundle`, in which case the bundle page replaces them and they are skipped; the bundle itself is written only when `--output` is `bundle` or `both`.

- `Code_Flows/<functionality_name>.md` — the flow document (step 4). Always written.
- `Code_Flows/<functionality_name>.html` — the interactive page (step 5). Written unless `--output` is `bundle`.
- `Code_Flows/<functionality_name>.json` — the flow sidecar (step 6). Always written.
- `Code_Flows/index.json` — the shared flow registry, created or updated in place, never rewritten from scratch (step 6). Always written.
- `Code_Flows/index.html` — the flow index, rebuilt from that registry every time it is written (step 6). Written unless `--output` is `bundle`.
- `Code_Flows/code-flow.html` — the bundle, written only when `--output` is `bundle` or `both` (see "The bundle" above).

## Automated tracing

Reading a repository function by function is what leaves a large map half-finished. The installed tracers do that reading in one pass, and they are the difference between a hundred flows traced in one session and ten. Run them unless `--tracer off`; nothing here depends on their being present, and when none applies every step still works by reading source, only slower.

`.code-flow/tracers/` holds one tracer per supported language. Run the ones whose language this repository contains, passing the `--detail` value the user passed you:

| Language | Command |
|---|---|
| Python | `python .code-flow/tracers/trace_python.py --root . --detail <detail> --out Code_Flows/trace-python.json` |
| TypeScript, JavaScript | `node .code-flow/tracers/trace_typescript.mjs --root . --detail <detail> --out Code_Flows/trace-typescript.json` |
| Rust | `python .code-flow/tracers/trace_rust.py --root . --detail <detail> --out Code_Flows/trace-rust.json` |
| Java | `python .code-flow/tracers/trace_java.py --root . --detail <detail> --out Code_Flows/trace-java.json` |
| C, C++, Objective-C, C# | `python .code-flow/tracers/trace_c_family.py --root . --detail <detail> --out Code_Flows/trace-c.json` |

A repository written in several of these runs several tracers, into one file each; nothing merges them, and everything else reads them as one catalog. Every tracer but the TypeScript one runs under Python. A tracer that is missing, exits non-zero, or needs an interpreter this machine does not have is not an error under `--tracer auto`: say which one did not run and why, and carry on reading source for that language.

`.code-flow/tracers/README.md` documents the output in full. What matters here: `functions[]` is one entry per function, already shaped like an inventory entry; `functions[].calls[]` is the call graph, each `to` naming another function's `id` with a `confidence` of `exact` or `heuristic`; `entryPoints[]` is where execution enters; `components[]` and `routes[]` carry the UI half; `ambiguousCalls[]` are the calls it refused to guess, `externalCalls[]` the ones that leave the repository, and `limits` is what it cannot see at all.

**A tracer is evidence, not the map.** Read the source of anything you describe — a `purpose` it inferred is where a description starts, not what it says. An `exact` call is a fact; a `heuristic` call is a claim, so confirm it against the source before drawing it and drop it when the source disagrees. `ambiguousCalls` and `limits` name real calls, so a chain passing through one is unfinished rather than finished: follow it by reading, and say in your report where you could not. Never present a traced map as complete — say **catalogued** and **found**, never "all".

## Frontend component mapping

A repository with a UI is two graphs, not one. Functions call functions; components render components; the two meet where a handler or a hook calls into the rest of the system. Mapping only the calls leaves the half of the system a user actually touches undocumented.

This applies unless `--frontend off`, and only to the frameworks the repository really uses — decided from `package.json` dependencies, then the config files present, then the file extensions on disk.

| Framework | A component is | Its children come from | Its inputs are |
|---|---|---|---|
| React, Preact, Solid | a capitalized function or class that returns markup | the JSX tags in its body, resolved through the file's imports | destructured props, or the props type |
| Vue | a `.vue` file, or an options object carrying a `template` | the tags in its `<template>` block | `defineProps`, or the `props` option |
| Angular | a class decorated `@Component` | the selectors its template uses, inline or in `templateUrl` | `@Input()` members |
| Svelte | a `.svelte` file | the capitalized tags in its markup | `export let` declarations |

Record alongside each one: its outputs — `@Output()`s, emits, or callback props; its lifecycle hooks and effects; the hooks, composables, stores or services it depends on; and the route that reaches it, if any. A custom hook, a composable and an injectable service are none of them components, and filing them as components distorts the tree: give them their own `kind` — `hook`, `service`, `store` — and keep them in the graph, because that is where a component's behavior actually lives.

Components are catalogued in `inventory.json` (pass 1, step b2 below) and drawn in flows as nodes of `kind: "component"` joined by edges of `kind: "render"`. Everything else about a flow is unchanged. A UI flow is worth its own flow when it starts at a route or at a mounted application root: trace it as any other flow is traced — route, page component, the components it renders, the hooks and handlers those call, and on into the services and requests they reach — so that one flow shows a click arriving at the server. Where a tracer ran it has already done this: `components[]` carries each component with its `children`, `inputs`, `outputs` and `hooks`, and `routes[]` pairs a path with the component it renders.

## Whole-codebase mode

Reached only when the user passed `--whole-code-base`. Two passes: catalogue what exists, then trace how it runs. They are separate because they answer different questions and because the second is far more expensive than the first.

**This mode never edits source files.** Step 3 adds docstrings in feature mode; at repository scale that would be a sweeping unrequested rewrite, so here you only read. Record what a function does in the inventory's `purpose` field instead — inferred from the body when there is no docstring.

### Pass 1 — breadth: catalogue what exists

This pass traces nothing. It records what is there.

**a. Choose the files to scan.** Walk the repository from the project root,
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

If a tracer ran, its `files[]` and `skipped[]` arrays are this census already — same paths, sizes, hashes and skip reasons. Take them, and add only what no tracer covered.

**b. Catalogue the functions.** Write `Code_Flows/inventory.json` with one entry
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
      "snippet": "def validate_email(value):\n    ..."
    }
  ]
}
```

- `id` — derived exactly as in step 5, from the same `file` and unqualified
  `name`. This is the whole point of the pass: a flow node and the inventory entry
  for the same function carry the same `id`, and that join is what lets a later
  command compute which catalogued functions no flow ever reaches.
- `name` — the function's **unqualified** name, the same form the `id` rule uses:
  `send`, never `EmailGateway.send`.
- `line` — the line of the function's own definition keyword, never a decorator or
  comment above it. `loc` — its length in lines, definition line through last line
  inclusive.
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
- `calls` — the functions this one calls, each an `id` in this same catalog with a
  `confidence` of `exact` or `heuristic`. Present when a tracer produced it, absent
  otherwise: it is a fact the tracer establishes, not something to infer by reading.
  It is also what makes pass 2 a graph walk instead of a second reading of the whole
  repository, which is the difference between finishing a large map and abandoning one.
- `snippet` — governed by `--detail`:

| `--detail` | `snippet` |
|---|---|
| `thin` | omit it entirely |
| `standard` (default) | include, capped at ~20 lines; omit for functions of 3 lines or fewer, since a trivial accessor tells a duplicate-detector nothing |
| `verbose` | include the full body, uncapped |

If a tracer ran, this catalog is its `functions[]` array: copy `id`, `name`, `file`, `line`, `loc`, `signature`, `purpose`, `role`, `exported`, `calls` and `snippet` straight across rather than deriving them again. Read source only for the entries you are about to describe in a flow, and for anything the tracer's `limits` say it could not see. Catalogue what the tracer found *and* what it says it missed; never report the first as if it were both.

  Inside every `snippet`, replace each `</` with `<\/`, exactly as in step 5.

**b2. Catalogue the components.** Skip this if `--frontend off`, or if the repository has no UI. Otherwise add a `components` array to the same `inventory.json`, one entry per component, hook, store or service: `id` (derived by the same rule as a function's, from the component's own file and unqualified name), `name`, `file`, `line`, `framework` (`react`, `vue`, `angular`, `svelte`, `solid` or `preact`, decided per file rather than per repository), `kind` (`component`, `page`, `layout`, `hook`, `service`, `store`, `directive`, `pipe` or `module`), `selector` (Angular's, or `null`), `inputs`, `outputs`, `hooks`, `children` (the `id` of every component this one renders — this is the tree) and `exported`. If a tracer ran, this is its `components[]` array copied across, and its `routes[]` array pairs a path with the component it renders.

**c. Record the file census.** In `Code_Flows/index.json`, set `meta.mode` to
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

The index page applies here too: having written `index.json`, rewrite
`Code_Flows/index.html` from it. After pass 1 that page shows the census and says
plainly that no flows have been traced yet — which is what a half-finished map
should look like. The bundle applies here too, on the same condition: if
`--output` is `bundle` or `both`, rebuild `Code_Flows/code-flow.html` from the
census now — `flows` will be empty until pass 2 traces some, which is a correct
rendering of a half-finished map, not an error.

`filesScanned` and `functionsCatalogued` describe the whole catalog, including files
carried forward unchanged from an earlier run — not only what this session re-read.
They are facts about the map, not about the session.

`hash` lets a later command warn that the map is stale without re-reading source.
Compute it with whatever the environment provides — `sha256sum <file>`,
`Get-FileHash -Algorithm SHA256 <file>`, or `certutil -hashfile <file> SHA256` —
and record `sha256:` followed by the first 6 hex characters. **If you cannot run
commands here, set `"hash": null` for every file and say so in your final report.
Never invent a hash value**; `size` alone still catches most edits.

**d. Resuming.** If `files` already lists a path whose `size` and `hash` are
unchanged, keep that file's existing `functions` entries and move on rather than
re-reading it. A repository too large to catalogue in one session is finished by
running the command again.

Before trusting `files[]`, read `Code_Flows/inventory.json`. If it is missing, or
exists but does not parse, ignore the census entirely and catalogue every file from
scratch — a census without a readable inventory would carry forward entries that are
no longer there, and the counts would describe a catalog that does not exist.

### Pass 2 — trace: map the flows

**a. Find the entry points.** An entry point is where execution enters the system
from outside it: HTTP routes and their handlers, CLI commands and subcommands,
`main()`, event and queue handlers, scheduled jobs, and the exported public API.
Use the inventory you just built — `exported` is a strong hint — plus the framework
conventions the repository actually uses (route decorators, a router table, an
`argv` parser, a job registry).

If a tracer ran, `entryPoints[]` is this list: take it, and add anything the
conventions above show it missed. Its `routes[]` are entry points too — a route is
where a user enters the system.

Record how many you found as `coverage.entryPointsFound` **before you trace any of
them**. Recording it first is what makes an unfinished run visible: `flowsTraced`
below `entryPointsFound` means the map is partial.

**b. Trace each one.** For every entry point not already mapped, run steps 2, 4, 5
and 6 exactly as written, treating that entry point as the requested flow — but
**skip step 3**: this mode does not edit source. Each flow produces its own
`Code_Flows/<slug>.md`, `.html` and `.json`, and its own entry in `index.json`'s
`flows` array. Derive the slug from the entry point's own name. Where the inventory
carries `calls`, step 2 is a walk of that graph from the entry point rather than a
fresh read of the repository: the nodes are the functions you reach, the edges are
the calls you walked, and the reading you do is of the functions you are about to
describe — which is what makes tracing every entry point in one pass possible.
**The bundle
applies here too** — after step 6 updates `index.json` for this flow, rebuild
`Code_Flows/code-flow.html` under the same `--output` condition as "The bundle"
above, so it stays current as each flow is traced.

Step 6 must leave `meta.mode` at `whole-code-base` and `meta.detail` as pass 1 set
them — it is the only step here that writes `meta`, and this mode depends on those
two values surviving every flow you trace.

**c. Skip what is already mapped.** Before tracing, check `index.json`'s `flows`
for that slug. If it is already there, skip it and move on — do not re-trace and do
not overwrite its files. This is what lets a repository be mapped across several
sessions: run the command again and it picks up where it stopped.

**d. Stop honestly.** A partial pass 2 is not an error. If you run out of room,
stop cleanly after finishing the flow you are on, leave `index.json` consistent, and
tell the user how many of the entry points you traced and that re-running continues
from there. Set `coverage.flowsTraced` to the length of `flows` — what you actually
did, never what you intended.

**e. Report.** Tell the user: the counts from `coverage`, where the artifacts are,
and — if `flowsTraced` is below `entryPointsFound` — that the map is partial and how
to finish it. Say **catalogued**, never "all": this discovery is search and reading,
not a compiler's view of the code, so it is best-effort by construction.
