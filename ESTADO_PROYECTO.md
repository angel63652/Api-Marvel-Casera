# 📦 ESTADO DEL PROYECTO — WMS Almacén (Distrigal SL)

> **Archivo de coordinación conjunto** entre agentes (Claude Code + Codex).
> Última actualización: **2026-06-01** · Rama: `claude/warehouse-management-system-vmW4R`

Este documento es la **fuente de verdad** del estado del proyecto. Cualquier agente
(Claude o Codex) debe leerlo antes de trabajar y actualizarlo al terminar.

---

## 1. Resumen del proyecto

Sistema de gestión de almacén de mercancía para **Distrigal SL** con:
- Entradas y salidas de mercancía, ubicaciones por **pasillos / racks / posiciones**.
- **Reposiciones** (auto-generadas desde stock bajo).
- **Picking** de órdenes con lector de códigos de barras o pantalla táctil (móvil).
- **Observaciones** en picking (producto no encontrado, error de ubicación).
- **Conformidad** al completar la orden (firma del operario/responsable).
- Reconocimiento por **NIU** y por **código de barras**.
- **Camiones propios**: flota, programación diaria/semanal/mensual, histórico, devoluciones.
- **Empleados propios**: personal, **nóminas**, **calendario inteligente**.
- **Correos de clientes** filtrados por **IA (Claude)** → carpeta del cliente + aviso a oficina.
- Integración **Gmail / Google Workspace**.

---

## 2. Stack tecnológico (DECISIONES TOMADAS)

| Capa | Tecnología | Notas |
|------|-----------|-------|
| Backend | **FastAPI** + SQLAlchemy 2 (async) | Python 3.12 |
| Base de datos | **PostgreSQL 16** (prod) / SQLite (dev) | `asyncpg` / `aiosqlite` |
| Frontend | **HTML + Tailwind (CDN) + Alpine.js** | PWA (web + móvil), no build step |
| Auth | **JWT (HS256)** + **bcrypt** | `python-jose`, `bcrypt` directo |
| IA correos | **Claude API** (`claude-sonnet-4-6`) | Anthropic SDK async |
| Email | **Gmail API** (OAuth2) | pendiente conectar credenciales |
| Infra | **Docker Compose** | `db` + `backend` |

Decisiones del usuario: Frontend **web + móvil** · BD **PostgreSQL** · prioridad
inicial **almacén + picking** · integraciones **Claude API + Gmail**.

---

## 3. Parámetros y configuración

### Variables de entorno (`warehouse/backend/.env.example`)
```
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/warehouse_db
SECRET_KEY=cambia-esta-clave-en-produccion
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
ANTHROPIC_API_KEY=            # <-- pendiente: pegar clave real
GMAIL_CLIENT_ID=              # <-- pendiente: OAuth Google
GMAIL_CLIENT_SECRET=          # <-- pendiente
GMAIL_REDIRECT_URI=http://localhost:8000/api/v1/emails/oauth-callback
APP_NAME=WMS Almacén
DEBUG=True
```

### Credenciales bootstrap (creadas al arrancar si no hay empleados)
- **Email:** `admin@distrigal.com`
- **Password:** `admin123`
- **Rol:** ADMIN
- ⚠️ **Cambiar en producción.**

### Puertos
- Backend API + UI: **8000**
- PostgreSQL: **5432**

### Roles y permisos
| Rol | Permisos clave |
|-----|----------------|
| `ADMIN` | Todo. Crea empleados. Desactiva productos. |
| `MANAGER` | Stock, ubicaciones, camiones, nóminas, aprobaciones. (jefe almacén/RRHH) |
| `OFFICE` | Órdenes, productos, clientes, correos. |
| `PICKER` | Picking de órdenes, recepción de reposiciones. |
| `DRIVER` | Completar rutas, registrar devoluciones. |

---

## 4. Modelo de datos (8 dominios, `warehouse/backend/app/models/`)

- **product.py** — `Product` (niu único, barcode único, current_stock, min_stock, unit).
- **location.py** — `Location` (code `A-01-03`, aisle/rack/position, capacity, current_load) + `ProductLocation` (M:N con cantidad).
- **movement.py** — `Movement` (ENTRY/EXIT/REPLENISHMENT/RETURN/ADJUSTMENT) + `MovementLine`.
- **replenishment.py** — `Replenishment` (PENDING/IN_PROGRESS/COMPLETED) + `ReplenishmentLine`.
- **order.py** — `Order` (PENDING/PICKING/COMPLETED/CANCELLED/RETURNED, conformity_signed) + `OrderLine` (PENDING/PICKED/MISSING/PARTIAL, observations).
- **truck.py** — `Truck` + `TruckSchedule` (DAILY/WEEKLY/MONTHLY, estimated/actual_cost) + `TruckReturn`.
- **employee.py** — `Employee` (role, hashed_password) + `Payroll` (year/month, net_salary) + `CalendarEvent` (TRUCK/PAYROLL/MEETING/DELIVERY/OTHER).
- **email_model.py** — `EmailClient` (carpeta + label Gmail) + `EmailMessage` (ai_category, ai_summary, ai_priority).

