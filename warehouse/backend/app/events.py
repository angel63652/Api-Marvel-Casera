"""In-process async pub/sub broker for real-time events (SSE).

Single-process only: each uvicorn worker has its own broker. For a multi-worker
deploy, swap the publish/subscribe backend for Redis pub/sub (same interface).

Used to push stock-availability changes to connected portal clients.
"""
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

# Bounded queues so a slow/stalled subscriber can't grow memory unbounded;
# on overflow we drop the oldest event for that subscriber.
_MAX_QUEUE = 100


class _Broker:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()

    async def publish(self, event: dict) -> None:
        for q in list(self._subscribers):
            if q.full():
                try:
                    q.get_nowait()  # drop oldest
                except asyncio.QueueEmpty:
                    pass
            q.put_nowait(event)

    @asynccontextmanager
    async def subscribe(self) -> AsyncIterator[asyncio.Queue]:
        q: asyncio.Queue = asyncio.Queue(maxsize=_MAX_QUEUE)
        self._subscribers.add(q)
        try:
            yield q
        finally:
            self._subscribers.discard(q)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


broker = _Broker()


async def publish_stock_change(product_id: int, available_stock: float) -> None:
    """Notify subscribers that a product's available stock changed."""
    await broker.publish(
        {"type": "stock", "product_id": product_id, "available_stock": available_stock}
    )
