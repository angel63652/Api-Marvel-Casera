"""Excel export tests (C6)."""
import io
import zipfile

XLSX_MAGIC = b"PK\x03\x04"  # xlsx is a zip


def _is_valid_xlsx(content: bytes) -> bool:
    if not content.startswith(XLSX_MAGIC):
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            return "xl/workbook.xml" in z.namelist()
    except zipfile.BadZipFile:
        return False


def test_truck_history_export_xlsx(client, auth):
    r = client.get("/api/v1/trucks/schedules/history/export", headers=auth)
    assert r.status_code == 200, r.text
    assert "spreadsheetml" in r.headers["content-type"]
    assert "attachment" in r.headers.get("content-disposition", "")
    assert _is_valid_xlsx(r.content)


def test_payroll_report_export_xlsx(client, auth):
    # Seed one payroll so the sheet has a data row.
    me = client.get("/api/v1/employees/me", headers=auth).json()
    client.post(f"/api/v1/employees/{me['id']}/payrolls", headers=auth, json={
        "employee_id": me["id"], "year": 2026, "month": 6,
        "salary_base": 1500.0, "bonuses": 100.0, "deductions": 50.0,
    })
    r = client.get("/api/v1/employees/payrolls/report/2026/6/export", headers=auth)
    assert r.status_code == 200, r.text
    assert _is_valid_xlsx(r.content)


def test_export_requires_auth(client):
    assert client.get("/api/v1/trucks/schedules/history/export").status_code == 401
    assert client.get("/api/v1/employees/payrolls/report/2026/6/export").status_code == 401
    assert client.get("/api/v1/products/export").status_code == 401
    assert client.get("/api/v1/orders/export").status_code == 401


def test_products_export_xlsx(client, auth):
    # Seed one product
    client.post("/api/v1/products", headers=auth, json={
        "niu": "NIU-EXP-001", "barcode": "NIU-EXP-001",
        "name": "Producto Exportación", "category": "TEST",
        "unit": "unit", "min_stock": 1, "current_stock": 5,
    })
    r = client.get("/api/v1/products/export", headers=auth)
    assert r.status_code == 200, r.text
    assert "spreadsheetml" in r.headers["content-type"]
    assert "attachment" in r.headers.get("content-disposition", "")
    assert _is_valid_xlsx(r.content)


def test_orders_export_xlsx(client, auth):
    r = client.get("/api/v1/orders/export", headers=auth)
    assert r.status_code == 200, r.text
    assert _is_valid_xlsx(r.content)
