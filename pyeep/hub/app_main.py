from aiohttp import web


class Main:
    async def home(self, request: web.BaseRequest) -> web.Response:
        return web.Response(text="PYEEP")

    def make_app(self) -> web.Application:
        """Make the main hub application."""
        app = web.Application()
        app.add_routes(
            [
                web.get("/", self.home),
            ]
        )
        return app
