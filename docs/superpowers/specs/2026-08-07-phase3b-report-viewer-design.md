# Design: Phase 3b — the report viewer

**Date:** 2026-08-07
**Status:** Approved
**Target version:** 1.3.0
**Extends:** [`2026-08-07-phase3-quality-reporting-design.md`](2026-08-07-phase3-quality-reporting-design.md)
and, through it, [`2026-08-06-dry-kiss-yagni-reporting-design.md`](2026-08-06-dry-kiss-yagni-reporting-design.md)

## How this document was produced

Drafted without the usual question-at-a-time dialogue, at the user's request, while
they were away from a machine. Every decision below that would normally have been a
question is marked **Decision** with the reasoning and the alternative that was
rejected, so approval is a matter of ratifying or overturning specific calls rather
than reading between the lines.

One instruction was given directly and is not a recommendation: **the retrofit of
viewer validation to the existing flow viewer is in scope.**

## What 3b ships

- `templates/shared/report.template.html` — the quality-report viewer, carrying
  exactly one `__REPORT_DATA__` token
- `Code_Flows/quality-report.html`, added to step 5 of all three quality templates
- Installer changes so the new scaffold lands in `.code-flow/`
- One validation harness covering **both** scaffolds
- Version 1.3.0 in `package.json` and `pyproject.toml`

Additive within 1.x. No breaking change.

## The finding that reshaped this design

`viewer.template.html` already handles every failure the parent spec asks 3b to test.
Reading it end to end:

- a `TOKEN` check, deliberately reassembled at runtime as `"__FLOW" + "_DATA__"` so
  the installer's string replacement cannot clobber the check itself
- a `JSON.parse` inside `try`/`catch`, whose failure message even names the specific
  trap this format has (`literal </ inside snippet strings must be escaped`)
- a `problems[]` validator covering a missing or empty `nodes` array, non-string and
  malformed and duplicate node ids, non-object edges, and **edges whose `from` or
  `to` matches no node** — the dangling-reference case the parent spec names
- a `fail(title, lines)` path that renders an error card into `#err`

So the error handling is not missing. **Only the tests are.** The scaffold has shipped
since 1.0.0 with one assertion against it — that `__FLOW_DATA__` appears exactly once.

That reframes the work. 3b is not "build error handling and test it"; it is "test
error handling that already exists, and write the second viewer to the same standard".
It also means the retrofit is cheap: the flow viewer will not need behavior changes to
pass the harness, only the structural marking described below.

## Decision 1: how the harness runs — extract the pure validator, no browser

**This is the load-bearing decision and the one most worth overturning if you
disagree.**

The constraint: this repository has **zero npm dependencies, including dev
dependencies** — `package.json` has no `devDependencies` key at all — and Python's
dev group is exactly `pytest`. That posture has held for three phases and is part of
what makes the package cheap to trust.

Asserting "a malformed substitution does not blank the page" normally means executing
the page's JavaScript, which means a DOM, which means `jsdom` — the first npm
dependency the project would ever take.

**Decision: do not take the dependency. Restructure each viewer so its decision logic
is a pure function, and test that function directly.**

Every failure the spec cares about is decided before anything is drawn:

| Failure | Decided by | Needs a DOM? |
|---|---|---|
| Token never replaced | string compare against `TOKEN` | no |
| Malformed JSON | `JSON.parse` in a `try` | no |
| Missing/empty `nodes` | `problems[]` | no |
| Bad, duplicate, malformed node id | `problems[]` | no |
| Edge referencing a missing node | `problems[]` | no |
| A finding citing a missing flow | the report viewer's equivalent | no |

The DOM-touching part is `fail()` — eleven lines that create an `h2` and a `pre` and
append them. That is not where a silent failure hides.

So each scaffold marks its boot-and-validate block with sentinel comments:

```
/* ==== validate:start ==== */
function validate(raw, TOKEN) { … returns {ok:true, data} | {ok:false, title, lines} }
/* ==== validate:end ==== */
```

`validate` is pure: text in, verdict out. It touches no `document`. The test extracts
the source between the sentinels and evaluates it, then drives it with fixtures. The
shipped artifact stays a single self-contained file that works from a `file://` URL
with no network — a hard requirement that rules out splitting the JS into a module.

**Rejected: `jsdom` as a devDependency.** It would test more — that `fail()` really
renders — but it buys coverage of the eleven least-risky lines at the cost of the
project's dependency posture, a lockfile, and a supply-chain surface for a package
whose entire value proposition is "it just copies some files".

**Rejected: a hand-rolled DOM stub.** Dependency-free, but a stub that satisfies
`getElementById`/`createElement`/`appendChild`/`innerHTML`/`hidden` is fifty lines of
test-only code that itself has no tests, and it would drift from real DOM semantics
silently. That is the shape of problem this project keeps finding, not a fix for it.

**Accepted cost, stated plainly:** nothing will assert that the error card is
*visible*. If someone deletes `errBox.hidden = false`, the suite stays green. In-repo
mitigation is that `fail()` is asserted to be *called* with the right title and lines,
and its body is short enough to review.

**Ratified.** The decision was put to the approver and stands. The stated mitigation
for the rendering gap is that both scaffolds are opened against real codebases before
a release goes out. That is a genuine control and the reason the trade is acceptable —
but it is a **human-in-the-loop, pre-release** control, not an automated one, and this
document should not later be read as claiming the rendering is tested. Two consequences
follow, and they are requirements, not observations:

- A release of 1.3.0 is gated on someone having opened both `quality-report.html` and
  a flow `.html` in a browser. That step belongs in the release checklist, not in
  anyone's memory.
