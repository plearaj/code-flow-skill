## Code Flow — Documentation Generator

The project includes a **Code Flow** skill that analyzes and documents code execution flows.

### Using Code Flow

When asked to document a code flow (e.g., "document the user login flow"), follow these steps:

1. **Identify the target flow** from the user's request. Derive a snake_case filename.
2. **Discover relevant files and functions** — search by file patterns and grep for keywords, then trace the call chain.
3. **Document undocumented functions** — add docstrings to any function in the flow that lacks one.
4. **Generate `Code_Flows/<functionality_name>.md`** containing:
   - Flow description
   - MermaidJS flow diagram (every function as a named node)
   - Bullet list of all function names in the flow
   - Function reference table with columns: Function, Description, File (`file:line` format)
5. **Generate `Code_Flows/<functionality_name>.html`** — an interactive, self-contained page of the same flow (see below).
6. **Report** both output file paths.

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
    { "id": "login_view", "label": "login_view()", "file": "src/web/views.py", "line": 12, "kind": "entry", "description": "HTTP handler for POST /login.", "snippet": "def login_view(request):\n    ..." }
  ],
  "edges": [
    { "from": "login_view", "to": "authenticate_user", "kind": "call", "label": "", "back": false }
  ]
}
```

Rules (follow exactly or the page refuses to render):
- One node per function. `id` is a unique `[a-z0-9_]` slug. **Every `edge.from`/`edge.to` MUST match a node `id`.**
- Node `kind` ∈ `entry` | `step` | `external` | `io` (default `step`). Edge `kind` ∈ `call` | `async` | `conditional` (default `call`). Set `"back": true` on edges that close a loop/recursion.
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

Flow docs go in: `Code_Flows/<functionality_name>.md` and `Code_Flows/<functionality_name>.html`
