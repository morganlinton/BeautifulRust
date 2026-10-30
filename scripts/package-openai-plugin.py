#!/usr/bin/env python3
"""Build the ZIP uploaded to the ChatGPT / Codex Plugins Directory.

The package holds the portable plugin.json, the skills and their references,
the icon, and the license. Eval cases stay out: they are test fixtures with
planted bugs, not instructions for the agent. The ZIP is reproducible, so the
same commit always builds the same bytes.

Stdlib only, Python 3.9+.
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path
from typing import List, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
TOP_LEVEL = ("plugin.json", "LICENSE", "PRIVACY.md")
EXCLUDED_DIRS = {"evals", "__pycache__"}
EXCLUDED_NAMES = {".DS_Store"}
# 1980-01-01, the earliest timestamp a ZIP entry can hold.
FIXED_TIME = (1980, 1, 1, 0, 0, 0)


def package_files(root: Path) -> List[Path]:
    """Files to package, relative to root, in a stable order."""
    manifest = json.loads((root / "plugin.json").read_text(encoding="utf-8"))
    interface = manifest["extensions"]["com.openai"]["interface"]
    files = {Path(name) for name in TOP_LEVEL}
    for key in ("composerIcon", "logo", "composerIconDark", "logoDark"):
        if key in interface:
            files.add(Path(interface[key]))
    for path in (root / "skills").rglob("*"):
        relative = path.relative_to(root)
        if path.is_dir() or path.name in EXCLUDED_NAMES:
            continue
        if EXCLUDED_DIRS.intersection(relative.parts):
            continue
        files.add(relative)
    missing = [str(f) for f in files if not (root / f).is_file()]
    if missing:
        raise FileNotFoundError("missing: %s" % ", ".join(sorted(missing)))
    return sorted(files, key=lambda f: f.as_posix())


def build(root: Path, out: Path) -> List[Path]:
    files = package_files(root)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for relative in files:
            info = zipfile.ZipInfo(relative.as_posix(), FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, (root / relative).read_bytes())
    return files


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root", type=Path, default=REPO_ROOT, help="repository root"
    )
    parser.add_argument(
        "--out",
        type=Path,
        help="output ZIP (default: dist/<name>-<version>.zip under the root)",
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    manifest = json.loads((root / "plugin.json").read_text(encoding="utf-8"))
    out = args.out or root / "dist" / (
        "%s-%s.zip" % (manifest["name"], manifest["version"])
    )
    try:
        files = build(root, out)
    except (FileNotFoundError, KeyError) as exc:
        print("package-openai-plugin: %s" % exc, file=sys.stderr)
        return 1
    print("Wrote %s (%d files)" % (out, len(files)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
