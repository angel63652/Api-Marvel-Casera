# AGENTS.md — Instrucciones para agentes (Codex / Claude)

## ⚠️ LEER ANTES DE HACER CUALQUIER COSA

Este repositorio contiene **UN único proyecto**: **WMS Almacén (Distrigal SL)**, todo en `warehouse/`.

> El antiguo proyecto Marvel (`src/marvel_metadata/`) fue **ELIMINADO**. No lo recrees.

**Trabaja solo en `warehouse/`** (+ archivos raíz de coordinación: `AGENTS.md`,
`ESTADO_PROYECTO.md`, `AUDITORIA.md`, `PROPUESTA_PORTAL_CLIENTE.md`, `coordination/`).
**NO crees ramas nuevas.** La rama de trabajo es `claude/warehouse-management-system-vmW4R`.

---

## 🤝 COOPERACIÓN ENTRE AGENTES (Claude ↔ Codex) — LEER

Trabajamos **dos agentes en paralelo** sobre la misma rama. Para no pisarnos:

1. **Lee y sigue `coordination/PROTOCOLO.md`** antes de tocar código. Es el flujo obligatorio.
2. **Haz *claim* en `coordination/TABLERO.md`** antes de empezar una tarea (tu nombre, fecha,
   `EN CURSO`, archivos). Una sola tarea `EN CURSO` por agente.
3. **No edites un archivo que el otro tiene en curso.** Reparto por defecto:
   **backend → Claude**, **frontend → Codex**. `warehouse/backend/app/main.py` es frontera (claim).
4. **`git pull --rebase` antes de empezar y antes de push.** Commits pequeños.
5. **Apunta decisiones/avisos en `coordination/BITACORA.md`** (solo en tu sección, al final).
6. Auditoría y plan del portal cliente: `AUDITORIA.md` y `PROPUESTA_PORTAL_CLIENTE.md` (raíz).

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

## 3. Qué hacer ahora → mira el TABLERO

C1, C2 y C3 ya están **HECHAS**. Las siguientes tareas, con dueño y estado, están en
**`coordination/TABLERO.md`**. Coge una tarea `LIBRE`, haz *claim* y sigue el `PROTOCOLO.md`.

**Prioridad actual:** Sprint 0 de endurecimiento (H1-H7) — son prerrequisito del portal
cliente. Detalle técnico y ubicaciones en `AUDITORIA.md`.

Reparto por defecto: **backend → Claude**, **frontend → Codex**. Si tu tarea cruza capas,
publica el contrato de API en `coordination/BITACORA.md` antes de implementar.
