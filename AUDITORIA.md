# Auditoría técnica — WMS Almacén (Distrigal SL)

**Fecha:** 2026-06-02
**Rama:** `claude/warehouse-management-system-vmW4R`
**Alcance:** `warehouse/` (backend FastAPI, frontend PWA, infraestructura) + raíz del repo
**Método:** revisión estática de código, modelos, routers, servicios, auth, infra y docs.

---

## 0. Resumen ejecutivo

El WMS está **funcional al ~80%** para el flujo operativo interno (stock, ubicaciones,
picking, órdenes, camiones, empleados, correos con IA). La arquitectura es moderna y
correcta: FastAPI + SQLAlchemy 2 async + PostgreSQL + Alembic, frontend PWA con
Tailwind/Alpine y service worker offline para picking.

**Veredicto:** apto para **piloto interno controlado**. **NO apto para exposición pública**
(ni para el portal cliente que se quiere construir) hasta cerrar los bloqueantes de
seguridad y concurrencia listados abajo.

### Estado por módulo

| Módulo | Completitud | ¿Bloqueante para producción? |
|--------|:-----------:|:----------------------------:|
| Backend API (54 endpoints) | 90% | No |
| Modelos + migraciones Alembic | 95% | No |
| Frontend PWA (13 plantillas) | 80% | No |
| Autenticación / autorización | 70% | **Sí** (ver §2) |
| Concurrencia de stock | 50% | **Sí** (ver §3) |
| Seguridad / secretos / CORS | 45% | **Sí** (ver §2) |
| Tests automatizados | 0% | **Sí** |
| CI/CD | roto | **Sí** (ver §6) |

---

## 1. Qué está bien (no tocar)

- **Arquitectura async correcta**: `create_async_engine` con `pool_pre_ping`, `get_db`
  con commit/rollback automático, servicios que usan `flush()`. Patrón consistente.
- **Modelo de datos sólido**: 16 tablas, relaciones bien definidas, enums de estado
  (OrderStatus, MovementType, etc.), stock derivable del ledger de movimientos.
- **Alembic configurado y operativo**: `alembic.ini`, `env.py` async y migración inicial
  `6b003a86a122_initial_warehouse_schema.py`. (Nota: un informe previo dijo que no había
  migraciones — **es incorrecto**, sí existen.)
- **Picking PWA bien resuelto**: escáner USB HID + táctil, cola offline, feedback de audio,
  ordenación de ruta por pasillo→rack→posición. Es la pieza más madura del frontend.
- **Auth base correcta**: JWT HS256, expiración 24 h, `bcrypt` directo (bien — evita el
  conflicto con passlib), `require_role()` con bypass de ADMIN.
- **Login frontend completo** (Tarea C1): inyección de `Authorization: Bearer`, redirección
  en 401, helpers `requireAuth/logout/getCurrentUser`, render de usuario por data-attributes.

> **Corrección a auditoría previa:** el modelo de IA `claude-sonnet-4-6` usado en
> `email_service.py` **es válido y vigente**. No debe cambiarse.

---

## 2. Bloqueantes de SEGURIDAD (resolver antes de cualquier exposición)

