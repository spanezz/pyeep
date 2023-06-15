from __future__ import annotations

from typing import Sequence

import numpy
import scipy.signal


class Butterworth:
    """
    Butterworth filter function
    """
    # See https://stackoverflow.com/questions/40483518/how-to-real-time-filter-with-scipy-and-lfilter
    #
    # See https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.lfilter.html#scipy.signal.lfilter
    # > The function sosfilt (and filter design using output='sos') should be
    # > preferred over lfilter for most filtering tasks, as second-order sections
    # > have fewer numerical problems.

    def __init__(
            self,
            rate: int,
            cutoff: float | Sequence[float],
            btype: str = "low",
            order: int = 3):
        self.sos = scipy.signal.butter(order, cutoff, btype=btype, output="sos", fs=rate)
        self.z: numpy.ndarray | None = None

    def __call__(self, sample: float) -> float:
        if self.z is None:
            self.z = scipy.signal.sosfilt_zi(self.sos) * sample
        filtered, self.z = scipy.signal.sosfilt(self.sos, [sample], zi=self.z)
        return filtered[0]
