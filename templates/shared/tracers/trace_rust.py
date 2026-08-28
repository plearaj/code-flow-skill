#!/usr/bin/env python3
"""Static call-graph tracer for Rust repositories.

Emits the envelope described in `README.md`: every function in a repository,
the calls between them, and the entry points execution can arrive through.
`/code-flow-map` runs this before it traces anything, so that mapping a
repository is a read of one file rather than a re-derivation of the whole call
graph from source.

It does not invoke `rustc` and does not read `target/`. A tracer that needed a
toolchain would work only where the project already builds, which is the case
least in need of a map. So it reads the source directly, over a masked copy in
which comments and literal contents are blanked out — see `_common.mask_source`,
and note that Rust's block comments nest, which a naive lexer gets wrong in a
way that silently swallows the rest of a file.

What is Rust-specific here, and worth knowing before trusting the output:

**`impl` blocks decide identity.** A method's qualified name is `Type::method`,
taken from the innermost enclosing `impl`, and two impls of the same type in one
file both contribute to it. A trait's default method belongs to the trait.

**Trait dispatch is invisible.** A call through `&dyn Trait` or a generic bound
reaches whichever impl the monomorphizer picks, which is not a static fact about
the text. Those calls resolve to the trait's own method where one exists, and
are otherwise listed as ambiguous with every impl as a candidate — never guessed.

**Macros are not expanded.** A call that only exists inside a macro body is not
found. Calls written as arguments to a macro — `assert_eq!(add(1, 2), 3)` — are,
because the argument text is ordinary code.

Usage:

    python trace_rust.py [--root DIR] [--out FILE] [--detail LEVEL]
"""
from __future__ import annotations

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

TRACER_NAME = "rust"
SOURCE_SUFFIXES = (".rs",)

IDENT = r"[A-Za-z_][A-Za-z0-9_]*"

# Keywords that are followed by `(` without being a call.
NOT_CALLS = frozenset(
    """if while for match return break continue let fn move as in loop else where
    unsafe async await impl dyn ref mut pub use mod crate super self Self type
    struct enum trait const static""".split()
)

# Methods every std collection, iterator, Option and Result answers to. A call
# like `items.iter().map(f).collect()` has a receiver this tracer cannot type,
# and matching `map` against the one function in the repository that happens to
# be named `map` invents an edge that does not exist. Names in this set are
# never resolved by the unique-name fallback when the call has a receiver.
COMMON_METHODS = frozenset(
    """new len is_empty iter iter_mut into_iter next map filter fold collect clone
    to_string to_owned as_str as_ref as_mut unwrap unwrap_or unwrap_or_else expect
    ok err ok_or ok_or_else and_then or_else push pop insert remove get get_mut
    contains contains_key keys values entry extend append clear sort sort_by join
    split splitn trim starts_with ends_with replace parse into from try_into
    try_from borrow borrow_mut lock read write send recv await count sum min max
    last first take skip zip chain rev any all find position flat_map cloned copied
    to_vec as_bytes to_lowercase to_uppercase format push_str with_capacity default
    add sub mul div eq ne cmp partial_cmp hash fmt drop deref""".split()
)

# Text in a body that means the function touches the world outside the process.
IO_PATTERNS = (
    r"\bstd::(fs|net|process|io::std)\b",
    r"\b(File|OpenOptions|TcpStream|TcpListener|UdpSocket|Command|Child)\s*::",
    r"\b(reqwest|hyper|ureq|surf|awc)\b",
    r"\b(sqlx|diesel|rusqlite|postgres|tokio_postgres|redis|mongodb)\b",
    r"\btokio::(fs|net|process)\b",
    r"\.(execute|query|query_as|fetch_one|fetch_all|fetch_optional)\s*\(",
    r"\.(read_to_string|read_to_end|write_all|flush|create|open|remove_file)\s*\(",
    r"\b(println|eprintln|print|eprint)\s*!",
)
IO_RE = re.compile("|".join(IO_PATTERNS))

