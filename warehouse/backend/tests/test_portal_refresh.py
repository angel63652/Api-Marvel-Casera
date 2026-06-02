"""Portal refresh-token tests (P7)."""
import uuid


def _register(client):
    suffix = uuid.uuid4().hex[:8]
    return client.post("/api/portal/auth/register", json={
        "company_name": f"Shop {suffix}", "tax_id": f"B{suffix}",
        "email": f"o-{suffix}@shop.com", "password": "supersecret123", "name": "O",
    }).json()


def test_register_and_login_return_refresh(client):
    reg = _register(client)
    assert reg["refresh_token"]
    login = client.post("/api/portal/auth/login", json={
        "email": reg["user"]["email"], "password": "supersecret123",
    }).json()
    assert login["refresh_token"]


def test_portal_refresh_then_logout_revokes(client):
    reg = _register(client)
    refresh = reg["refresh_token"]

    r = client.post("/api/portal/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 200, r.text
    new_access = r.json()["access_token"]
    assert new_access
    # The new access token works on a portal endpoint.
    me = client.get("/api/portal/auth/me", headers={"Authorization": f"Bearer {new_access}"})
    assert me.status_code == 200

    assert client.post("/api/portal/auth/logout", json={"refresh_token": refresh}).status_code == 200
    assert client.post("/api/portal/auth/refresh", json={"refresh_token": refresh}).status_code == 401


def test_portal_refresh_rejects_garbage(client):
    assert client.post("/api/portal/auth/refresh", json={"refresh_token": "nope"}).status_code == 401


def test_employee_refresh_not_valid_on_portal(client):
    # An employee refresh token must not work on the portal refresh endpoint.
    from tests.conftest import ADMIN_EMAIL, ADMIN_PASSWORD
    emp = client.post("/api/v1/employees/login", json={
        "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD,
    }).json()
    assert client.post(
        "/api/portal/auth/refresh", json={"refresh_token": emp["refresh_token"]}
    ).status_code == 401
