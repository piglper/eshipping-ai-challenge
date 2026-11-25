# Changelog

Todos los cambios relevantes del proyecto se documentan en este fichero.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa [Versionado Semántico](https://semver.org/lang/es/). Cada versión `0.x` corresponde al cierre de una fase del [plan](docs/PLAN.md); la `1.0.0` es la entrega.

## [Unreleased]

## [1.0.1] - 2026-11-26

### Changed
- La presentación se reorganiza para la entrevista, con un tribunal de RRHH, sistemas, arquitectura y operativa (#96). Cada bloque se dirige a su público: qué cambia en el día de operativa, con capturas de la PoC sobre datos sintéticos; decisiones y alternativas para arquitectura; qué habría que operar para sistemas; y cómo se ha trabajado y cómo se pondría en marcha, para todos.

## [1.0.0] - 2026-11-25

Entrega de la prueba técnica (fase F5).

### Added
- Resumen ejecutivo de una página (F5.1, `docs/00_resumen_ejecutivo.md`).
- Presentación final en HTML autocontenido y PDF (F5.3, `docs/presentacion/`).
- Auditoría de confidencialidad (F5.4): `make audit` (`python -m eshipping_ai.entrypoints.audit`) busca los valores reales de `data/` en los ficheros versionados, en todos los commits y en las issues y PR de GitHub. Informa de la categoría y el lugar de cada coincidencia, nunca del valor.

### Changed
- Revisión de coherencia entre documentos (F5.2): rol del remitente según el ADR-0013, modelo local del ADR-0015 y RF-11, RF-23, RF-24, RF-26 y RF-27 marcados como parciales en la PoC.
- Los documentos pasan de «Borrador» a «Entregado».

### Security
- Un caso de test de la extracción de referencias usaba un número de booking real. Se sustituye por uno sintético y se reescribe el historial para eliminarlo (`docs/09_seguridad.md` §9).

## [0.5.0] - 2026-11-25

Cierre de la fase F4 (evaluación): métricas frente al gold con intervalos, análisis de errores, rol del remitente en cascada, costes recalibrados con lo medido, benchmark de modelos locales y prueba de volumen.

### Added
- Prueba de volumen (F4.5): `make volume` replica los expedientes sintéticos con identificadores renumerados (`python -m eshipping_ai.synthetic --copies N`) y procesa unos 10.000 mensajes sin LLM. Resultado: unos 9.100 mensajes por minuto en un solo proceso, crecimiento lineal y la misma calidad que el conjunto base (arquitectura §9.10).
- Medición de costes y rendimiento (F4.4). El informe de procesado da la distribución por llamada al LLM de los tokens de entrada y salida y de la latencia (p50, p95 y máximo). Cada etapa de la CLI informa de sus segundos. `docs/06_costes.md` y la arquitectura §9 se recalibran con lo medido: el coste del LLM baja a menos de la mitad.
- Diagnóstico de errores en `eshipping evaluate` (F4.3):
  - la etapa que pierde cada valor esperado (no extraído, extraído mal, leído y no elegido, o de más);
  - el escalón y la zona que resuelven cada valor, con la precisión de lo aceptado sin revisión;
  - si un veredicto falla por el valor o por la reconciliación;
  - qué clases principales se confunden entre sí.
- Evaluación frente al gold standard (F4.2, `docs/11_evaluacion.md`). `eshipping evaluate` mide:
  - la asociación de cada correo (automática y correcta o equivocada, a revisión, sin asociar, ruido);
  - la clase principal y la precisión, el recall y el F1 por clase;
  - la precisión, el recall y el F1 de la extracción por campo, y el acierto del clasificador;
  - el veredicto exacto, la matriz de confusión y la detección de lo que pide acción.

  Cada proporción lleva su intervalo de Wilson al 95 %. El informe en Markdown o JSON (`--format`, `--out`) solo tiene cifras agregadas; los fallos, que nombran expedientes, solo salen con `--verbose`. Objetivos `make evaluate` (sintético) y `make evaluate-real` (muestra real, solo en local).
- `Mail` guarda su origen (`source_ref`) y el orden de los correos incrustados (`position`), con la migración 0003. Puerto `ProcessingStore.mail_outcomes()`.
- Tests de propiedades con Hypothesis (F4.1): con cualquier texto los extractores no fallan y cada mención apunta a los caracteres exactos que cita. El dígito de control ISO 6346 detecta cualquier error de un dígito, una fecha completa se lee tal como está escrita y una fecha sin año cae junto al mensaje. El perfil `HYPOTHESIS_PROFILE=thorough` lanza 5.000 ejemplos por propiedad.
- Marcador `integration`, que lleva solo todo test que usa el conjunto sintético generado, y los objetivos `make test-unit` y `make test-integration`.
- Test de integración con ficheros rotos, vacíos y binarios en la carpeta de correos: cuentan como fallo de ingesta o no dan mensajes, y los veredictos no cambian.
- Casos límite de fechas: fechas imposibles, el 29 de febrero sin año, rangos invertidos y rangos que cruzan el fin de año.
- Guía «Cómo probarlo» en el README.
- Dependencia de desarrollo `hypothesis` 6.170.17.

### Changed
- El modelo local por defecto pasa a ser `qwen3.5:4b`, elegido por benchmark frente a `llama3.2:3b` y `gemma4:e4b` (F4.4b, ADR-0015, `docs/11_evaluacion.md` §5.8).
- La ingesta de `.msg` solo descodifica el cuerpo HTML (RTF comprimido de Outlook) cuando no hay texto plano. Era el 97 % del tiempo de ingesta: la muestra pasa de 36,5 s a 2,8 s, con el mismo resultado.
- El rol del remitente se resuelve en cascada (ADR-0013), sin dar de alta los dominios uno a uno:
  - un directorio corto y curado: los dominios propios y un registro público de navieras;
  - las partes del expediente en el ERP (`Línea Transporte`, `Agente Aduana`, `Transportistas`, `Cliente Op.`, `Shipper` y `Consignee`), con una coincidencia estricta del nombre con el dominio o con el nombre visible del remitente;
  - y, por defecto, informativo.

  `config/senders.yaml` gana la sección `erp_parties` y pierde los dominios de transportista y agente de aduanas, que ahora salen del ERP. El procesado cuenta los mensajes por rol y por la señal que lo decidió (`roles=`). El ERP sintético tiene las columnas `Transportistas` y `Agente Aduana`.
- Un valor del LLM rellena un hueco, pero no desplaza a un valor fiable de las reglas (ADR-0014). Si discrepa, queda pendiente de confirmación.
- El clasificador no cuenta la palabra que etiqueta un booking (`BKG 990000101`, `booking nº ...`). Un hilo la conserva en el asunto trate de lo que trate cada respuesta, y por eso las respuestas de transporte salían como reserva. «Booking confirmation» sí cuenta. En la muestra real, la clase principal pasa del 47 % al 63 %.
- `make evaluate-real` usa una carpeta de trabajo por modelo, para comparar ejecuciones.
- La cobertura mínima del 90 % se exige en `make test` y en el CI (`fail_under`). La página de Streamlit queda fuera de la medida, porque se prueba con `AppTest` en un proceso que coverage no ve.

### Fixed
- El adaptador de Ollama acepta una respuesta que es la lista de hechos sin el objeto que la envuelve, cuando el esquema tiene una única propiedad de tipo lista. `gemma4:e4b` respondía así en una de cada seis llamadas, que fallaban.
- El lugar de carga de un expediente del gold sintético se partía en dos claves por una coma sin comillas en `sample.yaml`.
- `make help` muestra los objetivos con guion (`demo-llm`, `test-unit`, `test-integration`).

## [0.4.0] - 2026-11-24

Cierre de la fase F3 (PoC): canalización de extremo a extremo con CLI, escalón del LLM local y vista para operativos.

### Added
- Vista para operativos en Streamlit (F3.9, `make ui`): discrepancias de todos los expedientes por prioridad, vista del expediente con sus campos y la línea temporal de observaciones (estado, fuente y rango, escalón, zona y cita) y corrección simple. `ApplyCorrection`: aceptar o corregir añade una observación humana y rechazar sustituye la observación ganadora; nunca se edita lo que dijo una fuente, y el expediente se reconcilia de nuevo. Streamlit 1.66.1 como extra opcional `ui`.
- Escalón del LLM (F3.4, ADR-0008): `OllamaClient` (biblioteca estándar, esquema JSON impuesto con `format` o, si el modelo no lo admite, en las instrucciones; temperatura 0) y `FakeLLMClient`. Solo se pregunta por los campos que la clase del mensaje hace esperables, que las reglas no han encontrado y de los que el texto tiene pista. Cada valor se valida de forma determinista: la cita existe en el texto, la fecha está escrita en ella con contexto y sin que las reglas la atribuyan a otro campo, la fecha es plausible, el buque y el número de contenedores salen de la cita. Lo que falla se descarta y se cuenta por motivo. La confianza es fija por escalón (zona de revisión). `--no-llm`, `--model` y `--ollama-url` en la CLI y `make demo-llm`.
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

[Unreleased]: https://github.com/piglper/eshipping-ai-challenge/compare/v1.0.1...HEAD
[1.0.1]: https://github.com/piglper/eshipping-ai-challenge/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/piglper/eshipping-ai-challenge/compare/v0.5.0...v1.0.0
[0.5.0]: https://github.com/piglper/eshipping-ai-challenge/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/piglper/eshipping-ai-challenge/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/piglper/eshipping-ai-challenge/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/piglper/eshipping-ai-challenge/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/piglper/eshipping-ai-challenge/compare/v0.0.1...v0.1.0
[0.0.1]: https://github.com/piglper/eshipping-ai-challenge/releases/tag/v0.0.1
