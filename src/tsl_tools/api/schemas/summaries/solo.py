from pydantic import BaseModel

from ..base import FailedModel, SuccessModel
from ..base.solo import Record as BaseRecord
from .base import User


class Record(BaseRecord):
    user: User


class Data(BaseModel):
    record: Record | None
    rank: int
    rank_local: int


class SoloSuccessModel(SuccessModel):
    data: Data


type Solo = SoloSuccessModel | FailedModel
