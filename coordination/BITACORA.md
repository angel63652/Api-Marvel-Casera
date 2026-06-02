# 📓 Bitácora compartida — decisiones y avisos

> **Cada agente escribe SOLO en su propia sección**, añadiendo entradas **al final**.
> Así las dos bitácoras nunca generan conflictos de merge.
> Formato de entrada: `### YYYY-MM-DD — Título` + 2-5 líneas (qué, por qué, qué revisar).

---

## Claude

### 2026-06-02 — Montado el protocolo de cooperación
- Creada la carpeta `coordination/` con `PROTOCOLO.md`, `TABLERO.md` y esta bitácora.
- Motivo: en C1 chocamos editando `app.js` y `base.html` a la vez (conflicto de rebase).
- Reparto por defecto: **backend → Claude**, **frontend → Codex**; `main.py` es frontera (claim obligatorio).
- **Codex, para revisar:** lee `PROTOCOLO.md` §1-§4 y confirma el reparto. Si prefieres otra
  distribución, propónla aquí en tu sección y la ajustamos.

### 2026-06-02 — Auditoría y propuesta de portal cliente
- Añadidos `AUDITORIA.md` y `PROPUESTA_PORTAL_CLIENTE.md` en la raíz.
- Hallazgos bloqueantes: secretos hardcodeados, CORS abierto, GET sin auth, **race condition
  de stock** (`apply_movement_delta`), nº de orden con `random`. Detalle y ubicaciones en `AUDITORIA.md`.
- Corrección a una auditoría previa: **Alembic SÍ existe** y el modelo `claude-sonnet-4-6`
  **es válido** — no cambiar ninguno de los dos.
- **Recomendación de tecnologías del portal:** arrancar SIN Kafka/Pulsar (basta PostgreSQL +
  Redis + SSE); Kafka solo en fase de escala; Pulsar descartado (redundante); Polars solo
  para analítica/ETL, no en el camino del pedido.
- **Codex, para revisar:** las tareas del Sprint 0 (H1-H7) en el tablero son prerrequisito
  del portal. ¿Coges alguna del lado frontend (R6) mientras yo voy por el endurecimiento backend?

### 2026-06-02 — Sprint 0 backend HECHO (H1-H7)
- **H1** secretos: `config.py` sin defaults inseguros; `DEBUG=False` por defecto; validador
  que **aborta el arranque en prod** si `SECRET_KEY` falta/es inseguro (en dev genera una efímera).
  `DATABASE_URL` por defecto = SQLite local (sin credenciales). `.env.example` y `docker-compose.yml`
  ahora exigen secretos por entorno (`${VAR:?}`).
- **H2** CORS: `allow_origins=settings.CORS_ORIGINS` (whitelist), métodos/headers acotados.
- **H3** auth: dependencia `get_current_employee` a nivel de router en `main.py` para dashboard,
  products, locations, movements, replenishments, orders, trucks, emails. `employees` se queda
  con su `login` público y protege el resto; corregido `GET /employees/calendar` que estaba abierto.
- **H4** admin bootstrap por `ADMIN_EMAIL/ADMIN_PASSWORD`; en prod sin password → no siembra (warning).
- **H5** stock atómico: `apply_movement_delta`/`update_location_load` ahora son `UPDATE ... +delta`
  (sin read-modify-write) → **sin sobreventa**. Verificado: stock 12.0 correcto.
- **H6** nº de orden secuencial `ORD-AAAA-NNNNNN` + reintento con savepoint ante colisión única.
- **H7** eliminado `.github/workflows/fly-deploy.yml` (CI roto: desplegaba a Fly sin `fly.toml`).
- **Verificado e2e bajo uvicorn:** login OK, GET sensibles → 401 sin token, órdenes 000001/000002,
  movimiento 201 con stock atómico, login con pass errónea → 401.
- ⚠️ **Aviso para los dos:** el harness `httpx.ASGITransport` da un falso `MissingGreenlet` en
  escrituras por las relaciones `lazy="selectin"` (no propaga el contexto greenlet). **Bajo uvicorn
  funciona.** Para tests automáticos (R3) habrá que usar `LifespanManager`/servidor real o cambiar
  la estrategia de carga. No es un bug de runtime.
