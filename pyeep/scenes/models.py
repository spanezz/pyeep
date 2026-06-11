import abc
import importlib
from typing import Any, TYPE_CHECKING
import pydantic

if TYPE_CHECKING:
    from pyeep.scenes.base import Scene


class SceneDescription(pydantic.BaseModel, abc.ABC):
    """Base for scene descriptions loaded from YAML."""

    #: Scene name
    name: str
    #: Scene label (defaults to the capitalized name)
    label: str
    #: Python module for the scene
    module: str

    @pydantic.model_validator(mode="before")
    @classmethod
    def _fill_defaults(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if (name := data.get("name")) and "label" not in data:
                data["label"] = name.capitalize()
        return data

    @abc.abstractmethod
    def make_scene(self) -> "Scene":
        """Create the Scene from this description."""


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

    return cls


def load_scene_description(obj: Any) -> SceneDescription:
    """Deserialize a serialized SceneDescription object."""
    if not isinstance(obj, dict):
        raise ValueError(f"serialized SceneDescription {obj!r} is not a dict")
    cls = get_scene_description_subclass(obj)
    return cls.model_validate(obj)
