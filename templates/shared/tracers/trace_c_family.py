#!/usr/bin/env python3
"""Static call-graph tracer for C, C++, Objective-C and C# repositories.

One tracer for four languages because they are four dialects of one shape: a
brace-delimited body, a parenthesised parameter list, and a declaration that is
distinguished from a call only by what follows the closing parenthesis. What
differs between them — how a type is declared, how a method is written, what
counts as an entry point — is a table in this file rather than a separate
tracer, so that a repository mixing C and C++, or C# and generated C, is read
once and catalogued together.

It does not invoke a compiler and does not read a build directory. A tracer that
needed a configured build would be useless on exactly the repository most in
need of a map, and for C that means no preprocessor: `#include` is read as a
dependency edge rather than followed, and `#define` is not expanded.

What is worth knowing before trusting the output:

**A header declaration is evidence.** A call to a function declared in a header
this file includes resolves to that function's definition. This is the one
resolution that makes a C call graph possible at all, and it is why `.h` files
are read as carefully as `.c` files.

**The preprocessor is not run.** A function inside `#if` is catalogued whether
or not that branch is compiled, a call that only exists inside a macro body is
not found, and a `#define`d name is neither expanded nor resolved. Preprocessor
lines are blanked before parsing, so a macro whose body contains an unbalanced
brace cannot move a function's boundary.

**Overloads and templates share a name.** Two definitions of one name in one
file get the `_l<line>` suffix the id rule specifies, and a call that could mean
either is listed as ambiguous rather than assigned to the first.

**Objective-C is matched on selectors.** A method's name is its whole selector
(`initWithPath:andCache:`), which is what a message send names, so the two
match. Dynamic dispatch — `performSelector:`, `respondsToSelector:`, anything
built from a string — is invisible.

Usage:

    python trace_c_family.py [--root DIR] [--out FILE] [--detail LEVEL]
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

TRACER_NAME = "c-family"

SUFFIX_LANGUAGE = {
    ".c": "c", ".h": "c",
    ".cc": "cpp", ".cpp": "cpp", ".cxx": "cpp", ".c++": "cpp",
    ".hpp": "cpp", ".hh": "cpp", ".hxx": "cpp", ".ipp": "cpp", ".tpp": "cpp",
    ".m": "objc", ".mm": "objc",
    ".cs": "csharp",
}
SOURCE_SUFFIXES = tuple(sorted(SUFFIX_LANGUAGE))
HEADER_SUFFIXES = (".h", ".hpp", ".hh", ".hxx", ".ipp", ".tpp")

FLAVORS = {
    # `.h` is read with the C++ lexer rather than the C one: a header in a C++
    # project is C++, and the extra literal forms it understands do not occur in
    # C, so reading C with it costs nothing.
    "c": common.CPP,
    "cpp": common.CPP,
    "objc": common.OBJC,
    "csharp": common.CSHARP,
}

IDENT = r"[A-Za-z_][A-Za-z0-9_]*"

KEYWORDS = frozenset(
    """if else for while do switch case default try catch finally return goto break
    continue new delete sizeof alignof typeof decltype static_cast dynamic_cast
    const_cast reinterpret_cast throw using namespace typedef struct class union enum
    template typename public private protected virtual explicit inline static extern
    const volatile mutable constexpr consteval noexcept override final friend operator
    and or not xor bitand bitor compl this nullptr true false auto void register
    signed unsigned short long int char float double bool wchar_t char8_t char16_t
    char32_t defined lock unsafe fixed checked unchecked stackalloc await yield in out
    ref params where when is as base foreach select from group into orderby let join
    equals by ascending descending on""".split()
)

# Methods the standard libraries answer to. A receiver this tracer cannot type,
# calling one of these, is a call into the runtime -- and matching the name
# against a repository function called `size` or `count` would invent an edge.
COMMON_METHODS = frozenset(
    """size length count empty clear begin end cbegin cend rbegin rend front back
    push push_back push_front pop pop_back pop_front insert erase find at get set
    data c_str str append substr replace resize reserve swap emplace emplace_back
    first second value has_value value_or reset release lock unlock notify_one
    notify_all wait join detach close open flush read write seek tell good fail eof
    to_string toString ToString Add AddRange Remove RemoveAt Contains ContainsKey
    Clear Count Any All First FirstOrDefault Single SingleOrDefault Where Select
    SelectMany OrderBy ToList ToArray ToDictionary Skip Take Concat Equals GetHashCode
    GetType Dispose Invoke Wait Result Length Substring Split Trim Replace Join Format
    Parse TryParse Append AppendLine WriteLine Write ReadLine copy retain release
    autorelease description isEqual hash class respondsToSelector""".split()
)

IO_PATTERNS = (
    r"\b(fopen|fclose|fread|fwrite|fprintf|fscanf|printf|scanf|puts|getchar|open|read|write|close)\s*\(",
    r"\b(socket|bind|listen|accept|connect|send|recv|sendto|recvfrom)\s*\(",
    r"\b(std::(?:ifstream|ofstream|fstream|cout|cerr|cin))\b",
    r"\b(curl_easy_perform|sqlite3_|mysql_|PQexec|redisCommand)\w*\s*\(",
    r"\b(File|Directory|FileStream|StreamReader|StreamWriter|HttpClient|SqlConnection|SqlCommand|DbContext)\b",
    r"\b(Console\s*\.\s*(?:Write|WriteLine|ReadLine))\b",
    r"\b(NSFileManager|NSURLSession|NSData|NSLog)\b",
)
IO_RE = re.compile("|".join(IO_PATTERNS))

# Attribute -> entry-point kind, for C#.
ENTRY_ATTRIBUTE_RULES: Tuple[Tuple[str, str], ...] = (
    (r"^Http(Get|Post|Put|Patch|Delete|Head|Options)\b", "http-route"),
    (r"^Route\b", "http-route"),
    (r"^(FunctionName|Function)\b", "job"),
    (r"^(EventHandler|Subscribe)\b", "event"),
    (r"^(Command|Verb)\b", "cli-command"),
)
TEST_ATTRIBUTES = re.compile(r"^(Fact|Theory|Test|TestMethod|TestCase|SetUp|TearDown|Benchmark)\b")

# The gtest and Catch2 macros define a test function without ever writing a
# declaration this tracer would otherwise recognize.
TEST_MACRO_RE = re.compile(
    r"\b(?P<macro>TEST|TEST_F|TEST_P|TYPED_TEST|TEST_CASE|SCENARIO|BENCHMARK)\s*\("
)


# --- per-file analysis -----------------------------------------------------

INCLUDE_RE = re.compile(r"^[ \t]*#\s*(?:include|import)\s*[\"<]([^\">]+)[\">]", re.M)
DECL_RE = re.compile(
    r"(?P<owner>(?:" + IDENT + r"\s*::\s*)*)(?P<name>~?" + IDENT + r")\s*(?:<[^<>()]*>\s*)?\("
)
TAIL_RE = re.compile(
    r"\s*(?:const\b|volatile\b|mutable\b|noexcept(?:\s*\([^)]*\))?|override\b|final\b"
    r"|&&?|throw\s*\([^)]*\)|->\s*[\w:<>*&\s]+?|where\s+[^{;=]+)*\s*(?P<tail>[{;:=])"
)
TYPE_RE = re.compile(
    r"\b(?P<keyword>class|struct|union|interface|record)\s+"
    r"(?:[A-Z_][A-Z0-9_]*\s+)?"          # an export macro: `class MYLIB_API Foo`
    r"(?P<name>" + IDENT + r")\b(?P<head>[^{;]*)"
)
OBJC_BLOCK_RE = re.compile(r"@(?P<keyword>interface|implementation|protocol)\s+(?P<name>" + IDENT + r")(?P<head>[^\n]*)")
OBJC_METHOD_RE = re.compile(r"^[ \t]*(?P<kind>[-+])\s*\(\s*(?P<ret>[^)]*?)\s*\)\s*(?P<sel>[^;{]+)", re.M)
LOCAL_RE = re.compile(
    r"(?<![\w.>])(?P<type>[A-Za-z_][A-Za-z0-9_]*)(?:\s*<[^;=(){}]*>)?"
    r"(?:\s*[*&]+\s*|\s+)"      # `Foo *p`, `Foo& r`, `Foo x` -- all one shape
    r"(?P<var>[a-z_][A-Za-z0-9_]*)\s*[=;,)\[]"
)
AUTO_NEW_RE = re.compile(
    r"\b(?:auto|var)\s+(?P<var>" + IDENT + r")\s*=\s*(?:new\s+|std::make_(?:unique|shared)<)?"
    r"(?P<type>" + IDENT + r")"
)
CALL_RE = re.compile(
    r"(?P<path>(?:" + IDENT + r"\s*(?:::|->|\.)\s*)*)(?P<name>" + IDENT + r")\s*(?:<[^<>();]*>\s*)?\("
)


def language_for(rel: str, text: str) -> Optional[str]:
    """Which of the four dialects ``rel`` is written in, or None if it is neither.

    `.m` is Objective-C here and MATLAB, Mercury or Mathematica elsewhere, so it
    is claimed only when the file says so. A `.m` that is not Objective-C is
    reported as skipped-unparsed rather than read as if it were: a MATLAB script
    read by a C parser produces confident nonsense.
    """
    suffix = "." + rel.rsplit(".", 1)[-1].lower()
    language = SUFFIX_LANGUAGE.get(suffix)
    looks_objc = bool(
        re.search(r"^\s*(?:@(?:interface|implementation|import|protocol|class)\b|#import\b)", text, re.M)
    )
    if suffix == ".h":
        # A `.h` is C, C++ or Objective-C, and only its contents say which.
        return "objc" if looks_objc else language
    if language != "objc":
        return language
    return "objc" if looks_objc else None


class SourceFile:
    """One translation unit or header, read once."""

    def __init__(self, rel: str, text: str, language: str) -> None:
        self.rel = rel
        self.text = text
        self.language = language
        self.masked = common.mask_source(text, FLAVORS[language])
        self.index = common.LineIndex(text)
        self.lines = text.splitlines()
        self.is_header = rel.lower().endswith(HEADER_SUFFIXES)
        self.includes = [m.group(1) for m in INCLUDE_RE.finditer(text)]
        self.types: List[Dict[str, Any]] = []
        self.functions: List[Dict[str, Any]] = []
        self.prototypes: Set[str] = set()
        self.interface_selectors: Set[str] = set()
        self.declared_purposes: Dict[str, str] = {}

        if language == "objc":
            self._collect_objc_blocks()
        self._collect_types()
        self._collect_functions()
        if language == "objc":
            self._collect_objc_methods()
        self._collect_test_macros()

    # -- types --------------------------------------------------------------

    def _collect_types(self) -> None:
        for match in TYPE_RE.finditer(self.masked):
            head = match.group("head")
            brace = self.masked.find("{", match.end("name"))
            semicolon = self.masked.find(";", match.end("name"))
            if brace < 0 or (0 <= semicolon < brace):
                continue  # a forward declaration: `class Foo;`
            end = common.match_brace(self.masked, brace)
            if end < 0:
                continue
            self.types.append(
                {"name": match.group("name"), "keyword": match.group("keyword"),
                 "supers": _bases(head), "start": brace, "end": end,
                 "declStart": match.start(), "objc": False}
            )
        self.types.sort(key=lambda t: t["start"])

    def _collect_objc_blocks(self) -> None:
        """`@interface`/`@implementation` bodies, which end at `@end`, not at `}`."""
        for match in OBJC_BLOCK_RE.finditer(self.masked):
            end = self.masked.find("@end", match.end())
            if end < 0:
                continue
            head = match.group("head")
            self.types.append(
                {"name": match.group("name"), "keyword": match.group("keyword"),
                 "supers": _bases(head), "start": match.start(), "end": end,
                 "declStart": match.start(), "objc": True}
            )

    def enclosing_type(self, position: int) -> Optional[Dict[str, Any]]:
        best = None
        for record in self.types:
            if record["start"] < position < record["end"]:
                if best is None or record["start"] > best["start"]:
                    best = record
        return best

    def type_chain(self, position: int) -> List[str]:
        return [t["name"] for t in self.types if t["start"] < position < t["end"]]

    # -- functions ----------------------------------------------------------

    def _collect_functions(self) -> None:
        claimed: List[Tuple[int, int]] = []
        for match in DECL_RE.finditer(self.masked):
            name = match.group("name")
            if name.lstrip("~") in KEYWORDS:
                continue
            start = match.start("name")
            if any(low < start < high for low, high in claimed):
                continue
            if _preceded_by_member_access(self.masked, match.start("owner") or start):
                continue
            record = self._read_function(match, name, start)
            if record is None:
                continue
            if record["bodyStart"] < 0:
                self.prototypes.add(name)
                if record.get("purpose"):
                    self.declared_purposes.setdefault(name, record["purpose"])
                continue
            self.functions.append(record)
            claimed.append((record["bodyStart"], record["bodyEnd"]))

    def _read_function(self, match: "re.Match[str]", name: str, start: int) -> Optional[Dict[str, Any]]:
        params_end = common.match_paren(self.masked, match.end() - 1)
        if params_end < 0:
            return None
        tail = TAIL_RE.match(self.masked, params_end + 1)
        if not tail:
            return None
        marker = tail.group("tail")
        body_start = -1
        if marker == "{":
            body_start = tail.start("tail")
        elif marker == ":":
            body_start = _body_after_init_list(self.masked, tail.start("tail"))
            if body_start < 0:
                return None
        elif marker == "=":
            after = tail.end("tail")
            if self.masked[after : after + 1] != ">":
                return None  # `= default;`, `= 0;`, or an assignment
            body_start = after + 1
            body_end = self.masked.find(";", body_start)
            if body_end < 0:
                return None
            return self._function_record(match, name, start, params_end, body_start, body_end)
        elif marker == ";":
            # A prototype. Not a function, but the declaration a caller in
            # another file resolves through, so its name is kept.
            head = self._declaration_head(start, match.start("owner"))
            if head is None:
                return None
            line_start = self.index.start_of(self.index.line_of(start))
            _, above = self._attributes_above(line_start)
            return {"bodyStart": -1, "bodyEnd": -1,
                    "purpose": common.doc_comment_before(self.text, above)}
        if body_start < 0:
            return None
        body_end = common.match_brace(self.masked, body_start)
        if body_end < 0:
            return None
        return self._function_record(match, name, start, params_end, body_start, body_end)

    def _function_record(
        self, match: "re.Match[str]", name: str, start: int,
        params_end: int, body_start: int, body_end: int,
    ) -> Optional[Dict[str, Any]]:
        head = self._declaration_head(start, match.start("owner"))
        owner_path = [p for p in re.findall(IDENT, match.group("owner") or "")]
        enclosing = self.enclosing_type(start)
        chain = self.type_chain(start)
        owner = owner_path[-1] if owner_path else (enclosing["name"] if enclosing else None)
        if head is None:
            # A constructor and a destructor have no return type, so there is
            # nothing in front of the name to recognize them by -- only the fact
            # that the name is the class's own. Without this, every C++ class in
            # the repository is catalogued without the function that builds it.
            if owner and name.lstrip("~") == owner:
                head = ""
            else:
                return None

        line = self.index.line_of(start)
        line_start = self.index.start_of(line)
        attributes, above = self._attributes_above(line_start)
        params = " ".join(self.text[match.end() - 1 : params_end + 1].split())
        modifiers = head.split()
        return {
            "file": self.rel,
            "name": name,
            "qualname": "::".join((chain or owner_path) + [name]),
            "owner": owner,
            "line": line,
            "endLine": self.index.line_of(body_end),
            "signature": " ".join((name + params).split()),
            "purpose": common.doc_comment_before(self.text, above),
            "exported": _is_exported(self.language, head, self.is_header, enclosing),
            "async": "async" in modifiers,
            "static": "static" in modifiers,
            "io": bool(IO_RE.search(self.text[body_start : body_end + 1])),
            "decorators": attributes,
            "isTest": any(TEST_ATTRIBUTES.match(a) for a in attributes),
            "selector": None,
            "bodyStart": body_start,
            "bodyEnd": body_end,
            "params": params,
        }

    def _declaration_head(self, start: int, owner_start: Optional[int]) -> Optional[str]:
        """The type and modifiers in front of a name, or None if this is a call."""
        anchor = owner_start if owner_start is not None and owner_start < start else start
        boundary = max(
            self.masked.rfind(";", 0, anchor),
            self.masked.rfind("{", 0, anchor),
            self.masked.rfind("}", 0, anchor),
            self.masked.rfind(")", 0, anchor),
            self.masked.rfind(",", 0, anchor),
            self.masked.rfind(":", 0, anchor),
        )
        head = self.masked[boundary + 1 : anchor]
        head = re.sub(r"\[[^\]]*\]", " ", head)      # a C# attribute
        head = re.sub(r"<[^<>]*>", " ", head).strip()
        if not head:
            return None
        if head.endswith(".") or head.endswith("->"):
            return None
        tokens = head.replace("*", " ").replace("&", " ").split()
        if not tokens:
            return None
        if "namespace" in tokens or "using" in tokens:
            # `namespace std _GLIBCXX_VISIBILITY(default) { ... }` is a namespace
            # with an attribute macro on it, and reads exactly like a function
            # returning `std`. Found in libstdc++, where it made three headers
            # look like one six-thousand-line function each.
            return None
        last = tokens[-1]
        if last in KEYWORDS and last not in _TYPE_KEYWORDS and last not in _MODIFIERS:
            return None
        if not re.match(r"^[\w:\[\]]+$", last):
            return None
        return head

    def _attributes_above(self, line_start: int) -> Tuple[List[str], int]:
        """C# attributes stacked above a declaration, read from the source text."""
        attributes: List[str] = []
        cursor = line_start
        while cursor > 0:
            previous_start = self.text.rfind("\n", 0, cursor - 1) + 1
            raw = self.text[previous_start : cursor - 1].strip()
            if raw.startswith("[") and raw.endswith("]"):
                attributes.insert(0, raw[1:-1].strip())
                cursor = previous_start
                continue
            break
        line_end = self.text.find("\n", line_start)
        own_line = self.text[line_start : line_end if line_end > 0 else len(self.text)]
        for inline in re.finditer(r"\[(" + IDENT + r"(?:\([^)]*\))?)\]", own_line):
            attributes.append(inline.group(1).strip())
        return attributes, cursor

    # -- Objective-C --------------------------------------------------------

    def _collect_objc_methods(self) -> None:
        """`- (void)doThing:(id)a and:(id)b { ... }`, named by its whole selector.

        The selector is the name, because a message send names the selector and
        nothing else: matching on `doThing` alone would join two unrelated
        methods that happen to share a first keyword.
        """
        for match in OBJC_METHOD_RE.finditer(self.masked):
            selector = _selector_of(match.group("sel"))
            if not selector:
                continue
            cursor = match.end("sel")
            while cursor < len(self.masked) and self.masked[cursor] in " \t\n\r":
                cursor += 1
            if cursor >= len(self.masked):
                continue
            block = self.enclosing_type(match.start())
            if self.masked[cursor] != "{":
                if block and block["keyword"] in ("interface", "protocol"):
                    self.interface_selectors.add(selector)
                    purpose = common.doc_comment_before(
                        self.text, self.index.start_of(self.index.line_of(match.start()))
                    )
                    if purpose:
                        self.declared_purposes.setdefault(selector, purpose)
                continue
            body_end = common.match_brace(self.masked, cursor)
            if body_end < 0:
                continue
            line = self.index.line_of(match.start())
            line_start = self.index.start_of(line)
            self.functions.append(
                {
                    "file": self.rel,
                    "name": selector,
                    "qualname": ((block["name"] + "::") if block else "") + selector,
                    "owner": block["name"] if block else None,
                    "line": line,
                    "endLine": self.index.line_of(body_end),
                    "signature": " ".join(self.text[match.start() : cursor].split()),
                    "purpose": common.doc_comment_before(self.text, line_start),
                    "exported": True,  # decided in `finish_objc_exports`, once the
                    "async": False,    # file's own @interface has been read
                    "static": match.group("kind") == "+",
                    "io": bool(IO_RE.search(self.text[cursor : body_end + 1])),
                    "decorators": [],
                    "isTest": selector.startswith("test"),
                    "selector": selector,
                    "bodyStart": cursor,
                    "bodyEnd": body_end,
                    "params": self.text[match.start("sel") : cursor],
                }
            )


    # -- macro-defined tests ------------------------------------------------

    def _collect_test_macros(self) -> None:
        """gtest and Catch2 define a test body with a macro and no declaration.

        Left out, every assertion helper a test suite calls looks unreached, and
        the map reports a repository's test scaffolding as dead code.
        """
        claimed = [(f["bodyStart"], f["bodyEnd"]) for f in self.functions]
        for match in TEST_MACRO_RE.finditer(self.masked):
            paren = match.end() - 1
            args_end = common.match_paren(self.masked, paren)
            if args_end < 0:
                continue
            cursor = args_end + 1
            while cursor < len(self.masked) and self.masked[cursor] in " \t\n\r":
                cursor += 1
            if cursor >= len(self.masked) or self.masked[cursor] != "{":
                continue
            if any(low < match.start() < high for low, high in claimed):
                continue
            body_end = common.match_brace(self.masked, cursor)
            if body_end < 0:
                continue
            parts = [p.strip() for p in self.text[paren + 1 : args_end].split(",")]
            name = "_".join(p for p in parts if re.match(r"^" + IDENT + r"$", p))
            if not name:
                name = match.group("macro")
            line = self.index.line_of(match.start())
            self.functions.append(
                {
                    "file": self.rel, "name": name, "qualname": name, "owner": None,
                    "line": line, "endLine": self.index.line_of(body_end),
                    "signature": " ".join(self.text[match.start() : cursor].split()),
                    "purpose": common.doc_comment_before(self.text, self.index.start_of(line)),
                    "exported": False, "async": False, "static": False,
                    "io": bool(IO_RE.search(self.text[cursor : body_end + 1])),
                    "decorators": [match.group("macro")], "isTest": True, "selector": None,
                    "bodyStart": cursor, "bodyEnd": body_end, "params": "()",
                }
            )


