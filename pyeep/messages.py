from __future__ import annotations

import importlib
import logging
from typing import TYPE_CHECKING, Any, Type

if TYPE_CHECKING:
    from .component.base import Component

log = logging.getLogger(__name__)


class Jsonable:
    def as_jsonable(self) -> dict[str, Any]:
        return {
            "__module__": self.__class__.__module__,
            "__class__": self.__class__.__name__,
        }

    @staticmethod
    def jsonable_class(jsonable: dict[str, Any]) -> Type[Jsonable] | None:
        try:
            module_name = jsonable.pop("__module__")
            class_name = jsonable.pop("__class__")
        except Exception as e:
            log.error("message malformed: %r: %s", jsonable, e)
            return None

        try:
            mod = importlib.import_module(module_name)
            return getattr(mod, class_name)
        except Exception as e:
            log.error("cannot find module class %s.%s: %s", module_name, class_name, e)
            return None


class Message(Jsonable):
    """
    Base class for messages sent between components
    """
    def __init__(
            self, *,
            ts: float | None = None,
            src: Component | None = None,
            dst: str | None = None,
            name: str | None = None):
        self.ts = ts
        self.src = src
        self.dst = dst
        if name is None:
            self.name = self.__class__.__name__.lower()
        else:
            self.name = name

    def __str__(self) -> str:
        return self.name

    def as_jsonable(self) -> dict[str, Any]:
        res = super().as_jsonable()
        res["ts"] = self.ts
        res["src"] = self.src.name if self.src else None
        res["dst"] = self.dst
        res["name"] = self.name
        return res


class Shutdown(Message):
    """
    Message sent to initiate component shutdown
    """
    pass


class EmergencyStop(Message):
    """
    Request to stop any activity as soon as possible
    """
    pass


class DeviceScanRequest(Message):
    """
    Request to scan for new devices
    """
    def __init__(self, *, duration: float, **kwargs):
        super().__init__(**kwargs)
        # Duration in seconds of the scan
        self.duration = duration

    def __str__(self):
        return super().__str__() + f"(duration={self.duration})"


class ConfigSaveRequest(Message):
    """
    Message sent to initiate saving configuration
    """
    pass


class Configure(Message):
    """
    Message sent to a component to restore its configuration
    """
    def __init__(self, *, config: dict[str, Any], **kwargs):
        super().__init__(**kwargs)
        self.config = config

    def __str__(self):
        return super().__str__() + f"(config={self.config!r})"


class Shortcut(Message):
    """
    Event notifying the trigger of a named keyboard shortcut
    """
    def __init__(self, *, command: str, **kwargs):
        super().__init__(**kwargs)
        self.command = command

    def __str__(self):
        return super().__str__() + f"(command={self.command})"

    def as_jsonable(self) -> dict[str, Any]:
        res = super().as_jsonable()
        res["command"] = self.command
        return res


class Pause(Message):
    """
    Pause outputs in a group
    """
    def __init__(self, *, group: int, **kwargs):
        super().__init__(**kwargs)
        self.group = group

    def __str__(self) -> str:
        return super().__str__() + f"(group={self.group})"


class Resume(Message):
    """
    Unpause outputs in a group
    """
    def __init__(self, *, group: int, **kwargs):
        super().__init__(**kwargs)
        self.group = group

    def __str__(self) -> str:
        return super().__str__() + f"(group={self.group})"


class NewComponent(Message):
    """
    Notify that a new component has been added
    """
    def __str__(self) -> str:
        return super().__str__() + f"(component={self.src})"


class ComponentActiveStateChanged(Message):
    """
    Notify a change of active state for an input
    """
    def __init__(self, *, value: bool, **kwargs):
        super().__init__(**kwargs)
        self.value = value

    def __str__(self) -> str:
        return super().__str__() + f"(value={self.value})"
