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
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy import select

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database import create_tables, AsyncSessionLocal
from app.auth import hash_password, get_current_employee
from app.limiter import limiter
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
    portal_auth,
    portal,
    customer_requests,
    customers,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "frontend", "static"))
TEMPLATES_DIR = os.path.abspath(
    os.path.join(BASE_DIR, "..", "..", "frontend", "templates")
)


async def _create_default_admin() -> None:
    """Seed a bootstrap admin if no employees exist yet.

    The password comes from ADMIN_PASSWORD (env). In production (DEBUG=False) we
    refuse to seed a weak default: if ADMIN_PASSWORD is unset, seeding is skipped
    and a warning is logged. In development a throwaway default is used.
    """
    import logging
    from app.models.employee import Employee, EmployeeRole

    log = logging.getLogger("wms.bootstrap")

    password = settings.ADMIN_PASSWORD
    if not password:
        if settings.DEBUG:
            password = "admin123"
            log.warning(
                "ADMIN_PASSWORD no definido: usando contraseña de desarrollo "
                "'admin123'. NO usar en producción."
            )
        else:
            log.warning(
                "ADMIN_PASSWORD no definido en producción: no se crea admin "
                "bootstrap. Define ADMIN_EMAIL/ADMIN_PASSWORD para sembrarlo."
            )
            return

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Employee).limit(1))
        if result.scalar_one_or_none() is not None:
            return
        admin = Employee(
            employee_number="ADM-001",
            name="Administrador",
            surname="Sistema",
            dni="00000000A",
            email=settings.ADMIN_EMAIL,
            role=EmployeeRole.ADMIN,
            is_active=True,
            salary_base=0.0,
            hashed_password=hash_password(password),
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
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Rate limiting (SlowAPI): per-route decorator on /employees/login. We register
# the limiter + handler only (NO SlowAPIMiddleware): that middleware is a
# Starlette BaseHTTPMiddleware which breaks SQLAlchemy's async greenlet context
# during selectin serialization on write endpoints. Decorator-based limits don't
# need it.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ---- API routers -----------------------------------------------------------
API_PREFIX = "/api/v1"
# Routers whose every endpoint requires an authenticated employee. Applied at
# include time so no sensitive GET (stock, orders, movements, emails…) is ever
# left public by omission. The `employees` router is the exception: it owns the
# public `POST /login`, so it guards its own endpoints individually.
auth_dep = [Depends(get_current_employee)]
app.include_router(dashboard.router, prefix=API_PREFIX, dependencies=auth_dep)
app.include_router(products.router, prefix=API_PREFIX, dependencies=auth_dep)
app.include_router(locations.router, prefix=API_PREFIX, dependencies=auth_dep)
app.include_router(movements.router, prefix=API_PREFIX, dependencies=auth_dep)
app.include_router(replenishments.router, prefix=API_PREFIX, dependencies=auth_dep)
app.include_router(orders.router, prefix=API_PREFIX, dependencies=auth_dep)
app.include_router(trucks.router, prefix=API_PREFIX, dependencies=auth_dep)
app.include_router(employees.router, prefix=API_PREFIX)
app.include_router(emails.router, prefix=API_PREFIX, dependencies=auth_dep)

# ---- Client portal (separate auth realm; routers carry their own prefix) ----
app.include_router(portal_auth.router)
app.include_router(portal.router)
# Office-side customer management + change-request review (employee-gated).
app.include_router(customers.router, prefix=API_PREFIX, dependencies=auth_dep)
app.include_router(customer_requests.router, prefix=API_PREFIX, dependencies=auth_dep)

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


@app.get("/portal-sw.js", include_in_schema=False)
async def portal_service_worker():
    return FileResponse(
        os.path.join(STATIC_DIR, "js", "portal-sw.js"),
        media_type="application/javascript",
    )


PAGES = {
    "/": "dashboard.html",
    "/portal": "portal.html",
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