_TYPE_KEYWORDS = frozenset(
    """void int char float double bool auto long short signed unsigned wchar_t
    char8_t char16_t char32_t string object decimal byte sbyte uint ulong ushort
    nint nuint dynamic struct class enum union id instancetype""".split()
)
_MODIFIERS = frozenset(
    """static inline extern const constexpr consteval virtual explicit friend
    public private protected internal sealed abstract override async partial unsafe
    readonly volatile mutable template typename thread_local""".split()
)
_ACCESS_WORDS = frozenset({"public", "private", "protected", "virtual", "internal"})


def _bases(head: str) -> List[str]:
    """The base classes, interfaces and protocols named after a `:`."""
    if ":" not in head:
        return []
    tail = head.split(":", 1)[1]
    names = [n for n in re.findall(IDENT, tail) if n not in _ACCESS_WORDS]
    return names


def _is_exported(language: str, head: str, is_header: bool, enclosing: Optional[Dict[str, Any]]) -> bool:
    """Public API, biased towards true.

    Wrongly calling something private produces a false dead-code claim, which is
    the more expensive mistake. In C and C++ the one reliable negative signal is
    file-scope `static`, which really does mean "not visible outside this file";
    a `static` *member* means something else entirely and is left alone.
    """
    words = head.split()
    if language == "csharp":
        return "private" not in words
    if "static" in words and enclosing is None:
        return False
    return True


