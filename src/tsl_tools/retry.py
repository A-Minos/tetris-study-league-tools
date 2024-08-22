from asyncio import sleep
from collections.abc import Callable, Coroutine
from datetime import timedelta
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from .log import logger

T = TypeVar('T')
P = ParamSpec('P')


def retry(
    max_attempts: int = 3,
    exception_type: type[BaseException] | tuple[type[BaseException], ...] = Exception,
    delay: timedelta | None = None,
) -> Callable[[Callable[P, Coroutine[Any, Any, T]]], Callable[P, Coroutine[Any, Any, T]]]:
    def decorator(func: Callable[P, Coroutine[Any, Any, T]]) -> Callable[P, Coroutine[Any, Any, T]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            for i in range(max_attempts + 1):
                if i > 0:
                    message = f'Retrying: {func.__name__} ({i}/{max_attempts})'
                    logger.debug(message)
                if i == max_attempts:
                    break
                try:
                    return await func(*args, **kwargs)
                except exception_type as e:
                    if i == max_attempts:
                        raise
                    logger.exception(e)
                    if delay is not None:
                        await sleep(delay.total_seconds())
            return await func(*args, **kwargs)

        return wrapper

    return decorator
