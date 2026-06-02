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

### 2026-06-02 — P1 modelos del dominio cliente (HECHO) — arranca el PORTAL
- `models/customer.py`, **aislado del dominio empleado**: `Customer` (razón social, `tax_id` único, status),
  `CustomerUser` (login del portal OWNER/STAFF, email único, distinto de `Employee`),
  `CustomerAddress` (SHIPPING/BILLING), `CustomerChangeRequest` (FISCAL/ADDRESS, `payload` JSON,
  PENDING/APPROVED/REJECTED, revisor=empleado) → **los datos fiscales NO se editan directos, van a aprobación**.
- Migración `d4e5customer1` (up/down/up OK). Smoke: crea customer+user+address+change_request. 17 tests sin regresión.
- **Siguiente (yo):** P2 = auth realm de cliente (JWT `aud=portal`, hashing reutiliza `auth.hash_password`,
  tenancy por `customer_id`). Tras P2 haré P3 y **publicaré el contrato de API del portal** para que montes P5 (PWA cliente).
- **Codex:** P5 (PWA cliente) debe ir en páginas/JS separados de la PWA interna (otro realm de auth). Aún no empieces;
  te aviso con el contrato de P3.

### 2026-06-02 — P2 auth realm de cliente (HECHO)
- **Endpoints** (`routers/portal_auth.py`, montado en `/api/portal/auth`):
  - `POST /api/portal/auth/register` → crea `Customer` (PENDING) + `CustomerUser` (OWNER); devuelve token. Rate-limited.
  - `POST /api/portal/auth/login` → token. Rate-limited.
  - `GET  /api/portal/auth/me` → datos del usuario + customer (requiere token de portal).
- **Token de cliente**: JWT con `aud="portal"` + `type="customer"` + `customer_id`. Vida = `ACCESS_TOKEN_EXPIRE_MINUTES`.
- **Aislamiento de realms** (verificado con tests):
  - token de cliente en API interna `/api/v1/*` → **401/403** (`get_current_employee` lo rechaza por `aud`/`type`).
  - token de empleado en `/api/portal/*` → **401** (`get_current_customer_user` exige `aud=portal`).
- **Tenancy**: `get_current_customer_user` exige que `customer_id` del token coincida con el del usuario; bloquea
  customers SUSPENDED. Reutiliza `auth.hash_password/verify_password` (bcrypt, no passlib).
- ⚠️ Añadido `email-validator` a requirements (uso `EmailStr` en `schemas/portal.py`).
- **23 tests verdes** (6 nuevos de portal auth).
- **Siguiente (yo):** P3 = API del portal (catálogo con `available_stock`, carrito/reserva con `source="PORTAL_CART"`
  + TTL, crear pedido → genera `Order` interna, perfil/direcciones, change-requests). **Publicaré el contrato aquí**
  para que arranques P5 (PWA cliente) en paralelo. Aún NO empieces P5.

### 2026-06-02 — P3 API del portal (HECHO) — contrato para P5
- **Pricing por tarifa (opción B del usuario):** `Product.price_base` (precio venta) + tabla
  `product_tier_prices` (precio por `tier`). Resolución: tarifa del cliente → si no, base. Migración `e5f6pricing1`.
  Oficina fija tarifas con `PUT /api/v1/products/{id}/tier-prices?tier=&price=`.
- **Pedido sin sobreventa:** `reservation_service.reserve_if_available` (UPDATE atómico `WHERE available>=qty`).
  El pedido del portal crea una `Order` interna (customer_id=`CUST-{id}`) y reserva con `order_id` → el flujo
  interno de confirmar/cancelar ya consume/libera esas reservas (R4).
- **Gestión de clientes (oficina):** registro queda PENDING; oficina activa con `POST /api/v1/customers/{id}/approve?price_tier=`.
- **28 tests verdes** (5 nuevos: catálogo+precio tarifa, pedido+bloqueo sobreventa, PENDING no pide, tenancy, change-request+aprobación).

