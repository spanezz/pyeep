import struct
from typing import Any, Self, override

import pydantic


class Color(pydantic.BaseModel):
    """
    Represent a RGB color, whose channels have values from 0 to 1.
    """

    red: float = 0
    green: float = 0
    blue: float = 0

    @pydantic.model_validator(mode="before")
    @classmethod
    def accept_string(cls, data: Any) -> Any:
        """Allow to deserialize colors from a ``#aabbcc`` string."""
        if (
            isinstance(data, str)
            and len(stripped := data.strip()) == 7
            and stripped[0] == "#"
        ):
            colorbytes = bytes.fromhex(data[1:])
            r, g, b = struct.unpack("BBB", colorbytes)
            # TODO: see if there's a way to return a Color directly
            return {"red": r / 255, "green": g / 255, "blue": b / 255}
        return data

    @override
    def __str__(self) -> str:
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

    def __add__(self, color: "Color") -> Self:
        if not isinstance(color, Color):
            return NotImplemented
        return self.__class__(
            red=self._clip(self.red + color.red),
            green=self._clip(self.green + color.green),
            blue=self._clip(self.blue + color.blue),
        )

    def __mul__(self, value: float) -> Self:
        if not isinstance(value, (float, int)):
            return NotImplemented

        return self.__class__(
            red=self._clip(self.red * value),
            green=self._clip(self.green * value),
            blue=self._clip(self.blue * value),
        )

    # def as_rgba(self) -> Gdk.RGBA:
    #     color = Gdk.RGBA()
    #     color.red = self.red
    #     color.green = self.green
    #     color.blue = self.blue
    #     color.alpha = 1
    #     return color
