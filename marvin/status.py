from typing import Any
from typing import Dict

from gidgethub import routing
from gidgethub import sansio
from gidgethub.aiohttp import GitHubAPI

router = routing.Router()

# List of mutually exclusive status labels
ISSUE_STATUS_LABELS = {"awaiting_reviewer", "awaiting_changes", "needs_merger"}


async def set_issue_status(
    issue: Dict[str, Any], status: str, gh: GitHubAPI, token: str
) -> None:
    """Sets the status of an issue while resetting other status labels"""
    assert status in ISSUE_STATUS_LABELS

    # depending on whether the issue is actually a pull request
    issue_url = issue.get("issue_url", issue["url"])

    # Labels are mutually exclusive, so clear other labels first.
    labels = issue["labels"]
    label_names = {label["name"] for label in labels}
    # should never be more than one, but better to make it a set anyway
    status_labels = label_names.intersection(ISSUE_STATUS_LABELS)
    for label in status_labels:
        if label == status:  # Don't touch the label we're supposed to set.
            continue
        await gh.delete(issue_url + "/labels/" + label, oauth_token=token)

    if status not in status_labels:
        await gh.post(
            issue_url + "/labels", data={"labels": [status]}, oauth_token=token,
        )


@router.register("pull_request", action="synchronize")
async def pull_request_synchronize(
    event: sansio.Event, gh: GitHubAPI, token: str, *args: Any, **kwargs: Any
) -> None:
    # Synchronize means that the PRs branch moved, invalidating previous reviews.
    if "needs_merger" in {
        label["name"] for label in event.data["pull_request"]["labels"]
    }:
        await set_issue_status(
            event.data["pull_request"], "awaiting_reviewer", gh, token
        )
