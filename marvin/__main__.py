import logging
import os
import sys
import traceback

import aiohttp
from aiohttp import web
from gidgethub import apps
from gidgethub import routing
from gidgethub import sansio
from gidgethub.aiohttp import GitHubAPI

from marvin import commands
from marvin import constants
from marvin import status
from marvin import triage_runner

router = routing.Router(commands.router, status.router)
routes = web.RouteTableDef()


def is_bot_comment(event: sansio.Event) -> bool:
    """Determine whether an event was triggered by our own comments."""
    if "comment" not in event.data:
        return False
    comment = event.data["comment"]
    comment_author_login = comment["user"]["login"]
    return comment_author_login in [constants.BOT_NAME, constants.BOT_NAME + "[bot]"]


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

    # We detect the opt-in command here to decide whether or not we should
    # route the event. We do not act on it here. This is some code duplication,
    # but better safe than sorry.
    comment = event.data.get("comment")
    if comment is not None:
        by_pr_author = issue["user"]["id"] == comment["user"]["id"]
        if by_pr_author and "/marvin opt-in" in comment["body"]:
            return True
    else:
        pull_request = event.data.get("pull_request")
        if (
            pull_request is not None
            and event.data["action"] == "opened"
            and "/marvin opt-in" in pull_request["body"]
        ):
            return True

    return False


def log_event(event: sansio.Event) -> None:
    action = event.data.get("action")
    number = (
        event.data["issue"]["number"]
        if "issue" in event.data
        else event.data["pull_request"]["number"]
        if "pull_request" in event.data
        else None
    )
    print(f"New event: #{number} {event.event}->{action}")


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
            gh = GitHubAPI(session, constants.BOT_NAME)

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
            # Make sure a triage runner exists for this installation. Triage
            # runners are only started once at least one webhook event was
            # received. That's not ideal, but getting access to the list of
            # installations would otherwise be a pain.
            if installation_id not in triage_runner.runners:
                triage_runner.runners[installation_id] = triage_runner.TriageRunner(
                    installation_id,
                    gh_app_id=request.app["gh_app_id"],
                    gh_private_key=request.app["gh_private_key"],
                    min_delay_seconds=60,
                    max_delay_seconds=60 * 60 * 6,
                )
                print(f"Starting a triage runner for installation {installation_id}")
                triage_runner.runners[installation_id].start()

            if is_opted_in(event) and not is_bot_comment(event):
                log_event(event)
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
    logging.basicConfig(level=logging.DEBUG)

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
