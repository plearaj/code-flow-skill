"""What every tracer written in Python needs, and none of them should restate.

`trace_python.py` came first and had all of this inline. Adding Rust, Java and
the C family would have meant four copies of the id rule, four copies of the
skip-reason table and four copies of the envelope — in a project whose other
half is a tool for finding exactly that. So the parts that are about *a
repository* rather than about *a language* live here, and each tracer is left
holding only the thing that makes it a tracer for its language.

The split is: this module knows how to find files, name a function, hash a
census, mask a brace language's comments and strings, and assemble the output
document. It knows nothing about what a function looks like. Each tracer knows
that and nothing else.

Not a public interface. It ships beside the tracers in `.code-flow/tracers/`
and is imported by them; the directory is the unit, not the file. Python puts a
script's own directory on `sys.path`, which is what makes `import _common` work
from whatever directory the tracer was invoked from.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

TRACER_SCHEMA = 1
ID_RULE = "code-flow/v1"

DETAIL_LEVELS = ("thin", "standard", "verbose")


# --- ids -------------------------------------------------------------------


def derive_id(file: str, name: str) -> str:
    """Return the map's `id` for a function named ``name`` defined in ``file``.

    The rule, verbatim from the map templates: drop the extension from the
    path's last segment only, append `_` and the unqualified name, lowercase,
    replace every character outside `[a-z0-9_]`, collapse runs, trim.

    Every tracer calls this rather than implementing it, because a tracer whose
    ids differ from the map's by one character is worse than no tracer at all:
    `/code-flow-quality` subtracts reached ids from catalogued ids, so a
    mismatch reports the entire repository as unreachable, confidently.
    """
    head, _, last = file.rpartition("/")
    stem = last.rpartition(".")[0] or last
    combined = "{}/{}_{}".format(head, stem, name) if head else "{}_{}".format(stem, name)
    slug = re.sub(r"[^a-z0-9_]+", "_", combined.lower())
    return re.sub(r"_+", "_", slug).strip("_")


def assign_ids(functions: List[Dict[str, Any]]) -> None:
    """Set `id` on every record in ``functions``, in place.

    A name defined more than once in one file — an overload set in C++, two
    classes with a `get` in Python, a trait impl and an inherent impl in Rust —
    gets `_l<line>` appended to every one of its ids, including the first. The
    collision is decided from the file's own contents, so moving an unrelated
    file never renames anything, and the suffix comes from the definition line,
    so two same-named functions cannot swap identities when one of them moves.
    """
    counts: Dict[Tuple[str, str], int] = {}
    for fn in functions:
        key = (fn["file"], fn["name"])
        counts[key] = counts.get(key, 0) + 1
    for fn in functions:
        base = derive_id(fn["file"], fn["name"])
        if counts[(fn["file"], fn["name"])] > 1:
            fn["id"] = "{}_l{}".format(base, fn["line"])
        else:
            fn["id"] = base


# --- discovery -------------------------------------------------------------

# Directories never worth walking into. `.gitignore` covers most of these in
# most repositories; this list is what makes a tracer behave the same in a
# checkout that has no `.gitignore` at all.
PRUNE_DIRS = frozenset(
    {
        ".git", ".hg", ".svn", ".idea", ".vscode", "__pycache__", ".mypy_cache",
        ".pytest_cache", ".ruff_cache", ".tox", ".nox", ".eggs", "node_modules",
        ".venv", "venv", "env", ".env", "site-packages", "dist", "build",
        "target", "vendor", "third_party", "coverage", "htmlcov", ".next",
        ".nuxt", ".svelte-kit", ".terraform", ".gradle", ".mvn", "bin", "obj",
        "cmake-build-debug", "cmake-build-release", "DerivedData", "Pods",
    }
)

# One reason per skipped file, in the priority the map templates fix: a file
# that is both vendored and generated is reported as vendored, so two runs over
# the same repository produce the same counts.
#
# Matched against whole path *segments*, never as substrings. A substring test
# skipped `distutils/` and `xml/dom/xmlbuilder.py` from the Python standard
# library — "dist" and "build" occur inside ordinary words — and a file skipped
# for a reason that is not true is worse than a file not skipped: it is absent
# from the map with an explanation that looks right.
VENDORED_DIRS = frozenset(
    {"node_modules", "vendor", "third_party", "site-packages", "bower_components",
     ".venv", "venv", "env", ".env", "Pods", "external", "extern", "deps",
     "submodules", "packages"}
)
GENERATED_DIRS = frozenset(
    {"dist", "build", "target", "out", "coverage", "htmlcov", "__pycache__",
     ".next", ".nuxt", ".svelte-kit", ".mypy_cache", ".pytest_cache", ".ruff_cache",
     ".tox", ".nox", ".eggs", ".terraform", ".gradle", "obj", "cmake-build-debug",
     "cmake-build-release", "DerivedData", "generated", "gen"}
)
# These are filename markers, so they *are* substring tests — of the last path
# segment only, where "_pb2" and ".min." mean what they say.
GENERATED_FILE_MARKERS = (
    ".min.", "_pb2", ".generated.", "-generated.", ".g.", ".pb.", ".designer.",
    "_generated.", ".freezed.",
)

TEST_DIR_NAMES = frozenset(
    {"tests", "test", "spec", "specs", "__tests__", "testing", "testsuite",
     "unittest", "unittests", "androidTest"}
)


# Compared against a lowercased path, so lowercased once here rather than on
# every file: this runs a few times per file across tens of thousands of them.
_VENDORED_LOWER = frozenset(d.lower() for d in VENDORED_DIRS)
_GENERATED_LOWER = frozenset(d.lower() for d in GENERATED_DIRS)
_PRUNE_LOWER = frozenset(d.lower() for d in PRUNE_DIRS)


def git_tracked_files(root: str) -> Optional[List[str]]:
    """Return the repository's tracked and untracked-but-not-ignored files.

    Preferred over walking the tree because it applies the project's real
    ignore rules — every `.gitignore`, the global one, and `.git/info/exclude` —
    rather than this file's approximation of them.

    Returns None when this listing cannot stand in for the walk: the directory
    is not a git checkout, git is not installed, or git ran and listed nothing.
    That last case is not "an empty repository" — it is most often a directory
    the repository ignores, and keeping the empty list there catalogues nothing,
    reports no error, and produces a map that says the code is not present. A
    genuinely empty directory walks to nothing anyway, so falling back costs
    that case nothing and saves this one.
    """
    try:
        out = subprocess.run(
            ["git", "-C", root, "ls-files", "--cached", "--others", "--exclude-standard"],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    listed = [line for line in out.stdout.splitlines() if line]
    return listed or None


def walk_files(root: str) -> List[str]:
    """Return every file under ``root``, pruning the directories above."""
    found: List[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in PRUNE_DIRS and not d.startswith(".egg"))
        for name in sorted(filenames):
            rel = os.path.relpath(os.path.join(dirpath, name), root)
            found.append(rel.replace(os.sep, "/"))
    return found


def skip_reason(rel: str, suffixes: Sequence[str]) -> Optional[str]:
    """Return why ``rel`` is not analyzable, or None if it is a source file.

    The four reasons are the map's own: `vendored`, `generated`, `binary`,
    `unparsed`. `unparsed` is not decided here — it is what a parse failure in
    the caller means. A file this tracer's language does not claim returns
    None, which is "not mine", not "skipped": counting another language's
    files as skipped would make every polyglot repository look half-read.
    """
    lowered = rel.lower()
    parts = lowered.split("/")
    directories, name = parts[:-1], parts[-1]
    if any(part in _VENDORED_LOWER for part in directories):
        return "vendored"
    if any(part in _GENERATED_LOWER for part in directories):
        return "generated"
    if any(part in _PRUNE_LOWER for part in directories):
        return "generated"
    if not lowered.endswith(tuple(s.lower() for s in suffixes)):
        return None
    if any(marker in name for marker in GENERATED_FILE_MARKERS):
        return "generated"
    return None


def is_test_path(rel: str) -> bool:
    """Whether ``rel`` is test code, by directory or by filename convention.

    Tests are catalogued, never skipped: excluding them would make every helper
    only tests use look unreachable, which is a dead-code finding invented by
    the tracer rather than found in the repository.
    """
    parts = rel.split("/")
    stem = parts[-1].rsplit(".", 1)[0]
    if any(part in TEST_DIR_NAMES for part in parts[:-1]):
        return True
    lowered = stem.lower()
    if lowered.startswith("test_") or lowered.startswith("test-"):
        return True
    if lowered.endswith(("_test", "_tests", "-test", "_spec", "-spec", ".test", ".spec")):
        return True
    # Java, C# and C++ name a test class `FooTest`, `FooTests` or `FooSpec`.
    # Matched on the original casing rather than lowercased, so that `latest.rs`
    # — which ends in "test" — stays a source file.
    return stem.endswith(("Test", "Tests", "Spec", "Specs", "TestCase"))


def file_hash(path: str) -> Optional[str]:
    try:
        with open(path, "rb") as handle:
            digest = hashlib.sha256(handle.read()).hexdigest()
    except OSError:
        return None
    return "sha256:" + digest[:6]


def read_source(path: str) -> Optional[str]:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return None


# --- the brace-language lexer ----------------------------------------------
#
# Rust, Java, C, C++, C# and Objective-C all delimit a function body with
# braces, so finding a function means finding a `{` and its partner. That is
# only true of the *code*: a `{` inside a string literal or a comment is not a
# brace, and one comment with an unbalanced quote in it can otherwise shift
# every function boundary in a file by hundreds of lines.
#
# So rather than parse — which would mean a compiler per language, and none of
# them may be installed — each tracer works over a masked copy: comments and the
# insides of literals replaced by spaces, character for character, newlines
# left where they are. Indices and line numbers stay valid, so a match found in
# the masked text reads its own text back out of the original.


class Flavor:
    """How one language spells its comments and literals."""

    def __init__(
        self,
        line_comment: str = "//",
        block: Tuple[str, str] = ("/*", "*/"),
        nested_block: bool = False,
        char_literal: Optional[str] = "c",
        raw_rust: bool = False,
        raw_cpp: bool = False,
        verbatim_cs: bool = False,
        text_block: bool = False,
        preprocessor: bool = False,
        digit_separator: bool = False,
    ) -> None:
        self.line_comment = line_comment
        self.block = block
        self.nested_block = nested_block
        self.char_literal = char_literal
        self.raw_rust = raw_rust
        self.raw_cpp = raw_cpp
        self.verbatim_cs = verbatim_cs
        self.text_block = text_block
        self.preprocessor = preprocessor
        self.digit_separator = digit_separator


# `nested_block` is not a nicety: Rust's block comments nest, so a file that
# comments out a region containing another comment ends its comment in the
# wrong place under a non-nesting lexer, and everything after it is read as
# comment text.
RUST = Flavor(nested_block=True, char_literal="rust", raw_rust=True)
JAVA = Flavor(text_block=True)
C = Flavor(preprocessor=True, digit_separator=True)
CPP = Flavor(preprocessor=True, raw_cpp=True, digit_separator=True)
CSHARP = Flavor(verbatim_cs=True, preprocessor=True, digit_separator=True)
OBJC = Flavor(preprocessor=True, digit_separator=True)


def _line_start(text: str, i: int) -> bool:
    j = i - 1
    while j >= 0 and text[j] in " \t":
        j -= 1
    return j < 0 or text[j] == "\n"


def _logical_line_end(text: str, i: int) -> int:
    """End of the preprocessor line starting at ``i``, following continuations."""
    n = len(text)
    while i < n:
        if text[i] == "\\":
            j = i + 1
            while j < n and text[j] in " \t\r":
                j += 1
            if j < n and text[j] == "\n":
                i = j + 1
                continue
        if text[i] == "\n":
            return i
        i += 1
    return n


def mask_source(text: str, flavor: Flavor) -> str:
    """Return ``text`` with comment and literal *contents* replaced by spaces.

    Same length, same line breaks, same offsets. Literal delimiters survive, so
    a caller can still see that something was a string; what it said is gone,
    which is the point.
    """
    n = len(text)
    out = list(text)

    def blank(a: int, b: int) -> None:
        for k in range(a, min(b, n)):
            if out[k] != "\n":
                out[k] = " "

    i = 0
    while i < n:
        ch = text[i]

        if flavor.preprocessor and ch == "#" and _line_start(text, i):
            end = _logical_line_end(text, i)
            blank(i, end)
            i = end
            continue

        if flavor.line_comment and text.startswith(flavor.line_comment, i):
            end = text.find("\n", i)
            end = n if end < 0 else end
            blank(i, end)
            i = end
            continue

        if text.startswith(flavor.block[0], i):
            depth, j = 1, i + len(flavor.block[0])
            while j < n and depth:
                if flavor.nested_block and text.startswith(flavor.block[0], j):
                    depth += 1
                    j += len(flavor.block[0])
                    continue
                if text.startswith(flavor.block[1], j):
                    depth -= 1
                    j += len(flavor.block[1])
                    continue
                j += 1
            blank(i, j)
            i = j
            continue

        if flavor.raw_rust and ch in "rb" and _rust_raw_start(text, i):
            i = _mask_rust_raw(text, i, blank)
            continue

        if flavor.raw_cpp and ch in "Ru" and _cpp_raw_start(text, i):
            i = _mask_cpp_raw(text, i, blank, n)
            continue

        if flavor.verbatim_cs and (ch == "@" or ch == "$") and _cs_verbatim_start(text, i):
            i = _mask_cs_verbatim(text, i, blank, n)
            continue

        if flavor.text_block and text.startswith('"""', i):
            end = text.find('"""', i + 3)
            end = n if end < 0 else end + 3
            blank(i + 3, end - 3)
            i = end
            continue

        if ch == '"':
            j = i + 1
            while j < n and text[j] != '"':
                if text[j] == "\\":
                    j += 1
                elif text[j] == "\n":
                    break  # an unterminated string ends at the line, not the file
                j += 1
            blank(i + 1, j)
            i = min(j + 1, n)
            continue

        if ch == "'" and flavor.char_literal:
            i = _mask_char(text, i, flavor, blank, n)
            continue

        i += 1

    return "".join(out)


