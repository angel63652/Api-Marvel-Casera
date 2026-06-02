# Propuesta — Portal de Clientes (pedidos desde tienda)

**Fecha:** 2026-06-02
**Contexto:** ampliar el WMS Distrigal con un portal donde los clientes (tiendas)
hagan pedidos, vean stock en tiempo real y autogestionen sus datos fiscales y
direcciones, sincronizando con la base de datos de la empresa, con seguridad.

> Léase junto con `AUDITORIA.md`. Los bloqueantes §2 (seguridad) y §3 (concurrencia)
> de esa auditoría son **prerrequisitos** de este portal: sin stock atómico ni
> reservas, exponer pedidos a clientes provocaría sobreventa.

---

## 1. Principios de diseño

1. **Aislar el dominio cliente del dominio empleado.** El portal cliente NO debe
   reutilizar los roles internos (ADMIN/MANAGER/PICKER…). Es una superficie pública:
   modelo de identidad, auth y rate limiting propios.
2. **Stock disponible ≠ stock físico.** Se introduce el concepto de **reserva**.
   `disponible = físico − reservado − comprometido en órdenes abiertas`.
3. **Los datos maestros no se mutan directamente desde fuera.** Los cambios de datos
   fiscales/dirección entran como **solicitudes versionadas** que oficina valida (o se
   auto-aprueban según reglas), nunca un `UPDATE` directo del cliente sobre la tabla maestra.
4. **Empezar simple, escalar cuando los números lo pidan.** No introducir Kafka/Pulsar
   el día 1 (ver §6).

---

## 2. Valoración honesta de las tecnologías propuestas

| Tecnología | ¿Para qué sirve? | ¿Encaja ahora? | Recomendación |
|-----------|------------------|:--------------:|---------------|
| **Kafka** | Bus de eventos distribuido de alto throughput, retención y replay | Sobredimensionado para el volumen actual | **Fase 3 (escala).** Adoptarlo cuando haya >cientos de pedidos/seg o varios consumidores (ERP, BI, almacén, facturación). |
| **Pulsar** | Igual que Kafka + multi-tenant y geo-replicación nativa | Redundante con Kafka | **No.** Usar Kafka **o** Pulsar, nunca ambos. Pulsar solo si hubiese multi-almacén geo-distribuido. |
| **Polars** | DataFrames ultrarrápidos (analítica/ETL en memoria) | No gestiona pedidos (no es un broker ni una cola) | **Sí, pero para analítica/ETL:** informes de ventas, importación masiva de catálogo/tarifas, reconciliación. No en el camino transaccional del pedido. |

**Conclusión:** para el pedido transaccional en tiempo real, lo que se necesita primero
es **(a)** reservas de stock atómicas en PostgreSQL y **(b)** un canal de *push* a los
navegadores (WebSocket/SSE). El "event streaming" pesado (Kafka) es una optimización
posterior, no un requisito de arranque. Polars vive en el lado de informes, no en el pedido.

---

## 3. Arquitectura propuesta (por fases)

