# Changelog

Todos los cambios relevantes del proyecto se documentan en este fichero.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa [Versionado Semántico](https://semver.org/lang/es/). Cada versión `0.x` corresponde al cierre de una fase del [plan](docs/PLAN.md); la `1.0.0` es la entrega.

## [Unreleased]

## [0.2.0] - 2026-11-23

Cierre de la fase F1 (descubrimiento y análisis).

### Added
- Requisitos funcionales y no funcionales con prioridad, cobertura en la PoC y criterio de aceptación; supuestos y preguntas para EShipping (`docs/02_requisitos.md`).
- Glosario de dominio (`docs/glosario.md`).
- Metodología y cifras agregadas del gold standard (`docs/01_analisis_datos.md` §6), con siete veredictos frente al ERP. El gold standard en sí solo existe en local.
- Ambigüedades A-25 a A-29 (ofertas de buques, fechas mal escritas, precintos con formato de contenedor, ERP más reciente que los correos y significado de `Despacho`).
- Taxonomía de correos (9 clases) y de eventos con el modelo DCSA, y catálogo de 24 ambigüedades con su regla de resolución propuesta (`docs/03_taxonomia_y_ambiguedades.md`).
- ADR-0006: modelo de eventos basado en el estándar DCSA.

## [0.1.0] - 2026-11-22

Cierre de la fase F0 (entorno y proceso).

### Added
- Análisis de los datos de la muestra (`docs/01_analisis_datos.md`): estructura de los correos, tipos de correo y de PDF, identificadores, columnas del ERP para el cruce y primeras discrepancias, sin datos reales.
- Tablero de GitHub Projects con todas las tareas del plan.
- Configuración del proyecto en `pyproject.toml` (paquete `eshipping_ai` en `src/`, dependencias de desarrollo fijadas, ruff, mypy estricto, pytest y cobertura) y `Makefile` (`setup`, `lint`, `format`, `typecheck`, `test`, `check`).
- Framework `pre-commit` (ruff, mypy, gitleaks y comprobaciones de ficheros), ejecutado desde el hook de confidencialidad.
- CI en GitHub Actions: job de confidencialidad y secretos, y job de lint, tipos y tests.
- Plantillas de issue (tarea, bug y decisión) y de PR, y `CONTRIBUTING.md`.
- Plan de actuación completo (`docs/PLAN.md`) con fases, estándares, riesgos, trazabilidad e historial de revisiones.
- Sistema de registro de decisiones (ADR, formato MADR) con plantilla e índice.
- ADR-0001 a ADR-0004: uso de ADR, protección de datos confidenciales, flujo de trabajo en Git, y formato de entrega e interfaz de la PoC.
- ADR-0005: LLM local (Ollama) en la PoC, con criterios de eficiencia y comparativa de proveedores de pago para producción.
- Índice de documentación (`docs/README.md`).
- Principio de escalabilidad y mantenibilidad en el plan (§7.2): volumen de 100.000 correos al mes con crecimiento a 150.000 o más sin rediseño.
- Principio de selección de técnica por etapa en el plan (§7.1): la IA solo donde no llegan reglas, plantillas, OCR o ML clásico.

## [0.0.1] - 2026-11-21

### Added
- Estructura base del proyecto (`src/`, `tests/`, `data_sample/`), `README.md` y `CLAUDE.md` con las reglas de confidencialidad.
- `.gitignore` que excluye datos reales (`data/`, `*.csv`, `*.eml`, `*.msg`), entornos virtuales y secretos.
- Hook de pre-commit (`.githooks/pre-commit`) que bloquea commits con ficheros confidenciales.

[Unreleased]: https://github.com/piglper/eshipping-ai-challenge/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/piglper/eshipping-ai-challenge/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/piglper/eshipping-ai-challenge/compare/v0.0.1...v0.1.0
[0.0.1]: https://github.com/piglper/eshipping-ai-challenge/releases/tag/v0.0.1
