import os
import sys
from typing import Any
from typing import Dict
from typing import List

import aiohttp
from aiohttp import web
from gidgethub import aiohttp as gh_aiohttp
from gidgethub import apps
from gidgethub import routing
from gidgethub import sansio

router = routing.Router()
routes = web.RouteTableDef()

BOT_NAME = "marvin-mk2"
# secrets and configurations configured through the environment
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")
GH_APP_ID = os.environ.get("GH_APP_ID", "")
GH_PRIVATE_KEY = os.environ.get("GH_PRIVATE_KEY", "")

# map commands to mutually exclusive labels
ISSUE_STATE_COMMANDS = {
    "needs review": "needs_review",
    "needs work": "needs_work",
    "needs merge": "needs_merge",
}

GREETING_FOOTER = f"""

Once a reviewer has looked at this, they can either
- request changes and instruct me to switch the state back (@{BOT_NAME} needs work)
- merge the PR if it looks good and they have the appropriate permission
- switch the state to `needs_merge` (@{BOT_NAME} needs merge), which allows reviewers with merge permission to focus their reviews

If anything could be improved, do not hesitate to give [feedback](https://github.com/timokau/marvin-mk2/issues).
""".rstrip()

GREETING_WORK = (
    f"""
Hi! I'm an experimental bot. My goal is to guide this PR through its stages, hopefully ending with a merge.

I have initialized the PR in the `needs_work` state. This indicates that the PR is not finished yet or that there are outstanding change requests. If you think the PR is good as-is, you can tell me to switch the state as follows:

@{BOT_NAME} needs review

This will change the state to `needs_review`, which makes it easily discoverable by reviewers.
""".strip()
    + GREETING_FOOTER
)

GREETING_REVIEW = (
    f"""
Hi! I'm an experimental bot. My goal is to guide this PR through its stages, hopefully ending with a merge.

I have initialized the PR in the `needs_review` state. This indicates that you consider this PR good to go and makes it easily discoverable by reviewers.
""".strip()
    + GREETING_FOOTER
)

UNKNOWN_COMMAND_TEXT = f"""
Sorry, I can't help you. Is there maybe a typo in your command?
""".strip()


# Unfortunately its not possible to directly listen for mentions
# https://github.com/dear-github/dear-github/issues/294
def find_commands(comment_text: str) -> List[str]:
    r"""Filters a comment for commands.

    >>> find_commands("This is a comment without a command.")
    []
    >>> find_commands("This includes a command, but with the wrong mention.\n@marvin-mk3 command")
    []
    >>> find_commands("This includes a proper command.\n@marvin-mk2 command with multiple words")
    ['command with multiple words']
    >>> find_commands("@marvin-mk2 @marvin-mk2 test\n@marvin-mk3 asdf\n@marvin-mk2 another  ")
    ['@marvin-mk2 test', 'another']
    """

    commands = []
    for line in comment_text.splitlines():
        prefix = f"@{BOT_NAME}"
        if line.startswith(f"@{BOT_NAME}"):
            commands.append(line[len(prefix) :].strip())
    return commands


async def clear_state(
    issue: Dict[str, Any], gh: gh_aiohttp.GitHubAPI, token: str
) -> None:
    """Clears the state tag of an issue"""
    labels = issue["labels"]
    label_names = {label["name"] for label in labels}
    # should never be more than one, but better to make it a set anyway
    state_labels = label_names.intersection(ISSUE_STATE_COMMANDS.values())
    for label in state_labels:
        await gh.delete(issue["url"] + "/labels/" + label, oauth_token=token)


async def handle_new_pr(
    pull_request: Dict[str, Any], gh: gh_aiohttp.GitHubAPI, token: str
) -> None:
    """React to new issues"""
    comment_text = pull_request["body"]
    # If pull_request actually is a pull_request, we have to query issue_url.
    # If its an issue, we have to use "url".
    issue_url = pull_request.get("issue_url", pull_request["url"])
    add_labels_url = issue_url + "/labels"
    # Only handle one command for now, since a command can modify the issue and
    # we'd need to keep track of that.
    for command in find_commands(comment_text)[:1]:
        if command == "needs work":
            await gh.post(
                add_labels_url, data={"labels": ["marvin"]}, oauth_token=token,
            )
            await gh.post(
                issue_url + "/labels",
                data={"labels": [ISSUE_STATE_COMMANDS["needs work"]]},
                oauth_token=token,
            )
            await gh.post(
                pull_request["comments_url"],
                data={"body": GREETING_WORK},
                oauth_token=token,
            )
        elif command == "needs review":
            await gh.post(
                add_labels_url, data={"labels": ["marvin"]}, oauth_token=token,
            )
            await gh.post(
                add_labels_url,
                data={"labels": [ISSUE_STATE_COMMANDS["needs review"]]},
                oauth_token=token,
            )
            await gh.post(
                pull_request["comments_url"],
                data={"body": GREETING_REVIEW},
                oauth_token=token,
            )
        else:
            await gh.post(
                pull_request["comments_url"],
                data={"body": UNKNOWN_COMMAND_TEXT},
                oauth_token=token,
            )


