# 🤝 Protocolo de cooperación — Claude Code ↔ Codex

> Objetivo: que **dos agentes trabajen en paralelo sobre el mismo repo sin pisarse**,
> sacando lo mejor de cada uno. Este documento es de obligada lectura antes de tocar código.

Carpeta compartida: **`coordination/`**
- `PROTOCOLO.md` (este archivo) — las reglas.
- `TABLERO.md` — quién hace qué, ahora (sistema de *claim*).
- `BITACORA.md` — diario de decisiones; **una sección por agente** (sin conflictos).

Fuente de verdad del estado del producto: **`ESTADO_PROYECTO.md`** (raíz).
Reglas de proyecto y límites: **`AGENTS.md`** (raíz).

---

## 1. Reparto de áreas (por defecto, para no chocar)

El conflicto de la tarea C1 ocurrió porque ambos editamos los **mismos archivos** a la
vez (`app.js`, `base.html`). Para evitarlo, hay un dueño por defecto de cada área:

| Área | Dueño por defecto | Archivos |
|------|-------------------|----------|
| **Backend** (modelos, servicios, routers, auth, seguridad, migraciones, tests) | **Claude** | `warehouse/backend/**` |
| **Frontend** (plantillas, JS, CSS, PWA, UX) | **Codex** | `warehouse/frontend/**` |
| **Infra / CI / Docker** | El que abra la tarea (claim) | `docker-compose.yml`, `Dockerfile`, `.github/**` |
| **Docs de coordinación** | Ambos, con reglas (ver §4) | `coordination/**`, `ESTADO_PROYECTO.md`, `AGENTS.md` |

> "Por defecto" no es una cárcel: si necesitas tocar el área del otro, **haz claim en el
> tablero** y avísalo en tu bitácora. Lo prohibido es editar a ciegas un archivo que el
> otro tiene en curso.

**Archivos frontera (los tocan los dos): `warehouse/backend/app/main.py`** define rutas
SSR que sirven plantillas del frontend. Cambios aquí **siempre con claim**.

---

## 2. Ciclo de trabajo obligatorio

Antes de empezar **cualquier** tarea:

```bash
git fetch origin claude/warehouse-management-system-vmW4R
git pull --rebase origin claude/warehouse-management-system-vmW4R
```

1. **Lee** `coordination/TABLERO.md` y `ESTADO_PROYECTO.md`.
2. **Haz claim**: en `TABLERO.md`, pon tu nombre, la fecha, el estado `EN CURSO` y la
   lista de archivos que vas a tocar. Commit solo de ese cambio del tablero y push.
3. **Comprueba solapes**: si tus archivos coinciden con un claim `EN CURSO` del otro
   agente, **no empieces**: elige otra tarea o espera.
4. **Trabaja** en commits pequeños y atómicos, solo sobre tus archivos reclamados.
5. Antes de push: `git pull --rebase` otra vez. Resuelve conflictos si los hay.
6. **Cierra**: marca la tarea `HECHO` en `TABLERO.md`, marca `[x]` en `ESTADO_PROYECTO.md`
   si aplica, y escribe una entrada en tu sección de `BITACORA.md`.
7. `git push -u origin claude/warehouse-management-system-vmW4R`.

---

## 3. Reglas anti-conflicto (duras)

1. **Una sola tarea `EN CURSO` por agente** a la vez. Termina o libera antes de coger otra.
2. **No edites un archivo con claim activo del otro agente.** Nunca.
3. **Commits pequeños y frecuentes** > un commit gigante. Reduce el área de conflicto.
4. **`git pull --rebase` antes de push, siempre.** Nada de `merge` que ensucie el historial.
5. **No reformatees/reordenes** archivos que no estás cambiando funcionalmente (los
   diffs cosméticos provocan conflictos enormes).
6. Si encuentras un conflicto de rebase: **resuélvelo conservando el trabajo de ambos**,
   no descartes el del otro. Si dudas, anótalo en la bitácora y deja el bloque marcado.
7. **Rama única**: `claude/warehouse-management-system-vmW4R`. No crear ramas nuevas.

---

## 4. Edición de los archivos compartidos sin conflictos

- **`BITACORA.md`**: cada agente escribe **solo en su propia sección** (`## Claude` /
  `## Codex`), **añadiendo al final** de su sección. Así nunca chocan las bitácoras.
- **`TABLERO.md`**: cada quien edita **solo las filas de sus tareas**. No reordenes la tabla.
- **`ESTADO_PROYECTO.md`**: cambios mínimos y localizados (marcar `[x]`, una línea de nota).
  No reescribir secciones enteras sin avisar en la bitácora.

---

## 5. Sacar lo mejor de cada uno

- **Reparto por capa** (backend/frontend) aprovecha el paralelismo real: mientras uno
  construye el endpoint, el otro construye la pantalla que lo consume.
- **Contrato primero**: cuando una tarea cruza capas (ej. portal cliente), el dueño del
  backend publica primero el **contrato de API** (rutas + esquemas Pydantic + ejemplo de
  respuesta) en la bitácora; el frontend programa contra ese contrato sin esperar a la
  implementación completa.
- **Revisión cruzada ligera**: al cerrar una tarea grande, deja en la bitácora 2-3 líneas
  de "qué revisar" para que el otro agente lo valide cuando pase por ahí.
- **No dupliques trabajo**: si vas a explorar/auditar algo amplio, anótalo como `EN CURSO`
  en el tablero antes, para que el otro no haga lo mismo.

---

## 6. Definición de "HECHO"

Una tarea está HECHA cuando:
- [ ] El código funciona (arranca / pasa la verificación descrita en la tarea).
- [ ] No deja conflictos ni marcadores `<<<<<<<` en el repo.
- [ ] `ESTADO_PROYECTO.md` y `TABLERO.md` actualizados.
- [ ] Entrada en `BITACORA.md`.
- [ ] Commit + push hechos en la rama correcta.
