# AGENTS.md — Instrucciones para agentes (Codex / Claude)

> Archivo conjunto de coordinación. **Lee `ESTADO_PROYECTO.md` antes de empezar.**

## Contexto
Proyecto activo: **WMS Almacén (Distrigal SL)** en el directorio `warehouse/`.
Rama de trabajo: **`claude/warehouse-management-system-vmW4R`**.
(El directorio raíz también contiene un proyecto previo `marvel_metadata` no relacionado.)

## Reglas
1. **Toda la verdad del estado está en `ESTADO_PROYECTO.md`.** Léelo y actualízalo al terminar.
2. Desarrolla y commitea en la rama `claude/warehouse-management-system-vmW4R`.
3. No reintroduzcas `passlib` (usar `bcrypt` directo — ver gotcha #1 del estado).
4. Mantén el orden de rutas estáticas antes de `/{id}` en los routers.

## 👉 DÓNDE CONTINUAR (Codex empieza aquí)
La hoja de ruta completa está en `ESTADO_PROYECTO.md` §8. Resumen del siguiente paso:

- **TAREA C1 (ALTA):** Implementar **login en el frontend** — `login.html`, guardar
  JWT en `localStorage`, inyectar `Authorization: Bearer` en `static/js/app.js`,
  redirigir a `/login` ante 401. Esto desbloquea el uso real de toda la app.
- Luego **C2** (cablear páginas SSR ↔ API), **C3** (migraciones Alembic).

## Arranque rápido
```bash
cd warehouse/backend
pip install -r requirements.txt
DATABASE_URL="sqlite+aiosqlite:///./wms.db" uvicorn app.main:app --reload
# UI http://localhost:8000/ · Docs /docs · Login admin@distrigal.com / admin123
```

## Verificación
- `GET /health` → `{"status":"ok"}`
- `GET /docs` → 54 endpoints
- Flujo probado: login → producto → ubicación → entrada stock → orden → picking
  (barcode) → conformidad → stock descontado. (ver §7 del estado)
