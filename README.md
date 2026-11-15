# Python interview

Open `interview.code-workspace` in VS Code. Start in `solution.py`; paste
the supplied question into `PROBLEM.md` and examples into `tests/test_solution.py`.
The implementation is blank. The one discovered test is intentionally skipped
until you replace it with a real example.

No packages or remote Git repository are needed. The local `.venv` is prepared
on this Mac. To recreate it elsewhere: `python3 -m venv .venv`.

In VS Code:

- **Cmd+Shift+B** runs the tests in the terminal.
- **Terminal → Run Task → Interview: Run solution** runs `solution.py`.
- **F5** debugs the solution; a test-debug configuration is also available.
- The **Testing** sidebar discovers unittest examples.
- **Source Control** shows the current question's edits.

## A new question

Commit current work first, then use **Terminal → Run Task → Interview: New
question branch**, or:

```sh
.venv/bin/python scripts/new_question.py arrays-01
```

This creates `question/arrays-01` from the blank `interview-starter` tag. It
refuses to switch if files are uncommitted or the branch already exists. Your
previous question remains on its branch. Use names such as `graphs-01`,
`debugging-01` or `api-01`; the folder and commands stay the same.

Once you paste a supplied prompt, starter and tests, commit that import before
implementing so the solution diff is easy to inspect. Keep any supplied test
framework or project conventions; unittest is only the initial default.

## Continue with the AI

> Pair with me on PROBLEM.md. Use my comments and pseudocode as design input.
> Help me make the reasoning clear, and implement when I ask. Keep feedback
> natural; use coach mode at checkpoints when requested.

The harness remains in `../ai-coding-interview`; its setup is independent. Work
in this checkout and save editor buffers before switching interfaces.

## Local Git layout

- `main` and tag `interview-starter`: blank template.
- `practice/delivery-grid`: imported practice question.
- `question/*`: new questions from the blank template.

Open this workspace in the same VS Code window. Use the Interview Workbench
folder for code; the second folder is the existing harness for reference.
Save and commit your practice work before switching back with `git switch main`.
No remote is configured. If the interviewer provides a full Git repository,
open that repository and follow its instructions and native test commands.
