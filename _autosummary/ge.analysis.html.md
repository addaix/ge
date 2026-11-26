# ge.analysis

Issue and PR analysis: staleness, relevance, and state assessment.

Examines an issue or PR to determine if it’s still relevant, already fixed,
or needs further investigation before work begins.

### Module Attributes

| [`STALE_CLAIM_DAYS`](#ge.analysis.STALE_CLAIM_DAYS)   | Days without activity after which an In progress / In review issue is flagged.   |
|---------------------------------------------------------------------|----------------------------------------------------------------------------------|

### Functions

| [`analyze_issue`](#ge.analysis.analyze_issue)(repo, number, \*[, ...])       | Analyze an issue for staleness and current relevance.                   |
|-----------------------------------------------------------------------------------------------|-------------------------------------------------------------------------|
| [`analyze_pr`](#ge.analysis.analyze_pr)(repo, number)                     | Analyze a PR for review context and merge readiness.                    |
| [`check_referenced_files`](#ge.analysis.check_referenced_files)(repo, file_paths, \*) | Check if files mentioned in an issue still exist on the default branch. |

### ge.analysis.STALE_CLAIM_DAYS *= 14*

Days without activity after which an In progress / In review issue is flagged.

### ge.analysis.analyze_issue(repo, number, , stale_claim_days=14)

Analyze an issue for staleness and current relevance.

Returns a dict with:

> - state: open/closed
> - state_reason: completed / not_planned / duplicate / reopened, or None
> - status: GitHub’s native status (Backlog, Todo, In progress, …), or None
> - age_days: days since creation
> - last_activity_days: days since last comment/event
> - labels: list of label names
> - related_prs: PRs that reference this issue
> - related_commits: commits mentioning this issue
> - referenced_files: files mentioned in the issue body
> - signals: list of human-readable observations about freshness
> - recommendation: ‘proceed’, ‘investigate’, or ‘likely_resolved’
```pycon
>>> # analysis = analyze_issue('owner/repo', 42)
```

### ge.analysis.analyze_pr(repo, number)

Analyze a PR for review context and merge readiness.

Returns a dict with state, review status, CI signals, conflicts, etc.

```pycon
>>> # analysis = analyze_pr('owner/repo', 7)
```

### ge.analysis.check_referenced_files(repo, file_paths, , ref=None)

Check if files mentioned in an issue still exist on the default branch.

Returns dict mapping path -> {‘exists’: bool, ‘snippet’: str | None}.

```pycon
>>> # status = check_referenced_files('owner/repo', ['src/main.py'])
```
