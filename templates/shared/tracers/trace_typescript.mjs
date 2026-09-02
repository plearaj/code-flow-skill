#!/usr/bin/env node
/**
 * Static call-graph and component tracer for TypeScript / JavaScript repositories.
 *
 * Emits the same JSON envelope `trace_python.py` does, plus a `components` array,
 * because the front-end half of a TypeScript repository is a component tree and a
 * call graph that ignored it would describe half the system. `/code-flow-map` runs
 * this before it traces anything.
 *
 * Design constraints, in the order they mattered:
 *
 * **Zero dependencies, and no TypeScript compiler.** It runs under any Node 18+
 * inside the user's repository, where `typescript` may not be installed and
 * `node_modules` may not exist. So it lexes rather than parses: comments, string
 * bodies, template text and regex literals are blanked out in place — same length,
 * same line breaks, same indices — and every structural search runs over that mask
 * while every literal value is read back out of the original text. That is what
 * keeps a `//` inside a URL string, or a `{` inside a comment, from moving a
 * function's boundary.
 *
 * **Ids join with the map.** The `id` rule here is byte-for-byte the rule the map
 * templates state, collision suffix included.
 *
 * **Honest resolution.** `confidence` is `exact` when an import or a same-file
 * definition made the target certain and `heuristic` when a unique name match was
 * the only evidence. Calls that could mean several things land in `ambiguousCalls`
 * with their candidates instead of being guessed into an edge.
 *
 * Usage:
 *
 *     node trace_typescript.mjs [--root DIR] [--out FILE] [--detail LEVEL]
 *
 * `--detail thin|standard|verbose` governs snippets exactly as `/code-flow-map`'s
 * own flag does.
 */
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { execFileSync } from "node:child_process";

const TRACER_SCHEMA = 1;

const SOURCE_EXT = new Set([
  ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts", ".vue", ".svelte",
]);
const RESOLVE_EXT = [
  ".ts", ".tsx", ".d.ts", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts", ".vue", ".svelte",
];

const PRUNE_DIRS = new Set([
  ".git", ".hg", ".svn", ".idea", ".vscode", "node_modules", "bower_components",
  "dist", "build", "out", "target", "vendor", "third_party", "coverage",
  ".next", ".nuxt", ".svelte-kit", ".output", ".angular", ".cache", ".turbo",
  ".venv", "venv", "__pycache__", ".terraform", "storybook-static",
]);
// Matched against whole path *segments*, never as substrings: "dist" and
// "build" occur inside ordinary words, and a file skipped for a reason that is
// not true is worse than a file not skipped — it is absent from the map with an
// explanation that looks right.
const VENDORED_DIRS = new Set([
  "node_modules", "vendor", "third_party", "bower_components", ".venv", "venv", "env",
]);
const GENERATED_DIRS = new Set([
  "dist", "build", "out", "target", "coverage", ".next", ".nuxt", ".svelte-kit",
  ".output", ".angular", ".turbo", ".cache", "storybook-static",
]);
// Filename markers, so these *are* substring tests — of the last path segment
// only, where ".min." and ".d.ts" mean what they say.
const GENERATED_FILE_MARKERS = [".min.", ".bundle.", ".d.ts", "-generated.", ".generated."];

const TEST_DIRS = new Set(["test", "tests", "spec", "specs", "__tests__", "__mocks__", "e2e", "cypress"]);

// Words that are followed by `(` but are not calls.
const NOT_CALLS = new Set([
  "if", "for", "while", "switch", "catch", "return", "function", "typeof", "await",
  "new", "delete", "void", "yield", "in", "of", "do", "else", "case", "with",
  "super", "import", "require", "constructor", "set", "get", "async", "throw",
  "String", "Number", "Boolean", "Array", "Object", "Promise", "Error", "Date",
  "Math", "JSON", "Symbol", "Map", "Set", "WeakMap", "WeakSet", "RegExp", "BigInt",
  "parseInt", "parseFloat", "isNaN", "console", "expect", "describe", "it", "test",
]);

// Method names every array, string, promise and map answers to. A call like
// `rows.map(...)` has a receiver this tracer cannot type, and matching `map`
// against the one function in the repository that happens to be named `map`
// invents an edge that does not exist. Names here are never resolved by the
// unique-name fallback when the call has a receiver.
const COMMON_METHODS = new Set([
  "map", "filter", "forEach", "reduce", "find", "findIndex", "some", "every", "sort",
  "slice", "splice", "concat", "join", "push", "pop", "shift", "unshift", "includes",
  "indexOf", "then", "catch", "finally", "json", "text", "toString", "valueOf", "get",
  "set", "has", "delete", "add", "clear", "keys", "values", "entries", "trim", "split",
  "replace", "match", "test", "exec", "toUpperCase", "toLowerCase", "startsWith",
  "endsWith", "padStart", "padEnd", "repeat", "charAt", "substring", "flat", "flatMap",
  "bind", "call", "apply", "on", "off", "once", "emit", "next", "subscribe", "pipe",
]);

// Call text that means the function touches the world outside the process.
const IO_CALL_RE = new RegExp(
  [
    "^(fetch|XMLHttpRequest|WebSocket|EventSource)$",
    "^(axios|http|https|got|ky|superagent)\\b",
    "\\.(query|execute|findOne|findMany|findAll|insert|update|delete|save|commit|transaction)$",
    "^(localStorage|sessionStorage|indexedDB)\\b",
    "^(fs|fsPromises)\\.",
    "\\.(readFile|writeFile|readFileSync|writeFileSync|appendFile|mkdir|unlink)$",
    "\\.(emit|publish|send|sendMail|dispatch|postMessage)$",
  ].join("|")
);

// --- ids -------------------------------------------------------------------

/**
 * Return the map's `id` for a function named `name` defined in `file`.
 *
 * The rule, verbatim from the map templates: drop the extension from the path's
 * last segment only, append `_` and the unqualified name, lowercase, replace
 * every character outside `[a-z0-9_]`, collapse runs, trim.
 */
export function deriveId(file, name) {
  const cut = file.lastIndexOf("/");
  const head = cut === -1 ? "" : file.slice(0, cut);
  const last = cut === -1 ? file : file.slice(cut + 1);
  const dot = last.lastIndexOf(".");
  const stem = dot <= 0 ? last : last.slice(0, dot);
  const combined = head ? `${head}/${stem}_${name}` : `${stem}_${name}`;
  return combined.toLowerCase().replace(/[^a-z0-9_]+/g, "_").replace(/_+/g, "_").replace(/^_|_$/g, "");
}

/**
 * Set a unique `id` on every record in `functions`, in place.
 *
 * Called once with the whole repository's functions, and the exact counterpart
 * of `assign_ids` in `_common.py` -- the five tracers have to agree on this or
 * a map built from two of them joins against nothing. Three suffixes, each one
 * applied only where the step before it left two records sharing a string, so
 * code with no collisions gets the bare `deriveId` result the templates state:
 *
 * - `_l<line>` when one file derives one id twice. Counted by derived id, not
 *   by name: `_render` and `render`, `F` and `f`, a getter and its setter all
 *   slug to one string, and counting names left 107 duplicated ids across
 *   PrimeVue's 5,817 functions.
 * - `_<n>` when two of those are on the same line -- a bundled file's
 *   `function f(){}function F(){}` is one line and two definitions, and no
 *   record carries a column. `n` is the 1-based position among that line's
 *   same-id definitions, in source order. 105 of PrimeVue's 107 were this.
 * - `_f<rank>` when two files derive one id: the rule drops the extension, so
 *   `store.ts` and `store.js` beside each other fold to one stem, and it
 *   collapses underscore runs, so `ui/_Button.tsx` and `ui/Button.tsx` do too.
 *   The one suffix not decided from a single file's contents, because the
 *   collision is not inside one file, and applied only to the ids two files
 *   actually both derived, so a pair that shares a stem does not rename the
 *   functions that never collided. `rank` is the file's 1-based position among
 *   those files' paths, sorted in code-point order, so it is fixed by the
 *   repository's file names rather than by traversal order.
 */
