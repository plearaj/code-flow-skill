# Code Flow tracers

Two zero-dependency static tracers. Each one reads a repository and writes a
single JSON document describing every function it found, the calls between
them, the UI components it recognized, and the entry points execution can
arrive through.

They exist because tracing a large repository by reading files is the part of
`/code-flow-map` that does not fit in one session. Running a tracer first turns
"trace 118 flows" into a read of one file and a graph walk, which is the
difference between finishing a map in one pass and finishing it in four.

| Language | Tracer | Runs under |
|---|---|---|
| Python | `trace_python.py` | any CPython 3.9+ |
| TypeScript / JavaScript | `trace_typescript.mjs` | any Node 18+ |

Both install to `.code-flow/tracers/`.

## Running one

```bash
python .code-flow/tracers/trace_python.py --root . --out Code_Flows/trace-python.json
node .code-flow/tracers/trace_typescript.mjs --root . --out Code_Flows/trace-typescript.json
```

`--detail thin|standard|verbose` governs snippets exactly as `/code-flow-map`'s
own flag does: `thin` omits them, `standard` caps them at 20 lines and skips
functions of 3 lines or fewer, `verbose` includes whole bodies. With no `--out`
the JSON goes to stdout, so a tracer can be piped.

A repository written in both languages runs both, into two files. Nothing
merges them for you; `/code-flow-map` reads them as one catalog.

## What comes out

```json
{
  "schema": 1,
  "tracer": "python",
  "language": "python",
  "idRule": "code-flow/v1",
  "root": "/abs/path/to/repo",
  "detail": "standard",
  "files":    [{ "path": "src/a.py", "size": 4210, "hash": "sha256:9f2a1c" }],
  "skipped":  [{ "path": "vendor/x.py", "reason": "vendored" }],
  "functions": [
    {
      "id": "src_auth_service_authenticate",
      "name": "authenticate", "qualname": "authenticate",
      "file": "src/auth/service.py", "line": 12, "loc": 14,
      "signature": "authenticate(user_id, password)",
      "purpose": "Return the user when the password checks out.",
      "role": "source", "exported": true, "async": false, "io": false,
      "decorators": [],
      "calls": [{ "to": "src_auth_store_get", "name": "get", "line": 15, "confidence": "exact" }],
      "snippet": "def authenticate(user_id, password):\n    ..."
    }
  ],
  "components":  [],
  "routes":      [],
  "entryPoints": [{ "id": "...", "name": "login_view", "file": "src/web.py", "line": 8,
                    "kind": "http-route", "detail": "POST /login" }],
  "ambiguousCalls": [{ "from": "...", "name": "save", "line": 40, "candidates": ["...", "..."] }],
  "externalCalls":  [{ "name": "requests.get", "module": "requests", "callers": ["..."] }],
  "stats":  { "filesScanned": 214, "functionsFound": 1180, "callEdges": 2310, "entryPointsFound": 17 },
  "limits": ["Static analysis only: ..."]
}
```

Both tracers emit the same envelope. The TypeScript one additionally fills
`components`, `routes` and a `frameworks` object; the Python one leaves
`components` empty rather than omitting the key, so a consumer never has to
branch on which tracer wrote the file.

### The fields that carry the weight

**`id`** is the map's own id rule, applied by the tracer instead of by hand:
drop the extension from the path's last segment, append `_` and the function's
unqualified name, lowercase, replace every character outside `[a-z0-9_]`,
collapse runs, trim — with `_l<line>` appended when one file defines that name
more than once. A flow node and this file's entry for the same function
therefore carry the same `id`, which is what lets `/code-flow-quality` join
them. `idRule` names the version of that rule, so a future change to it is
detectable rather than silent.

**`confidence`** on a call is `exact` when an import, a `self.`/`this.`
receiver, a constructor binding or a same-file definition made the target
certain, and `heuristic` when a unique name match or a type annotation was the
only evidence. Nothing is guessed: a call that could mean several things is
listed in `ambiguousCalls` with its candidates and produces no edge, and a call
that leaves the repository is listed in `externalCalls`.

**`role`** is `test` for anything under a test directory or matching a test
filename, `source` otherwise. Tests are catalogued, never skipped — excluding
them would make every helper only tests use look unreachable.

**`exported`** is a per-language heuristic biased towards `true`, because
wrongly calling something private produces a false dead-code claim, which is the
more expensive mistake.

**`skipped`** is a file the tracer opened or listed and declined to read, with
one reason: `vendored`, `generated`, `binary` or `unparsed`. It is not a
complete inventory of everything absent from the map — a directory the tracer
never walks (`node_modules/`, `dist/`, anything `.gitignore` excludes) is absent
rather than counted, because counting it would mean walking it. Skip reasons are
matched against whole path segments, never substrings: `distutils/core.py` and
`xml/dom/xmlbuilder.py` are source files, not build output.

**`hash`** is `sha256:` and the first six hex characters of the file's content,
the same form `index.json`'s census records, so a later run can tell which files
changed without re-reading them.

## What they cannot see

Static analysis, and they say so in `limits` rather than implying completeness:

- reflection, `getattr`, `eval`, and dispatch through a string;
- dependency injection by token, service locators, and registries populated at
  runtime;
- entry points declared in configuration rather than in code;
- dynamic imports whose specifier is built from a variable;
- components produced by a factory or a higher-order component.

That is why `/code-flow-map` treats a tracer as evidence to trace *from*, not as
the map. Findings still say "found", never "all".

## Adding a language

A third tracer needs to do exactly three things to be usable: emit the envelope
above, derive `id` by the rule in `idRule`, and never invent an edge it cannot
justify. Nothing else about it is fixed — parse with whatever the language's
own tooling gives you.
