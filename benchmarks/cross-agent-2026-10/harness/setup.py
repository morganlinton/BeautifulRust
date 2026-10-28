import os, subprocess, shutil, sys
from pathlib import Path
B = Path(sys.argv[1]); REPO = Path(sys.argv[2])
WITH = """Skills for this task are in ./.agents/skills/ (rust-best-practices, rust-review, and rust-port). Before you start, read the SKILL.md of each one that applies to this task, and follow it. Read its references/ files when the SKILL.md tells you to.

"""
ENV = """Work only inside the current directory. Rust stable 1.99 is installed; if cargo isn't on PATH, run export PATH="$HOME/.rustup/toolchains/stable-aarch64-apple-darwin/bin:$PATH" first. crates.io is reachable.

Task:
"""
cases = sorted(REPO.glob("skills/*/evals/*/prompt.md"))
for p in cases:
    case = p.parent
    body = p.read_text().split("---", 2)[2].strip()
    for agent in ("claude", "codex"):
        for cond in ("with", "without"):
            ws = B / "runs" / case.name / f"{agent}-{cond}"
            ws.mkdir(parents=True)
            subprocess.run(["git", "init", "-q"], cwd=ws, check=True)
            if (case / "place-files.sh").exists():
                subprocess.run(["bash", str(case / "place-files.sh")], cwd=ws, check=True)
            if cond == "with":
                shutil.copytree(B / "skills", ws / ".agents" / "skills")
            subprocess.run(["git", "add", "-A"], cwd=ws, check=True)
            subprocess.run(["git", "-c", "user.name=bench", "-c", "user.email=bench@example.invalid",
                            "commit", "-q", "--allow-empty", "-m", "initial"], cwd=ws, check=True)
            (B / "prompts" / f"{case.name}--{agent}-{cond}.txt").write_text((WITH if cond == "with" else "") + ENV + body + "\n")
print(len(cases), "cases")
