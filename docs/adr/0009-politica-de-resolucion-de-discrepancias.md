# ADR-0009: Política de resolución de discrepancias: autoridad por campo, estado del dato, frescura y escalado a una persona

- **Estado:** Aceptado
- **Fecha:** 2026-11-23
- **Decisores:** Pablo Iglesias Peral
- **Referencias:** decisión D6, issue #20, [arquitectura §6.2](../04_arquitectura.md#62-worker-de-asociación-y-reconciliación), [taxonomía y ambigüedades](../03_taxonomia_y_ambiguedades.md) (A-03, A-05, A-06, A-12, A-13, A-15, A-16, A-25, A-28), [análisis de datos §6](../01_analisis_datos.md#6-gold-standard-f13), [ADR-0006](0006-modelo-de-eventos-basado-en-dcsa.md), [ADR-0008](0008-estrategia-de-ia-cascada-por-etapa.md)

## Contexto y problema

Para cada campo de un expediente hay que responder a dos preguntas:

1. **¿Cuál es el valor vigente según los correos?** Un mismo dato aparece varias veces, con valores distintos, en mensajes de remitentes distintos y con estados distintos (planificado, estimado o real). En la muestra, la salida del buque cambia varias veces por expediente; los hilos incluyen opciones de buques que no se reservan (A-25), preguntas sin respuesta (A-13) y reenvíos internos de avisos antiguos (A-16).
2. **Si difiere del ERP, ¿quién tiene razón y qué se hace?** El ERP y los correos son fotos de momentos distintos: en 8 de las 89 comparaciones del gold standard el ERP tiene un dato real posterior al último correo (A-28). El ERP no guarda cuándo se actualizó cada campo ni, salvo dos indicadores, si una fecha es estimada o real (A-03).

La respuesta tiene que ser **determinista y explicable** (RF-51, RNF-43; el LLM no participa, [ADR-0008](0008-estrategia-de-ia-cascada-por-etapa.md)), priorizar la precisión (S-06) y no escribir nunca en el ERP sin validación (RF-55).

## Factores de decisión

- Que un dato menos fiable o más antiguo no sustituya a uno mejor.
- Que no se generen alertas falsas cuando el ERP simplemente está más actualizado que los correos.
- Que cada veredicto se pueda explicar con la regla aplicada y las fuentes usadas.
- Que la política se pueda ajustar sin cambiar código (operaciones conoce mejor que nadie qué fuente manda en cada caso, P-11).
- Que la carga de revisión humana se concentre en lo que tiene impacto operativo.

## Opciones consideradas

1. **El ERP manda**: el ERP es la verdad y los correos solo generan avisos cuando difieren.
2. **El último dato manda**: el valor vigente es siempre el del mensaje más reciente, sea quien sea el remitente.
3. **Autoridad por campo, estado del dato y frescura, con reglas de dominio y escalado a una persona.**
4. **Fusión probabilística**: se combina el valor de todas las fuentes ponderando una fiabilidad aprendida por remitente.

## Decisión

Opción elegida: **«Autoridad por campo, estado del dato y frescura, con reglas de dominio y escalado a una persona»**. Toda la política es configuración versionada (`config/reconciliation.yaml`) y cada veredicto guarda la versión con la que se calculó.

### 1. Rol de la fuente

Cada mensaje tiene un **rol de fuente**, que se obtiene del dominio del remitente con un directorio de remitentes mantenido como configuración y validado por operaciones:

| Rol | Ejemplos |
|---|---|
| `carrier_api` | Eventos de la API de la naviera (DCSA), en el futuro |
| `carrier` | Naviera o su agente |
| `customs_doc` | Documento oficial de aduanas (PDF) |
| `customs_agent` | Agente de aduanas |
| `haulier` | Transportista de acarreo |
| `internal` | Personal de EShipping |
| `customer` | Cliente, cargador o destinatario |
| `inspector` | Agencia de inspección |
| `human_review` | Corrección validada por un operativo en el sistema |

En un reenvío, el rol es el del **autor original** del mensaje citado, no el de quien reenvía (A-16). Un remitente desconocido recibe el rol `customer` (el menos fiable) hasta que operaciones lo clasifique.

### 2. Autoridad por campo

Para cada campo, las fuentes se agrupan en tres rangos: **A** (autoridad: quien produce el hecho), **B** (fiable: quien lo transmite de primera mano) y **C** (informativa: de segunda mano).

