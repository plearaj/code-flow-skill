import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const tracer = path.join(repoRoot, "templates", "shared", "tracers", "trace_typescript.mjs");

const { maskSource, deriveId, assignIds, matchBrace, trace } = await import(tracer);

// `tests/test_tracers.py` covers what the tracer produces for a whole fixture
// repository, in the same file as the Python tracer's equivalents, because the
// envelope they share is a cross-language contract. What it cannot reach is the
// lexer — and the lexer is the part everything else rests on. A `{` inside a
// string that the mask fails to blank moves a function's boundary, and every
// call inside that function is then attributed to the wrong place, with the
// output still looking entirely plausible.

test("maskSource blanks string bodies but keeps their quotes and length", () => {
  const src = 'const a = "he{llo}"; const b = 1;';
  const masked = maskSource(src);
  assert.equal(masked.length, src.length, "the mask must be index-for-index with the source");
  assert.ok(!masked.includes("{"), "a brace inside a string survived the mask");
  assert.equal(masked.indexOf('"'), src.indexOf('"'), "the opening quote must stay findable");
  assert.ok(masked.includes("const b = 1;"), "code outside the string was blanked");
});

test("maskSource blanks comments without moving line numbers", () => {
  const src = "a();\n// } not a brace\nb();\n/* c();\n */\nd();";
  const masked = maskSource(src);
  assert.equal(masked.split("\n").length, src.split("\n").length);
  assert.ok(!masked.includes("}"), "a brace inside a line comment survived");
  assert.ok(!masked.includes("c()"), "a call inside a block comment survived");
  assert.ok(masked.includes("a()") && masked.includes("b()") && masked.includes("d()"));
});

test("maskSource keeps interpolations inside template literals as code", () => {
  const src = "const t = `text ${format(x)} more {`;";
  const masked = maskSource(src);
  assert.ok(masked.includes("format(x)"), "a call inside ${...} must stay visible");
  assert.ok(!masked.includes("text"), "template text must be blanked");
  assert.ok(!masked.includes("more"), "template text after an interpolation must be blanked");
});

test("maskSource blanks a regex body without eating a division", () => {
  const src = "const r = /a{2}b/g; const q = total / 2;";
  const masked = maskSource(src);
  assert.ok(!masked.includes("{2}"), "a brace inside a regex survived the mask");
  assert.ok(masked.includes("total / 2"), "a division was mistaken for a regex");
});

test("matchBrace finds the closing brace of a nested block", () => {
  const src = "function f(){ if (x) { g(); } }  after";
  const open = src.indexOf("{");
  assert.equal(src.slice(open, matchBrace(maskSource(src), open)), "{ if (x) { g(); } }");
});

test("deriveId implements the map's documented rule", () => {
  // The same three cases `tests/test_node_ids.py` pins for the Python side.
  assert.equal(deriveId("src/web/views.ts", "loginView"), "src_web_views_loginview");
  assert.equal(deriveId("src/v2.1/handler.ts", "run"), "src_v2_1_handler_run");
  assert.equal(deriveId("bin/entrypoint", "main"), "bin_entrypoint_main");
});

test("assignIds separates two names that derive one id", () => {
  // Counted by derived id, not by name: `_render` and `render` slug to the same
  // string, and counting names left both of them unsuffixed and sharing it --
  // 107 duplicated ids across PrimeVue's 5,817 functions.
  const functions = [
    { file: "a.ts", name: "_render", line: 12 },
    { file: "a.ts", name: "render", line: 40 },
    { file: "a.ts", name: "mount", line: 60 },
  ];
  assignIds(functions);
  assert.deepEqual(functions.map((fn) => fn.id), ["a_render_l12", "a_render_l40", "a_mount"]);
});

test("assignIds separates two definitions that share a line", () => {
  // 105 of PrimeVue's 107 were this: a bundled file puts two definitions on one
  // line, and no record carries a column, so the tie-break is source order.
  const functions = [
    { file: "b.js", name: "f", line: 1 },
    { file: "b.js", name: "F", line: 1 },
    { file: "b.js", name: "f", line: 3 },
  ];
  assignIds(functions);
  assert.deepEqual(functions.map((fn) => fn.id), ["b_f_l1_1", "b_f_l1_2", "b_f_l3"]);
});

test("assignIds separates two paths that fold to one stem", () => {
  // The collision no per-file rule can see: `ui/_Button.tsx` and `ui/Button.tsx`
  // derive one stem, because the leading `_` collapses into the separator. Only
  // the name both files define is suffixed; rank comes from sorting the paths,
  // so it does not depend on which file was walked first.
  const functions = [
    { file: "ui/Button.tsx", name: "render", line: 4 },
    { file: "ui/_Button.tsx", name: "render", line: 9 },
    { file: "ui/_Button.tsx", name: "measure", line: 20 },
  ];
  assignIds(functions);
  assert.deepEqual(functions.map((fn) => fn.id), [
    "ui_button_render_f1",
    "ui_button_render_f2",
    "ui_button_measure",
  ]);
});

test("assignIds leaves every id bare when nothing collides", () => {
  // The suffixes are the exception, not the shape. Ordinary code has to come out
  // looking exactly like the rule the map templates state.
  const functions = [
    { file: "src/web/views.ts", name: "loginView", line: 10 },
    { file: "src/web/models.ts", name: "User", line: 3 },
  ];
  assignIds(functions);
  assert.deepEqual(functions.map((fn) => fn.id), ["src_web_views_loginview", "src_web_models_user"]);
});

test("a brace inside a string does not move a function's boundary", () => {
  // The failure this whole lexer exists to prevent, asserted end to end: without
  // the mask, `openBrace`'s body would swallow `after` and the call inside it.
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "code-flow-tracer-"));
  fs.writeFileSync(
    path.join(dir, "index.js"),
    [
      "export function openBrace() {",
      '  return "a { without a match";',
      "}",
      "export function after() {",
      "  return openBrace();",
      "}",
      "",
    ].join("\n")
  );
  const result = trace(dir, "thin");
  const names = result.functions.map((fn) => fn.name).sort();
  assert.deepEqual(names, ["after", "openBrace"]);
  const after = result.functions.find((fn) => fn.name === "after");
  assert.equal(after.calls.length, 1);
  assert.equal(after.calls[0].confidence, "exact");
  fs.rmSync(dir, { recursive: true, force: true });
});

test("an unparseable-looking file never crashes the run", () => {
  // A tracer that throws on one bad file maps nothing. It must skip and carry on.
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "code-flow-tracer-"));
  fs.writeFileSync(path.join(dir, "broken.ts"), "export function a( {{{ unterminated");
  fs.writeFileSync(path.join(dir, "fine.ts"), "export function b() { return 1; }\n");
  const result = trace(dir, "thin");
  assert.ok(
    result.functions.some((fn) => fn.name === "b"),
    "a broken sibling stopped a valid file from being catalogued"
  );
  fs.rmSync(dir, { recursive: true, force: true });
});