def _rust_raw_start(text: str, i: int) -> bool:
    j = i
    if text[j] == "b":
        j += 1
    if j >= len(text) or text[j] != "r":
        return False
    j += 1
    while j < len(text) and text[j] == "#":
        j += 1
    return j < len(text) and text[j] == '"'


def _mask_rust_raw(text: str, i: int, blank: Callable[[int, int], None]) -> int:
    j = i
    if text[j] == "b":
        j += 1
    j += 1  # the r
    hashes = 0
    while text[j] == "#":
        hashes += 1
        j += 1
    j += 1  # the opening quote
    close = '"' + "#" * hashes
    end = text.find(close, j)
    end = len(text) if end < 0 else end
    blank(j, end)
    return min(end + len(close), len(text))


def _cpp_raw_start(text: str, i: int) -> bool:
    # R"delim(...)delim", and the u8/u/U/L-prefixed spellings of it.
    m = re.compile(r'(?:u8|u|U|L)?R"').match(text, i)
    return bool(m)


def _mask_cpp_raw(text: str, i: int, blank: Callable[[int, int], None], n: int) -> int:
    quote = text.index('"', i)
    close_paren = text.find("(", quote)
    if close_paren < 0:
        return i + 1
    delim = text[quote + 1 : close_paren]
    close = ")" + delim + '"'
    end = text.find(close, close_paren)
    if end < 0:
        blank(quote + 1, n)
        return n
    blank(quote + 1, end)
    return min(end + len(close), n)


