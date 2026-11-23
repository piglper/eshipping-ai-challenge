# Registro de decisiones (ADR)

Cada decisión relevante, técnica o de proyecto, se documenta como un *Architecture Decision Record* con el formato [MADR](https://adr.github.io/madr/). Ver el [ADR-0001](0001-registrar-decisiones-con-adr.md).

## Normas

- Un fichero por decisión: `NNNN-titulo-en-kebab-case.md`, numerado de forma correlativa.
- Se crea a partir de la [plantilla](template.md) en el mismo PR que introduce el cambio.
- Estados: `Propuesto` → `Aceptado` | `Rechazado`. Más tarde puede pasar a `Obsoleto` o `Sustituido por ADR-XXXX`.
- **Un ADR aceptado no se reescribe.** Si la decisión cambia, se crea un ADR nuevo que lo sustituye y se actualiza el estado del antiguo.
- Cada ADR enlaza con la issue o el PR que lo originó.

## Índice

| ADR | Título | Estado | Fecha |
|---|---|---|---|
| [0001](0001-registrar-decisiones-con-adr.md) | Registrar las decisiones con ADR | Aceptado | 2026-11-21 |
| [0002](0002-proteccion-datos-confidenciales.md) | Protección de los datos confidenciales | Aceptado | 2026-11-21 |
| [0003](0003-flujo-de-trabajo-git.md) | Flujo de trabajo en Git y GitHub | Aceptado | 2026-11-21 |
| [0004](0004-formato-entrega-e-interfaz-poc.md) | Formato de entrega e interfaz de la PoC | Aceptado | 2026-11-21 |
| [0005](0005-llm-local-ollama-en-la-poc.md) | LLM local (Ollama) en la PoC y comparativa de proveedores de pago | Aceptado | 2026-11-21 |
| [0006](0006-modelo-de-eventos-basado-en-dcsa.md) | Modelo de eventos basado en el estándar DCSA | Aceptado | 2026-11-22 |
| [0007](0007-monolito-modular-con-workers-por-etapa.md) | Monolito modular desplegado como workers por etapa detrás de colas | Aceptado | 2026-11-23 |
| [0008](0008-estrategia-de-ia-cascada-por-etapa.md) | Estrategia de IA: cascada de técnicas por etapa, con el LLM acotado al texto libre | Aceptado | 2026-11-23 |
| [0009](0009-politica-de-resolucion-de-discrepancias.md) | Política de resolución de discrepancias: autoridad por campo, estado del dato, frescura y escalado | Aceptado | 2026-11-23 |
| [0010](0010-proveedor-de-llm-de-produccion.md) | Proveedor de LLM de producción: lista corta con residencia en la UE y elección por evaluación | Aceptado | 2026-11-23 |
| [0011](0011-almacenamiento-postgresql-y-almacen-de-objetos.md) | Almacenamiento de producción: PostgreSQL y almacén de objetos compatible con S3 | Aceptado | 2026-11-23 |
| [0012](0012-despliegue-en-contenedores-portables.md) | Despliegue en contenedores portables sobre un servicio gestionado de la UE, sin Kubernetes | Aceptado | 2026-11-23 |
