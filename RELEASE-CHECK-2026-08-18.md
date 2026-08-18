# Release check — v1.1.0, 2026-08-18

The manual browser pass required by README's "Before publishing". Performed by
Claude against pages built from **this branch's** scaffolds (not pages generated
by an earlier version) and this repository's own `Code_Flows/` artifacts: 2 flows,
1 quality finding, 42 files catalogued.

Pages were built by filling each shipped scaffold's tokens the way the prompt
prose instructs, then served over `http://localhost:4319` and opened in a browser.

## Step 1 — every page renders, and links navigate

| Page | Scaffold | Result |
|---|---|---|
| `index.html` | `index.template.html` | Renders: "2 mapped flows", 4 stat tiles, both flow cards, Quality card, file census |
| `python_install.html` | `viewer.template.html` | Renders: call graph with nodes and edges, lane chips, detail panel, zoom |
| `quality-report.html` | `report.template.html` | Renders: coverage card ("2 of 4 entry points were traced"), severity/principle filters, finding DRY-01 with sites |
| `code-flow.html` | `bundle.template.html` | Renders all three in one document: landing view lists the same 2 flows, a flow opens its graph, report reachable |

Navigation, verified by clicking the real anchors and reading `location.pathname`
afterwards:

- `index.html` → flow card → `/python_install.html`, title "Python CLI Install · code flow"
- `quality-report.html` → `Flows` → `/index.html`
- Checked that neither link calls `preventDefault` (both reported
  `defaultPrevented: false`), so navigation is the anchor's own, not script-driven.

## Step 2 — corrupted data shows the error card, not a blank page

The opening `{` was removed from each page's embedded JSON block, and each result
was confirmed unparseable by `json.loads` **before** loading, so the test could not
pass vacuously.

| Page | Shown |
|---|---|
| `index.html` | `INVALID JSON IN #INDEX-DATA` + parser message + the `<\/` escaping tip |
| `quality-report.html` | `INVALID JSON IN #REPORT-DATA` + parser message + tip |
| `python_install.html` | `INVALID JSON IN #FLOW-DATA` + parser message + tip (chrome still drawn) |
| `code-flow.html` | `BUNDLE FAILED TO LOAD — Invalid JSON in bundle data:` + parser message |

**A first attempt at this step was thrown out.** It deleted a character from inside
a path string, which leaves JSON valid — the page rendered normally and would have
been recorded as a pass. The corruption must hit a structural character.

## Step 3 — a user theme applies in both modes

Rebuilt every page with a real theme in `__THEME_CSS__`:

```css
:root{--accent:#ff2d95;}
[data-theme="light"]{--accent:#008b45;}
```

On `quality-report.html`, computed `--accent` read from the live document:

| Mode | `data-theme` | Computed `--accent` | Expected |
|---|---|---|---|
| dark | `dark` | `#ff2d95` | `#ff2d95` |
| light | `light` | `#008b45` | `#008b45` |

Both are the user's values, not the built-in palette. This is the check that
proves `__THEME_CSS__` sits **after** the `[data-theme="light"]` block: placed
before it, the light row would have shown the shipped default and the theme would
appear broken the moment anyone used the toggle.

The same was separately confirmed on `code-flow.html` earlier in the phase.

## Not covered

- Only `python_install.html` was opened of the two per-flow pages; `node_install.html`
  uses the identical scaffold and data shape.
- Antigravity IDE, Codex and the Copilot CLI were not re-exercised for this release;
  the host observations in the README date from 2026-08-17.

## Attestation

`CODE_FLOW_RELEASE_CHECKED=1` is **not** set by this document. The variable attests
that a human performed this pass. The evidence above is offered so a human can
decide whether to set it.