# Attribute -> entry-point kind. Matched against the attribute as written, so
# `#[get("/x")]` and `#[actix_web::get("/x")]` land on the same rule.
ENTRY_ATTRIBUTE_RULES: Tuple[Tuple[str, str], ...] = (
    (r"^\s*(?:\w+::)*(get|post|put|patch|delete|head|options|route)\s*\(", "http-route"),
    (r"^\s*(?:tokio|async_std|actix_web|actix_rt)::main\b", "cli-command"),
    (r"^\s*no_mangle\b", "ffi-export"),
    (r"^\s*wasm_bindgen\b", "ffi-export"),
    (r"^\s*(proc_macro|proc_macro_derive|proc_macro_attribute)\b", "macro"),
    (r"^\s*(bench|criterion)\b", "job"),
)

TEST_ATTRIBUTES = re.compile(r"^\s*(?:\w+::)*(test|tokio::test|rstest|proptest)\b")


# --- per-file analysis -----------------------------------------------------

CALL_RE = re.compile(
    r"(?P<path>(?:" + IDENT + r"\s*(?:::|\.)\s*)*)(?P<name>" + IDENT + r")\s*(?:::\s*<[^<>()]*>\s*)?\("
)
LET_TYPED_RE = re.compile(
    r"\blet\s+(?:mut\s+)?(?P<var>" + IDENT + r")\s*:\s*(?:&\s*)?(?:mut\s+)?(?:dyn\s+)?(?P<type>" + IDENT + r")"
)
LET_BOUND_RE = re.compile(
    r"\blet\s+(?:mut\s+)?(?P<var>" + IDENT + r")\s*=\s*(?:&\s*)?"
    r"(?P<type>[A-Z][A-Za-z0-9_]*)\s*(?:::\s*" + IDENT + r")?\s*[({]"
)
PARAM_RE = re.compile(
    r"(?P<var>" + IDENT + r")\s*:\s*(?:&\s*)?(?:'" + IDENT + r"\s+)?(?:mut\s+)?(?:dyn\s+|impl\s+)?(?P<type>" + IDENT + r")"
)
FIELD_RE = re.compile(
    r"(?:pub(?:\s*\([^)]*\))?\s+)?(?P<field>" + IDENT + r")\s*:\s*(?:&\s*)?(?:'" + IDENT + r"\s+)?(?:mut\s+)?(?P<type>" + IDENT + r")"
)
ROUTE_RE = re.compile(r"\.route\s*\(\s*\"(?P<path>[^\"]*)\"\s*,\s*(?P<rest>[^;]*)")
HANDLER_RE = re.compile(r"\b(?:get|post|put|patch|delete|head|options|any)\s*\(\s*(" + IDENT + r")")


