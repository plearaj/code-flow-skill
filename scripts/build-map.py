"""Rebuild this repository's own code-flow map from the five shipped tracers.

`/code-flow.map --whole-code-base` is a prompt: a host reads it and does the work.
That makes dogfooding awkward, because "run the map over this repo" is then a
judgement call somebody makes in a session and cannot repeat. This script is the
mechanical half of that prompt — run every tracer, merge the catalogs into one
inventory, walk the resolved call graph out from each entry point — so a run can
be reproduced and two runs can be diffed.

It is a development tool, not part of either shipped package. What it deliberately
does *not* do is the reading: the quality command's step 4b verification is a
judgement the source has to settle, and nothing here substitutes for it.

    python3 scripts/build-map.py --out build/map

Usage:
  --root DIR   repository to trace (default: this repository)
  --out  DIR   where to write `Code_Flows/` (default: `<root>/Code_Flows`)
"""
import argparse, json, subprocess, sys, datetime, pathlib, collections

REPO = pathlib.Path(__file__).resolve().parent.parent

parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
parser.add_argument("--root", type=pathlib.Path, default=REPO)
parser.add_argument("--out", type=pathlib.Path, default=None)
args = parser.parse_args()

ROOT = args.root.resolve()
OUT = ((args.out or ROOT) / "Code_Flows").resolve()
OUT.mkdir(parents=True, exist_ok=True)
T = REPO / "templates" / "shared" / "tracers"

# The four Python tracers run under the interpreter running this script; the
# TypeScript one needs node. A tracer whose interpreter is missing is skipped
# with a line saying so rather than failing the run -- the same `--tracer auto`
# behaviour the map command describes.
TRACERS = [
    ([sys.executable, str(T / "trace_python.py")], "python"),
    (["node", str(T / "trace_typescript.mjs")], "typescript"),
    ([sys.executable, str(T / "trace_rust.py")], "rust"),
    ([sys.executable, str(T / "trace_java.py")], "java"),
    ([sys.executable, str(T / "trace_c_family.py")], "c-family"),
]

functions, components, files, skipped, entry_points = [], [], [], [], []
for cmd, lang in TRACERS:
    try:
        r = subprocess.run(cmd + ["--root", str(ROOT), "--detail", "standard"],
                           capture_output=True, text=True)
    except FileNotFoundError:
        print(f"  {lang:<11} skipped — {cmd[0]} is not on this machine", file=sys.stderr)
        continue
    if r.returncode != 0:
        print(f"  {lang}: FAILED\n{r.stderr[:600]}", file=sys.stderr)
        continue
    d = json.loads(r.stdout)
    functions += d["functions"]
    components += d.get("components", [])
    files += d.get("files", [])
    skipped += d.get("skipped", [])
    entry_points += d.get("entryPoints", [])
    print(f"  {lang:<11} {len(d['functions']):>4} functions, {len(d.get('entryPoints',[])):>2} entry points")

by_id = {f["id"]: f for f in functions}
assert len(by_id) == len(functions), "duplicate ids across tracers"

(OUT / "inventory.json").write_text(
    json.dumps({"schema": 1, "functions": functions, "components": components},
               indent=2, ensure_ascii=False), encoding="utf-8")

# --- flows: walk the resolved call graph out from each entry point ---------
# Edges the tracers are right to refuse, added back by reading. Every tracer's
# `main()` ends in `common.run_cli(prog, description, trace, argv)`, where `trace`
# is a *parameter* -- so the call the graph can see is `main -> run_cli`, and
# which of the five `trace` functions run_cli invokes is not something a static
# reader can know. Left alone, each tracer's entire body is unreachable from its
# own entry point. This is exactly the case `/code-flow.map` hands to a host to
# settle by reading, and the label records that these came from reading rather
# than from resolution.
EXTRA_EDGES = {
    f"templates_shared_tracers_{name}_main": [f"templates_shared_tracers_{name}_trace"]
    for name in ("trace_python", "trace_rust", "trace_java", "trace_c_family")
}

