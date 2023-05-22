from __future__ import annotations

from typing import Type, TypeVar

from ..component.active import ActiveComponent, ActiveController
from ..component.base import Component
from ..component.controller import Controller
from ..component.modes import ModeComponent, ModeController

C = TypeVar("C", bound="Input")


class Input(ModeComponent, ActiveComponent, Component):
    """
    Generic base for components managing inputs
    """
    def get_controller(self) -> Type["Controller"]:
        return InputController


class InputController(ActiveController[C], ModeController[C]):
    """
    User interface side for an input (controller and view)
    """
    def __init__(self, *, component: Component, **kwargs):
        kwargs.setdefault("name", "input_model_" + component.name)
        super().__init__(component=component, **kwargs)
