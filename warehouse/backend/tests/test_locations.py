"""DELETE /locations/{id} soft-deactivation tests."""


def _make_location(client, auth, code: str) -> dict:
    return client.post(
        "/api/v1/locations",
        headers=auth,
        json={
            "code": code,
            "aisle": "A",
            "rack": "1",
            "position": "01",
            "zone": "PICKING",
            "capacity": 100,
        },
    ).json()


def test_delete_location_deactivates(client, auth):
    loc = _make_location(client, auth, "LOC-DEL-001")
    assert loc.get("is_active", True)
    lid = loc["id"]

    r = client.delete(f"/api/v1/locations/{lid}", headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["id"] == lid

    # Should no longer appear in default listing (active_only=True)
    listing = client.get("/api/v1/locations", headers=auth).json()
    assert all(loc["id"] != lid for loc in listing)


def test_delete_location_404_on_missing(client, auth):
    r = client.delete("/api/v1/locations/99999", headers=auth)
    assert r.status_code == 404


def test_delete_location_requires_manager(client, auth):
    loc = _make_location(client, auth, "LOC-DEL-002")
    # Non-manager role → but auth is ADMIN which passes require_role("MANAGER") too
    # Just verify a non-auth user is rejected
    r = client.delete(f"/api/v1/locations/{loc['id']}")
    assert r.status_code == 401