class RustFile:
    """One `.rs` file, read once: its blocks, its types, its uses, its functions."""

    def __init__(self, rel: str, text: str) -> None:
        self.rel = rel
        self.text = text
        self.masked = common.mask_source(text, common.RUST)
        self.index = common.LineIndex(text)
        self.lines = text.splitlines()
        self.blocks: List[Dict[str, Any]] = []
        self.types: Set[str] = set()
        self.fields: Dict[str, Dict[str, str]] = {}
        self.uses: Dict[str, str] = {}
        self.functions: List[Dict[str, Any]] = []
        self.routes: List[Dict[str, str]] = []

        self._collect_uses()
        self._collect_blocks()
        self._collect_functions()
        self._collect_routes()

    # -- uses ---------------------------------------------------------------

    def _collect_uses(self) -> None:
        """Map every name a `use` brings into scope to the path it came from.

        `use a::b::{c, d as e};` puts `c` and `e` in scope; the brace form is the
        one that matters, because it is how almost every Rust file imports more
        than one thing.
        """
        for match in re.finditer(r"\buse\s+([^;]+);", self.masked):
            body = self.text[match.start(1) : match.end(1)]
            for alias, path in _expand_use(body.strip()):
                self.uses[alias] = path

    # -- blocks -------------------------------------------------------------

    def _collect_blocks(self) -> None:
        for match in re.finditer(r"\b(impl|trait|mod|struct|enum|union)\b", self.masked):
            keyword = match.group(1)
            after = match.end()
            if keyword in ("struct", "enum", "union"):
                self._record_type(after)
                continue
            if keyword == "mod":
                name_match = re.compile(r"\s*(" + IDENT + r")\s*\{").match(self.masked, after)
                if not name_match:
                    continue  # `mod foo;` — the module is another file
                brace = self.masked.index("{", name_match.end() - 1)
                end = common.match_brace(self.masked, brace)
                if end > 0:
                    self.blocks.append(
                        {"kind": "mod", "name": name_match.group(1), "type": None,
                         "trait": None, "start": brace, "end": end}
                    )
                continue
            self._record_impl_or_trait(keyword, after)

    def _record_type(self, after: int) -> None:
        name_match = re.compile(r"\s*(" + IDENT + r")").match(self.masked, after)
        if not name_match:
            return
        name = name_match.group(1)
        self.types.add(name)
        brace = self.masked.find("{", name_match.end())
        semicolon = self.masked.find(";", name_match.end())
        if brace < 0 or (0 <= semicolon < brace):
            return  # a tuple or unit struct: no named fields to read
        end = common.match_brace(self.masked, brace)
        if end < 0:
            return
        fields: Dict[str, str] = {}
        for field in FIELD_RE.finditer(self.masked[brace + 1 : end]):
            fields[field.group("field")] = field.group("type")
        if fields:
            self.fields[name] = fields

    def _record_impl_or_trait(self, keyword: str, after: int) -> None:
        cursor = after
        while cursor < len(self.masked) and self.masked[cursor] in " \t\n\r":
            cursor += 1
        if cursor < len(self.masked) and self.masked[cursor] == "<":
            closing = common.match_angle(self.masked, cursor)
            if closing < 0:
                return
            cursor = closing + 1
        brace = self.masked.find("{", cursor)
        if brace < 0:
            return
        head = self.masked[cursor:brace]
        head = re.split(r"\bwhere\b", head)[0]
        trait_name: Optional[str] = None
        if keyword == "trait":
            trait_name = _leading_name(head)
            type_name = None
        elif " for " in head:
            left, right = head.split(" for ", 1)
            trait_name = _leading_name(left)
            type_name = _leading_name(right)
        else:
            type_name = _leading_name(head)
        end = common.match_brace(self.masked, brace)
        if end < 0:
            return
        self.blocks.append(
            {"kind": keyword, "name": type_name or trait_name or "", "type": type_name,
             "trait": trait_name, "start": brace, "end": end}
        )
        if type_name:
            self.types.add(type_name)

    def enclosing(self, position: int) -> Optional[Dict[str, Any]]:
        """The innermost impl, trait or mod block containing ``position``."""
        best: Optional[Dict[str, Any]] = None
        for block in self.blocks:
            if block["start"] < position < block["end"]:
                if best is None or block["start"] > best["start"]:
                    best = block
        return best

    def module_prefix(self, position: int) -> List[str]:
        names = [b["name"] for b in self.blocks
                 if b["kind"] == "mod" and b["start"] < position < b["end"]]
        return names

    # -- functions ----------------------------------------------------------

    def _collect_functions(self) -> None:
        for match in re.finditer(r"\bfn\s+(" + IDENT + r")", self.masked):
            record = self._read_function(match)
            if record is not None:
                self.functions.append(record)

    def _read_function(self, match: "re.Match[str]") -> Optional[Dict[str, Any]]:
        name = match.group(1)
        cursor = match.end()
        if cursor < len(self.masked) and self.masked[cursor] == "<":
            closing = common.match_angle(self.masked, cursor)
            if closing < 0:
                return None
            cursor = closing + 1
        while cursor < len(self.masked) and self.masked[cursor] in " \t\n\r":
            cursor += 1
        if cursor >= len(self.masked) or self.masked[cursor] != "(":
            return None
        params_end = common.match_paren(self.masked, cursor)
        if params_end < 0:
            return None

        brace = self.masked.find("{", params_end)
        semicolon = self.masked.find(";", params_end)
        if brace < 0 or (0 <= semicolon < brace):
            # A trait method with no default body, or an `extern` declaration.
            # There is nothing to trace inside it, and cataloguing it as a
            # function would report a body that does not exist.
            return None
        body_end = common.match_brace(self.masked, brace)
        if body_end < 0:
            return None

        line = self.index.line_of(match.start())
        line_start = self.index.start_of(line)
        prefix = self.masked[line_start : match.start()]
        attributes, above = self._attributes_above(line_start)

        params = " ".join(self.text[cursor : params_end + 1].split())
        returns = " ".join(self.masked[params_end + 1 : brace].split())
        returns = re.split(r"\bwhere\b", returns)[0].strip()
        signature = name + params + (" " + returns if returns.startswith("->") else "")

        block = self.enclosing(match.start())
        owner = block["type"] if block and block["kind"] == "impl" else None
        if block and block["kind"] == "trait":
            owner = block["trait"]
        qualname = "::".join(self.module_prefix(match.start()) + ([owner] if owner else []) + [name])

        body = self.text[brace : body_end + 1]
        return {
            "file": self.rel,
            "name": name,
            "qualname": qualname,
            "owner": owner,
            "traitName": block["trait"] if block else None,
            "traitDecl": bool(block and block["kind"] == "trait"),
            "line": line,
            "endLine": self.index.line_of(body_end),
            "signature": " ".join(signature.split()),
            "purpose": common.doc_comment_before(self.text, above),
            "exported": bool(re.search(r"\bpub\b", prefix)),
            "async": bool(re.search(r"\basync\b", prefix)),
            "io": bool(IO_RE.search(body)),
            "decorators": attributes,
            "isTest": any(TEST_ATTRIBUTES.match(a) for a in attributes),
            "bodyStart": brace,
            "bodyEnd": body_end,
            "params": params,
        }

    def _attributes_above(self, line_start: int) -> Tuple[List[str], int]:
        """The `#[...]` attributes stacked above a declaration, read unmasked.

        Read from the original text rather than the masked copy because an
        attribute's payload is the part that matters — `#[get("/users")]` is an
        entry point *and* a URL, and the URL is exactly what masking removes.
        """
        attributes: List[str] = []
        cursor = line_start
        while cursor > 0:
            previous_start = self.text.rfind("\n", 0, cursor - 1) + 1
            raw = self.text[previous_start : cursor - 1].strip()
            if raw.startswith("#[") and raw.endswith("]"):
                attributes.insert(0, raw[2:-1].strip())
                cursor = previous_start
                continue
            if raw.startswith("#!["):
                cursor = previous_start
                continue
            break
        return attributes, cursor

    # -- routes -------------------------------------------------------------

    def _collect_routes(self) -> None:
        """axum-style `.route("/path", get(handler))`, read from the source text.

        Router registration is the one entry-point shape in Rust that is a call
        rather than an attribute, and skipping it would leave every axum service
        looking like it had no entry points at all.
        """
        for match in ROUTE_RE.finditer(self.text):
            for handler in HANDLER_RE.finditer(match.group("rest")):
                self.routes.append({"path": match.group("path"), "handler": handler.group(1)})


