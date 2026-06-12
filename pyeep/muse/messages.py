from pyeep.models.messages import Message


class HeadYesNo(Message):
    #: Gesture name
    gesture: str
    #: Duration of the gesture in seconds
    duration: float
    #: Intensity of the gesture in degrees per second
    intensity: float


class HeadMoved(Message):
    frames: int
    pitch: float
    roll: float


# class HeadGyro(Message):
#     def __init__(
#         self,
#         *,
#         timestamps: numpy.ndarray,
#         x: numpy.ndarray,
#         y: numpy.ndarray,
#         z: numpy.ndarray,
#         **kwargs,
#     ):
#         super().__init__(**kwargs)
#         self.timestamps = timestamps
#         self.x = x
#         self.y = y
#         self.z = z
#
#     def __str__(self):
#         return super().__str__() + (
#             f"(timestamps={self.timestamps},"
#             f" x={self.x}, y={self.y}, z={self.z})"
#         )
#
#     # def _distance2(self) -> float:
#     #     """
#     #     Experiment with comparing messages
#     #     """
#     #     return self.x ** 2 + self.y ** 2 + self.z ** 2
#
#     # def _adistance2(self) -> float:
#     #     """
#     #     Experiment with comparing messages
#     #     """
#     #     return self.ax ** 2 + self.ay ** 2 + self.az ** 2
#
#
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
