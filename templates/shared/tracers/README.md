# Code Flow tracers

Five zero-dependency static tracers. Each one reads a repository and writes a
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
| TypeScript / JavaScript / JSX / Vue / Svelte | `trace_typescript.mjs` | any Node 18+ |
| Rust | `trace_rust.py` | any CPython 3.9+ |
| Java | `trace_java.py` | any CPython 3.9+ |
| C / C++ / Objective-C / C# | `trace_c_family.py` | any CPython 3.9+ |

All of them install to `.code-flow/tracers/`, along with `_common.py` — the
discovery, id derivation, lexer and envelope the Python-hosted ones share. The
directory is the unit: a tracer imports its sibling, so moving one file out of it
on its own will not work.

They leave nothing behind in the repository they read. In particular they set
`sys.dont_write_bytecode`, so importing `_common` does not drop a `__pycache__/`
into somebody's tree.

## Running one

```bash
python .code-flow/tracers/trace_python.py   --root . --out Code_Flows/trace-python.json
node   .code-flow/tracers/trace_typescript.mjs --root . --out Code_Flows/trace-typescript.json
python .code-flow/tracers/trace_rust.py     --root . --out Code_Flows/trace-rust.json
python .code-flow/tracers/trace_java.py     --root . --out Code_Flows/trace-java.json
python .code-flow/tracers/trace_c_family.py --root . --out Code_Flows/trace-c.json
```

`--detail thin|standard|verbose` governs snippets exactly as `/code-flow-map`'s
own flag does: `thin` omits them, `standard` caps them at 20 lines and skips
functions of 3 lines or fewer, `verbose` includes whole bodies. With no `--out`
the JSON goes to stdout, so a tracer can be piped.

A repository written in several of these languages runs several tracers, into
one file each. Nothing merges them for you; `/code-flow-map` reads them as one
catalog. Four of the five run under Python, so one interpreter covers most of a
polyglot codebase.

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
      "owner": "UserService", "overrides": ["Describable.describe"],
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

Every tracer emits the same envelope. The TypeScript one additionally fills
`components`, `routes` and a `frameworks` object, and the C-family one adds
`dialects`; the rest leave `components` and `routes` empty rather than omitting
the keys, so a consumer never has to branch on which tracer wrote the file.

### The fields that carry the weight

**`id`** is the map's own id rule, applied by the tracer instead of by hand:
drop the extension from the path's last segment, append `_` and the function's
unqualified name, lowercase, replace every character outside `[a-z0-9_]`,
collapse runs, trim. A flow node and this file's entry for the same function
therefore carry the same `id`, which is what lets `/code-flow-quality` join
them. `idRule` names the version of that rule, so a future change to it is
detectable rather than silent.

Three suffixes keep that id unique, each applied only where the one before it
left two functions sharing a string — so on code where nothing collides, every
id is the bare derivation above:

| Suffix | When | Example |
|---|---|---|
| `_l<line>` | one file derives the same id twice | Python's `__add__` and `add` both slug to `add`; two classes with a `get`; an overload set |
| `_<n>` | two of those share a line, and no record carries a column | a bundled file's `function f(){}function F(){}`, `n` counting in source order |
| `_f<rank>` | two files derive the same id | `service.cpp` and `service.hpp`, since the rule drops the extension; `distutils/_msvccompiler.py` and `distutils/msvccompiler.py`, since it collapses underscore runs. `rank` sorts those two paths |

The first two are decided from a single file's contents, so an unrelated file
moving never renames anything. The third cannot be — the collision is between
two files — so it is applied as narrowly as possible: only to the ids the two
files actually both derived, never to the rest of either file.

**`confidence`** on a call is `exact` when an import, a `self.`/`this.`
receiver, a constructor binding, a header the calling file includes, or a
same-file definition made the target certain, and `heuristic` when a unique name
match or a type annotation was the only evidence. Nothing is guessed: a call
that could mean several things is listed in `ambiguousCalls` with its candidates
and produces no edge, and a call that leaves the repository is listed in
`externalCalls`.

**`role`** is `test` for anything under a test directory or matching a test
filename, `source` otherwise. Tests are catalogued, never skipped — excluding
them would make every helper only tests use look unreachable.

**`exported`** is a per-language heuristic biased towards `true`, because
wrongly calling something private produces a false dead-code claim, which is the
more expensive mistake.

**`owner`** is the unqualified name of the type that declares the function --
class, struct, trait, `impl` target, interface, `@implementation`. Absent for a
free function, which is how a consumer tells a method from a function without
parsing `qualname`.

**`overrides`** is the supertype declarations this function overrides, nearest
first, each written `Supertype.member` (or `Supertype::member` where the
language spells it that way). It is a *name*, not an id, and deliberately: a
Java interface method and a C++ pure virtual are declarations with no body, and
a tracer that catalogues bodies has no entry to point at, so an id-only field
would report the same relationship in Java and stay silent in C++. Where the
declaration is itself catalogued, `owner` and `name` find it.

Nothing here is inferred from a name. Each tracer reads the relationship its own
language states -- `impl Trait for Type` in Rust, `extends`/`implements` in Java
and TypeScript, the base-class list in Python and C++ -- and names a supertype
only where that supertype really declares the member: `AdminUserStore extends
UserStore` does not make `findAdmin` an override. A supertype outside the
repository is not named at all, the same silence `calls` keeps over a call that
leaves. This is what lets a consumer group sibling implementations without
guessing that two `save` methods in unrelated classes are a family.

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

Each tracer adds what its own language hides, in its own `limits` array:

| Tracer | What defeats it |
|---|---|
| `trace_rust.py` | trait dispatch through `dyn Trait` or a generic bound; macro bodies; `#[cfg]` branches, which are catalogued whether or not they compile |
| `trace_java.py` | which implementation the container injects behind an interface; overloads, distinguished by line rather than by parameter types; AOP and reflection-based wiring |
| `trace_c_family.py` | the preprocessor, which is never run — a `#define`d name is not expanded and a call that exists only inside a macro body is not found; function pointers; virtual dispatch; Objective-C `performSelector:` |

None of them guesses past its own limit. Where a call could mean several things
it becomes an `ambiguousCall` carrying its candidates, which is a thing the map
can report and act on, unlike a confident wrong answer.

That is why `/code-flow-map` treats a tracer as evidence to trace *from*, not as
the map. Findings still say "found", never "all".

## Adding a language

A tracer needs to do exactly three things to be usable: emit the envelope above,
derive `id` by the rule in `idRule`, and never invent an edge it cannot justify.
Nothing else about it is fixed — parse with whatever the language's own tooling
gives you.

If the language delimits its bodies with braces, `_common.py` already has most
of it. `mask_source` blanks comments and literal contents in place — same
length, same line breaks, so offsets and line numbers stay valid — which is what
makes a `{` inside a string safe to ignore; `Flavor` is the six-field
description of how a language spells its comments and literals, and adding one
is usually the whole lexer. `collect_sources`, `assign_ids`, `Resolution` and
`build_envelope` are the rest of the envelope. `trace_rust.py` is the shortest
example of a tracer built on it.

Then add the language to `tests/test_tracers.py`'s `TRACERS` table with a
fixture repository, and every shared contract in that module — the envelope, the
id rule, no dangling call targets, stated confidence, reproducibility, the
`--detail` flag, the census, the skip reasons — runs against it. Contracts a new
tracer has to opt into are contracts a new tracer will eventually fail.
