import json, sys
from pathlib import Path
B = Path(sys.argv[1]); key = json.loads((B / "key.json").read_text())
cfgs = ["claude-without", "claude-with", "codex-without", "codex-with"]
rows = {}; detail = {}
for g in sorted((B / "grading").glob("*/grading-run-*.json")):
    case = g.parent.name; run = g.stem.replace("grading-", "")
    cfg = key[f"{case}/{run}"]
    res = json.loads(g.read_text())["results"]
    rows.setdefault(case, {})[cfg] = (sum(r["passed"] for r in res), len(res))
    detail.setdefault(case, {})[cfg] = [r["grader"] for r in res if not r["passed"]]
print("case".ljust(28), *[c.ljust(15) for c in cfgs])
tot = {c: [0, 0] for c in cfgs}
for case, r in rows.items():
    print(case.ljust(28), *[(f"{r[c][0]}/{r[c][1]}" if c in r else "-").ljust(15) for c in cfgs])
    for c in cfgs:
        if c in r: tot[c][0] += r[c][0]; tot[c][1] += r[c][1]
print("TOTAL".ljust(28), *[f"{t[0]}/{t[1]}".ljust(15) for t in tot.values()])
print(json.dumps(detail, indent=1))
