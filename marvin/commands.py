import os
from typing import Any
from typing import Dict
from typing import List

from gidgethub import routing
from gidgethub import sansio
from gidgethub.aiohttp import GitHubAPI

from marvin.gh_util import request_review
from marvin.status import set_issue_status
from marvin.team import get_reviewer

router = routing.Router()

BOT_NAME = os.environ.get("BOT_NAME", "marvin-mk2")

GREETING = f"""
Hi! I'm an experimental bot. My goal is to guide this PR through its stages, hopefully ending with a merge. You can read up on the usage [here](https://github.com/timokau/marvin-mk2/blob/deployed/USAGE.md).
""".rstrip()

NO_SELF_REVIEW_TEXT = f"""
Sorry, you cannot set your own PR to `needs_merger`. Please wait for an external review. You may also actively search out a reviewer by pinging relevant people (look at the history of the files you're changing) or posting on discourse or IRC.
""".strip()


def find_commands(comment_text: str) -> List[str]:
    r"""Filters a comment for commands.

    >>> find_commands("This is a comment without a command.")
    []
    >>> find_commands("This includes a proper command.\n/command with multiple words")
    ['command with multiple words']
    >>> find_commands("//test\n/another  ")
    ['/test', 'another']
    """

    commands = []
    for line in comment_text.splitlines():
        prefix = "/"
        if line.startswith(prefix):
            commands.append(line[len(prefix) :].strip())
    return commands


async def handle_comment(
    comment: Dict[str, Any],
    issue: Dict[str, Any],
    pull_request_url: str,
    gh: GitHubAPI,
    token: str,
) -> None:
    """React to issue comments"""
    comment_text = comment["body"]
    comment_author_login = comment["user"]["login"]
    by_pr_author = issue["user"]["id"] == comment["user"]["id"]

    if comment_author_login in [BOT_NAME, BOT_NAME + "[bot]"]:
        return

    # check opt-in
    pr_labels = {label["name"] for label in issue["labels"]}
    commands = find_commands(comment_text)
    if "marvin" not in pr_labels:
        if by_pr_author and "marvin opt-in" == commands[0]:
            issue_url = issue.get("issue_url", issue["url"])
            await gh.post(
                issue_url + "/labels", data={"labels": ["marvin"]}, oauth_token=token,
            )
            await gh.post(
                issue["comments_url"], data={"body": GREETING}, oauth_token=token,
            )
            commands = commands[1:]
        else:
            return

    # Only handle one command for now, since a command can modify the issue and
    # we'd need to keep track of that.
    for command in commands:
        if command == "status awaiting_changes":
            await set_issue_status(issue, "awaiting_changes", gh, token)
        elif command == "status awaiting_reviewer":
            await set_issue_status(issue, "awaiting_reviewer", gh, token)
        elif command == "status needs_merger":
            if by_pr_author:
                await gh.post(
                    issue["comments_url"],
                    data={"body": NO_SELF_REVIEW_TEXT},
                    oauth_token=token,
                )
            else:
                await set_issue_status(issue, "needs_merger", gh, token)
                reviewer = await get_reviewer(
                    gh, token, issue, merge_permission_needed=True
                )
                if reviewer is not None:
                    print(
                        f"Requesting review (merge) from {reviewer} for {pull_request_url}."
                    )
                    await request_review(pull_request_url, "timokau", gh, token)
                else:
                    print(f"No reviewer found for {pull_request_url}.")
        else:
            print(f"Unknown command: {command}")


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
