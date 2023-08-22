from __future__ import annotations

import importlib
import logging
from typing import Any, Type

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
