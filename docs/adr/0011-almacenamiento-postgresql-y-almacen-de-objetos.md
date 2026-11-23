# ADR-0011: Almacenamiento de producción: PostgreSQL y almacén de objetos compatible con S3

- **Estado:** Aceptado
- **Fecha:** 2026-11-23
- **Decisores:** Pablo Iglesias Peral
- **Referencias:** decisión D7, issue #27, [modelo de datos](../05_modelo_datos.md), [arquitectura §9.5](../04_arquitectura.md#9-análisis-de-capacidad-f21b), [costes §4](../06_costes.md#4-requisitos-de-máquina), [seguridad](../09_seguridad.md), [ADR-0007](0007-monolito-modular-con-workers-por-etapa.md)

## Contexto y problema

El [modelo de datos](../05_modelo_datos.md) tiene tres capas: entrada inmutable (correos, mensajes, adjuntos y lecturas del ERP), observaciones inmutables (solo inserción) y proyecciones recalculables (valor vigente, veredictos), además de tablas operativas (cola de revisión, colas entre etapas, configuración, registro de llamadas al LLM). Hay que decidir dónde se guarda todo en producción.

Volumen con 100.000 correos al mes (arquitectura §9.5): unas 300.000 observaciones al mes, una base de datos que crece entre 10 y 25 GB al año con índices, y entre 0,5 y 1 TB al año de originales y adjuntos. Las consultas son transaccionales (asociar, proyectar por expediente, servir la cola de revisión) y algunas analíticas (indicadores por naviera, campo o remitente).

## Factores de decisión

- **Integridad:** transacciones y claves ajenas para el linaje (RF-60, RNF-43) y bloqueo por expediente en la proyección.
- **Consultas bitemporales** sencillas («estado a fecha X», RF-61).
- **Solo inserción** y reprocesado sin perder la historia (RNF-04, RNF-41).
- **Simplicidad de operación:** pocas piezas, que el equipo de EShipping pueda mantener.
- **Portabilidad:** disponible gestionado en cualquier nube y en local (D8).
- **Escalado** hasta 300.000 correos al mes o más sin rediseño (PLAN §7.2).
- **Datos personales:** cifrado, retención y borrado por partes (RNF-31).

## Opciones consideradas

1. **PostgreSQL + almacén de objetos compatible con S3**: eventos como tabla de solo inserción, proyecciones como tablas, colas con `SKIP LOCKED`, particiones mensuales.
2. **Almacén de eventos dedicado** (por ejemplo, KurrentDB, antes EventStoreDB) + base de datos de lectura para las proyecciones.
3. **Base de datos de documentos** (por ejemplo, MongoDB) para mensajes y expedientes.
4. **Data warehouse o lakehouse** (BigQuery, Snowflake, Parquet sobre almacén de objetos) como almacén principal.

## Decisión

Opción elegida: **«PostgreSQL + almacén de objetos compatible con S3»**.

- **PostgreSQL 17** (o la versión gestionada vigente) para metadatos, observaciones con su cita corta, proyecciones, veredictos, revisión, configuración, colas entre etapas y registro de llamadas al LLM.
  - Las observaciones son una tabla de solo inserción: el patrón de eventos se implementa en el modelo, sin una base de datos especializada.
  - Particiones mensuales de `mail`, `message`, `observation`, `stage_run` y `llm_call`; retención y archivado por partición.
  - Una réplica de lectura para la aplicación de revisión y los indicadores; alta disponibilidad con primario y réplica (o el servicio gestionado equivalente).
  - Columnas `jsonb` para lo que varía por fuente (fila original del ERP, componentes de la configuración).
- **Almacén de objetos compatible con S3** para originales, cuerpos limpios, adjuntos y su texto, con claves derivadas del hash, versionado, cifrado y reglas de ciclo de vida para la retención.
- **Analítica:** al principio, sobre la réplica de lectura y vistas materializadas. Solo si los indicadores lo piden, se exportan las particiones cerradas a Parquet en el mismo almacén de objetos y se consultan con un motor analítico (DuckDB o el de la nube), sin cambiar el almacén operativo.
- **En la PoC:** SQLite con el mismo esquema lógico y una carpeta local como almacén de objetos; SQLAlchemy y Alembic permiten pasar a PostgreSQL cambiando la conexión (F3.7, #35).

**Cuándo revisar esta decisión:**

- más de unos 1.000 millones de observaciones o de 2 TB en la base de datos;
- colas por encima de unas 500 tareas por segundo sostenidas (entonces, cola dedicada; ver [ADR-0012](0012-despliegue-en-contenedores-portables.md));
- necesidad de suscripciones a eventos por terceros (entonces, publicar los eventos además en un bus).

## Consecuencias

- **Positivas:**
  - Una sola base de datos transaccional cubre eventos, proyecciones, colas y revisión: integridad referencial del linaje y transacciones que incluyen la tarea de cola y el dato (sin el problema de la escritura doble).
  - La consulta bitemporal es SQL normal ([modelo de datos §6.2](../05_modelo_datos.md#62-consulta-estado-del-expediente-a-fecha-x-rf-61)).
  - Tecnología conocida, gestionada en todas las nubes y barata (costes §4: dos servidores pequeños).
  - Lo voluminoso y con datos personales queda fuera de la base de datos, en un almacén cifrado con retención por reglas.
- **Negativas y riesgos asumidos:**
  - Las garantías de un almacén de eventos (suscripciones, orden global de eventos) hay que construirlas si un día hacen falta; hoy no las pide ningún requisito.
  - Las colas sobre PostgreSQL añaden carga a la base de datos; a este volumen es despreciable (decenas de tareas por minuto), y el puerto `TaskQueue` permite cambiarlas.
  - Hay que operar particiones y vacío (`VACUUM`) de las tablas de colas; se automatiza con `pg_partman` o el equivalente gestionado.
- **Seguimiento:** medir el tamaño real y la latencia de las consultas de proyección y de la cola en la PoC y en el piloto.

## Análisis de las opciones

### PostgreSQL + almacén de objetos
- ✅ Transacciones, claves ajenas, particiones, `jsonb`, `SKIP LOCKED`; una sola pieza para casi todo.
- ✅ Disponible gestionado en todas las nubes y en local.
- ❌ Escala vertical en escritura; muy por encima del volumen previsto.

### Almacén de eventos dedicado
- ✅ Suscripciones y proyecciones de serie.
- ❌ Una pieza más y menos conocida; las proyecciones siguen necesitando otra base de datos; sin transacción conjunta con las colas y la revisión. Complejidad sin un requisito que la pida.

### Base de datos de documentos
- ✅ Esquema flexible para formatos variables.
- ❌ El linaje y la bitemporalidad son relacionales por naturaleza; las transacciones entre colecciones y la integridad son más débiles. `jsonb` ya da la flexibilidad necesaria.

### Data warehouse o lakehouse como almacén principal
- ✅ Excelente para analítica.
- ❌ No es transaccional ni de baja latencia: no sirve para la cola de revisión, el bloqueo por expediente ni las colas. Se puede añadir después para analítica sin cambiar el almacén operativo.