adjacency = collections.defaultdict(list)
for f in functions:
    for c in f.get("calls", []):
        adjacency[f["id"]].append(c)
for src, dsts in EXTRA_EDGES.items():
    for dst in dsts:
        if not any(c["to"] == dst for c in adjacency[src]):
            adjacency[src].append({"to": dst, "confidence": "read", "line": None})

def build_flow(entry_id):
    seen, order, edges = {entry_id}, [entry_id], []
    depth = {entry_id: 0}
    queue = [entry_id]
    while queue:
        cur = queue.pop(0)
        for call in adjacency.get(cur, []):
            to = call["to"]
            edges.append({"back": to in seen and depth.get(to, 0) <= depth.get(cur, 0),
                          "from": cur, "kind": "call", "label": "", "to": to})
            if to in seen:
                continue
            seen.add(to)
            depth[to] = depth[cur] + 1
            # An external call is a node too: it is where execution leaves this
            # repository, and it carries fan-out for the caller. It is never
            # walked past -- there is nothing catalogued on the other side.
            order.append(to)
            if to in by_id:
                queue.append(to)
    nodes = []
    for nid in order:
        fn = by_id.get(nid)
        if fn is None:
            nodes.append({"id": nid, "label": nid.replace("external_", "") + "()",
                          "file": "", "line": None, "kind": "external",
                          "description": "leaves this repository", "snippet": "",
                          "depth": depth[nid]})
            continue
        nodes.append({"id": nid, "label": fn["name"] + "()", "file": fn["file"],
                      "line": fn["line"], "kind": "entry" if nid == entry_id else fn.get("role", "source"),
                      "description": fn.get("purpose") or fn.get("signature", ""),
                      "snippet": fn.get("snippet", ""), "depth": depth[nid]})
    # dedupe edges, keep only those whose source is a real node
    ids = {n["id"] for n in nodes}
    uniq, seen_e = [], set()
    for e in edges:
        k = (e["from"], e["to"])
        if e["from"] in ids and k not in seen_e:
            seen_e.add(k); uniq.append(e)
    return nodes, uniq, depth

EXTRA_ENTRIES = ["templates_shared_tracers_trace_typescript_trace"]
have = {ep["id"] if isinstance(ep, dict) else ep for ep in entry_points}
for extra in EXTRA_ENTRIES:
    if extra in by_id and extra not in have:
        entry_points.append({"id": extra, "kind": "cli-command"})

flows = []
for ep in entry_points:
    eid = ep["id"] if isinstance(ep, dict) else ep
    if eid not in by_id:
        continue
    nodes, edges, depth = build_flow(eid)
    fn = by_id[eid]
    slug = eid
    (OUT / f"{slug}.json").write_text(json.dumps({
        "meta": {"slug": slug, "title": f"{fn['name']} — {(ep.get('kind') if isinstance(ep, dict) else '') or 'entry'}",
                 "entry": eid, "root": str(ROOT), "schema": 1},
        "nodes": nodes, "edges": edges}, indent=2, ensure_ascii=False), encoding="utf-8")
    flows.append({"slug": slug, "title": f"{fn['name']} — {(ep.get('kind') if isinstance(ep, dict) else '') or 'entry'}",
                  "file": f"{slug}.json", "entry": eid, "nodes": len(nodes)})

(OUT / "index.json").write_text(json.dumps({
    "meta": {"root": str(ROOT), "generated": datetime.date.today().isoformat(),
             "mode": "whole-code-base", "detail": "standard", "schema": 1},
    "coverage": {"filesScanned": len(files), "filesSkipped": len(skipped), "skipReason": {},
                 "functionsCatalogued": len(functions), "flowsTraced": len(flows),
                 "entryPointsFound": len(entry_points)},
    "files": files, "flows": flows}, indent=2, ensure_ascii=False), encoding="utf-8")

reached = set()
for fl in flows:
    reached |= {n["id"] for n in json.loads((OUT / fl["file"]).read_text())["nodes"]}
print(f"\n{len(functions)} functions, {len(flows)} flows, {len(reached)} reached")
