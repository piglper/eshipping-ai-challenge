# Changelog

Todos los cambios relevantes del proyecto se documentan en este fichero.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa [Versionado Semántico](https://semver.org/lang/es/). Cada versión `0.x` corresponde al cierre de una fase del [plan](docs/PLAN.md); la `1.0.0` es la entrega.

## [Unreleased]

### Added
- CLI `eshipping` (F3.8): `ingest`, `process`, `reconcile`, `run`, `report` (Markdown o JSON, lo urgente primero, con valor de los correos, valor del ERP, veredicto, regla y cita) y `evaluate` (acierto del veredicto por campo frente a un gold). Opciones `--workdir`, `--now` para repetir un día y `ESHIPPING_DATABASE_URL`. `make demo` ejecuta todo sobre los datos sintéticos. Adaptadores `SystemClock`, `FixedClock` y `LogNotifier` (avisos urgentes al log sin contenido).
- Asociación y procesado (F3.5, parte 2): `ProcessMessages` lee cada correo como un hilo, reúne los identificadores de todos sus mensajes y adjuntos (el booking suele estar solo en el asunto del último mensaje), decide el ruido con ese contexto, clasifica, asocia al expediente y guarda las observaciones con su zona de fiabilidad, rol de la fuente y evidencia. La asociación va del identificador más fuerte al más débil (expediente, booking vigente o sustituido, B/L, contenedor); un identificador de varios expedientes va a revisión y un expediente seguro enseña al índice los bookings y contenedores nuevos, de modo que un roleo con booking nuevo no parte el hilo. El booking que el hilo da por sustituido es alias, no valor. El índice de alias se siembra con el ERP.
- Directorio de remitentes (`config/senders.yaml`, RF-73): rol y orden día-mes por dominio; un remitente desconocido es un cliente. Con el orden conocido, una fecha como `04/10` deja de ser ambigua.
- Tablas `classification` y `association` con la migración 0002 y los puertos `InboxReader` y `ProcessingStore`.
- Reglas de extracción (F3.5, parte 1): clasificación por palabras clave con las clases de la taxonomía, triaje (carril urgente y mensajes sin ningún identificador) y paso de los hallazgos a candidatos de observación. La palabra que acompaña a una fecha decide si es salida, llegada, cut-off, carga o levante, y el vocabulario de la línea decide si es planificada, estimada o real; si las reglas no lo saben, no adivinan. Se reconocen buque y viaje, el cambio de buque, el booking sustituido en un roleo (no es un candidato vigente), el número de contenedores y las listas de opciones sin confirmar (A-25). Cada candidato lleva su evidencia literal.
- Persistencia (F3.7): `SqlRepository` sobre SQLAlchemy con todos los almacenes del dominio (SQLite en la PoC, PostgreSQL cambiando la URL), escrituras idempotentes, consulta «qué se sabía a fecha X» con `known_at` y `recorded_at`, sustitución de observaciones sin perder la historia y veredictos que sustituyen al anterior. Migraciones de Alembic (`make migrate`) comprobadas contra el esquema de la aplicación. Dependencias `sqlalchemy` 2.1.9 y `alembic` 1.20.1.
- Reconciliación con el ERP (F3.6, ADR-0009): lectura del CSV con normalización de espacios, fechas e indicadores; valor vigente de cada campo (humano, real sobre estimado, frescura entre fuentes de autoridad, fuente informativa pendiente de confirmación y conflictos); comparación con tolerancias de fecha, rango y aproximada, alias de booking y similitud de buque; reglas A («ERP más reciente») y B («error claro»); coherencia interna del ERP; lectura antigua; los siete veredictos con prioridades P1 a P3 y aviso de lo urgente. Política en `config/reconciliation.yaml`. El sistema nunca escribe en el ERP.
- Extractores deterministas (F3.3): identificadores con contexto (contenedores con dígito de control ISO 6346, bookings con alias anterior, expedientes completos y truncados, B/L), fechas con precisión (rangos, aproximadas, relativas, año inferido y orden día-mes marcado como ambiguo salvo perfil de remitente), puertos con UN/LOCODE y rol (carga o descarga), y equipo con código ISO y TEU. Todos devuelven la posición del hallazgo para citarlo como evidencia.
- Ingesta (F3.2): lectura de carpetas de `.eml` y `.msg`, desempaquetado de correos incrustados, división de cada hilo en mensajes fechados por su propia cabecera, limpieza de firmas, avisos legales e imágenes, deduplicación de mensajes citados por hash, texto de los PDF (los escaneados se marcan sin OCR) y almacén de objetos local con claves por hash. El cuerpo de un correo contenedor no cuenta como mensaje.
- Puertos `MailParser` y `ParsedMail`; `Repository` se divide en `InboxStore`, `ObservationStore`, `AliasStore`, `ErpStore` y `ProjectionStore`.
- Dependencias `extract-msg` 0.58.3 y `pypdf` 7.1.1.
- Modelo de dominio (`src/eshipping_ai/domain/`): vocabulario (clases de correo, eventos DCSA, clasificadores, roles y rangos de fuente, veredictos), identificadores con validación ISO 6346, entidades inmutables de las tres capas del modelo de datos con sus reglas de coherencia, y puertos de la arquitectura hexagonal.
- Contrato de capas con `import-linter` en `make lint` y en el CI.
- Dependencia de ejecución `pydantic` 2.14.4; de desarrollo, `import-linter` 2.17.
- Datos sintéticos (`data_sample/spec/sample.yaml`) y generador determinista (`eshipping_ai.synthetic`, `make sample`): cuatro expedientes inventados y un correo de ruido que siembran los siete veredictos, con correos contenedores `.eml`, ERP en CSV con el formato del real y gold en el mismo formato que el real.
- Dependencias `pyyaml` 6.0.4 y, de desarrollo, `types-pyyaml`.

### Fixed
- La evidencia de una fecha ya no empieza en mitad de una palabra.
- La clave de idempotencia de una observación incluye el expediente: un mensaje que habla de varios expedientes perdía observaciones con el mismo campo y valor.
- Seguridad: un remitente que no pasa SPF, DKIM o DMARC recibe el rol `customer`, coherente con el ADR-0009.

## [0.3.0] - 2026-11-23

Cierre de la fase F2 (diseño).

### Added
- Arquitectura (`docs/04_arquitectura.md`): impulsores, C4 niveles 1 a 3, funcionamiento de la canalización (prioridades, idempotencia, fallos, configuración versionada) y análisis de capacidad a 100.000, 150.000 y 300.000 correos al mes.
- ADR-0007: monolito modular hexagonal desplegado como workers por etapa detrás de colas.
- ADR-0008: estrategia de IA (D5), cascada de técnicas por etapa con el LLM acotado al texto libre y controles sobre su salida (entrada mínima, esquema JSON, cita verificada, confianza calibrada).
- ADR-0009: política de resolución de discrepancias (D6), con autoridad de la fuente por campo, valor vigente, tolerancias, veredictos, regla «ERP más reciente», coherencia interna del ERP y prioridades.
- Costes (`docs/06_costes.md`): coste del LLM por proveedor y escenario con precios oficiales consultados el 23/11/2026, requisitos de máquina por rol y coste técnico mensual a 100.000, 150.000 y 300.000 correos.
- ADR-0010: proveedor de LLM de producción (D5b), lista corta con residencia en la UE y elección por evaluación.
- Fiabilidad (`docs/07_fiabilidad.md`): métricas, confianza calibrada con vigilancia diaria y recalibración semanal y por evento, umbrales por campo, auditoría continua y límites estadísticos de la PoC.
- Modelo de datos (`docs/05_modelo_datos.md`): entrada y observaciones inmutables, proyecciones recalculables, linaje y bitemporalidad.
- Diagramas de secuencia de los flujos principales (`docs/04_arquitectura.md` §12).
- Aprendizaje continuo (`docs/08_aprendizaje_continuo.md`): mecanismos, control de calidad de las etiquetas, reversibilidad y gobernanza.
- Diseño de la PoC (`docs/10_diseno_poc.md`): qué se implementa y qué se simplifica, estructura del código, interfaces, datos sintéticos y orden de implementación.
- ADR-0011: almacenamiento de producción (D7), PostgreSQL y almacén de objetos compatible con S3.
- ADR-0012: despliegue (D8), contenedores portables en un servicio gestionado de la UE, sin Kubernetes.
- Seguridad y RGPD (`docs/09_seguridad.md`): datos, base legal y retención, controles, seudonimización antes del LLM y amenazas propias como la inyección de instrucciones.

### Changed
- Plan 1.10.0: F2 completa y PoC recortada (Streamlit mínima, OCR solo si sobra tiempo); calendario ajustado.

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

[Unreleased]: https://github.com/piglper/eshipping-ai-challenge/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/piglper/eshipping-ai-challenge/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/piglper/eshipping-ai-challenge/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/piglper/eshipping-ai-challenge/compare/v0.0.1...v0.1.0
[0.0.1]: https://github.com/piglper/eshipping-ai-challenge/releases/tag/v0.0.1
