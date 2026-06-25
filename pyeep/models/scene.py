import abc
import importlib
from typing import TYPE_CHECKING, Any, Self

import pydantic

if TYPE_CHECKING:
    from pyeep.nodes.hub import Hub
    from pyeep.nodes.scene import Scene


class SceneDescription(pydantic.BaseModel, abc.ABC):
    """Base for scene descriptions loaded from YAML."""

    _scene_class: "type[Scene[Self]]"

    #: Scene name
    name: str
    #: Scene label (defaults to the capitalized name)
    label: str
    #: Python module for the scene
    module: str
    #: Scene notes (Markdown free text)
    notes: str = ""
    #: Scene starts automatically at startup
    started: bool = True

    @pydantic.model_validator(mode="before")
    @classmethod
    def _fill_defaults(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if (name := data.get("name")) and "label" not in data:
                data["label"] = name.capitalize()
        return data

    def make_scene(self, *, hub: "Hub") -> "Scene[Self]":
        """Create the Scene from this description."""
        return self._scene_class(desc=self, hub=hub)

    @classmethod
    def scene(cls, scene_class: type["Scene[Self]"]) -> "type[Scene[Self]]":
        """Decorate a scene as the implementation of this description."""
        cls._scene_class = scene_class
        return scene_class


class SingleTargetSceneDescription(SceneDescription):
    """Base description for a scene with a single target selection."""

    #: Target group names
    targets: list[str] = []


def get_scene_description_subclass(
    obj: dict[str, Any],
) -> type[SceneDescription]:
    """Get the SceneDescription subclass for a serialized SceneDescription."""
    try:
        module_name = obj["module"]
    except Exception as e:
        raise ValueError(e)

    try:
        mod = importlib.import_module(module_name)
        cls = getattr(mod, "Description")
    except Exception as e:
        raise ValueError(
            f"invalid Scene Description {module_name}.Description: {e}"
        )

    if not issubclass(cls, SceneDescription):
        raise ValueError(
            f"{module_name}.Description is not a subclass of SceneDescription"
        )

    # This is checked by issubclass to be a SceneDescription subclass, but mypy
    # doesn't seem to pick it up
    return cls  # type: ignore[no-any-return]


def load_scene_description(obj: Any) -> SceneDescription:
    """Deserialize a serialized SceneDescription object."""
    if not isinstance(obj, dict):
        raise ValueError(f"serialized SceneDescription {obj!r} is not a dict")
    cls = get_scene_description_subclass(obj)
    return cls.model_validate(obj)
