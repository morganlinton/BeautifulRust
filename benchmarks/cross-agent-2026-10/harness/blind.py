"""Copy each run into grading/<case>/run-N without skills, git, or build output, and keep the key."""
import json, random, shutil, subprocess, sys
from pathlib import Path
B = Path(sys.argv[1]); REPO = Path(sys.argv[2]); ONLY = set(sys.argv[3:])
rng = random.Random(20261026)

kp = B / "key.json"
key = json.loads(kp.read_text()) if kp.exists() else {}
for case_dir in sorted((B / "runs").iterdir()):
    if ONLY and case_dir.name not in ONLY: continue
    cfgs = sorted(p.name for p in case_dir.iterdir())
    random.Random(case_dir.name).shuffle(cfgs)
    out = B / "grading" / case_dir.name
    if out.exists(): shutil.rmtree(out)
    out.mkdir(parents=True)
    for i, cfg in enumerate(cfgs, 1):
        src = case_dir / cfg; dst = out / f"run-{i}"
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".agents", ".git", "target"))
        diff = subprocess.run(["git", "diff", "HEAD", "--stat", "--", ".", ":!.agents", ":!target"], cwd=src, capture_output=True, text=True).stdout
        untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard", "--", ".", ":!target"], cwd=src, capture_output=True, text=True).stdout
        (out / f"run-{i}.changes.txt").write_text("Tracked files changed vs the original:\n" + (diff or "(none)\n") + "\nNew files:\n" + (untracked or "(none)\n"))
        key[f"{case_dir.name}/run-{i}"] = cfg
    eval_dir = next(REPO.glob(f"skills/*/evals/{case_dir.name}"))
    shutil.copytree(eval_dir / "graders", out / "graders")
    (out / "expected_outcome.txt").write_text(eval_dir.joinpath("case.yaml").read_text())
    (out / "task.txt").write_text(eval_dir.joinpath("prompt.md").read_text().split("---", 2)[2].strip() + "\n")
    orig = out / "original"; orig.mkdir()
    if (eval_dir / "files").exists():
        shutil.copytree(eval_dir / "files", orig, dirs_exist_ok=True)
(B / "key.json").write_text(json.dumps(key, indent=1))
print("blinded", len(key))
