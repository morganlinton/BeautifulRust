# Cross-agent benchmark, October 2026

Do the skills help agents other than Claude? This run gave the same eight Rust tasks to
Claude Code and to OpenAI's Codex CLI, each with and without the BeautifulRust skills,
and graded all 32 results blind against the assertions in each eval case.

## Results

Assertions passed, out of the total for each case:

| Case | Claude, no skills | Claude, skills | Codex, no skills | Codex, skills |
| --- | --- | --- | --- | --- |
| semver-library-api (write a library) | 10/10 | 10/10 | 6/10 | 9/10 |
| log-summary-cli (write a CLI) | 8/8 | 8/8 | 6/8 | 8/8 |
| refactor-inventory-module | 10/12 | 12/12 | 4/12 | 6/12 |
| bevy-arena-regen (add a Bevy feature) | 10/10 | 7/10 | 9/10 | 9/10 |
| review-inventory-module | 8/12 | 12/12 | 5/12 | 12/12 |
| review-bevy-arena | 8/11 | 10/11 | 7/11 | 11/11 |
| port-c-config-parser | 8/11 | 11/11 | 7/11 | 10/11 |
| port-python-task-graph | 10/11 | 10/11 | 9/11 | 11/11 |
| **Total** | **72/85 (85%)** | **80/85 (94%)** | **53/85 (62%)** | **76/85 (89%)** |

The skills raised Codex from 62% to 89% and Claude from 85% to 94%. The biggest gains
were in reviews: Codex went from 5/12 to 12/12 on the inventory review, with every
finding citing a location and a named rule and showing a code fix. Codex's refactor
improved least (4/12 to 6/12). Even with the skills it kept `Rc<RefCell>` in the API
and panicked on bad input through `unwrap_or_else(|| panic!(..))`.

[`results.json`](results.json) has every assertion for every run, with the grader's
pass or fail and its evidence.

## One regression

On the Bevy feature task, Claude scored 7/10 with the skills against 10/10 without:

- **Its `Regen` component got private fields, getters, and a constructor that panics on
  a negative rate.** The task wanted plain data. The Bevy reference was partly to blame:
  its example of a component that should stay encapsulated was "a health value that must
  stay at or below a maximum", which reads like this exact feature. The reference now
  says to keep fields private only when the fields must hold an invariant together, and
  that a rate and a cap are plain data. That change came after this run.
- **The new pause system ran after the regeneration system in the chain.** A hit
  therefore paused regeneration one frame late, which is an ECS ordering bug.
- **It ran `cargo fmt`, which re-wrapped existing code.** Three of the four runs did
  this and failed the "existing code not rewritten" assertion; only Claude without
  skills avoided it.

## How it was run

- **Tasks.** The eight eval cases under `skills/*/evals/`: the six from earlier releases
  and the two Bevy cases added for this one. Each run started in its own empty git
  repository with the case's input files.
- **Same prompt for both agents.** Every run got the case's prompt plus a short
  preamble: work only in this directory, here is where cargo lives. Runs with skills got
  a copy of all three skills in `.agents/skills/` and one extra paragraph telling the agent
  to read the SKILL.md files that apply. This measures what the skill content does once
  it is loaded, not whether an agent finds the skill on its own.
- **Claude** was Claude Opus 5.5 (`claude-opus-5-5`), run as Claude Code subagents, the
  same method as the earlier eval runs. Runs without skills were told not to use the
  Skill tool, so the installed plugin couldn't leak in. The nested `claude -p` command
  could not sign in from inside the Claude desktop app, so the CLI was not used.
- **Codex** was `codex exec` from Codex CLI 0.163.0 with its default model and reasoning
  settings, in the `workspace-write` sandbox with network access, so cargo could fetch
  crates. Codex reads `.agents/skills/` natively. The run without skills confirmed no
  BeautifulRust skill was visible.
- **Grading.** Each case's four results were copied to `run-1` through `run-4` in a
  shuffled order with the skill folders removed. A grader agent (Claude Opus 5.5) read
  the case's assertions, built and tested each run with cargo where an assertion needed
  it, and wrote a pass or fail with evidence. The key was applied afterwards. The
  scripts are in [`harness/`](harness/).

## Caveats

- **One run per configuration.** A single assertion is about one percentage point of
  the total, so treat small differences, such as 10/11 against 11/11, as noise.
- **The grader is a Claude model.** Labels were blind, but a Claude grader may still
  favor Claude-shaped output. Assertions about builds, tests, and clippy are mechanical;
  the review and naming assertions are judgment calls.
- **Defaults on both sides.** Codex ran faster and used less reasoning at its default
  settings: about one to two minutes per task, against one to eleven minutes per task
  for Claude. A higher Codex reasoning setting might close part of the
  gap without skills.
- **The skills cost tokens.** Claude used about 26% more tokens per task with the skills
  loaded, and Codex about 84% more input tokens. Most of Codex's input was cached
  repeats of the skill text.
- **One grader call was a judgment call.** For the semver doc-example assertion, the
  grader counted a crate with no doc examples as a fail, not a vacuous pass. That
  affected both Codex runs.
- **The Bevy cases are new.** They were written and checked against bevy 0.20.0 before
  these runs, but this is their first use. The plain-data assertion in the Bevy feature
  case and the reference's old wording disagreed, as described above.