#### 📜 CONTRATO PARA CODEX → tarea **P5 (PWA cliente)** — YA PUEDES EMPEZAR
PWA **separada** de la interna (otro realm de auth, `localStorage` keys propias p.ej. `portal_token`).
Todos los endpoints devuelven JSON; el token va en `Authorization: Bearer <token>`.
- **Auth** (sin token):
  - `POST /api/portal/auth/register` body `{company_name, tax_id, email, password, name?, phone?}` → `{access_token, user, customer}` (customer.status=PENDING).
  - `POST /api/portal/auth/login` body `{email, password}` → `{access_token, user, customer}`.
  - `GET /api/portal/auth/me` (con token) → `{access_token, user, customer}`.
- **Catálogo/pedidos (con token de portal):**
  - `GET /api/portal/catalog?search=&limit=&offset=` → `[{id, niu, barcode, name, category, unit, available_stock, price}]` (+ header `X-Total-Count`).
  - `POST /api/portal/orders` body `{items:[{product_id, quantity}], shipping_address_id?, notes?}` → `201` `{id, order_number, status, lines, total}`. Errores: **409** stock insuficiente (mensaje con disponible), **403** si cuenta no ACTIVE.
  - `GET /api/portal/orders` y `GET /api/portal/orders/{id}` → pedidos del propio cliente (404 si no es suyo).
- **Perfil:**
  - `GET /api/portal/profile` → `{customer, contact_email, contact_phone, price_tier, addresses[]}`.
  - `GET /api/portal/addresses` → `[AddressResponse]`.
  - `POST /api/portal/profile/change-request` body `{target:"FISCAL"|"ADDRESS", payload:{...}}` → `201` (queda PENDING hasta que oficina apruebe).
  - `GET /api/portal/profile/change-requests` → historial de solicitudes del cliente.
- **Notas:** mientras la cuenta esté PENDING, el catálogo se puede ver pero **no se puede pedir** (403). El access token
  del portal caduca en `ACCESS_TOKEN_EXPIRE_MINUTES` (60); el portal aún **no tiene refresh** (mejora futura) → en 401, re-login.
- ⚠️ **Realms separados:** un token de portal NO sirve en `/api/v1/*` y un token de empleado NO sirve en `/api/portal/*`.

- **Siguiente (yo):** P4 (tiempo real de stock vía SSE) o P6 (Polars). Pendiente tuyo: P5. Pendiente menor: precio del pedido
  NO se persiste (se recalcula con la tarifa actual) — si quieres “precio congelado” lo añadimos como columna en OrderLine.

### 2026-06-02 — P4 stock en tiempo real (SSE) (HECHO)
- **Broker pub/sub en proceso** (`app/events.py`, asyncio, colas acotadas que descartan lo más viejo).
  ⚠️ Single-process: para multi-worker hay que cambiar a Redis pub/sub (misma interfaz `broker.publish`).
- **SSE para el cliente**: `GET /api/portal/catalog/stream` (requiere token de portal) emite
  `event: stock` con `{product_id, available_stock}` + heartbeats cada 15s.
- **Disparadores** (`reservation_service.notify_available`): se publica al cambiar stock/disponible en
  movimientos (entrada/salida), creación de pedido interno, **pedido del portal**, confirmar, cancelar y devolver.
- ⚠️ Arreglado un `MissingGreenlet`: en cancelar/devolver no se debe iterar `order.lines` (lazy) tras las
  queries de `release_for_order` → ahora se consultan los `product_id` con un `select` explícito.
- **32 tests verdes** (4 nuevos: broker pub/sub, unsubscribe, SSE requiere auth, **SSE e2e**: un movimiento
  empuja el evento al cliente conectado).
- **📜 Para Codex (P5):** suscríbete a `GET /api/portal/catalog/stream` con `EventSource`/fetch-stream usando el
  token de portal; al recibir `event: stock` actualiza el `available_stock` de ese `product_id` en el catálogo.
- **Portal P1-P4 COMPLETO por mi lado.** Queda **P5** (tú) y **P6** (Polars, opcional). Avísame cuando quieras P6
  o bajar el access token / persistir precio de pedido.

### 2026-06-02 — P6 analítica con Polars (HECHO) — ROADMAP COMPLETO
- **`GET /api/v1/analytics/sales-summary?start_date=&end_date=&top=`** (MANAGER/OFFICE): unidades vendidas y
  revenue estimado por producto desde **órdenes COMPLETED** (la confirmación descuenta stock por delta cacheado,
  no escribe Movement, así que la fuente de ventas son las órdenes). Agregación con **Polars**.
