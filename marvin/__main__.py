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


@router.register("issue_comment", action="created")
async def issue_opened_event(event, gh, *args, **kwargs):
    """Echo back any issue comments"""
    url = event.data["issue"]["comments_url"]
    comment_author_login = event.data["comment"]["user"]["login"]
    if comment_author_login != BOT_NAME:
        comment_text = event.data["comment"]["body"]
        reply_text = f"Echo!\n{comment_text}"
        await gh.post(url, data={"body": reply_text})


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