> El **stock se deriva del libro de movimientos** (ENTRY/REPLENISHMENT/RETURN suman; EXIT resta; ADJUSTMENT con signo). `Product.current_stock` se cachea para lectura rápida; recalculable con `stock_service.recalculate_and_store`.

---

## 5. API — 54 endpoints bajo `/api/v1` (9 routers)

| Router | Prefijo | Endpoints destacados |
|--------|---------|----------------------|
| dashboard | `/dashboard` | `GET /stats` |
| products | `/products` | CRUD, `GET /barcode/{b}`, `GET /niu/{n}`, `GET /{id}/stock`, `GET /low-stock` |
| locations | `/locations` | CRUD, `GET /aisle/{a}`, `POST /{id}/assign-product` |
| movements | `/movements` | `GET/POST`, `GET /report/summary` (actualiza stock) |
| replenishments | `/replenishments` | CRUD, `POST /auto-generate`, `POST /{id}/lines/{lid}/receive` |
| orders | `/orders` | CRUD, `picking-list`, `start-picking`, `lines/{lid}/pick`, `observe`, `confirm`, `return` |
| trucks | `/trucks` | flota + `schedules` (calendar/history/complete/returns) |
| employees | `/employees` | `login`, `me`, CRUD, payrolls, calendar |
| emails | `/emails` | clients, messages, `filter` (IA), `sync`, `notify` |

Swagger interactivo: `http://localhost:8000/docs`

---

## 6. Frontend (`warehouse/frontend/`)

12 plantillas en `templates/`: `base`, `dashboard`, `products`, `locations`,
`movements`, `replenishments`, `orders`, **`picking`** (móvil, táctil, escáner),
`trucks`, `employees`, `calendar`, `emails`.

`static/`: `css/style.css`, `js/app.js` (fetch wrapper, toasts, escáner USB),
`js/picking.js` (BarcodeScanner + PickingManager + cola offline), `manifest.json`,
`sw.js` (service worker PWA).

> ⚠️ **Aún sin pantalla de login ni guardado de token JWT en el frontend.** Las
> páginas SSR cargan pero las llamadas a la API que requieren rol fallarán con 401
> hasta que se implemente el login en el cliente. Ver tareas pendientes.

---

## 7. ✅ Estado actual — QUÉ FUNCIONA (probado end-to-end)

Verificado arrancando el servidor con SQLite y `curl`:

- [x] Arranque app, creación de 16 tablas, bootstrap admin.
- [x] `POST /employees/login` → JWT válido.
- [x] Crear producto (NIU + barcode), ubicación.
- [x] Entrada de stock (`POST /movements` ENTRY) → `current_stock` sube + carga ubicación.
- [x] `GET /products/{id}/stock` → desglose por ubicación.
- [x] Crear orden → estado PENDING.
- [x] `start-picking` → asigna operario, estado PICKING.
- [x] `picking-list` ordenada por pasillo/rack/posición.
- [x] **Picar con barcode correcto** → línea PICKED.
- [x] **Barcode incorrecto rechazado** (HTTP 400). ✓ validación
- [x] **Observación** "producto no encontrado" → línea MISSING.
- [x] **Conformidad** → orden COMPLETED + **descuento de stock** (50→45). ✓
- [x] `GET /dashboard/stats`.
- [x] Lookup por código de barras (escáner).
- [x] **Filtro IA de correos** (heurístico de respaldo sin API key; usa Claude si hay clave).

---

## 8. 🔧 DÓNDE CONTINUAR — Hoja de ruta para Codex

> **Codex: empieza por la TAREA C1** (login frontend) — es lo que desbloquea el uso
> real de la app. Trabaja en la rama `claude/warehouse-management-system-vmW4R`.
> Marca `[x]` aquí al terminar cada tarea y haz commit.

### 🔴 Prioridad ALTA (desbloqueantes)

