import os
import sys
import traceback
from typing import Any
from typing import Dict
from typing import List

import aiohttp
from aiohttp import web
from gidgethub import aiohttp as gh_aiohttp
from gidgethub import apps
from gidgethub import routing
from gidgethub import sansio

from marvin.gh_util import request_review
from marvin.team import get_reviewer

router = routing.Router()
routes = web.RouteTableDef()

BOT_NAME = os.environ.get("BOT_NAME", "marvin-mk2")

# List of mutually exclusive status labels
ISSUE_STATUS_LABELS = {"needs_review", "needs_work", "needs_merge"}

GREETING = f"""
Hi! I'm an experimental bot. My goal is to guide this PR through its stages, hopefully ending with a merge. You can read up on the usage [here](https://github.com/timokau/marvin-mk2/blob/deployed/USAGE.md).
""".rstrip()


NO_SELF_REVIEW_TEXT = f"""
Sorry, you cannot set your own PR to `needs_merge`. Please wait for an external review. You may also actively search out a reviewer by pinging relevant people (look at the history of the files you're changing) or posting on discourse or IRC.
""".strip()


# Unfortunately its not possible to directly listen for mentions
# https://github.com/dear-github/dear-github/issues/294
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


async def set_issue_status(
    issue: Dict[str, Any], status: str, gh: gh_aiohttp.GitHubAPI, token: str
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


async def handle_comment(
    comment: Dict[str, Any],
    issue: Dict[str, Any],
    pull_request_url: str,
    gh: gh_aiohttp.GitHubAPI,
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
        if command == "status needs_work":
            await set_issue_status(issue, "needs_work", gh, token)
        elif command == "status needs_review":
            await set_issue_status(issue, "needs_review", gh, token)
        elif command == "status needs_merge":
            if by_pr_author:
                await gh.post(
                    issue["comments_url"],
                    data={"body": NO_SELF_REVIEW_TEXT},
                    oauth_token=token,
                )
            else:
                await set_issue_status(issue, "needs_merge", gh, token)
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
    event: sansio.Event, gh: gh_aiohttp.GitHubAPI, token: str, *args: Any, **kwargs: Any
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
    event: sansio.Event, gh: gh_aiohttp.GitHubAPI, token: str, *args: Any, **kwargs: Any
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
    event: sansio.Event, gh: gh_aiohttp.GitHubAPI, token: str, *args: Any, **kwargs: Any
) -> None:
    if event.data["review"]["state"] == "changes_requested":
        await set_issue_status(event.data["pull_request"], "needs_work", gh, token)
    await handle_comment(
        event.data["review"],
        event.data["pull_request"],
        event.data["pull_request"]["url"],
        gh,
        token,
    )


@router.register("pull_request", action="synchronize")
async def pull_request_synchronize(
    event: sansio.Event, gh: gh_aiohttp.GitHubAPI, token: str, *args: Any, **kwargs: Any
) -> None:
    # Synchronize means that the PRs branch moved, invalidating previous reviews.
    if "needs_merge" in {
        label["name"] for label in event.data["pull_request"]["labels"]
    }:
        await set_issue_status(event.data["pull_request"], "needs_review", gh, token)


def is_opted_in(event: sansio.Event) -> bool:
    """Perform a conservative opt-in check.

    Returns "true" if the PR is either already opted-in ("marvin" label
    present) or the current event contains the opt-in command by the PR author.
    """
    issue = event.data.get("issue", event.data.get("pull_request"))
    if issue is None:
        return False

    if "marvin" in {label["name"] for label in issue["labels"]}:
        return True

    comment = event.data.get("comment")
    if comment is None:
        return False

    # We detect the opt-in command here to decide whether or not we should
    # route the event. We do not act on it here. This is some code duplication,
    # but better safe than sorry.
    by_pr_author = issue["user"]["id"] == comment["user"]["id"]
    if by_pr_author and "marvin opt-in" in find_commands(comment["body"]):
        return True

    return False


@routes.post("/webhook")
async def process_webhook(request: web.Request) -> web.Response:
    try:
        # read the GitHub webhook payload
        body = await request.read()

        # parse the event
        event = sansio.Event.from_http(
            request.headers, body, secret=request.app["webhook_secret"]
        )

        async with aiohttp.ClientSession() as session:
            gh = gh_aiohttp.GitHubAPI(session, BOT_NAME)

            # Fetch the installation_access_token once for each webhook delivery.
            # The token is valid for an hour, so it could be cached if we need to
            # save some API calls.
            installation_id = event.data["installation"]["id"]
            installation_access_token = await apps.get_installation_access_token(
                gh,
                installation_id=installation_id,
                app_id=request.app["gh_app_id"],
                private_key=request.app["gh_private_key"],
            )

            if is_opted_in(event):
                # call the appropriate callback for the event
                await router.dispatch(event, gh, installation_access_token["token"])

        if gh.rate_limit is not None:
            print("GH rate limit remaining:", gh.rate_limit.remaining)

        # HTTP success
        return web.Response(status=200)
    except Exception:
        traceback.print_exc(file=sys.stderr)
        return web.Response(status=500)


def load_secret_from_env_or_file(key: str, file_key: str) -> str:
    if key in os.environ:
        return os.environ[key]
    elif file_key in os.environ:
        return open(os.environ[file_key]).read().strip()
    else:
        raise Exception(f"You need to set either {key} or {file_key}.")


def main() -> None:
    app = web.Application()
    app["webhook_secret"] = load_secret_from_env_or_file(
        "WEBHOOK_SECRET", "WEBHOOK_SECRET_FILE"
    )
    app["gh_private_key"] = load_secret_from_env_or_file(
        "GH_PRIVATE_KEY", "GH_PRIVATE_KEY_FILE"
    )
    app["gh_app_id"] = load_secret_from_env_or_file("GH_APP_ID", "GH_APP_ID_FILE")
    app.add_routes(routes)
    port_str = os.environ.get("PORT")
    port = int(port_str) if port_str is not None else None

    web.run_app(app, port=port)


if __name__ == "__main__":
    main()
