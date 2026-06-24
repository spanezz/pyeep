import asyncio

from typing import TYPE_CHECKING, TypedDict

from .component import Component

if TYPE_CHECKING:
    from pyeep.models.scene import SceneDescription

    from .hub import Hub


class SceneArgs[DESC: SceneDescription](TypedDict):
    """Arguments for Scene constructor."""

    desc: DESC
    hub: "Hub"


class Scene[DESC: SceneDescription](Component):
    """Component used for scenes."""

    def __init__(self, *, desc: DESC, hub: "Hub") -> None:
        """Initialize a scene from its description."""
        super().__init__(name=desc.name, hub=hub)
        self.desc = desc
        self.active = self.desc.started
        self.pause_until_active_event = asyncio.Event()

    async def start(self) -> None:
        """
        Start the scene.

        This does nothing if the scene is already started.
        """
        self.active = True
        self.pause_until_active_event.set()

    async def stop(self) -> None:
        """
        Stop the scene.

        This does nothing if the scene is already stopped.
        """
        self.active = False

    async def pause_until_active(self) -> None:
        """
        Wait until the scene has started.

        This does nothing if the scene has already started.
        """
        if self.active:
            return
        self.pause_until_active_event.clear()
        await self.pause_until_active_event.wait()