def _preceded_by_member_access(masked: str, position: int) -> bool:
    i = position - 1
    while i >= 0 and masked[i] in " \t\n\r":
        i -= 1
    if i < 0:
        return False
    if masked[i] == ".":
        return True
    return masked[i] == ">" and i > 0 and masked[i - 1] == "-"


def _body_after_init_list(masked: str, colon: int) -> int:
    """The `{` that opens a constructor's body, past its member initializer list.

    `Foo::Foo(int a) : a_{a}, b_(0) { ... }` has three braces and only the last
    one opens the body. An initializer's brace is preceded by the member's name;
    the body's is preceded by a `)` or a `}`.
    """
    i, n = colon + 1, len(masked)
    while i < n:
        ch = masked[i]
        if ch == "(":
            closing = common.match_paren(masked, i)
            if closing < 0:
                return -1
            i = closing + 1
            continue
        if ch == "{":
            back = i - 1
            while back >= 0 and masked[back] in " \t\n\r":
                back -= 1
            if back >= 0 and (masked[back].isalnum() or masked[back] == "_" or masked[back] == ">"):
                closing = common.match_brace(masked, i)
                if closing < 0:
                    return -1
                i = closing + 1
                continue
            return i
        if ch == ";":
            return -1
        i += 1
    return -1