| # | Severidad | Hallazgo | Ubicación | Acción |
|---|:---------:|----------|-----------|--------|
| S1 | **CRÍTICO** | `SECRET_KEY` con default inseguro y conocido | `config.py:15`, `docker-compose.yml`, `.env.example` | Requerir sin default; abortar arranque si no está en prod. Rotar. |
| S2 | **CRÍTICO** | `DATABASE_URL` con credenciales `postgres:password` por defecto | `config.py:10`, `docker-compose.yml:8` | Sin default; pasar por secreto. |
| S3 | **CRÍTICO** | `DEBUG=True` por defecto → `echo=True` del engine (SQL + datos en logs) | `config.py:8`, `database.py` | `DEBUG=False` por defecto. |
| S4 | **CRÍTICO** | CORS `allow_origins=["*"]` con `allow_credentials=True` | `main.py:76-82` | Whitelist explícita de orígenes. |
| S5 | **CRÍTICO** | Endpoints de lectura SIN autenticación: `dashboard/stats`, `products`, `orders`, `movements`, `emails/messages`, `emails/clients` | varios routers | Añadir `Depends(get_current_employee)` / `require_role`. |
| S6 | **ALTO** | Admin bootstrap con credenciales fijas `admin@distrigal.com / admin123` | `main.py:_create_default_admin` | Tomar de env; forzar cambio en primer login. |
| S7 | **ALTO** | Sin rate limiting en `/employees/login` → fuerza bruta | `routers/employees.py` | `slowapi` o middleware de rate limit. |
| S8 | **ALTO** | JWT en `localStorage` sin revocación; empleado desactivado conserva token 24 h | `auth.py`, `app.js` | Lista de revocación / tokens cortos + refresh. |
| S9 | **MEDIO** | Sin CSRF token en formularios POST/PUT | frontend | SameSite + token CSRF si se usan cookies. |
| S10 | **MEDIO** | `.env.example` y `docker-compose.yml` con secretos versionados | repo | Plantillas vacías; `docker-compose.override` local. |

---

## 3. Bloqueantes de CONCURRENCIA / INTEGRIDAD (críticos para pedidos en tiempo real)

Estos son **especialmente relevantes para el portal cliente**: si varios clientes y el
almacén tocan el mismo stock a la vez, hoy habría sobreventa.

| # | Severidad | Hallazgo | Ubicación | Acción |
|---|:---------:|----------|-----------|--------|
| C1 | **CRÍTICO** | `apply_movement_delta` hace *read-modify-write* sin bloqueo → race condition / sobreventa | `stock_service.py:50-59` | `UPDATE products SET current_stock = current_stock + :d WHERE id=:id` atómico, o `SELECT ... FOR UPDATE`. |
| C2 | **CRÍTICO** | `generate_order_number()` usa `random.randint` → colisiones posibles | `picking_service.py:111-115` | Secuencia de BD o tabla de contadores transaccional. |
| C3 | **ALTO** | Dinero y stock en `Float` (salarios, precios, costes, cantidades) | modelos varios | `Numeric(12,2)` para dinero, `Numeric(12,3)` para cantidades. |
| C4 | **ALTO** | `TruckSchedule.orders_assigned` es JSON sin validación ni FK | `truck.py` | Tabla puente con FK, o validación Pydantic estricta. |
| C5 | **MEDIO** | Sin nivel de aislamiento explícito; reservas de stock no modeladas | `database.py` | Introducir concepto de **reserva** (stock comprometido vs disponible). |
| C6 | **MEDIO** | Falta `updated_at` en `Location`, `OrderLine`, `MovementLine`, `ReplenishmentLine` | modelos | Añadir timestamps para auditoría. |

> **Nota de diseño:** el portal cliente necesita distinguir **stock físico**,
> **stock reservado** y **stock disponible** (`disponible = físico − reservado`). Hoy solo
> existe `current_stock`. Esto es un cambio de modelo, no solo de validación.

---

## 4. Calidad / mantenibilidad

| Severidad | Hallazgo | Acción |
|:---------:|----------|--------|
| ALTO | **0% de tests**. No hay `tests/`, `pytest`, ni fixtures | Suite con `pytest` + `httpx.AsyncClient`; objetivo ≥60%. Empezar por stock y auth. |
| MEDIO | Sin paginación en listados (`products`, `orders`, `movements`) | `limit`/`offset` o keyset; riesgo de DoS y lentitud. |
| MEDIO | `except Exception` que silencia errores (email service) | Capturar específico; loggear. |
| MEDIO | `__pycache__/*.pyc` versionados en git | Añadir a `.gitignore` y `git rm -r --cached`. |
| BAJO | Sin `downgrade()` en migración inicial | Implementar para rollback. |
| BAJO | Sin logging estructurado / observabilidad | Añadir logging + (opcional) Sentry. |