| Campo o evento | A (autoridad) | B (fiable) | C (informativa) |
|---|---|---|---|
| Buque, viaje, salida y llegada del buque, transbordo (`DEPA`, `ARRI`, `VCHG`, `ROLL`) | `carrier_api`, `carrier` | `internal` | `customer`, `haulier`, `customs_agent` |
| Cut-offs (`DCO`, `VCO`, `FCO`) | `carrier_api`, `carrier` | `internal`, `haulier` | `customer` |
| Booking y reserva (`CONF`, `AMND`) | `carrier` | `internal` | `customer` |
| Carga en almacén: fecha, hora y lugar (`STUF`) | `haulier` | `internal` | `customer` |
| Recogida del vacío y entrada en terminal (`GTOT`, `GTIN`) | `haulier`, `carrier_api` | `internal` | `customer` |
| Contenedores y precintos | `carrier`, `haulier`, `customs_doc` | `internal` | `customer` |
| Número y tipo de contenedores | `carrier` | `internal`, `haulier` | `customer` |
| Levante, DUA y circuito (`CUS-REL`, `CUS-REQ`) | `customs_doc` | `customs_agent`, `internal` | `customer` |
| B/L (`DRFT`, `ISSU`, `RELS`) | `carrier` | `internal` | `customer` |
| Inspección (`INSP`) | `inspector`, `customs_doc` | `internal`, `customs_agent` | `customer` |

`human_review` está por encima de todos los rangos (§3, regla 6).

### 3. Valor vigente de un campo según los correos

Para cada evento (tipo + lugar, ADR-0006) y cada campo del expediente, el proyector aplica estas reglas en orden:

1. **Candidatos válidos.** Se descartan las opciones ofertadas que no se han reservado (A-25), los datos marcados como ininterpretables (A-26) y los valores de mensajes no asociados con seguridad al expediente.
2. **El estado manda sobre la frescura.** Un valor `ACT` (real) prevalece sobre cualquier `EST` o `PLN`, aunque sea más antiguo: una previsión posterior no deshace un hecho. Dos `ACT` distintos de rango A o B son un **conflicto**.
3. **Dentro del mismo estado, frescura entre fuentes fiables.** El valor vigente es el de mayor `known_at` entre las fuentes de rango **A o B** (A-12). Los valores anteriores se conservan en el historial del evento.
4. **Una fuente informativa no sustituye.** Si un valor de rango C es más reciente que el vigente y es distinto, no lo sustituye: se registra como **pendiente de confirmación** y, si el campo es crítico (§6), genera una tarea de revisión. Ejemplo sintético: la naviera confirma la salida el 15/09; después, el cliente escribe «nos dicen que sale el 18/09». Vigente: 15/09; el 18/09 queda pendiente de confirmar.
5. **Fuentes del mismo rango que discrepan casi a la vez.** Si dos fuentes de rango A, o una de rango A y otra de rango B, dan valores distintos con menos de 24 horas de diferencia en `known_at` (ventana configurable), se marca **conflicto** y va a revisión (A-15).
6. **Corrección humana.** Un valor validado por un operativo (`human_review`) prevalece sobre todo lo anterior. Si después llega un valor distinto de rango A, no la sustituye de forma automática: se abre una tarea de revisión con el aviso «contradice una validación».
7. **Preguntas abiertas.** Un mensaje que pregunta por un valor sin afirmarlo («¿la salida es el 22?») no genera candidato; si contradice al vigente, se marca conflicto (A-13).

Un campo en **conflicto** no se compara con el ERP hasta que se resuelve; se muestra en la revisión con todos los candidatos, sus fuentes y sus citas.

### 4. Comparación con el ERP

**Normalización previa** de los dos lados (A-21): espacios, mayúsculas, formatos de fecha y número, nombres de buque sin prefijos (`M/V`, `MV`), puertos a UN/LOCODE y tipos de contenedor a ISO 6346.

**Tolerancias por campo:**

| Campo | Coincide si |
|---|---|
| Fechas con precisión de día u hora | Mismo día en la hora local del lugar del evento (el ERP no guarda hora) |
| Fechas con rango (A-05) | La fecha del ERP cae dentro del rango |
| Fechas aproximadas (A-06) | Diferencia de ±2 días como máximo |
| Buque | Nombre normalizado idéntico, o similitud alta (≥ 0,92) con el mismo IMO si se conoce |
| Puertos y lugar de carga | Mismo UN/LOCODE |
| Booking | Valor normalizado idéntico, o alias conocido del expediente (A-20) |
| Número de contenedores y TEU | Igualdad exacta; TEU coherente con los tipos (A-23) |

