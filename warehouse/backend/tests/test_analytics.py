"""Analytics + ETL tests (P6, Polars)."""
import io

from tests.test_stock import _mk_product, _mk_location


def _complete_order(client, auth, pid, lid, qty):
    """Create -> pick -> confirm an order so it counts as a completed sale."""
    order = client.post("/api/v1/orders", headers=auth, json={
        "customer_name": "C",
        "lines": [{"product_id": pid, "quantity_requested": qty, "location_id": lid}],
    }).json()
    oid = order["id"]
    me = client.get("/api/v1/employees/me", headers=auth).json()
    client.post(f"/api/v1/orders/{oid}/start-picking", headers=auth, json={"picker_id": me["id"]})
    line_id = client.get(f"/api/v1/orders/{oid}/picking-list", headers=auth).json()[0]["line_id"]
    p = client.get(f"/api/v1/products/{pid}", headers=auth).json()
    client.post(f"/api/v1/orders/{oid}/lines/{line_id}/pick", headers=auth,
                json={"barcode_scanned": p["barcode"], "quantity_picked": qty})
    r = client.post(f"/api/v1/orders/{oid}/confirm", headers=auth, json={})
    assert r.status_code == 200, r.text


def test_sales_summary_aggregates_completed_orders(client, auth):
    p = _mk_product(client, auth, price_base=4.0)
    loc = _mk_location(client, auth)
    client.post("/api/v1/movements", headers=auth, json={
        "type": "ENTRY", "lines": [{"product_id": p["id"], "location_id": loc["id"], "quantity": 100}],
    })
    _complete_order(client, auth, p["id"], loc["id"], 5)
    _complete_order(client, auth, p["id"], loc["id"], 3)

    r = client.get("/api/v1/analytics/sales-summary", headers=auth)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total_units"] >= 8
    top = next(t for t in data["top_products"] if t["product_id"] == p["id"])
    assert top["units"] == 8        # 5 + 3
    assert top["revenue"] == 32.0   # 8 * 4.0


def test_import_tier_prices_csv(client, auth):
    p1 = _mk_product(client, auth)
    p2 = _mk_product(client, auth)
    csv = f"niu,tier,price\n{p1['niu']},GOLD,9.5\n{p2['niu']},GOLD,3.25\nUNKNOWN,GOLD,1.0\n"
    files = {"file": ("tarifas.csv", io.BytesIO(csv.encode()), "text/csv")}
    r = client.post("/api/v1/analytics/import-tier-prices", headers=auth, files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] == 2
    assert body["skipped"] == 1  # UNKNOWN niu

    # Re-import updates instead of duplicating.
    files = {"file": ("tarifas.csv", io.BytesIO(csv.encode()), "text/csv")}
    r2 = client.post("/api/v1/analytics/import-tier-prices", headers=auth, files=files)
    assert r2.json()["updated"] == 2


def test_analytics_requires_auth(client):
    assert client.get("/api/v1/analytics/sales-summary").status_code == 401