def _leading_name(text: str) -> Optional[str]:
    match = re.search(IDENT, text.replace("dyn ", " ").replace("impl ", " "))
    return match.group(0) if match else None


def _expand_use(body: str) -> List[Tuple[str, str]]:
    """Flatten one `use` declaration into (name in scope, full path) pairs."""
    body = " ".join(body.split())
    results: List[Tuple[str, str]] = []
    brace = body.find("{")
    if brace >= 0:
        prefix = body[:brace].strip().rstrip(":")
        inner = body[brace + 1 : body.rfind("}")]
        for part in _split_top_level(inner):
            for alias, path in _expand_use(part.strip()):
                results.append((alias, (prefix + "::" + path) if prefix else path))
        return results
    if not body or body.endswith("*"):
        return results
    if " as " in body:
        path, alias = body.split(" as ", 1)
        return [(alias.strip(), path.strip())]
    tail = body.rsplit("::", 1)[-1]
    return [(tail.strip(), body.strip())]


def _split_top_level(text: str) -> List[str]:
    parts, depth, start = [], 0, 0
    for i, ch in enumerate(text):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(text[start:i])
            start = i + 1
    parts.append(text[start:])
    return [p for p in parts if p.strip()]


# --- the repository --------------------------------------------------------


def module_paths_for(rel: str) -> List[str]:
    """Every path a `use` could name this file by.

    Rust's module tree is the directory tree under `src`, with `mod.rs`, `lib.rs`
    and `main.rs` naming their own directory rather than themselves. A file in a
    workspace member is reachable both as `crate::a::b` from inside that crate
    and as `member_name::a::b` from outside it, so both are recorded.
    """
    parts = rel.split("/")
    if "src" not in parts:
        return []
    pivot = len(parts) - 1 - parts[::-1].index("src")
    crate_dir, inner = parts[:pivot], parts[pivot + 1 :]
    if not inner:
        return []
    stem = inner[-1][:-3]
    module_parts = inner[:-1] + ([] if stem in ("mod", "lib", "main") else [stem])
    dotted = "::".join(module_parts)

    paths = ["crate::" + dotted if dotted else "crate"]
    if dotted:
        paths.append(dotted)
    if crate_dir:
        crate_name = crate_dir[-1].replace("-", "_")
        paths.append("::".join([crate_name] + module_parts) if module_parts else crate_name)
    return paths


