"""Resource governance and scheduling."""

from __future__ import annotations

import asyncio
import os


class ResourceGovernor:
    """Manage CPU, browser, and LLM concurrency with backpressure."""

    def __init__(
        self,
        cpu_workers: int | None = None,
        browser_pool_size: int = 3,
        llm_concurrency: int = 5,
        queue_max_size: int = 1000,
    ):
        self.cpu_workers = max(1, cpu_workers or max(1, (os.cpu_count() or 2) - 1))
        self.browser_pool_size = max(1, browser_pool_size)
        self.llm_concurrency = max(1, llm_concurrency)
        self.queue_max_size = max(1, queue_max_size)

        self.cpu_semaphore = asyncio.Semaphore(self.cpu_workers)
        self.browser_semaphore = asyncio.Semaphore(self.browser_pool_size)
        self.llm_semaphore = asyncio.Semaphore(self.llm_concurrency)

        self.cpu_queue_size = 0
        self.browser_queue_size = 0
        self.llm_queue_size = 0
        self.cpu_active = 0
        self.browser_active = 0
        self.llm_active = 0

    async def cpu_task(self, coro):
        """Run CPU-bound task with concurrency control."""
        self.cpu_queue_size += 1
        try:
            async with self.cpu_semaphore:
                self.cpu_active += 1
                try:
                    return await coro
                finally:
                    self.cpu_active -= 1
        finally:
            self.cpu_queue_size -= 1

    async def browser_task(self, coro):
        """Run browser task with concurrency control."""
        self.browser_queue_size += 1
        try:
            async with self.browser_semaphore:
                self.browser_active += 1
                try:
                    return await coro
                finally:
                    self.browser_active -= 1
        finally:
            self.browser_queue_size -= 1

    async def llm_task(self, coro):
        """Run LLM task with concurrency control."""
        self.llm_queue_size += 1
        try:
            async with self.llm_semaphore:
                self.llm_active += 1
                try:
                    return await coro
                finally:
                    self.llm_active -= 1
        finally:
            self.llm_queue_size -= 1

    def can_accept_work(self) -> bool:
        """Check if queue has capacity."""
        total_queue = (
            self.cpu_queue_size +
            self.browser_queue_size +
            self.llm_queue_size
        )
        return total_queue < self.queue_max_size

    def get_metrics(self) -> dict[str, object]:
        """Get resource utilization metrics."""
        return {
            "cpu_workers": self.cpu_workers,
            "cpu_queue_size": self.cpu_queue_size,
            "cpu_active": self.cpu_active,
            "cpu_utilization": round(self.cpu_active / self.cpu_workers, 2),
            "browser_pool_size": self.browser_pool_size,
            "browser_queue_size": self.browser_queue_size,
            "browser_active": self.browser_active,
            "browser_utilization": round(self.browser_active / self.browser_pool_size, 2),
            "llm_concurrency": self.llm_concurrency,
            "llm_queue_size": self.llm_queue_size,
            "llm_active": self.llm_active,
            "llm_utilization": round(self.llm_active / self.llm_concurrency, 2),
            "can_accept_work": self.can_accept_work(),
        }

    def state(self) -> dict[str, object]:
        return {
            "purpose": "Manage CPU, browser, and LLM concurrency with backpressure",
            "config": {
                "cpu_workers": self.cpu_workers,
                "browser_pool_size": self.browser_pool_size,
                "llm_concurrency": self.llm_concurrency,
                "queue_max_size": self.queue_max_size,
            },
            "metrics": self.get_metrics(),
        }
