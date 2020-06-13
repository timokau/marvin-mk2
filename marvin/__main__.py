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

router = routing.Router()
routes = web.RouteTableDef()

BOT_NAME = os.environ.get("BOT_NAME", "marvin-mk2")

# List of mutually exclusive states
ISSUE_STATES = {"needs_review", "needs_work", "needs_merge"}

GREETING_FOOTER = f"""

Once a reviewer has looked at this, they can either
- request changes and instruct me to switch the state back (`/status needs_work`)
- merge the PR if it looks good and they have the appropriate permission
- switch the state to `needs_merge` (`/status needs_merge`), which allows reviewers with merge permission to focus their reviews

If anything could be improved, do not hesitate to give [feedback](https://github.com/timokau/marvin-mk2/issues).
""".rstrip()

GREETING_WORK = (
    f"""
Hi! I'm an experimental bot. My goal is to guide this PR through its stages, hopefully ending with a merge.

I have initialized the PR in the `needs_work` state. This indicates that the PR is not finished yet or that there are outstanding change requests. If you think the PR is good as-is, you can tell me to switch the state as follows:

`/status needs_review`

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


async def set_issue_state(
    issue: Dict[str, Any], state: str, gh: gh_aiohttp.GitHubAPI, token: str
) -> None:
    """Sets the state of an issue while resetting other states"""
    assert state in ISSUE_STATES

    # Labels are mutually exclusive, so clear other labels first.
    labels = issue["labels"]
    label_names = {label["name"] for label in labels}
    # should never be more than one, but better to make it a set anyway
    state_labels = label_names.intersection(ISSUE_STATES)
    for label in state_labels:
        if label == state:  # Don't touch the label we're supposed to set.
            continue
        await gh.delete(issue["url"] + "/labels/" + label, oauth_token=token)

    if state not in state_labels:
        await gh.post(
            issue["url"] + "/labels", data={"labels": [state]}, oauth_token=token,
        )


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
    command_recognized = False
    for command in find_commands(comment_text)[:1]:
        if command == "status needs_work":
            command_recognized = True
            await set_issue_state(pull_request, "needs_work", gh, token)
            await gh.post(
                pull_request["comments_url"],
                data={"body": GREETING_WORK},
                oauth_token=token,
            )
        elif command == "status needs_review":
            command_recognized = True
            await set_issue_state(pull_request, "needs_review", gh, token)
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
    if command_recognized:
        await gh.post(
            add_labels_url, data={"labels": ["marvin"]}, oauth_token=token,
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
        if command == "status needs_work":
            await set_issue_state(issue, "needs_work", gh, token)
        elif command == "status needs_review":
            await set_issue_state(issue, "needs_review", gh, token)
        elif command == "status needs_merge":
            if issue["user"]["id"] == comment["user"]["id"]:
                await gh.post(
                    issue["comments_url"],
                    data={"body": NO_SELF_REVIEW_TEXT},
                    oauth_token=token,
                )
            else:
                await set_issue_state(issue, "needs_merge", gh, token)
        else:
            await gh.post(
                issue["comments_url"],
                data={"body": UNKNOWN_COMMAND_TEXT},
                oauth_token=token,
            )


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
