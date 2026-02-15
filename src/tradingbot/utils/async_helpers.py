"""Async utility helpers for wrapping sync libraries."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any, Callable, TypeVar

T = TypeVar("T")

_executor = ThreadPoolExecutor(max_workers=4)


async def run_in_executor(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Run a synchronous function in a thread pool executor.

    Used by Alpaca and Polymarket connectors to wrap their sync clients
    so they present an async interface without blocking the event loop.
    """
    loop = asyncio.get_running_loop()
    if kwargs:
        func = partial(func, **kwargs)
    return await loop.run_in_executor(_executor, func, *args)
