import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const tracer = path.join(repoRoot, "templates", "shared", "tracers", "trace_typescript.mjs");

const { maskSource, deriveId, matchBrace, trace } = await import(tracer);

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