- **`POST /api/v1/analytics/import-tier-prices`** (multipart CSV `niu,tier,price`): ETL con Polars que hace
  upsert en `product_tier_prices`; filas con NIU desconocido se omiten. Devuelve `{created, updated, skipped}`.
- Añadidos a requirements: `polars>=1.0.0` y `email-validator>=2.0.0`.
- **35 tests verdes** (3 nuevos: sales-summary agrega completadas, import CSV crea/actualiza/omite, auth required).
- 🎉 **ROADMAP COMPLETO por mi lado:** Sprint 0 (H1-H7), Sprint 1 (R1-R5), Portal (P1-P6). Codex: R6-R9, C12, P5.
- **Pendiente menor (opcional, avísame):** persistir "precio congelado" en líneas de pedido; refresh tokens del
  portal (hoy access 60 min sin refresh); bajar `ACCESS_TOKEN_EXPIRE_MINUTES` interno a 15-30 (R8 ya cablea refresh).

### 2026-06-02 — Bajado el access token interno a 30 min (HECHO)
- `ACCESS_TOKEN_EXPIRE_MINUTES` interno → **30 min** (seguro: R8 auto-refresca en 401).
- **Desacoplado el portal:** nuevo `PORTAL_ACCESS_TOKEN_EXPIRE_MINUTES = 60`; `create_customer_token` lo usa.
  Motivo: el portal aún NO tiene refresh, así que mantenerlo en 60 evita desconectar tiendas a media sesión.
  Cuando hagamos refresh del portal, bajamos también este.
- 35 tests verdes.

### 2026-06-02 — P7 refresh tokens del portal (HECHO)
- Tabla **`customer_refresh_tokens`** (aislada de la de empleados). Migración `f6a7portalrt1` (un solo head, chain OK).
- `register` y `login` del portal ahora devuelven también `refresh_token`. Nuevos endpoints:
  - `POST /api/portal/auth/refresh`  body `{"refresh_token": "..."}` → `{access_token, token_type}`.
  - `POST /api/portal/auth/logout`   body `{"refresh_token": "..."}` → revoca (idempotente).
- Token de refresco del portal: JWT `aud=portal`, `type=customer_refresh`. Cross-realm verificado
  (un refresh de empleado NO sirve en `/api/portal/auth/refresh`).
- **Bajado `PORTAL_ACCESS_TOKEN_EXPIRE_MINUTES` a 30** (ya seguro con refresh). Ambos realms a 30 min ahora.
- **39 tests verdes** (4 nuevos de refresh del portal).

#### 📜 CONTRATO PARA CODEX → tarea **P8** (PWA cliente, consume P7)
En `portal.js` (mismo patrón que R8 pero con keys del portal):
1. Al **login/register**, guardar `portal_refresh = data.refresh_token` (además de `portal_token`).
2. En **401**, intentar UNA vez `POST /api/portal/auth/refresh` con `{refresh_token: portal_refresh}`;
   si 200 → guardar nuevo `portal_token` y reintentar la petición; si falla → limpiar y volver al login del portal.
3. En **logout**, llamar `POST /api/portal/auth/logout` con el refresh y luego limpiar `portal_token`/`portal_refresh`.
4. No intentes refresh en las llamadas a `/api/portal/auth/login` ni `/refresh` (evita bucles).

- **Estado:** roadmap + opcionales casi cerrados. Quedan opcionales menores: precio congelado en líneas de pedido,
  y C4-C7/C10 internos. Avísame.

### 2026-06-02 — C7 ajuste de stock con contraseña (HECHO)
- Nuevo **`POST /api/v1/movements/adjustment`** (rol MANAGER; ADMIN pasa): body `{product_id, location_id?,
  quantity (con signo), reason, password}`. **Re-verifica la contraseña del propio usuario** antes de aplicar.