class Repository:
    def __init__(self, root: str, detail: str) -> None:
        self.root = root
        self.detail = detail
        self.files: Dict[str, RustFile] = {}
        self.census: List[Dict[str, Any]] = []
        self.skipped: List[Dict[str, Any]] = []
        self.functions: List[Dict[str, Any]] = []
        self.resolution = common.Resolution()
        self.modules: Dict[str, str] = {}
        self.types: Set[str] = set()
        self.by_name: Dict[str, List[Dict[str, Any]]] = {}
        self.methods: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
        self.free: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}

    # -- indexing -----------------------------------------------------------

    def index(self) -> None:
        common.assign_ids(self.functions)
        for rel, source in self.files.items():
            self.types |= source.types
            for path in module_paths_for(rel):
                self.modules.setdefault(path, rel)
        for fn in self.functions:
            self.by_name.setdefault(fn["name"], []).append(fn)
            if fn["owner"]:
                self.methods.setdefault((fn["owner"], fn["name"]), []).append(fn)
            if fn["traitName"]:
                self.methods.setdefault((fn["traitName"], fn["name"]), []).append(fn)
            if not fn["owner"]:
                self.free.setdefault((fn["file"], fn["name"]), []).append(fn)

    # -- resolution ---------------------------------------------------------

    def resolve_all(self) -> None:
        for fn in self.functions:
            source = self.files[fn["file"]]
            body = source.masked[fn["bodyStart"] : fn["bodyEnd"] + 1]
            variables = self._variable_types(fn, body)
            seen: Set[Tuple[str, int]] = set()
            calls: List[Dict[str, Any]] = []
            for match in CALL_RE.finditer(body):
                name = match.group("name")
                if name in NOT_CALLS:
                    continue
                offset = fn["bodyStart"] + match.start("name")
                line = source.index.line_of(offset)
                if not match.group("path") and _follows_a_dot(body, match.start()):
                    # `xs.iter().map(f)`: a method call whose receiver is an
                    # expression, so `path` is empty even though this is not a
                    # bare call. Reading it as one would resolve `map` to
                    # whatever the repository happens to call `map`.
                    target = self._resolve_method(fn, source, variables, [("", ".")], name, line)
                else:
                    target = self._resolve(fn, source, variables, match.group("path"), name, line)
                if target is None:
                    continue
                key = (target[0], line)
                if key in seen:
                    continue
                seen.add(key)
                calls.append({"to": target[0], "name": name, "line": line, "confidence": target[1]})
            fn["calls"] = sorted(calls, key=lambda c: (c["line"], c["to"]))

    def _variable_types(self, fn: Dict[str, Any], body: str) -> Dict[str, str]:
        """What this function's local names are, where the text says so.

        Three sources, all textual: a typed parameter, a `let x: Type`, and a
        `let x = Type::new(...)`. Inference beyond that is the compiler's job,
        and guessing at it is how a tracer starts inventing edges.
        """
        variables: Dict[str, str] = {}
        for match in PARAM_RE.finditer(fn["params"]):
            variables[match.group("var")] = match.group("type")
        for match in LET_TYPED_RE.finditer(body):
            variables[match.group("var")] = match.group("type")
        for match in LET_BOUND_RE.finditer(body):
            variables[match.group("var")] = match.group("type")
        return variables

    def _resolve(
        self,
        fn: Dict[str, Any],
        source: RustFile,
        variables: Dict[str, str],
        path: str,
        name: str,
        line: int,
    ) -> Optional[Tuple[str, str]]:
        segments = _parse_path(path)
        if not segments:
            return self._resolve_bare(fn, source, name, line)
        if segments[-1][1] == "::":
            return self._resolve_path(fn, source, segments, name, line)
        return self._resolve_method(fn, source, variables, segments, name, line)

    def _resolve_bare(
        self, fn: Dict[str, Any], source: RustFile, name: str, line: int
    ) -> Optional[Tuple[str, str]]:
        local = self.free.get((source.rel, name))
        if local and len(local) == 1:
            return (local[0]["id"], "exact")

        imported = source.uses.get(name)
        if imported:
            resolved = self._through_use(imported, name)
            if resolved:
                return (resolved, "exact")
            if _is_external_root(imported):
                self.resolution.external_call(imported, imported.split("::")[0], fn["id"])
                return None

        return self._by_unique_name(fn, name, line)

    def _resolve_path(
        self,
        fn: Dict[str, Any],
        source: RustFile,
        segments: List[Tuple[str, str]],
        name: str,
        line: int,
    ) -> Optional[Tuple[str, str]]:
        owner = segments[-1][0]
        if owner == "Self":
            owner = fn["owner"] or ""
        candidates = self.methods.get((owner, name), [])
        if len(candidates) == 1:
            return (candidates[0]["id"], "exact")
        if len(candidates) > 1:
            self.resolution.ambiguous_call(fn["id"], name, line, [c["id"] for c in candidates])
            return None

        full = _absolute_path(source, [s[0] for s in segments])
        resolved = self._through_use(full + "::" + name, name)
        if resolved:
            return (resolved, "exact")

        root = full.split("::")[0]
        if _is_external_root(full):
            self.resolution.external_call(full + "::" + name, root, fn["id"])
            return None
        if owner and owner[:1].isupper() and owner not in self.types:
            # An associated function on a type this repository does not define:
            # `String::from`, `Vec::with_capacity`. Recording it as external is
            # the honest answer, and it is one the unique-name fallback would
            # otherwise get wrong for any repository with a function of the
            # same name.
            self.resolution.external_call(owner + "::" + name, owner, fn["id"])
            return None
        return self._by_unique_name(fn, name, line)

    def _resolve_method(
        self,
        fn: Dict[str, Any],
        source: RustFile,
        variables: Dict[str, str],
        segments: List[Tuple[str, str]],
        name: str,
        line: int,
    ) -> Optional[Tuple[str, str]]:
        receiver = segments[-1][0]
        owner: Optional[str] = None

        if receiver in ("self", "Self"):
            owner = fn["owner"] or fn["traitName"]
        elif len(segments) >= 2 and segments[-2][0] == "self":
            fields = source.fields.get(fn["owner"] or "", {})
            owner = fields.get(receiver)
        else:
            owner = variables.get(receiver)

        if owner:
            candidates = self.methods.get((owner, name), [])
            if len(candidates) == 1:
                return (candidates[0]["id"], "exact")
            if len(candidates) > 1:
                self.resolution.ambiguous_call(fn["id"], name, line, [c["id"] for c in candidates])
                return None

        if name in COMMON_METHODS:
            # `items.iter().map(f)` on a receiver this tracer cannot type. The
            # repository may well define a function called `map`; connecting the
            # two would put a call in the diagram that does not exist.
            return None
        return self._by_unique_name(fn, name, line)

    def _through_use(self, full_path: str, name: str) -> Optional[str]:
        """Resolve `a::b::name` to a function, via the module tree."""
        if "::" not in full_path:
            return None
        module_path, tail = full_path.rsplit("::", 1)
        if tail != name:
            module_path = full_path
        rel = self.modules.get(module_path)
        if rel is None:
            return None
        candidates = self.free.get((rel, name), [])
        if len(candidates) == 1:
            return candidates[0]["id"]
        owner = module_path.rsplit("::", 1)[-1]
        methods = self.methods.get((owner, name), [])
        if len(methods) == 1:
            return methods[0]["id"]
        return None

    def _by_unique_name(
        self, fn: Dict[str, Any], name: str, line: int
    ) -> Optional[Tuple[str, str]]:
        candidates = self.by_name.get(name, [])
        if len(candidates) == 1:
            return (candidates[0]["id"], "heuristic")
        if len(candidates) > 1:
            self.resolution.ambiguous_call(fn["id"], name, line, [c["id"] for c in candidates])
        return None


