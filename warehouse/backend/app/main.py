"""WMS Almacén - Distrigal SL.

FastAPI application entry point: wires routers, static files, server-rendered
pages, startup table creation and a bootstrap admin user.
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from app.config import settings
from app.database import create_tables, AsyncSessionLocal
from app.auth import hash_password
from app.routers import (
    products,
    locations,
    movements,
    replenishments,
    orders,
    trucks,
    employees,
    emails,
    dashboard,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "frontend", "static"))
TEMPLATES_DIR = os.path.abspath(
    os.path.join(BASE_DIR, "..", "..", "frontend", "templates")
)


async def _create_default_admin() -> None:
    """Create the bootstrap admin account if no employees exist yet."""
    from app.models.employee import Employee, EmployeeRole

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Employee).limit(1))
        if result.scalar_one_or_none() is not None:
            return
        admin = Employee(
            employee_number="ADM-001",
            name="Administrador",
            surname="Sistema",
            dni="00000000A",
            email="admin@distrigal.com",
            role=EmployeeRole.ADMIN,
            is_active=True,
            salary_base=0.0,
            hashed_password=hash_password("admin123"),
        )
        db.add(admin)
        await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    await _create_default_admin()
    yield


app = FastAPI(
    title="WMS Almacén - Distrigal SL",
    description="Sistema de gestión de almacén: stock, picking, camiones, "
    "empleados, nóminas y correos con IA.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- API routers -----------------------------------------------------------
API_PREFIX = "/api/v1"
app.include_router(dashboard.router, prefix=API_PREFIX)
app.include_router(products.router, prefix=API_PREFIX)
app.include_router(locations.router, prefix=API_PREFIX)
app.include_router(movements.router, prefix=API_PREFIX)
app.include_router(replenishments.router, prefix=API_PREFIX)
app.include_router(orders.router, prefix=API_PREFIX)
app.include_router(trucks.router, prefix=API_PREFIX)
app.include_router(employees.router, prefix=API_PREFIX)
app.include_router(emails.router, prefix=API_PREFIX)

# ---- Static files & templates ---------------------------------------------
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

templates = Jinja2Templates(directory=TEMPLATES_DIR)


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME, "version": "1.0.0"}


# ---- Server-rendered pages -------------------------------------------------
@app.get("/login", response_class=HTMLResponse, include_in_schema=False)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")


PAGES = {
    "/": "dashboard.html",
    "/products": "products.html",
    "/locations": "locations.html",
    "/movements": "movements.html",
    "/replenishments": "replenishments.html",
    "/orders": "orders.html",
    "/trucks": "trucks.html",
    "/employees": "employees.html",
    "/calendar": "calendar.html",
    "/emails": "emails.html",
}


def _make_page(template_name: str):
    async def _page(request: Request):
        return templates.TemplateResponse(request, template_name)

    return _page


for path, template_name in PAGES.items():
    app.add_api_route(
        path,
        _make_page(template_name),
        methods=["GET"],
        response_class=HTMLResponse,
        include_in_schema=False,
    )


@app.get("/picking/{order_id}", response_class=HTMLResponse, include_in_schema=False)
async def picking_page(request: Request, order_id: int):
    return templates.TemplateResponse(
        request, "picking.html", {"order_id": order_id}
    )


@app.get("/picking", response_class=HTMLResponse, include_in_schema=False)
async def picking_index(request: Request):
    return templates.TemplateResponse(
        request, "picking.html", {"order_id": None}
    )