def _selector_of(text: str) -> str:
    """Build `doThing:and:` from a method's parameter list, ignoring its types."""
    parts: List[str] = []
    depth = 0
    for match in re.finditer(r"[()\[\]]|(" + IDENT + r")\s*:", text):
        token = match.group(0)
        if token in "([":
            depth += 1
            continue
        if token in ")]":
            depth -= 1
            continue
        if depth == 0 and match.group(1):
            parts.append(match.group(1) + ":")
    if parts:
        return "".join(parts)
    bare = re.match(r"\s*(" + IDENT + r")\s*$", text)
    return bare.group(1) if bare else ""


# --- the repository --------------------------------------------------------

MESSAGE_RE = re.compile(r"\[")

OBJC_ENTRY_SELECTORS = {
    "application:didFinishLaunchingWithOptions:": "app-launch",
    "applicationDidFinishLaunching:": "app-launch",
    "application:didReceiveRemoteNotification:": "event",
    "viewDidLoad": "lifecycle",
    "viewWillAppear:": "lifecycle",
    "main": "cli-command",
}


class Repository:
    def __init__(self, root: str, detail: str) -> None:
        self.root = root
        self.detail = detail
        self.files: Dict[str, SourceFile] = {}
        self.census: List[Dict[str, Any]] = []
        self.skipped: List[Dict[str, Any]] = []
        self.functions: List[Dict[str, Any]] = []
        self.resolution = common.Resolution()
        self.types: Dict[str, Dict[str, Any]] = {}
        self.by_name: Dict[str, List[Dict[str, Any]]] = {}
        self.methods: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
        self.fields: Dict[str, Dict[str, str]] = {}
        self.headers: Dict[str, List[str]] = {}
        self.visible: Dict[str, Set[str]] = {}

    def index(self) -> None:
        common.assign_ids(self.functions)
        for rel, source in self.files.items():
            for record in source.types:
                self.types.setdefault(
                    record["name"],
                    {"file": rel, "supers": record["supers"], "keyword": record["keyword"]},
                )
            if source.is_header:
                self.headers.setdefault(rel.rsplit("/", 1)[-1].lower(), []).append(rel)
            self._collect_fields(source)
        for fn in self.functions:
            self.by_name.setdefault(fn["name"], []).append(fn)
            if fn["owner"]:
                self.methods.setdefault((fn["owner"], fn["name"]), []).append(fn)
        for rel in self.files:
            self.visible[rel] = self._names_visible_from(rel)

    def _names_visible_from(self, rel: str, seen: Optional[Set[str]] = None) -> Set[str]:
        """Every name the headers this file includes declare, transitively.

        This is the resolution that makes a C call graph possible. A call to a
        bare name is ordinarily a guess; a call to a name declared in a header
        this very file includes is evidence, because that is precisely what an
        include is for.
        """
        seen = seen or set()
        if rel in seen or len(seen) > 200:
            return set()
        seen.add(rel)
        source = self.files.get(rel)
        if source is None:
            return set()
        names = set(source.prototypes) | {f["name"] for f in source.functions}
        for include in source.includes:
            basename = include.rsplit("/", 1)[-1].lower()
            for header in self.headers.get(basename, []):
                names |= self._names_visible_from(header, seen)
        return names

    def _collect_fields(self, source: SourceFile) -> None:
        bodies = [(f["bodyStart"], f["bodyEnd"]) for f in source.functions]
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
                if match.group("type") not in KEYWORDS or match.group("type") in _TYPE_KEYWORDS:
                    fields.setdefault(match.group("var"), match.group("type"))

    # -- resolution ---------------------------------------------------------

    def resolve_all(self) -> None:
        for fn in self.functions:
            source = self.files[fn["file"]]
            body = source.masked[fn["bodyStart"] : fn["bodyEnd"] + 1]
            variables = self._variable_types(fn, body)
            seen: Set[Tuple[str, int]] = set()
            calls: List[Dict[str, Any]] = []

            for offset, receiver, selector in _message_sends(body):
                line = source.index.line_of(fn["bodyStart"] + offset)
                target = self._resolve_message(fn, variables, receiver, selector, line)
                if target and (target[0], line) not in seen:
                    seen.add((target[0], line))
                    calls.append({"to": target[0], "name": selector, "line": line,
                                  "confidence": target[1]})

            for match in CALL_RE.finditer(body):
                name = match.group("name")
                if name in KEYWORDS:
                    continue
                line = source.index.line_of(fn["bodyStart"] + match.start("name"))
                target = self._resolve_call(
                    fn, source, variables, match.group("path"), name, line,
                    _preceded_by_new(body, match.start()),
                    not match.group("path") and _follows_member_access(body, match.start()),
                )
                if target is None:
                    continue
                if (target[0], line) in seen:
                    continue
                seen.add((target[0], line))
                calls.append({"to": target[0], "name": name, "line": line, "confidence": target[1]})

            fn["calls"] = sorted(calls, key=lambda c: (c["line"], c["to"]))

    def _variable_types(self, fn: Dict[str, Any], body: str) -> Dict[str, str]:
        variables = dict(self.fields.get(fn["owner"] or "", {}))
        for match in LOCAL_RE.finditer(fn["params"]):
            variables[match.group("var")] = match.group("type")
        for match in LOCAL_RE.finditer(body):
            variables[match.group("var")] = match.group("type")
        for match in AUTO_NEW_RE.finditer(body):
            variables[match.group("var")] = match.group("type")
        return variables

    def _resolve_call(
        self, fn: Dict[str, Any], source: SourceFile, variables: Dict[str, str],
        path: str, name: str, line: int, constructed: bool, chained: bool,
    ) -> Optional[Tuple[str, str]]:
        if constructed:
            candidates = self.methods.get((name, name), [])
            if len(candidates) == 1:
                return (candidates[0]["id"], "exact")
            if name not in self.types:
                self.resolution.external_call("new " + name, name, fn["id"])
            return None

        segments = [m.group(1) for m in re.finditer(r"(" + IDENT + r")\s*(?:::|->|\.)", path)]
        if not segments and not chained:
            return self._resolve_unqualified(fn, source, name, line)

        receiver = segments[-1] if segments else None
        owner: Optional[str] = None
        if receiver in ("this", "self"):
            owner = fn["owner"]
        elif receiver in self.types:
            owner = receiver
        elif receiver and receiver in variables:
            owner = variables[receiver]

        if owner:
            found = self._lookup(owner, name)
            if found:
                return (found, "exact")
            candidates = self.methods.get((owner, name), [])
            if len(candidates) > 1:
                self.resolution.ambiguous_call(fn["id"], name, line, [c["id"] for c in candidates])
                return None

        if name in COMMON_METHODS:
            return None
        if receiver and receiver not in self.types and receiver not in variables and "::" in path:
            # A namespace-qualified call into something this repository does not
            # define: `std::sort`, `boost::asio::connect`.
            self.resolution.external_call(receiver + "::" + name, receiver, fn["id"])
            return None
        return self._by_unique_name(fn, name, line)

    def _resolve_unqualified(
        self, fn: Dict[str, Any], source: SourceFile, name: str, line: int
    ) -> Optional[Tuple[str, str]]:
        local = [f for f in self.by_name.get(name, []) if f["file"] == source.rel]
        if len(local) == 1:
            return (local[0]["id"], "exact")
        found = self._lookup(fn["owner"] or "", name)
        if found:
            return (found, "exact")
        if name in self.visible.get(source.rel, set()):
            candidates = self.by_name.get(name, [])
            if len(candidates) == 1:
                # Declared in a header this file includes, and defined once.
                return (candidates[0]["id"], "exact")
            if len(candidates) > 1:
                self.resolution.ambiguous_call(
                    fn["id"], name, line, [c["id"] for c in candidates]
                )
                return None
        return self._by_unique_name(fn, name, line)

    def _resolve_message(
        self, fn: Dict[str, Any], variables: Dict[str, str],
        receiver: str, selector: str, line: int,
    ) -> Optional[Tuple[str, str]]:
        owner: Optional[str] = None
        if receiver in ("self", "super"):
            owner = fn["owner"]
            if receiver == "super":
                for parent in self.types.get(fn["owner"] or "", {}).get("supers", []):
                    found = self._lookup(parent, selector)
                    if found:
                        return (found, "exact")
        elif receiver in self.types:
            owner = receiver
        elif receiver in variables:
            owner = variables[receiver]

        if owner:
            found = self._lookup(owner, selector)
            if found:
                return (found, "exact")
        return self._by_unique_name(fn, selector, line)

    def _lookup(self, type_name: str, name: str, seen: Optional[Set[str]] = None) -> Optional[str]:
        seen = seen or set()
        if not type_name or type_name in seen:
            return None
        seen.add(type_name)
        candidates = self.methods.get((type_name, name), [])
        if len(candidates) == 1:
            return candidates[0]["id"]
        if len(candidates) > 1:
            return None
        for parent in self.types.get(type_name, {}).get("supers", []):
            found = self._lookup(parent, name, seen)
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


