#!/usr/bin/env python3
"""Static call-graph tracer for Python repositories.

Emits one JSON document describing every function in a repository, the calls
between them, and the entry points execution can arrive through. `/code-flow-map`
runs this before it traces anything, so that mapping a repository is a read of
one file rather than a re-derivation of the whole call graph from source.

Design constraints, in the order they mattered:

**Zero dependencies.** It runs under any CPython 3.9+ with nothing installed,
because it has to run inside the user's repository, not this one.

**Ids join with the map.** The `id` rule here is byte-for-byte the rule the map
templates state in prose, collision suffix included. A flow node and this
tracer's entry for the same function carry the same `id`, which is the whole
reason the output is usable as an inventory.

**Honest resolution.** Every resolved call carries a `confidence`: `exact` when
an import, a `self.` receiver or a same-file definition made the target certain,
`heuristic` when a unique name match was the only evidence. Calls that could
mean several things land in `ambiguousCalls` with their candidates rather than
being guessed into an edge, and calls that leave the repository land in
`externalCalls`. Static analysis cannot see `getattr`, dependency injection or
a registry populated at runtime, so the output says "found", never "all".

Usage:

    python trace_python.py [--root DIR] [--out FILE] [--detail LEVEL]

`--detail thin|standard|verbose` governs snippets exactly as `/code-flow-map`'s
own flag does: `thin` omits them, `standard` caps them at 20 lines and skips
functions of 3 lines or fewer, `verbose` includes whole bodies.
"""
from __future__ import annotations

import ast
import os
import re
import sys
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

# This runs inside the user's repository, so it leaves nothing behind in it:
# importing a sibling module would otherwise write a `__pycache__/` into the
# tree it was asked to read.
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as common  # noqa: E402  (the path has to be set first)

# Everything about finding files, naming functions and assembling the output is
# shared with the other tracers; see `_common.py`. What is left here is what is
# actually specific to reading Python.
from _common import is_test_path  # noqa: E402  (the path has to be set first)

TRACER_NAME = "python"

SOURCE_SUFFIXES = (".py", ".pyi")

# Decorator text -> entry-point kind. Matched against the decorator as written,
# so `@app.get("/x")`, `@router.get(...)` and `@bp.route(...)` all land on the
# same rule without this table having to know the framework's variable names.
ENTRY_DECORATOR_RULES: Tuple[Tuple[str, str], ...] = (
    (r"\.(route|get|post|put|patch|delete|head|options|websocket|api_route)\s*\(", "http-route"),
    (r"\b(app|api|router|bp|blueprint|server)\s*\.\s*(websocket|sse)\b", "http-route"),
    (r"\b(click|typer|cli|app)\s*\.\s*(command|group)\b", "cli-command"),
    (r"@command\b", "cli-command"),
    (r"\b(shared_task|celery\.task|app\.task|task|periodic_task|job|cron)\b", "job"),
    (r"\b(on_event|listens_for|receiver|subscribe|event|on|handler|hook)\b", "event"),
    (r"\b(lambda_handler|entrypoint|main)\b", "cli-command"),
)

# Call text that means the function touches the world outside the process. Used
# only to set `io: true`, which the map turns into a node of kind `io`.
IO_CALL_PATTERNS = (
    r"^open$", r"^print$", r"^input$",
    r"^(requests|httpx|urllib|urllib3|aiohttp|http|socket|smtplib|ftplib)\b",
    r"^(sqlite3|psycopg2|psycopg|pymysql|MySQLdb|asyncpg|sqlalchemy|redis|pymongo|boto3|botocore)\b",
    r"^(subprocess|shutil|pathlib|os)\b",
    r"\.(execute|executemany|commit|rollback|fetchone|fetchall|cursor)$",
    r"\.(read_text|write_text|read_bytes|write_bytes|mkdir|unlink|rmtree)$",
    r"\.(save|delete|create|bulk_create|get_or_create|update_or_create)$",
    r"\.(send|sendall|recv|publish|enqueue|emit)$",
)
IO_CALL_RE = re.compile("|".join(IO_CALL_PATTERNS))

