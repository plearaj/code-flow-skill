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
  // Both scaffolds run this code inside `(function(){"use strict"; ...})()`.
  // Evaluating the extracted block without the same directive would run it in
  // sloppy mode, which is not "the same decision logic the browser runs" —
  // the one thing this harness exists to claim.
  return new Function('"use strict";' + block + "; return validate;")();
}

// `wrongShape` is per-scaffold on purpose. `{nothing:"useful"}` breaks a rule in
// the two data viewers, but the index legitimately *accepts* a registry carrying
// neither `flows` nor `files` — it drops those sections rather than erroring, so
// that document is valid there and would prove nothing. Each scaffold therefore
// supplies a document that violates one of its own rules, and names the message
// it expects back.
const SCAFFOLDS = [
  {
    file: "viewer.template.html",
    token: "__FLOW_DATA__",
    wrongShape: { nothing: "useful" },
    expect: [/`nodes` must be a non-empty array/],
  },
  {
    file: "report.template.html",
    token: "__REPORT_DATA__",
    wrongShape: { nothing: "useful" },
    expect: [
      /`schema` must be 1/,
      /`meta` must be an object/,
      /`coverage` must be an object/,
      /`findings` must be an array/,
    ],
  },
  {
    file: "index.template.html",
    token: "__INDEX_DATA__",
    wrongShape: { flows: "not-an-array" },
    expect: [/`flows` must be an array when present/],
  },
];

for (const { file, token, wrongShape, expect } of SCAFFOLDS) {
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
    const v = validate(JSON.stringify(wrongShape), token);
    assert.equal(v.ok, false);
    assert.ok(v.lines.length > 0, "a shape failure must say what was wrong");
    // `ok:false` plus a non-empty `lines` array is satisfied by a validator
    // that rejects everything unconditionally, so pin the actual reason each
    // scaffold gives rather than settling for "some lines came back."
    for (const pattern of expect) {
      assert.match(v.lines.join(" "), pattern);
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

// The index page's whole job is to survive a registry that is missing things:
// a feature-mode map has no `files` census, and a fresh repo has no `flows`.
// It must render those as absent sections, never as an error card — so the
// permissive path needs pinning as tightly as the rejecting one.
test("index.template.html: a registry with no flows and no files is accepted, not an error", () => {
  const validate = extractValidate("index.template.html");
  const v = validate(JSON.stringify({ meta: { mode: "feature" } }), "__INDEX_DATA__");
  assert.equal(v.ok, true, "an empty registry must render, not fail");
  assert.deepEqual(v.flows, [], "absent flows must normalise to an empty array");
  assert.deepEqual(v.files, [], "absent files must normalise to an empty array");
});

test("index.template.html: a flow entry without a slug is reported", () => {
  const validate = extractValidate("index.template.html");
  const v = validate(
    JSON.stringify({ flows: [{ title: "User Login" }] }),
    "__INDEX_DATA__"
  );
  assert.equal(v.ok, false);
  assert.match(v.lines.join(" "), /flows\[0\] is missing a string `slug`/);
});

// The bundle scaffold marks the same sentinels as the three scaffolds above,
// so it is lifted the same way. `liftValidator` is just `extractValidate`
// under the name this suite's cases use for it.
const liftValidator = extractValidate;

const bundleValidate = liftValidator("bundle.template.html");

test("bundle validator rejects the unreplaced token", () => {
  // Written as a concatenation so a naive string replace over this file cannot
  // rewrite the check itself — the same guard the other three scaffolds use.
  const TOKEN = "__BUNDLE" + "_DATA__";
  const r = bundleValidate(TOKEN, TOKEN);
  assert.equal(r.ok, false);
  assert.match(r.error, /not been generated|placeholder/i);
});

test("bundle validator rejects malformed JSON", () => {
  const r = bundleValidate("{not json", "__BUNDLE" + "_DATA__");
  assert.equal(r.ok, false);
});

test("bundle validator requires an index and a flows array", () => {
  const TOKEN = "__BUNDLE" + "_DATA__";
  assert.equal(bundleValidate('{"flows":[]}', TOKEN).ok, false, "missing index");
  assert.equal(bundleValidate('{"index":{}}', TOKEN).ok, false, "missing flows");
});

test("bundle validator accepts a report-less bundle", () => {
  // `report` is optional: a project that has never run /code-flow.quality has
  // no quality-report.json, and that is not an error.
  const TOKEN = "__BUNDLE" + "_DATA__";
  const data = '{"index":{"flows":[]},"flows":[]}';
  assert.equal(bundleValidate(data, TOKEN).ok, true);
});

// --- the shipped examples, against the scaffolds that must accept them -------

// Every test above feeds a validator something built to be rejected, which
// proves the validator says no. Nothing proved it says *yes* to a real
// document. `examples/` is the closest thing this repository has to real
// output — it is what the README shows and what a reader copies — so it is the
// right thing to put through the validators the scaffolds actually run.
//
// This gap shipped a bug: `--rules` added a fifth detector, `rule-violation`,
// and the report scaffold's allowlist was never told about it. A quality
// report produced with `--rules` failed validation and rendered as an error
// page instead of findings. Every other test passed, because none of them
// validated a document that had a rule-violation finding in it.
const EXAMPLES = [
  ["sample-flow.json", "viewer.template.html", "__FLOW_DATA__"],
  ["sample-report.json", "report.template.html", "__REPORT_DATA__"],
  ["sample-report-unverified.json", "report.template.html", "__REPORT_DATA__"],
];

for (const [example, scaffold, token] of EXAMPLES) {
  test(`${scaffold} accepts examples/${example}`, () => {
    const raw = fs.readFileSync(path.join(repoRoot, "examples", example), "utf8");
    const validate = extractValidate(scaffold);
    const v = validate(raw, token);
    assert.equal(
      v.ok,
      true,
      `examples/${example} was rejected by ${scaffold}: ` +
        `${v.title || ""} ${(v.lines || []).join(" ")}`
    );
  });
}

test("report.template.html accepts every detector the quality command can emit", () => {
  // Named individually rather than inferred from the examples, so that adding a
  // detector to the templates without adding it here fails, instead of quietly
  // depending on whether some example happens to use it.
  const DETECTORS = [
    "duplicate-intent",
    "repeated-sequence",
    "complexity-hotspot",
    "unreached",
    "rule-violation",
  ];
  const validate = extractValidate("report.template.html");
  const base = JSON.parse(
    fs.readFileSync(path.join(repoRoot, "examples", "sample-report.json"), "utf8")
  );

  for (const detector of DETECTORS) {
    const doc = { ...base, findings: [{ ...base.findings[0], detector }] };
    const v = validate(JSON.stringify(doc), "__REPORT_DATA__");
    assert.equal(
      v.ok,
      true,
      `the report scaffold rejects detector "${detector}": ` +
        `${(v.lines || []).join(" ")}`
    );
  }
});

test("the bundle accepts a bundle built from the shipped examples", () => {
  const flow = JSON.parse(
    fs.readFileSync(path.join(repoRoot, "examples", "sample-flow.json"), "utf8")
  );
  const report = JSON.parse(
    fs.readFileSync(path.join(repoRoot, "examples", "sample-report.json"), "utf8")
  );
  const bundle = {
    index: { flows: [{ slug: flow.meta.slug, feature: flow.meta.feature }] },
    flows: [flow],
    report,
  };
  const v = extractValidate("bundle.template.html")(
    JSON.stringify(bundle),
    "__BUNDLE" + "_DATA__"
  );
  assert.equal(v.ok, true, `${v.title || ""} ${(v.lines || []).join(" ")}`);
});
