import abc
from pathlib import Path
from typing import NotRequired, Unpack, override

import aiohttp_jinja2
import jinja2
import pydantic
from aiohttp import web
from markupsafe import Markup

from pyeep.models.messages import Message
from pyeep.nodes import Component, Hub, NodeArgs


class Assets(pydantic.BaseModel):
    """Bundle of web assets."""

    js_modules: dict[str, str] = {}
    css: set[str] = set()

    def add(self, assets: "Assets") -> None:
        """Add an asset bundle."""
        self.js_modules.update(assets.js_modules)
        self.css.update(assets.css)


class WebHub(Hub, abc.ABC):
    """Hub that has web-connected components."""

    @abc.abstractmethod
    async def web_message_to_ui(
        self, msg: Message, component: "WebComponent"
    ) -> None:
        """Forward a message to the web side of a component."""


class WebComponentArgs(NodeArgs):
    """Arguments for WebComponent constructor."""

    hub: WebHub
    namespace: NotRequired[str | None]


class WebComponent(Component, abc.ABC):
    """Base class for components with a web UI."""

    hub: WebHub

    #: Section of the UI where this component is mounted
    section: str

    def __init__(self, **kwargs: Unpack[WebComponentArgs]) -> None:
        super().__init__(**kwargs)

    def get_assets(self) -> Assets:
        """Get the assets to load for this component."""
        return Assets()

    @abc.abstractmethod
    def get_static_path(self) -> Path | None:
        """
        Return the on-disk path to use for static files.

        :returns: the path, or None if this component has no static files
        """

    @abc.abstractmethod
    def get_template_path(self) -> Path | None:
        """
        Return the on-disk path to use for template files.

        :returns: the path, or None if this component has no templates
        """

    @override
    async def receive(self, message: Message) -> None:
        await super().receive(message)
        # Forward the message to the web-side of this component.
        # This can still be overridden to also do local processing
        await self.hub.web_message_to_ui(message, self)

    def add_views(self, app: web.Application, *, prefix: str) -> None:
        """
        Install the scene as a subapp of the Main hub app.

        :param app: add views to this app
        :param prefix: URL prefix to use for views
        """
        # TODO: app.router.add_view(f"{prefix}/", Home)

    @jinja2.pass_context
    async def render_widget(self, context: jinja2.runtime.Context) -> str:
        request = context["request"]
        return Markup(
            await aiohttp_jinja2.render_string_async(
                f"{self.section}/{self.name}/ui.html",
                request,
                context.derived({"node": self}),  # type: ignore[arg-type]
            )
        )