- Any future change to either scaffold's rendering — layout, theming, the error card —
  re-incurs the same gap. The green suite will not tell you. Treat a rendering change
  as requiring the manual pass again.

## Decision 2: `quality-report.html` is written unconditionally

The map side writes an `.html` per flow with no flag, so parity says yes. The obvious
objection — that it doubles the artifacts dropped into `Code_Flows/` — does not apply
here: the quality report is **one** file regardless of repository size, not one per
flow. There is nothing to multiply.

**Decision: written every run, alongside the `.json` and `.md`.** No flag.

## Decision 3: the output section gains a third rendering, and the parity baseline holds

3b must edit the quality templates, which Phase 3a just finished holding at parity
baseline 0. That is safe, and it is exactly what the output section was structured
for: the JSON is written first and every other artifact renders from it, so a third
rendering is an addition rather than a rewrite.

Two guards make this cheap now that they exist:

- `tests/test_host_parity.py` is committed, so drift fails the suite automatically
  rather than depending on someone re-running a script by hand.
- The rule that "nothing in it may contradict that file" already governs the
  markdown, and extends to the HTML unchanged.

**Decision: edit the output section in all three hosts, keep baseline 0, keep the
ordering rule verbatim.** The HTML is named after the markdown so the written order
is `json → md → html`.

### Correction, found in Phase 3b's Task 5 review: the output section is two steps, not one

This decision was first written as "edit step 5", and its two halves were
unsatisfiable together. The shipped templates split the output across **two**
sections — `#### 5. Write the Report Data` writes the JSON, `#### 6. Write the
Report` renders the markdown — so appending the HTML to step 5 would have produced
the written order `json → html → md`, contradicting the ordering rule in this same
decision and making the block's own opening word ("Last") false where it is read.

**The HTML paragraph is appended to the end of step 6, after the markdown.** Read
"step 5" anywhere in this document as naming the output section as a whole; the
ordering rule is the binding half. `tests/test_template_contracts.py` pins the
written order `json < md < html` in all three hosts, so moving the block back would
now fail the suite rather than pass quietly.

## Decision 4: what the report viewer shows

Deliberately narrow, because a viewer is where scope creep lives.

- The coverage banner first, matching the markdown's "coverage leads" rule and
  carrying the same changed-file and dropped-finding counts
- Findings in the JSON's order — the analysis already sorted them; the viewer must
  not re-sort, or two renderings of one file would disagree
- Per finding: `id`, `severity`, `principle`, `detector`, `title`, `rationale`,
  `suggestion`, `confidence`, its evidence fields, and its sites with
  `file:line`, `symbol` and `snippet`
- Filter by severity and by principle. **No sorting controls** — see above.
- The same light/dark theme toggle the flow viewer already has, so the two artifacts
  look like siblings

**Not in scope:** links from a finding into the flow viewer, cross-artifact
navigation, search, and anything that reads a file from disk. A finding names a
`file:line`; the viewer displays it as text. It cannot open an editor and must not
pretend to.

## Decision 5: the honesty rules bind the viewer too

This matters more than it sounds. The markdown's honesty rules exist because a
quality report is easy to over-read, and a *prettier* rendering makes over-reading
easier. So:

- Coverage leads, visually as well as structurally. It is not collapsible.
- "catalogued", never "all".
- An empty findings array renders the "clean within what was mapped" sentence
  prominently — **not** an empty state, and never a checkmark, a green banner, or
  anything else that reads as a pass. This is the single most dangerous screen in
  the product and the design should treat it that way.
- `unreached` findings render as candidates. The viewer never renders a delete
  affordance and never phrases a suggestion as an instruction to delete.
- A skipped detector is shown with its reason, not hidden.

These get contract tests against the template text, the same way the markdown's do.

## Testing

**The shared harness**, covering both scaffolds from one set of cases with
per-scaffold fixtures: token never replaced; malformed JSON; well-formed JSON of the
wrong shape; a dangling reference (a flow-viewer edge naming no node, a report-viewer
finding citing a missing flow); and a valid document, which must produce no problems.

**Retrofit.** The flow viewer is expected to pass without behavior changes. If a case
fails, that is a real bug the scaffold has been shipping since 1.0.0 — fix it and say
so in the task report rather than adjusting the test to match.

**Contract tests** for `report.template.html`: exactly one `__REPORT_DATA__` token,
the sentinel markers present, the honesty phrasings present, no external network
reference of any kind.

**Installer tests** in both languages: `EXPECTED_ALL` gains
`.code-flow/report.template.html`, asserted identically in `test/install.test.js` and
`tests/test_installer_python.py`, plus the byte-identity map and the README table pin
that Phase 3a added.

**Not tested, disclosed:** that the page renders correctly in a browser. No harness
here does that; the mitigation is that both scaffolds are self-contained static files
a human can open directly.

## Risks

- **The sentinel-extraction approach is unusual** and a reviewer may reasonably
  dislike it. It is the price of the zero-dependency posture. Decision 1 names the
  alternative.
- **`report.template.html` will be large** — the flow viewer is 436 lines. A viewer
  with filters and a theme toggle is a real frontend artifact in one file, and it
  cannot be split without breaking the offline single-file requirement. Expect
  400-600 lines and do not treat that as a defect.
- **`__REPORT_DATA__` substitution has the same `</` trap** the flow viewer documents
  in its own error message. Snippets in findings are source code and will contain it.
  The report viewer must carry the same escaping rule and say so in step 5.

## Approval

Decision 1 was the one open question and it was ratified as drafted: no browser
dependency, sentinel-extracted pure validators, with pre-release manual testing on
real codebases covering the rendering gap. See the ratification note under Decision 1
for the two requirements that follow from it.

Every other decision here is either forced by an existing rule or reversible cheaply.
