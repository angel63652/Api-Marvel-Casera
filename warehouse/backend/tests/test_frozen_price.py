"""Frozen order-line price tests (C14)."""
from tests.test_stock import _mk_product, _mk_location
from tests.test_portal_orders import _register_active


def test_portal_order_total_frozen_after_tariff_change(client, auth):
    p = _mk_product(client, auth, price_base=10.0)
    loc = _mk_location(client, auth)
    client.post("/api/v1/movements", headers=auth, json={
        "type": "ENTRY", "lines": [{"product_id": p["id"], "location_id": loc["id"], "quantity": 50}],
    })
    client.put(f"/api/v1/products/{p['id']}/tier-prices?tier=GOLD&price=8.0", headers=auth)
    ph, customer_id, _ = _register_active(client, auth, tier="GOLD")

    order = client.post("/api/portal/orders", headers=ph, json={
        "items": [{"product_id": p["id"], "quantity": 2}],
    }).json()
    oid = order["id"]
    assert order["total"] == 16.0  # 2 * 8.0 (GOLD)

    # Tariff goes up AFTER the order; the existing order total must not change.
    client.put(f"/api/v1/products/{p['id']}/tier-prices?tier=GOLD&price=99.0", headers=auth)
    again = client.get(f"/api/portal/orders/{oid}", headers=ph).json()
    assert again["total"] == 16.0  # frozen
    assert again["lines"][0]["unit_price"] == 8.0