def _cs_verbatim_start(text: str, i: int) -> bool:
    return bool(re.compile(r'(?:@\$?|\$@)"').match(text, i))


def _mask_cs_verbatim(text: str, i: int, blank: Callable[[int, int], None], n: int) -> int:
    quote = text.index('"', i)
    j = quote + 1
    while j < n:
        if text[j] == '"':
            if j + 1 < n and text[j + 1] == '"':
                j += 2  # "" is an escaped quote inside a verbatim string
                continue
            break
        j += 1
    blank(quote + 1, j)
    return min(j + 1, n)


def _mask_char(text: str, i: int, flavor: Flavor, blank: Callable[[int, int], None], n: int) -> int:
    """Mask a character literal, or step over something that only looks like one.

    Two things spell `'` without opening a literal, and both would otherwise
    swallow the rest of the file: a Rust lifetime (`'a`, `'static`) and a C++
    digit separator (`1'000'000`).
    """
    if flavor.char_literal == "rust":
        if text.startswith("\\", i + 1):
            j = i + 2
            while j < n and text[j] != "'":
                if text[j] == "\\":
                    j += 1
                j += 1
            blank(i + 1, j)
            return min(j + 1, n)
        if i + 2 < n and text[i + 2] == "'":
            blank(i + 1, i + 2)
            return i + 3
        return i + 1  # a lifetime

    if flavor.digit_separator and i > 0 and text[i - 1].isalnum() and i + 1 < n and text[i + 1].isalnum():
        return i + 1

    j = i + 1
    while j < n and text[j] != "'":
        if text[j] == "\\":
            j += 1
        elif text[j] == "\n":
            break
        j += 1
    blank(i + 1, j)
    return min(j + 1, n)


