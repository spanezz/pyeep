from pyeep.models.messages import Event


class HeadYesNo(Event):
    """Yes/no/meh gestures."""

    #: Gesture name
    gesture: str
    #: Duration of the gesture in seconds
    duration: float
    #: Intensity of the gesture in degrees per second
    intensity: float


class HeadMoved(Event):
    """Head position tracking."""

    frames: int
    pitch: float
    roll: float


class HeadGyro(Event):
    """Head acceleration tracking."""

    #: X axis acceleration
    x: float
    #: Y axis acceleration
    y: float
    #: Z axis acceleration
    z: float

    # def _distance2(self) -> float:
    #     """
    #     Experiment with comparing messages
    #     """
    #     return self.x ** 2 + self.y ** 2 + self.z ** 2

    # def _adistance2(self) -> float:
    #     """
    #     Experiment with comparing messages
    #     """
    #     return self.ax ** 2 + self.ay ** 2 + self.az ** 2


# class BrainWaves(Message):
#     def __init__(
#         self,
#         *,
#         timestamp: float,
#         alpha: float,
#         beta: float,
#         gamma: float,
#         delta: float,
#         theta: float,
#         **kwargs,
#     ):
#         super().__init__(**kwargs)
#         self.timestamp = timestamp
#         self.alpha = alpha
#         self.beta = beta
#         self.gamma = gamma
#         self.delta = delta
#         self.theta = theta
#
#     def __str__(self):
#         return super().__str__() + (
#             f"(timestamp={self.timestamp},"
#             f" alpha={self.alpha}, beta={self.beta}, gamma={self.gamma}, delta={self.delta}, theta={self.theta})"
#         )
