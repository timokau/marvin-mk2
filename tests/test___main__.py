from typing import Any
from typing import Dict
from typing import List
from typing import Tuple

from gidgethub import sansio

from marvin import __main__ as main


class GitHubAPIMock:
    def __init__(self) -> None:
        self.post_data: List[Tuple[str, Dict[str, Any]]] = []

    async def post(self, url: str, oauth_token: str, data: Dict[str, Any]) -> None:
        self.post_data.append((url, data))


async def test_adds_needs_review_label() -> None:
    data = {
        "action": "created",
        "issue": {
            "url": "issue-url",
            "pull_request": {"url": "pr-url"},
            "user": {"id": 42, "login": "somebody"},
            "labels": [{"name": "marvin"}],
        },
        "comment": {
            "body": "/status needs_review",
            "user": {"id": 42, "login": "somebody"},
        },
    }
    event = sansio.Event(data, event="issue_comment", delivery_id="1")
    gh = GitHubAPIMock()
    await main.router.dispatch(event, gh, token="fake-token")
    assert gh.post_data == [("issue-url/labels", {"labels": ["needs_review"]})]
