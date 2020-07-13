from typing import Any
from typing import Dict
from typing import List
from typing import Tuple

from gidgethub import sansio

from marvin import __main__ as main


class GitHubAPIMock:
    def __init__(self) -> None:
        self.post_data: List[Tuple[str, Dict[str, Any]]] = []
        self.delete_urls: List[str] = []

    async def post(self, url: str, oauth_token: str, data: Dict[str, Any]) -> None:
        self.post_data.append((url, data))

    async def delete(self, url: str, oauth_token: str) -> None:
        self.delete_urls.append(url)


async def test_adds_awaiting_reviewer_label() -> None:
    data = {
        "action": "created",
        "issue": {
            "url": "issue-url",
            "pull_request": {"url": "pr-url"},
            "user": {"id": 42, "login": "somebody"},
            "labels": [{"name": "marvin"}],
        },
        "comment": {
            "body": "/status awaiting_reviewer",
            "user": {"id": 42, "login": "somebody"},
        },
    }
    event = sansio.Event(data, event="issue_comment", delivery_id="1")
    gh = GitHubAPIMock()
    await main.router.dispatch(event, gh, token="fake-token")
    assert gh.post_data == [("issue-url/labels", {"labels": ["awaiting_reviewer"]})]


async def test_removes_old_status_labels_on_new_status() -> None:
    data = {
        "action": "created",
        "issue": {
            "url": "issue-url",
            "pull_request": {"url": "pr-url"},
            "user": {"id": 42, "login": "somebody"},
            "labels": [
                {"name": "marvin"},
                {"name": "awaiting_changes"},
                {"name": "needs_merger"},
            ],
        },
        "comment": {
            "body": "/status awaiting_reviewer",
            "user": {"id": 42, "login": "somebody"},
        },
    }
    event = sansio.Event(data, event="issue_comment", delivery_id="1")
    gh = GitHubAPIMock()
    await main.router.dispatch(event, gh, token="fake-token")
    assert gh.post_data == [("issue-url/labels", {"labels": ["awaiting_reviewer"]})]
    assert set(gh.delete_urls) == {
        "issue-url/labels/needs_merger",
        "issue-url/labels/awaiting_changes",
    }


async def test_sets_awaiting_changes_to_awaiting_review_on_author_comment() -> None:
    data = {
        "action": "created",
        "issue": {
            "url": "issue-url",
            "pull_request": {"url": "pr-url"},
            "user": {"id": 42, "login": "author"},
            "labels": [{"name": "marvin"}, {"name": "awaiting_changes"}],
        },
        "comment": {
            "body": "The body is irrelevant.",
            "user": {"id": 42, "login": "author"},
        },
    }
    event = sansio.Event(data, event="issue_comment", delivery_id="1")
    gh = GitHubAPIMock()
    await main.router.dispatch(event, gh, token="fake-token")
    assert gh.post_data == [("issue-url/labels", {"labels": ["awaiting_reviewer"]})]
    assert set(gh.delete_urls) == {
        "issue-url/labels/awaiting_changes",
    }


async def test_does_not_modify_needs_merge_on_author_comment() -> None:
    data = {
        "action": "created",
        "issue": {
            "url": "issue-url",
            "pull_request": {"url": "pr-url"},
            "user": {"id": 42, "login": "author"},
            "labels": [{"name": "marvin"}, {"name": "needs_merge"}],
        },
        "comment": {
            "body": "The body is irrelevant.",
            "user": {"id": 42, "login": "author"},
        },
    }
    event = sansio.Event(data, event="issue_comment", delivery_id="1")
    gh = GitHubAPIMock()
    await main.router.dispatch(event, gh, token="fake-token")
    assert gh.post_data == []
    assert gh.delete_urls == []


async def test_does_not_crash_on_empty_pull_request_summary() -> None:
    data = {
        "action": "submitted",
        "pull_request": {
            "url": "pr-url",
            "user": {"id": 42, "login": "somebody"},
            "labels": [{"name": "marvin"}, {"name": "needs_merger"}],
        },
        "review": {
            "body": None,
            "state": "changes_requested",
            "user": {"id": 42, "login": "somebody"},
        },
    }
    event = sansio.Event(data, event="pull_request_review", delivery_id="1")
    gh = GitHubAPIMock()
    await main.router.dispatch(event, gh, token="fake-token")
    assert gh.post_data == [("pr-url/labels", {"labels": ["awaiting_changes"]})]
    assert set(gh.delete_urls) == {
        "pr-url/labels/needs_merger",
    }


