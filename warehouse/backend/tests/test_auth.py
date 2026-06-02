"""Auth, RBAC gating and refresh-token tests (R2/H3)."""
import httpx

from tests.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, _start_server


def test_login_ok_returns_access_and_refresh(client):
    r = client.post(
        "/api/v1/employees/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["employee"]["email"] == ADMIN_EMAIL


def test_login_bad_password_401(client):
    r = client.post(
        "/api/v1/employees/login",
        json={"email": ADMIN_EMAIL, "password": "wrong"},
    )
    assert r.status_code == 401


def test_sensitive_get_requires_auth(client):
    # H3: these must not be public.
    for path in ("/api/v1/products", "/api/v1/orders", "/api/v1/movements",
                 "/api/v1/dashboard/stats", "/api/v1/emails/messages"):
        assert client.get(path).status_code == 401, path


def test_get_with_token_ok(client, auth):
    assert client.get("/api/v1/products", headers=auth).status_code == 200
    assert client.get("/api/v1/dashboard/stats", headers=auth).status_code == 200


def test_refresh_then_logout_revokes(client):
    login = client.post(
        "/api/v1/employees/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    ).json()
    refresh = login["refresh_token"]

    # refresh -> new access token
    r = client.post("/api/v1/employees/refresh", json={"refresh_token": refresh})
    assert r.status_code == 200
    assert r.json()["access_token"]

    # logout revokes; subsequent refresh fails
    assert client.post("/api/v1/employees/logout", json={"refresh_token": refresh}).status_code == 200
    assert client.post("/api/v1/employees/refresh", json={"refresh_token": refresh}).status_code == 401


def test_refresh_rejects_garbage(client):
    assert client.post("/api/v1/employees/refresh", json={"refresh_token": "not-a-jwt"}).status_code == 401


def test_login_rate_limited(tmp_path_factory):
    # Dedicated server with a tight login limit so we don't trip the shared one.
    tmp_path = tmp_path_factory.mktemp("wms_rl")
    proc, base_url = _start_server(tmp_path, {"LOGIN_RATE_LIMIT": "3/minute"})
    try:
        with httpx.Client(base_url=base_url, timeout=10) as c:
            codes = [
                c.post("/api/v1/employees/login",
                       json={"email": "x@x.com", "password": "bad"}).status_code
                for _ in range(5)
            ]
        assert 429 in codes, codes
        assert codes[:3] == [401, 401, 401], codes
    finally:
        proc.terminate()
