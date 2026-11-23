"""One smoke test against the real ``gh`` and a public repository (addaix/ge#23).

The rest of the suite patches ``gh``, so a change in ``gh``'s output would surface only in
use. This one runs the real thing. It is skipped unless ``GE_LIVE=1`` is set and ``gh`` is
installed and authenticated: ``GE_LIVE=1 pytest -m network``.
"""

import os
import shutil

import pytest

from ge.github import get_default_branch, get_issue

pytestmark = pytest.mark.network

#: A public repository and an issue in it that will not go away.
PUBLIC_REPO = "cli/cli"
PUBLIC_ISSUE = 1


@pytest.fixture(autouse=True)
def _live_only():
    if os.environ.get("GE_LIVE") != "1":
        pytest.skip("live gh smoke test: set GE_LIVE=1 to run")
    if shutil.which("gh") is None:
        pytest.skip("gh is not installed")


def test_get_issue_has_the_fields_ge_reads():
    issue = get_issue(PUBLIC_REPO, PUBLIC_ISSUE)
    assert issue["number"] == PUBLIC_ISSUE
    for field in ("title", "body", "state", "labels", "user"):
        assert field in issue


def test_get_default_branch_is_a_name():
    assert isinstance(get_default_branch(PUBLIC_REPO), str)