**Estado del dato en el ERP:** `SalidaOK`/`LlegadaOK = SI` se interpreta como `ACT`, y `NO` como `EST` (supuesto S-08, pendiente de P-07). El resto de fechas del ERP se tratan como `EST`.

**Veredicto** (el mismo vocabulario que el gold standard):

| Situación | Veredicto | Acción |
|---|---|---|
| Los dos tienen valor y coinciden con la tolerancia | `MATCH` | Ninguna |
| El ERP no tiene columna para el dato (contenedores, viaje, cut-offs, transbordos) | `NOT_IN_ERP` | Se guarda en el expediente enriquecido; sin revisión |
| El ERP lo tiene y los correos no | `MAIL_MISSING` | Ninguna (no hay evidencia) |
| Los correos lo tienen (vigente, sin conflicto) y el ERP lo tiene vacío | `ERP_MISSING` | **Propuesta** de completar el ERP |
| Difieren y el ERP es probablemente más reciente (regla A) | `ERP_NEWER` | Ninguna alerta; queda registrado y entra en el muestreo de auditoría |
| Difieren y el error del ERP es claro (regla B) | `ERP_ERROR` | **Propuesta** de corrección, con la cita que la respalda |
| Difieren sin poder atribuirlo | `DISCREPANCY` | Tarea de revisión |

**Regla A, «el ERP es más reciente»** (A-28), en este orden:
1. Si se conoce la fecha de actualización del campo en el ERP (lo ideal, P-07) y es posterior al `known_at` del valor vigente → `ERP_NEWER`.
2. Si no se conoce: el ERP marca el dato como real (`ACT`), el vigente de los correos es `EST` o `PLN`, y la fecha del ERP es posterior al `known_at` del último mensaje del expediente → `ERP_NEWER`. Es decir, el hecho ocurrió después de lo último que dicen los correos y alguien lo apuntó.

**Regla B, «error claro del ERP»:** el valor vigente es de rango A (o `human_review`), su confianza calibrada supera el umbral del campo y se cumple al menos una de estas condiciones:
- el valor del ERP viola una regla de dominio (§5);
- la diferencia es típica de una errata (mismo día con el mes cambiado, dígitos traspuestos) y el valor de los correos es `ACT` o de un documento oficial;
- se conoce la fecha de actualización del ERP y es anterior al `known_at` del valor vigente (el ERP no recogió un cambio posterior).

Si no se cumple ni la regla A ni la B → `DISCREPANCY`.

La lectura del ERP que se usa es la última, con su `read_at`. Si es más antigua que un umbral configurable (por defecto, 24 horas), no se emiten `ERP_ERROR` ni `ERP_MISSING`, solo `DISCREPANCY` con el aviso de lectura antigua.

### 5. Reglas de coherencia interna del ERP (RF-54)

Se evalúan en cada lectura del ERP, aunque no haya correos:

- Salida anterior a la llegada.
- Carga en almacén no posterior a la salida ni anterior al alta del expediente.
- Levante no posterior a la salida.
- TEU coherente con el número y tipo de contenedores; volumen y peso dentro de la capacidad del equipo.
- Columnas duplicadas iguales (`Salida` = `Fecha Dep.`).

Cada regla incumplida genera un aviso de calidad del dato, sin necesidad de correos, y sirve como condición de la regla B.

### 6. Prioridad y escalado

| Prioridad | Cuándo | Qué se hace |
|---|---|---|
| **P1 · urgente** | `ERP_ERROR`, `DISCREPANCY` o conflicto en un campo crítico (buque, salida, cut-offs, carga en almacén) con el evento a menos de 72 horas, o un `ROLL`/`VCHG` nuevo | Aviso inmediato (Teams o correo) y primera posición en la cola de revisión (RNF-03) |
| **P2 · hoy** | `ERP_ERROR`, `DISCREPANCY` o conflicto en un campo crítico con el evento más lejos; `ERP_MISSING` en un campo crítico | Cola de revisión, ordenada por la fecha del evento |
| **P3 · normal** | `ERP_MISSING` en campos no críticos (levante, B/L, equipo); valores pendientes de confirmación en campos no críticos | Cola de revisión agrupada por expediente; se pueden validar en bloque |
| Sin revisión | `MATCH`, `NOT_IN_ERP`, `MAIL_MISSING`, `ERP_NEWER` | Registro y muestreo de auditoría (F2.6) |

La criticidad de cada campo, la ventana de 72 horas y los umbrales son configuración.

### 7. Qué se propone y qué se decide

