import json, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
B = Path(sys.argv[1]); PAR = int(sys.argv[2]) if len(sys.argv) > 2 else 4
env = dict(os.environ)
env["PATH"] = str(Path.home() / ".rustup/toolchains/stable-aarch64-apple-darwin/bin") + ":" + env["PATH"]
jobs = sorted(p for p in (B / "prompts").glob("*--codex-*.txt"))
def run(p):
    name = p.stem
    case, cfg = name.split("--")
    ws = B / "runs" / case / cfg
    log = B / "logs" / name; log.mkdir(parents=True, exist_ok=True)
    cmd = ["codex", "exec", "-C", str(ws), "--sandbox", "workspace-write",
           "--add-dir", str(Path.home() / ".cargo"),
           "-c", "sandbox_workspace_write.network_access=true",
           "--ephemeral", "--json", "-o", str(log / "last.md"), p.read_text()]
    t = time.time()
    with open(log / "events.jsonl", "w") as out, open(log / "stderr.txt", "w") as err:
        try:
            rc = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=out, stderr=err, env=env, timeout=2400).returncode
        except subprocess.TimeoutExpired:
            rc = "timeout"
    (log / "meta.json").write_text(json.dumps({"rc": rc, "seconds": round(time.time() - t)}))
    print(name, rc, round(time.time() - t), flush=True)
with ThreadPoolExecutor(PAR) as ex:
    list(ex.map(run, jobs))
print("ALL DONE")
