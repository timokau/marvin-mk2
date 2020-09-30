import os
from typing import Any
from typing import Dict

from gidgethub import routing
from gidgethub import sansio
from gidgethub.aiohttp import GitHubAPI

from marvin import gh_util
from marvin import status
from marvin import triage
from marvin.command_router import CommandRouter

router = routing.Router()
command_router = CommandRouter([status.command_router, triage.command_router])

BOT_NAME = os.environ.get("BOT_NAME", "marvin-mk2")

GREETING = f"""
Hi! I'm an experimental bot. My goal is to guide this PR through its stages, hopefully ending with a merge. You can read up on the usage [here](https://github.com/timokau/marvin-mk2/blob/deployed/USAGE.md).
""".rstrip()


async def handle_comment(
    event: sansio.Event,
    comment: Dict[str, Any],
    issue: Dict[str, Any],
    pull_request_url: str,
    gh: GitHubAPI,
    token: str,
) -> None:
    """React to issue comments"""
    comment_text = comment["body"]
    by_pr_author = issue["user"]["id"] == comment["user"]["id"]

    # check opt-in
    pr_labels = {label["name"] for label in issue["labels"]}
    if "marvin" not in pr_labels:
        if by_pr_author and "marvin opt-in" in comment_text:
            issue_url = issue.get("issue_url", issue["url"])
            await gh.post(
                issue_url + "/labels", data={"labels": ["marvin"]}, oauth_token=token,
            )
            await gh_util.post_comment(gh, token, issue["comments_url"], GREETING)
        else:
            return

    for command in command_router.find_commands(comment_text):
        await command_router.command_handlers[command](
            gh=gh,
            token=token,
            event=event,
            issue=issue,
            pull_request_url=pull_request_url,
            comment=comment,
        )
        # Only handle one command for now, since a command can modify the issue and
        # we'd need to keep track of that.
        return


@router.register("pull_request", action="opened")
async def pull_request_opened_event(
    event: sansio.Event, gh: GitHubAPI, token: str, *args: Any, **kwargs: Any
) -> None:
    await handle_comment(
        event,
        event.data["pull_request"],
        event.data["pull_request"],
        event.data["pull_request"]["url"],
        gh,
        token,
    )


@router.register("issue_comment", action="created")
async def issue_comment_event(
    event: sansio.Event, gh: GitHubAPI, token: str, *args: Any, **kwargs: Any
) -> None:
    # Pull requests are issues, but issues are not pull requests. Theoretically
    # this event could be triggered by either, we only want to handle pull
    # requests.
    if "pull_request" in event.data["issue"]:
        await handle_comment(
            event,
            event.data["comment"],
            event.data["issue"],
            event.data["issue"]["pull_request"]["url"],
            gh,
            token,
        )


@router.register("pull_request_review_comment", action="created")
async def pull_request_review_comment_event(
    event: sansio.Event, gh: GitHubAPI, token: str, *args: Any, **kwargs: Any
) -> None:
    await handle_comment(
        event,
        event.data["comment"],
        event.data["pull_request"],
        event.data["pull_request"]["url"],
        gh,
        token,
    )


@router.register("pull_request_review", action="submitted")
async def pull_request_review_submitted_event(
    event: sansio.Event, gh: GitHubAPI, token: str, *args: Any, **kwargs: Any
) -> None:
    # Pull request reviews may or may not have a comment.
    if event.data["review"]["body"] is not None:
        await handle_comment(
            event,
            event.data["review"],
            event.data["pull_request"],
            event.data["pull_request"]["url"],
            gh,
            token,
        )