# Callables that are never worth an edge: control flow in disguise, builtins,
# and the type constructors every codebase calls thousands of times.
# Method names every container and string answers to. A call like
# `self._read().get(key)` has a receiver this tracer cannot type, and matching
# `get` against the one function in the repository that happens to be named
# `get` invents an edge that does not exist. Names in this set are never
# resolved by the unique-name fallback when the call has a receiver.
CONTAINER_METHODS = frozenset(
    """get keys items values append extend insert pop remove clear copy update add
    discard sort reverse index count join split rsplit strip lstrip rstrip format
    startswith endswith lower upper title replace encode decode read write close
    seek tell flush next send throw group match search sub findall setdefault
    union intersection difference isdigit isalpha splitlines partition""".split()
)

BUILTIN_CALLS = frozenset(
    """abs all any ascii bin bool bytearray bytes callable chr classmethod compile complex
    delattr dict dir divmod enumerate eval exec filter float format frozenset getattr
    globals hasattr hash help hex id input int isinstance issubclass iter len list locals
    map max memoryview min next object oct ord pow property range repr reversed round set
    setattr slice sorted staticmethod str sum super tuple type vars zip
    Exception ValueError TypeError KeyError IndexError RuntimeError NotImplementedError
    StopIteration AttributeError OSError IOError FileNotFoundError ZeroDivisionError""".split()
)


# --- module naming ---------------------------------------------------------


def module_name_for(root: str, rel: str) -> Optional[str]:
    """Return the dotted module name ``rel`` is importable as.

    Walks up from the file while each directory holds an `__init__.py`, so
    `src/pkg/mod.py` in a src-layout project is `pkg.mod` rather than
    `src.pkg.mod` — which is the name its own imports will use.
    """
    if not rel.endswith(".py"):
        return None
    parts = rel.split("/")
    stem = parts[-1][:-3]
    package: List[str] = []
    for i in range(len(parts) - 2, -1, -1):
        init = os.path.join(root, *parts[: i + 1], "__init__.py")
        if os.path.isfile(init):
            package.insert(0, parts[i])
        else:
            break
    if stem == "__init__":
        return ".".join(package) if package else None
    return ".".join(package + [stem])


# --- per-file analysis -----------------------------------------------------


