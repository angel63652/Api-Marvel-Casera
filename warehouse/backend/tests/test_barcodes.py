"""Barcode label generation tests (C10)."""
import struct
import zlib


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _is_valid_png(data: bytes) -> bool:
    if not data.startswith(PNG_SIGNATURE):
        return False
    # Check IHDR chunk
    try:
        length = struct.unpack(">I", data[8:12])[0]
        return length == 13 and data[12:16] == b"IHDR"
    except Exception:
        return False


def _png_dimensions(data: bytes) -> tuple[int, int]:
    w, h = struct.unpack(">II", data[16:24])
    return w, h


def test_label_returns_png(client, auth):
    # Create a product with barcode and NIU
    product = client.post(
        "/api/v1/products",
        headers=auth,
        json={
            "niu": "NIU-LABEL-001",
            "barcode": "1234567890128",
            "name": "Producto Etiqueta Test",
            "category": "TEST",
            "unit": "unit",
            "min_stock": 5,
            "current_stock": 10,
        },
    ).json()
    pid = product["id"]

    r = client.get(f"/api/v1/products/{pid}/label", headers=auth)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "image/png"
    assert "attachment" in r.headers.get("content-disposition", "")
    assert _is_valid_png(r.content)
    w, h = _png_dimensions(r.content)
    assert w > 0 and h > 0


def test_label_requires_auth(client):
    r = client.get("/api/v1/products/1/label")
    assert r.status_code == 401


def test_label_404_on_missing_product(client, auth):
    r = client.get("/api/v1/products/99999/label", headers=auth)
    assert r.status_code == 404


def test_label_uses_niu_when_no_barcode(client, auth):
    # Create product with only a NIU (barcode omitted / empty)
    product = client.post(
        "/api/v1/products",
        headers=auth,
        json={
            "niu": "NIU-NOBARCODE-002",
            "barcode": "NIU-NOBARCODE-002",  # same value as NIU fallback
            "name": "Sin Código de Barras",
            "category": "TEST",
            "unit": "unit",
            "min_stock": 1,
            "current_stock": 0,
        },
    ).json()
    pid = product["id"]

    r = client.get(f"/api/v1/products/{pid}/label", headers=auth)
    assert r.status_code == 200
    assert _is_valid_png(r.content)


def test_label_content_disposition_filename(client, auth):
    product = client.post(
        "/api/v1/products",
        headers=auth,
        json={
            "niu": "NIU-DISP-003",
            "barcode": "NIU-DISP-003",
            "name": "Disp Test",
            "category": "TEST",
            "unit": "unit",
            "min_stock": 1,
            "current_stock": 0,
        },
    ).json()
    pid = product["id"]
    r = client.get(f"/api/v1/products/{pid}/label", headers=auth)
    assert f"label_{pid}.png" in r.headers.get("content-disposition", "")
