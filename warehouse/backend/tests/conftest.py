"""Test fixtures: spin up a real uvicorn server against a temp SQLite DB.

We use a real server (not httpx.ASGITransport) on purpose: the in-process ASGI
transport does not propagate SQLAlchemy's async greenlet context, which makes
selectin relationship loads during response serialization raise a spurious
MissingGreenlet on write endpoints. A real uvicorn process behaves correctly.
"""
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
ADMIN_EMAIL = "admin@distrigal.com"
ADMIN_PASSWORD = "admin123"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_server(tmp_path: Path, extra_env: dict | None = None):
    port = _free_port()
    db_path = tmp_path / "test.db"
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite+aiosqlite:///{db_path}",
        "DEBUG": "False",
        "SECRET_KEY": "test-secret-key-for-pytest-only-0123456789abcdef",
        "ADMIN_EMAIL": ADMIN_EMAIL,
        "ADMIN_PASSWORD": ADMIN_PASSWORD,
        "CORS_ORIGINS": '["http://localhost"]',
        "LOGIN_RATE_LIMIT": "1000/minute",
        "PYTHONPATH": str(BACKEND_DIR),
    }
    if extra_env:
        env.update(extra_env)

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port)],
        cwd=str(BACKEND_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    base_url = f"http://127.0.0.1:{port}"
    # Wait for readiness.
    deadline = time.time() + 30
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(
                "uvicorn exited early:\n" + proc.stdout.read().decode(errors="replace")
            )
        try:
            r = httpx.get(f"{base_url}/health", timeout=1)
            if r.status_code == 200:
                break
        except Exception:
            time.sleep(0.3)
    else:
        proc.terminate()
        raise RuntimeError("server did not become ready in time")
    return proc, base_url


@pytest.fixture(scope="session")
def server(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("wms")
    proc, base_url = _start_server(tmp_path)
    yield base_url
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture()
def client(server):
    with httpx.Client(base_url=server, timeout=10) as c:
        yield c


@pytest.fixture()
def admin_token(client) -> str:
    r = client.post(
        "/api/v1/employees/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture()
def auth(admin_token) -> dict:
    return {"Authorization": f"Bearer {admin_token}"}
