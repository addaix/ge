# ge.status

GitHub’s native issue statuses: read, set and search them.

GitHub issues carry a *status* (public preview since 2026-11-23): one of a fixed
set, each in a *category* that decides whether the issue is open or closed.

| Status      | Category    | State   | State reason   |
|-------------|-------------|---------|----------------|
| Backlog     | backlog     | open    |                |
| Todo        | planned     | open    |                |
| In progress | started     | open    |                |
| In review   | started     | open    |                |
| Done        | completed   | closed  | completed      |
| Not planned | not_planned | closed  | not_planned    |
| Duplicate   | duplicate   | closed  | duplicate      |

Setting a closed status closes the issue and setting an open one reopens it, so
the status is the single field to write. GitHub also moves it on its own:
assigning a person moves Backlog to Todo, linking a draft PR moves it to In
progress, linking an open PR (or marking the draft ready) moves it to In review,
closing moves it to Done, and **reopening resets it to Backlog**.

Everything goes through the `gh` CLI (REST `status` field; GraphQL only for
Duplicate, which needs the original issue). Where statuses are not available
(the preview has not reached that repository, or the viewer cannot see them),
[`issue_status()`](#ge.status.issue_status) returns `None` and callers fall back on open/closed.

```pycon
>>> normalize_status('in-progress')
'In progress'
>>> normalize_status('TODO')
'Todo'
>>> status_query('In progress')
'status:"In progress"'
```

### Module Attributes

| [`ISSUE_STATUSES`](#ge.status.ISSUE_STATUSES)    | GitHub's status names, in display order.                        |
|--------------------------------------------------------------------|-----------------------------------------------------------------|
| [`CLAIM_CATEGORY`](#ge.status.CLAIM_CATEGORY)    | someone is working on the issue.                                |
| [`SEARCH_RESULT_CAP`](#ge.status.SEARCH_RESULT_CAP) | GitHub's search API serves at most this many results per query. |

### Functions

| [`is_claimed`](#ge.status.is_claimed)(issue)                                  | Whether the issue's status says someone is working on it (In progress or In review: category `started`).                                                                                                                                      |
|-----------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [`issue_status`](#ge.status.issue_status)(repo, number)                         | The issue's status name, or `None` when it has none or statuses are not available for this repository.                                                                                                                                        |
| [`issues_with_status`](#ge.status.issues_with_status)(status, \*[, repo, owner, ...]) | Yield issues in one status, across a repository or a whole owner.                                                                                                                                                                             |
| [`normalize_status`](#ge.status.normalize_status)(name, \*[, statuses])             | Return the exact status name GitHub expects for a loosely spelled one.                                                                                                                                                                        |
| [`planning_statuses`](#ge.status.planning_statuses)(owner)                           | The statuses available to an owner's repositories, in display order, as `[{'id', 'name', 'category', 'state', 'state_reason'}]` (`id` is the GraphQL node id); `None` when issue statuses are not available to that owner, or cannot be read. |
| [`set_issue_status`](#ge.status.set_issue_status)(repo, number, status, \*[, ...])  | Set an issue's status; GitHub closes or reopens it to match.                                                                                                                                                                                  |
| [`status_category`](#ge.status.status_category)(issue)                             | The status's category key in a REST or GraphQL issue payload, or `None`.                                                                                                                                                                      |
| [`status_name`](#ge.status.status_name)(issue)                                 | The status name in a REST or GraphQL issue payload, or `None`.                                                                                                                                                                                |
| [`status_query`](#ge.status.status_query)(status, \*[, statuses])               | The search qualifier for one status (exact name, quoted).                                                                                                                                                                                     |

### ge.status.CLAIM_CATEGORY *= 'started'*

someone is working on the issue.
GitHub advises matching statuses by category key or id rather than by name.

* **Type:**
  The category of In progress and In review

### ge.status.ISSUE_STATUSES *= ('Backlog', 'Todo', 'In progress', 'In review', 'Done', 'Not planned', 'Duplicate')*

GitHub’s status names, in display order. The set is fixed by GitHub during
the preview; [`planning_statuses()`](#ge.status.planning_statuses) reads the live set for one owner.

### ge.status.SEARCH_RESULT_CAP *= 1000*

GitHub’s search API serves at most this many results per query.

### ge.status.is_claimed(issue)

Whether the issue’s status says someone is working on it (In progress or
In review: category `started`).

* **Return type:**
  [`bool`](https://docs.python.org/3/builtins/functions.html#bool)

### ge.status.issue_status(repo, number)

The issue’s status name, or `None` when it has none or statuses are
not available for this repository.

```pycon
>>> # issue_status('owner/repo', 42)  # -> 'In progress'
```

* **Return type:**
  [`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

### ge.status.issues_with_status(status, , repo=None, owner=None, extra_query='', limit=100, statuses=('Backlog', 'Todo', 'In progress', 'In review', 'Done', 'Not planned', 'Duplicate'))

Yield issues in one status, across a repository or a whole owner.

Each item is `{'repo', 'number', 'title', 'url', 'status', 'state',
'updated_at', 'assignees', 'labels'}`, most recently updated first.
`extra_query` adds search terms (`'label:bug'`, `'updated:<2026-11-01'`).
At most `SEARCH_RESULT_CAP` results are reachable through search.

```pycon
>>> # list(issues_with_status('In progress', owner='octocat'))
```

* **Return type:**
  [`Iterator`](https://docs.python.org/3/library/typing.html#typing.Iterator)[[`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)]

### ge.status.normalize_status(name, , statuses=('Backlog', 'Todo', 'In progress', 'In review', 'Done', 'Not planned', 'Duplicate'))

Return the exact status name GitHub expects for a loosely spelled one.

Case, hyphens and underscores are ignored (`in-progress`, `NOT_PLANNED`).

```pycon
>>> normalize_status('not_planned')
'Not planned'
>>> normalize_status('doing')
Traceback (most recent call last):
  ...
ValueError: Unknown issue status 'doing'. Valid: Backlog, Todo, In progress, In review, Done, Not planned, Duplicate
```

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### ge.status.planning_statuses(owner)

The statuses available to an owner’s repositories, in display order, as
`[{'id', 'name', 'category', 'state', 'state_reason'}]` (`id` is the
GraphQL node id); `None` when issue statuses are not available to that
owner, or cannot be read.

* **Return type:**
  [`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`list`](https://docs.python.org/3/builtins/stdtypes.html#list)]

### ge.status.set_issue_status(repo, number, status, , duplicate_of=None, statuses=('Backlog', 'Todo', 'In progress', 'In review', 'Done', 'Not planned', 'Duplicate'))

Set an issue’s status; GitHub closes or reopens it to match.

Returns `{'number', 'state', 'state_reason', 'status'}` as GitHub now
reports them. `Duplicate` needs `duplicate_of` (the original issue’s
number in the same repository). Raises `RuntimeError` when GitHub did not
apply it (issue statuses unavailable in that repository).

Setting an open status on a closed issue reopens it: check the state first
if that is not what you want.

```pycon
>>> # set_issue_status('owner/repo', 42, 'In progress')
```

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### ge.status.status_category(issue)

The status’s category key in a REST or GraphQL issue payload, or `None`.

```pycon
>>> status_category({'status': {'name': 'In review', 'category': 'started', 'id': 8}})
'started'
>>> status_category({'status': {'name': 'Duplicate', 'category': {'key': 'duplicate'}}})
'duplicate'
```

* **Return type:**
  [`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

### ge.status.status_name(issue)

The status name in a REST or GraphQL issue payload, or `None`.

```pycon
>>> status_name({'status': {'name': 'Todo', 'category': 'planned', 'id': 3}})
'Todo'
>>> status_name({'state': 'open'}) is None
True
```

* **Return type:**
  [`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

### ge.status.status_query(status, , statuses=('Backlog', 'Todo', 'In progress', 'In review', 'Done', 'Not planned', 'Duplicate'))

The search qualifier for one status (exact name, quoted).

GitHub’s search accepts only the exact status name (any case) here, not the
category key and not a comma list; `no:status` finds issues without one.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)
