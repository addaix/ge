# GitHub's native issue statuses: what they are, how they behave, how people use them

Research date: 2026-11-26 (three days after the public preview). Decision that follows from it: [docs/decisions/0001-native-issue-statuses.md](../../../../docs/decisions/0001-native-issue-statuses.md). Tooling: `ge/status.py`.

## Summary and recommendation

GitHub issues now carry a **status** (public preview since 2026-11-23) [1][2]: a fixed set of seven, Backlog, Todo, In progress, In review, Done, Not planned, Duplicate, each in a **category** (`backlog`, `planned`, `started`, `completed`, `not_planned`, `duplicate`) that decides open/closed and the closed `state_reason`. It is the same shape as Linear's workflow-state categories [3] and Jira's status categories [4], except that GitHub also fixes the status names. It is readable and writable through REST and GraphQL today (verified below), searchable with `status:"<name>"`, not yet settable from `gh` [5], and it records no history in the issue timeline.

**Recommendation for agent-driven repos:** use the status for one thing it does better than anything else, the *live claim*: an agent sets **In progress** when it starts on an issue, GitHub moves it to In review when a PR is linked and to Done when the PR merges, and the agent puts it back to **Todo** if it stops without a PR. Keep labels for what a status cannot say (who the issue is waiting on, why it is blocked, what kind of work it is) and keep issue dependencies as the source of truth for blocking. Do not backfill old issues, and do not build readers that *depend* on statuses until GA: a missing status means "unknown", not "Backlog".

## What it is

- **Name and status**: "Issue statuses", with "repository boards" (a board layout for repository saved views, grouped by status, drag to change status) [1]. Public preview, "subject to change", "rolling out gradually" (GraphQL schema descriptions). Feedback thread: [2].
- **The set is fixed.** A maintainer: "The issue statuses are fixed to this set" [2]. No custom statuses, no per-repo configuration, no off switch documented [2][6].
- **Enablement** is per owner (organization or user); once an owner has it, all its repositories do [2]. `planningStatuses` on `Organization`, `User` and `Repository` returns `null` where it is not available.
- **Categories** (GraphQL `PlanningStatusCategory { key name state stateReason }`):

| Status | Category key | State | State reason |
|---|---|---|---|
| Backlog | `backlog` | open | |
| Todo | `planned` | open | |
| In progress | `started` | open | |
| In review | `started` | open | |
| Done | `completed` | closed | completed |
| Not planned | `not_planned` | closed | not_planned |
| Duplicate | `duplicate` | closed | duplicate |

GitHub's guidance is to match statuses by id or category key rather than by name [7]; "clients should expect new keys to be added" (schema).

## Automatic transitions

Documented [1][6]: assigning a user moves the issue to Todo; assigning an agent moves it to In progress; linking a draft PR moves it to In progress; marking the draft ready for review, or linking an open PR, moves it to In review. If a Project owned by the same owner has a Status option with a matching name, the two sync both ways [1][6]. Community reports say assignment can pull an issue backwards in a synced Project (Testing to Todo) and ask for an off switch [2].

Verified by probing a private repository on 2026-11-26:

- A new issue starts in **Backlog**. Issues created before the preview have **no status** (`null`) until something sets one; the UI shows them as Backlog.
- Assigning a person moved Backlog to **Todo**; unassigning did not move it back.
- Assigning a person to an issue already **In progress** left it In progress (so a claim is not undone by a later assignment; community reports differ when the issue was in Todo [8]).
- `gh issue close` moved any open status to **Done**; `--reason "not planned"` to **Not planned**.
- **Reopening resets the status to Backlog**, whatever it was before closing.
- Setting a closed status closes the issue with the matching `state_reason`; setting an open status on a closed issue reopens it (`state_reason: reopened`).
- The issue timeline and events API record **no status-change events** (only Projects have `ProjectV2ItemStatusChangedEvent`). The docs describe a webhook `issues` action `status_changed` with `changes.status.from` [7]; one webhook consumer crashed on it [9].

## API surface (verified 2026-11-26, `gh` 2.72)

