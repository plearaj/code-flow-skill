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
    // that rejects everything unconditionally. Both scaffolds now have a
    // real validator, so pin the actual reason down for each rather than
    // settling for "some lines came back."
    if (file === "viewer.template.html") {
      assert.match(v.lines.join(" "), /`nodes` must be a non-empty array/);
    } else if (file === "report.template.html") {
      assert.match(v.lines.join(" "), /`schema` must be 1/);
      assert.match(v.lines.join(" "), /`meta` must be an object/);
      assert.match(v.lines.join(" "), /`coverage` must be an object/);
      assert.match(v.lines.join(" "), /`findings` must be an array/);
    }
  });

  test(`${file}: an empty document is reported, not silently accepted`, () => {
    const validate = extractValidate(file);
    const v = validate("", token);
    assert.equal(v.ok, false);
    // Same rationale as above: `ok:false` alone doesn't distinguish "the
    // parser correctly rejected empty input" from "everything is rejected."
    // Both scaffolds route empty input through the JSON.parse failure path,
    // so assert on that specific title for each.
    assert.match(v.title, /invalid json/i);
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

const VALID_REPORT = {
  schema: 1,
  meta: { root: "C:/Users/example/project", generated: "2026-08-07", readCode: false,
          mapGenerated: "2026-08-06", mapMode: "whole-code-base", mapDetail: "standard" },
  coverage: { flowsTraced: 14, entryPointsFound: 17, functionsCatalogued: 1180,
              flowsUnreadable: 0, filesChanged: 6, findingsDropped: 2, detectorsSkipped: [] },
  findings: [{
    id: "DRY-01", principle: "DRY", detector: "duplicate-intent", severity: "high",
    title: "Email validation is implemented three times",
    rationale: "Three functions normalise and check an address with the same rules.",
    suggestion: "Consolidate on one validator and have the others call it.",
    confidence: "unverified", effort: "small",
    sites: [{ file: "src/auth/validators.py", line: 12, symbol: "validate_email" }],
  }],
};

function report(overrides) {
  return JSON.stringify({ ...VALID_REPORT, ...overrides });
}

test("report.template.html: a valid report produces no problems", () => {
  const validate = extractValidate("report.template.html");
  const v = validate(report({}), "__REPORT_DATA__");
  assert.equal(v.ok, true, v.ok ? "" : v.title + ": " + (v.lines || []).join(" "));
  assert.equal(v.findings.length, 1);
  assert.equal(v.coverage.flowsTraced, 14);
});

test("report.template.html: an empty findings array is valid, not an error", () => {
  const validate = extractValidate("report.template.html");
  const v = validate(report({ findings: [] }), "__REPORT_DATA__");
  assert.equal(v.ok, true, "a clean report is a real report, not a failure");
  assert.equal(v.findings.length, 0);
});

test("report.template.html: a duplicate finding id is reported", () => {
  const validate = extractValidate("report.template.html");
  const dup = [VALID_REPORT.findings[0], { ...VALID_REPORT.findings[0] }];
  const v = validate(report({ findings: dup }), "__REPORT_DATA__");
  assert.equal(v.ok, false);
  assert.match(v.lines.join(" "), /duplicate finding id "DRY-01"/);
});

test("report.template.html: a finding with no sites is reported", () => {
  const validate = extractValidate("report.template.html");
  const bare = [{ ...VALID_REPORT.findings[0], sites: [] }];
  const v = validate(report({ findings: bare }), "__REPORT_DATA__");
  assert.equal(v.ok, false);
  assert.match(v.lines.join(" "), /DRY-01.*at least one site/);
});

test("report.template.html: an out-of-enum severity is reported", () => {
  const validate = extractValidate("report.template.html");
  const bad = [{ ...VALID_REPORT.findings[0], severity: "critical" }];
  const v = validate(report({ findings: bad }), "__REPORT_DATA__");
  assert.equal(v.ok, false);
  assert.match(v.lines.join(" "), /severity "critical"/);
});

test("report.template.html: a missing coverage block is reported", () => {
  const validate = extractValidate("report.template.html");
  const v = validate(report({ coverage: undefined }), "__REPORT_DATA__");
  assert.equal(v.ok, false);
  assert.match(v.lines.join(" "), /`coverage`/);
});

test("report.template.html: a wrong schema version is reported", () => {
  const validate = extractValidate("report.template.html");
  const v = validate(report({ schema: 2 }), "__REPORT_DATA__");
  assert.equal(v.ok, false);
  assert.match(v.lines.join(" "), /schema/i);
});
