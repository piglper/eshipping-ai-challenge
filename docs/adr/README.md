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
