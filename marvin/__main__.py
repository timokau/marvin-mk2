import os

from aiohttp import web

routes = web.RouteTableDef()


@routes.get("/")
async def main(request):
    return web.Response(status=200, text="Hello world!")


if __name__ == "__main__":
    app = web.Application()
    app.add_routes(routes)
    port = os.environ.get("PORT")
    if port is not None:
        port = int(port)

    web.run_app(app, port=port)