async def handle_comment(
    comment: Dict[str, Any], issue: Dict[str, Any], gh: gh_aiohttp.GitHubAPI, token: str
) -> None:
    """React to issue comments"""
    comment_text = comment["body"]
    comment_author_login = comment["user"]["login"]
    if comment_author_login in [BOT_NAME, BOT_NAME + "[bot]"]:
        return

    # check opt-in
    if "marvin" not in {label["name"] for label in issue["labels"]}:
        return

    # Only handle one command for now, since a command can modify the issue and
    # we'd need to keep track of that.
    for command in find_commands(comment_text)[:1]:
        if command == "echo":
            comment_text = comment["body"]
            reply_text = f"Echo!\n{comment_text}"
            await gh.post(
                issue["comments_url"], data={"body": reply_text}, oauth_token=token,
            )
        elif command == "agree with me":
            # https://developer.github.com/v3/reactions/#reaction-types For
            # some reason reactions have been in "beta" since 2016. We need to
            # opt in with the accept header.
            # https://developer.github.com/changes/2016-05-12-reactions-api-preview/
            await gh.post(
                comment["url"] + "/reactions",
                data={"content": "+1"},
                accept="application/vnd.github.squirrel-girl-preview+json",
                oauth_token=token,
            )
        elif command in ISSUE_STATE_COMMANDS:
            await clear_state(issue, gh, token)
            await gh.post(
                issue["url"] + "/labels",
                data={"labels": [ISSUE_STATE_COMMANDS[command]]},
                oauth_token=token,
            )
        else:
            await gh.post(
                issue["comments_url"],
                data={"body": UNKNOWN_COMMAND_TEXT},
                oauth_token=token,
            )


# Work on issues too for easier testing.
@router.register("issues", action="opened")
async def issue_open_event(
    event: sansio.Event, gh: gh_aiohttp.GitHubAPI, token: str, *args: Any, **kwargs: Any
) -> None:
    await handle_new_pr(event.data["issue"], gh, token)


@router.register("issue_comment", action="created")
async def issue_comment_event(
    event: sansio.Event, gh: gh_aiohttp.GitHubAPI, token: str, *args: Any, **kwargs: Any
) -> None:
    await handle_comment(event.data["comment"], event.data["issue"], gh, token)


@router.register("pull_request_review_comment", action="created")
async def pull_request_review_comment_event(
    event: sansio.Event, gh: gh_aiohttp.GitHubAPI, token: str, *args: Any, **kwargs: Any
) -> None:
    await handle_comment(event.data["comment"], event.data["pull_request"], gh, token)


@router.register("pull_request", action="opened")
async def pull_request_open_event(
    event: sansio.Event, gh: gh_aiohttp.GitHubAPI, token: str, *args: Any, **kwargs: Any
) -> None:
    await handle_new_pr(event.data["pull_request"], gh, token)


@routes.post("/webhook")
async def main(request: web.Request) -> web.Response:
    # read the GitHub webhook payload
    body = await request.read()

    # parse the event
    event = sansio.Event.from_http(request.headers, body, secret=WEBHOOK_SECRET)

    async with aiohttp.ClientSession() as session:
        gh = gh_aiohttp.GitHubAPI(session, BOT_NAME)

        # Fetch the installation_access_token once for each webhook delivery.
        # The token is valid for an hour, so it could be cached if we need to
        # save some API calls.
        installation_id = event.data["installation"]["id"]
        installation_access_token = await apps.get_installation_access_token(
            gh,
            installation_id=installation_id,
            app_id=GH_APP_ID,
            private_key=GH_PRIVATE_KEY,
        )

        # call the appropriate callback for the event
        await router.dispatch(event, gh, installation_access_token["token"])

    # HTTP success
    return web.Response(status=200)


if __name__ == "__main__":
    # The lookups should not throw an exception at import time to allow for
    # testing. If we're actually executing the bot though, we have to make sure
    # all credentials are supplied.
    if WEBHOOK_SECRET == "" or GH_APP_ID == "" or GH_PRIVATE_KEY == "":
        print(
            "Credentials not set. You need to set the WEBHOOK_SECRET, GH_APP_ID and GH_PRIVATE_KEY environment variables",
            file=sys.stderr,
        )
        sys.exit(1)
    app = web.Application()
    app.add_routes(routes)
    port_str = os.environ.get("PORT")
    if port_str is not None:
        port = int(port_str)

    web.run_app(app, port=port)
