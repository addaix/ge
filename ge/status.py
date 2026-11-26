"""GitHub's native issue statuses: read, set and search them.

GitHub issues carry a *status* (public preview since 2026-11-23): one of a fixed
set, each in a *category* that decides whether the issue is open or closed.

=============  ===========  ======  ============
Status         Category     State   State reason
=============  ===========  ======  ============
Backlog        backlog      open
Todo           planned      open
In progress    started      open
In review      started      open
Done           completed    closed  completed
Not planned    not_planned  closed  not_planned
Duplicate      duplicate    closed  duplicate
=============  ===========  ======  ============

Setting a closed status closes the issue and setting an open one reopens it, so
the status is the single field to write. GitHub also moves it on its own:
assigning a person moves Backlog to Todo, linking a draft PR moves it to In
progress, linking an open PR (or marking the draft ready) moves it to In review,
closing moves it to Done, and **reopening resets it to Backlog**.

Everything goes through the ``gh`` CLI (REST ``status`` field; GraphQL only for
Duplicate, which needs the original issue). Where statuses are not available
(the preview has not reached that repository, or the viewer cannot see them),
:func:`issue_status` returns ``None`` and callers fall back on open/closed.

>>> normalize_status('in-progress')
'In progress'
>>> normalize_status('TODO')
'Todo'
>>> status_query('In progress')
'status:"In progress"'
"""

from typing import Iterator, Optional

from ge.util import gh_api, parse_repo_spec

ISSUE_STATUSES = (
    "Backlog",
    "Todo",
    "In progress",
    "In review",
    "Done",
    "Not planned",
    "Duplicate",
)
"""GitHub's status names, in display order. The set is fixed by GitHub during
the preview; :func:`planning_statuses` reads the live set for one owner."""

OPEN_STATUSES = ISSUE_STATUSES[:4]
CLOSED_STATUSES = ISSUE_STATUSES[4:]


def _key(name: str) -> str:
    return " ".join(name.replace("-", " ").replace("_", " ").split()).lower()


_BY_KEY = {_key(s): s for s in ISSUE_STATUSES}


def normalize_status(name: str, *, statuses=ISSUE_STATUSES) -> str:
    """Return the exact status name GitHub expects for a loosely spelled one.

    Case, hyphens and underscores are ignored (``in-progress``, ``NOT_PLANNED``).

    >>> normalize_status('not_planned')
    'Not planned'
    >>> normalize_status('doing')
    Traceback (most recent call last):
      ...
    ValueError: Unknown issue status 'doing'. Valid: Backlog, Todo, In progress, In review, Done, Not planned, Duplicate
    """
    by_key = _BY_KEY if statuses is ISSUE_STATUSES else {_key(s): s for s in statuses}
    try:
        return by_key[_key(name)]
    except KeyError:
        raise ValueError(
            f"Unknown issue status {name!r}. Valid: {', '.join(statuses)}"
        ) from None


def status_query(status: str) -> str:
    """The search qualifier for one status (exact name, quoted).

    GitHub's search accepts only the exact status name (any case) here, not the
    category key and not a comma list; ``no:status`` finds issues without one.
    """
    return f'status:"{normalize_status(status)}"'


def issue_status(repo, number) -> Optional[str]:
    """The issue's status name, or ``None`` when it has none or statuses are
    not available for this repository.

    >>> # issue_status('owner/repo', 42)  # -> 'In progress'
    """
    owner, name = parse_repo_spec(repo)
    issue = gh_api(f"repos/{owner}/{name}/issues/{number}")
    return status_name(issue)


def status_name(issue) -> Optional[str]:
    """The status name in a REST or GraphQL issue payload, or ``None``.

    >>> status_name({'status': {'name': 'Todo', 'category': 'planned', 'id': 3}})
    'Todo'
    >>> status_name({'state': 'open'}) is None
    True
    """
    status = (issue or {}).get("status")
    return status.get("name") if isinstance(status, dict) else None


def set_issue_status(repo, number, status, *, duplicate_of=None) -> dict:
    """Set an issue's status; GitHub closes or reopens it to match.

    Returns ``{'number', 'state', 'state_reason', 'status'}`` as GitHub now
    reports them. ``Duplicate`` needs ``duplicate_of`` (the original issue's
    number in the same repository).

    >>> # set_issue_status('owner/repo', 42, 'In progress')
    """
    owner, name = parse_repo_spec(repo)
    status = normalize_status(status)
    if status == "Duplicate":
        if duplicate_of is None:
            raise ValueError(
                "Status 'Duplicate' needs duplicate_of=<number of the original issue>"
            )
        return _set_duplicate(owner, name, number, duplicate_of)
    if duplicate_of is not None:
        raise ValueError("duplicate_of only applies to status 'Duplicate'")
    issue = gh_api(
        f"repos/{owner}/{name}/issues/{number}", method="PATCH", body={"status": status}
    )
    return _summary(issue)