- El endpoint genérico `POST /movements` ahora **rechaza `type=ADJUSTMENT`** (403) y remite al gated.
- El ajuste crea un `Movement` ADJUSTMENT + línea con cantidad firmada y aplica el delta (atómico) + notify SSE.
- **43 tests verdes** (4 nuevos: ajuste +5/−4 con password OK; password incorrecta→401; ADJUSTMENT genérico→403;
  rol no-MANAGER→403).
- **📌 Codex (frontend, opcional):** en `movements.html`/`dashboard.html`, el ajuste de stock debe pedir la
  contraseña del usuario y llamar a `/movements/adjustment` (no al genérico).
- **Pendiente opcional:** precio congelado en líneas de pedido; C6 (Excel), C10 (etiquetas barcode); C4/C5 (Gmail/SMTP, requieren credenciales).

### 2026-06-02 — C14 precio congelado en líneas de pedido (HECHO)
- Nueva columna `OrderLine.unit_price` (NUMERIC 12,2). Migración `a7b8olprice1` (un head, up/down OK).
- **Se captura el precio al crear la línea:** portal → precio de la **tarifa** del cliente; pedido interno → `price_base`.
- La respuesta del portal usa el **precio guardado** (fallback a precio vivo solo para líneas antiguas sin precio).
- Verificado: total del pedido = 16.0 (2×8 GOLD); tras **subir la tarifa a 99**, el pedido **sigue en 16.0** (congelado).
- **44 tests verdes.**
- **Opcionales restantes:** C6 (Excel), C10 (etiquetas barcode); C4/C5 (Gmail/SMTP — requieren credenciales reales).

### 2026-06-02 — C6 export a Excel (HECHO)
- `services/excel_service.py` (openpyxl): `build_xlsx(sheet, headers, rows)` con cabecera en negrita y anchos auto.
- **`GET /api/v1/trucks/schedules/history/export`** (MANAGER/OFFICE) → xlsx del histórico de viajes completados
  (fecha, matrícula, conductor, tipo, ruta, coste est./real/desviación, estado).
- **`GET /api/v1/employees/payrolls/report/{year}/{month}/export`** (MANAGER) → xlsx de nóminas del periodo.
- `openpyxl` ya estaba en requirements; lo añadí al entorno de test.
- **47 tests verdes** (3 nuevos: ambos export devuelven un .xlsx válido —magic PK + workbook.xml— y exigen auth).
- **📌 Codex (frontend, opcional):** los botones "Exportar Excel" deben apuntar a esos endpoints (con el token).
- **Opcionales restantes:** C10 (etiquetas barcode con Pillow); C4/C5 (Gmail/SMTP, requieren credenciales).

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

### 2026-06-02 — R9 stock reservado/disponible en frontend interno
- Claim respetado: solo `products.html`, `orders.html` y cierre en tablero/bitacora.
- Productos muestra stock fisico, reservado y disponible; el estado visual se calcula contra `available_stock`.
- Ordenes muestra disponibilidad al seleccionar producto, limpia lineas sin coincidencia para evitar `product_id` stale y bloquea cantidades superiores al disponible antes del `POST /orders`.
- Verificacion: `git diff --check`, parseo de scripts inline con Node empaquetado y mock JS de normalizacion/lookup/bloqueo por stock.
- Limitacion: smoke visual autenticado no completado porque la BD SQLite local no tiene la columna nueva de R4.
- [BACKEND] En entorno local `sqlite+aiosqlite:///./wms.db`, `GET /api/v1/products?limit=5&offset=0` devuelve 500: `sqlite3.OperationalError: no such column: products.reserved_stock`. Falta aplicar migracion `c3d4reserv01` o recrear la BD local antes del smoke visual.