class FileAnalyzer(ast.NodeVisitor):
    """Collect functions, imports, classes and raw call sites from one module."""

    def __init__(self, rel: str, source: str, tree: ast.AST) -> None:
        self.rel = rel
        self.lines = source.splitlines()
        self.tree = tree
        self.functions: List[Dict[str, Any]] = []
        self.classes: Dict[str, Dict[str, Any]] = {}
        self.imports: Dict[str, Dict[str, Any]] = {}
        self.dunder_all: Optional[Set[str]] = None
        self.has_main_guard = False
        self._class_stack: List[str] = []
        self._func_stack: List[Dict[str, Any]] = []
        # Simple `name = ClassName(...)` and `name: ClassName` bindings, which is
        # what turns an `obj.method()` call from a guess into a resolution.
        self._var_types: Dict[str, str] = {}

    # -- helpers

    def _segment(self, node: ast.AST) -> str:
        try:
            return ast.unparse(node)
        except Exception:  # pragma: no cover - unparse is total on parsed trees
            return ""

    def _snippet(self, node: ast.AST) -> str:
        start = getattr(node, "lineno", 1) - 1
        end = getattr(node, "end_lineno", start + 1)
        return "\n".join(self.lines[start:end])

    def _current(self) -> Optional[Dict[str, Any]]:
        return self._func_stack[-1] if self._func_stack else None

    # -- module level

    def visit_Module(self, node: ast.Module) -> None:
        for stmt in node.body:
            if isinstance(stmt, ast.If) and self._segment(stmt.test).replace('"', "'") in (
                "__name__ == '__main__'",
                "'__main__' == __name__",
            ):
                self.has_main_guard = True
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name) and target.id == "__all__":
                        self.dunder_all = {
                            elt.value
                            for elt in getattr(stmt.value, "elts", [])
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                        }
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            local = alias.asname or alias.name.split(".")[0]
            target = alias.name if alias.asname else alias.name.split(".")[0]
            self.imports[local] = {"module": target, "name": None, "full": alias.name}
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        for alias in node.names:
            local = alias.asname or alias.name
            self.imports[local] = {
                "module": module,
                "name": alias.name,
                "level": node.level,
                "full": "{}.{}".format(module, alias.name) if module else alias.name,
            }
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.classes[node.name] = {
            "name": node.name,
            "line": node.lineno,
            "bases": [self._segment(b) for b in node.bases],
            "decorators": [self._segment(d) for d in node.decorator_list],
            "methods": {},
        }
        self._class_stack.append(node.name)
        self.generic_visit(node)
        self._class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._function(node, is_async=True)

    def _function(self, node: ast.AST, is_async: bool) -> None:
        name = node.name  # type: ignore[attr-defined]
        cls = self._class_stack[-1] if self._class_stack else None
        parent = self._current()
        qual_parts = [p for p in ([parent["qualname"]] if parent else [cls] if cls else []) if p]
        qualname = ".".join(qual_parts + [name])
        decorators = [self._segment(d) for d in node.decorator_list]  # type: ignore[attr-defined]
        args = self._segment(node.args)  # type: ignore[attr-defined]
        returns = getattr(node, "returns", None)
        signature = "{}{}({}){}".format(
            "async " if is_async else "",
            name,
            args,
            " -> {}".format(self._segment(returns)) if returns is not None else "",
        )
        line = node.lineno  # type: ignore[attr-defined]
        end = getattr(node, "end_lineno", line)
        entry = {
            "name": name,
            "qualname": qualname,
            "file": self.rel,
            "line": line,
            "endLine": end,
            "loc": max(1, end - line + 1),
            "signature": signature,
            "purpose": (ast.get_docstring(node) or "").strip().splitlines()[:1],  # type: ignore[arg-type]
            "async": is_async,
            "class": cls,
            "decorators": decorators,
            "nested": parent is not None,
            "io": False,
            "calls": [],
            "_node": node,
        }
        entry["purpose"] = entry["purpose"][0] if entry["purpose"] else ""
        self.functions.append(entry)
        if cls and cls in self.classes and parent is None:
            self.classes[cls]["methods"][name] = entry
        self._func_stack.append(entry)
        saved_vars = dict(self._var_types)
        self.generic_visit(node)
        self._var_types = saved_vars
        self._func_stack.pop()

    def visit_Assign(self, node: ast.Assign) -> None:
        if isinstance(node.value, ast.Call):
            callee = node.value.func
            base = callee.id if isinstance(callee, ast.Name) else None
            if base and base[:1].isupper():
                # A constructor call names the class outright, so a method
                # found through it is resolved, not guessed.
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self._var_types[target.id] = (base, "exact")
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        annotation = self._segment(node.annotation)
        base = annotation.split("[")[0].split(".")[-1].strip()
        if isinstance(node.target, ast.Name) and base[:1].isupper():
            # An annotation may name a protocol or a base class, so it is
            # evidence rather than proof.
            self._var_types[node.target.id] = (base, "heuristic")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        current = self._current()
        if current is not None:
            text = self._segment(node.func)
            receiver: Optional[str] = None
            name = ""
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
                if isinstance(node.func.value, ast.Name):
                    receiver = node.func.value.id
                elif isinstance(node.func.value, ast.Attribute):
                    receiver = self._segment(node.func.value)
            if name:
                if IO_CALL_RE.search(text):
                    current["io"] = True
                current["calls"].append(
                    {
                        "name": name,
                        "receiver": receiver,
                        "text": text,
                        "line": node.lineno,
                        "varType": self._var_types.get(receiver or "", None),
                        "unknownReceiver": receiver is None
                        and isinstance(node.func, ast.Attribute),
                    }
                )
        self.generic_visit(node)


# --- resolution ------------------------------------------------------------


