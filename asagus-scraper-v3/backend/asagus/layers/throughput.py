from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable, Iterable
from concurrent.futures import ProcessPoolExecutor
from typing import TypeVar

from asagus.models import ThroughputProfile


T = TypeVar("T")
R = TypeVar("R")


class AsyncCPUHybridExecutor:
    """Asyncio for network I/O, ProcessPoolExecutor for CPU-heavy parsing/ranking."""

    def __init__(self, profile: ThroughputProfile | None = None) -> None:
        cpu_default = max(1, (os.cpu_count() or 4) - 1)
        self.profile = profile or ThroughputProfile(cpu_workers=cpu_default)
        self.io_semaphore = asyncio.Semaphore(self.profile.io_concurrency)
        self.queue: asyncio.Queue[T] = asyncio.Queue(maxsize=self.profile.queue_maxsize)
        self._process_pool: ProcessPoolExecutor | None = None

    @property
    def process_pool(self) -> ProcessPoolExecutor:
        if self._process_pool is None:
            self._process_pool = ProcessPoolExecutor(max_workers=self.profile.cpu_workers)
        return self._process_pool

    async def run_io(self, func: Callable[..., Awaitable[R]], *args: object) -> R:
        async with self.io_semaphore:
            return await func(*args)

    async def run_cpu(self, func: Callable[..., R], *args: object) -> R:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.process_pool, func, *args)

    async def map_cpu(self, func: Callable[[T], R], items: Iterable[T]) -> list[R]:
        tasks = [self.run_cpu(func, item) for item in items]
        return await asyncio.gather(*tasks)

    async def produce(self, item: T, priority: float = 0.5) -> bool:
        if not self.queue.full():
            await self.queue.put(item)
            return True
        if self.profile.backpressure_policy == "drop_low_priority" and priority < 0.25:
            return False
        await self.queue.put(item)
        return True

    async def close(self) -> None:
        if self._process_pool:
            self._process_pool.shutdown(wait=True, cancel_futures=True)
            self._process_pool = None

    def state(self) -> dict[str, object]:
        return {
            "io_concurrency": self.profile.io_concurrency,
            "cpu_workers": self.profile.cpu_workers,
            "queue_maxsize": self.profile.queue_maxsize,
            "queued_items": self.queue.qsize(),
            "browser_contexts": self.profile.browser_contexts,
            "backpressure_policy": self.profile.backpressure_policy,
            "pattern": "asyncio for I/O + ProcessPoolExecutor for CPU-bound extraction, hashing, BM25/SPLADE scoring and graph work",
        }
