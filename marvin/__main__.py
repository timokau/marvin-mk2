import os

import aiohttp
from aiohttp import web
from gidgethub import aiohttp as gh_aiohttp
from gidgethub import routing
from gidgethub import sansio

router = routing.Router()
routes = web.RouteTableDef()

BOT_NAME = "marvin-mk2"
# secrets and configurations configured through the environment
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET")
GH_OAUTH_TOKEN = os.environ.get("GH_TOKEN")


# Unfortunately its not possible to directly listen for mentions
# https://github.com/dear-github/dear-github/issues/294
def find_commands(comment_text):
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


@router.register("issue_comment", action="created")
async def issue_comment_event(event, gh, *args, **kwargs):
    """React to issue comments"""
    comment_text = event.data["comment"]["body"]
    comment_author_login = event.data["comment"]["user"]["login"]
    if comment_author_login == BOT_NAME:
        return

    for command in find_commands(comment_text):
        if command == "echo":
            comment_text = event.data["comment"]["body"]
            reply_text = f"Echo!\n{comment_text}"
            await gh.post(
                event.data["issue"]["comments_url"], data={"body": reply_text}
            )
        elif command == "agree with me":
            # https://developer.github.com/v3/reactions/#reaction-types For
            # some reason reactions have been in "beta" since 2016. We need to
            # opt in with the accept header.
            # https://developer.github.com/changes/2016-05-12-reactions-api-preview/
            await gh.post(
                event.data["comment"]["url"] + "/reactions",
                data={"content": "+1"},
                accept="application/vnd.github.squirrel-girl-preview+json",
            )
        elif command == "needs review":
            await gh.post(
                event.data["issue"]["url"] + "/labels",
                data={"labels": ["needs_review"]},
            )


@routes.post("/")
async def main(request):
    # read the GitHub webhook payload
    body = await request.read()

    # parse the event
    event = sansio.Event.from_http(request.headers, body, secret=WEBHOOK_SECRET)

    async with aiohttp.ClientSession() as session:
        gh = gh_aiohttp.GitHubAPI(session, BOT_NAME, oauth_token=GH_OAUTH_TOKEN)

        # call the appropriate callback for the event
        await router.dispatch(event, gh)

    # HTTP success
    return web.Response(status=200)


if __name__ == "__main__":
    app = web.Application()
    app.add_routes(routes)
    port = os.environ.get("PORT")
    if port is not None:
        port = int(port)

    web.run_app(app, port=port)