def _message_sends(body: str) -> List[Tuple[int, str, str]]:
    """Every `[receiver selector:...]` in a body, as (offset, receiver, selector).

    Objective-C's one call syntax that nothing else shares, and the reason a
    tracer that only knew C would find no calls at all in an iOS codebase.
    """
    sends: List[Tuple[int, str, str]] = []
    for match in MESSAGE_RE.finditer(body):
        closing = common.match_delim(body, match.start(), "[", "]")
        if closing < 0:
            continue
        inner = body[match.start() + 1 : closing]
        head = re.match(r"\s*(" + IDENT + r")\s+(.*)$", inner, re.S)
        if not head:
            continue
        selector = _selector_of(head.group(2))
        if selector:
            sends.append((match.start(), head.group(1), selector))
    return sends


def _follows_member_access(body: str, start: int) -> bool:
    i = start - 1
    while i >= 0 and body[i] in " \t\n\r":
        i -= 1
    if i < 0:
        return False
    if body[i] in ".)":
        return True
    return body[i] == ">" and i > 0 and body[i - 1] == "-"


def _preceded_by_new(body: str, start: int) -> bool:
    return bool(re.search(r"\bnew\s+$", body[max(0, start - 8) : start]))


# --- entry points ----------------------------------------------------------


def attribute_entry(attribute: str) -> Optional[Tuple[str, str]]:
    for pattern, kind in ENTRY_ATTRIBUTE_RULES:
        if re.match(pattern, attribute):
            return kind, _attribute_detail(attribute, kind)
    return None


