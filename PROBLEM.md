# Outbound webhook delivery practice

This is an original summary of the practice problem. The supplied interview
handout is retained locally and is not distributed in this public repository.

Build a pipeline that durably accepts an internal event, selects its registered
customer destinations, and dispatches a signed HTTP request to each independently.
Explore what happens when a destination is unavailable, a response is lost, or a
process crashes between database and queue operations.

The rehearsal focuses on an explainable working slice and explicit reliability
boundaries. The current code implements Flask ingress, seeded routing, and atomic
SQLite acceptance. The proposed queue, dispatch workers, retries, and dead-letter
handling are described in [the design](design/spec.md) and remain future work.

Use [the portable prompts](INTERVIEW_PROMPTS.md) to pair on one feature at a time.