export function assignIds(functions) {
  const groups = new Map();
  for (const fn of functions) {
    const key = `${fn.file}\u0000${deriveId(fn.file, fn.name)}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(fn);
  }
  for (const group of groups.values()) {
    const base = deriveId(group[0].file, group[0].name);
    if (group.length === 1) {
      group[0].id = base;
      continue;
    }
    const byLine = new Map();
    for (const fn of group) {
      if (!byLine.has(fn.line)) byLine.set(fn.line, []);
      byLine.get(fn.line).push(fn);
    }
    for (const [line, onLine] of byLine) {
      if (onLine.length === 1) onLine[0].id = `${base}_l${line}`;
      else onLine.forEach((fn, i) => (fn.id = `${base}_l${line}_${i + 1}`));
    }
  }

  const filesById = new Map();
  for (const fn of functions) {
    if (!filesById.has(fn.id)) filesById.set(fn.id, new Set());
    filesById.get(fn.id).add(fn.file);
  }
  const ranks = new Map();
  for (const [id, paths] of filesById) {
    if (paths.size < 2) continue;
    const byPath = new Map();
    [...paths].sort().forEach((file, i) => byPath.set(file, i + 1));
    ranks.set(id, byPath);
  }
  if (ranks.size === 0) return;
  for (const fn of functions) {
    const byPath = ranks.get(fn.id);
    if (byPath) fn.id = `${fn.id}_f${byPath.get(fn.file)}`;
  }
}

// --- lexing ----------------------------------------------------------------

/**
 * Return `src` with comments, string bodies, template text and regex bodies
 * replaced by spaces, preserving length, indices and newlines.
 *
 * Quotes, backticks and slashes are kept so a literal's extent stays findable and
 * its value can be read back out of the original text by index. Interpolations
 * inside a template literal are left as code, because a call inside `${...}` is a
 * real call.
 */
export function maskSource(src) {
  const out = Array.from(src);
  const n = src.length;
  const blank = (from, to) => {
    for (let k = from; k < to && k < n; k++) if (out[k] !== "\n") out[k] = " ";
  };
  // A stack of contexts: "code" (with a brace depth, so `}` can close a `${`)
  // and "tpl" for the literal text of a template.
  const stack = [{ type: "code", brace: 0 }];
  let i = 0;
  let prev = "";       // last significant character seen in code
  let prevWord = "";   // last identifier/keyword seen, for regex-vs-divide
  while (i < n) {
    const ctx = stack[stack.length - 1];
    const c = src[i];
    if (ctx.type === "tpl") {
      if (c === "\\") { blank(i, i + 2); i += 2; continue; }
      if (c === "`") { i += 1; stack.pop(); prev = "`"; continue; }
      if (c === "$" && src[i + 1] === "{") { i += 2; stack.push({ type: "code", brace: 0, inTpl: true }); prev = "{"; continue; }
      if (out[i] !== "\n") out[i] = " ";
      i += 1;
      continue;
    }
    if (c === "/" && src[i + 1] === "/") {
      let j = src.indexOf("\n", i);
      if (j === -1) j = n;
      blank(i, j);
      i = j;
      continue;
    }
    if (c === "/" && src[i + 1] === "*") {
      let j = src.indexOf("*/", i + 2);
      j = j === -1 ? n : j + 2;
      blank(i, j);
      i = j;
      continue;
    }
    if (c === '"' || c === "'") {
      let j = i + 1;
      while (j < n && src[j] !== c) {
        if (src[j] === "\\") j += 1;
        if (src[j] === "\n") break;
        j += 1;
      }
      blank(i + 1, j);
      i = Math.min(j + 1, n);
      prev = c;
      continue;
    }
    if (c === "`") { i += 1; stack.push({ type: "tpl" }); continue; }
    if (c === "/" && regexCanStartHere(prev, prevWord)) {
      let j = i + 1;
      let inClass = false;
      while (j < n) {
        const d = src[j];
        if (d === "\\") { j += 2; continue; }
        if (d === "\n") break;
        if (d === "[") inClass = true;
        else if (d === "]") inClass = false;
        else if (d === "/" && !inClass) break;
        j += 1;
      }
      if (j < n && src[j] === "/") {
        blank(i + 1, j);
        i = j + 1;
        prev = "/";
        continue;
      }
    }
    if (c === "{") ctx.brace += 1;
    if (c === "}") {
      if (ctx.brace === 0 && ctx.inTpl) { stack.pop(); i += 1; prev = "}"; continue; }
      ctx.brace = Math.max(0, ctx.brace - 1);
    }
    if (/[A-Za-z_$]/.test(c)) {
      let j = i;
      while (j < n && /[\w$]/.test(src[j])) j += 1;
      prevWord = src.slice(i, j);
      prev = src[j - 1];
      i = j;
      continue;
    }
    if (!/\s/.test(c)) { prev = c; prevWord = ""; }
    i += 1;
  }
  return out.join("");
}

const REGEX_PRECEDERS = new Set(["(", ",", "=", ":", "[", "!", "&", "|", "?", "{", "}", ";", "+", "-", "*", "%", "~", "^", "<", ">", ""]);
const REGEX_KEYWORDS = new Set(["return", "typeof", "instanceof", "in", "of", "new", "delete", "void", "do", "else", "case", "yield", "await"]);

function regexCanStartHere(prev, prevWord) {
  if (REGEX_KEYWORDS.has(prevWord)) return true;
  if (/[\w$)\]]/.test(prev)) return false;
  return REGEX_PRECEDERS.has(prev);
}

/** Return the index just past the `}` matching the `{` at `open`. */
export function matchBrace(masked, open) {
  let depth = 0;
  for (let i = open; i < masked.length; i++) {
    const c = masked[i];
    if (c === "{") depth += 1;
    else if (c === "}") {
      depth -= 1;
      if (depth === 0) return i + 1;
    }
  }
  return masked.length;
}

/** Return the index just past the `)` matching the `(` at `open`. */
function matchParen(masked, open) {
  let depth = 0;
  for (let i = open; i < masked.length; i++) {
    const c = masked[i];
    if (c === "(") depth += 1;
    else if (c === ")") {
      depth -= 1;
      if (depth === 0) return i + 1;
    }
  }
  return masked.length;
}

/** Line number (1-based) of a character offset. */
function lineAt(lineStarts, index) {
  let lo = 0;
  let hi = lineStarts.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (lineStarts[mid] <= index) lo = mid;
    else hi = mid - 1;
  }
  return lo + 1;
}

function lineStartsOf(src) {
  const starts = [0];
  for (let i = 0; i < src.length; i++) if (src[i] === "\n") starts.push(i + 1);
  return starts;
}

// --- discovery -------------------------------------------------------------

/**
 * Return the repository's tracked and untracked-but-not-ignored files.
 *
 * Preferred over walking the tree because it applies the project's real ignore
 * rules rather than this file's approximation of them. Returns null when the
 * directory is not a git checkout or git is not installed.
 */
function gitTrackedFiles(root) {
  try {
    const out = execFileSync("git", ["-C", root, "ls-files", "--cached", "--others", "--exclude-standard"], {
      encoding: "utf8",
      maxBuffer: 64 * 1024 * 1024,
      stdio: ["ignore", "pipe", "ignore"],
    });
    // An empty listing is not a usable answer: git ran, but under a directory
    // the repository ignores it names nothing, and `[]` is truthy here -- so
    // `gitTrackedFiles(root) || walkFiles(root)` would keep it and the tracer
    // would catalogue an empty repository without saying so. Null falls through
    // to the walk, which is what the caller already does for a missing git.
    const listed = out.split("\n").filter(Boolean);
    return listed.length ? listed : null;
  } catch {
    return null;
  }
}

function walkFiles(root) {
  const found = [];
  const walk = (dir, prefix) => {
    let entries;
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const entry of entries.sort((a, b) => (a.name < b.name ? -1 : 1))) {
      if (entry.isDirectory()) {
        if (PRUNE_DIRS.has(entry.name)) continue;
        walk(path.join(dir, entry.name), prefix ? `${prefix}/${entry.name}` : entry.name);
      } else if (entry.isFile()) {
        found.push(prefix ? `${prefix}/${entry.name}` : entry.name);
      }
    }
  };
  walk(root, "");
  return found;
}

/** Return why `rel` is not analyzable, or null if it is a source file. */
function skipReason(rel) {
  const lowered = rel.toLowerCase();
  const parts = lowered.split("/");
  const directories = parts.slice(0, -1);
  const name = parts[parts.length - 1];
  if (directories.some((p) => VENDORED_DIRS.has(p))) return "vendored";
  if (directories.some((p) => GENERATED_DIRS.has(p))) return "generated";
  if (directories.some((p) => PRUNE_DIRS.has(p))) return "generated";
  if (!SOURCE_EXT.has(path.extname(lowered))) return null;
  if (GENERATED_FILE_MARKERS.some((m) => name.includes(m))) return "generated";
  return null;
}

function isTestPath(rel) {
  const parts = rel.split("/");
  const base = parts[parts.length - 1];
  if (parts.slice(0, -1).some((p) => TEST_DIRS.has(p))) return true;
  return /\.(test|spec)\.[cm]?[jt]sx?$/.test(base) || /^(test|spec)[-_.]/.test(base);
}

function fileHash(abs) {
  try {
    return "sha256:" + crypto.createHash("sha256").update(fs.readFileSync(abs)).digest("hex").slice(0, 6);
  } catch {
    return null;
  }
}

// --- imports ---------------------------------------------------------------

/**
 * Return this file's local-name -> {module, name} map, plus every specifier it
 * pulls in. Scans the mask so a specifier inside a comment is invisible, then
 * reads the specifier text back out of the original source by index.
 */
