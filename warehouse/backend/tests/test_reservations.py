"""Stock reservation tests (R4): available = current_stock - reserved_stock."""
from tests.test_stock import _mk_product, _mk_location


def _stock(client, auth, pid):
    return client.get(f"/api/v1/products/{pid}", headers=auth).json()


def _add_stock(client, auth, pid, lid, qty):
    r = client.post("/api/v1/movements", headers=auth, json={
        "type": "ENTRY",
        "lines": [{"product_id": pid, "location_id": lid, "quantity": qty}],
    })
    assert r.status_code == 201, r.text


def test_order_creation_reserves_stock(client, auth):
    p = _mk_product(client, auth)
    loc = _mk_location(client, auth)
    _add_stock(client, auth, p["id"], loc["id"], 10)

    before = _stock(client, auth, p["id"])
    assert before["current_stock"] == 10
    assert before["reserved_stock"] == 0
    assert before["available_stock"] == 10

    client.post("/api/v1/orders", headers=auth, json={
        "customer_name": "C",
        "lines": [{"product_id": p["id"], "quantity_requested": 4, "location_id": loc["id"]}],
    })

    after = _stock(client, auth, p["id"])
    assert after["current_stock"] == 10        # physical unchanged
    assert after["reserved_stock"] == 4         # held
    assert after["available_stock"] == 6        # 10 - 4


def test_confirm_consumes_reservation_and_drops_stock(client, auth):
    p = _mk_product(client, auth)
    loc = _mk_location(client, auth)
    _add_stock(client, auth, p["id"], loc["id"], 10)

    order = client.post("/api/v1/orders", headers=auth, json={
        "customer_name": "C",
        "lines": [{"product_id": p["id"], "quantity_requested": 4, "location_id": loc["id"]}],
    }).json()
    oid = order["id"]
    me = client.get("/api/v1/employees/me", headers=auth).json()
    client.post(f"/api/v1/orders/{oid}/start-picking", headers=auth, json={"picker_id": me["id"]})
    line_id = client.get(f"/api/v1/orders/{oid}/picking-list", headers=auth).json()[0]["line_id"]
    client.post(f"/api/v1/orders/{oid}/lines/{line_id}/pick", headers=auth,
                json={"barcode_scanned": p["barcode"], "quantity_picked": 4})

    r = client.post(f"/api/v1/orders/{oid}/confirm", headers=auth, json={})
    assert r.status_code == 200, r.text

    after = _stock(client, auth, p["id"])
    assert after["current_stock"] == 6      # 10 - 4 shipped
    assert after["reserved_stock"] == 0     # hold consumed
    assert after["available_stock"] == 6


def test_cancel_releases_reservation(client, auth):
    p = _mk_product(client, auth)
    loc = _mk_location(client, auth)
    _add_stock(client, auth, p["id"], loc["id"], 10)

    order = client.post("/api/v1/orders", headers=auth, json={
        "customer_name": "C",
        "lines": [{"product_id": p["id"], "quantity_requested": 3, "location_id": loc["id"]}],
    }).json()
    assert _stock(client, auth, p["id"])["reserved_stock"] == 3

    r = client.put(f"/api/v1/orders/{order['id']}/status?status=CANCELLED", headers=auth)
    assert r.status_code == 200, r.text

    after = _stock(client, auth, p["id"])
    assert after["reserved_stock"] == 0
    assert after["available_stock"] == 10
