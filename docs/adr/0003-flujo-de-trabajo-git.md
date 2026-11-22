# ADR-0003: Flujo de trabajo en Git y GitHub

- **Estado:** Aceptado
- **Fecha:** 2026-11-21
- **Decisores:** Pablo Iglesias Peral
- **Referencias:** [PLAN.md §9](../PLAN.md#9-flujo-de-trabajo-en-git-y-github), decisión D4

## Contexto y problema

Los técnicos de EShipping pueden revisar el repositorio para valorar cómo se trabaja: ramas, commits, PR y gestión de tareas. Se quiere demostrar un ciclo de desarrollo profesional, adaptado a una persona y a una semana de plazo.

## Factores de decisión

- Que sea un proceso reconocible como estándar en la industria.
- Historial legible y trazable entre issue, PR y commit.
- Que no frene el avance con ceremonia innecesaria.

## Opciones consideradas

1. GitHub Flow + Conventional Commits + SemVer, con issues, milestones, Projects y PR.
2. Git Flow (ramas `develop`, `release` y `hotfix`).
3. Trunk-based con commits directos a `main`.

## Decisión

Opción elegida: **GitHub Flow + Conventional Commits + SemVer, con el proceso completo en GitHub**:

- `main` siempre estable. Ramas cortas `tipo/<issue>-<tema>`.
- Conventional Commits en español, con referencia a la issue.
- Un PR por issue, con plantilla y checklist de confidencialidad, CI en verde y fusión *squash*.
- Issues con plantillas y etiquetas; un milestone por fase; tablero de GitHub Projects.
- Una etiqueta y una release por fase (`v0.x.0`) y `v1.0.0` en la entrega.

## Consecuencias

- **Positivas:** trazabilidad completa entre requisito, issue, PR, commit y release; el historial es legible para los revisores.
- **Negativas:** sobrecarga del proceso para una persona (riesgo R7), que se mitiga con plantillas ligeras.
- **Limitación:** en un repositorio privado con el plan gratuito, GitHub no aplica la protección de ramas. Se suple con disciplina documentada y con el CI; se activa si se dispone de GitHub Pro.

## Análisis de las opciones

### Git Flow
- ✅ Muy estructurado.
- ❌ Excesivo para entrega continua y una sola persona; más ramas que mantener.

### Trunk-based con commits directos
- ✅ Lo más rápido.
- ❌ No demuestra revisión ni trazabilidad, que es justo lo que se quiere enseñar.
