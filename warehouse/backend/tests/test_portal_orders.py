"""Client portal API tests (P3): catalog pricing, ordering, tenancy, change-requests."""
import uuid

from tests.conftest import ADMIN_EMAIL, ADMIN_PASSWORD
from tests.test_stock import _mk_product, _mk_location


def _register_active(client, auth, *, tier="GENERAL"):
    """Register a portal customer and have the office approve it (ACTIVE)."""
    suffix = uuid.uuid4().hex[:8]
    reg = client.post("/api/portal/auth/register", json={
        "company_name": f"Shop {suffix}", "tax_id": f"B{suffix}",
        "email": f"o-{suffix}@shop.com", "password": "supersecret123", "name": "O",
    }).json()
    customer_id = reg["customer"]["id"]
    # Office approves + sets tier.
    r = client.post(f"/api/v1/customers/{customer_id}/approve?price_tier={tier}", headers=auth)
    assert r.status_code == 200, r.text
    # Re-login to get a token reflecting ACTIVE.
    tok = client.post("/api/portal/auth/login", json={
        "email": reg["user"]["email"], "password": "supersecret123",
    }).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}, customer_id, reg["user"]["email"]


def _stock(client, auth, pid, lid, qty):
    client.post("/api/v1/movements", headers=auth, json={
        "type": "ENTRY", "lines": [{"product_id": pid, "location_id": lid, "quantity": qty}],
    })


def test_catalog_shows_available_and_tier_price(client, auth):
    p = _mk_product(client, auth, price_base=10.0)
    loc = _mk_location(client, auth)
    _stock(client, auth, p["id"], loc["id"], 8)
    # tier price override for GOLD
    client.put(f"/api/v1/products/{p['id']}/tier-prices?tier=GOLD&price=7.5", headers=auth)

    ph, *_ = _register_active(client, auth, tier="GOLD")
    cat = client.get("/api/portal/catalog", headers=ph)
    assert cat.status_code == 200, cat.text
    item = next(i for i in cat.json() if i["id"] == p["id"])
    assert item["available_stock"] == 8
    assert item["price"] == 7.5  # GOLD tier price wins over base 10.0


def test_portal_order_reserves_and_blocks_oversell(client, auth):
    p = _mk_product(client, auth, price_base=5.0)
    loc = _mk_location(client, auth)
    _stock(client, auth, p["id"], loc["id"], 10)
    ph, customer_id, _ = _register_active(client, auth)

    # Order within stock works and reserves.
    r = client.post("/api/portal/orders", headers=ph, json={
        "items": [{"product_id": p["id"], "quantity": 6}],
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["order_number"].startswith("ORD-")
    assert body["total"] == 30.0  # 6 * 5.0

    prod = client.get(f"/api/v1/products/{p['id']}", headers=auth).json()
    assert prod["reserved_stock"] == 6
    assert prod["available_stock"] == 4

    # Second order exceeding available is blocked (no overselling).
    r2 = client.post("/api/portal/orders", headers=ph, json={
        "items": [{"product_id": p["id"], "quantity": 5}],
    })
    assert r2.status_code == 409, r2.text


def test_pending_customer_cannot_order(client, auth):
    # Register but DON'T approve -> PENDING -> ordering forbidden.
    suffix = uuid.uuid4().hex[:8]
    reg = client.post("/api/portal/auth/register", json={
        "company_name": f"Shop {suffix}", "tax_id": f"B{suffix}",
        "email": f"o-{suffix}@shop.com", "password": "supersecret123",
    }).json()
    ph = {"Authorization": f"Bearer {reg['access_token']}"}
    p = _mk_product(client, auth)
    r = client.post("/api/portal/orders", headers=ph, json={
        "items": [{"product_id": p["id"], "quantity": 1}],
    })
    assert r.status_code == 403, r.text


def test_order_tenancy_isolation(client, auth):
    p = _mk_product(client, auth, price_base=1.0)
    loc = _mk_location(client, auth)
    _stock(client, auth, p["id"], loc["id"], 20)
    a_h, _, _ = _register_active(client, auth)
    b_h, _, _ = _register_active(client, auth)

    order = client.post("/api/portal/orders", headers=a_h, json={
        "items": [{"product_id": p["id"], "quantity": 1}],
    }).json()
    oid = order["id"]
    # A sees it; B does not.
    assert client.get(f"/api/portal/orders/{oid}", headers=a_h).status_code == 200
    assert client.get(f"/api/portal/orders/{oid}", headers=b_h).status_code == 404
    assert all(o["id"] != oid for o in client.get("/api/portal/orders", headers=b_h).json())


def test_change_request_flow_with_office_approval(client, auth):
    ph, customer_id, _ = _register_active(client, auth)
    # Customer requests a fiscal change.
    cr = client.post("/api/portal/profile/change-request", headers=ph, json={
        "target": "FISCAL", "payload": {"contact_phone": "600111222"},
    })
    assert cr.status_code == 201, cr.text
    cr_id = cr.json()["id"]

    # Office sees it pending and approves -> applied to master data.
    pending = client.get("/api/v1/customer-requests?status=PENDING", headers=auth).json()
    assert any(r["id"] == cr_id for r in pending)
    ap = client.post(f"/api/v1/customer-requests/{cr_id}/approve", headers=auth)
    assert ap.status_code == 200, ap.text
    assert ap.json()["status"] == "APPROVED"

    prof = client.get("/api/portal/profile", headers=ph).json()
    assert prof["contact_phone"] == "600111222"
