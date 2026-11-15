# Python interview workspace

This is a standalone interview repository. Unrelated Esse product and release work
is outside scope. Use the supplied problem and code; no algorithm is preselected.

Pair naturally: let the human lead through questions, examples, comments and
pseudocode. Discuss sketches as design input; implement when asked. Keep agreed
changes small enough to explain, and run relevant tests after changes. Preserve
the human's edits; re-read saved files before editing and say when unsaved text
is unavailable. Use one active writer across interfaces.

The reusable harness is at `../ai-coding-interview`. For its pairing guidance,
read its `AGENTS.md` and `ai_team/coordinator/AGENTS.md` explicitly. Coach mode is
optional: when requested, read its `ai_team/coach/AGENTS.md` and give feedback at
checkpoints, distinguishing human, joint and AI contributions. No automatic
delegation, evaluation, session paperwork or solution generation is required.

Use the interviewer's supplied constraints and AI-use rules when available.
Keep imported starter files and tests intact unless a correction is agreed.
After importing a question, offer a local baseline commit before solution edits.
Report tests actually run; the initial skipped example proves no solution behavior.

Run: `.venv/bin/python solution.py`
Tests: `.venv/bin/python -m unittest discover -s tests -v`
Fresh branch: `.venv/bin/python scripts/new_question.py arrays-01`

`interview-starter` is the blank baseline tag. Do not reset, clean or overwrite
existing work to start a new question. Commit or explicitly stash current edits
first. No remote, push, deployment or external service is configured.