def _follows_a_dot(body: str, start: int) -> bool:
    """Whether the call at ``start`` is chained onto something with a `.`."""
    i = start - 1
    while i >= 0 and body[i] in " \t\n\r":
        i -= 1
    return i >= 0 and body[i] == "."


def _parse_path(path: str) -> List[Tuple[str, str]]:
    """Split a call's qualifier into (segment, separator) pairs."""
    return [
        (m.group(1), m.group(2))
        for m in re.finditer(r"(" + IDENT + r")\s*(::|\.)", path)
    ]


def _absolute_path(source: RustFile, segments: List[str]) -> str:
    """Rewrite a call's path through this file's `use` declarations."""
    if not segments:
        return ""
    head, rest = segments[0], segments[1:]
    if head in ("crate", "self", "super"):
        return "::".join(segments)
    expanded = source.uses.get(head)
    if expanded:
        return "::".join([expanded] + rest)
    return "::".join(segments)


def _is_external_root(path: str) -> bool:
    root = path.split("::")[0]
    return root not in ("crate", "self", "super") and root.islower()


# --- entry points ----------------------------------------------------------


BIN_DIRS = ("src/bin/", "examples/", "benches/")


def attribute_entry(attribute: str) -> Optional[Tuple[str, str]]:
    for pattern, kind in ENTRY_ATTRIBUTE_RULES:
        if re.search(pattern, attribute):
            return kind, _attribute_detail(attribute, kind)
    return None


