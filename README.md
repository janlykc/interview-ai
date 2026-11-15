# Ai assisted interview

Start each question in the interview repo, with the AI Team Harness alongside it
in VS Code. The harness provides the pairing and coaching guidance; this repo
holds the prompt, design notes, implementation, and tests.

1. **Start clean.** From a clean checkout, use **Terminal → Run Task → Interview:
   New question branch**, or run `.venv/bin/python scripts/new_question.py round-01`.
   This creates `question/round-01` from the current local `main`; existing branches
   and uncommitted work are protected. Keep `main` for reusable setup.
2. **Capture the question.** Paste it into [PROBLEM.md](PROBLEM.md). Add supplied
   starter files and tests as given. If useful, commit the import before editing
   the solution so you can review the delta.
3. **Design if time allows.** Capture the input/output contract and one or two
   examples in [design/spec.md](design/spec.md). Sketch the approach and first
   testable checkpoint in [design/outline.md](design/outline.md). For a short
   round, say the example and the approach aloud, or sketch them in code.
4. **Implement and verify.** Put a standalone answer in [solution.py](solution.py)
   and examples in [tests/test_solution.py](tests/test_solution.py). Press
   **Cmd+Shift+B** for tests. Use **Interview: Run solution** under Terminal →
   Run Task, or select **Interview: Debug solution** / **Interview: Debug tests**
   in Run and Debug and press **F5**. Set a breakpoint on an executable line.
   The initial example is skipped until you replace it with a real test.

If given a full project, follow its structure and test commands rather than
flattening it into the template. The Python scaffold needs no third-party
packages. To recreate the environment, run `python3 -m venv .venv` here.

For pairing, say: “Read PROBLEM.md and my design notes if I’ve filled them in.
Use my examples and pseudocode. Discuss the approach with me and implement
when I ask. Use coach mode only when I ask for feedback.”

`practice/delivery-grid` is the onboarding rehearsal. Commit your work before
switching back with `git switch main`. All branches are local.
