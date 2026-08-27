#!/usr/bin/env python3
"""Static call-graph tracer for Java repositories.

Emits the envelope described in `README.md`. It does not invoke `javac`, read
`target/` or `build/`, or need the project to compile — a tracer that required a
working build would be useless on exactly the repository most in need of a map.
It reads the source over a masked copy in which comments, string literals, text
blocks and character literals are blanked out, so that a brace inside a string
cannot move a method's boundary.

What is Java-specific here, and worth knowing before trusting the output:

**A method belongs to its class.** `qualname` is `Class.method`, from the
innermost enclosing type, and a constructor is a method whose name is the class
name. Nested and inner classes nest in the name.

**Inheritance is followed, interfaces are not resolved.** A call to an
inherited method resolves to the definition it inherits, through `extends`
chains this repository defines. A call through an interface reference reaches
whichever implementation was injected, which is not a static fact about the
text: those resolve to the interface's own declaration if it has a body, and are
otherwise listed as ambiguous with every implementation as a candidate.

**Overloads share a name.** Two methods of the same name in one file get the
`_l<line>` suffix the id rule specifies, and a call that could mean either is
ambiguous rather than assigned to the first.

Usage:

    python trace_java.py [--root DIR] [--out FILE] [--detail LEVEL]
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

TRACER_NAME = "java"
SOURCE_SUFFIXES = (".java",)

IDENT = r"[A-Za-z_$][A-Za-z0-9_$]*"

# Words that are followed by `(` without naming a method.
KEYWORDS = frozenset(
    """if else for while do switch case default try catch finally return throw throws
    new synchronized assert instanceof yield super this break continue class interface
    enum record extends implements package import public private protected static final
    abstract native transient volatile strictfp void var""".split()
)

# Methods the JDK's own types answer to. A receiver this tracer cannot type,
# calling one of these, is a call into the standard library -- and matching the
# name against a repository method that happens to be called `get` or `add`
# would put an edge in the diagram that does not exist.
COMMON_METHODS = frozenset(
    """get put add addAll remove removeAll clear size isEmpty contains containsKey
    containsAll keySet values entrySet iterator hasNext next stream parallelStream
    map filter collect forEach reduce findFirst findAny anyMatch allMatch noneMatch
    sorted distinct limit skip count toList of ofNullable orElse orElseGet orElseThrow
    ifPresent isPresent valueOf toString equals hashCode compareTo clone length charAt
    substring indexOf lastIndexOf split trim strip replace replaceAll matches concat
    startsWith endsWith toLowerCase toUpperCase format join append insert delete
    setLength close flush read write println printf print run start join interrupt
    apply accept test compare build builder create getClass name ordinal getMessage
    getCause printStackTrace intValue longValue doubleValue booleanValue""".split()
)

IO_PATTERNS = (
    r"\b(File|Files|Paths?|FileReader|FileWriter|InputStream|OutputStream|BufferedReader)\b",
    r"\b(Socket|ServerSocket|HttpClient|HttpURLConnection|URLConnection|RestTemplate|WebClient|OkHttpClient)\b",
    r"\b(Connection|Statement|PreparedStatement|ResultSet|DataSource|JdbcTemplate|EntityManager|SessionFactory)\b",
    r"\bSystem\s*\.\s*(out|err|in|exit|getenv)\b",
    r"\.(save|saveAll|delete|deleteById|findById|findAll|persist|merge|flush|executeQuery|executeUpdate)\s*\(",
    r"\.(send|sendAsync|publish|convertAndSend|produce|commit|rollback)\s*\(",
)
IO_RE = re.compile("|".join(IO_PATTERNS))

# Annotation -> entry-point kind, matched against the annotation as written so
# that `@GetMapping` and `@RequestMapping(method = GET)` land on the same rule.
ENTRY_ANNOTATION_RULES: Tuple[Tuple[str, str], ...] = (
    (r"^(Get|Post|Put|Patch|Delete)Mapping\b", "http-route"),
    (r"^RequestMapping\b", "http-route"),
    (r"^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)$", "http-route"),
    (r"^Path\b", "http-route"),
    (r"^(Scheduled|SchedulerLock)\b", "job"),
    (r"^(EventListener|TransactionalEventListener)\b", "event"),
    (r"^(KafkaListener|RabbitListener|JmsListener|SqsListener|StreamListener)\b", "event"),
    (r"^(MessageMapping|SubscribeMapping)\b", "event"),
    (r"^(Bean|PostConstruct|PreDestroy)\b", "lifecycle"),
    (r"^(ShellMethod|Command)\b", "cli-command"),
)

TEST_ANNOTATIONS = re.compile(r"^(Test|ParameterizedTest|RepeatedTest|TestFactory|BeforeEach|AfterEach|BeforeAll|AfterAll)\b")

# Servlet callbacks are entry points by name and by superclass, not by annotation.
SERVLET_METHODS = frozenset({"doGet", "doPost", "doPut", "doDelete", "doHead", "doOptions", "service"})


# --- per-file analysis -----------------------------------------------------

TYPE_RE = re.compile(
    r"\b(?P<keyword>class|interface|enum|record|@interface)\s+(?P<name>" + IDENT + r")"
)
CALL_RE = re.compile(
    r"(?P<path>(?:" + IDENT + r"\s*\.\s*)*)(?P<name>" + IDENT + r")\s*\("
)
NEW_RE = re.compile(r"\bnew\s+(?P<type>" + IDENT + r")\s*(?:<[^;{}]*>\s*)?\(")
LOCAL_RE = re.compile(
    r"(?<![.\w])(?P<type>[A-Z][A-Za-z0-9_$]*)(?:\s*<[^;=(){}]*>)?(?:\s*\[\s*\])?\s+"
    # `:` is in the terminator set for the enhanced-for form, `for (Item x : xs)`,
    # which is where a great deal of Java code names the type of the thing it is
    # about to call methods on.
    r"(?P<var>[a-z_$][A-Za-z0-9_$]*)\s*[=;,):]"
)
VAR_NEW_RE = re.compile(r"\bvar\s+(?P<var>" + IDENT + r")\s*=\s*new\s+(?P<type>" + IDENT + r")")
DECL_TAIL_RE = re.compile(r"\s*(?:throws\s+[\w.,\s]+)?\s*(?P<tail>[{;])")


class JavaFile:
    """One `.java` file: its package, imports, types, and the methods in them."""

    def __init__(self, rel: str, text: str) -> None:
        self.rel = rel
        self.text = text
        self.masked = common.mask_source(text, common.JAVA)
        self.index = common.LineIndex(text)
        self.lines = text.splitlines()
        self.package = ""
        self.imports: Dict[str, str] = {}
        self.static_imports: Dict[str, str] = {}
        self.wildcards: List[str] = []
        self.types: List[Dict[str, Any]] = []
        self.methods: List[Dict[str, Any]] = []

        self._collect_package_and_imports()
        self._collect_types()
        self._collect_methods()

    # -- header -------------------------------------------------------------

    def _collect_package_and_imports(self) -> None:
        match = re.search(r"\bpackage\s+([\w.]+)\s*;", self.masked)
        if match:
            self.package = match.group(1)
        for match in re.finditer(r"\bimport\s+(static\s+)?([\w.]+(?:\.\*)?)\s*;", self.masked):
            static, path = match.group(1), match.group(2)
            if path.endswith(".*"):
                self.wildcards.append(path[:-2])
                continue
            simple = path.rsplit(".", 1)[-1]
            if static:
                self.static_imports[simple] = path
            else:
                self.imports[simple] = path

    # -- types --------------------------------------------------------------

    def _collect_types(self) -> None:
        for match in TYPE_RE.finditer(self.masked):
            brace = self.masked.find("{", match.end())
            semicolon = self.masked.find(";", match.end())
            if brace < 0 or (0 <= semicolon < brace):
                continue  # a forward reference in an import or a `record R();`
            head = self.masked[match.end() : brace]
            end = common.match_brace(self.masked, brace)
            if end < 0:
                continue
            self.types.append(
                {
                    "name": match.group("name"),
                    "keyword": match.group("keyword"),
                    "supers": _supertypes(head),
                    "start": brace,
                    "end": end,
                    "declStart": match.start(),
                    "annotations": self._annotations_above(
                        self.index.start_of(self.index.line_of(match.start()))
                    )[0],
                }
            )
        self.types.sort(key=lambda t: t["start"])

    def enclosing_type(self, position: int) -> Optional[Dict[str, Any]]:
        best = None
        for record in self.types:
            if record["start"] < position < record["end"]:
                if best is None or record["start"] > best["start"]:
                    best = record
        return best

    def type_chain(self, position: int) -> List[str]:
        return [t["name"] for t in self.types if t["start"] < position < t["end"]]

    # -- methods ------------------------------------------------------------

    def _collect_methods(self) -> None:
        """Find every method declaration, and nothing that only looks like one.

        Java gives no keyword to search for — a declaration is a type, a name and
        a parenthesis, which is also what a call is. The three things that
        separate them: a declaration is followed by `{` or `;` (after an optional
        `throws`), it is not preceded by a `.` or by `new`, and it does not sit
        inside another method's body.
        """
        claimed: List[Tuple[int, int]] = []
        for match in CALL_RE.finditer(self.masked):
            name = match.group("name")
            if name in KEYWORDS or match.group("path"):
                continue
            start = match.start("name")
            if any(low < start < high for low, high in claimed):
                continue
            record = self._read_method(match, name, start)
            if record is None:
                continue
            self.methods.append(record)
            claimed.append((record["bodyStart"], record["bodyEnd"]))

    def _read_method(self, match: "re.Match[str]", name: str, start: int) -> Optional[Dict[str, Any]]:
        owner = self.enclosing_type(start)
        if owner is None:
            return None
        params_end = common.match_paren(self.masked, match.end() - 1)
        if params_end < 0:
            return None
        tail = DECL_TAIL_RE.match(self.masked, params_end + 1)
        if not tail:
            return None

        line = self.index.line_of(start)
        line_start = self.index.start_of(line)
        head = self._declaration_head(start)
        if head is None:
            return None

        annotations, above = self._annotations_above(line_start)
        abstract = tail.group("tail") == ";"
        if abstract:
            body_start = body_end = tail.start("tail")
        else:
            body_start = tail.start("tail")
            body_end = common.match_brace(self.masked, body_start)
            if body_end < 0:
                return None

        params = " ".join(self.text[match.end() - 1 : params_end + 1].split())
        modifiers = head.split()
        returns = modifiers[-1] if modifiers and modifiers[-1] not in _MODIFIERS else ""
        chain = self.type_chain(start)
        return {
            "file": self.rel,
            "name": name,
            "qualname": ".".join(chain + [name]),
            "owner": owner["name"],
            "line": line,
            "endLine": self.index.line_of(body_end),
            "signature": " ".join((name + params).split()),
            "returns": returns,
            "purpose": common.doc_comment_before(self.text, above),
            "exported": _is_exported(head, owner),
            "async": False,
            "io": bool(IO_RE.search(self.text[body_start : body_end + 1])),
            "decorators": annotations,
            "isTest": any(TEST_ANNOTATIONS.match(a) for a in annotations),
            "isConstructor": name == owner["name"],
            "abstract": abstract,
            "static": "static" in modifiers,
            "bodyStart": body_start,
            "bodyEnd": body_end,
            "params": params,
        }

    def _declaration_head(self, start: int) -> Optional[str]:
        """The modifiers and return type in front of a name, or None if it is a call.

        Anything from the previous statement boundary up to the name. A call has
        either nothing there, a `.` (it has a receiver), or a keyword such as
        `return` or `new`. A declaration has a type, possibly preceded by
        modifiers and generics.
        """
        boundary = max(
            self.masked.rfind(";", 0, start),
            self.masked.rfind("{", 0, start),
            self.masked.rfind("}", 0, start),
            self.masked.rfind(")", 0, start),
        )
        head = self.masked[boundary + 1 : start]
        head = re.sub(r"@" + IDENT + r"(?:\s*\([^)]*\))?", " ", head)
        head = re.sub(r"<[^<>]*>", " ", head).strip()
        if not head or head.endswith("."):
            return None
        last = head.split()[-1]
        if last in KEYWORDS and last not in _MODIFIERS and last != "void":
            return None
        if not re.match(r"^[\w.$\[\]]+$", last):
            return None
        return head

    def _annotations_above(self, line_start: int) -> Tuple[List[str], int]:
        """The annotations stacked above a declaration, read from the source text.

        Read unmasked because the payload is the part that matters:
        `@GetMapping("/users")` is an entry point *and* a URL, and the URL is
        exactly what masking removes.
        """
        annotations: List[str] = []
        cursor = line_start
        while cursor > 0:
            previous_start = self.text.rfind("\n", 0, cursor - 1) + 1
            raw = self.text[previous_start : cursor - 1].strip()
            if raw.startswith("@") and not raw.startswith("@interface"):
                annotations.insert(0, raw[1:].strip())
                cursor = previous_start
                continue
            break
        # An annotation written on the declaration's own line, which is the norm
        # for the short ones: `@Override public String toString() {`.
        line_end = self.text.find("\n", line_start)
        own_line = self.text[line_start : line_end if line_end > 0 else len(self.text)]
        for inline in re.finditer(r"@(" + IDENT + r"(?:\s*\([^)]*\))?)", own_line):
            annotations.append(inline.group(1).strip())
        return annotations, cursor


_MODIFIERS = frozenset(
    """public private protected static final abstract synchronized native transient
    volatile strictfp default sealed non-sealed""".split()
)


def _is_exported(head: str, owner: Dict[str, Any]) -> bool:
    """Public API, biased towards true.

    Wrongly calling something private produces a false dead-code claim, which is
    the more expensive mistake. An interface member is public whether or not it
    says so, and a package-private method is reachable from its own package.
    """
    if "private" in head.split():
        return False
    if owner["keyword"] == "interface":
        return True
    return True


def _supertypes(head: str) -> List[str]:
    names: List[str] = []
    for keyword in ("extends", "implements", "permits"):
        match = re.search(r"\b" + keyword + r"\b(?P<list>[^{]*)", head)
        if not match:
            continue
        for part in match.group("list").split(","):
            cleaned = re.sub(r"<[^>]*>", "", part).strip()
            cleaned = cleaned.split()[0] if cleaned.split() else ""
            cleaned = cleaned.rsplit(".", 1)[-1]
            if cleaned and cleaned not in ("extends", "implements", "permits"):
                names.append(cleaned)
    return names


# --- the repository --------------------------------------------------------


class Repository:
    def __init__(self, root: str, detail: str) -> None:
        self.root = root
        self.detail = detail
        self.files: Dict[str, JavaFile] = {}
        self.census: List[Dict[str, Any]] = []
        self.skipped: List[Dict[str, Any]] = []
        self.functions: List[Dict[str, Any]] = []
        self.resolution = common.Resolution()
        self.types: Dict[str, Dict[str, Any]] = {}
        self.by_name: Dict[str, List[Dict[str, Any]]] = {}
        self.methods: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
        self.fields: Dict[str, Dict[str, str]] = {}

    def index(self) -> None:
        common.assign_ids(self.functions)
        for rel, source in self.files.items():
            for record in source.types:
                self.types.setdefault(
                    record["name"],
                    {"file": rel, "supers": record["supers"], "keyword": record["keyword"]},
                )
            self._collect_fields(source)
        for fn in self.functions:
            self.by_name.setdefault(fn["name"], []).append(fn)
            self.methods.setdefault((fn["owner"], fn["name"]), []).append(fn)

    def _collect_fields(self, source: JavaFile) -> None:
        """Field types, read from the parts of a class body no method claimed.

        A field is where a Java service keeps its collaborators, so without this
        every `this.repository.save(...)` in the repository resolves to nothing —
        which is most of the call graph in most Java applications.
        """
        bodies = [(m["bodyStart"], m["bodyEnd"]) for m in source.methods]
        for record in source.types:
            spans: List[Tuple[int, int]] = []
            cursor = record["start"]
            for low, high in sorted(bodies):
                if low < record["start"] or high > record["end"]:
                    continue
                spans.append((cursor, low))
                cursor = high
            spans.append((cursor, record["end"]))
            text = " ".join(source.masked[a:b] for a, b in spans if a < b)
            fields = self.fields.setdefault(record["name"], {})
            for match in LOCAL_RE.finditer(text):
                fields.setdefault(match.group("var"), match.group("type"))

    # -- resolution ---------------------------------------------------------

    def resolve_all(self) -> None:
        for fn in self.functions:
            source = self.files[fn["file"]]
            if fn["abstract"]:
                fn["calls"] = []
                continue
            body = source.masked[fn["bodyStart"] : fn["bodyEnd"] + 1]
            variables = self._variable_types(fn, body)
            seen: Set[Tuple[str, int]] = set()
            calls: List[Dict[str, Any]] = []
            for match in CALL_RE.finditer(body):
                name = match.group("name")
                if name in KEYWORDS:
                    continue
                line = source.index.line_of(fn["bodyStart"] + match.start("name"))
                constructed = _preceded_by_new(body, match.start())
                chained = not match.group("path") and _follows_a_dot(body, match.start())
                target = self._resolve(
                    fn, source, variables, match.group("path"), name, line, constructed, chained
                )
                if target is None:
                    continue
                key = (target[0], line)
                if key in seen:
                    continue
                seen.add(key)
                calls.append({"to": target[0], "name": name, "line": line, "confidence": target[1]})
            fn["calls"] = sorted(calls, key=lambda c: (c["line"], c["to"]))

    def _variable_types(self, fn: Dict[str, Any], body: str) -> Dict[str, str]:
        variables = dict(self.fields.get(fn["owner"], {}))
        for match in LOCAL_RE.finditer(fn["params"]):
            variables[match.group("var")] = match.group("type")
        for match in LOCAL_RE.finditer(body):
            variables[match.group("var")] = match.group("type")
        for match in VAR_NEW_RE.finditer(body):
            variables[match.group("var")] = match.group("type")
        return variables

    def _resolve(
        self,
        fn: Dict[str, Any],
        source: JavaFile,
        variables: Dict[str, str],
        path: str,
        name: str,
        line: int,
        constructed: bool,
        chained: bool,
    ) -> Optional[Tuple[str, str]]:
        if constructed:
            return self._resolve_constructor(fn, name)

        segments = [m.group(1) for m in re.finditer(r"(" + IDENT + r")\s*\.", path)]
        if not segments and not chained:
            return self._resolve_unqualified(fn, source, name, line)

        receiver = segments[-1] if segments else None
        owner: Optional[str] = None
        if receiver in ("this", None) and not chained:
            owner = fn["owner"]
        elif receiver == "super":
            for parent in self.types.get(fn["owner"], {}).get("supers", []):
                found = self._lookup(parent, name)
                if found:
                    return (found, "exact")
        elif receiver in self.types:
            owner = receiver  # a static call on a type this repository defines
        elif receiver and receiver in variables:
            owner = variables[receiver]
        elif receiver and receiver in source.imports:
            self.resolution.external_call(
                source.imports[receiver] + "." + name, source.imports[receiver], fn["id"]
            )
            return None

        if owner:
            found = self._lookup(owner, name)
            if found:
                return (found, "exact")
            candidates = self.methods.get((owner, name), [])
            if len(candidates) > 1:
                self.resolution.ambiguous_call(fn["id"], name, line, [c["id"] for c in candidates])
                return None

        if name in COMMON_METHODS:
            # A receiver this tracer cannot type, calling something every JDK
            # collection answers to. The repository may define a `get`; joining
            # the two would invent an edge.
            return None
        return self._by_unique_name(fn, name, line)

    def _resolve_constructor(self, fn: Dict[str, Any], type_name: str) -> Optional[Tuple[str, str]]:
        candidates = self.methods.get((type_name, type_name), [])
        if len(candidates) == 1:
            return (candidates[0]["id"], "exact")
        if type_name not in self.types:
            self.resolution.external_call("new " + type_name, type_name, fn["id"])
        return None

    def _resolve_unqualified(
        self, fn: Dict[str, Any], source: JavaFile, name: str, line: int
    ) -> Optional[Tuple[str, str]]:
        found = self._lookup(fn["owner"], name)
        if found:
            return (found, "exact")
        static = source.static_imports.get(name)
        if static:
            owner = static.rsplit(".", 2)[-2] if static.count(".") >= 1 else ""
            found = self._lookup(owner, name)
            if found:
                return (found, "exact")
        return self._by_unique_name(fn, name, line)

    def _lookup(self, type_name: str, method: str, seen: Optional[Set[str]] = None) -> Optional[str]:
        """A method on a type, following `extends` and `implements` upward.

        Interfaces are walked as well as classes, so a call declared on an
        interface this repository defines resolves to that declaration rather
        than being guessed at one of its implementations.
        """
        seen = seen or set()
        if not type_name or type_name in seen:
            return None
        seen.add(type_name)
        candidates = self.methods.get((type_name, method), [])
        if len(candidates) == 1:
            return candidates[0]["id"]
        if len(candidates) > 1:
            return None
        for parent in self.types.get(type_name, {}).get("supers", []):
            found = self._lookup(parent, method, seen)
            if found:
                return found
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
    i = start - 1
    while i >= 0 and body[i] in " \t\n\r":
        i -= 1
    return i >= 0 and body[i] in ".)"


def _preceded_by_new(body: str, start: int) -> bool:
    head = body[max(0, start - 8) : start]
    return bool(re.search(r"\bnew\s+$", head))


# --- entry points ----------------------------------------------------------


def annotation_entry(annotation: str) -> Optional[Tuple[str, str]]:
    for pattern, kind in ENTRY_ANNOTATION_RULES:
        if re.match(pattern, annotation):
            return kind, _annotation_detail(annotation, kind)
    return None


def _annotation_detail(annotation: str, kind: str) -> str:
    if kind != "http-route":
        return annotation
    verb = re.match(r"(Get|Post|Put|Patch|Delete)Mapping", annotation)
    path = re.search(r"\"([^\"]*)\"", annotation)
    method = verb.group(1).upper() if verb else re.match(r"[A-Z]+", annotation)
    label = method if isinstance(method, str) else (method.group(0) if method else "")
    return (label + " " + path.group(1)).strip() if path else (label or annotation)


def collect_entry_points(repo: Repository) -> List[Dict[str, Any]]:
    """Where execution can arrive: an annotation, `main`, or a servlet callback.

    A class-level `@RequestMapping` prefix is not composed with the method's own
    path here. The detail is what the annotation says, and saying more than the
    annotation says would be inventing a URL.
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
        matched = False
        for annotation in fn["decorators"]:
            found = annotation_entry(annotation)
            if found:
                add(fn, found[0], found[1])
                matched = True
                break
        if matched:
            continue
        if fn["name"] == "main" and fn["static"] and "String" in fn["params"]:
            add(fn, "cli-command", fn["file"])
        elif fn["name"] in SERVLET_METHODS and _extends_servlet(repo, fn["owner"]):
            add(fn, "http-route", fn["name"])

    return sorted(entries.values(), key=lambda e: (e["file"], e["line"]))


