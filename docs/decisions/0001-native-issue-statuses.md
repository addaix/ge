# ADR-0001: Native issue statuses carry the live claim; labels keep who and why

- **Status:** Accepted (provisional while GitHub's issue statuses are in preview)
- **Date:** 2026-11-26
- **Research:** [misc/docs/research/general/github-issue-statuses.md](../../misc/docs/research/general/github-issue-statuses.md)

## Context

GitHub issues now have a native status (Backlog, Todo, In progress, In review, Done, Not planned, Duplicate), writable through REST and GraphQL, searchable with `status:"<name>"`, and moved automatically by assignment, linked PRs and closing. The set is fixed and the feature is a preview.

Agents using `ge` and the GitHub-memory conventions already track work with open/closed issues, `Closes #N` in PRs, a label for chores that wait on a human, a `blocked` label backed by issue dependencies, and a checklist inside roadmap issues (`ge.RoadmapStore`, todo/doing/done). What was missing is a GitHub-side signal that *someone is working on this issue right now*: two agent sessions can pick up the same issue, and a reader cannot tell a claimed issue from a filed one.

## Decision

1. **The status is the issue's progress, and only that.** Meaning, as agents use it:
   - **Backlog**: filed, not scheduled (GitHub's default for new issues; nothing to do).
   - **Todo**: queued to be worked next. Assigning someone sets it.
   - **In progress**: an agent session (or a person) is working on it now. **The agent sets it when it starts** (`ge set-status <repo> <n> in-progress`). This is the claim.
   - **In review**: a PR is linked. GitHub sets it; agents do not.
   - **Done / Not planned / Duplicate**: set by closing (`Closes #N` on merge; `gh issue close --reason "not planned"`; `ge set-status <repo> <n> duplicate --duplicate-of <m>`).
2. **Before starting, read the status.** In progress or In review means someone has claimed it: ask, or pick another issue. A claim quiet for more than 14 days is flagged by `ge analyze-issue` as possibly stale.
3. **Stopping without a PR, set it back to Todo.** A blocked agent that stays on the issue leaves In progress and says why in the decision log.
4. **Labels keep what a status cannot say**: who the issue waits on (a human-chore label), why it is blocked (`blocked`, with issue dependencies as the source of truth), and what kind of work it is. **No progress labels** (`in-progress`, `wip`, `status:*`): the native status replaces them.
5. **Best effort, never a dependency.** Issues filed before the preview have no status until one is set, and setting it works. Where statuses are unavailable, `ge.set_issue_status` raises ("did not set") and `ge.issue_status` returns `None`: carry on and fall back on open/closed. Nothing may fail because a status could not be set, and no reader may treat a missing status as Backlog.
6. **No backfill, no Projects mirror.** Old issues keep no status until they are touched. Do not track the same progress in a Projects v2 Status field; if a same-owner Project uses matching option names, GitHub syncs them both ways.
7. **Reopening resets to Backlog.** An agent reopening an issue to work on it sets In progress again.

## Alternatives rejected

- **Wait for GA.** The write path works now and the claim solves a real collision; the cost of the preview changing is one module (`ge/status.py`) and one paragraph of skill text.
- **Status replaces the human-chore and blocked labels.** There is no status for "waiting on a person" or "blocked", and the set is fixed; folding them into Todo would lose the reason.
- **Assignee as the claim.** Agents share one account, so the assignee cannot tell sessions apart, and assignment notifies.

## Consequences

- `ge` gains `status`, `set-status`, `in-status` (CLI) and `issue_status`, `set_issue_status`, `issues_with_status`, `planning_statuses` (Python); `analyze_issue` reports `status`, `state_reason` and a stale-claim signal.
- "What is in flight" across an owner is one query: `ge in-status "In progress" --owner <owner>`.
- Revisit at GA, or if GitHub adds custom statuses, a timeline event for status changes, or `gh` support.
