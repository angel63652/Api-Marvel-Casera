# AGENTS.md — Instrucciones para agentes (Codex / Claude)

## ⚠️ LEER ANTES DE HACER CUALQUIER COSA

Este repositorio contiene **DOS proyectos independientes**:

| Directorio | Proyecto | Estado |
|-----------|---------|--------|
| `src/marvel_metadata/` | API de metadatos de cómics Marvel | **CONGELADO — no tocar** |
| `warehouse/` | **WMS Almacén (Distrigal SL)** | **ACTIVO — trabaja aquí** |

**NO trabajes en `src/marvel_metadata/` ni en ningún otro directorio.**
**NO crees ramas nuevas.** La rama de trabajo es `claude/warehouse-management-system-vmW4R`.

---

## 1. Proyecto activo: WMS Almacén (Distrigal SL)

Todo está en `warehouse/`. Lee `ESTADO_PROYECTO.md` para el contexto completo.

**Rama:** `claude/warehouse-management-system-vmW4R`
**URL local:** `http://localhost:8000`
**Docs API:** `http://localhost:8000/docs` (54 endpoints)
**Login por defecto:** `admin@distrigal.com` / `admin123`

### Arranque
```bash
cd warehouse/backend
pip install -r requirements.txt
DATABASE_URL="sqlite+aiosqlite:///./wms.db" uvicorn app.main:app --reload
```

### Verificación rápida
```bash
curl http://localhost:8000/health
# → {"status":"ok","app":"WMS Almacén","version":"1.0.0"}
```

---

## 2. Reglas obligatorias

1. **Solo toca archivos dentro de `warehouse/`** y los archivos raíz `AGENTS.md` / `ESTADO_PROYECTO.md`.
2. **Commitea en `claude/warehouse-management-system-vmW4R`** — nunca en main, nunca en ramas nuevas.
3. **No uses `passlib`** — usa `bcrypt` directamente (`import bcrypt`). Ver `warehouse/backend/app/auth.py`.
4. Mantén el orden de rutas en los routers: rutas estáticas (`/calendar`, `/schedules/history`) **antes** de `/{id}`.
5. **Actualiza `ESTADO_PROYECTO.md`** al terminar: marca `[x]` en las tareas completadas.

---

## 3. Tarea actual → TAREA C1 (ALTA PRIORIDAD)

**Implementar login en el frontend.**

El backend de autenticación ya funciona (`POST /api/v1/employees/login` devuelve JWT).
El problema: las páginas HTML no envían el token, por lo que todas las llamadas
que requieren rol devuelven 401.

### Archivos a crear / modificar:

**A) `warehouse/frontend/templates/login.html`** (crear)
- Página de login: formulario email + password, diseño igual que `base.html` (Tailwind + Alpine.js)
- Al submit: `POST /api/v1/employees/login` con JSON `{email, password}`
- Si OK: guardar `token` en `localStorage.setItem('wms_token', token)` y `wms_user` (JSON del empleado)
- Si error: mostrar mensaje de error
- No usa `base.html` (no hay sidebar en login)

**B) `warehouse/backend/app/main.py`** (modificar)
- Añadir ruta `GET /login` → sirve `login.html`
- La ruta raíz `/` debe redirigir a `/login` si no hay token (esto se gestiona en el JS del cliente)

**C) `warehouse/frontend/static/js/app.js`** (modificar)
- En la función `api(method, path, body)`: añadir header `Authorization: Bearer <token>` leyendo `localStorage.getItem('wms_token')`
- Si cualquier respuesta es 401: limpiar localStorage y redirigir a `/login`
- Añadir función `logout()`: borra `wms_token` y `wms_user` de localStorage, redirige a `/login`
- Añadir función `getCurrentUser()`: lee y parsea `wms_user` de localStorage
- Añadir función `requireAuth()`: si no hay token en localStorage, redirigir a `/login`

**D) `warehouse/frontend/templates/base.html`** (modificar)
- Llamar a `requireAuth()` al inicio del `<script>` del body
- En el header: mostrar nombre del usuario logueado (`getCurrentUser().full_name`)
- Añadir botón "Cerrar sesión" que llame a `logout()`

### Verificación de la tarea C1:
```bash
# 1. Visitar http://localhost:8000/ → debe redirigir a /login
# 2. Login con admin@distrigal.com / admin123 → redirige a /
# 3. Dashboard carga datos reales (no 401)
# 4. Botón logout → vuelve a /login
# 5. Sin token: intentar /products directamente → redirige a /login
```

---

## 4. Tareas siguientes (después de C1)

Ver `ESTADO_PROYECTO.md` §8 para la lista completa. Orden:

- **C2** — Cablear páginas SSR con endpoints reales (verificar fetch en products, orders, picking, trucks, employees, emails)
- **C3** — Migraciones Alembic
- **C4** — OAuth Gmail real
- **C7** — Aprobación con contraseña para cambios de stock sensibles
