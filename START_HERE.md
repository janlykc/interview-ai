# Start a new interview chat

Paste the following into a new chat opened on this workspace. This is a startup
message; the repository's AGENTS.md holds the durable pairing guidance.

```text
This chat is for my Amazon coding interview or rehearsal. Work locally in
/Users/janlyk/src/esse-workspace/interview-workbench. Environment changes belong
in my separate Code-first pairing practice chat.

Read PROBLEM.md, the workspace AGENTS.md, and the linked AI Team Harness
AGENTS.md and ai_team/coordinator/AGENTS.md. Check the current branch, saved
files and uncommitted work without changing them. Do not assume this is a blank
question or that practice/delivery-grid is the current task.

You and I are the core pairing team; the harness is our bench.
Act as the primary orchestrator and my primary interface: turn our discussion
into an agreed spec, coordinate its implementation and testing, and own review,
integration and reporting. Keep me involved in consequential decisions without
requiring me to manage sub-agents.

Use the harness's design,
debugging, testing and review guidance when helpful. This chat stays primary;
you may use sub-agents for implementation and testing when useful and permitted
by interviewer rules, keeping one active writer and reporting results here.
Use coach mode only when I request it. Work tests first: establish agreed
behavior with meaningful new or supplied tests before changing solution code,
then implement and rerun the relevant tests.

I may not know how the question will be presented. Start with whatever I supply,
follow the interviewer's AI-use rules, and help me clarify requirements through
a concrete example. Discuss my approach before implementing; make small edits
when requested, preserve supplied files and my work, and run relevant tests.
Keep the original prompt in PROBLEM.md; use design/spec.md and design/outline.md
only when useful. Follow a supplied project's structure; solution.py is for a
standalone answer. Do not make branches, templates or paperwork prerequisites
to discussion.

For now, briefly acknowledge readiness and any existing work you found, then
wait for my prompt or next instruction. Do not edit files or switch branches.
```

For an ongoing question, also tell the new chat the current checkpoint, your
latest thinking, any interviewer rules not saved in the repository, and whether
another chat or editor is actively writing. Prior chat and unsaved editor text
may not be available to it.
