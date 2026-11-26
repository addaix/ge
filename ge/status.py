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

CLAIM_CATEGORY = "started"
"""The category of In progress and In review: someone is working on the issue.
GitHub advises matching statuses by category key or id rather than by name."""


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


def status_query(status: str, *, statuses=ISSUE_STATUSES) -> str:
    """The search qualifier for one status (exact name, quoted).

    GitHub's search accepts only the exact status name (any case) here, not the
    category key and not a comma list; ``no:status`` finds issues without one.
    """
    return f'status:"{normalize_status(status, statuses=statuses)}"'


def issue_status(repo, number) -> Optional[str]:
    """The issue's status name, or ``None`` when it has none or statuses are
    not available for this repository.

    >>> # issue_status('owner/repo', 42)  # -> 'In progress'
    """
    owner, name = parse_repo_spec(repo)
    issue = gh_api(f"repos/{owner}/{name}/issues/{number}")
    return status_name(issue)


def status_category(issue) -> Optional[str]:
    """The status's category key in a REST or GraphQL issue payload, or ``None``.

    >>> status_category({'status': {'name': 'In review', 'category': 'started', 'id': 8}})
    'started'
    >>> status_category({'status': {'name': 'Duplicate', 'category': {'key': 'duplicate'}}})
    'duplicate'
    """
    status = (issue or {}).get("status")
    category = status.get("category") if isinstance(status, dict) else None
    return category.get("key") if isinstance(category, dict) else category


def is_claimed(issue) -> bool:
    """Whether the issue's status says someone is working on it (In progress or
    In review: category ``started``)."""
    return status_category(issue) == CLAIM_CATEGORY


def status_name(issue) -> Optional[str]:
    """The status name in a REST or GraphQL issue payload, or ``None``.

    >>> status_name({'status': {'name': 'Todo', 'category': 'planned', 'id': 3}})
    'Todo'
    >>> status_name({'state': 'open'}) is None
    True
    """
    status = (issue or {}).get("status")
    return status.get("name") if isinstance(status, dict) else None


def set_issue_status(
    repo, number, status, *, duplicate_of=None, statuses=ISSUE_STATUSES
) -> dict:
    """Set an issue's status; GitHub closes or reopens it to match.

    Returns ``{'number', 'state', 'state_reason', 'status'}`` as GitHub now
    reports them. ``Duplicate`` needs ``duplicate_of`` (the original issue's
    number in the same repository). Raises ``RuntimeError`` when GitHub did not
    apply it (issue statuses unavailable in that repository).

    Setting an open status on a closed issue reopens it: check the state first
    if that is not what you want.

    >>> # set_issue_status('owner/repo', 42, 'In progress')
    """
    owner, name = parse_repo_spec(repo)
    status = normalize_status(status, statuses=statuses)
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
    summary = _summary(issue)
    if summary["status"] != status:
        raise RuntimeError(
            f"GitHub did not set {owner}/{name}#{number} to {status!r} "
            f"(it reports {summary['status']!r}): issue statuses may be unavailable there"
        )
    return summary


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
    planningStatuses(first: 20) { nodes { id name category { key } } }
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
    status_id = next(
        (s["id"] for s in statuses if s["category"]["key"] == "duplicate"), None
    )
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
    ``[{'id', 'name', 'category', 'state', 'state_reason'}]`` (``id`` is the
    GraphQL node id); ``None`` when issue statuses are not available to that
    owner, or cannot be read."""
    query = """
    query($owner: String!) {
      repositoryOwner(login: $owner) {
        ... on Organization { planningStatuses(first: 20) { ...S } }
        ... on User { planningStatuses(first: 20) { ...S } }
      }
    }
    fragment S on PlanningStatusConnection {
      nodes { id name category { key state stateReason } }
    }
    """
    try:
        owner_data = _graphql(query, owner=owner)["repositoryOwner"] or {}
    except RuntimeError:
        return None
    statuses = owner_data.get("planningStatuses")
    if statuses is None:
        return None
    return [
        {
            "id": n["id"],
            "name": n["name"],
            "category": n["category"]["key"],
            "state": n["category"]["state"].lower(),
            "state_reason": (n["category"]["stateReason"] or "").lower() or None,
        }
        for n in statuses["nodes"]
    ]


SEARCH_RESULT_CAP = 1000
"""GitHub's search API serves at most this many results per query."""


def issues_with_status(
    status,
    *,
    repo=None,
    owner=None,
    extra_query="",
    limit=100,
    statuses=ISSUE_STATUSES,
) -> Iterator[dict]:
    """Yield issues in one status, across a repository or a whole owner.

    Each item is ``{'repo', 'number', 'title', 'url', 'status', 'state',
    'updated_at', 'assignees', 'labels'}``, most recently updated first.
    ``extra_query`` adds search terms (``'label:bug'``, ``'updated:<2026-11-01'``).
    At most ``SEARCH_RESULT_CAP`` results are reachable through search.

    >>> # list(issues_with_status('In progress', owner='octocat'))
    """
    if (repo is None) == (owner is None):
        raise ValueError("Pass exactly one of repo= or owner=")
    scope = f"repo:{'/'.join(parse_repo_spec(repo))}" if repo else f"user:{owner}"
    q = " ".join(
        x
        for x in (
            scope,
            "is:issue",
            status_query(status, statuses=statuses),
            extra_query,
        )
        if x
    )
    limit = min(limit, SEARCH_RESULT_CAP)
    per_page = max(1, min(100, limit))
    seen = 0
    page = 1
    while seen < limit:
        out = gh_api(
            "search/issues",
            params={
                "q": q,
                "sort": "updated",
                "order": "desc",
                "per_page": str(per_page),
                "page": str(page),
            },
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
        total = out.get("total_count")
        if len(items) < per_page or (total is not None and seen >= total):
            return
        page += 1
