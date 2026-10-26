# Contributing

Thanks for helping make BeautifulRust better. Issues and pull requests are welcome. A few
conventions keep the skills consistent and trustworthy.

## The one rule: every rule needs a source

The skills are a synthesis of published Rust guidance, not a list of opinions. Each rule
you add or change should trace back to one of the sources in the README, or to another
source of similar weight, such as the Rust Reference, the standard library docs, the
clippy lint list, or an accepted RFC. Link it in your pull request. If the sources
disagree, say which one you followed and why.

## Good first contributions

- **A rule the skills get wrong or miss.** Open a "Propose a rule" issue with the source,
  a short example of code the agent writes today, and what it should write instead.
- **A review false positive.** If `rust-review` flags something that's actually fine,
  open a "Review false positive" issue with the code and the finding. These become new
  eval cases.
- **A new eval case.** A realistic prompt, the input files it needs, and one assertion
  per file. See [Testing the skills](README.md#testing-the-skills) for the layout.
- **A broken install path.** Agents move their skill directories. If an install step in
  the README stopped working, a fix with a link to the agent's current docs is very
  welcome.

## Making a change

1. **Edit the skill.** Each skill is `skills/<name>/SKILL.md`. Keep it under about 500
   lines; longer material belongs in `references/`. Explain why a rule matters, not just
   what it is. Agents follow reasoning better than commands.
2. **Compile your examples.** Every Rust code block in the skills and the README must
   compile on stable Rust. Run `python3 scripts/check-examples.py`; CI runs it too.
   Most examples are fragments, so `scripts/examples.json` gives each one the code
   around it that it needs, such as a type it uses or the function its statements
   belong in. If you add, move, or change the first line of a block, update its entry
   there. A block that can't compile on its own, like signatures without bodies, gets
   a `skip` with the reason.
3. **Check lint changes.** If you touch `lints/`, run clippy on a crate that uses the
   config and confirm the lint name is accepted and actually fires.
4. **Run the evals if you changed behavior.** From the skill's directory:

   ```bash
   claude plugin eval . --allow-tools Write,Edit,Bash --scaffold
   ```

   These are real model runs and are billed, so a maintainer can run them for you if
   you'd rather not. Say in the pull request whether you ran them.
5. **Validate the plugin** with `claude plugin validate .` from the repo root.
6. **Add a line to the Unreleased section of [CHANGELOG.md](CHANGELOG.md).**

## Style

- Write for an agent reading it mid-task: direct, imperative, one idea per bullet.
- Prefer a short code example to a paragraph of description.
- No Claude-specific instructions in the skills. They are standard Agent Skills and should
  work in any agent.

## License

By contributing, you agree your contribution is licensed under the MIT license in
[LICENSE](LICENSE).
