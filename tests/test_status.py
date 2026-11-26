"""Tests for ge.status (GitHub's native issue statuses) and the gh_api GET fix."""

import json
from unittest.mock import MagicMock, patch

import pytest

from ge import status as st
from ge.util import gh_api


class TestNormalize:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("backlog", "Backlog"),
            ("TODO", "Todo"),
            ("in-progress", "In progress"),
            ("in_review", "In review"),
            ("  In   Progress ", "In progress"),
            ("not planned", "Not planned"),
            ("Duplicate", "Duplicate"),
        ],
    )
    def test_spellings(self, raw, expected):
        assert st.normalize_status(raw) == expected

    def test_unknown_lists_valid_names(self):
        with pytest.raises(ValueError, match="Valid: Backlog, Todo"):
            st.normalize_status("blocked")

    def test_custom_status_set_is_a_seam(self):
        assert st.status_query("testing", statuses=("Testing",)) == 'status:"Testing"'
        with pytest.raises(ValueError):
            st.status_query("testing")

    def test_status_query_quotes_exact_name(self):
        assert st.status_query("in-progress") == 'status:"In progress"'


class TestRead:
    def test_status_name_rest_payload(self):
        issue = {"status": {"category": "started", "id": 4, "name": "In progress"}}
        assert st.status_name(issue) == "In progress"

    def test_claim_is_by_category(self):
        assert st.is_claimed({"status": {"name": "In review", "category": "started"}})
        assert st.is_claimed({"status": {"name": "Renamed", "category": {"key": "started"}}})
        assert not st.is_claimed({"status": {"name": "Todo", "category": "planned"}})
        assert not st.is_claimed({"status": None})

    def test_status_name_absent_or_null(self):
        assert st.status_name({"state": "open"}) is None
        assert st.status_name({"status": None}) is None

    def test_issue_status(self):
        with patch("ge.status.gh_api", return_value={"status": {"name": "Todo"}}) as m:
            assert st.issue_status("o/r", 3) == "Todo"
        m.assert_called_once_with("repos/o/r/issues/3")


class TestSet:
    def test_patches_status_name(self):
        reply = {
            "number": 3,
            "state": "open",
            "state_reason": None,
            "status": {"name": "In progress", "category": "started", "id": 4},
        }
        with patch("ge.status.gh_api", return_value=reply) as m:
            out = st.set_issue_status("o/r", 3, "in-progress")
        m.assert_called_once_with(
            "repos/o/r/issues/3", method="PATCH", body={"status": "In progress"}
        )
        assert out == {
            "number": 3,
            "state": "open",
            "state_reason": None,
            "status": "In progress",
        }

    def test_not_applied_raises(self):
        reply = {"number": 3, "state": "open", "state_reason": None, "status": None}
        with patch("ge.status.gh_api", return_value=reply):
            with pytest.raises(RuntimeError, match="did not set"):
                st.set_issue_status("o/r", 3, "Todo")

    def test_duplicate_needs_original(self):
        with pytest.raises(ValueError, match="duplicate_of"):
            st.set_issue_status("o/r", 3, "Duplicate")

    def test_duplicate_of_only_with_duplicate(self):
        with pytest.raises(ValueError, match="only applies"):
            st.set_issue_status("o/r", 3, "Done", duplicate_of=2)

    def test_duplicate_goes_through_graphql(self):
        lookup = {
            "data": {
                "repository": {
                    "issue": {"id": "I_3"},
                    "original": {"id": "I_2"},
                    "planningStatuses": {
                        "nodes": [
                            {"id": "S_B", "name": "Backlog", "category": {"key": "backlog"}},
                            {"id": "S_D", "name": "Dupe", "category": {"key": "duplicate"}},
                        ]
                    },
                }
            }
        }
        mutated = {
            "data": {
                "setIssueStatus": {
                    "issue": {
                        "number": 3,
                        "state": "CLOSED",
                        "stateReason": "DUPLICATE",
                        "status": {"name": "Duplicate"},
                    }
                }
            }
        }
        with patch("ge.status.gh_api", side_effect=[lookup, mutated]) as m:
            out = st.set_issue_status("o/r", 3, "duplicate", duplicate_of=2)
        variables = m.call_args_list[1].kwargs["body"]["variables"]
        assert variables == {"issue": "I_3", "status": "S_D", "original": "I_2"}
        assert out == {
            "number": 3,
            "state": "closed",
            "state_reason": "duplicate",
            "status": "Duplicate",
        }


