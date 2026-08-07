---
mode: agent
description: Map a code flow (or the whole codebase) into markdown plus an interactive HTML page.
---

Analyze the codebase and generate flow documentation for the requested functionality.

The user's request follows this prompt. If it is empty, analyze the project structure, suggest 3-5 key flows, and ask which to document.

1. **Identify the target flow** from the user's request. Derive a snake_case filename.
2. **Discover relevant files and functions** — search by file patterns and grep for keywords, then trace the call chain.
3. **Document undocumented functions** — add docstrings to any function in the flow that lacks one.
4. **Generate `Code_Flows/<functionality_name>.md`** containing: a flow description, a MermaidJS diagram in which every function appears as a named node, a bullet list of every function in the diagram, and a reference table with each function's description and its exact `file:line` location.
5. **Generate `Code_Flows/<functionality_name>.html`** by reading `.code-flow/viewer.template.html` and replacing the single token `__FLOW_DATA__` with the flow-data JSON object. Change nothing else in the template. If that file is missing, write a minimal Mermaid-based page instead and tell the user to reinstall `code-flow` for the full viewer.
6. **Report both output paths** to the user.