### 2026-06-02 — P5 PWA portal cliente
- Claim respetado: frontend separado (`portal.html`, `portal.js`, `portal-manifest.json`, `portal-sw.js`) y `main.py` solo para servir `/portal` + `/portal-sw.js`.
- Portal con realm aislado: claves `portal_token`, `portal_user`, `portal_customer`, `portal_cart`; no reutiliza `wms_token`.
- Pantallas incluidas: login/registro, catalogo con `available_stock` y precio de tarifa, carrito persistido, envio de pedidos, historico de pedidos, perfil, direcciones y solicitudes de cambio.
- Integra P4: fetch-stream a `GET /api/portal/catalog/stream` con bearer token; actualiza `available_stock` en catalogo/carrito y ajusta cantidades si baja el disponible.
- Service worker propio en `/portal-sw.js` con cache de shell/estaticos; no cachea respuestas autenticadas de `/api/portal/*`.
- Verificacion: sintaxis JS OK, manifest JSON OK, smoke HTTP en SQLite limpia (`/portal`, SW, manifest, register, me, catalog, 403 en pedido PENDING), navegador integrado renderiza acceso/registro, `pytest tests/test_portal_orders.py -q` verde y `pytest tests/test_events.py -q` verde.
- Limitacion: la suite completa `pytest -q` supero 120s en local; se paro el uvicorn residual de pruebas antes de cerrar.
- [BACKEND] Ejecutar juntos `pytest tests/test_portal_orders.py tests/test_events.py -q` reproduce timeout en `test_stream_emits_stock_event_on_movement` al crear producto, aunque ambas suites pasan por separado. Parece fixture/servidor de test tras P3+P4, no bloqueo de P5.

### 2026-06-03 — C13 UI analitica y carga de tarifas
- Claim respetado: solo `dashboard.html` y cierre en tablero/bitacora.
- Dashboard interno muestra tarjeta de analitica con filtros `start_date`, `end_date`, `top`, KPIs y tabla de `top_products`.
- Se añade carga CSV de tarifas (`niu,tier,price`) con multipart, bearer JWT, reintento tras refresh 401 y resultado `created/updated/skipped`.
- Verificacion: `git diff --check`, parseo del script inline con Node empaquetado, `pytest tests/test_analytics.py -q --tb=short` verde, smoke HTTP en SQLite limpia (`/`, `GET /analytics/sales-summary`, `POST /analytics/import-tier-prices`) verde.
- Limitacion: el navegador embebido abrio `/login`, pero no completo login por fallo del runtime de interaccion (`fill`/click con clipboard/CDP). La comprobacion autenticada se cubrio con smoke HTTP.
- [BACKEND] En la `wms.db` local existente, `GET /api/v1/analytics/sales-summary` devuelve 500: `sqlite3.OperationalError: no such column: products.price_base`; `POST /api/v1/analytics/import-tier-prices` devuelve 500 por `products.reserved_stock`. La BD local necesita migraciones/recreacion antes de smoke visual autenticado.

### 2026-06-03 — P8 auto-refresh del portal cliente
- Claim respetado: `portal.js`, `portal-sw.js` y cierre en tablero/bitacora.
- Login/registro guardan `portal_refresh`; `/auth/me` conserva el refresh existente cuando no viene en la respuesta.
- `portalApi()` reintenta una vez tras 401 usando `POST /api/portal/auth/refresh`, con una sola peticion de refresh compartida si hay varias llamadas simultaneas.
- Logout llama `POST /api/portal/auth/logout` con el refresh y despues limpia `portal_token`, `portal_refresh`, usuario y cliente.
- Stream SSE de stock intenta refrescar en 401 y reinicia la conexion si obtiene un access nuevo.
- `portal-sw.js` sube a `2026-06-03-p8` para invalidar la cache de `portal.js`.
- Verificacion: `node --check` en `portal.js` y `portal-sw.js`, mock Node de refresh+retry/preservar refresh/logout, `pytest tests/test_portal_refresh.py -q --tb=short` verde.

### 2026-06-03 — C15 UI ajuste de stock con contrasena
- Claim respetado: solo `movements.html` y cierre en tablero/bitacora.
- Movimientos incorpora pestana Ajustes, boton "Ajuste Stock" visible para ADMIN/MANAGER y modal especifico con producto, delta firmado, motivo y contrasena.
- El ajuste llama a `POST /api/v1/movements/adjustment`; entradas/salidas siguen usando `POST /movements`.
- La tabla representa `ADJUSTMENT` como Ajuste, con badge amber y cantidad firmada.
- Verificacion: parseo del script inline con Node empaquetado, mock Node del flujo frontend, `pytest tests/test_adjustment.py -q --tb=short` verde y smoke HTTP live: entrada 10, ajuste -3, stock final 7, password incorrecta 401, filtro `type=ADJUSTMENT` OK.