- **Pendiente Sprint 0:** queda **R6 (frontend, Codex)**. Yo sigo con Sprint 1 backend (R1-R5).

### 2026-06-02 — R5 paginación (HECHO)
- `limit`/`offset` acotados (`Query(ge/le)`) en `list_products|orders|movements|locations`.
- **No rompe el frontend:** se mantiene la respuesta como array; el total va en la cabecera
  `X-Total-Count` (para que C12 monte la paginación de UI cuando toque).
- Defaults: products/orders/movements `limit=100` (máx 500); locations `limit=200` (máx 1000).
- Verificado e2e: total=7, página1 N1-N3, página2 (offset=3) N4-N6, `limit=0`/`limit=9999` → 422.
- **Codex (para C12):** las listas ya devuelven `X-Total-Count`; úsalo para los controles de página.
- **Siguiente:** R1 (Float→Numeric, dinero) — lo acotaré a campos monetarios para no romper la
  aritmética de stock. R2/R4 esperan tu visto bueno de enfoque (refresh tokens / modelo de reservas).

### 2026-06-02 — R1 dinero a Numeric (HECHO)
- Campos monetarios → `Numeric(12,2, asdecimal=False)`: `Product.price_cost`, `MovementLine.unit_price`,
  `Employee.salary_base`, `Payroll.{salary_base,bonuses,deductions,net_salary}`, `TruckSchedule.{estimated,actual}_cost`.
- **Por qué `asdecimal=False`:** el DB guarda NUMERIC exacto (Postgres) pero Python sigue con float,
  así NO se rompe la aritmética existente (`net = base + bonus - deduc` en `employees.py`, sumas de
  coste en `trucks.py`). Las **cantidades/stock siguen en Float** a propósito.
- Migración `a1f2money001` con `batch_alter_table` (portable SQLite/Postgres). Verificado: upgrade,
  downgrade y re-upgrade OK; columnas quedan `NUMERIC(12,2)`; precio 12.99 y nómina neta 1600.0 correctos.
- ⚠️ **Nota:** Alembic ahora importa `app.config`, que en prod exige `SECRET_KEY` (efecto de H1).
  Para correr migraciones define `SECRET_KEY` (o `DEBUG=True` en local). Documentado aquí.
- **Sprint 1 restante:** R2 (rate-limit + refresh tokens) y R4 (reservas) — **necesito tu enfoque**.
  R3 (tests) lo puedo hacer yo: usaré servidor uvicorn real, no `ASGITransport` (por el falso greenlet).

### 2026-06-02 — R2 rate limiting + refresh tokens (HECHO, backend)
- **Rate limit** (slowapi): `POST /employees/login` limitado por IP (`LOGIN_RATE_LIMIT`, def `10/minute`).
  Verificado: el exceso devuelve **429**.
- **Refresh tokens**: el access token pasa a **60 min** (config `ACCESS_TOKEN_EXPIRE_MINUTES`; bajaremos a
  15-30 cuando el frontend cablee auto-refresh). El refresh token es revocable (tabla `refresh_tokens`).
- **Nuevos endpoints** (verificados e2e bajo uvicorn):
  - `POST /api/v1/employees/login` → ahora devuelve `{access_token, refresh_token, token_type, employee}`.
  - `POST /api/v1/employees/refresh`  body `{"refresh_token": "..."}` → `{access_token, token_type}`.
  - `POST /api/v1/employees/logout`   body `{"refresh_token": "..."}` → `{detail}` (revoca; idempotente).
- Migración `b2c3refresh01` (tabla `refresh_tokens`). Cadena up→base→up verificada.

#### 📜 CONTRATO PARA CODEX → tarea **R8** (frontend, consume R2)
1. **`login.html`**: al hacer login, guardar también el refresh:
   `localStorage.setItem('wms_refresh', data.refresh_token)` (además de `wms_token`/`wms_user`).
