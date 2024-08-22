from asyncio import Lock, sleep
from collections.abc import Callable, Coroutine
from functools import wraps
from http import HTTPStatus
from time import time
from typing import Any

from httpx import AsyncClient, HTTPError
from msgspec import json
from yarl import URL

from .exception import RequestError
from .log import logger

LIMIT = 1

decoder = json.Decoder()


def limit[**P, T](func: Callable[P, Coroutine[Any, Any, T]]) -> Callable[P, Coroutine[Any, Any, T]]:
    last_call = 0
    lock = Lock()

    @wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        nonlocal last_call
        async with lock:
            if (diff := (time() - last_call)) < LIMIT:
                logger.debug(f'request limit {(limit_time:=LIMIT-diff)}s')
                await sleep(limit_time)
        last_call = time()
        return await func(*args, **kwargs)

    return wrapper


class Request:
    """网络请求相关类"""

    def __init__(self, proxy: str | None) -> None:
        self.proxy = proxy
        self.session = AsyncClient(proxy=self.proxy)

    async def __call__(
        self,
        url: URL,
        *,
        is_json: bool = True,
    ) -> bytes:
        try:
            async with AsyncClient(proxy=self.proxy) as session:
                response = await session.get(str(url))
                if response.status_code != HTTPStatus.OK:
                    msg = f'请求错误 code: {response.status_code} {HTTPStatus(response.status_code).phrase}\n{response.text}'
                    raise RequestError(msg, status_code=response.status_code)
                if is_json:
                    decoder.decode(response.content)
                return response.content
        except HTTPError as e:
            msg = f'请求错误 \n{e!r}'
            raise RequestError(msg) from e
