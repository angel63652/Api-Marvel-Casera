"""Real-time stock events tests (P4)."""
import asyncio
import json

import httpx
import pytest

from tests.test_stock import _mk_product, _mk_location
from tests.test_portal_orders import _register_active


def test_broker_pub_sub():
    """The in-process broker delivers published events to subscribers."""
    from app.events import broker, publish_stock_change

    async def scenario():
        received = []
        async with broker.subscribe() as q:
            await publish_stock_change(42, 7.0)
            evt = await asyncio.wait_for(q.get(), timeout=2)
            received.append(evt)
        return received

    out = asyncio.run(scenario())
    assert out == [{"type": "stock", "product_id": 42, "available_stock": 7.0}]


def test_broker_unsubscribe_removes_queue():
    from app.events import broker

    async def scenario():
        assert broker.subscriber_count == 0
        async with broker.subscribe():
            assert broker.subscriber_count == 1
        assert broker.subscriber_count == 0

    asyncio.run(scenario())


def test_stream_requires_auth(client):
    # No token -> rejected before streaming starts.
    r = client.get("/api/portal/catalog/stream")
    assert r.status_code == 401


def test_stream_emits_stock_event_on_movement(client, auth, server):
    """End-to-end: a stock movement pushes a `stock` event to a portal SSE client."""
    p = _mk_product(client, auth)
    loc = _mk_location(client, auth)
    ph, *_ = _register_active(client, auth)

    with httpx.Client(base_url=server, timeout=20) as sse_client:
        with sse_client.stream("GET", "/api/portal/catalog/stream", headers=ph) as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers["content-type"]
            lines = resp.iter_lines()
            next(lines)  # ": connected" comment

            # Trigger a stock change in another connection.
            client.post("/api/v1/movements", headers=auth, json={
                "type": "ENTRY",
                "lines": [{"product_id": p["id"], "location_id": loc["id"], "quantity": 9}],
            })

            data_line = None
            for _ in range(20):
                line = next(lines)
                if line.startswith("data:"):
                    data_line = line
                    break
            assert data_line is not None, "no data event received"
            payload = json.loads(data_line[len("data:"):].strip())
            assert payload["type"] == "stock"
            assert payload["product_id"] == p["id"]
            assert payload["available_stock"] == 9
