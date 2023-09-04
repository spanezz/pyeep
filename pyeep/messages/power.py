from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .message import Message

if TYPE_CHECKING:
    from ..animation import PowerAnimation

log = logging.getLogger(__name__)


class SetRate(Message):
    """
    Notify the sample rate of a component

    This is mainly used to for communication between a PowerOutputBottom and a
    PowerOutputTop
    """
    def __init__(self, *, rate: float, **kwargs):
        super().__init__(**kwargs)
        self.rate = rate

    def __str__(self) -> str:
        return super().__str__() + f"(rate={self.rate})"

    def as_jsonable(self) -> dict[str, Any]:
        res = super().as_jsonable()
        res["rate"] = self.rate
        return res


class SetPower(Message):
    """
    Set the power of an output.

    This is mainly used to send power commands from a PowerOutputTop to a
    PowerOutputBottom
    """
    def __init__(self, *, power: float, **kwargs):
        super().__init__(**kwargs)
        self.power = power

    def __str__(self) -> str:
        return super().__str__() + f"(power={self.power})"

    def as_jsonable(self) -> dict[str, Any]:
        res = super().as_jsonable()
        res["power"] = self.power
        return res


class SetGroupPower(Message):
    """
    Set the power of the outputs in the given group
    """
    def __init__(self, *, group: int, power: float | PowerAnimation, **kwargs):
        super().__init__(**kwargs)
        self.group = group
        self.power = power

    def __str__(self) -> str:
        return super().__str__() + f"(group={self.group}, power={self.power})"

    def as_jsonable(self) -> dict[str, Any]:
        res = super().as_jsonable()
        res["group"] = self.group
        res["power"] = fun() if (fun := getattr(self.power, "as_jsonable", None)) else self.power
        return res


class IncreaseGroupPower(Message):
    """
    Increase the power of an output group by a given amount
    """
    def __init__(self, *, group: int, amount: float | PowerAnimation, **kwargs):
        super().__init__(**kwargs)
        self.group = group
        self.amount = amount

    def __str__(self) -> str:
        return super().__str__() + f"(group={self.group}, amount={self.amount})"

    def as_jsonable(self) -> dict[str, Any]:
        res = super().as_jsonable()
        res["group"] = self.group
        fun = getattr(self.amount, "as_jsonable", None)
        res["amount"] = fun() if fun is not None else self.amount
        return res
