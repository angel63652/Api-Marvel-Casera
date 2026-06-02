# ðŸ“‹ Tablero de tareas â€” Claude â†” Codex

> Sistema de *claim*. Antes de trabajar: pon tu nombre, fecha y `EN CURSO` en tu fila.
> **Una sola tarea `EN CURSO` por agente.** No edites filas que no son tuyas.
> Estados: `LIBRE` Â· `EN CURSO` Â· `BLOQUEADA` Â· `HECHO`.

Lee `PROTOCOLO.md` antes de tocar nada. Rama: `claude/warehouse-management-system-vmW4R`.

---

## ðŸ”´ Sprint 0 â€” Endurecimiento (OBLIGATORIO antes del portal cliente)

Ver detalle en `AUDITORIA.md` Â§2-Â§3 y Â§8.

| ID | Tarea | Ãrea | DueÃ±o | Estado | Archivos / notas |
|----|-------|------|-------|--------|------------------|
| H1 | Sacar secretos del cÃ³digo (SECRET_KEY/DATABASE_URL sin default; `DEBUG=False`) | backend/infra | **Claude** | âœ… HECHO (2026-06-02) | `config.py`, `docker-compose.yml`, `.env.example` |
| H2 | CORS whitelist (quitar `allow_origins=["*"]` + credentials) | backend | **Claude** | âœ… HECHO (2026-06-02) | `main.py` (usa `settings.CORS_ORIGINS`) |
| H3 | Autenticar GET sensibles (dashboard, products, orders, movements, emails) | backend | **Claude** | âœ… HECHO (2026-06-02) | dep a nivel de router en `main.py` + `GET /calendar` |
| H4 | Admin bootstrap por env (`ADMIN_EMAIL/ADMIN_PASSWORD`) | backend | **Claude** | âœ… HECHO (2026-06-02) | `main.py`; en prod sin pass â†’ no siembra |
| H5 | Stock atÃ³mico (eliminar race en `apply_movement_delta`) | backend | **Claude** | âœ… HECHO (2026-06-02) | `stock_service.py` (UPDATE atÃ³mico + clamp CASE) |
| H6 | NÂº de orden por secuencia (quitar `random.randint`) | backend | **Claude** | âœ… HECHO (2026-06-02) | `picking_service.py` + retry savepoint en `orders.py` |
| H7 | Limpiar CI roto (`.github/fly-deploy.yml` huÃ©rfano) + `__pycache__` | infra | **Claude** | âœ… HECHO (2026-06-02) | workflow eliminado; pycache ya no trackeado |

## ðŸŸ¡ Sprint 1 â€” Robustez

| ID | Tarea | Ãrea | DueÃ±o | Estado | Archivos / notas |
|----|-------|------|-------|--------|------------------|
| R1 | Float â†’ Numeric (dinero) + migraciÃ³n Alembic | backend | **Claude** | âœ… HECHO (2026-06-02) | `Numeric(12,2,asdecimal=False)` en price_cost/unit_price/salary/costes; migraciÃ³n `a1f2money001` (batch, up+down OK) |
| R2 | Rate limiting en login + revocaciÃ³n/refresh de tokens | backend | **Claude** | âœ… HECHO (2026-06-02) | slowapi 429; access 60min + refresh revocable (tabla `refresh_tokens`); `/refresh` + `/logout`; migraciÃ³n `b2c3refresh01`. **Falta cablear frontend (ver R8)** |
| R8 | Cablear auto-refresh de token en frontend (consume R2) | frontend | **Codex** | HECHO (2026-06-02) | `login.html` guarda refresh; `app.js` refresca una vez en 401 y revoca en logout |
| R3 | Tests (`pytest`): auth/tokens, stock atÃ³mico, paginaciÃ³n, picking | backend | **Claude** | âœ… HECHO (2026-06-02) | 14 tests verdes (servidor uvicorn real). Fixes: quitar SlowAPIMiddleware y re-select en `create_movement` (greenlet/selectin) |
| R4 | Modelo de **reservas de stock** (`available = fÃ­sico âˆ’ reservado`) | backend | **Claude** | âœ… HECHO (2026-06-02) | ledger `stock_reservations` + `Product.reserved_stock`; `reservation_service`; Ã³rdenes reservan/consumen/liberan; `available_stock` en API; migraciÃ³n `c3d4reserv01`; 3 tests |
| R5 | PaginaciÃ³n en listados largos | backend | **Claude** | âœ… HECHO (2026-06-02) | `limit`/`offset` acotados + cabecera `X-Total-Count` en products/orders/movements/locations |
| R6 | Cola offline picking a IndexedDB + cachÃ© SW versionado | frontend | **Codex** | HECHO (2026-06-02) | IndexedDB + migraciÃ³n desde `localStorage`; SW `2026-06-02-r6` |
| R7 | Corregir cableado frontend restante fuera de C2 | frontend | **Codex** | HECHO (2026-06-02) | Movimientos usa `/products?search`, `ENTRY/EXIT` y payload real; reposiciones usa estados API y `received_qty` |
| R9 | Mostrar stock reservado/disponible en frontend interno | frontend | **Codex** | HECHO (2026-06-02) | `products.html` muestra fisico/reservado/disponible; `orders.html` valida cantidad contra `available_stock` |