def _attribute_detail(attribute: str, kind: str) -> str:
    if kind != "http-route":
        return attribute
    verb = re.match(r"\s*(?:\w+::)*(\w+)", attribute)
    path = re.search(r"\"([^\"]*)\"", attribute)
    if verb and path:
        return "{} {}".format(verb.group(1).upper(), path.group(1))
    return attribute


def collect_entry_points(repo: Repository) -> List[Dict[str, Any]]:
    """Where execution can arrive, by the three routes Rust offers.

    An attribute macro states it outright; `fn main` states it by name and
    position; a router registers it as a call, which is the only one that needs
    reading the body of another function to find.
    """
    entries: Dict[str, Dict[str, Any]] = {}

    def add(fn: Dict[str, Any], kind: str, detail: str) -> None:
        entries.setdefault(
            fn["id"],
            {"id": fn["id"], "name": fn["name"], "file": fn["file"], "line": fn["line"],
             "kind": kind, "detail": detail},
        )

    for fn in repo.functions:
        if fn["role"] == "test":
            continue
        for attribute in fn["decorators"]:
            found = attribute_entry(attribute)
            if found:
                add(fn, found[0], found[1])
                break
        if fn["name"] == "main" and not fn["owner"]:
            if fn["file"].endswith("src/main.rs") or fn["file"] == "main.rs" or any(
                part in fn["file"] for part in BIN_DIRS
            ):
                add(fn, "cli-command", fn["file"])

    for rel, source in repo.files.items():
        for route in source.routes:
            candidates = repo.free.get((rel, route["handler"]), [])
            if len(candidates) != 1:
                candidates = repo.by_name.get(route["handler"], [])
            if len(candidates) == 1:
                add(candidates[0], "http-route", route["path"])

    return sorted(entries.values(), key=lambda e: (e["file"], e["line"]))


