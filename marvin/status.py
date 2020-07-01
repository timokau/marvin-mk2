from typing import Any
from typing import Dict

from gidgethub import routing
from gidgethub import sansio
from gidgethub.aiohttp import GitHubAPI

from marvin.command_router import CommandRouter
from marvin.gh_util import request_review
from marvin.team import get_reviewer

router = routing.Router()
command_router = CommandRouter()

# List of mutually exclusive status labels
ISSUE_STATUS_LABELS = {
    "needs_reviewer",
    "awaiting_reviewer",
    "awaiting_changes",
    "needs_merger",
    "awaiting_merger",
}

NO_SELF_REVIEW_TEXT = f"""
Sorry, you cannot set your own PR to `needs_merger` or `awaiting_merger`. Please wait for an external review. You may also actively search out a reviewer by pinging relevant people (look at the history of the files you're changing) or posting on discourse or IRC.
""".strip()


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


@router.register("issue_comment", action="created")
async def issue_comment_event(
    event: sansio.Event, gh: GitHubAPI, token: str, *args: Any, **kwargs: Any
) -> None:
    # If the command issues an explicit command, that should override default
    # behaviour.
    if len(command_router.find_commands(event.data["comment"]["body"])) > 0:
        return

    by_pr_author = (
        event.data["issue"]["user"]["id"] == event.data["comment"]["user"]["id"]
    )
    if by_pr_author:
        label_names = {label["name"] for label in event.data["issue"]["labels"]}
        if "awaiting_changes" in label_names:
            # A new comment by the author is probably some justification or request
            # for clarification. Action of the reviewer is needed.
            await set_issue_status(event.data["issue"], "awaiting_reviewer", gh, token)
    else:
        # A new comment by somebody else is likely a review asking for
        # clarification or changes (provided it doesn't explicitly contain a
        # status command).
        await set_issue_status(event.data["issue"], "awaiting_changes", gh, token)


@command_router.register_command("/status needs_reviewer")
async def needs_reviewer_command(
    gh: GitHubAPI, token: str, issue: Dict[str, Any], **kwargs: Any
) -> None:
    await set_issue_status(issue, "needs_reviewer", gh, token)


@command_router.register_command("/status awaiting_changes")
async def awaiting_changes_command(
    gh: GitHubAPI, token: str, issue: Dict[str, Any], **kwargs: Any
) -> None:
    await set_issue_status(issue, "awaiting_changes", gh, token)


@command_router.register_command("/status awaiting_reviewer")
async def awaiting_reviewer_command(
    gh: GitHubAPI, token: str, issue: Dict[str, Any], **kwargs: Any
) -> None:
    await set_issue_status(issue, "awaiting_reviewer", gh, token)


@command_router.register_command("/status needs_merger")
async def needs_merger_command(
    gh: GitHubAPI,
    token: str,
    issue: Dict[str, Any],
    pull_request_url: str,
    comment: Dict[str, Any],
    **kwargs: Any,
) -> None:
    by_pr_author = issue["user"]["id"] == comment["user"]["id"]
    if by_pr_author:
        await gh.post(
            issue["comments_url"],
            data={"body": NO_SELF_REVIEW_TEXT},
            oauth_token=token,
        )
    else:
        await set_issue_status(issue, "needs_merger", gh, token)
        reviewer = await get_reviewer(gh, token, issue, merge_permission_needed=True)
        if reviewer is not None:
            print(f"Requesting review (merge) from {reviewer} for {pull_request_url}.")
            await request_review(pull_request_url, "timokau", gh, token)
        else:
            print(f"No reviewer found for {pull_request_url}.")


@command_router.register_command("/status awaiting_merger")
async def awaiting_merger_command(
    gh: GitHubAPI,
    token: str,
    issue: Dict[str, Any],
    comment: Dict[str, Any],
    **kwargs: Any,
) -> None:
    by_pr_author = issue["user"]["id"] == comment["user"]["id"]
    if by_pr_author:
        await gh.post(
            issue["comments_url"],
            data={"body": NO_SELF_REVIEW_TEXT},
            oauth_token=token,
        )
    else:
        await set_issue_status(issue, "awaiting_merger", gh, token)