## ðŸŸ¢ Roadmap interno pendiente (de ESTADO_PROYECTO.md)

| ID | Tarea | Ãrea | DueÃ±o | Estado | Notas |
|----|-------|------|-------|--------|-------|
| C4 | OAuth Gmail real | backend | â€” | LIBRE | `email_service.sync_gmail` listo |
| C5 | EnvÃ­o real de notificaciones a oficina (SMTP/Gmail) | backend | â€” | LIBRE | `email_service.notify_office` |
| C6 | Export Excel (camiones, nÃ³minas) | full | â€” | LIBRE | `openpyxl` ya estÃ¡ |
| C7 | AprobaciÃ³n con contraseÃ±a en ajustes de stock | backend | â€” | LIBRE | `verify_password` existe |
| C10 | Etiquetas de barcode (Pillow) | backend | â€” | LIBRE | |
| C12 | PaginaciÃ³n frontend (consume R5) | frontend | **Codex** | HECHO (2026-06-02) | productos/ordenes/movimientos/ubicaciones consumen `limit`/`offset` + `X-Total-Count` |
| C13 | UI analitica y carga de tarifas (consume P6) | frontend | **Codex** | HECHO (2026-06-03) | `dashboard.html`; consume `/analytics/sales-summary` y `/analytics/import-tier-prices` |

## ðŸ”µ Portal Cliente (ver `PROPUESTA_PORTAL_CLIENTE.md`) â€” tras Sprint 0/1

| ID | Tarea | Ãrea | DueÃ±o | Estado | Notas |
|----|-------|------|-------|--------|-------|
| P1 | Modelos dominio cliente (customer, customer_user, address, change_request) | backend | **Claude** | ✅ HECHO (2026-06-02) | `models/customer.py` (4 modelos + enums) + migración `d4e5customer1`; aislado del dominio empleado; 17 tests sin regresión |
| P2 | Auth realm de cliente (JWT `aud=portal`, tenancy) | backend | **Claude** | ✅ HECHO (2026-06-02) | `/api/portal/auth/{register,login,me}`; token `aud=portal type=customer`; cross-realm rechazado; rate-limit; 6 tests (23 total) |
| P3 | API portal (catálogo, carrito/reserva, pedidos, perfil) | backend | **Claude** | ✅ HECHO (2026-06-02) | pricing por tarifa + catálogo + pedido sin sobreventa (`reserve_if_available`) + perfil/direcciones + change-requests + admin clientes (oficina); migración `e5f6pricing1`; 28 tests. **Contrato P5 en BITACORA** |
| P4 | Tiempo real stock (Redis pub/sub o LISTEN/NOTIFY → SSE) | backend | **Claude** | ✅ HECHO (2026-06-02) | broker in-proc `events.py` + SSE `GET /api/portal/catalog/stream`; notify en movimientos/órdenes/portal; 32 tests (4 nuevos, incl. SSE e2e) |
| P5 | PWA portal cliente (separada de la interna) | frontend | **Codex** | ✅ HECHO (2026-06-02) | `/portal` con auth cliente, catalogo, carrito, pedidos, perfil/change-requests y stock SSE; PWA aislada (`portal_*`) |
| P6 | Analítica con Polars (informes, ETL tarifas) | backend | **Claude** | ✅ HECHO (2026-06-02) | `GET /api/v1/analytics/sales-summary` + `POST /import-tier-prices` (CSV); Polars; 35 tests (3 nuevos) |
| P7 | Refresh tokens del portal cliente | backend | **Claude** | ✅ HECHO (2026-06-02) | tabla `customer_refresh_tokens`; `/api/portal/auth/{refresh,logout}`; portal token a 30 min; migración `f6a7portalrt1`; 39 tests |
| P8 | Auto-refresh del token en la PWA cliente (consume P7) | frontend | — | LIBRE | contrato en BITACORA; `portal.js` (guardar refresh, refrescar en 401, logout server-side) |

---

## âœ… HistÃ³rico (HECHO)

| ID | Tarea | DueÃ±o | Fecha |
|----|-------|-------|-------|
| C1 | Login frontend JWT | Claude + Codex | 2026-06-02 |
| C2 | PÃ¡ginas SSR conectadas a API | Codex | 2026-06-02 |
| C3 | Migraciones Alembic | Codex | 2026-06-02 |
| C11 | Iconos PWA 192/512 | â€” | (existen) |
| â€” | AuditorÃ­a + propuesta portal cliente | Claude | 2026-06-02 |