- **REST read**: every issue payload has `status`: `{"category": "started", "id": 4, "name": "In progress"}` or `null`. (One early report found no `status` key on 2026-11-24 [10]; it is present now.)
- **REST write**: `PATCH /repos/{o}/{r}/issues/{n}` with `{"status": "In progress"}` (the exact name, as a string); `POST /repos/{o}/{r}/issues` accepts `status` too. An object (`{"name": ...}`) is rejected with 422. The REST reference documents only `GET planning-statuses` [11], so this write path is ahead of the docs.
- **GraphQL**: `Issue.status: PlanningStatus` (`id`, `name`, `category`), `Issue.viewerCanSetStatus`, mutation `setIssueStatus(input: {issueId, statusId, duplicateIssueId})` ("closing or reopening it when the status calls for it"; `duplicateIssueId` is required for Duplicate), `CreateIssueInput.statusId` (an open status from the owner's `planningStatuses`; ignored without permission, falling back to Backlog). Status ids are global (`IS_kgAC` ...) and identical across owners.
- **Search**: `status:"In progress"`, `status:Todo`, `no:status`. Only exact names (any case) are accepted; category keys, hyphenated forms (`in-progress`) and comma lists are rejected with "Unknown issue status". GraphQL `IssueFilters` cannot filter by status [12].
- **CLI**: `gh` has no status flag yet; the request is [5]. Until it lands, `gh api` (or `ge set-status`) is the way.
- **Status cannot be cleared** back to none [2][12].

## How the community is using it (first three days)

Almost every early adopter is a repository driven by AI coding agents. Patterns, most to least common:

1. **Wait for GA; labels stay the source of truth**, because the set is fixed and writes were thought to be undocumented [13][14].
2. **Status replaces `status:*` labels**: labels migrated and deleted, the rule written into the agents' instructions [12][15]; one maps a `status: blocked` label onto native issue dependencies instead [10].
3. **Hybrid**: status carries the execution phase; labels keep why an issue waits and on whom (needs-info, needs-decision, lanes) [16][17].
4. **Claim protocol for agents**: on start the agent sets In progress (and often assigns itself) so two sessions do not take the same issue; on stopping without a PR it resets to Todo [8][15]. Creating a branch (`gh issue develop`) moves nothing, so the agent must set it [18].
5. **Todo as the dispatch queue**: "auto pick takes Todo issues only" [17]; Backlog hidden from the working view [12].
6. **One best-effort writer** that mirrors an existing state machine into the status and does nothing when `planningStatuses` is null [19][16].
7. **Minimal adoption**: one line in AGENTS.md, no backfill, closing sets Done by itself [20].

Critiques [2]: the fixed set (people want Testing, Waiting, needs-info, ready-for-human); "In review" conflates "waiting for review" with "being reviewed"; automation surprises with no switch to turn rules off; a status cannot be removed; Projects sync only by name and only for same-owner projects; the documentation lags the API.

## Prior art

Linear fixes categories (Backlog, Unstarted, Started, Completed, Canceled) and lets teams define statuses inside them [3]. Jira has three fixed categories (To Do, In Progress, Done) under custom statuses [4]. GitHub Projects v2 has Status as an ordinary single-select field with built-in automations (item added sets Todo, closed sets Done) [21]. GitLab work-item statuses have categories Triage, To do, In progress, Done, Canceled, with custom lifecycles on paid tiers [22]. GitHub's design is the strictest of these: fixed categories *and* fixed names.

## Open questions

- Whether GA brings custom statuses, an off switch for the automations, or a timeline event.
- Whether `gh issue edit --status` lands [5].
- Whether the REST write path is kept as is (it is undocumented today).

## REFERENCES

1. [Issue statuses and repository boards are in public preview, GitHub Changelog, 2026-11-23](https://github.blog/changelog/2026-11-23-issue-statuses-and-repository-boards-are-in-public-preview/)
2. [Issue statuses feedback discussion, GitHub Community #212171](https://github.com/orgs/community/discussions/212171)
3. [Linear docs: Configuring workflows](https://linear.app/docs/configuring-workflows)
4. [Jira: Defining status field values](https://confluence.atlassian.com/adminjiraserver0914/defining-status-field-values-1385108401.html)
5. [cli/cli#14996: support issue status in gh](https://github.com/cli/cli/issues/14996)
6. [GitHub Docs: About issue statuses](https://docs.github.com/en/issues/tracking-your-work-with-issues/learning-about-issues/about-issue-statuses)
7. [GitHub Docs: Issue status webhooks and workflows](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/issue-status-webhooks-and-workflows)
8. [publira/publira#6835: set In progress when you start work, state the rule in AGENTS.md](https://github.com/publira/publira/issues/6835)
9. [book000/github-webhook-bridge#2784: status_changed webhook action](https://github.com/book000/github-webhook-bridge/issues/2784)
10. [mrh-is/mistria-fyi#756](https://github.com/mrh-is/mistria-fyi/issues/756)
11. [GitHub REST: planning statuses](https://docs.github.com/en/rest/repos/planning-statuses)
12. [williamthorsen/top-right#148](https://github.com/williamthorsen/top-right/issues/148)
13. [DKJ-Solutions/dkj-marketplace#4457: revisit once GA with a documented write API](https://github.com/DKJ-Solutions/dkj-marketplace/issues/4457)
14. [starfoxcom/bindwright#1424: use GitHub's new issue states in the tracker](https://github.com/starfoxcom/bindwright/issues/1424)
15. [J4EU/Store-Expiration-Tracker#121](https://github.com/J4EU/Store-Expiration-Tracker/issues/121)
16. [jaylouiz/agent-workflow#22: set native status next to the phase labels](https://github.com/jaylouiz/agent-workflow/issues/22)
17. [lordlothar99/saani#72](https://github.com/lordlothar99/saani/issues/72)
18. [shoji9x9/skills#1138](https://github.com/shoji9x9/skills/issues/1138)
19. [phmilk/reforged-ts#958: mirror the claim board's status into the issue status](https://github.com/phmilk/reforged-ts/issues/958)
20. [loftwah/app-composer#1209](https://github.com/loftwah/app-composer/issues/1209)
21. [GitHub Docs: Using the built-in automations (Projects)](https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/using-the-built-in-automations)
22. [GitLab Docs: Work item status](https://docs.gitlab.com/user/work_items/status)
