"""The lexer three tracers now share, tested where it is cheapest to test.

`_common.mask_source` is the reason the Rust, Java and C-family tracers can find
a function without a compiler: it blanks comments and literal contents in place,
same length and same line breaks, so a `{` inside a string cannot close a block
early. Everything those three tracers conclude rests on it being right.

Each case here is a thing that swallows the rest of a file when it goes wrong —
a nested comment, a lifetime, a raw string, a macro continuation — which is what
makes them worth their own tests rather than only being visible as a missing
function three fixtures away.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from .conftest import REPO_ROOT
from .test_node_ids import derive_id as reference_derive_id

# Set before the import, for the same reason the tracers set it: importing a
# module out of `templates/` writes a `__pycache__/` next to it, and `npm pack`
# packs the working tree rather than the git index. A stale `.pyc` would ship in
# the tarball and fail the publish workflow's wheel-integrity check, without
# `git status` ever mentioning it -- the directory is `.gitignore`d.
sys.dont_write_bytecode = True
sys.path.insert(0, str(REPO_ROOT / "templates" / "shared" / "tracers"))

import _common  # noqa: E402  (the path has to be set first)

FLAVORS = {
    "rust": _common.RUST,
    "java": _common.JAVA,
    "c": _common.C,
    "cpp": _common.CPP,
    "csharp": _common.CSHARP,
    "objc": _common.OBJC,
}


@pytest.mark.parametrize("name", sorted(FLAVORS))
def test_masking_preserves_every_offset(name: str) -> None:
    """The masked copy is read for structure and the original for text, at the
    same indices. A mask that changed a length would misreport every line number
    after it — quietly, since the output would still look like a call graph."""
    source = (
        'a "string with a { brace" b\n'
        "/* comment with a } brace */\n"
        "// line comment\n"
        "c 'x' d\n"
    )
    masked = _common.mask_source(source, FLAVORS[name])
    assert len(masked) == len(source)
    assert masked.count("\n") == source.count("\n")
    for i, ch in enumerate(source):
        if ch == "\n":
            assert masked[i] == "\n", f"line break at {i} was masked away"


def test_a_rust_block_comment_nests() -> None:
    """Rust is the one language here whose block comments nest. Ending the
    comment at the first `*/` leaves the rest of the file inside a comment that
    never closes, and the file appears to define nothing."""
    source = "fn a() {}\n/* outer /* inner */ still comment */\nfn b() {}\n"
    masked = _common.mask_source(source, _common.RUST)
    assert "fn b()" in masked
    assert masked.count("fn ") == 2

    # And the same text read with a non-nesting lexer proves the case is real.
    naive = _common.mask_source(source, _common.JAVA)
    assert "still comment" in naive


def test_a_rust_lifetime_is_not_a_character_literal() -> None:
    """`&'a str` opens a quote that never closes. Read as a character literal it
    runs to the next `'` in the file — often hundreds of lines away."""
    source = "fn s<'a>(x: &'a str) -> &'a str { x }\nfn after() { }\n"
    masked = _common.mask_source(source, _common.RUST)
    assert "fn after()" in masked
    assert "'a" in masked, "the lifetime should survive as code"


def test_a_rust_char_literal_is_masked() -> None:
    source = "fn f() { let c = '}'; }\n"
    masked = _common.mask_source(source, _common.RUST)
    assert masked.count("}") == 1, "the brace inside a char literal is not a brace"


def test_a_cpp_raw_string_holds_whatever_it_likes() -> None:
    """`R"( ... )"` has no escapes, so a quote or a brace inside it is text."""
    source = 'void f() { auto s = R"json({ "a": " })json"; }\nvoid g() { }\n'
    masked = _common.mask_source(source, _common.CPP)
    assert _common.match_brace(masked, masked.index("{")) > 0
    assert "void g()" in masked


def test_a_csharp_verbatim_string_escapes_quotes_by_doubling() -> None:
    source = 'void F() { var s = @"a "" { b"; }\nvoid G() { }\n'
    masked = _common.mask_source(source, _common.CSHARP)
    opening = masked.index("{")
    assert _common.match_brace(masked, opening) > 0
    assert "void G()" in masked


def test_a_java_text_block_is_masked() -> None:
    source = 'class A {\n  String s = """\n  { "a": 1 }\n  """;\n  void f() {}\n}\n'
    masked = _common.mask_source(source, _common.JAVA)
    assert _common.match_brace(masked, masked.index("{")) == len(source.rstrip()) - 1
    assert "void f()" in masked


def test_a_c_macro_continuation_cannot_open_a_block() -> None:
    """`#define LOOP(n) for (...) {` leaves an unbalanced brace that would swallow
    the next function whole. Preprocessor lines are blanked, continuations
    included, so the brace never exists."""
    source = "#define TWICE(x) do { \\\n    x; x; \\\n} while (0)\n\nint f(void) { return 1; }\n"
    masked = _common.mask_source(source, _common.C)
    braces = masked.index("{")
    assert _common.match_brace(masked, braces) == masked.rindex("}")
    assert "int f(void)" in masked


def test_a_cpp_digit_separator_is_not_a_character_literal() -> None:
    source = "int f() { return 1'000'000; }\nint g() { return 2; }\n"
    masked = _common.mask_source(source, _common.CPP)
    assert "int g()" in masked
    assert masked.count("}") == 2


def test_an_unterminated_string_ends_at_its_line() -> None:
    """A broken literal is a real thing to find in a real repository. Running it
    to the end of the file would take every function after it with it."""
    source = 'void f() { const char *s = "oops;\n}\nvoid g() { }\n'
    masked = _common.mask_source(source, _common.C)
    assert "void g()" in masked


def test_a_doc_comment_is_anchored_backwards() -> None:
    """Searched forwards from the top of a window, every function inherits the
    description of the one above it — which reads as correct, everywhere, and is
    wrong everywhere."""
    source = "/** Adds. */\nint add(int a) { return a; }\n\nint sub(int a) { return -a; }\n"
    assert _common.doc_comment_before(source, source.index("int add")) == "Adds."
    assert _common.doc_comment_before(source, source.index("int sub")) == ""


def test_a_doc_comment_stops_at_the_first_javadoc_tag() -> None:
    source = "/**\n * Authenticates a user.\n * @param id the user\n */\nvoid f() {}\n"
    assert _common.doc_comment_before(source, source.index("void f")) == "Authenticates a user."


def test_an_xml_doc_comment_loses_its_tags() -> None:
    """C# writes doc comments as XML, and `<summary>` is markup, not prose."""
    source = "/// <summary>Returns every report.</summary>\npublic void F() {}\n"
    assert _common.doc_comment_before(source, source.index("public")) == "Returns every report."