function collectImports(src, masked) {
  const imports = new Map();
  const specifiers = [];
  const add = (local, module, name, typeOnly) => {
    if (!imports.has(local)) imports.set(local, { module, name, typeOnly: !!typeOnly });
  };

  const importRe = /\bimport\s+(type\s+)?([\s\S]*?)\s*\bfrom\s*(['"])/g;
  let m;
  while ((m = importRe.exec(masked)) !== null) {
    const quote = m.index + m[0].length - 1;
    const end = masked.indexOf(m[3], quote + 1);
    if (end === -1) continue;
    const module = src.slice(quote + 1, end);
    specifiers.push(module);
    const clause = m[2];
    const typeOnly = !!m[1];
    const namespace = /\*\s*as\s+([A-Za-z_$][\w$]*)/.exec(clause);
    if (namespace) add(namespace[1], module, null, typeOnly);
    const named = /\{([\s\S]*)\}/.exec(clause);
    if (named) {
      for (const piece of named[1].split(",")) {
        const parts = piece.trim().replace(/^type\s+/, "").split(/\s+as\s+/);
        const original = parts[0].trim();
        const local = (parts[1] || parts[0]).trim();
        if (original) add(local, module, original, typeOnly);
      }
    }
    const beforeBrace = clause.split(/[,{]/)[0].trim();
    if (/^[A-Za-z_$][\w$]*$/.test(beforeBrace)) add(beforeBrace, module, "default", typeOnly);
    importRe.lastIndex = end + 1;
  }

  const bareRe = /\b(?:import|export)\s*(?:\*\s*)?(?:\{[^}]*\}\s*)?(?:from\s*)?(['"])/g;
  const requireRe = /\b(?:require|import)\s*\(\s*(['"])/g;
  for (const re of [bareRe, requireRe]) {
    re.lastIndex = 0;
    while ((m = re.exec(masked)) !== null) {
      const quote = m.index + m[0].length - 1;
      const end = masked.indexOf(m[1], quote + 1);
      if (end === -1) continue;
      const spec = src.slice(quote + 1, end);
      if (spec && !specifiers.includes(spec)) specifiers.push(spec);
    }
  }

  const cjsRe = /\b(?:const|let|var)\s+(\{[^}]*\}|[A-Za-z_$][\w$]*)\s*=\s*require\s*\(\s*(['"])/g;
  while ((m = cjsRe.exec(masked)) !== null) {
    const quote = m.index + m[0].length - 1;
    const end = masked.indexOf(m[2], quote + 1);
    if (end === -1) continue;
    const module = src.slice(quote + 1, end);
    const target = m[1];
    if (target.startsWith("{")) {
      for (const piece of target.slice(1, -1).split(",")) {
        const parts = piece.trim().split(":");
        const original = parts[0].trim();
        const local = (parts[1] || parts[0]).trim();
        if (original) add(local, module, original, false);
      }
    } else {
      add(target, module, null, false);
    }
  }
  return { imports, specifiers };
}

// --- declarations ----------------------------------------------------------

/**
 * The keywords that open a block a reader has to hold a case for. `class`,
 * `function` and a bare scope are not among them: brace depth is not decision
 * depth, and counting an object literal or a nested class would report a wide
 * configuration table as complex.
 */
const CONTROL_KEYWORDS = new Set([
  "if", "else", "for", "while", "do", "switch", "try", "catch", "finally",
]);

/**
 * Whether the `{` at `brace` opens the body of a control statement.
 *
 * Decided from the start of the statement the brace belongs to, not the token in
 * front of it: `if (cond) {` ends in `)` and a paren-free head ends in an
 * ordinary identifier, and reading back to the nearest `{`, `}` or `;` covers
 * both, and covers `} else {` as the same case. A `)` on the way back is stepped
 * over whole, because `for (i = 0; i < n; i++)` carries semicolons of its own.
 *
 * Two shapes settle first: a `{` directly after `(`, `,`, `=`, `:` or `[` is an
 * argument or an initialiser and never a block, and a `{` after `=>` is a
 * block-bodied arrow, which carries no keyword to find.
 */
function opensAControlBlock(masked, brace, floor) {
  let i = brace - 1;
  while (i >= floor && /\s/.test(masked[i])) i -= 1;
  if (i < floor) return false;
  if (masked[i] === ">" && i > floor && masked[i - 1] === "=") return true;
  if ("(,=:[".includes(masked[i])) return false;
  let j = i;
  while (j >= floor && !"{};".includes(masked[j])) {
    if (masked[j] === ")") {
      let opened = 0;
      for (; j >= floor; j--) {
        if (masked[j] === ")") opened += 1;
        else if (masked[j] === "(") {
          opened -= 1;
          if (opened === 0) break;
        }
      }
    }
    j -= 1;
  }
  let k = j + 1;
  while (k <= i && /\s/.test(masked[k])) k += 1;
  let word = "";
  while (k <= i && /[\w$]/.test(masked[k])) word += masked[k++];
  return CONTROL_KEYWORDS.has(word);
}

/**
 * How deeply control flow nests inside one function body.
 *
 * The same measurement `_common.py::max_control_nesting` takes for the four
 * Python-hosted tracers, over the same masked text -- a `{` inside a string or
 * a comment has already been blanked. The body's own outermost brace is not a
 * level, so a flat function returns 0.
 *
 * A nested arrow or function expression is catalogued in its own right with its
 * own count, but its braces are inside this body and are counted here too: the
 * mask cannot tell a callback's `if` from its enclosing function's. That
 * over-reports a function built out of inline callbacks, which is the direction
 * to err in for a detector whose findings are candidates for reading.
 */
function maxControlNesting(masked, start, end) {
  const stack = [];
  let depth = 0;
  let best = 0;
  for (let i = start; i < end; i++) {
    if (masked[i] === "{") {
      const control = opensAControlBlock(masked, i, start);
      stack.push(control);
      if (control) best = Math.max(best, (depth += 1));
    } else if (masked[i] === "}") {
      if (stack.pop()) depth -= 1;
    }
  }
  return best;
}

/**
 * The two span finders every collector below shares.
 *
 * Both close over one file's masked text and nothing else, so they are built
 * once per file and handed to whichever collector needs them -- the same way
 * `collectClassMembers` has always taken them.
 */
function spanFinders(masked) {
const bodyAfterParams = (from) => {
  // From just past a parameter list, skip a return-type annotation and land on
  // the body's `{`, or on the `=>` of a concise arrow body.
  let i = from;
  let depth = 0;
  while (i < masked.length) {
    const c = masked[i];
    if (c === "{" && depth === 0) return { open: i, end: matchBrace(masked, i) };
    if (c === "(" || c === "[" || c === "<") depth += 1;
    else if (c === ")" || c === "]" || c === ">") depth = Math.max(0, depth - 1);
    else if (c === ";" && depth === 0) return null;
    i += 1;
  }
  return null;
};

const arrowBody = (arrowEnd) => {
  let i = arrowEnd;
  while (i < masked.length && /\s/.test(masked[i])) i += 1;
  if (masked[i] === "{") return { open: i, end: matchBrace(masked, i) };
  // A concise body: run to the end of the statement at depth 0.
  let depth = 0;
  for (let j = i; j < masked.length; j++) {
    const c = masked[j];
    if (c === "(" || c === "[" || c === "{") depth += 1;
    else if (c === ")" || c === "]" || c === "}") {
      if (depth === 0) return { open: i, end: j };
      depth -= 1;
    } else if ((c === ";" || c === "\n") && depth === 0) {
      if (c === "\n") {
        const rest = masked.slice(j + 1, j + 200);
        if (/^\s*[.?:&|+*/-]/.test(rest)) continue;
      }
      return { open: i, end: j };
    }
  }
  return { open: i, end: masked.length };
};

  return { bodyAfterParams, arrowBody };
}

/** `function name(...)`, declared or as a named expression. */
function collectFunctionDeclarations(rel, src, masked, lineStarts, spans) {
  const { bodyAfterParams } = spans;
  const functions = [];
  const push = (entry) => functions.push(entry);
  const fnRe = /(?:^|[^\w$.'"])(export\s+)?(default\s+)?(async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)\s*(?:<[^<>]*>)?\s*\(/g;
  let m;
  while ((m = fnRe.exec(masked)) !== null) {
    const nameStart = m.index + m[0].lastIndexOf(m[4]);
    const paren = m.index + m[0].length - 1;
    const afterParams = matchParen(masked, paren);
    const body = bodyAfterParams(afterParams);
    if (!body) continue;
    const declStart = m.index + (m[0].length - m[0].trimStart().length);
    push({
      name: m[4],
      file: rel,
      start: declStart,
      line: lineAt(lineStarts, nameStart),
      bodyStart: body.open,
      bodyEnd: body.end,
      endLine: lineAt(lineStarts, body.end - 1),
      signature: oneLine(src.slice(declStart, Math.min(afterParams, body.open))),
      exported: !!m[1] || !!m[2],
      async: !!m[3],
      kind: "function",
      class: null,
      decorators: [],
    });
    fnRe.lastIndex = paren;
  }
  return functions;
}

/** `const name = (...) => ...` and `const name = function (...) { ... }`. */
function collectBoundFunctions(rel, src, masked, lineStarts, spans) {
  const { bodyAfterParams, arrowBody } = spans;
  const functions = [];
  const push = (entry) => functions.push(entry);
  let m;
  const bindRe = /(?:^|[^\w$.])(export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*(?::\s*[^=;]+?)?=\s*(async\s+)?(\(|<|function\b|[A-Za-z_$][\w$]*\s*=>)/g;
  while ((m = bindRe.exec(masked)) !== null) {
    const declStart = m.index + (m[0].length - m[0].trimStart().length);
    const valueStart = m.index + m[0].length - m[4].length;
    let body = null;
    let signatureEnd = valueStart;
    if (m[4] === "function") {
      const paren = masked.indexOf("(", valueStart);
      if (paren === -1) continue;
      const afterParams = matchParen(masked, paren);
      signatureEnd = afterParams;
      body = bodyAfterParams(afterParams);
    } else if (m[4].endsWith("=>")) {
      // `const f = x => …`: the binding regex matched the arrow itself, so
      // there is nothing to search for.
      const arrow = m.index + m[0].length - 2;
      signatureEnd = arrow;
      body = arrowBody(arrow + 2);
    } else {
      // `(params) => …` or `<T>(params) => …`. Find where the parameter list
      // closes, then require the binding's own `=>` to follow it.
      let scan;
      if (m[4] === "<") {
        const paren = masked.indexOf("(", valueStart);
        if (paren === -1) continue;
        scan = matchParen(masked, paren);
      } else {
        scan = matchParen(masked, valueStart);
      }
      const arrow = masked.indexOf("=>", scan);
      if (arrow === -1) continue;
      // Only a return-type annotation may sit between the parameter list and
      // the arrow. Anything else — a property access, a call, an operator —
      // means the parentheses were a grouped expression, not a parameter list,
      // and the arrow belongs to a callback inside it. Taking it would both
      // invent a function and skip `lastIndex` past the real ones after it.
      if (!/^\s*(:[^=]*)?$/.test(masked.slice(scan, arrow))) continue;
      signatureEnd = arrow;
      body = arrowBody(arrow + 2);
    }
    if (!body) continue;
    push({
      name: m[2],
      file: rel,
      start: declStart,
      line: lineAt(lineStarts, declStart),
      bodyStart: body.open,
      bodyEnd: body.end,
      endLine: lineAt(lineStarts, Math.max(body.open, body.end - 1)),
      signature: oneLine(src.slice(declStart, Math.min(signatureEnd, declStart + 300))),
      exported: !!m[1],
      async: !!m[3],
      kind: "function",
      class: null,
      decorators: [],
    });
    bindRe.lastIndex = Math.max(bindRe.lastIndex, body.open);
  }
  return functions;
}

/** Classes, and every method inside them. */
function collectClasses(rel, src, masked, lineStarts, spans) {
  const { bodyAfterParams, arrowBody } = spans;
  const functions = [];
  const classes = new Map();
  const push = (entry) => functions.push(entry);
  let m;
  const classRe = /(?:^|[^\w$.])(export\s+)?(default\s+)?(?:abstract\s+)?class\s+([A-Za-z_$][\w$]*)/g;
  while ((m = classRe.exec(masked)) !== null) {
    const name = m[3];
    const open = masked.indexOf("{", m.index + m[0].length);
    if (open === -1) continue;
    const end = matchBrace(masked, open);
    const headEnd = open;
    const heritage = src.slice(m.index, headEnd);
    const decorators = decoratorsBefore(src, masked, m.index);
    const record = {
      name,
      file: rel,
      line: lineAt(lineStarts, m.index),
      start: m.index,
      bodyStart: open,
      bodyEnd: end,
      exported: !!m[1] || !!m[2],
      extends: (/\bextends\s+([A-Za-z_$][\w$.]*)/.exec(heritage) || [])[1] || null,
      implements: (/\bimplements\s+([^{]+)/.exec(heritage) || [])[1] || null,
      decorators,
      methods: new Map(),
      members: [],
    };
    classes.set(name, record);
    for (const method of collectClassMembers(rel, src, masked, lineStarts, record, bodyAfterParams, arrowBody)) {
      record.methods.set(method.name, method);
      push(method);
    }
    classRe.lastIndex = open;
  }
  return { functions, classes };
}

/**
 * Find every named function, method, arrow binding and class in one file.
 *
 * Every span is decided by brace or paren matching over the mask, never by a
 * regex reaching across the file: a `}` inside a string or comment has already
 * been blanked, so the boundaries this returns are the real ones.
 *
 * The three passes are independent and the order they concatenate in does not
 * reach the output: `buildOutput` sorts the whole catalog by file and line
 * before emitting it, and ids take their `_l` collision suffix from a function's
 * line rather than its position. That is what makes splitting one loop into
 * three safe, and it is worth knowing before anyone reorders them back.
 */
function collectFunctions(rel, src, masked, lineStarts) {
  const spans = spanFinders(masked);
  const { functions: methods, classes } = collectClasses(rel, src, masked, lineStarts, spans);
  return {
    functions: [
      ...collectFunctionDeclarations(rel, src, masked, lineStarts, spans),
      ...collectBoundFunctions(rel, src, masked, lineStarts, spans),
      ...methods,
    ],
    classes,
  };
}

/** Return the decorators written immediately above `index`, outermost first. */
function decoratorsBefore(src, masked, index) {
  const found = [];
  let i = index;
  for (let guard = 0; guard < 20; guard++) {
    const head = masked.slice(0, i);
    const at = head.lastIndexOf("@");
    if (at === -1) return found.reverse();
    const between = masked.slice(at, i);
    // Only a decorator if nothing but its own call and whitespace sits between.
    const paren = masked.indexOf("(", at);
    let stop = at;
    if (paren !== -1 && /^@[A-Za-z_$][\w$.]*\s*$/.test(masked.slice(at, paren))) {
      stop = matchParen(masked, paren);
    } else {
      const nameMatch = /^@[A-Za-z_$][\w$.]*/.exec(between);
      if (!nameMatch) return found.reverse();
      stop = at + nameMatch[0].length;
    }
    if (!/^\s*$/.test(masked.slice(stop, i))) return found.reverse();
    found.push(src.slice(at, stop));
    i = at;
  }
  return found.reverse();
}

/** Scan one class body for methods and arrow-valued properties. */
function collectClassMembers(rel, src, masked, lineStarts, cls, bodyAfterParams, arrowBody) {
  const members = [];
  const body = masked.slice(cls.bodyStart + 1, cls.bodyEnd - 1);
  const base = cls.bodyStart + 1;
  let depth = 0;
  let i = 0;
  let statementStart = 0;
  while (i < body.length) {
    const c = body[i];
    if (c === "{" || c === "(" || c === "[") depth += 1;
    else if (c === "}" || c === ")" || c === "]") depth = Math.max(0, depth - 1);
    if (depth === 0 && (c === ";" || c === "}" || c === "\n")) {
      statementStart = i + 1;
      i += 1;
      continue;
    }
    if (depth === 0 && /[A-Za-z_$#@]/.test(c) && (i === 0 || /[\s;}]/.test(body[i - 1]))) {
      const slice = body.slice(i, i + 400);
      const method = /^((?:(?:public|private|protected|readonly|static|abstract|override|declare|async|get|set)\s+)*)\*?\s*([A-Za-z_$#][\w$]*)\s*(?:<[^<>]*>)?\s*\(/.exec(slice);
      if (method) {
        const nameOffset = i + method[0].lastIndexOf(method[2]);
        const paren = base + i + method[0].length - 1;
        const afterParams = matchParen(masked, paren);
        const span = bodyAfterParams(afterParams);
        if (span) {
          members.push({
            name: method[2],
            file: rel,
            start: base + i,
            line: lineAt(lineStarts, base + nameOffset),
            bodyStart: span.open,
            bodyEnd: span.end,
            endLine: lineAt(lineStarts, span.end - 1),
            signature: oneLine(`${cls.name}.${src.slice(base + nameOffset, Math.min(afterParams, span.open))}`),
            exported: cls.exported && !/\bprivate\b/.test(method[1]),
            async: /\basync\b/.test(method[1]),
            kind: "method",
            class: cls.name,
            decorators: decoratorsBefore(src, masked, base + i),
          });
          i = span.end - base;
          continue;
        }
      }
      const prop = /^((?:(?:public|private|protected|readonly|static|override|declare)\s+)*)([A-Za-z_$#][\w$]*)\s*(?::\s*[^=;]+?)?=\s*(async\s+)?(\(|[A-Za-z_$][\w$]*\s*=>)/.exec(slice);
      if (prop) {
        const valueStart = base + i + prop[0].length - prop[4].length;
        const scan = prop[4] === "(" ? matchParen(masked, valueStart) : valueStart;
        const arrow = masked.indexOf("=>", scan);
        if (arrow !== -1 && arrow < scan + 200) {
          const span = arrowBody(arrow + 2);
          members.push({
            name: prop[2],
            file: rel,
            start: base + i,
            line: lineAt(lineStarts, base + i),
            bodyStart: span.open,
            bodyEnd: span.end,
            endLine: lineAt(lineStarts, Math.max(span.open, span.end - 1)),
            signature: oneLine(`${cls.name}.${src.slice(base + i, Math.min(arrow, base + i + 200))}`),
            exported: cls.exported && !/\bprivate\b/.test(prop[1]),
            async: !!prop[3],
            kind: "method",
            class: cls.name,
            decorators: decoratorsBefore(src, masked, base + i),
          });
          i = span.end - base;
          continue;
        }
      }
      const field = /^((?:(?:public|private|protected|readonly|static|override|declare)\s+)*)([A-Za-z_$#][\w$]*)\s*(?:[?!])?\s*(?::|=)/.exec(slice);
      if (field) {
        cls.members.push({
          name: field[2],
          decorators: decoratorsBefore(src, masked, base + i),
          text: oneLine(src.slice(base + i, base + i + 160)),
          line: lineAt(lineStarts, base + i),
        });
      }
      // Skip past this identifier so the scan cannot rematch inside it.
      let j = i;
      while (j < body.length && /[\w$#@.]/.test(body[j])) j += 1;
      i = Math.max(j, i + 1);
      continue;
    }
    i += 1;
  }
  return members;
}

function oneLine(text) {
  return text.replace(/\s+/g, " ").trim();
}

// --- single-file components ------------------------------------------------

/**
 * Return the regions of a `.vue` or `.svelte` file that are script, plus its
 * template text.
 *
 * Everything outside a `<script>` block is blanked in the mask rather than cut
 * out, so every offset and line number still refers to the real file.
 */
function splitSingleFileComponent(src, masked) {
  const scriptRanges = [];
  const re = /<script\b([^>]*)>/gi;
  let m;
  while ((m = re.exec(src)) !== null) {
    const open = m.index + m[0].length;
    const close = src.toLowerCase().indexOf("</script>", open);
    const end = close === -1 ? src.length : close;
    scriptRanges.push({ start: open, end, attrs: m[1] || "" });
    re.lastIndex = end;
  }
  let template = "";
  const tpl = /<template\b[^>]*>([\s\S]*)<\/template>/i.exec(src);
  if (tpl) template = tpl[1];
  if (!scriptRanges.length) return { masked: " ".repeat(0) + masked.replace(/[^\n]/g, " "), scriptRanges, template };
  const chars = Array.from(masked);
  for (let i = 0; i < chars.length; i++) {
    const inScript = scriptRanges.some((r) => i >= r.start && i < r.end);
    if (!inScript && chars[i] !== "\n") chars[i] = " ";
  }
  return { masked: chars.join(""), scriptRanges, template };
}

/** Return the capitalized or hyphenated element names used in a template. */
function templateTags(template) {
  const tags = new Set();
  const re = /<\s*([A-Za-z][\w.-]*)/g;
  let m;
  while ((m = re.exec(template)) !== null) {
    const tag = m[1];
    if (/^[A-Z]/.test(tag) || tag.includes("-")) tags.add(tag);
  }
  return [...tags];
}

// --- calls -----------------------------------------------------------------

/**
 * Attribute every call site in a file to the innermost named function
 * containing it.
 *
 * Anonymous callbacks are deliberately not their own nodes: a call inside
 * `items.map(x => save(x))` belongs to the function a reader would name.
 */
function collectCallSites(rel, src, masked, lineStarts, functions) {
  const spans = functions
    .map((fn) => ({ fn, from: fn.bodyStart, to: fn.bodyEnd }))
    .sort((a, b) => a.to - a.from - (b.to - b.from));
  const owner = (index) => {
    for (const span of spans) if (index >= span.from && index < span.to) return span.fn;
    return null;
  };

  const callRe = /([A-Za-z_$][\w$]*(?:\s*\.\s*[A-Za-z_$][\w$]*)*)\s*(?:<[^<>()]*>\s*)?\(/g;
  let m;
  while ((m = callRe.exec(masked)) !== null) {
    const text = m[1].replace(/\s+/g, "");
    const parts = text.split(".");
    const name = parts[parts.length - 1];
    const receiver = parts.length > 1 ? parts.slice(0, -1).join(".") : null;
    if (NOT_CALLS.has(name) && !receiver) continue;
    const before = masked[m.index - 1];
    // The guard exists so `a.b(` is counted once for the whole path rather than
    // again for `b`: a `.` in front means the regex has already captured this
    // name as part of a longer one. A spread's third dot sits in exactly that
    // position and means the opposite -- `...f(x)` is a call like any other.
    const spread = before === "." && masked.slice(m.index - 3, m.index) === "...";
    if (!spread && before && /[\w$.]/.test(before)) continue;
    if (/\b(function|class)\s*$/.test(masked.slice(Math.max(0, m.index - 12), m.index))) continue;
    const fn = owner(m.index);
    if (!fn) continue;
    if (IO_CALL_RE.test(text)) fn.io = true;
    (fn.rawCalls ||= []).push({ name, receiver, text, line: lineAt(lineStarts, m.index) });
  }

  const jsxRe = /<\s*([A-Z][\w$]*(?:\.[A-Z][\w$]*)*)/g;
  while ((m = jsxRe.exec(masked)) !== null) {
    const fn = owner(m.index);
    if (!fn) continue;
    (fn.rendered ||= new Set()).add(m[1].split(".")[0]);
  }
}

// --- framework detection ---------------------------------------------------

function readJson(abs) {
  try {
    return JSON.parse(fs.readFileSync(abs, "utf8"));
  } catch {
    return null;
  }
}

/** Return the front-end and back-end frameworks this repository declares. */
function detectFrameworks(root, files) {
  const pkg = readJson(path.join(root, "package.json")) || {};
  const deps = { ...(pkg.dependencies || {}), ...(pkg.devDependencies || {}), ...(pkg.peerDependencies || {}) };
  const has = (name) => Object.prototype.hasOwnProperty.call(deps, name);
  const frameworks = [];
  if (has("react") || has("preact") || has("next") || files.some((f) => f.endsWith(".tsx") || f.endsWith(".jsx"))) frameworks.push("react");
  if (has("vue") || has("nuxt") || files.some((f) => f.endsWith(".vue"))) frameworks.push("vue");
  if (has("@angular/core") || files.some((f) => /\.component\.ts$/.test(f))) frameworks.push("angular");
  if (has("svelte") || files.some((f) => f.endsWith(".svelte"))) frameworks.push("svelte");
  if (has("solid-js")) frameworks.push("solid");
  const backend = [];
  for (const name of ["express", "koa", "fastify", "@nestjs/core", "hapi", "@hapi/hapi", "apollo-server", "next"]) {
    if (has(name)) backend.push(name.replace("@nestjs/core", "nestjs").replace("@hapi/hapi", "hapi"));
  }
  return { frontend: frameworks, backend, pkg };
}

// --- components ------------------------------------------------------------

const REACT_LIFECYCLE = new Set([
  "componentDidMount", "componentDidUpdate", "componentWillUnmount", "render", "shouldComponentUpdate",
]);
const ANGULAR_LIFECYCLE = new Set([
  "ngOnInit", "ngOnChanges", "ngOnDestroy", "ngAfterViewInit", "ngAfterContentInit", "ngDoCheck",
]);
const VUE_LIFECYCLE = new Set([
  "created", "mounted", "updated", "unmounted", "beforeMount", "beforeUnmount", "beforeDestroy", "destroyed", "setup",
]);

/** Pull `key: 'value'` out of a decorator or options object, by index. */
function optionString(text, key) {
  const re = new RegExp(`\\b${key}\\s*:\\s*(['"\`])([\\s\\S]*?)\\1`);
  const m = re.exec(text);
  return m ? m[2] : null;
}

function optionList(text, key) {
  const re = new RegExp(`\\b${key}\\s*:\\s*\\[([\\s\\S]*?)\\]`);
  const m = re.exec(text);
  if (!m) return [];
  return m[1]
    .split(",")
    .map((piece) => piece.trim().replace(/^['"`]|['"`]$/g, "").split(/[\s(]/)[0])
    .filter(Boolean);
}

/**
 * Return every UI component this file declares, for whichever framework it is
 * written in. The framework is decided per file, not per repository: a monorepo
 * with an Angular admin app and a React storefront is one repository.
 */
/**
 * Angular: the decorator is the declaration, so it needs no heuristic.
 */
function angularComponents(file, pascal) {
  const { rel, src, masked, functions, classes, template, imports } = file;
  const found = [];
  for (const cls of classes.values()) {
    const decorator = cls.decorators.find((d) => /^@(Component|Directive|Pipe|Injectable|NgModule)\b/.test(d));
    if (!decorator) continue;
    const type = /^@(\w+)/.exec(decorator)[1];
    const inputs = cls.members.filter((mm) => mm.decorators.some((d) => d.startsWith("@Input"))).map((mm) => mm.name);
    const outputs = cls.members.filter((mm) => mm.decorators.some((d) => d.startsWith("@Output"))).map((mm) => mm.name);
    const hooks = [...cls.methods.keys()].filter((n) => ANGULAR_LIFECYCLE.has(n));
    found.push({
      id: deriveId(rel, cls.name),
      name: cls.name,
      file: rel,
      line: cls.line,
      framework: "angular",
      kind: type === "Component" ? "component" : type === "Injectable" ? "service" : type.toLowerCase(),
      selector: optionString(decorator, "selector"),
      templateFile: optionString(decorator, "templateUrl"),
      template: optionString(decorator, "template"),
      inputs,
      outputs,
      hooks,
      exported: cls.exported,
      children: [],
      declares: type === "NgModule" ? optionList(decorator, "declarations") : [],
      imports: type === "NgModule" ? optionList(decorator, "imports") : optionList(decorator, "imports"),
      members: [...cls.methods.keys()].map((n) => deriveId(rel, n)),
    });
  }
  return found;
}
/**
 * Vue and Svelte single-file components: the file is the component.
 */
function singleFileComponents(file, pascal) {
  const { rel, src, masked, functions, classes, template } = file;
  const ext = path.extname(rel);
  const found = [];
  if (ext === ".vue" || ext === ".svelte") {
    const framework = ext === ".vue" ? "vue" : "svelte";
    const setup = /defineProps\s*(?:<([\s\S]*?)>)?\s*\(([\s\S]*?)\)/.exec(src);
    const emits = /defineEmits\s*(?:<([\s\S]*?)>)?\s*\(([\s\S]*?)\)/.exec(src);
    const props = setup
      ? [...(setup[1] || setup[2] || "").matchAll(/([A-Za-z_$][\w$]*)\s*[?:]/g)].map((mm) => mm[1])
      : [...(/\bprops\s*:\s*\{([\s\S]*?)\n\s*\}/.exec(src)?.[1] || "").matchAll(/([A-Za-z_$][\w$]*)\s*:/g)].map((mm) => mm[1]);
    found.push({
      id: deriveId(rel, pascal),
      name: pascal,
      file: rel,
      line: 1,
      framework,
      kind: "component",
      selector: null,
      inputs: props,
      outputs: emits ? [...(emits[1] || emits[2] || "").matchAll(/['"]?([A-Za-z_$][\w$-]*)['"]?\s*[:(]/g)].map((mm) => mm[1]) : [],
      hooks: functions.filter((fn) => VUE_LIFECYCLE.has(fn.name)).map((fn) => fn.name),
      exported: true,
      children: [],
      tags: templateTags(template || ""),
      members: functions.map((fn) => fn.id).filter(Boolean),
    });
  }
  return found;
}
/**
 * React and Solid: a capitalized function that returns markup.
 */
function reactComponents(file, pascal, frameworks) {
  const { rel, src, masked, functions, classes, template } = file;
  const found = [];
  if (frameworks.includes("react") || frameworks.includes("solid")) {
    for (const fn of functions) {
      if (!/^[A-Z]/.test(fn.name)) continue;
      if (fn.class) continue;
      const rendersJsx = fn.rendered && fn.rendered.size > 0;
      const body = src.slice(fn.bodyStart, fn.bodyEnd);
      const looksJsx = rendersJsx || /return\s*\(?\s*</.test(body) || /createElement\s*\(/.test(body);
      if (!looksJsx) continue;
      const params = /\(([^)]*)\)/.exec(fn.signature);
      const destructured = params && params[1].trim().startsWith("{")
        ? [...params[1].matchAll(/([A-Za-z_$][\w$]*)\s*[,:}=]/g)].map((mm) => mm[1])
        : [];
      found.push({
        id: fn.id,
        name: fn.name,
        file: rel,
        line: fn.line,
        framework: frameworks.includes("solid") && !frameworks.includes("react") ? "solid" : "react",
        kind: /\/(pages|app|views|routes)\//.test("/" + rel) ? "page" : "component",
        selector: null,
        inputs: destructured,
        outputs: [],
        hooks: [...new Set((fn.rawCalls || []).filter((c) => /^use[A-Z]/.test(c.name)).map((c) => c.name))],
        exported: fn.exported,
        children: [],
        tags: [...(fn.rendered || [])],
        members: [fn.id],
      });
    }
    for (const cls of classes.values()) {
      if (!cls.extends || !/Component|PureComponent/.test(cls.extends)) continue;
      found.push({
        id: deriveId(rel, cls.name),
        name: cls.name,
        file: rel,
        line: cls.line,
        framework: "react",
        kind: "component",
        selector: null,
        inputs: [],
        outputs: [],
        hooks: [...cls.methods.keys()].filter((n) => REACT_LIFECYCLE.has(n)),
        exported: cls.exported,
        children: [],
        tags: [],
        members: [...cls.methods.values()].map((mm) => mm.id).filter(Boolean),
      });
    }
  }
  return found;
}
/**
 * Custom React hooks and Vue composables: neither components nor plain
 * functions, but where a component's behaviour actually lives.
 */
function behaviourHooks(file, pascal, frameworks) {
  const { rel, src, masked, functions, classes, template } = file;
  const found = [];
  // functions: they are where a component's behavior actually lives.
  for (const fn of functions) {
    if (!/^use[A-Z]/.test(fn.name) || fn.class) continue;
    found.push({
      id: fn.id,
      name: fn.name,
      file: rel,
      line: fn.line,
      framework: frameworks.includes("vue") && !frameworks.includes("react") ? "vue" : "react",
      kind: "hook",
      selector: null,
      inputs: [],
      outputs: [],
      hooks: [...new Set((fn.rawCalls || []).filter((c) => /^use[A-Z]/.test(c.name)).map((c) => c.name))],
      exported: fn.exported,
      children: [],
      tags: [],
      members: [fn.id],
    });
  }
  return found;
}

/**
 * Every component this file declares, in framework order.
 *
 * Each framework recognises its own shape and nothing else, so they are four
 * independent passes over one file rather than one pass with four branches.
 * They concatenate in the order below, which is the order the catalog has
 * always been in.
 */
function collectComponents(file, frameworks) {
  const { rel, imports } = file;
  const ext = path.extname(rel);
  const base = path.basename(rel, ext);
  const pascal = base
    .split(/[-_.]/)
    .filter(Boolean)
    .map((p) => p[0].toUpperCase() + p.slice(1))
    .join("");

  const found = [
    ...angularComponents(file, pascal),
    ...singleFileComponents(file, pascal),
    ...reactComponents(file, pascal, frameworks),
    ...behaviourHooks(file, pascal, frameworks),
  ];
  for (const component of found) {
    component.importedNames = [...imports.keys()];
  }
  return found;
  return found;
}

// --- module resolution -----------------------------------------------------

/** Read `compilerOptions.baseUrl` and `paths` from tsconfig or jsconfig. */
function loadPathAliases(root) {
  for (const name of ["tsconfig.json", "jsconfig.json", "tsconfig.base.json"]) {
    const abs = path.join(root, name);
    if (!fs.existsSync(abs)) continue;
    let text;
    try {
      text = fs.readFileSync(abs, "utf8");
    } catch {
      continue;
    }
    // tsconfig is JSON with comments and trailing commas in the wild, so it is
    // masked the same way source is before being parsed.
    const cleaned = maskSource(text).replace(/,(\s*[}\]])/g, "$1");
    let data = null;
    try {
      data = JSON.parse(text.replace(/\/\/[^\n]*/g, "").replace(/\/\*[\s\S]*?\*\//g, "").replace(/,(\s*[}\]])/g, "$1"));
    } catch {
      try {
        data = JSON.parse(cleaned);
      } catch {
        data = null;
      }
    }
    if (!data || !data.compilerOptions) continue;
    const options = data.compilerOptions;
    return {
      baseUrl: options.baseUrl ? path.posix.normalize(options.baseUrl.replace(/\\/g, "/")) : null,
      paths: options.paths || {},
    };
  }
  return { baseUrl: null, paths: {} };
}

/**
 * Resolve an import specifier to a repo-relative file, or null when it leaves
 * the repository. Applies Node's extension and `index` rules and any tsconfig
 * `paths` alias, because an unresolved alias is a whole subtree of missing edges.
 */
function makeResolver(fileSet, aliases) {
  const candidates = (base) => {
    const list = [base];
    for (const ext of RESOLVE_EXT) list.push(base + ext);
    for (const ext of RESOLVE_EXT) list.push(`${base}/index${ext}`);
    return list;
  };
  const firstExisting = (base) => candidates(base).find((c) => fileSet.has(c)) || null;
  return (fromRel, spec) => {
    if (!spec) return null;
    if (spec.startsWith(".")) {
      const dir = fromRel.includes("/") ? fromRel.slice(0, fromRel.lastIndexOf("/")) : "";
      const joined = path.posix.normalize(dir ? `${dir}/${spec}` : spec).replace(/^\.\//, "");
      return firstExisting(joined);
    }
    for (const [pattern, targets] of Object.entries(aliases.paths || {})) {
      const star = pattern.indexOf("*");
      if (star === -1) {
        if (pattern !== spec) continue;
        for (const target of targets) {
          const hit = firstExisting(path.posix.normalize(`${aliases.baseUrl || "."}/${target}`).replace(/^\.\//, ""));
          if (hit) return hit;
        }
        continue;
      }
      const head = pattern.slice(0, star);
      const tail = pattern.slice(star + 1);
      if (!spec.startsWith(head) || !spec.endsWith(tail)) continue;
      const middle = spec.slice(head.length, spec.length - tail.length);
      for (const target of targets) {
        const base = path.posix.normalize(`${aliases.baseUrl || "."}/${target.replace("*", middle)}`).replace(/^\.\//, "");
        const hit = firstExisting(base);
        if (hit) return hit;
      }
    }
    if (aliases.baseUrl) {
      const hit = firstExisting(path.posix.normalize(`${aliases.baseUrl}/${spec}`).replace(/^\.\//, ""));
      if (hit) return hit;
    }
    return null;
  };
}

// --- call resolution -------------------------------------------------------

/** Collect `const x = new Foo()` bindings and Angular constructor injection. */
function collectVarTypes(src, masked, classes) {
  const types = new Map();
  // `new Foo()` names the class outright; an annotation names a type that may
  // be an interface or a base class, so the two carry different confidence.
  const re = /\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*(?::\s*([A-Za-z_$][\w$]*))?\s*=\s*new\s+([A-Za-z_$][\w$]*)/g;
  let m;
  while ((m = re.exec(masked)) !== null) types.set(m[1], { type: m[3] || m[2], confidence: "exact" });
  const annotated = /\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*:\s*([A-Z][\w$]*)/g;
  while ((m = annotated.exec(masked)) !== null) {
    if (!types.has(m[1])) types.set(m[1], { type: m[2], confidence: "heuristic" });
  }
  for (const cls of classes.values()) {
    const ctor = cls.methods.get("constructor");
    if (!ctor) continue;
    const head = src.slice(ctor.start, ctor.bodyStart);
    const params = /\(([\s\S]*)\)/.exec(head);
    if (!params) continue;
    for (const piece of params[1].split(",")) {
      const injected = /(?:private|public|protected|readonly)?\s*([A-Za-z_$][\w$]*)\s*:\s*([A-Z][\w$]*)/.exec(piece);
      if (injected) types.set(`this.${injected[1]}`, { type: injected[2], confidence: "heuristic" });
    }
  }
  return types;
}

function resolveAllCalls(repo) {
  for (const file of repo.files.values()) {
    for (const fn of file.functions) {
      const resolved = [];
      const seen = new Set();
      for (const call of fn.rawCalls || []) {
        const outcome = resolveCall(repo, file, fn, call);
        if (!outcome) continue;
        if (outcome.kind === "call") {
          const key = `${outcome.to}@${outcome.line}`;
          if (seen.has(key)) continue;
          seen.add(key);
          resolved.push({ to: outcome.to, name: call.name, line: call.line, confidence: outcome.confidence });
        } else if (outcome.kind === "ambiguous") {
          repo.ambiguous.push({ from: fn.id, name: call.name, line: call.line, candidates: outcome.candidates });
        } else if (outcome.kind === "external") {
          const slot = repo.external.get(outcome.name) || { name: outcome.name, module: outcome.module, callers: [] };
          if (!slot.callers.includes(fn.id)) slot.callers.push(fn.id);
          repo.external.set(outcome.name, slot);
        }
      }
      fn.calls = resolved;
    }
  }
}

function exportedFunctionIn(repo, rel, name) {
  const file = repo.files.get(rel);
  if (!file) return null;
  const matches = file.functions.filter((f) => f.name === name && !f.class);
  if (matches.length === 1) return matches[0];
  const cls = file.classes.get(name);
  if (cls) {
    const ctor = cls.methods.get("constructor");
    if (ctor) return ctor;
  }
  return null;
}

/** The class a heritage clause names, and the file it was declared in. */
function classByName(repo, file, name) {
  const simple = name.split(".").pop();
  const local = file.classes.get(simple);
  if (local) return { file, cls: local };
  const imported = file.imports.get(simple);
  if (!imported) return null;
  const rel = repo.resolve(file.rel, imported.module);
  const other = rel && repo.files.get(rel);
  if (!other) return null;
  const named = imported.name && imported.name !== "default" ? imported.name : simple;
  const cls = other.classes.get(named) || other.classes.get(simple);
  return cls ? { file: other, cls } : null;
}

/**
 * The base-class methods `fn` overrides, nearest base first.
 *
 * Only `extends` is followed. `implements` names an interface, and an interface
 * declares no bodies, so there is no method record to check the name against --
 * naming one anyway would report an override for every method of a class that
 * happens to implement something. A base outside the repository resolves to
 * nothing and is not named, the same silence a call that leaves keeps.
 */
function overriddenNames(repo, file, fn) {
  if (!fn.class) return [];
  const found = [];
  const seen = new Set();
  let context = { file, cls: file.classes.get(fn.class) };
  while (context && context.cls && !seen.has(context.cls.name)) {
    seen.add(context.cls.name);
    if (!context.cls.extends) break;
    const parent = classByName(repo, context.file, context.cls.extends);
    if (!parent) break;
    if (parent.cls.methods.has(fn.name)) {
      const declaration = `${parent.cls.name}.${fn.name}`;
      if (!found.includes(declaration)) found.push(declaration);
    }
    context = parent;
  }
  return found;
}

function methodOnClass(repo, file, className, method) {
  const local = file.classes.get(className);
  if (local && local.methods.has(method)) return local.methods.get(method);
  const imported = file.imports.get(className);
  if (imported) {
    const rel = repo.resolve(file.rel, imported.module);
    const other = rel && repo.files.get(rel);
    if (other) {
      const cls = other.classes.get(imported.name && imported.name !== "default" ? imported.name : className);
      if (cls && cls.methods.has(method)) return cls.methods.get(method);
      for (const candidate of other.classes.values()) {
        if (candidate.methods.has(method) && candidate.name === className) return candidate.methods.get(method);
      }
    }
  }
  return null;
}

function resolveCall(repo, file, fn, call) {
  const { name, receiver } = call;
  const hit = (target, confidence) =>
    target && target.id && target.id !== fn.id ? { kind: "call", to: target.id, line: call.line, confidence } : null;

  if (receiver === "this" && fn.class) {
    const cls = file.classes.get(fn.class);
    if (cls && cls.methods.has(name)) return hit(cls.methods.get(name), "exact");
    if (cls && cls.extends) {
      const inherited = methodOnClass(repo, file, cls.extends.split(".").pop(), name);
      if (inherited) return hit(inherited, "exact");
    }
  }

  if (!receiver) {
    const local = file.functions.filter((f) => f.name === name && !f.class);
    if (local.length === 1) return hit(local[0], "exact");
    const cls = file.classes.get(name);
    if (cls && cls.methods.has("constructor")) return hit(cls.methods.get("constructor"), "exact");
    const imported = file.imports.get(name);
    if (imported) {
      const rel = repo.resolve(file.rel, imported.module);
      if (rel) {
        const wanted = imported.name && imported.name !== "default" ? imported.name : name;
        const target = exportedFunctionIn(repo, rel, wanted) || exportedFunctionIn(repo, rel, name);
        if (target) return hit(target, "exact");
      } else {
        return { kind: "external", name: `${imported.module}.${name}`, module: imported.module };
      }
    }
    return byUniqueName(repo, fn, name, call, false);
  }

  const head = receiver.split(".")[0];
  const imported = file.imports.get(head);
  if (imported) {
    const rel = repo.resolve(file.rel, imported.module);
    if (rel) {
      const target = exportedFunctionIn(repo, rel, name);
      if (target) return hit(target, "exact");
      const viaClass = methodOnClass(repo, file, imported.name && imported.name !== "default" ? imported.name : head, name);
      if (viaClass) return hit(viaClass, "exact");
    } else {
      return { kind: "external", name: `${imported.module}.${name}`, module: imported.module };
    }
  }

  const varType = file.varTypes.get(receiver) || file.varTypes.get(head);
  if (varType) {
    const target = methodOnClass(repo, file, varType.type, name);
    if (target) return hit(target, varType.confidence);
  }

  const localClass = file.classes.get(head);
  if (localClass && localClass.methods.has(name)) return hit(localClass.methods.get(name), "exact");

  return byUniqueName(repo, fn, name, call, true);
}

function byUniqueName(repo, fn, name, call, hasReceiver) {
  if (hasReceiver && COMMON_METHODS.has(name)) return null;
  const candidates = (repo.byName.get(name) || []).filter((f) => f.id !== fn.id);
  if (!candidates.length) return null;
  if (candidates.length === 1) return { kind: "call", to: candidates[0].id, line: call.line, confidence: "heuristic" };
  return { kind: "ambiguous", candidates: candidates.slice(0, 8).map((c) => c.id) };
}

// --- component tree --------------------------------------------------------

/**
 * Fill each component's `children`, using whichever evidence its framework
 * leaves behind: an Angular selector in a template, a JSX tag resolved through
 * the file's imports, or a tag in a Vue or Svelte template.
 */
function linkComponents(repo) {
  const bySelector = new Map();
  const byName = new Map();
  for (const component of repo.components) {
    if (component.selector) bySelector.set(component.selector.replace(/[[\]]/g, ""), component);
    if (!byName.has(component.name)) byName.set(component.name, component);
  }

  for (const component of repo.components) {
    const file = repo.files.get(component.file);
    if (!file) continue;
    const children = new Set();

    if (component.framework === "angular") {
      let template = component.template || "";
      if (!template && component.templateFile) {
        const dir = component.file.includes("/") ? component.file.slice(0, component.file.lastIndexOf("/")) : "";
        const rel = path.posix.normalize(dir ? `${dir}/${component.templateFile}` : component.templateFile).replace(/^\.\//, "");
        try {
          template = fs.readFileSync(path.join(repo.root, rel), "utf8");
          component.templateResolved = rel;
        } catch {
          component.templateResolved = null;
        }
      }
      for (const tag of templateTags(template)) {
        const target = bySelector.get(tag);
        if (target && target.id !== component.id) children.add(target.id);
      }
    }

    for (const tag of component.tags || []) {
      const imported = file.imports.get(tag);
      if (imported) {
        const rel = repo.resolve(file.rel, imported.module);
        const target = rel && repo.components.find((c) => c.file === rel && (c.name === tag || c.name === (imported.name || tag)));
        if (target && target.id !== component.id) {
          children.add(target.id);
          continue;
        }
      }
      const sameFile = repo.components.find((c) => c.file === component.file && c.name === tag);
      if (sameFile && sameFile.id !== component.id) {
        children.add(sameFile.id);
        continue;
      }
      const known = byName.get(tag) || bySelector.get(tag);
      if (known && known.id !== component.id) children.add(known.id);
    }

    component.children = [...children].sort();
  }
}

// --- routes and entry points ----------------------------------------------

/** Return the routes this file declares, whichever router declares them. */
function collectRoutes(repo, file) {
  const routes = [];
  const { src, masked, rel } = file;
  const componentIn = (name) => {
    const imported = file.imports.get(name);
    if (imported) {
      const target = repo.resolve(rel, imported.module);
      if (target) {
        const found = repo.components.find((c) => c.file === target && (c.name === name || c.name === imported.name));
        if (found) return found;
      }
    }
    return (
      repo.components.find((c) => c.file === rel && c.name === name) ||
      repo.components.find((c) => c.name === name) ||
      null
    );
  };

  // React Router elements: <Route path="/x" element={<Home />} />
  const routeEl = /<\s*Route\b([\s\S]{0,400}?)\/?>/g;
  let m;
  while ((m = routeEl.exec(masked)) !== null) {
    const text = src.slice(m.index, m.index + m[0].length);
    const pathAttr = /path\s*=\s*["'{]?\s*["']?([^"'}\s]*)/.exec(text);
    const element = /(?:element\s*=\s*\{\s*<\s*([A-Z][\w$]*)|component\s*=\s*\{?\s*([A-Z][\w$]*))/.exec(text);
    if (!element) continue;
    const component = componentIn(element[1] || element[2]);
    if (component) {
      routes.push({ path: pathAttr ? pathAttr[1] || "/" : "/", component: component.id, router: "react-router", file: rel });
    }
  }

  // Object routes: { path: '/x', component: Home } — Vue Router and Angular.
  const objectRoute = /\{[^{}]*\bpath\s*:\s*(['"`])([\s\S]*?)\1[^{}]*\}/g;
  while ((m = objectRoute.exec(masked)) !== null) {
    const text = src.slice(m.index, m.index + m[0].length);
    const quoteStart = m.index + m[0].indexOf(m[1]);
    const routePath = src.slice(quoteStart + 1, quoteStart + 1 + Math.max(0, m[2].length));
    const named = /\b(?:component|loadComponent|element)\s*:\s*\(?\)?\s*=?>?\s*(?:import\(\s*['"`]([^'"`]+)['"`]\s*\)|<?\s*([A-Z][\w$]*))/.exec(text);
    if (!named) continue;
    if (named[1]) {
      const target = repo.resolve(rel, named[1]);
      const found = target && repo.components.find((c) => c.file === target);
      if (found) routes.push({ path: routePath, component: found.id, router: "lazy", file: rel });
      continue;
    }
    const component = componentIn(named[2]);
    if (component) routes.push({ path: routePath, component: component.id, router: "object", file: rel });
  }

  return routes;
}

/** Return file-system routes for Next.js and Nuxt style directories. */
function fileSystemRoutes(repo) {
  const routes = [];
  for (const rel of repo.files.keys()) {
    const m = /(?:^|\/)((?:src\/)?(?:app|pages))\/(.+)\.(tsx|jsx|ts|js|vue)$/.exec(rel);
    if (!m) continue;
    const tail = m[2];
    if (/^_/.test(path.basename(tail))) continue;
    if (/(^|\/)(layout|loading|error|not-found|middleware|template)$/.test(tail)) continue;
    if (m[1].endsWith("app") && !/(^|\/)page$/.test(tail)) continue;
    const routePath =
      "/" +
      tail
        .replace(/(^|\/)page$/, "")
        .replace(/(^|\/)index$/, "")
        .replace(/\[\.\.\.(\w+)\]/g, ":$1*")
        .replace(/\[(\w+)\]/g, ":$1")
        .replace(/^\/+|\/+$/g, "");
    const component = repo.components.find((c) => c.file === rel) || null;
    const file = repo.files.get(rel);
    const fallback = (file.functions.find((f) => f.exported) || file.functions[0]) || null;
    const target = component ? component.id : fallback ? fallback.id : null;
    if (target) routes.push({ path: routePath || "/", component: target, router: "file-system", file: rel });
  }
  return routes;
}

const HTTP_METHOD_DECORATORS = /^@(Get|Post|Put|Patch|Delete|Head|Options|All|Sse|MessagePattern|EventPattern|Cron|Subscribe)\b/;

/** Return every place execution can enter this repository from outside. */
function collectEntryPoints(repo) {
  const entries = new Map();
  const add = (id, name, file, line, kind, detail) => {
    if (!id || entries.has(id)) return;
    entries.set(id, { id, name, file, line, kind, detail });
  };

  for (const route of repo.routes) {
    const target = repo.byId.get(route.component) || repo.components.find((c) => c.id === route.component);
    if (target) add(route.component, target.name, target.file, target.line || 1, "route", `${route.router} ${route.path}`);
  }

  for (const file of repo.files.values()) {
    // Nest-style controllers: the decorator names the route.
    for (const fn of file.functions) {
      const decorator = (fn.decorators || []).find((d) => HTTP_METHOD_DECORATORS.test(d));
      if (decorator && fn.role !== "test") {
        const cls = fn.class && file.classes.get(fn.class);
        const controller = cls && cls.decorators.find((d) => /^@(Controller|Resolver|WebSocketGateway)\b/.test(d));
        const prefix = controller ? (/@\w+\(\s*['"`]([^'"`]*)/.exec(controller) || [])[1] || "" : "";
        add(
          fn.id,
          fn.name,
          file.rel,
          fn.line,
          "http-route",
          `${decorator.split("(")[0].slice(1)}${prefix ? " /" + prefix : ""}`
        );
      }
    }

    // Express, Koa and Fastify: `app.get("/x", handler)`.
    const routeCall = /\b([A-Za-z_$][\w$]*)\s*\.\s*(get|post|put|patch|delete|head|options|all|route)\s*\(\s*(['"`])/g;
    let m;
    while ((m = routeCall.exec(file.masked)) !== null) {
      if (!/^(app|router|server|api|route|fastify|express)$/i.test(m[1])) continue;
      const quote = m.index + m[0].length - 1;
      const end = file.masked.indexOf(m[3], quote + 1);
      if (end === -1) continue;
      const routePath = file.src.slice(quote + 1, end);
      const rest = file.masked.slice(end + 1, end + 200);
      const handler = /,\s*(?:async\s*)?([A-Za-z_$][\w$.]*)\s*[),]/.exec(rest);
      let target = null;
      if (handler) {
        const parts = handler[1].split(".");
        const wanted = parts[parts.length - 1];
        target = file.functions.find((f) => f.name === wanted && !f.class) || (repo.byName.get(wanted) || [])[0] || null;
      }
      if (!target) {
        target = file.functions.find((f) => m.index >= f.bodyStart && m.index < f.bodyEnd) || null;
      }
      if (target) add(target.id, target.name, file.rel, target.line, "http-route", `${m[2].toUpperCase()} ${routePath}`);
    }

    // Serverless and worker conventions.
    for (const fn of file.functions) {
      if (fn.class || fn.role === "test") continue;
      if (/^(handler|main|bootstrap|start|lambdaHandler)$/.test(fn.name) && fn.exported) {
        add(fn.id, fn.name, file.rel, fn.line, "main", "conventional entry name");
      }
    }

    // Where a front-end application is mounted.
    const mount = /(?:createRoot\s*\([\s\S]{0,80}?\)\s*\.\s*render|ReactDOM\s*\.\s*render|createApp|bootstrapApplication)\s*\(\s*<?\s*([A-Z][\w$]*)/.exec(file.masked);
    if (mount) {
      const component = repo.components.find((c) => c.name === mount[1]);
      if (component) add(component.id, component.name, component.file, component.line, "app-root", `mounted in ${file.rel}`);
    }
  }

  // package.json bin and main.
  const pkg = repo.frameworks.pkg || {};
  const targets = [];
  if (typeof pkg.main === "string") targets.push(pkg.main);
  if (typeof pkg.bin === "string") targets.push(pkg.bin);
  else if (pkg.bin && typeof pkg.bin === "object") targets.push(...Object.values(pkg.bin));
  for (const target of targets) {
    const rel = path.posix.normalize(String(target).replace(/^\.\//, ""));
    const file = repo.files.get(rel);
    if (!file) continue;
    const fn = file.functions.find((f) => /^(main|run|start|cli)$/.test(f.name)) || file.functions.find((f) => f.exported);
    if (fn) add(fn.id, fn.name, file.rel, fn.line, "cli-command", `package.json ${target}`);
  }

  return [...entries.values()].sort((a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
}

// --- output ----------------------------------------------------------------

function snippetFor(file, fn, detail) {
  if (detail === "thin") return null;
  const lines = file.src.split("\n");
  let body = lines.slice(fn.line - 1, fn.endLine).join("\n");
  if (detail === "standard") {
    if (fn.endLine - fn.line + 1 <= 3) return null;
    body = body.split("\n").slice(0, 20).join("\n");
  }
  return body.replace(/<\//g, "<\\/");
}

function buildOutput(repo, detail) {
  const functions = [];
  for (const file of repo.files.values()) {
    for (const fn of file.functions) {
      const record = {
        id: fn.id,
        name: fn.name,
        qualname: fn.class ? `${fn.class}.${fn.name}` : fn.name,
        file: file.rel,
        line: fn.line,
        loc: Math.max(1, fn.endLine - fn.line + 1),
        nesting: maxControlNesting(file.masked, fn.bodyStart, fn.bodyEnd),
        signature: fn.signature,
        purpose: fn.purpose || "",
        role: fn.role,
        exported: fn.exported,
        async: !!fn.async,
        io: !!fn.io,
        decorators: fn.decorators || [],
        calls: fn.calls || [],
      };
      if (fn.class) record.owner = fn.class;
      const overrides = overriddenNames(repo, file, fn);
      if (overrides.length) record.overrides = overrides;
      if (fn.componentId) record.component = fn.componentId;
      const snippet = snippetFor(file, fn, detail);
      if (snippet !== null) record.snippet = snippet;
      functions.push(record);
    }
  }
  functions.sort((a, b) => (a.file === b.file ? a.line - b.line : a.file < b.file ? -1 : 1));

  const called = new Set();
  for (const fn of functions) for (const call of fn.calls) called.add(call.to);

  const skipCounts = {};
  for (const item of repo.skipped) skipCounts[item.reason] = (skipCounts[item.reason] || 0) + 1;

  return {
    schema: TRACER_SCHEMA,
    tracer: "typescript",
    language: "typescript",
    idRule: "code-flow/v1",
    root: repo.root.split(path.sep).join("/"),
    detail,
    frameworks: { frontend: repo.frameworks.frontend, backend: repo.frameworks.backend },
    files: repo.census,
    skipped: repo.skipped,
    functions,
    components: repo.components.map((component) => {
      const copy = { ...component };
      delete copy.tags;
      delete copy.template;
      return copy;
    }),
    routes: repo.routes,
    entryPoints: repo.entryPoints,
    ambiguousCalls: repo.ambiguous.sort((a, b) => (a.from === b.from ? a.line - b.line : a.from < b.from ? -1 : 1)),
    externalCalls: [...repo.external.values()].sort((a, b) => (a.name < b.name ? -1 : 1)),
    stats: {
      filesScanned: repo.census.length,
      filesSkipped: repo.skipped.length,
      skipReason: skipCounts,
      functionsFound: functions.length,
      callEdges: functions.reduce((sum, f) => sum + f.calls.length, 0),
      ambiguousCalls: repo.ambiguous.length,
      externalCalls: repo.external.size,
      entryPointsFound: repo.entryPoints.length,
      componentsFound: repo.components.length,
      routesFound: repo.routes.length,
      unreachedCandidates: functions.filter((f) => !called.has(f.id)).length,
    },
    limits: [
      "Static analysis only: dynamic imports built from variables, dependency injection by " +
        "string token, registry lookups and configuration-declared routes are invisible to it.",
      "Calls resolved by unique name carry confidence 'heuristic'; ambiguous ones are listed " +
        "in ambiguousCalls rather than guessed into edges.",
      "Components are recognized per framework by declaration shape; one produced by a factory " +
        "or a higher-order component may be missed.",
      "`overrides` names only a declaration this repository defines: a method that overrides " +
        "one from a dependency, a framework base class or the standard library carries nothing.",
      "`overrides` follows `extends` only. An interface declares no bodies, so a class that " +
        "implements one carries nothing for the members it satisfies.",
    ],
  };
}

// --- driver ----------------------------------------------------------------

export function trace(rootDir, detail) {
  const root = path.resolve(rootDir);
  const listing = gitTrackedFiles(root) || walkFiles(root);
  const relevant = [];
  const skipped = [];
  for (const rel of listing.sort()) {
    if (!SOURCE_EXT.has(path.extname(rel).toLowerCase())) continue;
    const reason = skipReason(rel);
    if (reason) {
      skipped.push({ path: rel, reason });
      continue;
    }
    relevant.push(rel);
  }

  const frameworks = detectFrameworks(root, relevant);
  const aliases = loadPathAliases(root);
  const resolve = makeResolver(new Set(relevant), aliases);

  const repo = {
    root,
    files: new Map(),
    census: [],
    skipped,
    components: [],
    routes: [],
    entryPoints: [],
    byId: new Map(),
    byName: new Map(),
    ambiguous: [],
    external: new Map(),
    frameworks,
    resolve,
  };

  for (const rel of relevant) {
    const abs = path.join(root, rel.split("/").join(path.sep));
    let src;
    try {
      src = fs.readFileSync(abs, "utf8");
    } catch {
      skipped.push({ path: rel, reason: "unparsed" });
      continue;
    }
    if (src.includes("\u0000")) {
      skipped.push({ path: rel, reason: "binary" });
      continue;
    }
    let masked = maskSource(src);
    let template = "";
    const ext = path.extname(rel).toLowerCase();
    if (ext === ".vue" || ext === ".svelte") {
      const split = splitSingleFileComponent(src, masked);
      masked = split.masked;
      template = split.template;
    }
    const lineStarts = lineStartsOf(src);
    const { functions, classes } = collectFunctions(rel, src, masked, lineStarts);
    const { imports } = collectImports(src, masked);
    const isTest = isTestPath(rel);

    for (const fn of functions) {
      fn.role = isTest ? "test" : "source";
      fn.purpose = docCommentFor(src, fn);
    }

    collectCallSites(rel, src, masked, lineStarts, functions);
    repo.files.set(rel, {
      rel,
      src,
      masked,
      lineStarts,
      functions,
      classes,
      imports,
      template,
      varTypes: collectVarTypes(src, masked, classes),
    });
    let size = 0;
    try {
      size = fs.statSync(abs).size;
    } catch {
      size = 0;
    }
    repo.census.push({ path: rel, size, hash: fileHash(abs) });
  }

  // Ids last, and for every file at once: two of the three collision suffixes
  // are decided inside one file, but the third compares one file's path against
  // every other's, so nothing can be indexed by id until the walk is over.
  const catalogued = [...repo.files.values()].flatMap((file) => file.functions);
  assignIds(catalogued);
  for (const fn of catalogued) {
    repo.byId.set(fn.id, fn);
    if (!repo.byName.has(fn.name)) repo.byName.set(fn.name, []);
    repo.byName.get(fn.name).push(fn);
  }

  resolveAllCalls(repo);

  for (const file of repo.files.values()) {
    for (const component of collectComponents(file, frameworks.frontend)) {
      repo.components.push(component);
      for (const memberId of component.members || []) {
        const fn = repo.byId.get(memberId);
        if (fn && !fn.componentId) fn.componentId = component.id;
      }
    }
  }
  linkComponents(repo);

  for (const file of repo.files.values()) repo.routes.push(...collectRoutes(repo, file));
  repo.routes.push(...fileSystemRoutes(repo));
  const seenRoutes = new Set();
  repo.routes = repo.routes.filter((route) => {
    const key = `${route.file}|${route.path}|${route.component}`;
    if (seenRoutes.has(key)) return false;
    seenRoutes.add(key);
    return true;
  });

  repo.entryPoints = collectEntryPoints(repo);
  return buildOutput(repo, detail);
}

/**
 * Return the first line of the JSDoc block immediately above a function.
 *
 * Anchored from the end backwards, never by a non-greedy match forwards: a
 * forward match starts at the *first* `/**` in the window, which on a file of
 * documented functions is the previous function's comment, and every function
 * would inherit its neighbour's description.
 */
function docCommentFor(src, fn) {
  const head = src.slice(Math.max(0, fn.start - 800), fn.start).replace(/\s+$/, "");
  if (!head.endsWith("*/")) return "";
  const open = head.lastIndexOf("/**");
  if (open === -1) return "";
  const lines = head
    .slice(open + 3, head.length - 2)
    .split("\n")
    .map((line) => line.replace(/^\s*\*?\s?/, "").trim())
    .filter(Boolean);
  return lines.length && !lines[0].startsWith("@") ? lines[0] : "";
}

function parseArgs(argv) {
  const args = { root: ".", out: null, detail: "standard", help: false };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--root") args.root = argv[++i];
    else if (argv[i] === "--out") args.out = argv[++i];
    else if (argv[i] === "--detail") args.detail = argv[++i];
    else if (argv[i] === "--help" || argv[i] === "-h") args.help = true;
  }
  return args;
}

const invokedDirectly =
  process.argv[1] && import.meta.url.endsWith(path.basename(process.argv[1]));
if (invokedDirectly) {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    process.stdout.write(
      "Static call-graph and component tracer for TypeScript/JavaScript (code-flow).\n\n" +
        "  node trace_typescript.mjs [--root DIR] [--out FILE] [--detail thin|standard|verbose]\n"
    );
    process.exit(0);
  }
  if (!["thin", "standard", "verbose"].includes(args.detail)) {
    process.stderr.write(`unknown --detail ${args.detail}; using standard\n`);
    args.detail = "standard";
  }
  const result = trace(args.root, args.detail);
  const text = JSON.stringify(result, null, 2);
  if (args.out) {
    fs.mkdirSync(path.dirname(path.resolve(args.out)), { recursive: true });
    fs.writeFileSync(args.out, text + "\n");
    const s = result.stats;
    process.stderr.write(
      `traced ${s.filesScanned} files, ${s.functionsFound} functions, ${s.callEdges} call edges, ` +
        `${s.componentsFound} components, ${s.entryPointsFound} entry points -> ${args.out}\n`
    );
  } else {
    process.stdout.write(text + "\n");
  }
}