- El sistema **nunca** escribe en el ERP. Las propuestas (`ERP_MISSING`, `ERP_ERROR`) se presentan con el valor actual, el propuesto, la cita, la fuente y la regla aplicada; el operativo las acepta, las corrige o las rechaza.
- Aceptar o corregir genera un evento `human_review`; rechazar con un motivo alimenta el aprendizaje (por ejemplo, «el cliente tiene razón en este caso» puede revelar un rol de fuente mal asignado).
- Cada veredicto guarda la regla aplicada, los candidatos considerados, la lectura del ERP usada y la versión de la configuración (RNF-43).

### Ejemplo de configuración (sintético)

```yaml
version: 2026.11.23-1
conflict_window_hours: 24
erp_stale_after_hours: 24
urgent_horizon_hours: 72
fields:
  vessel_departure:
    event: DEPA@POL
    critical: true
    authority:
      A: [carrier_api, carrier]
      B: [internal]
      C: [customer, haulier, customs_agent]
    tolerance: {date: same_local_day, approx_days: 2}
    erp_column: Salida
    erp_actual_flag: SalidaOK
  stuffing:
    event: STUF
    critical: true
    authority:
      A: [haulier]
      B: [internal]
      C: [customer]
    tolerance: {date: same_local_day, location: same_unlocode}
    erp_column: F. Carga
```

## Consecuencias

- **Positivas:**
  - Las alertas falsas por un ERP más actualizado se evitan con una regla explícita, en lugar de saturar la cola de revisión (en el gold standard serían 8 de 89 comparaciones).
  - Cada veredicto se explica en una línea: «la naviera (rango A) confirmó el 15/09 en el mensaje X; el ERP dice 15/08 con `SalidaOK = NO`; regla B: errata de mes».
  - Operaciones puede cambiar la autoridad de una fuente o la criticidad de un campo sin desplegar código.
  - Los conflictos y las fuentes de segunda mano no contaminan el valor vigente.
- **Negativas y riesgos asumidos:**
  - La regla A sin fecha de actualización del ERP es una heurística: puede dejar pasar como `ERP_NEWER` un error del ERP que, por casualidad, tenga una fecha real posterior. Se mitiga con el muestreo de auditoría de los `ERP_NEWER` y se resuelve si DEIWORLD expone la fecha de actualización por campo (P-07).
  - La autoridad por campo se basa en la práctica habitual del sector, no en la de EShipping; hay que validarla con operaciones (P-11).
  - El directorio de remitentes hay que mantenerlo; un remitente mal clasificado degrada sus datos a rango C (el fallo es prudente, no peligroso).
- **Seguimiento:**
  - En F4 (#40) se reproducen los veredictos del gold standard y se mide la precisión y el recall de cada uno; las diferencias se analizan regla por regla.
  - Las respuestas a P-07, P-08 y P-11 pueden cambiar la tabla de autoridad, la regla A o la interpretación de `SalidaOK`; en ese caso se crea un ADR que sustituya a este.
  - En producción, la tasa de propuestas rechazadas por regla y por rol de fuente indica qué ajustar.

## Análisis de las opciones

### El ERP manda
- ✅ Simple; no hay que decidir entre fuentes de correo.
- ❌ Contradice el objetivo: el ERP tiene errores (4 claros en la muestra) y le faltan datos que solo están en los correos.
- ❌ Cada diferencia se convierte en un aviso, también las que se deben a un ERP desactualizado o a un correo de segunda mano.

### El último dato manda
- ✅ Simple y casi siempre acertado cuando todas las fuentes son fiables.
- ❌ Un cliente que repite una fecha antigua, una pregunta o una opción no reservada sustituyen a la confirmación de la naviera.
- ❌ Una previsión posterior deshace un hecho real.

### Autoridad por campo, estado del dato y frescura
- ✅ Recoge cómo razona un operativo: quién sabe de verdad cada cosa, si es un hecho o una previsión y cuándo se dijo.
- ✅ Determinista, explicable y configurable.
- ❌ Más reglas y una configuración que mantener y validar con operaciones.

### Fusión probabilística con fiabilidad aprendida
- ✅ Aprovecha el historial real de aciertos de cada remitente.
- ❌ Sin histórico, no hay de dónde aprender la fiabilidad.
- ❌ Más difícil de explicar a un operativo y de auditar.
- ➡️ Se usa como **evolución**: la tasa de acierto histórica por remitente (F2.8, #24) se usará para **proponer** cambios de rango, que se aplican como configuración revisada, no de forma automática.
