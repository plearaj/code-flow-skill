import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

const START = "/* ==== validate:start ==== */";
const END = "/* ==== validate:end ==== */";

// The scaffolds must stay single self-contained files that work from a file://
// URL, so their JS cannot be a module we could import. Instead each marks its
// pure decision logic with sentinels, and we lift that block out and run it.
// Nothing here touches the DOM, because nothing validate() does touches the DOM.
function extractValidate(templateName) {
  const src = fs.readFileSync(
    path.join(repoRoot, "templates", "shared", templateName),
    "utf8"
  );
  const from = src.indexOf(START);
  const to = src.indexOf(END);
  assert.ok(from !== -1, `${templateName} is missing ${START}`);
  assert.ok(to !== -1, `${templateName} is missing ${END}`);
  assert.ok(to > from, `${templateName} has its sentinels in the wrong order`);
  const block = src.slice(from + START.length, to);
  return new Function(`${block}; return validate;`)();
}

const SCAFFOLDS = [
  { file: "viewer.template.html", token: "__FLOW_DATA__" },
  { file: "report.template.html", token: "__REPORT_DATA__" },
];

for (const { file, token } of SCAFFOLDS) {
  test(`${file}: an unreplaced token is reported, not parsed`, () => {
    const validate = extractValidate(file);
    const v = validate(token, token);
    assert.equal(v.ok, false);
    assert.match(v.title + " " + v.lines.join(" "), /placeholder|never replaced/i);
  });

  test(`${file}: malformed JSON is reported with the parser's message`, () => {
    const validate = extractValidate(file);
    const v = validate("{ not json", token);
    assert.equal(v.ok, false);
    assert.match(v.title, /invalid json/i);
    assert.ok(v.lines.length > 0, "the parser's message must reach the user");
  });

  test(`${file}: well-formed JSON of the wrong shape is reported`, () => {
    const validate = extractValidate(file);
    const v = validate(JSON.stringify({ nothing: "useful" }), token);
    assert.equal(v.ok, false);
    assert.ok(v.lines.length > 0, "a shape failure must say what was wrong");
    // `ok:false` plus a non-empty `lines` array is satisfied by a validator
    // that rejects everything unconditionally (this is exactly what the
    // report.template.html stub does today, on purpose — see the RED-run
    // notes in the task report). For the flow viewer we know the real shape
    // rule, so pin the actual reason down rather than settling for "some
    // lines came back."
    if (file === "viewer.template.html") {
      assert.match(v.lines.join(" "), /`nodes` must be a non-empty array/);
    }
  });

  test(`${file}: an empty document is reported, not silently accepted`, () => {
    const validate = extractValidate(file);
    const v = validate("", token);
    assert.equal(v.ok, false);
    // Same rationale as above: `ok:false` alone doesn't distinguish "the
    // parser correctly rejected empty input" from "everything is rejected."
    // The flow viewer routes empty input through the JSON.parse failure
    // path, so assert on that specific title.
    if (file === "viewer.template.html") {
      assert.match(v.title, /invalid json/i);
    }
  });
}

test("viewer.template.html: an edge naming no node is reported", () => {
  const validate = extractValidate("viewer.template.html");
  const v = validate(
    JSON.stringify({
      meta: {},
      nodes: [{ id: "a_handle_request" }],
      edges: [{ from: "a_handle_request", to: "b_validate_email" }],
    }),
    "__FLOW_DATA__"
  );
  assert.equal(v.ok, false);
  assert.match(v.lines.join(" "), /b_validate_email.*does not match any node id/);
});

// The check above only exercises the `to`-side lookup. `from` and `to` are
// checked independently in the scaffold, so a fixture that only breaks `to`
// would leave a deleted `from` check undetected (confirmed by mutation: see
// task report). Cover the `from` side explicitly so both branches fire.
test("viewer.template.html: an edge whose from-endpoint names no node is reported", () => {
  const validate = extractValidate("viewer.template.html");
  const v = validate(
    JSON.stringify({
      meta: {},
      nodes: [{ id: "b_validate_email" }],
      edges: [{ from: "a_handle_request", to: "b_validate_email" }],
    }),
    "__FLOW_DATA__"
  );
  assert.equal(v.ok, false);
  assert.match(v.lines.join(" "), /a_handle_request.*does not match any node id/);
});

test("viewer.template.html: a valid flow document produces no problems", () => {
  const validate = extractValidate("viewer.template.html");
  const v = validate(
    JSON.stringify({
      meta: { title: "User login" },
      nodes: [{ id: "a_handle_request" }, { id: "b_validate_email" }],
      edges: [{ from: "a_handle_request", to: "b_validate_email" }],
    }),
    "__FLOW_DATA__"
  );
  assert.equal(v.ok, true, v.ok ? "" : v.title + ": " + (v.lines || []).join(" "));
  assert.equal(v.nodes.length, 2);
  assert.equal(v.edges.length, 1);
});
