import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from aiohttp import web

from pyeep.models import load_primitive
from pyeep.models.messages import Broadcast, Command, Event, Message
from pyeep.nodes.web import WebComponent

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
        if request.path.startswith("/hub/"):
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

    async def web_send(
        self, component: WebComponent, msg: dict[str, Any]
    ) -> None:
        """Send a message to the UI-side of a web component."""
        # payload = (
        #     f"""{{"dst": "{component.routing_key}", "msg": {msg.as_json}}}"""
        # )
        payload = json.dumps({"rk": component.routing_key, "msg": msg})
        async with asyncio.TaskGroup() as tg:
            for ui in self.ui_clients:
                tg.create_task(ui.ws.send_str(payload))

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

    async def ui_message_from_js(self, msg: dict[str, Any]) -> None:
        """Dispatch a message received from JavaScript."""
        if (rk := msg.get("rk")) is None:
            self.log.warning("JS message receved without routing key: %r", msg)
            return
        if (payload := msg.get("msg")) is None:
            self.log.warning("JS message receved without payload: %r", msg)
            return
        if (component := self.hub.components.get(rk)) is None:
            self.log.warning(
                "JS message receved for unknown compomnent: %r", msg
            )
            return
        if not isinstance(component, WebComponent):
            self.log.warning(
                "JS message receved for non-web compomnent: %r", msg
            )
            return
        await component.web_receive(payload)
        # match msg := load_primitive(json.loads(wsmsg.data)):
        #     case Event():
        #         await self.hub.inbound_event(msg)
        #     case Broadcast():
        #         await self.hub.inbound_broadcast(msg)
        #     case Command():
        #         await self.hub.inbound_command(msg)
        #     case _:
        #         log.warning("received unexpected message", msg)

    async def ui_io(self, request: web.Request) -> web.WebSocketResponse:
        """Websocket endpoint to communicate with the UI."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self.ui_clients.add(ui := UI(self.hub, ws))
        try:
            async for wsmsg in ws:
                match wsmsg.type:
                    case web.WSMsgType.text:
                        try:
                            msg = json.loads(wsmsg.data)
                        except json.JSONDecodeError as exc:
                            self.hub.log.warning(
                                "received message with non-JSON payload (%s): %r",
                                exc,
                                wsmsg.data,
                            )
                        else:
                            await self.ui_message_from_js(msg)
                    case web.WSMsgType.binary:
                        log.warning("received unexpected binary message", wsmsg)
                    case web.WSMsgType.close:
                        break
                    case web.WSMsgType.error:
                        log.error("received unexpected error message", wsmsg)
                        break
        finally:
            self.ui_clients.discard(ui)
        return ws
