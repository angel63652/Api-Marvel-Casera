"""Stock, order-number, picking and pagination tests (H5/H6/R5)."""
import uuid


def _mk_product(client, auth, **over):
    suffix = uuid.uuid4().hex[:8]
    payload = {
        "niu": f"NIU-{suffix}",
        "barcode": f"BC-{suffix}",
        "name": f"Prod {suffix}",
        "unit": "unit",
        "min_stock": 1,
        "current_stock": 0,
    }
    payload.update(over)
    r = client.post("/api/v1/products", headers=auth, json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def _mk_location(client, auth):
    suffix = uuid.uuid4().hex[:6]
    r = client.post(
        "/api/v1/locations",
        headers=auth,
        json={"code": f"A-{suffix}", "aisle": "A", "rack": "01", "position": suffix, "capacity": 100},
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_entry_movement_increments_stock(client, auth):
    p = _mk_product(client, auth)
    loc = _mk_location(client, auth)
    r = client.post(
        "/api/v1/movements",
        headers=auth,
        json={"type": "ENTRY", "lines": [
            {"product_id": p["id"], "location_id": loc["id"], "quantity": 10}
        ]},
    )
    assert r.status_code == 201, r.text
    got = client.get(f"/api/v1/products/{p['id']}", headers=auth).json()
    assert got["current_stock"] == 10


def test_stock_deltas_accumulate(client, auth):
    p = _mk_product(client, auth)
    loc = _mk_location(client, auth)
    for qty, mtype in [(10, "ENTRY"), (5, "ENTRY"), (3, "EXIT")]:
        r = client.post(
            "/api/v1/movements",
            headers=auth,
            json={"type": mtype, "lines": [
                {"product_id": p["id"], "location_id": loc["id"], "quantity": qty}
            ]},
        )
        assert r.status_code == 201, r.text
    got = client.get(f"/api/v1/products/{p['id']}", headers=auth).json()
    assert got["current_stock"] == 12  # 10 + 5 - 3


def test_order_numbers_are_sequential(client, auth):
    p = _mk_product(client, auth)
    nums = []
    for _ in range(3):
        r = client.post(
            "/api/v1/orders",
            headers=auth,
            json={"customer_name": "C", "lines": [
                {"product_id": p["id"], "quantity_requested": 1}
            ]},
        )
        assert r.status_code == 201, r.text
        nums.append(r.json()["order_number"])
    # All ORD-YYYY-NNNNNN, strictly increasing, no random collisions.
    seqs = [int(n.rsplit("-", 1)[1]) for n in nums]
    assert seqs == sorted(seqs)
    assert len(set(nums)) == 3


def test_money_field_roundtrips(client, auth):
    p = _mk_product(client, auth, price_cost=12.99)
    got = client.get(f"/api/v1/products/{p['id']}", headers=auth).json()
    assert got["price_cost"] == 12.99


def test_pagination_and_total_header(client, auth):
    # Create a handful so pages are meaningful.
    for _ in range(5):
        _mk_product(client, auth)
    r = client.get("/api/v1/products?limit=2&offset=0", headers=auth)
    assert r.status_code == 200
    assert "x-total-count" in {k.lower() for k in r.headers}
    assert int(r.headers["X-Total-Count"]) >= 5
    assert len(r.json()) == 2
    # out-of-range limit rejected
    assert client.get("/api/v1/products?limit=0", headers=auth).status_code == 422
    assert client.get("/api/v1/products?limit=9999", headers=auth).status_code == 422


def test_picking_flow_with_barcode(client, auth):
    p = _mk_product(client, auth)
    loc = _mk_location(client, auth)
    client.post("/api/v1/movements", headers=auth, json={
        "type": "ENTRY",
        "lines": [{"product_id": p["id"], "location_id": loc["id"], "quantity": 10}],
    })
    order = client.post("/api/v1/orders", headers=auth, json={
        "customer_name": "C",
        "lines": [{"product_id": p["id"], "quantity_requested": 2, "location_id": loc["id"]}],
    }).json()
    oid = order["id"]

    me = client.get("/api/v1/employees/me", headers=auth).json()
    r = client.post(f"/api/v1/orders/{oid}/start-picking", headers=auth,
                    json={"picker_id": me["id"]})
    assert r.status_code == 200, r.text

    pick_list = client.get(f"/api/v1/orders/{oid}/picking-list", headers=auth).json()
    assert pick_list
    line_id = pick_list[0]["line_id"]

    # Correct barcode picks the line.
    r = client.post(
        f"/api/v1/orders/{oid}/lines/{line_id}/pick",
        headers=auth,
        json={"barcode_scanned": p["barcode"], "quantity_picked": 2},
    )
    assert r.status_code == 200, r.text


def test_picking_rejects_wrong_barcode(client, auth):
    p = _mk_product(client, auth)
    loc = _mk_location(client, auth)
    client.post("/api/v1/movements", headers=auth, json={
        "type": "ENTRY",
        "lines": [{"product_id": p["id"], "location_id": loc["id"], "quantity": 5}],
    })
    order = client.post("/api/v1/orders", headers=auth, json={
        "customer_name": "C",
        "lines": [{"product_id": p["id"], "quantity_requested": 1, "location_id": loc["id"]}],
    }).json()
    oid = order["id"]
    me = client.get("/api/v1/employees/me", headers=auth).json()
    client.post(f"/api/v1/orders/{oid}/start-picking", headers=auth, json={"picker_id": me["id"]})
    line_id = client.get(f"/api/v1/orders/{oid}/picking-list", headers=auth).json()[0]["line_id"]

    r = client.post(
        f"/api/v1/orders/{oid}/lines/{line_id}/pick",
        headers=auth,
        json={"barcode_scanned": "WRONG-CODE", "quantity_picked": 1},
    )
    assert r.status_code == 400, r.text
