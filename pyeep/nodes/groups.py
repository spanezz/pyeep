import asyncio
import fnmatch
import re
from pathlib import Path
from typing import Any, Unpack, override, Collection

import pydantic

from pyeep.animator import PowerAnimator, ColorAnimator
from pyeep.models.messages.color import SetColor
from pyeep.models.messages.power import SetPower
from pyeep.models.animation import AnimationPrimitive
from pyeep.models.color import Color
from pyeep.models.messages import (
    Message,
    RoutingKey,
    RoutingKeys,
    build_routing_keys,
)
from pyeep.nodes import Component, Node
from pyeep.nodes.messages import ComponentAdded, ComponentRemoved
from pyeep.nodes.web import WebComponent, WebComponentArgs, WebHub
from pyeep.utils.modules import get_package_path


class GroupDescription(pydantic.BaseModel):
    """Description of a group loaded from YAML."""

    name: str
    label: str
    icon: str
    color: Color
    match: list[str]

    @pydantic.model_validator(mode="before")
    @classmethod
    def _fill_defaults(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if (name := data.get("name")) and "label" not in data:
                data["label"] = name.capitalize()
            data.setdefault("icon", data["label"][0])
        return data


class Group(WebComponent):
    """Manage a group of connected clients."""

    section = "groups"

    def __init__(
        self,
        *,
        desc: GroupDescription,
        hub: "WebHub",
        namespace: str | None = None,
    ) -> None:
        """Initialize a scene from its description."""
        super().__init__(name=desc.name, namespace=namespace, hub=hub)
        self.desc = desc
        self.re_match: re.Pattern[str] = self.compile_matches()
        self.members: set[RoutingKey] = set()
        self.js_class = "Group"
        self.dom_classes.append("group")
        self.power_animator = PowerAnimator(
            name="power", frame_duration_ns=100_000_000
        )
        self.color_animator = ColorAnimator(
            name="color", frame_duration_ns=100_000_000
        )

    def compile_matches(self) -> re.Pattern[str]:
        """Compile matches in group description to regular expressions."""
        patterns: list[str] = []
        for match in self.desc.match:
            if match.startswith("match:"):
                patterns.append(fnmatch.translate(match.removeprefix("match:")))
            elif match.startswith("re:"):
                patterns.append(match.removeprefix("re:"))
            else:
                patterns.append(f"^{re.escape(match)}$")
        return re.compile("|".join(patterns))

    def match(self, msg: ComponentAdded) -> bool:
        """Check if this component matches this group."""
        if msg.src is None:
            return False
        return self.re_match.match(msg.src) is not None

    def dst(self) -> RoutingKeys:
        """Return a RoutingKeys to target this group."""
        return build_routing_keys(self.members)

    @override
    async def web_receive(self, message: dict[str, Any]) -> None:
        await super().web_receive(message)
        self.log.info("Received from web: %r", message)

    async def membership_changed(self) -> None:
        """Called when the group membership has changed."""
        await self.web_send({"membership": sorted(self.members)})

    @override
    async def receive(self, msg: Message) -> None:
        await super().receive(msg)
        if msg.src is None:
            self.log.error("Ignoring event without source: %s", msg)
            return
        match msg:
            case ComponentAdded():
                self.log.info("New component: %s", msg.src)
                if self.match(msg):
                    self.members.add(msg.src)
                    await self.membership_changed()
            case ComponentRemoved():
                self.log.info("Component removed: %s", msg.src)
                self.members.discard(msg.src)
                await self.membership_changed()
            case _:
                await super().receive(msg)

    @override
    def get_static_path(self) -> Path | None:
        static_path = get_package_path("pyeep.hub") / "static" / "group"
        if static_path.exists():
            return static_path
        return None

    @override
    def get_template_path(self) -> Path | None:
        template_path = get_package_path("pyeep.hub") / "templates" / "group"
        if template_path.exists():
            return template_path
        return None

    async def disconnect_by_prefix(self, prefix: str) -> None:
        """Report disconnection of all components with this prefix."""
        self.members.discard(prefix)
        match = f"{prefix}."
        for name in list(self.members):
            if name.startswith(match):
                self.members.discard(name)
        await self.membership_changed()

    async def web_set_power(self, power: float) -> None:
        await self.web_send({"power": power})

    async def web_set_color(self, color: Color) -> None:
        self.log.info("WSC %s", color)
        await self.web_send({"color": str(color)})

    async def notify_set_power(self, power: float | AnimationPrimitive[float]):
        """Notify that a SetPower command has been sent to the group members."""
        match power:
            case float():
                await self.web_set_power(power)
            case AnimationPrimitive():
                self.power_animator.add_at_next_tick(power.get_animation())

    async def notify_set_color(
        self, color: Color | AnimationPrimitive[Color]
    ) -> None:
        """Notify that a SetColor command has been sent to the group members."""
        match color:
            case Color():
                await self.web_set_color(color)
            case AnimationPrimitive():
                self.color_animator.add_at_next_tick(color.get_animation())

    async def power_animations(self) -> None:
        async for value in self.power_animator.values():
            await self.web_set_power(value)

    async def color_animations(self) -> None:
        async for value in self.color_animator.values():
            await self.web_set_color(value)

    @override
    async def init(self) -> None:
        await super().init()
        await self.start_task(self.power_animations())
        await self.start_task(self.color_animations())


class Groups(Component):
    """Manage groups of connected clients."""

    hub: WebHub

    def __init__(self, **kwargs: Unpack[WebComponentArgs]) -> None:
        super().__init__(**kwargs)
        self.groups: dict[str, Group] = {}

    async def add(self, desc: GroupDescription) -> None:
        """Add a group by its description."""
        group = Group(desc=desc, hub=self.hub, namespace=self.routing_key)
        if group.name in self.groups:
            raise RuntimeError(f"group {group.name} defined multiple times")
        self.groups[group.name] = group
        await self.hub.add_component(group)
        self.log.info("Added group %s - %s", group.name, group.desc.label)

    def dst(self, *names: str) -> RoutingKeys:
        """Return a RoutingKeys targeting components in the named groups."""
        res: set[str] = set()
        for name in names:
            if group := self.groups.get(name):
                res.update(group.members)
        return build_routing_keys(res)

    async def disconnect_by_prefix(self, prefix: str) -> None:
        """Report disconnection of all components with this prefix."""
        async with asyncio.TaskGroup() as tg:
            for group in self.groups.values():
                tg.create_task(group.disconnect_by_prefix(prefix))

    async def set_power(
        self,
        sender: Node,
        groups: Collection[str],
        power: float | AnimationPrimitive[float],
    ) -> None:
        """Send a SetPower command to the named groups."""
        async with asyncio.TaskGroup() as tg:
            dst = self.dst(*groups)
            tg.create_task(sender.send_command(SetPower(dst=dst, power=power)))
            for name in groups:
                if group := self.groups.get(name):
                    tg.create_task(group.notify_set_power(power))

    async def set_color(
        self,
        sender: Node,
        groups: Collection[str],
        color: Color | AnimationPrimitive[Color],
    ) -> None:
        """Send a SetColor command to the named groups."""
        async with asyncio.TaskGroup() as tg:
            dst = self.dst(*groups)
            tg.create_task(sender.send_command(SetColor(dst=dst, color=color)))
            for name in groups:
                if group := self.groups.get(name):
                    tg.create_task(group.notify_set_color(color))
