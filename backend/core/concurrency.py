"""Utilitários para executar trabalho CPU/IO-bound fora do event loop."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


async def run_sync(func: Callable[..., T], /, *args, **kwargs) -> T:
    """Executa callable síncrona no thread pool padrão do asyncio."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