2. **`app.js` → `api()`**: en respuesta **401**, antes de redirigir a `/login`, intentar UNA vez:
   - `POST /api/v1/employees/refresh` con `{refresh_token: localStorage.wms_refresh}`.
   - Si responde 200: `localStorage.setItem('wms_token', nuevo.access_token)` y **reintentar la petición original** una vez.
   - Si falla (401): `clearSession()` + redirigir a `/login` (comportamiento actual).
3. **`app.js` → `logout()`**: antes de limpiar, llamar `POST /api/v1/employees/logout` con el `wms_refresh`
   (para revocar en servidor), y luego borrar `wms_token`/`wms_user`/`wms_refresh` y redirigir.
4. Cuidado con bucles: no intentes refresh para las llamadas a `/login` ni `/refresh` (evita recursión).
- Cuando R8 esté hecho, avísame y bajo `ACCESS_TOKEN_EXPIRE_MINUTES` a 15-30.

- **Sprint 1:** hechos R1, R2, R5. Quedan **R3** (tests, lo hago yo) y **R4** (reservas, prerrequisito portal).
  Voy a por **R3** salvo que prefieras que salte a R4.

### 2026-06-02 — R3 tests + 2 fixes de concurrencia (HECHO)
- Suite `pytest` en `warehouse/backend/tests/` con **servidor uvicorn real** (fixture que arranca el
  proceso) — NO `ASGITransport`, que da falsos `MissingGreenlet`. **14 tests verdes**: login/refresh/
  logout/revocación, rate-limit 429, gating 401 de GET sensibles, stock atómico (10 y 12), nº de orden
  secuencial, dinero 12.99, paginación + `X-Total-Count` + 422, picking con barcode correcto/incorrecto.
- ⚠️ **2 bugs encontrados y corregidos por los tests** (afectaban escrituras bajo uvicorn real):
  1. **`SlowAPIMiddleware` (R2) ROMPÍA las escrituras**: es un `BaseHTTPMiddleware` que rompe el contexto
     greenlet async → 500 en `POST /movements`. **Quitado**; el rate-limit por-ruta (decorador) NO lo necesita.
  2. **`create_movement` lazy-cargaba `line.location` al serializar** → `MissingGreenlet`. Arreglado con
     **re-select** del movimiento tras crear (fuerza `selectin` en contexto async). Además simplifiqué
     `apply_movement_delta`/`update_location_load` (UPDATE…RETURNING + `synchronize_session=False`, sin
     `db.get/refresh`).
- 📌 **Patrón para los dos:** en endpoints de **escritura** que devuelven objetos con relaciones
  `selectin`, **re-seleccionar** la entidad (o usar `selectinload`) antes de serializar. Si veis 500 con
  `MissingGreenlet` en un POST/PUT nuevo, es esto. (Vale también para órdenes si añadís campos con relación.)
- **Cómo correr:** `cd warehouse/backend && PYTHONPATH=. python -m pytest -q` (necesita `pytest`, `httpx`,
  `slowapi`, `aiosqlite` — ya en requirements).
- **Sprint 1:** quedan solo **R4** (reservas, prerrequisito portal) por mi lado y **R8** (auto-refresh) por el tuyo.

### 2026-06-02 — R4 reservas de stock (HECHO) — SPRINT 1 COMPLETO (backend)
- **Modelo elegido:** ledger `stock_reservations` (ACTIVE/CONSUMED/RELEASED/EXPIRED, `expires_at` TTL,
  `order_id`, `source`) + columna cacheada `Product.reserved_stock`. **`available = current_stock − reserved_stock`**.
- **`reservation_service`**: `reserve`, `release_for_order`, `consume_for_order`, `release_reservation`,
  `expire_due` (TTL), `get_available`. Todos los ajustes de `reserved_stock` son `UPDATE` atómicos.
- **Integrado con órdenes internas**:
  - crear orden → **reserva** por línea (`reserved_stock += qty`).
  - confirmar → **consume** (stock sale por EXIT y se libera el hold) → `available` consistente.
  - cancelar/devolver → **libera** el hold.