---

## 5. Frontend / PWA

- **Todas las páginas llaman a la API real** (no son mockups). Grado de completitud:
  picking 95%, órdenes 90%, dashboard/movimientos 85%, productos/ubicaciones 75-80%,
  camiones/empleados/correos/calendario 60-75% (faltan export Excel, OAuth Gmail, drag-drop).
- **Service worker** correcto (network-first API, cache-first estáticos) pero:
  - Los CDN (Tailwind, Alpine) **no se cachean** → sin CSS en offline real. (MEDIO)
  - Caché sin versionado (`wms-cache-v1` fijo) → riesgo de assets mezclados en updates. (MEDIO)
- **Cola offline de picking en `localStorage`**, no IndexedDB → límite ~5-10 MB y sin cifrar. (ALTO para órdenes grandes)
- **PWA instalable** (manifest + iconos 192/512 + meta tags iOS). Bien.

---

## 6. Infraestructura / CI/CD

| Severidad | Hallazgo | Acción |
|:---------:|----------|--------|
| **CRÍTICO** | `.github/fly-deploy.yml` despliega a Fly.io en cada push a `main`, pero `fly.toml` fue borrado con el proyecto Marvel → **CI roto y deploy huérfano** | Eliminar o reescribir el workflow para el WMS. |
| ALTO | CI sin tests, sin lint, sin escaneo de seguridad | Añadir `pytest`, `ruff`, `bandit` antes de deploy. |
| ALTO | `docker-compose.yml` sin límites de memoria, sin reverse proxy/TLS | Añadir Nginx/Traefik + límites. |
| MEDIO | Falta Redis (cache/locks) y broker para tareas async | Necesario para el portal cliente (ver propuesta). |
| MEDIO | `create_all()` en startup además de Alembic | En prod usar solo `alembic upgrade head`. |

---

## 7. Roadmap interno (estado real)

| Tarea | Estado |
|-------|--------|
| C1 — Login frontend JWT | ✅ Hecho |
| C2 — Páginas SSR conectadas a API | ✅ Hecho |
| C3 — Migraciones Alembic | ✅ Hecho |
| C4 — OAuth Gmail real | 🔴 Pendiente |
| C5 — Envío real de notificaciones a oficina | 🔴 Pendiente |
| C6 — Export Excel (camiones, nóminas) | 🔴 Pendiente |
| C7 — Aprobación por contraseña en ajustes de stock | 🔴 Pendiente |
| C8 — WebSockets de alertas en tiempo real | 🔴 Pendiente |
| C9 — Tests automatizados | 🔴 Pendiente |
| C10 — Generación de etiquetas barcode | 🔴 Pendiente |
| C11 — Iconos PWA reales | ✅ (existen 192/512) |
| C12 — Paginación | 🔴 Pendiente |

---

## 8. Plan de remediación priorizado

**Sprint 0 — Endurecimiento (1 semana) — OBLIGATORIO antes del portal cliente**
1. S1-S4: secretos fuera del código + CORS whitelist + `DEBUG=False`.
2. S5-S6: autenticar todos los GET sensibles; admin bootstrap por env.
3. C1-C2: stock atómico + nº de orden por secuencia.
4. Limpiar `.github/fly-deploy.yml` (roto) y `__pycache__` del repo.

**Sprint 1 — Robustez (1-2 semanas)**
5. C3 (Float→Numeric) con migración Alembic.
6. S7-S8: rate limiting + revocación/refresh de tokens.
7. C9: tests de stock, auth y picking (≥60%).
8. C5 (reservas de stock) — prerrequisito del portal.

**Sprint 2 — Pulido**
9. Paginación, IndexedDB en cola offline, caché versionado, export Excel, OAuth Gmail.

---

Ver **`PROPUESTA_PORTAL_CLIENTE.md`** para el diseño del nuevo portal de clientes
(pedidos desde tienda, stock en tiempo real, autogestión de datos fiscales) y la
valoración honesta de Kafka / Pulsar / Polars.
