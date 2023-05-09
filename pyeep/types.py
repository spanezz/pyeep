from __future__ import annotations

from typing import NamedTuple

from .gtk import Gdk


class Color(NamedTuple):
    """
    Represent a RGB color, whose channels have values from 0 to 1
    """
    red: float = 0
    green: float = 0
    blue: float = 0

    def __str__(self):
        return (
            "#"
            f"{int(round(self.red * 255)):02x}"
            f"{int(round(self.green * 255)):02x}"
            f"{int(round(self.blue * 255)):02x}"
        )

    @staticmethod
    def _clip(val: float) -> float:
        """
        Clip a value between 0 to 1 inclusive
        """
        if val < 0:
            return 0
        if val > 1:
            return 1
        return val

    def __add__(self, color: Color):
        return Color(
            self._clip(self.red + color.red),
            self._clip(self.green + color.green),
            self._clip(self.blue + color.blue),
        )

    def as_rgba(self) -> Gdk.RGBA:
        color = Gdk.RGBA()
        color.red = self.red
        color.green = self.green
        color.blue = self.blue
        color.alpha = 1
        return color
