import asyncio
from typing import override

import numpy as np

from pyeep.models.color import Color
from pyeep.models.messages.message import Message
from pyeep.models.messages.color import SetGroupColor
from pyeep.scenes.models import SceneDescription
from pyeep.scenes.base import Scene
from pyeep.muse.messages import HeadYesNo, HeadMoved, HeadGyro
from pyeep.utils import dsp


class Description(SceneDescription):
    """Dance with lights scene description."""

    @override
    def make_scene(self) -> "SceneDance":
        return SceneDance(self)


class SceneDance(Scene):
    """Control lights based on head position."""

    def __init__(self, desc: Description, /) -> None:
        super().__init__(desc)

        #: Output group for generated messages
        # TODO: configure via UI
        self.output_group: int = 1

        # Input sampling rate used for the Butterworth filter
        input_rate = 52
        self.filter_red = dsp.Butterworth(rate=input_rate, cutoff=10)
        self.filter_green = dsp.Butterworth(rate=input_rate, cutoff=10)
        self.filter_blue = dsp.Butterworth(rate=input_rate, cutoff=10)
        # self.last_bw_ts: float | None = None

    @override
    async def receive(self, msg: Message) -> None:
        match msg:
            case HeadYesNo():
                value = msg.intensity**2

                red = 0
                green = 0
                blue = 0

                match msg.gesture:
                    case "meh":
                        # Meh
                        red = value
                        green = value / 3
                    case "yes":
                        # Yes
                        green = value
                    case "no":
                        # No
                        red = value

                red = self.filter_red(red)
                green = self.filter_green(green)
                blue = self.filter_blue(blue)

                color = Color(
                    red=np.clip(red, 0, 1),
                    green=np.clip(green, 0, 1),
                    blue=np.clip(blue, 0, 1),
                )

                await self.send(
                    SetGroupColor(group=self.output_group, color=color)
                )

            case HeadMoved():

                def norm(val: float, min_angle=0, max_angle=80) -> float:
                    return (
                        (abs(val) - min_angle) / (max_angle - min_angle)
                    ) ** 2

                blue = self.filter_blue(norm(msg.pitch, max_angle=40))
                green = self.filter_green(norm(msg.roll, max_angle=40))
                red = self.filter_red(1 - max(blue, green))

                color = Color(
                    red=np.clip(red, 0, 1),
                    green=np.clip(green, 0, 1),
                    blue=np.clip(blue, 0, 1),
                )

                await self.send(
                    SetGroupColor(group=self.output_group, color=color)
                )

            case HeadGyro():
                min_dps = 0.0
                max_dps = 200.0

                def norm(val: float) -> float:
                    return ((abs(val) - min_dps) / (max_dps - min_dps)) ** 2

                red = self.filter_red(norm(msg.x))
                green = self.filter_green(norm(msg.y))
                blue = self.filter_blue(norm(msg.z))

                color = Color(
                    red=np.clip(red, 0, 1),
                    green=np.clip(green, 0, 1),
                    blue=np.clip(blue, 0, 1),
                )

                await self.send(
                    SetGroupColor(group=self.output_group, color=color)
                )

            # case BrainWaves():
            #     # min_db = 30
            #     # max_db = 60
            #     if (
            #         self.last_bw_ts is None
            #         or msg.timestamp - self.last_bw_ts > 0.05
            #     ):
            #         self.last_bw_ts = msg.timestamp
            #         bwmin = min((msg.alpha, msg.beta, msg.theta))
            #         bwmax = max((msg.alpha, msg.beta, msg.theta))
            #         color = Color(
            #             red=numpy.clip(
            #                 (msg.alpha - bwmin) / (bwmax - bwmin), 0, 1
            #             ),
            #             green=numpy.clip(
            #                 (msg.beta - bwmin) / (bwmax - bwmin), 0, 1
            #             ),
            #             blue=numpy.clip(
            #                 (msg.theta - bwmin) / (bwmax - bwmin), 0, 1
            #             ),
            #         )
            #         self.scene.send(
            #             SetGroupColor(group=self.scene.get_group(), color=color)
            #         )

    @override
    async def main(self) -> None:
        await asyncio.Event().wait()
