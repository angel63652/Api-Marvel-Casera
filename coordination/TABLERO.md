# 📋 Tablero de tareas — Claude ↔ Codex

> Sistema de *claim*. Antes de trabajar: pon tu nombre, fecha y `EN CURSO` en tu fila.
> **Una sola tarea `EN CURSO` por agente.** No edites filas que no son tuyas.
> Estados: `LIBRE` · `EN CURSO` · `BLOQUEADA` · `HECHO`.

Lee `PROTOCOLO.md` antes de tocar nada. Rama: `claude/warehouse-management-system-vmW4R`.

---

## 🔴 Sprint 0 — Endurecimiento (OBLIGATORIO antes del portal cliente)

Ver detalle en `AUDITORIA.md` §2-§3 y §8.

| ID | Tarea | Área | Dueño | Estado | Archivos / notas |
|----|-------|------|-------|--------|------------------|
| H1 | Sacar secretos del código (SECRET_KEY/DATABASE_URL sin default; `DEBUG=False`) | backend/infra | **Claude** | ✅ HECHO (2026-06-02) | `config.py`, `docker-compose.yml`, `.env.example` |
| H2 | CORS whitelist (quitar `allow_origins=["*"]` + credentials) | backend | **Claude** | ✅ HECHO (2026-06-02) | `main.py` (usa `settings.CORS_ORIGINS`) |
| H3 | Autenticar GET sensibles (dashboard, products, orders, movements, emails) | backend | **Claude** | ✅ HECHO (2026-06-02) | dep a nivel de router en `main.py` + `GET /calendar` |
| H4 | Admin bootstrap por env (`ADMIN_EMAIL/ADMIN_PASSWORD`) | backend | **Claude** | ✅ HECHO (2026-06-02) | `main.py`; en prod sin pass → no siembra |
| H5 | Stock atómico (eliminar race en `apply_movement_delta`) | backend | **Claude** | ✅ HECHO (2026-06-02) | `stock_service.py` (UPDATE atómico + clamp CASE) |
| H6 | Nº de orden por secuencia (quitar `random.randint`) | backend | **Claude** | ✅ HECHO (2026-06-02) | `picking_service.py` + retry savepoint en `orders.py` |
| H7 | Limpiar CI roto (`.github/fly-deploy.yml` huérfano) + `__pycache__` | infra | **Claude** | ✅ HECHO (2026-06-02) | workflow eliminado; pycache ya no trackeado |

## 🟡 Sprint 1 — Robustez

| ID | Tarea | Área | Dueño | Estado | Archivos / notas |
|----|-------|------|-------|--------|------------------|
| R1 | Float → Numeric (dinero) + migración Alembic | backend | **Claude** | ✅ HECHO (2026-06-02) | `Numeric(12,2,asdecimal=False)` en price_cost/unit_price/salary/costes; migración `a1f2money001` (batch, up+down OK) |
| R2 | Rate limiting en login + revocación/refresh de tokens | backend | **Claude** | ✅ HECHO (2026-06-02) | slowapi 429; access 60min + refresh revocable (tabla `refresh_tokens`); `/refresh` + `/logout`; migración `b2c3refresh01`. **Falta cablear frontend (ver R8)** |
| R8 | Cablear auto-refresh de token en frontend (consume R2) | frontend | **Codex** | HECHO (2026-06-02) | `login.html` guarda refresh; `app.js` refresca una vez en 401 y revoca en logout |
| R3 | Tests (`pytest`): auth/tokens, stock atómico, paginación, picking | backend | **Claude** | ✅ HECHO (2026-06-02) | 14 tests verdes (servidor uvicorn real). Fixes: quitar SlowAPIMiddleware y re-select en `create_movement` (greenlet/selectin) |
| R4 | Modelo de **reservas de stock** (`available = físico − reservado`) | backend | **Claude** | ✅ HECHO (2026-06-02) | ledger `stock_reservations` + `Product.reserved_stock`; `reservation_service`; órdenes reservan/consumen/liberan; `available_stock` en API; migración `c3d4reserv01`; 3 tests |
| R5 | Paginación en listados largos | backend | **Claude** | ✅ HECHO (2026-06-02) | `limit`/`offset` acotados + cabecera `X-Total-Count` en products/orders/movements/locations |
| R6 | Cola offline picking a IndexedDB + caché SW versionado | frontend | **Codex** | HECHO (2026-06-02) | IndexedDB + migración desde `localStorage`; SW `2026-06-02-r6` |
| R7 | Corregir cableado frontend restante fuera de C2 | frontend | **Codex** | HECHO (2026-06-02) | Movimientos usa `/products?search`, `ENTRY/EXIT` y payload real; reposiciones usa estados API y `received_qty` |

## 🟢 Roadmap interno pendiente (de ESTADO_PROYECTO.md)

| ID | Tarea | Área | Dueño | Estado | Notas |
|----|-------|------|-------|--------|-------|
| C4 | OAuth Gmail real | backend | — | LIBRE | `email_service.sync_gmail` listo |
| C5 | Envío real de notificaciones a oficina (SMTP/Gmail) | backend | — | LIBRE | `email_service.notify_office` |
| C6 | Export Excel (camiones, nóminas) | full | — | LIBRE | `openpyxl` ya está |
| C7 | Aprobación con contraseña en ajustes de stock | backend | — | LIBRE | `verify_password` existe |
| C10 | Etiquetas de barcode (Pillow) | backend | — | LIBRE | |
| C12 | Paginación frontend (consume R5) | frontend | **Codex** | HECHO (2026-06-02) | productos/ordenes/movimientos/ubicaciones consumen `limit`/`offset` + `X-Total-Count` |

## 🔵 Portal Cliente (ver `PROPUESTA_PORTAL_CLIENTE.md`) — tras Sprint 0/1

| ID | Tarea | Área | Dueño | Estado | Notas |
|----|-------|------|-------|--------|-------|
| P1 | Modelos dominio cliente (customer, customer_user, address, change_request) | backend | **Claude** | EN CURSO (2026-06-02) | `models/customer.py` + migración; aislado del dominio empleado |
| P2 | Auth realm de cliente (JWT `aud=portal`, tenancy) | backend | — | LIBRE | depende P1 |
| P3 | API portal (catálogo, carrito/reserva, pedidos, perfil) | backend | — | LIBRE | publicar contrato primero |
| P4 | Tiempo real stock (Redis pub/sub o LISTEN/NOTIFY → SSE) | backend | — | LIBRE | |
| P5 | PWA portal cliente (separada de la interna) | frontend | — | LIBRE | contra contrato de P3 |
| P6 | Analítica con Polars (informes, ETL tarifas) | backend | — | LIBRE | fuera del camino del pedido |

---

## ✅ Histórico (HECHO)

| ID | Tarea | Dueño | Fecha |
|----|-------|-------|-------|
| C1 | Login frontend JWT | Claude + Codex | 2026-06-02 |
| C2 | Páginas SSR conectadas a API | Codex | 2026-06-02 |
| C3 | Migraciones Alembic | Codex | 2026-06-02 |
| C11 | Iconos PWA 192/512 | — | (existen) |
| — | Auditoría + propuesta portal cliente | Claude | 2026-06-02 |
