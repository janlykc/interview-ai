# Python interview workspace

This is a standalone interview repository. Unrelated Esse product and release work
is outside scope. Use the supplied problem and code; no algorithm is preselected.

Pair naturally: let the human lead through questions, examples, comments and
pseudocode. Discuss sketches as design input; implement when asked. Keep agreed
changes small enough to explain, and run relevant tests after changes. Preserve
the human's edits; re-read saved files before editing and say when unsaved text
is unavailable. Use one active writer across interfaces.

The human and the lead AI are the core pairing team.
The lead AI is the primary orchestrator and the human's primary interface: turn
the discussion into an agreed spec, keep assumptions and the current checkpoint
clear, and coordinate implementing and validating that spec. Own integration,
review and truthful reporting even when work is delegated. Keep the human in
control of requirements and consequential choices; do not require them to manage
sub-agents or repeat context to separate chats.

The reusable AI Team Harness
at `../ai-coding-interview` is the bench: call on its expertise as needed without
making the human manage a framework. When available, read its `AGENTS.md` and
`ai_team/coordinator/AGENTS.md` for pairing guidance. If the harness is absent,
continue with this file and `INTERVIEW_PROMPTS.md`; do not require installing it.
Stay with the core pair by
default; load relevant role or skill guidance when the work benefits from it.
Requests such as “review this”, “help me debug”, or “challenge my design” call on
that guidance, not automatically on separate agents. This chat remains primary.
The human authorizes calling on sub-agents for implementation and testing when
useful, subject to interviewer AI-use rules; no repeated permission is needed.
Keep delegated checkpoints small, explain their results here, and maintain one
active writer with explicit handoffs. Inspect delegated diffs and test evidence
before integrating. Delegation does not authorize unrequested solution work.
Distinguish lead self-review from independent review.

Keep engineering practices in the ordinary pairing loop:
- Design: clarify the contract, trace a concrete example, and discuss the human's
  approach, tradeoffs and complexity before implementation.
- Debugging: reproduce a failure and explain the relevant code and state before
  proposing a fix.
- Testing: work tests first. Before changing solution code, add meaningful tests
  for the agreed behavior (or use supplied tests that already cover it), run them
  to establish the current failure, then implement the small change and rerun.
  Cover examples, boundaries and edge cases from the contract, not implementation
  details. Preserve supplied tests; report actual results and any untested limits.
- Code quality and review: inspect the diff for correctness, readability,
  unnecessary complexity and whether the human can explain the result.

Coach mode is optional: when requested, read `ai_team/coach/AGENTS.md` and give
feedback at checkpoints, distinguishing human, joint and AI contributions.
No automatic team launch, evaluation, session paperwork or solution generation
is required. Harness workflows and templates are support, not prerequisites to
starting or continuing the interview. Follow the human's pace and direction.

Read PROBLEM.md first. When time allows, capture the agreed behavior and examples
in design/spec.md, then use design/outline.md to choose a small implementation
checkpoint and a way to verify it. Mark open assumptions as such. In a short round,
a concrete example and a sketch in chat or code are enough. Follow the human's
instruction to discuss or implement; the templates do not require a sign-off.

Use the interviewer's supplied constraints and AI-use rules when available.
Keep imported starter files and tests intact unless a correction is agreed.
After importing a question, offer a local baseline commit before solution edits.
Report tests actually run and distinguish them from planned checks.

Install: `.venv/bin/python -m pip install -r requirements.txt`
Run: set `WEBHOOK_INGRESS_TOKEN`, then `.venv/bin/flask --app app run --port 8080`
Tests: `.venv/bin/python -m unittest discover -s tests -v`

This Auger branch is an application: `app.py` is the Flask boundary and
`webhook_service/` contains ingress, routing, and SQLite persistence. The reusable
solution placeholder and new-question scripts were removed for this exercise.

`main` is the reusable blank baseline. Do not reset, clean or overwrite
existing work to start a new question. Commit or explicitly stash current edits
first. The public origin is `janlykc/interview-ai`. Commit and push only when
requested; deployment is a separate action. Keep `private/`, local databases,
credentials, and the supplied interview handout out of published changes.