def _attribute_detail(attribute: str, kind: str) -> str:
    if kind != "http-route":
        return attribute
    verb = re.match(r"Http(Get|Post|Put|Patch|Delete|Head|Options)", attribute)
    path = re.search(r"\"([^\"]*)\"", attribute)
    label = verb.group(1).upper() if verb else "ROUTE"
    return (label + " " + path.group(1)).strip() if path else label


def collect_entry_points(repo: Repository) -> List[Dict[str, Any]]:
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
        for attribute in fn["decorators"]:
            found = attribute_entry(attribute)
            if found:
                add(fn, found[0], found[1])
                matched = True
                break
        if matched:
            continue
        if fn["selector"] and fn["selector"] in OBJC_ENTRY_SELECTORS:
            add(fn, OBJC_ENTRY_SELECTORS[fn["selector"]], fn["selector"])
        elif fn["name"] == "main" and not fn["owner"]:
            add(fn, "cli-command", fn["file"])
        elif fn["name"] == "Main" and fn["static"]:
            add(fn, "cli-command", fn["file"])

    return sorted(entries.values(), key=lambda e: (e["file"], e["line"]))


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
            "dialect": source.language,
        }
        snippet = common.snippet_for(source.lines, fn["line"], fn["endLine"], loc, repo.detail)
        if snippet is not None:
            record["snippet"] = snippet
        records.append(record)
    return records


