"""Parse a small task-definition format and compute a deterministic run order.

Format, one task per line:

    name: kind [p=N] <- dep1, dep2

`kind` is one of build, test, deploy. `[p=N]` is an optional integer priority
(higher runs first among tasks that are ready at the same time). `<- deps` is
optional. Blank lines and lines starting with '#' are ignored.
"""

KINDS = ("build", "test", "deploy")


class TaskError(Exception):
    """Base class for every error this module raises."""


class ParseError(TaskError):
    def __init__(self, line_no, message):
        super().__init__(f"line {line_no}: {message}")
        self.line_no = line_no


class MissingDependency(TaskError):
    def __init__(self, task, dep):
        super().__init__(f"{task} depends on unknown task {dep}")
        self.task = task
        self.dep = dep


class CycleError(TaskError):
    def __init__(self, cycle):
        super().__init__("cycle: " + " -> ".join(cycle))
        self.cycle = cycle


class Task:
    def __init__(self, name, kind, deps=None, priority=None):
        self.name = name
        self.kind = kind
        self.deps = deps or []
        self.priority = priority

    def __repr__(self):
        return f"Task({self.name!r}, {self.kind!r}, {self.deps!r}, {self.priority!r})"


def parse_tasks(text):
    """Returns a dict of name -> Task, in the order tasks were defined."""
    tasks = {}
    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ParseError(line_no, "expected 'name: kind'")
        name, rest = line.split(":", 1)
        name = name.strip()
        if not name or not name.replace("-", "").replace("_", "").isalnum():
            raise ParseError(line_no, f"bad task name {name!r}")
        if name in tasks:
            raise ParseError(line_no, f"duplicate task {name}")
        deps = []
        if "<-" in rest:
            rest, dep_text = rest.split("<-", 1)
            deps = [d.strip() for d in dep_text.split(",") if d.strip()]
        priority = None
        if "[p=" in rest:
            rest, prio_text = rest.split("[p=", 1)
            if not prio_text.strip().endswith("]"):
                raise ParseError(line_no, "unclosed priority")
            try:
                priority = int(prio_text.strip()[:-1])
            except ValueError:
                raise ParseError(line_no, "priority must be an integer")
        kind = rest.strip()
        if kind not in KINDS:
            raise ParseError(line_no, f"unknown kind {kind!r}")
        tasks[name] = Task(name, kind, deps, priority)
    return tasks


def _ready_key(task):
    # Higher priority first; tasks without a priority come after all that have one;
    # ties broken by name.
    has = task.priority is not None
    return (not has, -(task.priority or 0), task.name)


def execution_order(tasks):
    """Returns task names in a valid run order.

    Raises MissingDependency for a dependency that isn't defined and CycleError,
    naming the cycle, if no order exists.
    """
    for t in tasks.values():
        for d in t.deps:
            if d not in tasks:
                raise MissingDependency(t.name, d)
    remaining = {name: set(t.deps) for name, t in tasks.items()}
    order = []
    while remaining:
        ready = [tasks[n] for n, deps in remaining.items() if not deps]
        if not ready:
            raise CycleError(_find_cycle(tasks, remaining))
        nxt = min(ready, key=_ready_key)
        order.append(nxt.name)
        del remaining[nxt.name]
        for deps in remaining.values():
            deps.discard(nxt.name)
    return order


def _find_cycle(tasks, remaining):
    start = min(remaining)
    path, seen = [], {}
    node = start
    while node not in seen:
        seen[node] = len(path)
        path.append(node)
        node = min(d for d in tasks[node].deps if d in remaining)
    return path[seen[node]:] + [node]


def summarize(tasks):
    """Returns a count of tasks per kind, for every kind, in KINDS order."""
    counts = {k: 0 for k in KINDS}
    for t in tasks.values():
        counts[t.kind] += 1
    return counts
