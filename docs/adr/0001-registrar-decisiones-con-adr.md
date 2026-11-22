# ADR-0001: Registrar las decisiones con ADR

- **Estado:** Aceptado
- **Fecha:** 2026-11-21
- **Decisores:** Pablo Iglesias Peral
- **Referencias:** [PLAN.md §8](../PLAN.md#8-estándares-de-documentación)

## Contexto y problema

El enunciado valora la «solidez de la justificación técnica» y pide explícitamente las «alternativas descartadas». Además, el plan va a cambiar durante el desarrollo y hace falta un histórico de por qué se tomó cada decisión, no solo de qué cambió.

## Factores de decisión

- Trazabilidad del porqué de cada decisión.
- Poca fricción para un equipo de una persona y una semana de plazo.
- Revisable por PR y legible para los técnicos de EShipping.

## Opciones consideradas

1. ADR en Markdown con formato MADR, dentro del repositorio.
2. Una sección de decisiones dentro de un único documento.
3. Decisiones en la wiki o en las issues de GitHub.

## Decisión

Opción elegida: **ADR en formato MADR dentro de `docs/adr/`**. Es un estándar reconocido, se versiona con el código y cada decisión queda aislada, con su contexto y sus alternativas.

## Consecuencias

- **Positivas:** histórico inmutable de las decisiones; los ADR alimentan directamente el entregable «justificación técnica y alternativas descartadas».
- **Negativas:** un poco más de esfuerzo por decisión.
- **Seguimiento:** el plan (§14) mantiene una vista resumida del estado de las decisiones.

## Análisis de las opciones

### Sección en un único documento
- ✅ Muy sencillo.
- ❌ Se reescribe y se pierde el histórico; mezcla decisiones con planificación.

### Wiki o issues de GitHub
- ✅ Buena integración con GitHub.
- ❌ La wiki no se versiona junto al código ni se revisa por PR; las issues se dispersan.
