# Changelog

Todos los cambios relevantes del proyecto se documentan en este fichero.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa [Versionado Semántico](https://semver.org/lang/es/). Cada versión `0.x` corresponde al cierre de una fase del [plan](docs/PLAN.md); la `1.0.0` es la entrega.

## [Unreleased]

### Added
- Plan de actuación completo (`docs/PLAN.md`) con fases, estándares, riesgos, trazabilidad e historial de revisiones.
- Sistema de registro de decisiones (ADR, formato MADR) con plantilla e índice.
- ADR-0001 a ADR-0004: uso de ADR, protección de datos confidenciales, flujo de trabajo en Git, y formato de entrega e interfaz de la PoC.
- Índice de documentación (`docs/README.md`).

## [0.0.1] - 2026-11-21

### Added
- Estructura base del proyecto (`src/`, `tests/`, `data_sample/`), `README.md` y `CLAUDE.md` con las reglas de confidencialidad.
- `.gitignore` que excluye datos reales (`data/`, `*.csv`, `*.eml`, `*.msg`), entornos virtuales y secretos.
- Hook de pre-commit (`.githooks/pre-commit`) que bloquea commits con ficheros confidenciales.

[Unreleased]: https://github.com/piglper/eshipping-ai-challenge/compare/v0.0.1...HEAD
[0.0.1]: https://github.com/piglper/eshipping-ai-challenge/releases/tag/v0.0.1
