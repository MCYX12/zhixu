import asyncio
from dataclasses import dataclass


class QueueError(Exception):
    def __init__(self, code: str):
        self.code = code


@dataclass
class Lease:
    queue: "GenerationQueue"
    user: str
    released: bool = False

    def release(self):
        if not self.released:
            self.released = True
            self.queue.active -= 1
            self.queue.users.discard(self.user)
            self.queue.semaphore.release()


class GenerationQueue:
    """One event loop / one worker. Counts complete streams, not just HTTP headers."""

    def __init__(self, concurrency: int, capacity: int, timeout: float):
        self.semaphore = asyncio.Semaphore(concurrency)
        self.concurrency = concurrency
        self.capacity = capacity
        self.timeout = timeout
        self.users: set[str] = set()
        self.active = 0
        self.waiting = 0

    async def acquire(self, user: str) -> Lease:
        if user in self.users:
            raise QueueError("user_request_in_progress")
        if self.semaphore.locked() and self.waiting >= self.capacity:
            raise QueueError("queue_full")
        self.users.add(user)
        self.waiting += 1
        try:
            await asyncio.wait_for(self.semaphore.acquire(), timeout=self.timeout)
        except BaseException as error:
            self.users.discard(user)
            if isinstance(error, TimeoutError):
                raise QueueError("queue_timeout") from error
            raise
        finally:
            self.waiting -= 1
        self.active += 1
        return Lease(self, user)