# --- reading the masked text -----------------------------------------------


def match_delim(masked: str, i: int, opener: str, closer: str) -> int:
    """Index of the delimiter closing the one at ``i``, or -1 if unbalanced.

    Only ever run over masked text; over raw source a brace inside a string
    would close a block early and every function after it would be wrong.
    """
    if i < 0 or i >= len(masked) or masked[i] != opener:
        return -1
    depth = 0
    for j in range(i, len(masked)):
        ch = masked[j]
        if ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return j
    return -1


def match_brace(masked: str, i: int) -> int:
    return match_delim(masked, i, "{", "}")


def match_paren(masked: str, i: int) -> int:
    return match_delim(masked, i, "(", ")")


def match_angle(masked: str, i: int) -> int:
    """Match a generic-argument bracket. Unreliable by nature, and known to be.

    `<` is also less-than, so this gives up rather than guessing when the span
    runs long or crosses a statement boundary — a wrong answer here would drag
    a function's signature across half a file.
    """
    if i >= len(masked) or masked[i] != "<":
        return -1
    depth = 0
    for j in range(i, min(len(masked), i + 400)):
        ch = masked[j]
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth -= 1
            if depth == 0:
                return j
        elif ch in ";{}":
            return -1
    return -1


class LineIndex:
    """Line numbers for offsets, computed once per file rather than per match."""

    def __init__(self, text: str) -> None:
        self.starts = [0]
        for i, ch in enumerate(text):
            if ch == "\n":
                self.starts.append(i + 1)

    def line_of(self, index: int) -> int:
        lo, hi = 0, len(self.starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self.starts[mid] <= index:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1

    def start_of(self, line: int) -> int:
        return self.starts[max(0, min(line - 1, len(self.starts) - 1))]


DOC_LINE_PREFIXES = ("///", "//!", "//", "*")


def doc_comment_before(text: str, index: int) -> str:
    """Return the doc comment immediately above ``index``, as one line of prose.

    Two shapes, both anchored *backwards* from the declaration: a `/** ... */`
    or `/*! ... */` block ending just above it, and a run of `///` or `//` lines.
    Anchoring backwards is the whole trick — a forward search from the start of
    the window finds the *previous* function's comment, and every function in
    the file then inherits its neighbour's description.
    """
    head = text[:index].rstrip()
    if head.endswith("*/"):
        open_at = head.rfind("/*")
        if open_at >= 0:
            body = head[open_at + 2 : -2]
            lines = []
            for raw in body.splitlines():
                line = raw.strip().lstrip("*!").strip()
                if line.startswith("@") or line.startswith("\\"):
                    break  # a javadoc tag block; the prose is done
                if line:
                    lines.append(line)
            return _first_sentence(" ".join(lines))

    lines: List[str] = []
    for raw in reversed(head.splitlines()):
        line = raw.strip()
        if not line:
            break
        if line.startswith("///") or line.startswith("//!"):
            lines.insert(0, line[3:].strip())
        elif line.startswith("//"):
            lines.insert(0, line[2:].strip())
        else:
            break
    return _first_sentence(" ".join(part for part in lines if part))


_DOC_TAG_RE = re.compile(r"</?(?:summary|remarks|returns|value|para|c|code|see|param)[^>]*>")


def _first_sentence(text: str) -> str:
    # C# writes doc comments as XML, so the prose arrives wrapped in tags. Only
    # the documentation tags are stripped -- a `Vec<T>` in a Rust doc comment is
    # not markup, and removing it would change what the sentence says.
    text = _DOC_TAG_RE.sub(" ", text)
    text = " ".join(text.split())
    if not text:
        return ""
    cut = text.find(". ")
    if cut > 0:
        text = text[: cut + 1]
    return text[:240]


def snippet_for(lines: List[str], start_line: int, end_line: int, loc: int, detail: str) -> Optional[str]:
    """The body a function carries as evidence, governed by `--detail`.

    `</` is escaped because the map inlines this into a `<script>` block, where
    the sequence would end the script element early and take the rest of the
    document with it.
    """
    if detail == "thin":
        return None
    body = "\n".join(lines[start_line - 1 : end_line])
    if detail == "standard":
        if loc <= 3:
            return None
        body = "\n".join(body.splitlines()[:20])
    return body.replace("</", "<\\/")


# --- inheritance -----------------------------------------------------------


def overridden_names(
    types: Dict[str, Dict[str, Any]],
    methods: Dict[Tuple[str, str], List[Dict[str, Any]]],
    owner: Optional[str],
    name: str,
    separator: str = ".",
) -> List[str]:
    """The supertype declarations `owner.name` overrides, nearest first.

    Shared by the two tracers whose languages spell inheritance the same way --
    a type naming its supertypes, walked upward until the names run out. Two
    rules keep it from inventing anything. It searches supertypes only, never
    `owner` itself, because a method does not override its own type's other
    overload -- an overload set inside one type is exactly what a
    name-and-arity guess mistakes for a family. And it names a supertype only
    where that supertype really declares this member: `AdminUserStore extends
    UserStore` does not make `findAdmin` an override of anything.

    The result is a *name*, `Supertype.member`, not an id, because the id would
    often not exist. A Java interface method and a C++ pure virtual are
    declarations with no body, and a tracer that catalogues bodies has no entry
    to point at -- Java's abstract declarations are catalogued and C++'s are
    not, so an id-only field would report the same relationship in one language
    and stay silent in the other. The name is what makes two implementations of
    one declaration recognizable as siblings, which is what a consumer asks for;
    where the declaration is itself catalogued, `owner` and `name` locate it.

    A supertype outside this repository -- `Object`, a class from a jar -- is
    not in `types`, so nothing above it is named. That is the refusal `calls`
    makes, for the reason `calls` makes it: what the tracer cannot see, it does
    not report.
    """
    if not owner:
        return []
    found: List[str] = []
    seen: Set[str] = {owner}
    frontier: List[str] = list(types.get(owner, {}).get("supers", []))
    while frontier:
        parent = frontier.pop(0)
        if not parent or parent in seen:
            continue
        seen.add(parent)
        if methods.get((parent, name)):
            declaration = parent + separator + name
            if declaration not in found:
                found.append(declaration)
        frontier.extend(types.get(parent, {}).get("supers", []))
    return found


# --- resolution bookkeeping ------------------------------------------------


class Resolution:
    """The three things a tracer can conclude about a call, and their records.

    Kept together because the rule they enforce is one rule: an edge is only
    ever written when the target is known. A call that could mean several
    things becomes an `ambiguousCall` carrying its candidates, and a call that
    leaves the repository becomes an `externalCall` carrying its callers.
    Neither becomes an edge, because a false edge puts a call in a diagram that
    a reader will go looking for and not find.
    """

    def __init__(self) -> None:
        self.ambiguous: List[Dict[str, Any]] = []
        self.external: Dict[str, Dict[str, Any]] = {}

    def ambiguous_call(self, caller: str, name: str, line: int, candidates: Iterable[str]) -> None:
        ordered = sorted(set(candidates))
        self.ambiguous.append(
            {"from": caller, "name": name, "line": line, "candidates": ordered}
        )

    def external_call(self, name: str, module: str, caller: str) -> None:
        record = self.external.setdefault(name, {"name": name, "module": module, "callers": []})
        if caller not in record["callers"]:
            record["callers"].append(caller)

    def sorted_ambiguous(self) -> List[Dict[str, Any]]:
        return sorted(self.ambiguous, key=lambda a: (a["from"], a["line"], a["name"]))

    def sorted_external(self) -> List[Dict[str, Any]]:
        for record in self.external.values():
            record["callers"].sort()
        return [self.external[key] for key in sorted(self.external)]


# --- the output document ---------------------------------------------------


def build_envelope(
    tracer: str,
    language: str,
    root_abs: str,
    detail: str,
    files: List[Dict[str, Any]],
    skipped: List[Dict[str, Any]],
    functions: List[Dict[str, Any]],
    entry_points: List[Dict[str, Any]],
    resolution: Resolution,
    limits: Sequence[str],
    components: Optional[List[Dict[str, Any]]] = None,
    routes: Optional[List[Dict[str, Any]]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Assemble the document every tracer emits, in the one order they all use.

    `components` and `routes` are always present, empty where a language has no
    UI to find. A consumer that had to ask which tracer wrote a file before it
    could read it is not a contract, and every tracer added later would then be
    a change to every consumer.
    """
    components = components or []
    routes = routes or []
    functions = sorted(functions, key=lambda f: (f["file"], f["line"]))

    called = {call["to"] for fn in functions for call in fn["calls"]}
    skip_counts: Dict[str, int] = {}
    for item in skipped:
        skip_counts[item["reason"]] = skip_counts.get(item["reason"], 0) + 1

    document: Dict[str, Any] = {
        "schema": TRACER_SCHEMA,
        "tracer": tracer,
        "language": language,
        "idRule": ID_RULE,
        "root": root_abs,
        "detail": detail,
        "files": files,
        "skipped": skipped,
        "functions": functions,
        "components": components,
        "routes": routes,
        "entryPoints": entry_points,
        "ambiguousCalls": resolution.sorted_ambiguous(),
        "externalCalls": resolution.sorted_external(),
        "stats": {
            "filesScanned": len(files),
            "filesSkipped": len(skipped),
            "skipReason": skip_counts,
            "functionsFound": len(functions),
            "callEdges": sum(len(f["calls"]) for f in functions),
            "ambiguousCalls": len(resolution.ambiguous),
            "externalCalls": len(resolution.external),
            "entryPointsFound": len(entry_points),
            "componentsFound": len(components),
            "unreachedCandidates": sum(1 for f in functions if f["id"] not in called),
        },
        "limits": list(limits),
    }
    if extra:
        document.update(extra)
    return document


# Said by every tracer, because it is true of all of them and a reader who is
# only given the resolutions will present them as the whole graph.
BASE_LIMITS = (
    "Static analysis only: reflection, dynamic dispatch through a string, dependency "
    "injection, registry lookups and configuration-declared entry points are invisible to it.",
    "Calls resolved by unique name carry confidence 'heuristic'; ambiguous ones are "
    "listed in ambiguousCalls rather than guessed into edges.",
    "`overrides` names only a declaration this repository defines: a method that overrides "
    "one from a dependency, a framework base class or the standard library carries nothing.",
)


# --- driver ----------------------------------------------------------------


def run_cli(
    prog: str,
    description: str,
    trace: Callable[[str, str], Dict[str, Any]],
    argv: Optional[Sequence[str]] = None,
) -> int:
    """The command line every tracer presents, so that the map drives them alike.

    `--detail` is handed straight through from `/code-flow-map`'s own flag, and
    means the same thing here as it does there.
    """
    parser = argparse.ArgumentParser(prog=prog, description=description)
    parser.add_argument("--root", default=".", help="Repository root to trace (default: .)")
    parser.add_argument("--out", default=None, help="Write JSON here instead of stdout")
    parser.add_argument(
        "--detail",
        default="standard",
        choices=list(DETAIL_LEVELS),
        help="How much snippet evidence each function carries (default: standard)",
    )
    args = parser.parse_args(argv)

    result = trace(args.root, args.detail)
    text = json.dumps(result, indent=2, sort_keys=False)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
        stats = result["stats"]
        sys.stderr.write(
            "traced {} files, {} functions, {} call edges, {} entry points -> {}\n".format(
                stats["filesScanned"], stats["functionsFound"], stats["callEdges"],
                stats["entryPointsFound"], args.out,
            )
        )
    else:
        sys.stdout.write(text + "\n")
    return 0


def collect_sources(root_abs: str, suffixes: Sequence[str]) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Return (paths this tracer should read, records for the ones it skipped).

    Discovery is the same problem in every language, and getting it subtly
    different per tracer is how two tracers over one repository come to disagree
    about how big it is.
    """
    listing = git_tracked_files(root_abs)
    candidates = listing if listing is not None else walk_files(root_abs)
    lowered = tuple(s.lower() for s in suffixes)

    keep: List[str] = []
    skipped: List[Dict[str, Any]] = []
    for rel in sorted(candidates):
        if not rel.lower().endswith(lowered):
            continue
        reason = skip_reason(rel, suffixes)
        if reason is not None:
            skipped.append({"path": rel, "reason": reason})
            continue
        keep.append(rel)
    return keep, skipped