async def test_sets_to_awaiting_reviewer_on_comment() -> None:
    data = {
        "action": "created",
        "issue": {
            "url": "issue-url",
            "pull_request": {"url": "pr-url"},
            "user": {"id": 42, "login": "author"},
            "labels": [{"name": "marvin"}, {"name": "needs_reviewer"}],
        },
        "comment": {
            "body": "The body is irrelevant.",
            "user": {"id": 43, "login": "non-author"},
        },
    }
    event = sansio.Event(data, event="issue_comment", delivery_id="1")
    gh = GitHubAPIMock()
    await main.router.dispatch(event, gh, token="fake-token")
    assert gh.post_data == [("issue-url/labels", {"labels": ["awaiting_reviewer"]})]
    assert set(gh.delete_urls) == {
        "issue-url/labels/needs_reviewer",
    }


async def test_sets_to_awaiting_reviewer_on_assigned() -> None:
    data = {
        "action": "assigned",
        "pull_request": {
            "url": "pr-url",
            "user": {"id": 42, "login": "author"},
            "labels": [{"name": "marvin"}, {"name": "needs_reviewer"}],
        },
    }
    event = sansio.Event(data, event="pull_request", delivery_id="1")
    gh = GitHubAPIMock()
    await main.router.dispatch(event, gh, token="fake-token")
    assert gh.post_data == [("pr-url/labels", {"labels": ["awaiting_reviewer"]})]
    assert set(gh.delete_urls) == {
        "pr-url/labels/needs_reviewer",
    }


async def test_sets_to_awaiting_reviewer_on_review_requested() -> None:
    data = {
        "action": "review_requested",
        "pull_request": {
            "url": "pr-url",
            "user": {"id": 42, "login": "author"},
            "labels": [{"name": "marvin"}, {"name": "needs_reviewer"}],
        },
    }
    event = sansio.Event(data, event="pull_request", delivery_id="1")
    gh = GitHubAPIMock()
    await main.router.dispatch(event, gh, token="fake-token")
    assert gh.post_data == [("pr-url/labels", {"labels": ["awaiting_reviewer"]})]
    assert set(gh.delete_urls) == {
        "pr-url/labels/needs_reviewer",
    }


async def test_sets_to_awaiting_reviewer_on_review_submitted() -> None:
    data = {
        "action": "submitted",
        "pull_request": {
            "url": "pr-url",
            "user": {"id": 42, "login": "author"},
            "labels": [{"name": "marvin"}, {"name": "needs_reviewer"}],
        },
        "review": {
            "body": None,
            "state": "comment",
            "user": {"id": 43, "login": "non-author"},
        },
    }
    event = sansio.Event(data, event="pull_request_review", delivery_id="1")
    gh = GitHubAPIMock()
    await main.router.dispatch(event, gh, token="fake-token")
    assert gh.post_data == [("pr-url/labels", {"labels": ["awaiting_reviewer"]})]
    assert set(gh.delete_urls) == {
        "pr-url/labels/needs_reviewer",
    }


async def test_sets_to_needs_reviewer_when_marked_as_ready() -> None:
    data = {
        "action": "ready_for_review",
        "pull_request": {
            "url": "pr-url",
            "user": {"id": 42, "login": "somebody"},
            "labels": [{"name": "marvin"}, {"name": "awaiting_changes"}],
        },
        "review": {
            "body": None,
            "state": "changes_requested",
            "user": {"id": 42, "login": "somebody"},
        },
    }
    event = sansio.Event(data, event="pull_request", delivery_id="1")
    gh = GitHubAPIMock()
    await main.router.dispatch(event, gh, token="fake-token")
    assert gh.post_data == [("pr-url/labels", {"labels": ["needs_reviewer"]})]
    assert set(gh.delete_urls) == {
        "pr-url/labels/awaiting_changes",
    }
