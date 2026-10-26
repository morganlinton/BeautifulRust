import unittest

from taskgraph import (
    CycleError, MissingDependency, ParseError, TaskError, execution_order,
    parse_tasks, summarize,
)

SAMPLE = """
# a small pipeline
compile: build [p=5]
lint: test
unit: test [p=2] <- compile
docs: build
ship: deploy <- unit, lint, docs
"""


class ParseTests(unittest.TestCase):
    def test_parses_fields(self):
        tasks = parse_tasks(SAMPLE)
        self.assertEqual(list(tasks), ["compile", "lint", "unit", "docs", "ship"])
        self.assertEqual(tasks["unit"].kind, "test")
        self.assertEqual(tasks["unit"].priority, 2)
        self.assertEqual(tasks["ship"].deps, ["unit", "lint", "docs"])
        self.assertIsNone(tasks["lint"].priority)

    def test_negative_priority(self):
        self.assertEqual(parse_tasks("a: build [p=-3]")["a"].priority, -3)

    def test_parse_errors_report_line(self):
        cases = {
            "a: build\nnope": 2,
            "a: compile": 1,
            "a: build\na: test": 2,
            "a b: build": 1,
            "a: build [p=x]": 1,
            "a: build [p=3": 1,
        }
        for text, line in cases.items():
            with self.subTest(text=text):
                with self.assertRaises(ParseError) as cm:
                    parse_tasks(text)
                self.assertEqual(cm.exception.line_no, line)

    def test_errors_share_a_base_class(self):
        self.assertTrue(issubclass(ParseError, TaskError))
        self.assertTrue(issubclass(CycleError, TaskError))
        self.assertTrue(issubclass(MissingDependency, TaskError))


class OrderTests(unittest.TestCase):
    def test_order_respects_deps_and_priority(self):
        order = execution_order(parse_tasks(SAMPLE))
        self.assertEqual(order, ["compile", "unit", "docs", "lint", "ship"])

    def test_missing_dependency(self):
        with self.assertRaises(MissingDependency) as cm:
            execution_order(parse_tasks("a: build <- ghost"))
        self.assertEqual((cm.exception.task, cm.exception.dep), ("a", "ghost"))

    def test_cycle_is_named(self):
        text = "a: build <- c\nb: build <- a\nc: build <- b\nd: test"
        with self.assertRaises(CycleError) as cm:
            execution_order(parse_tasks(text))
        self.assertEqual(cm.exception.cycle, ["a", "c", "b", "a"])

    def test_empty(self):
        self.assertEqual(execution_order(parse_tasks("")), [])


class SummaryTests(unittest.TestCase):
    def test_counts_every_kind_in_order(self):
        self.assertEqual(list(summarize(parse_tasks(SAMPLE)).items()),
                         [("build", 2), ("test", 2), ("deploy", 1)])
        self.assertEqual(summarize({}), {"build": 0, "test": 0, "deploy": 0})


if __name__ == "__main__":
    unittest.main()
