"""Client portal auth tests (P2): realm isolation + tenancy."""
import uuid


def _register(client, **over):
    suffix = uuid.uuid4().hex[:8]
    payload = {
        "company_name": f"Tienda {suffix}",
        "tax_id": f"B{suffix}",
        "email": f"owner-{suffix}@shop.com",
        "password": "supersecret123",
        "name": "Owner",
    }
    payload.update(over)
    return client.post("/api/portal/auth/register", json=payload)


def test_register_creates_pending_customer_and_returns_token(client):
    r = _register(client)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["access_token"]
    assert body["customer"]["status"] == "PENDING"
    assert body["user"]["role"] == "OWNER"


def test_register_rejects_duplicate_tax_id(client):
    r1 = _register(client, tax_id="BDUP123", email=f"a-{uuid.uuid4().hex[:6]}@s.com")
    assert r1.status_code == 201
    r2 = _register(client, tax_id="BDUP123", email=f"b-{uuid.uuid4().hex[:6]}@s.com")
    assert r2.status_code == 400


def test_portal_login_and_me(client):
    reg = _register(client).json()
    email = reg["user"]["email"]
    r = client.post("/api/portal/auth/login", json={"email": email, "password": "supersecret123"})
    assert r.status_code == 200, r.text
    tok = r.json()["access_token"]
    me = client.get("/api/portal/auth/me", headers={"Authorization": f"Bearer {tok}"})
    assert me.status_code == 200
    assert me.json()["user"]["email"] == email


def test_portal_login_bad_password(client):
    reg = _register(client).json()
    email = reg["user"]["email"]
    r = client.post("/api/portal/auth/login", json={"email": email, "password": "wrongpass1"})
    assert r.status_code == 401


def test_customer_token_rejected_on_employee_api(client):
    # A portal token must not access internal employee endpoints.
    tok = _register(client).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    assert client.get("/api/v1/products", headers=h).status_code in (401, 403)
    assert client.get("/api/v1/dashboard/stats", headers=h).status_code in (401, 403)


def test_employee_token_rejected_on_portal_me(client, admin_token):
    # An employee token must not pass the portal realm.
    h = {"Authorization": f"Bearer {admin_token}"}
    assert client.get("/api/portal/auth/me", headers=h).status_code == 401
