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

---

## Codex

<!-- Codex: escribe aquí tus entradas, añadiendo al final de esta sección. -->
