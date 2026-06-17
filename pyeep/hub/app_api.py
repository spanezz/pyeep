import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from aiohttp import web

from pyeep.models import load_primitive
from pyeep.models.messages import Broadcast, Command, Event, Message

if TYPE_CHECKING:
    from .hub import HubApp

log = logging.getLogger("hub.api")


class UI:
    def __init__(self, hub: "HubApp", ws: web.WebSocketResponse) -> None:
        self.hub = hub
        self.ws = ws

    async def receive_from_ui(self, data: dict[str, Any]) -> None:
        pass

    async def close(self) -> None:
        await self.ws.close()


class API:
    """Handle Hub API for pyeep clients."""

    def __init__(self, *, hub: "HubApp") -> None:
        """
        Initialize the API app.

        :param token: API token to use to authenticate clients
        """
        self.hub = hub
        #: Clients currently connected
        self.clients: dict[str, web.WebSocketResponse] = {}
        #: UI clients currently connected
        self.ui_clients: set[UI] = set()
        self.app = self.make_app()

    def make_app(self) -> web.Application:
        """Make the main hub application."""
        app = web.Application(middlewares=[self.check_token])
        app.add_routes(
            [
                web.get("/hub/", self.whoami),
                web.get("/hub/{name}", self.messages),
                web.get("/ui/io/", self.ui_io),
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

    async def fanout_broadcast(self, msg: Broadcast) -> None:
        """Send a broadcast message to connected clients."""
        async with asyncio.TaskGroup() as tg:
            for ws in self.clients.values():
                tg.create_task(ws.send_str(msg.as_json))

    async def fanout_command(self, cmd: Command) -> None:
        """Send a command to matching connected clients."""
        client_names: set[str] = set()
        for rk in cmd.dst:
            client_names.add(rk.split(".", 1)[0])

        async with asyncio.TaskGroup() as tg:
            for name in client_names:
                if (ws := self.clients.get(name)) is not None:
                    tg.create_task(ws.send_str(cmd.as_json))

    async def fanout_ui(self, msg: Message) -> None:
        """Send a message to all connected UIs."""
        async with asyncio.TaskGroup() as tg:
            for ui in self.ui_clients:
                tg.create_task(ui.ws.send_str(msg.as_json))

    async def close_all_clients(self) -> None:
        """Close all client connections."""
        async with asyncio.TaskGroup() as tg:
            for ws in self.clients.values():
                tg.create_task(ws.close())
            for ui in self.ui_clients:
                tg.create_task(ui.close())

    async def messages(self, request: web.Request) -> web.WebSocketResponse:
        """Websocket message exchange endpoint."""
        client_name = request.match_info["name"]
        if client_name in self.clients:
            raise web.HTTPForbidden(
                reason=f"client {client_name!r} already registered"
            )

        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self.clients[client_name] = ws
        try:
            async for wsmsg in ws:
                match wsmsg.type:
                    case web.WSMsgType.text:
                        msg = load_primitive(json.loads(wsmsg.data))
                        if isinstance(msg, Event):
                            await self.hub.inbound_event(msg)
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

    async def ui_io(self, request: web.Request) -> web.WebSocketResponse:
        """Websocket endpoint to communicate with the UI."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self.ui_clients.add(ui := UI(self.hub, ws))
        try:
            async for wsmsg in ws:
                match wsmsg.type:
                    case web.WSMsgType.text:
                        msg = json.loads(wsmsg.data)
                        if isinstance(msg, dict):
                            await ui.receive_from_ui(msg)
                        log.warning("received unexpected JSON message", wsmsg)
                    case web.WSMsgType.binary:
                        log.warning("received unexpected binary message", wsmsg)
                    case web.WSMsgType.close:
                        break
                    case web.WSMsgType.error:
                        log.error("received unexpected error message", wsmsg)
                        break
        finally:
            del self.ui_clients[ui]
        return ws