LIMITS = common.BASE_LIMITS + (
    "The preprocessor is not run: a function inside `#if` is catalogued whether or not "
    "that branch compiles, a call that exists only inside a macro body is not found, and "
    "a `#define`d name is neither expanded nor resolved.",
    "A call through a function pointer, a virtual method on a base-class reference, or an "
    "Objective-C `performSelector:` reaches an implementation chosen at runtime, which is "
    "not a static fact about the text.",
    "Overloads and template instantiations are distinguished by line, not by parameter "
    "types, so a call that could mean either is listed as ambiguous rather than assigned "
    "to one of them.",
    "A bare call resolves through the headers a file includes; a name reached some other "
    "way -- a forward declaration, a compiler builtin, a linker-provided symbol -- resolves "
    "by unique name at best.",
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
        language = language_for(rel, text)
        if language is None:
            # A `.m` that is not Objective-C. Reading it with a C parser would
            # produce confident nonsense, so it is reported as unread instead.
            repo.skipped.append({"path": rel, "reason": "unparsed"})
            continue
        source = SourceFile(rel, text, language)
        repo.files[rel] = source
        try:
            size = os.path.getsize(path)
        except OSError:
            size = 0
        repo.census.append({"path": rel, "size": size, "hash": common.file_hash(path)})

        in_test_file = common.is_test_path(rel)
        for fn in source.functions:
            fn["role"] = "test" if (in_test_file or fn["isTest"]) else "source"
            repo.functions.append(fn)

    declared = set()
    purposes: Dict[str, str] = {}
    for source in repo.files.values():
        declared |= source.interface_selectors
        for name, purpose in source.declared_purposes.items():
            purposes.setdefault(name, purpose)
    for fn in repo.functions:
        if not fn["purpose"]:
            fn["purpose"] = purposes.get(fn["name"], "")
    for fn in repo.functions:
        if fn["selector"]:
            # A method is public when some `@interface` in the repository
            # declares it -- which is normally a different file from the
            # `@implementation` that defines it.
            fn["exported"] = fn["selector"] in declared

    repo.index()
    repo.resolve_all()
    return common.build_envelope(
        tracer=TRACER_NAME,
        language="c-family",
        root_abs=root_abs.replace(os.sep, "/"),
        detail=detail,
        files=repo.census,
        skipped=repo.skipped,
        functions=build_functions(repo),
        entry_points=collect_entry_points(repo),
        resolution=repo.resolution,
        limits=LIMITS,
        extra={"dialects": sorted({s.language for s in repo.files.values()})},
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    return common.run_cli(
        "trace_c_family.py",
        "Static call-graph tracer for C, C++, Objective-C and C# repositories (code-flow).",
        trace,
        argv,
    )


if __name__ == "__main__":
    raise SystemExit(main())
