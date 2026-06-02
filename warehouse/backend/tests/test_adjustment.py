"""Password-gated stock adjustment tests (C7)."""
import uuid

from tests.conftest import ADMIN_PASSWORD
from tests.test_stock import _mk_product, _mk_location


def test_adjustment_with_correct_password(client, auth):
    p = _mk_product(client, auth)
    loc = _mk_location(client, auth)
    client.post("/api/v1/movements", headers=auth, json={
        "type": "ENTRY", "lines": [{"product_id": p["id"], "location_id": loc["id"], "quantity": 10}],
    })
    # +5 adjustment
    r = client.post("/api/v1/movements/adjustment", headers=auth, json={
        "product_id": p["id"], "location_id": loc["id"],
        "quantity": 5, "reason": "recuento físico", "password": ADMIN_PASSWORD,
    })
    assert r.status_code == 201, r.text
    assert client.get(f"/api/v1/products/{p['id']}", headers=auth).json()["current_stock"] == 15
    # -4 adjustment (signed)
    r = client.post("/api/v1/movements/adjustment", headers=auth, json={
        "product_id": p["id"], "quantity": -4, "reason": "merma", "password": ADMIN_PASSWORD,
    })
    assert r.status_code == 201, r.text
    assert client.get(f"/api/v1/products/{p['id']}", headers=auth).json()["current_stock"] == 11


def test_adjustment_wrong_password_rejected(client, auth):
    p = _mk_product(client, auth)
    r = client.post("/api/v1/movements/adjustment", headers=auth, json={
        "product_id": p["id"], "quantity": 5, "reason": "ajuste", "password": "WRONG",
    })
    assert r.status_code == 401, r.text


def test_generic_movement_rejects_adjustment_type(client, auth):
    p = _mk_product(client, auth)
    r = client.post("/api/v1/movements", headers=auth, json={
        "type": "ADJUSTMENT", "lines": [{"product_id": p["id"], "quantity": 3}],
    })
    assert r.status_code == 403, r.text


def test_adjustment_requires_manager_role(client, auth):
    # Create a PICKER and verify they cannot adjust stock even with their password.
    suffix = uuid.uuid4().hex[:6]
    pwd = "pickerpass123"
    emp = client.post("/api/v1/employees", headers=auth, json={
        "employee_number": f"E-{suffix}", "name": "Pick", "surname": "Er",
        "dni": f"D{suffix}", "email": f"pick-{suffix}@d.com", "role": "PICKER",
        "password": pwd,
    })
    assert emp.status_code == 201, emp.text
    tok = client.post("/api/v1/employees/login", json={
        "email": f"pick-{suffix}@d.com", "password": pwd,
    }).json()["access_token"]
    ph = {"Authorization": f"Bearer {tok}"}
    p = _mk_product(client, auth)
    r = client.post("/api/v1/movements/adjustment", headers=ph, json={
        "product_id": p["id"], "quantity": 5, "reason": "ajuste", "password": pwd,
    })
    assert r.status_code == 403, r.text