### Fase 1 — MVP sin streaming pesado (recomendada para empezar)
```
Cliente (PWA tienda)
   │  HTTPS + JWT cliente
   ▼
FastAPI  ── /api/portal/*  (routers nuevos, auth de cliente separada)
   │
   ├── PostgreSQL  (stock + reservas atómicas, pedidos, solicitudes de datos)
   ├── Redis        (cache de catálogo, locks, pub/sub para tiempo real, rate limit)
   └── SSE / WebSocket  ── push de stock y estado de pedido a navegadores
```
- **Tiempo real**: cambios de stock publican en `Redis pub/sub` (o `LISTEN/NOTIFY` de
  PostgreSQL); FastAPI los reenvía por **SSE** (más simple que WebSocket para "solo lectura
  de stock") o WebSocket si se quiere bidireccional.
- **Reservas**: al añadir al carrito/confirmar, `INSERT` en `stock_reservation` dentro de
  una transacción que comprueba disponible con `SELECT ... FOR UPDATE`. Expiran por TTL.

### Fase 2 — Desacoplar con cola ligera
- Redis Streams o RabbitMQ para procesar pedidos de forma asíncrona (confirmación,
  facturación, notificación a almacén) sin acoplar el request HTTP.

### Fase 3 — Event streaming (solo si la escala lo exige)
- **Kafka** como columna vertebral de eventos: `order.created`, `stock.changed`,
  `customer.updated`. Consumidores independientes: almacén (genera órdenes de picking),
  facturación, BI. Aquí **Polars** consume los topics para analítica casi en tiempo real.

---

## 4. Cambios en el modelo de datos (Fase 1)

Nuevas tablas (dominio cliente, separadas de las internas):

- **`customer`** — datos maestros del cliente/tienda: razón social, NIF/CIF, estado, tarifa.
- **`customer_user`** — credenciales de acceso al portal (email, hash, customer_id, rol del lado cliente: OWNER/STAFF). Auth independiente del empleado.
- **`customer_address`** — direcciones de envío/facturación (varias por cliente).
- **`customer_data_change_request`** — solicitudes de cambio de datos fiscales/dirección,
  versionadas, con estado `PENDING/APPROVED/REJECTED` y revisor (oficina). **Nunca** UPDATE directo.
- **`stock_reservation`** — `product_id, customer_order_id, quantity, expires_at, status`.
  Base del "stock disponible".
- **`customer_order`** + **`customer_order_line`** — pedido del cliente (distinto de la
  `Order` interna de picking; al confirmarse genera una `Order` interna).

Cambios en modelos existentes:
- `Product`: añadir propiedad calculada/columna `reserved_stock`; exponer `available_stock`.
- Resolver antes los bloqueantes C1-C3 de la auditoría (stock atómico, nº orden por secuencia, Float→Numeric).

---

## 5. Superficie de API del portal (borrador)

```
POST   /api/portal/auth/login            # auth cliente (JWT separado)
POST   /api/portal/auth/register         # alta (con verificación de email)
GET    /api/portal/catalog               # catálogo con stock DISPONIBLE (paginado)
GET    /api/portal/catalog/stream        # SSE: actualizaciones de stock en vivo
POST   /api/portal/cart/reserve          # reserva temporal (TTL)
POST   /api/portal/orders                # confirmar pedido -> crea reservas firmes + Order interna
GET    /api/portal/orders                # historial de pedidos del cliente
GET    /api/portal/orders/{id}           # estado y seguimiento
GET    /api/portal/profile               # datos fiscales y direcciones (solo lectura directa)
POST   /api/portal/profile/change-request# solicitud de cambio fiscal/dirección (a aprobación)
GET    /api/portal/addresses             # direcciones
```
Lado interno (oficina):
```
GET    /api/v1/customer-requests         # cola de solicitudes de cambio
POST   /api/v1/customer-requests/{id}/approve|reject
```

---

## 6. Seguridad del portal (no negociable)

- **Realm separado**: JWT de cliente con `aud=portal`, claves/rotación propias; un token de
  cliente nunca debe validar contra endpoints internos `/api/v1/*` y viceversa.
- **Tenancy estricto**: todo query del portal filtra por `customer_id` del token. Tests que
  prueben que el cliente A no ve datos del cliente B (IDOR).
- **Rate limiting** por IP y por cuenta en login, registro y catálogo.
- **Validación y saneado** de todas las entradas (Pydantic estricto, longitudes, tipos).
- **Datos fiscales = PII** → RGPD: minimización, cifrado en reposo de campos sensibles,
  registro de auditoría de accesos/cambios, derecho de rectificación vía change-request.
- **HTTPS/TLS obligatorio**; cookies `Secure`/`SameSite` si se usan; CSRF si hay cookies.
- **Aprobación de cambios fiscales** antes de impactar datos maestros (evita fraude/errores).
- **Resolver primero** S1-S9 de la auditoría: hoy el backend no está listo para exposición pública.

---

## 7. Plan de entrega sugerido

| Fase | Contenido | Dependencias |
|------|-----------|--------------|
| **0** | Endurecimiento backend (Sprint 0 de la auditoría) | — |
| **1** | Reservas de stock + `available_stock` + tests de concurrencia | Fase 0 |
| **2** | Auth y modelos de cliente + perfil/direcciones + change-requests | Fase 1 |
| **3** | Catálogo + carrito con reserva + creación de pedido → Order interna | Fase 2 |
| **4** | Tiempo real (Redis pub/sub o LISTEN/NOTIFY → SSE) | Fase 3 |
| **5** | PWA portal cliente (separada de la PWA interna) | Fase 3-4 |
| **6** | Analítica con **Polars** (informes, ETL tarifas) | Fase 3 |
| **7** | (Si escala) **Kafka** como bus de eventos; Polars consume topics | métricas reales |

---

## 8. Recomendación final

1. **Sí** al portal cliente: aporta valor claro (autoservicio, menos llamadas/correos).
2. **Primero seguridad y concurrencia** (Sprints 0-1 de la auditoría). Sin esto, el portal
   es un riesgo de sobreventa y fuga de datos.
3. **Arrancar sin Kafka ni Pulsar.** PostgreSQL (reservas) + Redis (cache/pub-sub/locks) +
   SSE cubren el tiempo real del MVP con mucha menos complejidad operativa.
4. **Elegir UNA tecnología de streaming** (Kafka, no Pulsar) y solo cuando las métricas lo
   justifiquen.
5. **Polars** desde la Fase 6 para informes e importaciones masivas, fuera del camino del pedido.
6. **PWA de cliente separada** de la interna: dominios, estilos y auth distintos.
