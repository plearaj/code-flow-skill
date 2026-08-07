---
mode: agent
description: Analyze and document the flow of a code feature, generating a markdown file and an interactive HTML page with flow diagrams and function reference tables.
---

Analyze the codebase and document the execution flow of the requested functionality (e.g., "the user login flow").

Follow these steps exactly:

1. **Identify the target flow** from the user's request. Derive a snake_case filename (e.g. "user login" → `user_login.md`). If no functionality was named, analyze the project structure, suggest 3-5 key flows, and ask the user to pick one before going any further.
2. **Discover relevant files and functions** — search by file patterns and grep for keywords, then trace the call chain.
3. **Document undocumented functions** — add docstrings to any function in the flow that lacks one.
4. **Generate `Code_Flows/<functionality_name>.md`** containing:
   - Flow description
   - MermaidJS flow diagram (every function as a named node)
   - Bullet list of all function names in the flow
   - Function reference table with columns: Function, Description, File (`file:line` format)
5. **Generate `Code_Flows/<functionality_name>.html`** — an interactive, self-contained page of the same flow (see below).
6. **Write the machine-readable artifacts.** These are the contract consumed by `code-flow.quality`; they are not optional. Write `Code_Flows/<functionality_name>.json` containing exactly the flow-data JSON object used in step 5. Then create or update `Code_Flows/index.json`, adding or replacing this flow's entry in its `flows` array (matched on `slug`) while preserving all other entries — and any `coverage` values you did not compute this run. If `Code_Flows/index.json` exists but does not parse as JSON, **stop**: do not overwrite it and do not regenerate it. Report the file path and what is wrong with it to the user and let them repair or delete it — rewriting the file would silently discard the registry of every flow mapped before this one. Each entry holds `slug`, `title`, `file`, `entry`, and `nodes`: `title` is `meta.feature` from the sidecar's JSON object (step 5), `file` is the sidecar's filename relative to `Code_Flows/` (a bare filename, not a path), `entry` is the `id` of the one node whose `kind` is `entry` (exactly one node has it), and `nodes` is the count of entries in the flow's `nodes` array. The file also carries `meta` (`root`, `generated`, `mode: "feature"`, `schema: 1`) and `coverage.flowsTraced`, set to the length of `flows` after your update.
7. **Report the markdown and HTML paths** to the user, and mention that the JSON artifacts were updated.

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
- Node `kind` ∈ `entry` | `step` | `external` | `io` (default `step`). `entry` = where the flow starts; `external` = a third-party/library boundary; `io` = a DB/network/file side effect. This drives node color. **Exactly one** node MUST have `kind: entry`; if the flow has several plausible roots, pick the one the user asked about and mark the rest `step`. Edge `kind` ∈ `call` | `async` | `conditional` (default `call`). Set `"back": true` on edges that close a loop/recursion.
- File paths use **forward slashes**, repo-relative; `meta.root` is the absolute root, forward slashes.
- `snippet` is optional (≤ ~40 lines). **Replace each `</` with `<\/` inside every snippet.** No trailing commas.

**b. Fill the template** — read `.code-flow/viewer.template.html` and write `Code_Flows/<functionality_name>.html` as an exact copy with the single token `__FLOW_DATA__` replaced by the JSON. Change nothing else. The page self-validates and shows a specific error card (not a blank page) if the JSON is malformed or an edge is dangling.

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

### Output Location

All four outputs go in `Code_Flows/` at the project root — create that directory if it does not exist. None of them is optional:

- `Code_Flows/<functionality_name>.md` — the flow document (step 4)
- `Code_Flows/<functionality_name>.html` — the interactive page (step 5)
- `Code_Flows/<functionality_name>.json` — the flow sidecar (step 6)
- `Code_Flows/index.json` — the shared flow registry, created or updated in place, never rewritten from scratch (step 6)