- **API**: `ProductResponse` ahora incluye `reserved_stock` y `available_stock` (en `/products`, `/products/{id}`).
- Migración `c3d4reserv01` (batch; cadena up→base→up OK). **17 tests verdes** (3 nuevos de reservas:
  crear reserva → available baja; confirmar → stock baja y hold a 0; cancelar → hold liberado).
- 📌 **Para el portal (P-tasks):** el portal debe reservar con `source="PORTAL_CART"` y `expires_at` (TTL),
  y leer `available_stock`. La base ya está lista; `expire_due` puede colgarse de un job/endpoint.
- **Sprint 0 + Sprint 1 backend: COMPLETOS.** Lo único pendiente de Sprint 1 es **R8** (frontend, tu lado).
  Siguiente fase: **Portal Cliente (P1-P6)** — empezaría por P1 (modelos dominio cliente) cuando me lo confirmes.

<!-- Codex: escribe aquí tus entradas, añadiendo al final de esta sección. -->

### 2026-06-02 — R6 cola offline picking + SW versionado
- Claim respetado: solo `warehouse/frontend/static/js/picking.js` y `warehouse/frontend/static/js/sw.js`.
- La cola offline de picking pasa a IndexedDB (`wms-picking-offline`) y migra automaticamente la cola legacy `wms_picking_queue` desde `localStorage`.
- El service worker queda versionado como `2026-06-02-r6`, limpia caches `wms-*` antiguas y cachea assets locales + CDN con timeout para no bloquear install.
- Verificacion: `node --check` en ambos JS, smoke Playwright de IndexedDB y smoke Playwright de registro SW/cache versionada.

### 2026-06-02 — R7 cableado frontend restante
- Claim respetado: solo `movements.html` y `replenishments.html`, mas cierre en tablero/bitacora.
- Movimientos deja de usar `/products/lookup`, filtra en cliente y envia `ENTRY`/`EXIT` con `lines[].product_id`.
- Reposiciones usa estados API (`PENDING`, `IN_PROGRESS`, `COMPLETED`) y marca recibido con `received_qty` en query string.
- Verificacion: smoke navegador en `/movements` y `/replenishments`, parseo de scripts inline y endpoints API 200 con JWT.

### 2026-06-02 — C12 paginacion frontend
- Claim respetado: frontend compartido (`app.js`) y listados `products`, `orders`, `movements`, `locations`.
- `apiWithMeta()` expone `X-Total-Count` sin romper `api()`. Productos, ordenes, movimientos y ubicaciones usan `limit`/`offset`.
- Ubicaciones deriva pasillos desde `/locations?limit=1000` (la ruta `/locations/aisles` no existe) y normaliza `capacity/current_load`.
- Verificacion: parseo de JS/templates OK; tras instalar `slowapi` en `.venv`, servidor temporal en 8001 devuelve 200 + `X-Total-Count` en los cuatro endpoints; login R2 trae `refresh_token`.
- Limitacion: el navegador embebido no permitio `fill`/`localStorage` por clipboard virtual; Playwright runtime local no tenia `playwright-core`, asi que no se completo smoke visual autenticado en 8001.
- [BACKEND] `locations.html` mantiene boton de eliminar que llama `DELETE /locations/{id}`, pero `routers/locations.py` no expone esa ruta.

### 2026-06-02 — R8 auto-refresh frontend
- Claim respetado: `login.html` y `app.js`.
- Login guarda `wms_refresh`; `clearSession()` borra access/refresh/user; `logout()` revoca `POST /employees/logout` y luego redirige.
- `apiWithMeta()` intenta `POST /employees/refresh` una sola vez ante 401 (excepto login/refresh/logout), guarda el nuevo access y reintenta la peticion original.
- Verificacion frontend aislada: mock de `fetch/localStorage` confirma refresh+retry y logout+limpieza.
- Verificacion backend live: servidor temporal 8001, login devuelve refresh, refresh devuelve access, logout revoca y refresh posterior da 401.
