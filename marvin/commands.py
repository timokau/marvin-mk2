import os
import re
from typing import Any
from typing import Dict

from gidgethub import routing
from gidgethub import sansio
from gidgethub.aiohttp import GitHubAPI

from marvin import status
from marvin.command_router import CommandRouter
from marvin.status import set_issue_status

router = routing.Router()
command_router = CommandRouter([status.command_router])

BOT_NAME = os.environ.get("BOT_NAME", "marvin-mk2")

GREETING = f"""
Hi! I'm an experimental bot. My goal is to guide this PR through its stages, hopefully ending with a merge. You can read up on the usage [here](https://github.com/timokau/marvin-mk2/blob/deployed/USAGE.md).
""".rstrip()


async def handle_comment(
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
            await gh.post(
                issue["comments_url"], data={"body": GREETING}, oauth_token=token,
            )
        else:
            return

    for regex in command_router.command_handlers.keys():
        for _ in re.findall(regex, comment_text):
            await command_router.command_handlers[regex](
                gh=gh,
                token=token,
                issue=issue,
                pull_request_url=pull_request_url,
                comment=comment,
            )
            # Only handle one command for now, since a command can modify the issue and
            # we'd need to keep track of that.
            return


@router.register("issue_comment", action="created")
async def issue_comment_event(
    event: sansio.Event, gh: GitHubAPI, token: str, *args: Any, **kwargs: Any
) -> None:
    # Pull requests are issues, but issues are not pull requests. Theoretically
    # this event could be triggered by either, we only want to handle pull
    # requests.
    if "pull_request" in event.data["issue"]:
        await handle_comment(
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
    if event.data["review"]["state"] == "changes_requested":
        await set_issue_status(
            event.data["pull_request"], "awaiting_changes", gh, token
        )
    await handle_comment(
        event.data["review"],
        event.data["pull_request"],
        event.data["pull_request"]["url"],
        gh,
        token,
    )
