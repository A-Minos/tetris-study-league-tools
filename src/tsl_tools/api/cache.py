from asyncio import Lock
from datetime import UTC, datetime
from typing import ClassVar
from weakref import WeakValueDictionary

from aiocache import Cache as ACache  # type: ignore[import-untyped]
from pydantic import TypeAdapter
from yarl import URL

from ..log import logger
from ..request import Request, limit
from .schemas.base import FailedModel, SuccessModel

request = limit(Request(None))


class Cache:
    cache = ACache(ACache.MEMORY)
    task: ClassVar[WeakValueDictionary[URL, Lock]] = WeakValueDictionary()

    @classmethod
    async def get(cls, url: URL) -> bytes:
        lock = cls.task.setdefault(url, Lock())
        async with lock:
            if (cached_data := await cls.cache.get(url)) is not None:
                logger.debug(f'{url}: Cache hit!')
                return cached_data
            response_data = await request(url)
            parsed_data = TypeAdapter[SuccessModel | FailedModel](SuccessModel | FailedModel).validate_json(
                response_data
            )
            if isinstance(parsed_data, SuccessModel):
                await cls.cache.add(
                    url,
                    response_data,
                    (parsed_data.cache.cached_until - datetime.now(UTC)).total_seconds(),
                )
            return response_data
