#!/usr/bin/env python3
"""Tests for scripts/check-examples.py."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tests._support import REPO_ROOT, load_script, write

SCRIPT = REPO_ROOT / "scripts" / "check-examples.py"
HAS_CARGO = shutil.which("cargo") is not None

ce = load_script("check-examples.py")

README = """\
# Demo

```rust
pub fn double(x: u32) -> u32 {
    x * 2
}
```

```bash
cargo test
```

- A list item with an indented example:

  ```rust
  let y = double(2);
  ```

~~~markdown
```rust
<a template placeholder, not real code>
```
~~~
"""


class RepoTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        write(self.root / "README.md", README)

    def tearDown(self):
        self._tmp.cleanup()

    def blocks(self):
        return ce.find_blocks(self.root, self.root / "README.md")

    def harness(self, data):
        write(self.root / "scripts" / "examples.json", json.dumps(data))


class FindBlocksTest(RepoTest):
    def test_finds_rust_blocks_only(self):
        blocks = self.blocks()
        self.assertEqual([b.index for b in blocks], [1, 2])
        self.assertEqual(blocks[0].line, 4)
        self.assertIn("pub fn double", blocks[0].code)

    def test_dedents_indented_blocks(self):
        self.assertEqual(self.blocks()[1].code, "let y = double(2);")

    def test_ignores_rust_fences_nested_in_other_blocks(self):
        codes = " ".join(b.code for b in self.blocks())
        self.assertNotIn("template placeholder", codes)

    def test_skips_eval_fixtures(self):
        write(self.root / "skills" / "demo" / "SKILL.md", "```rust\nfn a() {}\n```\n")
        write(self.root / "skills" / "demo" / "evals" / "case" / "prompt.md", "```rust\nbroken\n```\n")
        names = [p.relative_to(self.root).as_posix() for p in ce.doc_files(self.root)]
        self.assertIn("skills/demo/SKILL.md", names)
        self.assertNotIn("skills/demo/evals/case/prompt.md", names)


class NormalizeTest(unittest.TestCase):
    def test_placeholder_function_body_becomes_todo(self):
        code = "fn f(x: u8) -> bool { /* ... */ }"
        self.assertEqual(ce.normalize(code), "fn f(x: u8) -> bool { todo!() }")

    def test_placeholder_trait_and_struct_bodies_are_left_alone(self):
        code = "pub trait T: Sealed { /* ... */ }\npub struct S { /* ... */ }"
        self.assertEqual(ce.normalize(code), code)


class HarnessTest(RepoTest):
    def apply(self, data):
        blocks = self.blocks()
        problems = ce.apply_harness(self.root, blocks, data)
        return blocks, problems

    def test_template_and_prelude_are_attached(self):
        blocks, problems = self.apply({"files": {"README.md": {
            "prelude": "use std::fmt;",
            "blocks": {"2": {"first_line": "let y = double(2);",
                             "template": ["fn wrap() {", "{code}", "}"]}},
        }}})
        self.assertEqual(problems, [])
        self.assertEqual(blocks[0].prelude, "use std::fmt;")
        self.assertEqual(blocks[1].template, "fn wrap() {\n{code}\n}")

    def test_first_line_mismatch_reports_drift_at_the_block(self):
        blocks, problems = self.apply({"files": {"README.md": {
            "blocks": {"2": {"first_line": "let z = 3;", "template": "{code}"}},
        }}})
        self.assertEqual(len(problems), 1)
        self.assertEqual((problems[0].path, problems[0].line), ("README.md", 16))
        self.assertIn("update the harness", problems[0].message)
        self.assertIsNotNone(blocks[1].skip)

    def test_skip_needs_a_reason(self):
        blocks, problems = self.apply({"files": {"README.md": {
            "blocks": {"2": {"first_line": "let y = double(2);", "skip": ""}},
        }}})
        self.assertEqual(len(problems), 1)
        self.assertIn("skip needs a reason", problems[0].message)

    def test_skip_with_reason_is_not_an_error(self):
        blocks, problems = self.apply({"files": {"README.md": {
            "blocks": {"2": {"first_line": "let y = double(2);", "skip": "a fragment"}},
        }}})
        self.assertEqual(problems, [])
        self.assertEqual(blocks[1].skip, "a fragment")

    def test_unknown_block_and_file_are_errors(self):
        _, problems = self.apply({"files": {
            "README.md": {"blocks": {"9": {"first_line": "x"}}},
            "missing.md": {"blocks": {}},
        }})
        messages = " ".join(p.message for p in problems)
        self.assertIn("no rust block #9", messages)
        self.assertIn("missing.md", messages)

    def test_template_without_code_slot_is_an_error(self):
        _, problems = self.apply({"files": {"README.md": {
            "blocks": {"1": {"first_line": "pub fn double(x: u32) -> u32 {", "template": "fn f() {}"}},
        }}})
        self.assertIn("has no {code}", problems[0].message)


class MappingTest(RepoTest):
    def test_rendered_lines_map_back_to_markdown_and_harness(self):
        block = self.blocks()[1]
        block.template = "fn wrap() {\n{code}\n}"
        source = ce.render(block, "scripts/examples.json").split("\n")
        code_line = source.index("let y = double(2);") + 1
        self.assertEqual(block.lines[code_line], ("README.md", 16))
        self.assertEqual(block.lines[code_line - 1][0], "scripts/examples.json")

    def test_cargo_errors_map_to_markdown_lines(self):
        block = self.blocks()[0]
        ce.render(block, "scripts/examples.json")
        modules = {"src/ex_001.rs": block}
        message = {
            "reason": "compiler-message",
            "message": {
                "level": "error",
                "message": "mismatched types",
                "code": {"code": "E0308"},
                "spans": [{"file_name": "src/ex_001.rs", "line_start": 3, "is_primary": True}],
            },
        }
        warning = {"reason": "compiler-message", "message": {"level": "warning", "message": "unused", "spans": []}}
        output = "\n".join([json.dumps(message), json.dumps(warning), "not json"])
        problems = ce.map_errors(output, modules)
        self.assertEqual(len(problems), 1)
        self.assertEqual((problems[0].path, problems[0].line), ("README.md", 5))
        self.assertEqual(problems[0].message, "mismatched types [E0308]")


@unittest.skipUnless(HAS_CARGO, "cargo is not installed")
class EndToEndTest(RepoTest):
    def test_a_broken_example_reports_its_markdown_line(self):
        write(self.root / "README.md", "# Demo\n\n```rust\nfn f() -> u32 {\n    \"not a number\"\n}\n```\n")
        problems, compiled, skipped = ce.check_repo(self.root)
        self.assertEqual((compiled, skipped), (1, 0))
        self.assertEqual(len(problems), 1)
        self.assertEqual((problems[0].path, problems[0].line), ("README.md", 5))

    def test_a_fragment_compiles_with_its_template(self):
        # Each block is its own module, so block 2 cannot call block 1's double().
        write(self.root / "README.md", README.replace("let y = double(2);", "let y = 2 * 2;"))
        self.harness({"files": {"README.md": {"blocks": {
            "2": {"first_line": "let y = 2 * 2;", "template": ["fn wrap() {", "{code}", "}"]},
        }}}})
        problems, compiled, skipped = ce.check_repo(self.root)
        self.assertEqual(problems, [])
        self.assertEqual((compiled, skipped), (2, 0))


if __name__ == "__main__":
    unittest.main()