# --- output ----------------------------------------------------------------


def _overridden_names(fn: Dict[str, Any]) -> List[str]:
    """The trait member an `impl Trait for Type` method implements, if any.

    Rust states the relationship outright and the language enforces it: every
    method in an `impl Describe for UserStore` block implements a member of
    `Describe`, or the crate does not compile. So there is nothing to look up
    here and nothing to infer -- unlike the tracers that have to find a
    declaration before they can name it, this one reads the answer off the
    block header. That also means a trait's *required* methods, which have no
    body and so are never catalogued, are covered anyway.
    """
    trait = fn["traitName"]
    if not trait or fn["traitDecl"]:
        return []
    return [trait + "::" + fn["name"]]


def build_functions(repo: Repository) -> List[Dict[str, Any]]:
    records = []
    for fn in repo.functions:
        source = repo.files[fn["file"]]
        record = {
            "id": fn["id"],
            "name": fn["name"],
            "qualname": fn["qualname"],
            "file": fn["file"],
            "line": fn["line"],
            "loc": fn["endLine"] - fn["line"] + 1,
            "signature": fn["signature"],
            "purpose": fn["purpose"],
            "role": fn["role"],
            "exported": fn["exported"],
            "async": fn["async"],
            "io": fn["io"],
            "decorators": fn["decorators"],
            "calls": fn["calls"],
        }
        if fn["owner"]:
            record["owner"] = fn["owner"]
        overrides = _overridden_names(fn)
        if overrides:
            record["overrides"] = overrides
        snippet = common.snippet_for(
            source.lines, fn["line"], fn["endLine"], record["loc"], repo.detail
        )
        if snippet is not None:
            record["snippet"] = snippet
        records.append(record)
    return records


LIMITS = common.BASE_LIMITS + (
    "`overrides` is read off the `impl Trait for Type` header, so it covers a trait's "
    "required methods as well as its defaults -- but only for traits, since an inherent "
    "`impl` block overrides nothing.",
    "Trait dispatch through `dyn Trait` or a generic bound is resolved to the trait's "
    "own method where one exists, and left ambiguous otherwise: which impl runs is not "
    "a static fact about the text.",
    "Macros are not expanded, so a call that exists only inside a macro body is not found.",
    "`#[cfg(...)]` is not evaluated: code behind a disabled feature is catalogued as if it were live.",
)


def trace(root: str, detail: str) -> Dict[str, Any]:
    root_abs = os.path.abspath(root)
    keep, skipped = common.collect_sources(root_abs, SOURCE_SUFFIXES)
    repo = Repository(root_abs, detail)
    repo.skipped = skipped

    for rel in keep:
        path = os.path.join(root_abs, rel.replace("/", os.sep))
        text = common.read_source(path)
        if text is None:
            repo.skipped.append({"path": rel, "reason": "unparsed"})
            continue
        source = RustFile(rel, text)
        repo.files[rel] = source
        try:
            size = os.path.getsize(path)
        except OSError:
            size = 0
        repo.census.append({"path": rel, "size": size, "hash": common.file_hash(path)})

        in_test_file = common.is_test_path(rel)
        for fn in source.functions:
            in_test_mod = any(
                block["kind"] == "mod"
                and block["name"] in ("test", "tests")
                and block["start"] < fn["bodyStart"] < block["end"]
                for block in source.blocks
            )
            fn["role"] = "test" if (in_test_file or fn["isTest"] or in_test_mod) else "source"
            repo.functions.append(fn)

    repo.index()
    repo.resolve_all()
    functions = build_functions(repo)
    return common.build_envelope(
        tracer=TRACER_NAME,
        language="rust",
        root_abs=root_abs.replace(os.sep, "/"),
        detail=detail,
        files=repo.census,
        skipped=repo.skipped,
        functions=functions,
        entry_points=collect_entry_points(repo),
        resolution=repo.resolution,
        limits=LIMITS,
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    return common.run_cli(
        "trace_rust.py",
        "Static call-graph tracer for Rust repositories (code-flow).",
        trace,
        argv,
    )


if __name__ == "__main__":
    raise SystemExit(main())
