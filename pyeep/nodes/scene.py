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
