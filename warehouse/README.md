# WMS Almacén — Distrigal SL

Sistema de gestión de almacén con entradas/salidas de mercancía, ubicaciones por
pasillos, picking con lector de códigos de barras (o pantalla táctil), entrega de
órdenes con conformidad, gestión de camiones, empleados/nóminas, calendario
inteligente y filtrado de correos de clientes con IA (Claude) + Gmail.

## Arranque rápido (desarrollo, SQLite)

```bash
cd warehouse/backend
pip install -r requirements.txt
DATABASE_URL="sqlite+aiosqlite:///./wms.db" uvicorn app.main:app --reload
```

- Web/UI: http://localhost:8000/
- API docs (Swagger): http://localhost:8000/docs
- Health: http://localhost:8000/health

**Usuario por defecto:** `admin@distrigal.com` / `admin123` (rol ADMIN)

## Arranque con PostgreSQL (Docker)

```bash
cd warehouse
cp backend/.env.example backend/.env   # edita SECRET_KEY, ANTHROPIC_API_KEY...
docker compose up --build
```

## Estructura

```
warehouse/
├── backend/                  FastAPI + SQLAlchemy async + PostgreSQL
│   ├── app/
│   │   ├── models/           8 modelos de dominio
│   │   ├── schemas/          esquemas Pydantic v2
│   │   ├── routers/          9 routers (54 endpoints) bajo /api/v1
│   │   ├── services/         stock, picking, email (IA)
│   │   ├── auth.py           JWT + bcrypt + roles
│   │   ├── config.py         settings (.env)
│   │   ├── database.py       engine async + get_db
│   │   └── main.py           app, rutas SSR, bootstrap admin
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/                 PWA (HTML + Tailwind + Alpine.js)
│   ├── templates/            12 páginas (dashboard, picking, etc.)
│   └── static/               css, js, manifest, service worker
└── docker-compose.yml

```

## Roles

| Rol | Acceso |
|-----|--------|
| ADMIN | Todo (super usuario) |
| MANAGER | Stock, nóminas, aprobaciones, camiones |
| OFFICE | Órdenes, clientes, correos |
| PICKER | Picking de órdenes |
| DRIVER | Rutas y entregas |

Ver `ESTADO_PROYECTO.md` (raíz del repo) para el estado completo y la hoja de ruta.
