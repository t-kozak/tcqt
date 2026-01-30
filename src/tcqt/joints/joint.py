import abc
from typing import Literal

from ..workplane import Workplane

JointFaceSelector = Literal["X>", "X<", "Y>", "Y<", "Z>", "Z<"]


class Joint(abc.ABC):
    @abc.abstractmethod
    def apply_female(
        self,
        workplane: Workplane,
        face: JointFaceSelector,
        offset: tuple[float, float] = (0, 0),
    ) -> Workplane:
        raise NotImplementedError()

    @abc.abstractmethod
    def apply_male(
        self,
        workplane: Workplane,
        face: JointFaceSelector,
        offset: tuple[float, float] = (0, 0),
    ) -> Workplane:
        raise NotImplementedError()