class TestPlanningStatuses:
    def test_unreadable_is_none(self):
        with patch("ge.status.gh_api", side_effect=RuntimeError("gh api graphql failed")):
            assert st.planning_statuses("o") is None

    def test_not_available(self):
        reply = {"data": {"repositoryOwner": {"planningStatuses": None}}}
        with patch("ge.status.gh_api", return_value=reply):
            assert st.planning_statuses("someone") is None

    def test_available(self):
        node = {
            "id": "S_F",
            "name": "Done",
            "category": {"key": "completed", "state": "CLOSED", "stateReason": "COMPLETED"},
        }
        reply = {"data": {"repositoryOwner": {"planningStatuses": {"nodes": [node]}}}}
        with patch("ge.status.gh_api", return_value=reply):
            assert st.planning_statuses("o") == [
                {"id": "S_F", "name": "Done", "category": "completed", "state": "closed", "state_reason": "completed"}
            ]


def _item(n):
    return {
        "repository_url": "https://api.github.com/repos/o/r",
        "number": n,
        "title": f"t{n}",
        "html_url": f"https://github.com/o/r/issues/{n}",
        "status": {"name": "In progress"},
        "state": "open",
        "updated_at": "2026-11-26T00:00:00Z",
        "assignees": [{"login": "a"}],
        "labels": [{"name": "bug"}],
    }


class TestSearch:
    def test_query_and_shape(self):
        with patch("ge.status.gh_api", return_value={"items": [_item(1)]}) as m:
            out = list(st.issues_with_status("in progress", owner="o", extra_query="label:bug"))
        params = m.call_args.kwargs["params"]
        assert params["q"] == 'user:o is:issue status:"In progress" label:bug'
        assert params["sort"] == "updated"
        assert out[0]["repo"] == "o/r" and out[0]["status"] == "In progress"
        assert out[0]["assignees"] == ["a"] and out[0]["labels"] == ["bug"]

    def test_limit_and_paging(self):
        pages = [{"items": [_item(i) for i in range(2)]}, {"items": [_item(9)]}]
        with patch("ge.status.gh_api", side_effect=pages):
            out = list(st.issues_with_status("Todo", repo="o/r", limit=2))
        assert [x["number"] for x in out] == [0, 1]

    def test_stops_at_total_count_and_search_cap(self):
        page = {"total_count": 2, "items": [_item(1), _item(2)]}
        with patch("ge.status.gh_api", return_value=page) as m:
            out = list(st.issues_with_status("Todo", repo="o/r", limit=5000))
        assert len(out) == 2 and m.call_count == 1
        assert m.call_args.kwargs["params"]["per_page"] == "100"

    def test_exactly_one_scope(self):
        with pytest.raises(ValueError):
            list(st.issues_with_status("Todo"))
        with pytest.raises(ValueError):
            list(st.issues_with_status("Todo", repo="o/r", owner="o"))


class TestGhApiMethod:
    """A GET with fields must stay a GET (gh defaults to POST when fields are given)."""

    def _run(self, **kw):
        done = MagicMock(returncode=0, stdout=json.dumps({"ok": 1}), stderr="")
        with patch("ge.util._check_gh"), patch("ge.util.subprocess.run", return_value=done) as m:
            gh_api("search/issues", **kw)
        return m.call_args.args[0]

    def test_get_with_params_is_explicit(self):
        cmd = self._run(params={"q": "x"})
        assert cmd[cmd.index("-X") + 1] == "GET"

    def test_plain_get_has_no_method_flag(self):
        assert "-X" not in self._run()