def test_the_shared_id_rule_is_the_maps_id_rule() -> None:
    """Every tracer derives ids from this one function, so it is the single place
    the map's rule can drift from the tracers' rule. Checked against
    `tests/test_node_ids.py`'s implementation rather than a copy of it."""
    cases = [
        ("src/auth/service.py", "authenticate"),
        ("src/Store.java", "find"),
        ("src/store.rs", "get"),
        ("src/UserBox.m", "recordForUser:"),
        ("weird name (1).cpp", "Foo::bar"),
    ]
    for path, name in cases:
        assert _common.derive_id(path, name) == reference_derive_id(path, name), path


def test_collision_suffixes_come_from_the_line_not_the_order() -> None:
    """Two functions of one name in one file both get a suffix, and the suffix is
    the definition line — so they cannot swap identities when one of them moves,
    and a caller that only asked about one of them still sees both suffixed."""
    functions = [
        {"file": "a.rs", "name": "get", "line": 10},
        {"file": "a.rs", "name": "get", "line": 38},
        {"file": "a.rs", "name": "new", "line": 20},
    ]
    _common.assign_ids(functions)
    assert [fn["id"] for fn in functions] == ["a_get_l10", "a_get_l38", "a_new"]


def test_two_names_that_derive_one_id_are_a_collision() -> None:
    """The suffix is decided by derived id, not by name.

    `__add__` and `add` are different names and one id, so counting names left
    both of them unsuffixed and sharing it. This is the mechanism behind 158 of
    the CPython standard library's duplicated ids, every C++ destructor beside
    its constructor, and every Java `Builder`/`builder()` pair.
    """
    functions = [
        {"file": "d.py", "name": "__add__", "line": 12},
        {"file": "d.py", "name": "add", "line": 40},
        {"file": "d.py", "name": "subtract", "line": 60},
    ]
    _common.assign_ids(functions)
    assert [fn["id"] for fn in functions] == ["d_add_l12", "d_add_l40", "d_subtract"]


def test_two_definitions_on_one_line_are_separated_by_position() -> None:
    """`_l<line>` cannot separate two definitions that share a line.

    `void set(int); void set(char);` written on one line is an overload set, and
    so is a bundled file's `function f(){}function F(){}`. No record carries a
    column, so the tie-break is source order on that line. 105 of PrimeVue's 107
    duplicated ids were this shape.
    """
    functions = [
        {"file": "a.cpp", "name": "set", "line": 7},
        {"file": "a.cpp", "name": "set", "line": 7},
        {"file": "a.cpp", "name": "set", "line": 9},
    ]
    _common.assign_ids(functions)
    assert [fn["id"] for fn in functions] == ["a_set_l7_1", "a_set_l7_2", "a_set_l9"]


def test_two_paths_that_fold_to_one_stem_are_separated_by_rank() -> None:
    """The collision the per-file suffixes cannot see.

    `distutils/_msvccompiler.py` and `distutils/msvccompiler.py` derive the same
    stem — the leading `_` collapses into the separator — so every function in
    one shadowed its namesake in the other. Rank comes from sorting the
    colliding paths, so it does not depend on which file was walked first.
    """
    functions = [
        {"file": "distutils/msvccompiler.py", "name": "link", "line": 4},
        {"file": "distutils/_msvccompiler.py", "name": "link", "line": 9},
        {"file": "distutils/ccompiler.py", "name": "link", "line": 3},
    ]
    _common.assign_ids(functions)
    assert [fn["id"] for fn in functions] == [
        "distutils_msvccompiler_link_f2",
        "distutils_msvccompiler_link_f1",
        "distutils_ccompiler_link",
    ]


def test_a_repository_with_no_collisions_keeps_every_bare_id() -> None:
    """The suffixes are the exception, not the shape. Ordinary code has to come
    out of `assign_ids` looking exactly like the rule the templates state, or
    every id in every hand-written map is wrong."""
    functions = [
        {"file": "src/web/views.py", "name": "login_view", "line": 10},
        {"file": "src/web/models.py", "name": "User", "line": 3},
        {"file": "src/main.py", "name": "main", "line": 1},
    ]
    _common.assign_ids(functions)
    assert [fn["id"] for fn in functions] == [
        "src_web_views_login_view",
        "src_web_models_user",
        "src_main_main",
    ]
