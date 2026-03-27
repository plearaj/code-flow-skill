## Code Flow — Documentation Generator

The project includes a **Code Flow** skill that analyzes and documents code execution flows.

### Using Code Flow

When asked to document a code flow (e.g., "document the spectral attention flow"), follow these steps:

1. **Identify the target flow** from the user's request. Derive a snake_case filename.
2. **Discover relevant files and functions** — search by file patterns and grep for keywords, then trace the call chain.
3. **Document undocumented functions** — add docstrings to any function in the flow that lacks one.
4. **Generate `Code_Flows/<functionality_name>.md`** containing:
   - Flow description
   - MermaidJS flow diagram (every function as a named node)
   - Bullet list of all function names in the flow
   - Function reference table with columns: Function, Description, File (`file:line` format)
5. **Report** the output file path.

### Output Location

All flow docs go in: `Code_Flows/<functionality_name>.md`
