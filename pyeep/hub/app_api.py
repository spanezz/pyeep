import json
import logging
from typing import Callable, Awaitable, TYPE_CHECKING

from aiohttp import web

from pyeep.models import load_primitive
from pyeep.models.messages import Message

if TYPE_CHECKING:
    from .hub import Hub

log = logging.getLogger("hub.api")


class API:
    """Handle Hub API for pyeep clients."""

    def __init__(self, *, hub: "Hub") -> None:
        """
        Initialize the API app.

        :param token: API token to use to authenticate clients
        """
        self.hub = hub
        #: Clients currently connected
        self.clients: dict[str, web.WebSocketResponse] = {}
        self.app = self.make_app()

    def make_app(self) -> web.Application:
        """Make the main hub application."""
        app = web.Application(middlewares=[self.check_token])
        app.add_routes(
            [
                web.get("/hub/", self.whoami),
                web.get("/hub/{name}", self.messages),
            ]
        )
        return app

    @web.middleware
    async def check_token(
        self,
        request: web.Request,
        handler: Callable[[web.Request], Awaitable[web.StreamResponse]],
    ) -> web.StreamResponse:
        """Check for the presence of an auth token."""
        if (token := request.cookies.get("Token")) is None:
            raise web.HTTPForbidden(reason="missing token")
        if token != self.hub.token:
            raise web.HTTPForbidden(reason="invalid token")
        return await handler(request)

    async def whoami(self, request: web.BaseRequest) -> web.Response:
        # TODO: return JSON
        return web.Response(text="PYEEP")

    async def fanout(self, msg: Message) -> None:
        """Send a message to all connected clients but the one it comes from."""
        for name, ws in self.clients.items():
            if msg.src and msg.src[0] == name:
                continue
            await ws.send_str(msg.as_json)

    async def messages(self, request: web.Request) -> web.WebSocketResponse:
        """Websocket message exchange endpoint."""
        client_name = request.match_info["name"]
        if client_name in self.clients:
            raise web.HTTPForbidden(
                reason=f"client {client_name!r} already registered"
            )

        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self.clients[client_name] = ws = ws
        try:
            async for wsmsg in ws:
                match wsmsg.type:
                    case web.WSMsgType.text:
                        msg = load_primitive(json.loads(wsmsg.data))
                        if isinstance(msg, Message):
                            await self.fanout(msg)
                            await self.hub.process_message_from_client(msg)
                    case web.WSMsgType.binary:
                        log.warning("received unexpected binary message", wsmsg)
                    case web.WSMsgType.close:
                        break
                    case web.WSMsgType.error:
                        log.error("received unexpected error message", wsmsg)
                        break
        finally:
            del self.clients[client_name]
        return ws
