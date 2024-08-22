from abc import ABC, abstractmethod
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel
from typing_extensions import override

T = TypeVar('T', bound=Literal['IO'])


class BaseUser(BaseModel, ABC, Generic[T]):
    """游戏用户"""

    platform: T

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BaseUser):
            return self.unique_identifier == other.unique_identifier
        return False

    @property
    @abstractmethod
    def unique_identifier(self) -> str:
        raise NotImplementedError


class User(BaseUser[Literal['IO']]):
    platform: Literal['IO'] = 'IO'

    ID: str
    name: str

    @property
    @override
    def unique_identifier(self) -> str:
        return self.ID