class Repository:
    """Every analyzed file, and the indexes that let one call find its target."""

    def __init__(self, root: str, detail: str) -> None:
        self.root = root
        self.detail = detail
        self.files: List[Dict[str, Any]] = []
        self.skipped: List[Dict[str, str]] = []
        self.analyzers: Dict[str, FileAnalyzer] = {}
        self.modules: Dict[str, str] = {}  # dotted module -> rel path
        self.functions: List[Dict[str, Any]] = []
        self.by_id: Dict[str, Dict[str, Any]] = {}
        self.by_name: Dict[str, List[Dict[str, Any]]] = {}
        self.ambiguous: List[Dict[str, Any]] = []
        self.external: Dict[str, Dict[str, Any]] = {}

    # -- ids

    def assign_ids(self) -> None:
        """Give every function its map `id`, applying the collision suffix.

        Per analyzer, which is per file: the suffix is decided from one file's
        own contents, never from which functions a caller happened to ask about,
        which is what keeps an id stable across runs.
        """
        for analyzer in self.analyzers.values():
            common.assign_ids(analyzer.functions)

    def index(self) -> None:
        for analyzer in self.analyzers.values():
            for fn in analyzer.functions:
                self.functions.append(fn)
                self.by_id[fn["id"]] = fn
                self.by_name.setdefault(fn["name"], []).append(fn)

    # -- lookups

    def module_file(self, dotted: str) -> Optional[str]:
        if dotted in self.modules:
            return self.modules[dotted]
        # `import pkg.mod` bound as `pkg` still points at a real module file.
        while "." in dotted:
            dotted = dotted.rsplit(".", 1)[0]
            if dotted in self.modules:
                return self.modules[dotted]
        return None

    def resolve_relative(self, rel: str, module: str, level: int) -> Optional[str]:
        """Resolve `from ..pkg import x` against the importing file's package."""
        own = module_name_for(self.root, rel)
        if own is None:
            return None
        parts = own.split(".")
        # A module's own name contributes one level; `__init__` files already
        # name their package, so `level` counts from the package either way.
        base = parts[: max(0, len(parts) - level)] if not rel.endswith("__init__.py") else parts[: max(0, len(parts) - level + 1)]
        dotted = ".".join([p for p in base if p] + ([module] if module else []))
        return dotted or None

    def function_in_file(self, rel: str, name: str) -> Optional[Dict[str, Any]]:
        analyzer = self.analyzers.get(rel)
        if analyzer is None:
            return None
        module_level = [f for f in analyzer.functions if f["name"] == name and not f["class"] and not f["nested"]]
        if len(module_level) == 1:
            return module_level[0]
        return None

    def class_in_file(self, rel: str, name: str) -> Optional[Dict[str, Any]]:
        analyzer = self.analyzers.get(rel)
        if analyzer is None:
            return None
        return analyzer.classes.get(name)

    # -- the resolver

    def resolve_calls(self) -> None:
        for rel, analyzer in self.analyzers.items():
            for fn in analyzer.functions:
                resolved: List[Dict[str, Any]] = []
                seen: Set[Tuple[str, int]] = set()
                for call in fn["calls"]:
                    outcome = self._resolve_one(analyzer, fn, call)
                    if outcome is None:
                        continue
                    kind, payload = outcome
                    if kind == "call":
                        key = (payload["to"], payload["line"])
                        if key in seen:
                            continue
                        seen.add(key)
                        resolved.append(payload)
                    elif kind == "ambiguous":
                        self.ambiguous.append(payload)
                    elif kind == "external":
                        slot = self.external.setdefault(
                            payload["name"], {"name": payload["name"], "module": payload["module"], "callers": []}
                        )
                        if fn["id"] not in slot["callers"]:
                            slot["callers"].append(fn["id"])
                fn["resolvedCalls"] = resolved

    def _resolve_one(
        self, analyzer: FileAnalyzer, fn: Dict[str, Any], call: Dict[str, Any]
    ) -> Optional[Tuple[str, Dict[str, Any]]]:
        name = call["name"]
        receiver = call["receiver"]
        rel = analyzer.rel

        if receiver is None and name in BUILTIN_CALLS:
            return None

        def hit(target: Dict[str, Any], confidence: str) -> Tuple[str, Dict[str, Any]]:
            return (
                "call",
                {"to": target["id"], "name": name, "line": call["line"], "confidence": confidence},
            )

        # 1. `self.x()` / `cls.x()` — the one receiver whose meaning is certain.
        if receiver in ("self", "cls") and fn["class"]:
            cls = analyzer.classes.get(fn["class"])
            if cls and name in cls["methods"]:
                return hit(cls["methods"][name], "exact")
            inherited = self._inherited_method(analyzer, fn["class"], name)
            if inherited is not None:
                return hit(inherited, "exact")

        if receiver is None:
            # 2. A function nested inside this one.
            nested = [
                f
                for f in analyzer.functions
                if f["name"] == name and f["qualname"].startswith(fn["qualname"] + ".")
            ]
            if len(nested) == 1:
                return hit(nested[0], "exact")
            # 3. A module-level function in this file.
            local = self.function_in_file(rel, name)
            if local is not None:
                return hit(local, "exact")
            # 4. A class in this file, called as a constructor.
            cls = analyzer.classes.get(name)
            if cls and "__init__" in cls["methods"]:
                return hit(cls["methods"]["__init__"], "exact")
            # 5. An imported name.
            imported = analyzer.imports.get(name)
            if imported is not None:
                target = self._through_import(analyzer, imported, imported.get("name") or name)
                if target is not None:
                    return target
                return ("external", {"name": imported.get("full", name), "module": imported["module"]})
            # 6. A unique match anywhere in the repository.
            return self._by_unique_name(name, call, fn, has_receiver=call.get("unknownReceiver", False))

        # 7. A receiver that names an imported module or symbol.
        imported = analyzer.imports.get(receiver.split(".")[0] if receiver else "")
        if imported is not None:
            target = self._through_import(analyzer, imported, name, receiver=receiver)
            if target is not None:
                return target
            return ("external", {"name": "{}.{}".format(imported.get("full", receiver), name), "module": imported["module"]})

        # 8. A receiver bound to a class in this file — `store = Store()`.
        var_type = call.get("varType")
        if var_type:
            type_name, type_confidence = var_type
            cls = analyzer.classes.get(type_name)
            if cls and name in cls["methods"]:
                return hit(cls["methods"][name], type_confidence)
            imported_cls = analyzer.imports.get(type_name)
            if imported_cls is not None:
                target = self._through_import(analyzer, imported_cls, name, receiver=type_name)
                if target is not None:
                    return ("call", dict(target[1], confidence=type_confidence))

        # 9. A class in this file used as a receiver — `Store.build()`.
        cls = analyzer.classes.get(receiver)
        if cls and name in cls["methods"]:
            return hit(cls["methods"][name], "exact")

        # 10. Nothing named the target; fall back to a unique name match.
        return self._by_unique_name(name, call, fn, has_receiver=True)

    def _inherited_method(
        self, analyzer: FileAnalyzer, class_name: str, method: str, depth: int = 0
    ) -> Optional[Dict[str, Any]]:
        """Find ``method`` on a base class defined in the same file."""
        if depth > 4:
            return None
        cls = analyzer.classes.get(class_name)
        if cls is None:
            return None
        for base in cls["bases"]:
            simple = base.split("[")[0].split(".")[-1].strip()
            parent = analyzer.classes.get(simple)
            if parent is None:
                continue
            if method in parent["methods"]:
                return parent["methods"][method]
            found = self._inherited_method(analyzer, simple, method, depth + 1)
            if found is not None:
                return found
        return None

    def _through_import(
        self,
        analyzer: FileAnalyzer,
        imported: Dict[str, Any],
        wanted: str,
        receiver: Optional[str] = None,
    ) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Resolve a call through an import record, or return None if it leaves."""
        module = imported["module"]
        level = imported.get("level", 0) or 0
        if level:
            dotted = self.resolve_relative(analyzer.rel, module, level)
        else:
            dotted = imported.get("full") if imported.get("name") is None else module
        if not dotted:
            return None
        rel = self.module_file(dotted)
        if rel is None and imported.get("name"):
            # `from pkg import mod` where `mod` is itself a module.
            rel = self.module_file("{}.{}".format(dotted, imported["name"]))
        if rel is None:
            return None
        target = self.function_in_file(rel, wanted)
        if target is not None:
            return ("call", {"to": target["id"], "name": wanted, "line": 0, "confidence": "exact"})
        # A class imported by name, then called or used as a receiver.
        symbol = imported.get("name") or receiver
        if symbol:
            cls = self.class_in_file(rel, symbol)
            if cls is None and receiver:
                cls = self.class_in_file(rel, receiver)
            if cls is not None:
                if wanted in cls["methods"]:
                    return ("call", {"to": cls["methods"][wanted]["id"], "name": wanted, "line": 0, "confidence": "exact"})
                if wanted == symbol and "__init__" in cls["methods"]:
                    return (
                        "call",
                        {"to": cls["methods"]["__init__"]["id"], "name": wanted, "line": 0, "confidence": "exact"},
                    )
        return None

    def _by_unique_name(
        self, name: str, call: Dict[str, Any], fn: Dict[str, Any], has_receiver: bool = False
    ) -> Optional[Tuple[str, Dict[str, Any]]]:
        if has_receiver and name in CONTAINER_METHODS:
            return None
        candidates = [f for f in self.by_name.get(name, []) if f["id"] != fn["id"]]
        if not candidates:
            return None
        if len(candidates) == 1:
            return (
                "call",
                {"to": candidates[0]["id"], "name": name, "line": call["line"], "confidence": "heuristic"},
            )
        return (
            "ambiguous",
            {
                "from": fn["id"],
                "name": name,
                "line": call["line"],
                "candidates": [c["id"] for c in candidates[:8]],
            },
        )


# --- entry points ----------------------------------------------------------


def decorator_entry_kind(decorators: Sequence[str]) -> Optional[Tuple[str, str]]:
    for text in decorators:
        for pattern, kind in ENTRY_DECORATOR_RULES:
            if re.search(pattern, text):
                return kind, text
    return None


def console_scripts(root: str) -> List[str]:
    """Return `module:function` targets declared in pyproject.toml.

    Parsed with `tomllib` where it exists (3.11+) and by regex otherwise, so a
    3.9 or 3.10 interpreter still finds them rather than silently reporting a
    repository with no CLI entry points.
    """
    path = os.path.join(root, "pyproject.toml")
    if not os.path.isfile(path):
        return []
    try:
        text = open(path, "r", encoding="utf-8", errors="replace").read()
    except OSError:
        return []
    targets: List[str] = []
    try:
        import tomllib  # type: ignore

        data = tomllib.loads(text)
        for table in ("scripts", "gui-scripts"):
            targets += list(data.get("project", {}).get(table, {}).values())
        poetry = data.get("tool", {}).get("poetry", {}).get("scripts", {})
        targets += [v for v in poetry.values() if isinstance(v, str)]
    except Exception:
        section = re.search(r"\[project\.scripts\](.*?)(?=\n\[|\Z)", text, re.DOTALL)
        if section:
            targets += re.findall(r'=\s*"([^"]+)"', section.group(1))
    return [t for t in targets if isinstance(t, str) and ":" in t]


def django_url_targets(repo: Repository) -> List[Tuple[str, str]]:
    """Return (view-id, route) pairs declared in Django-style url modules."""
    found: List[Tuple[str, str]] = []
    for rel, analyzer in repo.analyzers.items():
        if not rel.endswith("urls.py"):
            continue
        source = "\n".join(analyzer.lines)
        for route, target in re.findall(
            r"(?:path|re_path|url)\(\s*[rbf]?['\"]([^'\"]*)['\"]\s*,\s*([A-Za-z_][\w.]*)", source
        ):
            symbol = target.split(".")[-1]
            matches = repo.by_name.get(symbol, [])
            if len(matches) == 1:
                found.append((matches[0]["id"], route or "/"))
    return found


def collect_entry_points(repo: Repository) -> List[Dict[str, Any]]:
    """Return every place execution can enter the repository from outside.

    Ordered and de-duplicated by id, so re-running the tracer over an unchanged
    tree produces a byte-identical list.
    """
    entries: Dict[str, Dict[str, Any]] = {}

    def add(fn: Dict[str, Any], kind: str, detail: str) -> None:
        if fn["role"] == "test":
            return
        current = entries.get(fn["id"])
        if current is None:
            entries[fn["id"]] = {"id": fn["id"], "name": fn["name"], "file": fn["file"], "line": fn["line"], "kind": kind, "detail": detail}

    for fn in repo.functions:
        found = decorator_entry_kind(fn["decorators"])
        if found is not None:
            add(fn, found[0], found[1])

    for target in console_scripts(repo.root):
        module, _, func = target.partition(":")
        rel = repo.module_file(module.strip())
        if rel is None:
            continue
        hit = repo.function_in_file(rel, func.strip().split(".")[0])
        if hit is not None:
            add(hit, "cli-command", "console script {}".format(target))

    for view_id, route in django_url_targets(repo):
        fn = repo.by_id.get(view_id)
        if fn is not None:
            add(fn, "http-route", route)

    for rel, analyzer in repo.analyzers.items():
        if analyzer.has_main_guard:
            for fn in analyzer.functions:
                if fn["name"] == "main" and not fn["class"]:
                    add(fn, "main", "{}  (__main__ guard)".format(rel))

    for fn in repo.functions:
        if fn["class"] or fn["nested"] or fn["role"] == "test":
            continue
        if fn["name"] in ("main", "handler", "lambda_handler", "run"):
            add(fn, "main", "conventional entry name")

    return [entries[key] for key in sorted(entries)]


# --- output ----------------------------------------------------------------


def exported_for(analyzer: FileAnalyzer, fn: Dict[str, Any]) -> bool:
    """Whether the function is public API, by the map's own heuristic.

    Biased towards `true` deliberately: wrongly calling something private
    produces a false dead-code claim downstream, which is the more expensive
    mistake.
    """
    if analyzer.dunder_all is not None and not fn["class"]:
        return fn["name"] in analyzer.dunder_all
    if fn["name"].startswith("_") and not fn["name"].startswith("__"):
        return False
    return True


def _base_class(
    repo: Repository, analyzer: FileAnalyzer, base: str
) -> Optional[Tuple[FileAnalyzer, Dict[str, Any]]]:
    """The class record a base-class expression names, and the file it is in.

    `bases` holds the expression as written -- `Base`, `models.Base`,
    `Generic[T]` -- so the subscript and the dotted path come off before the
    name is looked up: first in the same module, then through whatever the
    module imported. A base this repository does not define resolves to
    nothing, which is the answer, not a failure.
    """
    simple = base.split("[")[0].split(".")[-1].strip()
    if not simple:
        return None
    local = analyzer.classes.get(simple)
    if local is not None:
        return (analyzer, local)
    imported = analyzer.imports.get(simple)
    if imported is None:
        return None
    level = imported.get("level", 0) or 0
    if level:
        dotted = repo.resolve_relative(analyzer.rel, imported["module"], level)
    else:
        dotted = imported.get("full") if imported.get("name") is None else imported["module"]
    rel = repo.module_file(dotted) if dotted else None
    if rel is None:
        return None
    other = repo.analyzers.get(rel)
    if other is None:
        return None
    found = other.classes.get(simple)
    return (other, found) if found is not None else None


def overridden_names(
    repo: Repository, analyzer: FileAnalyzer, fn: Dict[str, Any]
) -> List[str]:
    """The base-class methods this one overrides, nearest base first.

    Python has no `override` keyword, so the fact has to come from the class
    statement: a method overrides when a base class this repository defines
    declares the same name. A base outside the repository -- `object`,
    `unittest.TestCase`, a framework's model class -- is not resolvable here and
    so is not named, the same silence `calls` keeps over a call that leaves.

    Nested functions are skipped: `class` names the enclosing class for those
    too, but a closure inside a method is not a member of anything.
    """
    cls = fn["class"] if not fn["nested"] else None
    return _walk_bases(repo, analyzer, cls, fn["name"], set(), 0)


def _walk_bases(
    repo: Repository,
    analyzer: FileAnalyzer,
    cls: Optional[str],
    name: str,
    seen: Set[str],
    depth: int,
) -> List[str]:
    if not cls or depth > 4 or cls in seen:
        return []
    seen.add(cls)
    record = analyzer.classes.get(cls)
    if record is None:
        return []
    found: List[str] = []
    for base in record["bases"]:
        resolved = _base_class(repo, analyzer, base)
        if resolved is None:
            continue
        other, parent = resolved
        if name in parent["methods"]:
            declaration = parent["name"] + "." + name
            if declaration not in found:
                found.append(declaration)
        for deeper in _walk_bases(repo, other, parent["name"], name, seen, depth + 1):
            if deeper not in found:
                found.append(deeper)
    return found


def build_output(repo: Repository, root_abs: str) -> Dict[str, Any]:
    functions: List[Dict[str, Any]] = []
    for fn in repo.functions:
        analyzer = repo.analyzers[fn["file"]]
        record = {
            "id": fn["id"],
            "name": fn["name"],
            "qualname": fn["qualname"],
            "file": fn["file"],
            "line": fn["line"],
            "loc": fn["loc"],
            "signature": fn["signature"],
            "purpose": fn["purpose"],
            "role": fn["role"],
            "exported": exported_for(analyzer, fn),
            "async": fn["async"],
            "io": fn["io"],
            "decorators": fn["decorators"],
            "calls": fn.get("resolvedCalls", []),
        }
        if fn["class"] and not fn["nested"]:
            record["owner"] = fn["class"]
        overrides = overridden_names(repo, analyzer, fn)
        if overrides:
            record["overrides"] = overrides
        snippet = common.snippet_for(
            analyzer.lines, fn["line"], fn["endLine"], fn["loc"], repo.detail
        )
        if snippet is not None:
            record["snippet"] = snippet
        functions.append(record)

    # `Resolution` is the bookkeeping every tracer shares; this one filled the
    # same two structures by hand before there was anything to share it with.
    resolution = common.Resolution()
    resolution.ambiguous = repo.ambiguous
    resolution.external = repo.external

    return common.build_envelope(
        tracer=TRACER_NAME,
        language="python",
        root_abs=root_abs,
        detail=repo.detail,
        files=repo.files,
        skipped=repo.skipped,
        functions=functions,
        entry_points=collect_entry_points(repo),
        resolution=resolution,
        limits=common.BASE_LIMITS + (
            "Decorators are read as text, so a decorator that wraps a function in "
            "another function is recorded rather than followed.",
        ),
    )


# --- driver ----------------------------------------------------------------


def trace(root: str, detail: str) -> Dict[str, Any]:
    root_abs = os.path.abspath(root)
    keep, skipped = common.collect_sources(root_abs, SOURCE_SUFFIXES)

    repo = Repository(root_abs, detail)
    repo.skipped = skipped
    for rel in keep:
        path = os.path.join(root_abs, rel.replace("/", os.sep))
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                source = handle.read()
        except OSError:
            repo.skipped.append({"path": rel, "reason": "unparsed"})
            continue
        try:
            tree = ast.parse(source, filename=rel)
        except (SyntaxError, ValueError, RecursionError):
            repo.skipped.append({"path": rel, "reason": "unparsed"})
            continue
        analyzer = FileAnalyzer(rel, source, tree)
        analyzer.visit(tree)
        for fn in analyzer.functions:
            fn["role"] = "test" if is_test_path(rel) else "source"
        repo.analyzers[rel] = analyzer
        try:
            size = os.path.getsize(path)
        except OSError:
            size = 0
        repo.files.append({"path": rel, "size": size, "hash": common.file_hash(path)})
        dotted = module_name_for(root_abs, rel)
        if dotted:
            repo.modules.setdefault(dotted, rel)

    repo.assign_ids()
    repo.index()
    repo.resolve_calls()
    return build_output(repo, root_abs.replace(os.sep, "/"))


def main(argv: Optional[Sequence[str]] = None) -> int:
    if sys.version_info < (3, 9):
        sys.stderr.write("trace_python.py needs Python 3.9 or newer (it uses ast.unparse).\n")
        return 2
    return common.run_cli(
        "trace_python.py",
        "Static call-graph tracer for Python repositories (code-flow).",
        trace,
        argv,
    )


if __name__ == "__main__":
    raise SystemExit(main())