def _extends_servlet(repo: Repository, type_name: str, seen: Optional[Set[str]] = None) -> bool:
    seen = seen or set()
    if type_name in seen:
        return False
    seen.add(type_name)
    supers = repo.types.get(type_name, {}).get("supers", [])
    if any(parent.endswith("Servlet") for parent in supers):
        return True
    return any(_extends_servlet(repo, parent, seen) for parent in supers)


# --- output ----------------------------------------------------------------


def build_functions(repo: Repository) -> List[Dict[str, Any]]:
    records = []
    for fn in repo.functions:
        source = repo.files[fn["file"]]
        loc = fn["endLine"] - fn["line"] + 1
        record = {
            "id": fn["id"],
            "name": fn["name"],
            "qualname": fn["qualname"],
            "file": fn["file"],
            "line": fn["line"],
            "loc": loc,
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
        # A constructor shares its class's name, so it can only ever collide
        # with a supertype the class is named after -- never an override.
        overrides = (
            []
            if fn["isConstructor"]
            else common.overridden_names(repo.types, repo.methods, fn["owner"], fn["name"])
        )
        if overrides:
            record["overrides"] = overrides
        snippet = common.snippet_for(source.lines, fn["line"], fn["endLine"], loc, repo.detail)
        if snippet is not None:
            record["snippet"] = snippet
        records.append(record)
    return records


LIMITS = common.BASE_LIMITS + (
    "A call through an interface or an abstract type resolves to the declaration it is "
    "written against, not to the implementation the container injects: which one runs is "
    "a runtime fact.",
    "Overloads are distinguished by line, not by parameter types, so a call that could "
    "mean either overload is listed as ambiguous rather than assigned to one.",
    "Annotation-driven wiring beyond the listed entry-point annotations -- AOP advice, "
    "`@Configuration` bean graphs, reflection-based frameworks -- is invisible to it.",
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
        source = JavaFile(rel, text)
        repo.files[rel] = source
        try:
            size = os.path.getsize(path)
        except OSError:
            size = 0
        repo.census.append({"path": rel, "size": size, "hash": common.file_hash(path)})

        in_test_file = common.is_test_path(rel)
        for fn in source.methods:
            fn["role"] = "test" if (in_test_file or fn["isTest"]) else "source"
            repo.functions.append(fn)

    repo.index()
    repo.resolve_all()
    return common.build_envelope(
        tracer=TRACER_NAME,
        language="java",
        root_abs=root_abs.replace(os.sep, "/"),
        detail=detail,
        files=repo.census,
        skipped=repo.skipped,
        functions=build_functions(repo),
        entry_points=collect_entry_points(repo),
        resolution=repo.resolution,
        limits=LIMITS,
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    return common.run_cli(
        "trace_java.py",
        "Static call-graph tracer for Java repositories (code-flow).",
        trace,
        argv,
    )


if __name__ == "__main__":
    raise SystemExit(main())
