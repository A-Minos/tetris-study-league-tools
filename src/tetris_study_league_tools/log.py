from loguru import logger
from richuru import install  # type: ignore[import-untyped]

install(level='DEBUG')

__all__ = ['logger']
