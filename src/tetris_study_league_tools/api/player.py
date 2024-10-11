from types import MappingProxyType
from typing import Literal, cast, overload

from pydantic import TypeAdapter

from ..constant import BASE_URL, USER_ID, USER_NAME
from ..exception import RequestError
from .cache import Cache
from .schemas.base import FailedModel
from .schemas.summaries import (
    LeagueSuccessModel,
    SummariesModel,
)
from .schemas.summaries import (
    SoloSuccessModel as SummariesSoloSuccessModel,
)
from .schemas.summaries.base import User as SummariesUser
from .schemas.user import User
from .schemas.user_info import UserInfo, UserInfoSuccess
from .typing import Summaries


class Player:
    __SUMMARIES_MAPPING: MappingProxyType[Summaries, type[SummariesModel]] = MappingProxyType(
        {
            '40l': SummariesSoloSuccessModel,
            'blitz': SummariesSoloSuccessModel,
            'league': LeagueSuccessModel,
        }
    )

    @overload
    def __init__(self, *, user_id: str, trust: bool = False): ...
    @overload
    def __init__(self, *, user_name: str, trust: bool = False): ...
    def __init__(self, *, user_id: str | None = None, user_name: str | None = None, trust: bool = False):
        self.user_id = user_id
        self.user_name = user_name
        if not trust:
            if self.user_id is not None:
                if not USER_ID.match(self.user_id):
                    msg = 'Invalid user id'
                    raise ValueError(msg)
            elif self.user_name is not None:
                if not USER_NAME.match(self.user_name):
                    msg = 'Invalid user name'
                    raise ValueError(msg)
            else:
                msg = 'Invalid user'
                raise ValueError(msg)
        self.__user: User | None = None
        self._user_info: UserInfoSuccess | None = None
        self._summaries: dict[Summaries, SummariesModel] = {}

    @property
    def _request_user_parameter(self) -> str:
        return self.user_id or cast(str, self.user_name).lower()

    @property
    async def user(self) -> User:
        if self.__user is not None:
            return self.__user
        if (user := (await self._get_local_summaries_user())) is not None:
            self.__user = User(
                ID=user.id,
                name=user.username,
            )
        else:
            user_info = await self.get_info()
            self.__user = User(
                ID=user_info.data.id,
                name=user_info.data.username,
            )
        self.user_id = self.__user.ID
        self.user_name = self.__user.name
        return self.__user

    async def get_info(self) -> UserInfoSuccess:
        """Get User Info"""
        if self._user_info is None:
            raw_user_info = await Cache.get(BASE_URL / 'users' / self._request_user_parameter)
            user_info = TypeAdapter[UserInfo](UserInfo).validate_json(raw_user_info)
            if isinstance(user_info, FailedModel):
                msg = f'用户信息请求错误:\n{user_info.error}'
                raise RequestError(msg)
            self._user_info = user_info
        return self._user_info

    @overload
    async def get_summaries(self, summaries_type: Literal['40l', 'blitz']) -> SummariesSoloSuccessModel: ...
    @overload
    async def get_summaries(self, summaries_type: Literal['league']) -> LeagueSuccessModel: ...

    async def get_summaries(self, summaries_type: Summaries) -> SummariesModel:
        if summaries_type not in self._summaries:
            raw_summaries = await Cache.get(
                BASE_URL / 'users' / self._request_user_parameter / 'summaries' / summaries_type
            )
            summaries = TypeAdapter[SummariesModel | FailedModel](
                self.__SUMMARIES_MAPPING[summaries_type] | FailedModel
            ).validate_json(raw_summaries)
            if isinstance(summaries, FailedModel):
                msg = f'用户Summaries数据请求错误:\n{summaries.error}'
                raise RequestError(msg)
            self._summaries[summaries_type] = summaries
        return self._summaries[summaries_type]

    @property
    async def sprint(self) -> SummariesSoloSuccessModel:
        return await self.get_summaries('40l')

    @property
    async def blitz(self) -> SummariesSoloSuccessModel:
        return await self.get_summaries('blitz')

    @property
    async def league(self) -> LeagueSuccessModel:
        return await self.get_summaries('league')

    async def _get_local_summaries_user(self) -> SummariesUser | None:
        allow_summaries: set[Literal['40l', 'blitz']] = {'40l', 'blitz'}
        if has_summaries := (allow_summaries & self._summaries.keys()):
            for i in has_summaries:
                if (record := (await self.get_summaries(i)).data.record) is not None:
                    return record.user
        return None

    @property
    async def avatar_revision(self) -> int | None:
        if self._user_info is not None:
            return self._user_info.data.avatar_revision
        if (user := (await self._get_local_summaries_user())) is not None:
            return user.avatar_revision
        return (await self.get_info()).data.avatar_revision

    @property
    async def banner_revision(self) -> int | None:
        if self._user_info is not None:
            return self._user_info.data.banner_revision
        if (user := (await self._get_local_summaries_user())) is not None:
            return user.banner_revision
        return (await self.get_info()).data.banner_revision