- [x] **C1 — Login en el frontend.**
  - Crear `frontend/templates/login.html` + ruta `GET /login` en `app/main.py`.
  - En `static/js/app.js`: guardar el JWT en `localStorage`, añadir header
    `Authorization: Bearer <token>` en el `api()` wrapper, redirigir a `/login` si 401.
  - Mostrar usuario logueado + botón logout en `base.html`.

- [x] **C2 — Conectar las páginas SSR con sus endpoints reales.**
  - Revisar cada plantilla en `frontend/templates/` y verificar que los `fetch`
    apuntan a rutas existentes de la sección 5. Los agentes generaron el HTML pero
    no se ha validado el cableado contra la API real.
  - Páginas a revisar: `products`, `orders`, `picking`, `trucks`, `employees`, `emails`.

- [ ] **C3 — Migraciones Alembic.**
  - `alembic init`, configurar `env.py` para `Base.metadata` async, primera revisión.
  - Hoy las tablas se crean con `create_all` en startup (suficiente para dev, no para prod).

### 🟡 Prioridad MEDIA

- [ ] **C4 — OAuth Gmail real.**
  - Endpoint `GET /emails/oauth-callback`, guardar tokens, pasar `credentials` a
    `EmailService.sync_gmail` (ya implementado, solo falta inyectar credenciales).
  - Archivo: `app/services/email_service.py` (método `sync_gmail` listo).

- [ ] **C5 — Envío real de notificaciones a oficina.**
  - En `email_service.notify_office` hoy solo marca en BD. Añadir envío SMTP/Gmail.

- [ ] **C6 — Exportar a Excel** (camiones histórico, nóminas).
  - `openpyxl` ya está en requirements. Botón "Exportar Excel" existe en `trucks.html`.

- [ ] **C7 — Aprobación con contraseña para cambios de stock sensibles.**
  - El plan original pedía un endpoint `POST /employees/{id}/approve-action` que
    re-verifica la contraseña del MANAGER antes de un ajuste. NO implementado aún.
  - `verify_password` ya existe en `app/auth.py`.

- [ ] **C8 — WebSockets para alertas en tiempo real** entre roles (opcional).

### 🟢 Prioridad BAJA / pulido

- [ ] **C9 — Tests automatizados** (`pytest` + `httpx.AsyncClient`). No hay tests aún.
- [ ] **C10 — Generación de etiquetas de código de barras** (Pillow ya disponible).
- [ ] **C11 — Iconos PWA reales** (192x192, 512x512) en `static/icons/`.
- [ ] **C12 — Paginación** en listados largos (productos, órdenes, movimientos).

---

## 9. ⚠️ Notas técnicas / gotchas para el siguiente agente

1. **bcrypt directo, NO passlib.** Hubo un conflicto `passlib`/`bcrypt 4.x` en este
   entorno. `app/auth.py` usa `bcrypt` directamente. No reintroducir passlib.
2. **`Truck.model`** es columna `model` en BD, pero el schema expone `model_name`
   (Pydantic reserva `model_`). El mapeo se hace manual en `routers/trucks.py`.
3. **Orden de rutas en `trucks.py` y `employees.py`**: las rutas estáticas
   (`/schedules/calendar`, `/calendar`, `/payrolls/report`) se declaran ANTES de
   `/{id}` para que no las capture el path param. Mantener ese orden.
4. **`get_db` hace commit automático** al final de cada request; los servicios usan
   `flush()`, no `commit()`.
5. **Stock**: usar siempre `stock_service.apply_movement_delta` para no descuadrar
   `Product.current_stock`.
6. La clasificación de correos cae a un **heurístico por palabras clave** si no hay
   `ANTHROPIC_API_KEY`. Con clave usa `claude-sonnet-4-6`.

---

## 10. Cómo arrancar para probar

```bash
cd warehouse/backend
pip install -r requirements.txt
DATABASE_URL="sqlite+aiosqlite:///./wms.db" uvicorn app.main:app --reload
# UI:   http://localhost:8000/
# Docs: http://localhost:8000/docs
# Login: admin@distrigal.com / admin123
```

---

## 11. Repositorios de referencia consultados

- [infiniteoo/wms](https://github.com/infiniteoo/wms) — Next.js + PostgreSQL + React Native.
- [GreaterWMS/GreaterWMS](https://github.com/GreaterWMS/GreaterWMS) — Python, logística real.
- [OCA/wms](https://github.com/OCA/wms) — Odoo, picking barcode + carriers.
- [OCA/stock-logistics-barcode](https://github.com/OCA/stock-logistics-barcode).
- [fjykTec/ModernWMS](https://github.com/fjykTec/ModernWMS).
- [warehauser/warehauser](https://github.com/warehauser/warehauser) — Django WMS.
