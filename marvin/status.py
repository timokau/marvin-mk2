from typing import Any
from typing import Dict

from gidgethub import routing
from gidgethub import sansio
from gidgethub.aiohttp import GitHubAPI

from marvin import gh_util
from marvin import triage_runner
from marvin.command_router import CommandRouter

router = routing.Router()
command_router = CommandRouter()

NO_SELF_REVIEW_TEXT = f"""
Sorry, you cannot set your own PR to `needs_merger` or `awaiting_merger`. Please wait for an external review. You may also actively search out a reviewer by pinging relevant people (look at the history of the files you're changing) or posting on discourse or IRC.
""".strip()


@router.register("pull_request", action="synchronize")
async def pull_request_synchronize(
    event: sansio.Event, gh: GitHubAPI, token: str, *args: Any, **kwargs: Any
) -> None:
    # Synchronize means that the PRs branch moved, invalidating previous reviews.
    if "needs_merger" in {
        label["name"] for label in event.data["pull_request"]["labels"]
    }:
        await gh_util.set_issue_status(
            event.data["pull_request"], "awaiting_reviewer", gh, token
        )


@router.register("pull_request_review_comment", action="created")
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
            await gh_util.set_issue_status(
                event.data["issue"], "awaiting_reviewer", gh, token
            )
    else:
        # A new comment by somebody else is likely a review asking for
        # clarification or changes (provided it doesn't explicitly contain a
        # status command).
        await gh_util.set_issue_status(
            event.data["issue"], "awaiting_changes", gh, token
        )


@router.register("pull_request_review", action="submitted")
async def pull_request_review_submitted_event(
    event: sansio.Event, gh: GitHubAPI, token: str, *args: Any, **kwargs: Any
) -> None:
    if len(command_router.find_commands(event.data["review"]["body"])) > 0:
        return
    if event.data["review"]["state"] == "changes_requested":
        await gh_util.set_issue_status(
            event.data["pull_request"], "awaiting_changes", gh, token
        )


@command_router.register_command("/status needs_reviewer")
async def needs_reviewer_command(
    gh: GitHubAPI, event: sansio.Event, token: str, issue: Dict[str, Any], **kwargs: Any
) -> None:
    await gh_util.set_issue_status(issue, "needs_reviewer", gh, token)
    triage_runner.runners[event.data["installation"]["id"]].run_soon(gh, token)


@command_router.register_command("/status awaiting_changes")
async def awaiting_changes_command(
    gh: GitHubAPI, token: str, issue: Dict[str, Any], **kwargs: Any
) -> None:
    await gh_util.set_issue_status(issue, "awaiting_changes", gh, token)


@command_router.register_command("/status awaiting_reviewer")
async def awaiting_reviewer_command(
    gh: GitHubAPI, token: str, issue: Dict[str, Any], **kwargs: Any
) -> None:
    await gh_util.set_issue_status(issue, "awaiting_reviewer", gh, token)


@command_router.register_command("/status needs_merger")
async def needs_merger_command(
    gh: GitHubAPI,
    token: str,
    event: sansio.Event,
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
        await gh_util.set_issue_status(issue, "needs_merger", gh, token)
        triage_runner.runners[event.data["installation"]["id"]].run_soon(gh, token)


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
        await gh_util.set_issue_status(issue, "awaiting_merger", gh, token)