def _summary(issue) -> dict:
    return {
        "number": issue.get("number"),
        "state": issue.get("state"),
        "state_reason": issue.get("state_reason"),
        "status": status_name(issue),
    }


_DUPLICATE_STATUS_QUERY = """
query($owner: String!, $name: String!, $number: Int!, $original: Int!) {
  repository(owner: $owner, name: $name) {
    issue(number: $number) { id }
    original: issue(number: $original) { id }
    planningStatuses(first: 20) { nodes { id name } }
  }
}
"""

_SET_STATUS_MUTATION = """
mutation($issue: ID!, $status: ID!, $original: ID) {
  setIssueStatus(input: {issueId: $issue, statusId: $status, duplicateIssueId: $original}) {
    issue { number state stateReason status { name } }
  }
}
"""


def _graphql(query, **variables) -> dict:
    out = gh_api(
        "graphql", method="POST", body={"query": query, "variables": variables}
    )
    if out.get("errors"):
        raise RuntimeError(f"GraphQL error: {out['errors']}")
    return out["data"]


def _set_duplicate(owner, name, number, original) -> dict:
    repo = _graphql(
        _DUPLICATE_STATUS_QUERY,
        owner=owner,
        name=name,
        number=int(number),
        original=int(original),
    )["repository"]
    statuses = (repo.get("planningStatuses") or {}).get("nodes") or []
    status_id = next((s["id"] for s in statuses if s["name"] == "Duplicate"), None)
    if status_id is None:
        raise RuntimeError(f"Issue statuses are not available in {owner}/{name}")
    issue = _graphql(
        _SET_STATUS_MUTATION,
        issue=repo["issue"]["id"],
        status=status_id,
        original=repo["original"]["id"],
    )["setIssueStatus"]["issue"]
    return {
        "number": issue["number"],
        "state": issue["state"].lower(),
        "state_reason": (issue.get("stateReason") or "").lower() or None,
        "status": status_name(issue),
    }


def planning_statuses(owner) -> Optional[list]:
    """The statuses available to an owner's repositories, in display order, as
    ``[{'name', 'category', 'state', 'state_reason'}]``; ``None`` when issue
    statuses are not available to that owner."""
    query = """
    query($owner: String!) {
      repositoryOwner(login: $owner) {
        ... on Organization { planningStatuses(first: 20) { ...S } }
        ... on User { planningStatuses(first: 20) { ...S } }
      }
    }
    fragment S on PlanningStatusConnection {
      nodes { name category { key state stateReason } }
    }
    """
    owner_data = _graphql(query, owner=owner)["repositoryOwner"] or {}
    statuses = owner_data.get("planningStatuses")
    if statuses is None:
        return None
    return [
        {
            "name": n["name"],
            "category": n["category"]["key"],
            "state": n["category"]["state"].lower(),
            "state_reason": (n["category"]["stateReason"] or "").lower() or None,
        }
        for n in statuses["nodes"]
    ]


def issues_with_status(
    status, *, repo=None, owner=None, extra_query="", limit=100
) -> Iterator[dict]:
    """Yield issues in one status, across a repository or a whole owner.

    Each item is ``{'repo', 'number', 'title', 'url', 'status', 'state',
    'updated_at', 'assignees', 'labels'}``. ``extra_query`` adds search terms
    (``'label:manual-task'``, ``'updated:<2026-11-01'``).

    >>> # list(issues_with_status('In progress', owner='thorwhalen'))
    """
    if (repo is None) == (owner is None):
        raise ValueError("Pass exactly one of repo= or owner=")
    scope = f"repo:{'/'.join(parse_repo_spec(repo))}" if repo else f"user:{owner}"
    q = " ".join(x for x in (scope, "is:issue", status_query(status), extra_query) if x)
    per_page = min(100, limit)
    seen = 0
    page = 1
    while seen < limit:
        out = gh_api(
            "search/issues",
            params={"q": q, "per_page": str(per_page), "page": str(page)},
        )
        items = out.get("items", [])
        for it in items:
            yield {
                "repo": it["repository_url"].split("/repos/", 1)[-1],
                "number": it["number"],
                "title": it["title"],
                "url": it["html_url"],
                "status": status_name(it),
                "state": it["state"],
                "updated_at": it["updated_at"],
                "assignees": [a["login"] for a in it.get("assignees") or []],
                "labels": [l["name"] for l in it.get("labels") or []],
            }
            seen += 1
            if seen >= limit:
                return
        if len(items) < per_page:
            return
        page += 1
