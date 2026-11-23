# Plan de actuación — Prueba técnica Ingeniero IA (EShipping)

| Campo | Valor |
|---|---|
| Versión | 1.13.0 |
| Estado | Borrador para revisión |
| Responsable | Pablo Iglesias Peral |
| Última actualización | 23/11/2026 |
| Documentos relacionados | [Índice de ADR](adr/README.md) · [CHANGELOG](../CHANGELOG.md) · [Índice de documentación](README.md) |

> Documento vivo. Cada cambio se registra en el [historial de revisiones](#15-historial-de-revisiones) y cada decisión relevante en un [ADR](adr/README.md). No contiene datos reales.

---

## Índice

1. [Objetivo](#1-objetivo)
2. [Alcance](#2-alcance)
3. [Principios de trabajo](#3-principios-de-trabajo)
4. [Calendario e hitos](#4-calendario-e-hitos)
5. [Fases en detalle](#5-fases-en-detalle)
6. [Estándares de ingeniería de software](#6-estándares-de-ingeniería-de-software)
7. [Estándares de arquitectura](#7-estándares-de-arquitectura)
8. [Estándares de documentación](#8-estándares-de-documentación)
9. [Flujo de trabajo en Git y GitHub](#9-flujo-de-trabajo-en-git-y-github)
10. [Gestión de la calidad](#10-gestión-de-la-calidad)
11. [Seguridad y confidencialidad](#11-seguridad-y-confidencialidad)
12. [Riesgos](#12-riesgos)
13. [Trazabilidad con el enunciado](#13-trazabilidad-con-el-enunciado)
14. [Registro de decisiones](#14-registro-de-decisiones)
15. [Historial de revisiones](#15-historial-de-revisiones)

---

## 1. Objetivo

Diseñar un sistema capaz de procesar un flujo continuo de **unos 100.000 correos operativos al mes**, preparado para crecer a **150.000 al mes o más** sin rediseño, que:

1. reciba e ingiera los correos,
2. los clasifique por tipo de evento,
3. extraiga los datos relevantes,
4. los normalice y los asocie al expediente,
5. los cruce con el ERP (DEIWORLD) y resuelva las discrepancias,
6. almacene el resultado y genere datos útiles para el negocio,
7. aprenda de forma continua de los operativos y de la relación con clientes y proveedores.

Este diseño se valida con una **prueba de concepto (PoC) funcional** sobre los correos y el CSV de muestra.

**Prioridad:** la calidad del planteamiento y la solidez de las decisiones. La PoC valida el diseño y demuestra buenas prácticas de ingeniería; no busca ser espectacular, sino correcta, mantenible y honesta en sus métricas.

### 1.1 Criterios de éxito (según el apartado 10 del enunciado: "Qué valoraremos")

| Criterio de la empresa | Cómo lo demostramos |
|---|---|
| Calidad y claridad de la arquitectura | Documento de arquitectura con modelo C4 y diagramas de secuencia |
| Escalabilidad | Análisis de capacidad (100.000 → 150.000 correos), diseño sin estado y basado en colas, prueba de volumen sintético |
| Solidez de la justificación técnica | ADR con alternativas evaluadas y descartadas |
| Realismo en costes y fiabilidad | Modelo de costes con supuestos explícitos y recalibrado con mediciones de la PoC; métricas por campo con intervalos de confianza |
| Tratamiento de la ambigüedad entre fuentes | Catálogo de ambigüedades y política de resolución documentada y aplicada en el código |
| Claridad en la comunicación | Presentación (PDF o HTML), resumen ejecutivo, repositorio ordenado y guion de la entrevista |

---

## 2. Alcance

### 2.1 Dentro del alcance
- Diseño de la arquitectura completa para producción (más de 100.000 correos).
- PoC de extremo a extremo: ingesta de `.msg` y `.eml` (con adjuntos), clasificación, extracción, normalización, asociación a expediente, cruce con el ERP, discrepancias y almacenamiento.
- Interfaz de la PoC: **línea de comandos (CLI) y Streamlit** (una vista de expedientes, discrepancias y validación por el operativo).
- Evaluación cuantitativa frente a un conjunto de referencia (gold standard).
- Entregables documentales del apartado 8 del enunciado y una presentación final en PDF o HTML.
- Repositorio privado con un proceso de desarrollo completo, accesible para los técnicos de EShipping si lo solicitan.

### 2.2 Fuera del alcance
- Integración real con DEIWORLD, con el buzón corporativo o con las APIs y webs de las navieras: se diseña, pero en la PoC se simula con adaptadores.
- Despliegue en la nube y entrenamiento o fine-tuning de modelos: se diseña y se presupuesta, pero no se ejecuta.
- Autenticación de usuarios en la interfaz.

---

## 3. Principios de trabajo

1. **Confidencialidad primero**: ningún dato real sale de `data/` (ver la [sección 11](#11-seguridad-y-confidencialidad) y el [ADR-0002](adr/0002-proteccion-datos-confidenciales.md)).
2. **Decisiones explícitas y trazables**: toda decisión relevante tiene su ADR, con sus alternativas y consecuencias.
3. **Diseño antes que código**: no se implementa nada que no esté reflejado en el diseño.
4. **Agnóstico de proveedor**: el LLM, el almacenamiento y la ingesta se usan detrás de interfaces (puertos), de modo que la PoC puede usar un modelo local y la producción otro proveedor sin reescribir el dominio.
5. **Medir, no suponer**: las cifras de fiabilidad y de coste salen de mediciones o de supuestos declarados.
6. **Alcance protegido**: si hay retraso, se recorta la PoC, nunca el diseño ni la documentación.
7. **Todo como código**: código, documentación, diagramas, configuración y proceso se versionan en el repositorio.
8. **La IA no es un requisito, es una herramienta**: cada etapa usa la técnica más simple, barata y explicable que la resuelva con la fiabilidad necesaria (parsers, reglas, validaciones, OCR, NLP clásico...). El LLM solo entra donde esas técnicas no llegan, y nunca toma decisiones que deban ser deterministas y auditables. Ver la [sección 7.1](#71-selección-de-técnica-por-etapa).
9. **Escalable y mantenible por diseño**: el volumen actual (100.000 correos al mes) no es el techo. Pasar a 150.000 o más debe resolverse con **configuración y más réplicas, nunca con cambios de arquitectura ni de código**. Cualquier componente que no cumpla esto se rechaza en el diseño. Ver la [sección 7.2](#72-escalabilidad-y-mantenibilidad).

---

## 4. Calendario e hitos

Recepción: jueves 19/11/2026. Plazo de la empresa: jueves 26/11. **Objetivo interno: todo terminado el miércoles 25/11.** El jueves queda solo como colchón de emergencia.

| Fase | Fechas | Milestone en GitHub | Hito al cierre | Versión |
|---|---|---|---|---|
| F0. Entorno y proceso | Sáb 21/11 | `F0 · Entorno` | Repositorio, proceso y plan aprobados | `v0.1.0` |
| F1. Descubrimiento y análisis | Sáb 21 – Dom 22/11 (mañana) | `F1 · Descubrimiento` | Datos entendidos, requisitos y gold standard | `v0.2.0` |
| F2. Diseño | Dom 22/11 (tarde) – Mar 24/11 (mañana) | `F2 · Diseño` | Arquitectura y ADR cerrados | `v0.3.0` |
| F3. Implementación de la PoC | Mar 24/11 | `F3 · PoC` | Pipeline de extremo a extremo funcionando | `v0.4.0` |
| F4. Evaluación y pruebas | Mar 24/11 (noche) – Mié 25/11 (mañana) | `F4 · Evaluación` | Métricas finales, costes recalibrados | `v0.5.0` |
| F5. Documentación y entrega | Mié 25/11 | `F5 · Entrega` | **Todo terminado** | `v1.0.0` |
| F6. Cierre | Tras el proceso de selección | — | Datos reales eliminados | — |

```mermaid
gantt
    title Plan de la prueba técnica (objetivo: 25/11)
    dateFormat YYYY-MM-DD
    axisFormat %a %d
    section Fases
    F0 Entorno y proceso      :done,    f0, 2026-11-21, 1d
    F1 Descubrimiento         :done,    f1, 2026-11-21, 1.5d
    F2 Diseño                 :         f2, 2026-11-23, 1.5d
    F3 PoC                    :         f3, after f2, 0.75d
    F4 Evaluación             :         f4, after f3, 0.5d
    F5 Documentación y entrega:         f5, 2026-11-25, 1d
    Colchón                   :crit,    b,  2026-11-26, 1d
```

Al cierre de cada fase se hace una **revisión de fase**: se comprueban los criterios de salida, se actualiza este plan (y su historial), se escribe el CHANGELOG y se crea la etiqueta de versión.

---

## 5. Fases en detalle

Cada fase indica sus **tareas** (cada una será una issue de GitHub), sus **entregables** y sus **criterios de salida**.

### F0. Entorno y proceso

| # | Tarea | Estado |
|---|---|---|
| F0.1 | Git, `.gitignore`, hook de pre-commit contra datos reales, estructura, `.venv`, `CLAUDE.md` | ✅ |
| F0.2 | Repositorio privado en GitHub | ✅ |
| F0.3 | Plan de actuación, CHANGELOG y sistema de ADR (este documento) | ✅ |
| F0.4 | `pyproject.toml` con dependencias y configuración de las herramientas (ruff, mypy, pytest) | ✅ |
| F0.5 | Framework `pre-commit`: ruff, mypy, detección de secretos y el hook de datos existente | ✅ |
| F0.6 | Plantillas de GitHub: issues (tarea, bug, decisión), PR y `CONTRIBUTING.md` | ✅ |
| F0.7 | Etiquetas, milestones (uno por fase), tablero de GitHub Projects e issues de F1–F5 (issues #2–#50) y tablero de Projects | ✅ |
| F0.8 | CI en GitHub Actions: lint, tipos y tests, solo con datos sintéticos | ✅ |
| F0.9 | Decisión D1 (proveedor de LLM para la PoC) → [ADR-0005](adr/0005-llm-local-ollama-en-la-poc.md) | ✅ |
| F0.10 | Instalar Ollama y descargar los modelos candidatos (sin datos todavía): `qwen3.5:4b`, `gemma4:e4b` (9,5 GB en disco, justo en 16 GB) y `llama3.2:3b` | ✅ |

**Entregables:** el repositorio configurado, este plan, `CHANGELOG.md`, los ADR 0001–0005 y el `CONTRIBUTING.md`.

**Criterios de salida:** el CI pasa en `main`, el plan está aprobado y las issues de F1 están creadas.

### F1. Descubrimiento y análisis

| # | Tarea |
|---|---|
| F1.1 | Inventario de correos: estructura del `.msg` (cabeceras, cuerpo HTML o texto, hilos encadenados, adjuntos, idioma, tipo de remitente) |
| F1.2 | Análisis del CSV del ERP: columnas relevantes para el cruce, formatos, nulos y calidad del dato |
| F1.3 | Cruce manual correo ↔ ERP por expediente: construir el **gold standard** (solo en `data/`) |
| F1.4 | Catálogo de ambigüedades entre fuentes (significados de ETD y ETA según la fuente, fechas estimadas frente a reales, tipos de cut-off, formatos y zonas horarias, varios contenedores, hilos con información contradictoria) |
| F1.5 | Taxonomía de tipos de correo y evento |
| F1.6 | Especificación de requisitos funcionales y no funcionales, con identificadores (`RF-xx`, `RNF-xx`) |
| F1.7 | Lista de preguntas para EShipping y supuestos adoptados (incluida la distribución horaria de los correos, la proporción con PDF y la latencia aceptable por tipo de evento) |

**Entregables:** `docs/01_analisis_datos.md` (describe patrones sin datos reales), `docs/02_requisitos.md`, `docs/03_taxonomia_y_ambiguedades.md` (F1.4 y F1.5 juntas, porque cada ambigüedad se define sobre un evento de la taxonomía), `docs/glosario.md`.

**Criterios de salida:** todos los correos están inventariados, el gold standard está completo, y cada requisito tiene identificador y criterio de aceptación.

### F2. Diseño

| # | Tarea |
|---|---|
| F2.1 | Arquitectura con el modelo C4 (niveles 1 a 3): contexto, contenedores y componentes, aplicando las reglas de escalabilidad y mantenibilidad ([§7.2](#72-escalabilidad-y-mantenibilidad)) |
| F2.1b | Análisis de capacidad: rendimiento por etapa, cuellos de botella, réplicas necesarias a 100.000, 150.000 y 300.000 correos al mes, y qué cambia (solo configuración) al crecer |
| F2.2 | Diagramas de secuencia de los flujos principales: ingesta → evento, discrepancia → revisión, corrección → aprendizaje |
| F2.3 | Modelo de datos: correo, documento, evento extraído (valor, fuente, confianza, evidencia), expediente, discrepancia, corrección. Incluye linaje del dato y bitemporalidad (cuándo ocurrió y cuándo lo supimos) |
| F2.4 | Estrategia de IA (ADR): validar y formalizar la técnica por etapa ([§7.1](#71-selección-de-técnica-por-etapa)): deterministas, plantillas, OCR, NLP clásico y LLM, frente a las alternativas («todo LLM», «todo reglas») |
| F2.5 | Política de resolución de discrepancias (ADR): jerarquía de fuentes por campo, frescura, reglas de dominio y escalado a un humano |
| F2.6 | Diseño de fiabilidad: métricas, calibración de la confianza, umbrales y muestreo de auditoría |
| F2.7 | Modelo de costes **mensual y por correo** para 100.000 y 150.000 correos al mes: cómputo, LLM, OCR, almacenamiento y horas de revisión humana |
| F2.7b | **Comparativa de proveedores de LLM** (pago y autoalojado): precio por millón de tokens, lotes y caché, coste para 100.000 y 150.000 correos, calidad, latencia, residencia en la UE y política de datos. Precios de fuentes oficiales con fecha de consulta |
| F2.8 | Aprendizaje continuo: correcciones como señal, few-shot dinámico, nuevas plantillas y control de calidad de las etiquetas |
| F2.9 | Seguridad, privacidad y cumplimiento (RGPD, retención, seudonimización, proveedores externos) |
| F2.10 | Diseño de la PoC: qué partes de la arquitectura se implementan y cuáles se simulan |

**Entregables:** `docs/04_arquitectura.md`, `docs/05_modelo_datos.md`, `docs/06_costes.md`, `docs/07_fiabilidad.md`, `docs/08_aprendizaje_continuo.md`, `docs/09_seguridad.md` y los ADR correspondientes.

**Criterios de salida:** cada requisito de F1 está cubierto por un componente, y cada decisión tiene su ADR en estado `Aceptado`.

### F3. Implementación de la PoC

| # | Tarea |
|---|---|
| F3.1 | Modelo de dominio y esquemas (Pydantic) |
| F3.2 | Adaptador de ingesta: `.msg`, `.eml` y adjuntos PDF (texto digital y OCR si no hay capa de texto) |
| F3.3 | Extractores deterministas: identificadores (expediente, booking, B/L, contenedor con dígito de control ISO 6346), fechas y puertos (UN/LOCODE) |
| F3.4 | Puerto `LLMClient` y adaptador de Ollama: clasificación y extracción con esquema JSON impuesto, temperatura 0 y entrada limpia ([ADR-0005](adr/0005-llm-local-ollama-en-la-poc.md)) |
| F3.5 | Normalización y asociación correo → expediente |
| F3.6 | Adaptador del ERP (CSV) y motor de reconciliación |
| F3.7 | Persistencia (SQLite, con un esquema migrable a PostgreSQL) |
| F3.8 | CLI (`ingest`, `process`, `report`, `evaluate`) |
| F3.9 | Interfaz Streamlit: expedientes, línea temporal de eventos, discrepancias, validar o corregir |
| F3.10 | Datos sintéticos en `data_sample/` para la demo pública y los tests |

**Alcance recortado (revisión 1.10.0):** para no reducir el diseño (F2), la PoC se recorta en lo que menos aporta a la valoración: la interfaz Streamlit (F3.9) se limita a la vista del expediente, la lista de discrepancias y una corrección simple; el OCR (F3.2) se queda en detectar y marcar los PDF escaneados, y se implementa solo si sobra tiempo. El resto de tareas se mantiene.

**Entregables:** el código en `src/`, los tests en `tests/` y la demo reproducible con `data_sample/`.

**Criterios de salida:** el pipeline procesa la muestra real (en local) y la sintética de extremo a extremo, el CI está en verde y el código tiene cobertura mínima en el dominio.

### F4. Evaluación y pruebas

| # | Tarea |
|---|---|
| F4.1 | Tests unitarios y de integración (pytest) con datos sintéticos |
| F4.2 | Evaluación frente al gold standard: precisión, recall y F1 por campo, exactitud de la clasificación, discrepancias detectadas. **Solo se publican métricas agregadas** |
| F4.3 | Análisis de errores: tipología, qué parte del pipeline falla y **porcentaje resuelto en cada escalón** (determinista, plantilla, ML, LLM, humano) |
| F4.4 | Medición de tokens, latencia y memoria por correo y recalibración del modelo de costes y de la comparativa de proveedores |
| F4.4b | **Benchmark de modelos locales** (2–3 candidatos de 3 a 8B parámetros, cuantizados): acierto frente al gold standard, latencia y memoria. Elección justificada |
| F4.5 | Prueba de volumen sintético (por ejemplo, 10.000 correos generados): rendimiento por etapa y extrapolación al pico de 150.000 correos al mes |

**Entregables:** `docs/10_evaluacion.md` e informe reproducible con `make evaluate`.

**Criterios de salida:** las métricas están documentadas con sus limitaciones (muestra pequeña, intervalos de confianza).

### F5. Documentación y entrega

| # | Tarea |
|---|---|
| F5.1 | Resumen ejecutivo de una página |
| F5.2 | Revisión de coherencia entre documentos y del checklist de la [sección 13](#13-trazabilidad-con-el-enunciado) |
| F5.3 | Presentación final (PDF o HTML; el formato lo elige el responsable) |
| F5.4 | Auditoría de confidencialidad: búsqueda de datos reales en todo el repositorio y su historial, y revisión de las capturas |
| F5.5 | Guion de la entrevista (10–15 minutos) y preguntas previsibles |
| F5.6 | Versión `v1.0.0`: etiqueta, release y CHANGELOG |

**Criterios de salida:** todos los entregables están en verde, la auditoría está limpia y la entrega está enviada.

### F6. Cierre
- Borrar `data/`, las salidas derivadas, el gold standard y todas las copias (Descargas, papelera, adjuntos del correo, cachés y bases de datos locales).
- Confirmar que el historial de git nunca contuvo datos reales.
- Decidir si se archiva el repositorio o se mantiene privado.

---

## 6. Estándares de ingeniería de software

| Ámbito | Estándar |
|---|---|
| Lenguaje | Python 3.14 (`.venv`). Tipado estático en todo el código |
| Proyecto | `pyproject.toml` (PEP 621), estructura de paquete instalable (`src/`) |
| Estilo | `ruff` (lint y formato, PEP 8), docstrings estilo Google |
| Tipos | `mypy` en modo estricto en el dominio |
| Tests | `pytest` y `pytest-cov`; pirámide de tests (unitarios en el dominio e integración en los adaptadores); objetivo de cobertura del 80 % en el dominio |
| Configuración | Variables de entorno y `.env` (no versionado), siguiendo los principios 12-factor; `.env.example` sin secretos |
| Logging | Logging estructurado (JSON) sin datos personales; identificadores seudonimizados en los logs |
| Errores | Excepciones de dominio tipadas, sin `except` genéricos silenciosos |
| Dependencias | Versiones fijadas y lista mínima |
| Automatización | `Makefile` con `setup`, `lint`, `test`, `run`, `demo` y `evaluate` |
| Idioma | Código e identificadores en inglés; documentación, commits y issues en español |

---

## 7. Estándares de arquitectura

- **Arquitectura hexagonal (puertos y adaptadores)**: el dominio no depende de infraestructura. Los puertos son `MailSource`, `DocumentParser`, `LLMClient`, `ERPGateway`, `Repository` y `Notifier`.
- **Principios SOLID** y separación clara entre dominio, aplicación e infraestructura.
- **Modelo C4** para los diagramas y **Mermaid** para que sean versionables.
- **Diseño orientado a eventos**: cada correo genera eventos de dominio inmutables (por ejemplo, `ETAChanged` o `VesselChanged`), y el estado del expediente se deriva de ellos. Esto da auditoría y trazabilidad.
- **Idempotencia** en la ingesta (deduplicación por `Message-ID` y hash), para poder reprocesar sin efectos secundarios.
- **Observabilidad**: métricas por etapa (tiempo, coste, confianza) desde la PoC.
- **Humano en el bucle (human-in-the-loop)**: la baja confianza o las discrepancias críticas se envían a una cola de revisión, nunca se escriben a ciegas en el ERP.

### 7.1 Selección de técnica por etapa

Propuesta preliminar: se valida con los datos en F1 y se formaliza en el ADR de la estrategia de IA (D5) en F2. **Validada y formalizada en el [ADR-0008](adr/0008-estrategia-de-ia-cascada-por-etapa.md)**, que es la referencia vigente. El criterio es elegir la técnica más simple que cumpla, por este orden: **determinista → plantilla → NLP clásico o ML → LLM**.

| Etapa | Técnica principal | Cuándo se recurre a otra | ¿LLM? |
|---|---|---|---|
| Ingesta y parseo (`.msg`, `.eml`, MIME) | Parsers estándar (`extract-msg`, `email`) | — | No |
| Limpieza del cuerpo (HTML, firmas, avisos legales, hilos citados) | Reglas y heurísticas | — | No |
| Texto de PDF digital | Extracción de texto (`pdfplumber`, `pypdf`) | Si el PDF no tiene capa de texto → OCR | No |
| PDF escaneado o imagen | **OCR** (Tesseract) | — | No |
| PDF de formato fijo por proveedor | **Plantillas por proveedor** (coordenadas o anclas de texto) | Proveedor o formato desconocido → LLM, y la salida sirve para crear una plantilla nueva | Solo como respaldo |
| Identificadores (expediente, booking, B/L, contenedor) | **Expresiones regulares y validación** (dígito de control ISO 6346) | — | No |
| Fechas y horas | Parser de fechas con los formatos conocidos y una zona horaria explícita | Expresiones relativas o ambiguas («next Monday», «ETA +2») | Solo los casos ambiguos |
| Puertos | Diccionario UN/LOCODE y coincidencia aproximada | — | No |
| Buques | Lista de buques conocida (ERP e histórico) y coincidencia aproximada | — | No |
| Clasificación del tipo de correo o evento | Reglas por asunto, remitente y palabras clave → modelo clásico (TF-IDF + regresión logística) entrenado con las correcciones | Baja confianza de los anteriores | Solo el resto |
| Extracción de texto libre (retrasos, motivos, cambios) | LLM con esquema JSON | — | **Sí** |
| Asociación correo → expediente | **Claves deterministas** (expediente, booking, B/L, contenedor) | Sin clave → coincidencia por varios campos; si sigue sin resolverse → revisión humana | No |
| Reconciliación con el ERP y discrepancias | **Motor de reglas** con jerarquía de fuentes por campo | — | **Nunca**: debe ser determinista y auditable |
| Resolución de casos dudosos | Revisión humana | — | No (el LLM puede sugerir, el humano decide) |
| Analítica de negocio | SQL y agregaciones | — | No |

### 7.2 Escalabilidad y mantenibilidad

**Dimensionamiento** (supuestos que se validarán con EShipping; ver F1.7):

| Métrica | 100.000 correos al mes | 150.000 correos al mes |
|---|---|---|
| Media por día laborable (unos 22 días) | ~4.500 | ~6.800 |
| Media por hora laborable (unas 10 horas) | ~450 | ~680 |
| Pico estimado (×3 sobre la media horaria) | ~1.400 por hora (~23 por minuto) | ~2.000 por hora (~35 por minuto) |
| Adjuntos (PDF) | Por medir en F1 | Por medir en F1 |

El sistema se dimensiona para el **pico**, no para la media, y con margen para crecer al menos 2× sobre los 150.000 correos al mes.

**Reglas de diseño para la escalabilidad:**
- **Workers sin estado detrás de colas**, con escalado horizontal en cada etapa por separado (OCR, LLM y reconciliación escalan de forma independiente según su cuello de botella).
- **Desacoplamiento por colas**: control de la presión entre etapas (*backpressure*), reintentos con espera exponencial y cola de mensajes fallidos (*dead-letter*). Un pico se absorbe en la cola, no se pierde.
- **Idempotencia** en todas las etapas: se puede reprocesar sin duplicar.
- **Procesamiento por lotes** cuando el proveedor lo permite (las APIs batch de los LLM suelen tener descuento), y procesamiento en tiempo real solo para lo urgente (por ejemplo, un cambio de cut-off).
- **Cascada de técnicas** ([§7.1](#71-selección-de-técnica-por-etapa)): cuanto menos llegue al LLM, menos crece el coste con el volumen.
- **Almacenamiento particionado** por fecha y con índices por expediente, booking y contenedor; retención y archivado definidos.
- **Límites externos**: los límites de uso de la API del LLM y del ERP se gestionan con limitación de tasa y colas, no fallando.
- **Coste proporcional**: el modelo de costes se expresa **por mes y por correo**, para que el paso a 150.000 sea una multiplicación con supuestos visibles.

**Reglas de diseño para la mantenibilidad:**
- **Arquitectura hexagonal**: cambiar de proveedor de LLM, de OCR, de buzón o de base de datos supone cambiar un adaptador, no el dominio.
- **Lo que cambia con el negocio es configuración o datos, no código**: plantillas de proveedores, reglas de clasificación, jerarquía de fuentes, umbrales de confianza y catálogo de tipos de evento. Añadir una naviera nueva no requiere desplegar código.
- **Versionado de todo lo que afecta al resultado**: prompts, modelos, plantillas y reglas, para saber con qué versión se procesó cada correo y poder reprocesar.
- **Esquemas explícitos** (Pydantic, y migraciones de base de datos) y contratos entre etapas.
- **Observabilidad**: métricas por etapa (rendimiento, latencia, cola pendiente, coste, confianza), logs estructurados y alertas. Sin observabilidad no se puede escalar con seguridad.
- **Tests automáticos y CI**, y documentación viva (ADR y runbooks).

**Indicador clave**: el porcentaje de campos resueltos en cada escalón (determinista, plantilla, ML, LLM, humano). Se mide en la PoC (F4) y alimenta el modelo de costes: cuanto menos llegue al LLM, más barato y más explicable es el sistema.

---

## 8. Estándares de documentación

Se aplica *docs-as-code*: la documentación vive en el repositorio, en Markdown, se revisa por PR igual que el código y se versiona con él.

| Artefacto | Propósito | Estándar |
|---|---|---|
| `README.md` | Puerta de entrada: qué es, cómo se ejecuta, dónde está todo | — |
| `docs/README.md` | Índice de toda la documentación | — |
| `docs/PLAN.md` | Plan de actuación (este documento) | Cabecera de control con versión y [historial de revisiones](#15-historial-de-revisiones) |
| `docs/adr/` | **Registro de decisiones**: qué, por qué, alternativas y consecuencias | [MADR](https://adr.github.io/madr/), numerados y nunca borrados (si una decisión cambia, se marca como `Sustituido por ADR-XXXX`) |
| `CHANGELOG.md` | Historial de cambios del proyecto por versión | [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) + [SemVer](https://semver.org/lang/es/) |
| `CONTRIBUTING.md` | Normas de trabajo: ramas, commits, PR, definición de hecho | — |
| Diagramas | Arquitectura y flujos | C4 + Mermaid, dentro del Markdown |
| Docstrings | Documentación del código | Estilo Google |

**Cómo se guarda el histórico** (tres niveles complementarios):
1. **Decisiones** → un ADR por decisión. Es el *porqué*.
2. **Cambios del plan** → el historial de revisiones de este documento. Es el *cómo ha evolucionado la planificación*.
3. **Cambios del producto** → el `CHANGELOG.md` por versión. Es el *qué se ha entregado*.

Git aporta el detalle fino (quién, cuándo y qué línea), y cada entrada de los tres niveles enlaza con su PR o su issue.

---

## 9. Flujo de trabajo en Git y GitHub

Ver el [ADR-0003](adr/0003-flujo-de-trabajo-git.md).

- **Modelo de ramas**: GitHub Flow. `main` siempre estable; ramas cortas `feat/`, `fix/`, `docs/`, `test/`, `chore/` + `<issue>-<tema>` (por ejemplo, `feat/12-extractor-contenedores`).
- **Commits**: [Conventional Commits](https://www.conventionalcommits.org/es/v1.0.0/), en español, atómicos y con referencia a la issue (`Refs #12`, `Closes #12`). Nunca contienen datos reales.
- **Pull requests**: una por issue, con plantilla (contexto, cambios, cómo probarlo, checklist de confidencialidad), CI en verde y autorrevisión antes de fusionar. Fusión *squash* para mantener un historial lineal.
- **Issues**: plantillas para tarea, bug y decisión. Etiquetas por tipo (`type:feat`, `type:docs`, ...), área (`area:ingesta`, `area:extraccion`, ...) y prioridad.
- **Milestones**: uno por fase (F0–F5). **Tablero**: GitHub Projects (Pendiente / En curso / En revisión / Hecho).
- **Versiones**: una etiqueta y una release por fase (`v0.1.0` … `v1.0.0`).
- **Protección de `main`**: en un repositorio privado con el plan gratuito de GitHub, las reglas de protección de ramas no se aplican. Se suple con disciplina documentada (no se hace push directo a `main` y todo pasa por PR) y con el CI. Si se dispone de GitHub Pro, se activa.

---

## 10. Gestión de la calidad

**Definición de hecho (DoD)** de una issue:
- [ ] El código cumple ruff y mypy, y los tests pasan en el CI.
- [ ] Hay tests nuevos para la lógica nueva.
- [ ] La documentación afectada está actualizada (y el ADR, si hubo decisión).
- [ ] No hay datos reales (lo comprueban el hook y la revisión del diff).
- [ ] El PR está revisado y fusionado, y la issue cerrada.

**Revisión de código**: autorrevisión con checklist, más una revisión asistida (`/code-review`) en los PR de código relevantes.

**Revisión de fase**: al cerrar cada milestone se comprueban los criterios de salida y se actualizan el plan, el CHANGELOG y la etiqueta de versión.

---

## 11. Seguridad y confidencialidad

Ver el [ADR-0002](adr/0002-proteccion-datos-confidenciales.md) y el `CLAUDE.md`.

| Control | Medida |
|---|---|
| Repositorio | `.gitignore` (`data/`, `*.csv`, `*.eml`, `*.msg`, ...), hook de pre-commit que bloquea esos ficheros y detección de secretos |
| Salidas | Todo lo derivado de datos reales se guarda en `data/output/` (ignorado) |
| Tests y demo | Solo datos sintéticos (`data_sample/`) |
| Logs | Sin contenido de correos; identificadores seudonimizados |
| Servicios externos | La PoC usa un LLM local (Ollama): los datos reales no salen del equipo ([ADR-0005](adr/0005-llm-local-ollama-en-la-poc.md)). Para producción se documentan las garantías de cada proveedor de pago |
| Asistencia de IA en el desarrollo | Se usa Claude Code, que lee los datos en local y los procesa en la API de Anthropic; se declara en la propuesta |
| Capturas y presentación | Solo con datos sintéticos o anonimizados |
| Cierre | Borrado de todas las copias (F6) |

---

## 12. Riesgos

| ID | Riesgo | Prob. | Impacto | Mitigación |
|---|---|---|---|---|
| R1 | Fuga de datos reales (repositorio, logs, prompts, capturas) | Baja | Crítico | Controles de la sección 11, revisión antes de cada push, auditoría en F5 |
| R2 | Envío no declarado de datos a terceros | Baja | Alto | Decisión D1 explícita y declarada |
| R3 | Muestra pequeña (unos 10 correos) para medir la fiabilidad | Alta | Medio | Intervalos de confianza, transparencia y un diseño de medición para producción |
| R4 | Parseo complejo de `.msg`, de PDF o de hilos | Media | Medio | Librerías maduras (`extract-msg`, `pdfplumber`), OCR solo si hace falta |
| R5 | Un LLM local, con poca memoria (16 GB), rinde peor | Media | Medio | Cascada (reglas primero), entrada limpia, esquema JSON, benchmark de modelos (F4.4b) y comparativa con los de pago |
| R6 | Falta de tiempo | Media | Alto | Alcance protegido (principio 6), milestones diarios, día de colchón |
| R7 | Sobrecarga del proceso (demasiada ceremonia para una persona) | Media | Bajo | Plantillas ligeras e issues de tamaño razonable |
| R8 | Sobreingeniería de la PoC | Media | Medio | Criterios de salida por fase; la PoC solo valida el diseño |
| R9 | Diseño que no aguante el crecimiento (100.000 → 150.000 correos al mes o más) | Media | Alto | Principio 9, reglas de la §7.2, análisis de capacidad (F2.1b) y prueba de volumen (F4.5) |
| R10 | Gold standard etiquetado con asistencia de IA sin revisión humana completa | Media | Alto | Revisión humana antes de publicar las métricas; métricas marcadas como provisionales; la PoC no usa el modelo que etiquetó |

---

## 13. Trazabilidad con el enunciado

| Requisito del enunciado | Entregable | Fase | Estado |
|---|---|---|---|
| 8 · Documento de arquitectura con diagrama | `04_arquitectura.md` | F2 | ⏳ |
| 8 · Justificación técnica y alternativas descartadas | `docs/adr/` | F2 | ⏳ |
| 8 · Estimación de costes | `06_costes.md` | F2, F4 | ⏳ |
| 8 · Planteamiento de la medición de fiabilidad | `07_fiabilidad.md`, `10_evaluacion.md` | F2, F4 | ⏳ |
| 8 · PoC funcional que admite correos nuevos | `src/`, CLI, Streamlit | F3 | ⏳ |
| 7 · Modelo de IA y por qué | ADR de la estrategia de IA | F2 | ⏳ |
| 7 · Coste computacional y económico | `06_costes.md` | F2, F4 | ⏳ |
| 7 · Datos obtenidos y estructura | `05_modelo_datos.md` | F2 | ⏳ |
| 7 · Fiabilidad y baja confianza | `07_fiabilidad.md` | F2 | ⏳ |
| 7 · Escalabilidad (100.000 → 150.000 correos al mes) | `04_arquitectura.md` (análisis de capacidad), `06_costes.md` | F2, F4 | ⏳ |
| 7 · Aprendizaje continuo sin aprender de errores | `08_aprendizaje_continuo.md` | F2 | ⏳ |
| 3 · Ambigüedad entre fuentes | `03_taxonomia_y_ambiguedades.md`, ADR-0006, ADR de reconciliación | F1, F2 | 🔄 |
| 4 · Declarar el envío a servicios externos | `09_seguridad.md`, presentación | F2, F5 | ⏳ |
| 5.1–5.7 · Capacidades del sistema | `02_requisitos.md` (RF-01…RF-73, RNF-01…RNF-44) | F1 | ✅ |

---

## 14. Registro de decisiones

El detalle está en el [índice de ADR](adr/README.md). Aquí se muestra solo el estado.

### 14.1 Decisiones tomadas

| ID | Decisión | ADR |
|---|---|---|
| — | Registrar las decisiones con ADR (formato MADR) | [ADR-0001](adr/0001-registrar-decisiones-con-adr.md) |
| — | Controles de protección de los datos confidenciales | [ADR-0002](adr/0002-proteccion-datos-confidenciales.md) |
| D4 | Proceso completo en GitHub: GitHub Flow, Conventional Commits, SemVer, issues, milestones y PR | [ADR-0003](adr/0003-flujo-de-trabajo-git.md) |
| D2, D3 | Entrega en presentación PDF o HTML con acceso opcional al repositorio; PoC con CLI y Streamlit | [ADR-0004](adr/0004-formato-entrega-e-interfaz-poc.md) |
| D1 | LLM local (Ollama) en la PoC, optimizado para eficiencia; comparativa de proveedores de pago para producción | [ADR-0005](adr/0005-llm-local-ollama-en-la-poc.md) |
| — | Modelo de eventos basado en DCSA (tipo + clasificador planificado, estimado o real), con extensiones para aduanas e incidencias | [ADR-0006](adr/0006-modelo-de-eventos-basado-en-dcsa.md) |
| — | Monolito modular hexagonal desplegado como workers por etapa detrás de colas | [ADR-0007](adr/0007-monolito-modular-con-workers-por-etapa.md) |
| D5 | Estrategia de IA: cascada de técnicas por etapa, con el LLM acotado al texto libre y nunca en la asociación ni en la reconciliación | [ADR-0008](adr/0008-estrategia-de-ia-cascada-por-etapa.md) |
| D6 | Política de discrepancias: autoridad de la fuente por campo, el estado del dato (real sobre estimado) antes que la frescura, regla «ERP más reciente», prioridades P1–P3 y nunca escritura en el ERP sin validación | [ADR-0009](adr/0009-politica-de-resolucion-de-discrepancias.md) |
| D5b | Proveedor de LLM de producción: lista corta de cuatro candidatos con residencia en la UE, elección por evaluación sobre el conjunto de referencia; escenario de referencia de costes con Claude Haiku 5.5 y escalado a Sonnet 5.5; autoalojado como contingencia | [ADR-0010](adr/0010-proveedor-de-llm-de-produccion.md) |

### 14.2 Decisiones abiertas

| ID | Decisión | Opciones | Fase en que se decide |
|---|---|---|---|
| D9 | Modelos locales de la PoC | 2–3 candidatos; se elige por benchmark | F4 |
| D7 | Almacenamiento de producción | PostgreSQL, almacén de eventos, data warehouse | F2 |
| D8 | Plataforma de despliegue de referencia | Nube (AWS, Azure o GCP) o local | F2 |

---

## 15. Historial de revisiones

| Versión | Fecha | Autor | Cambios | Referencia |
|---|---|---|---|---|
| 0.1.0 | 21/11/2026 | P. Iglesias Peral | Primer borrador: fases, riesgos y decisiones abiertas | — |
| 0.2.0 | 21/11/2026 | P. Iglesias Peral | Calendario ajustado para terminar el miércoles 25/11 | — |
| 1.0.0 | 21/11/2026 | P. Iglesias Peral | Plan completo: alcance, estándares de ingeniería, arquitectura y documentación, flujo de GitHub, calidad, trazabilidad; decisiones D2–D4 tomadas; histórico en tres niveles (ADR, historial del plan y CHANGELOG) | `docs/plan-actuacion` |
| 1.1.0 | 21/11/2026 | P. Iglesias Peral | D1 decidida: Ollama en local en la PoC con criterios de eficiencia y comparativa de proveedores de pago (ADR-0005). Nuevas tareas F0.10, F2.7b y F4.4b, y decisión abierta D9. Responsable: Pablo Iglesias Peral | `docs/plan-actuacion` |
| 1.2.0 | 21/11/2026 | P. Iglesias Peral | Principio 8 («la IA no es un requisito»); nueva §7.1 con la técnica por etapa (deterministas, plantillas, OCR, ML clásico, LLM solo para el resto, reconciliación nunca con LLM); F2.4, F3.2 y F4.3 ajustadas | `docs/plan-actuacion` |
| 1.3.0 | 21/11/2026 | P. Iglesias Peral | Volumen como flujo mensual (100.000 al mes, crecimiento a 150.000 o más). Principio 9 y nueva §7.2 de escalabilidad y mantenibilidad con dimensionamiento. Tareas F2.1b (capacidad) y F1.7, F2.7 y F4.5 ajustadas. Riesgo R9 | `docs/plan-actuacion` |
| 1.4.0 | 22/11/2026 | P. Iglesias Peral | F0 casi cerrada: herramientas de calidad (`pyproject.toml`, ruff, mypy estricto, pytest, `Makefile`), `pre-commit` encadenado desde `.githooks/pre-commit`, CI con job de confidencialidad, plantillas de GitHub y `CONTRIBUTING.md`. Etiquetas, milestones e issues #2–#50 creados. Paquete en `src/eshipping_ai/`. Pendiente el tablero de Projects (requiere permiso `project` en `gh`) | #2–#6 |
| 1.5.0 | 22/11/2026 | P. Iglesias Peral | F0.7 cerrada con el tablero de Projects. F0.10: candidatos locales elegidos (`qwen3.5:4b`, `gemma4:e4b`, `llama3.2:3b`), los únicos de 3–8B de las familias recientes que caben en 16 GB. Primer entregable de F1: `docs/01_analisis_datos.md`. Hallazgo que afecta al diseño: la clave de asociación es el **booking** (en 37 de 38 asuntos), no el expediente (7 de 38) | #5, #7, #8, #9 |
| 1.6.0 | 22/11/2026 | P. Iglesias Peral | F1.4 y F1.5 en un único entregable (`docs/03_taxonomia_y_ambiguedades.md`). Nueva decisión: modelo de eventos DCSA (ADR-0006), que afecta a F2.3 y F3.1 | #11, #12 |
| 1.7.0 | 22/11/2026 | P. Iglesias Peral | F1.3: gold standard en dos niveles (correo y expediente) con siete veredictos frente al ERP, incluido `ERP_NEWER` porque el ERP es posterior a los correos. Etiquetado asistido por Claude Code, pendiente de revisión humana; las métricas de F4 serán provisionales hasta entonces (nuevo riesgo R10) | #10 |
| 1.8.0 | 22/11/2026 | P. Iglesias Peral | F1.6 y F1.7: `docs/02_requisitos.md` con 43 RF y 20 RNF (MoSCoW, cobertura en la PoC y criterio de aceptación), 10 supuestos y 13 preguntas; glosario. Supuesto S-01 explícito: el volumen del enunciado se interpreta como mensual | #13, #14 |
| 1.9.0 | 23/11/2026 | P. Iglesias Peral | Revisión de fase de F1, cerrada con `v0.2.0`. Criterios de salida: correos inventariados y requisitos con identificador y criterio de aceptación, cumplidos; gold standard completo pero pendiente de revisión humana (R10 sigue abierto). Retraso de medio día sobre el calendario: F2 se hace de forma compacta, priorizando arquitectura y capacidad, estrategia de IA (D5), discrepancias (D6), costes y diseño de la PoC, para empezar F3 el martes 24/11 por la mañana | #57 |
| 1.10.0 | 23/11/2026 | P. Iglesias Peral | Se revoca el plan compacto de F2 de la revisión 1.9.0: F2 se hace completa y se recorta la PoC (Streamlit mínima y OCR solo si sobra tiempo; ver F3). Calendario: F2 hasta el martes 24/11 por la mañana, F3 el martes y F4 hasta el miércoles por la mañana. Primer entregable de F2: `docs/04_arquitectura.md` (C4 y capacidad) y ADR-0007. Hallazgo de la capacidad: el cómputo no es el cuello de botella (menos de 1,5 núcleos en el pico a 300.000 correos al mes); lo son la revisión humana, el coste del LLM y la frescura del ERP | #15, #16 |
| 1.11.0 | 23/11/2026 | P. Iglesias Peral | D5 decidida: cascada de técnicas por etapa (ADR-0008), que valida §7.1 con la evidencia de F1. El LLM se limita al texto libre, con entrada mínima, esquema JSON, cita verificada y confianza calibrada, y nunca interviene en identificadores, asociación ni reconciliación. La elección del proveedor de producción queda como D5b (F2.7b) | #19 |
| 1.12.0 | 23/11/2026 | P. Iglesias Peral | D6 decidida (ADR-0009): roles de fuente y autoridad por campo en tres rangos, valor vigente con el estado del dato antes que la frescura, fuentes de segunda mano que no sustituyen, conflictos a revisión, regla «ERP más reciente» con y sin fecha de actualización del ERP, regla de error claro, coherencia interna del ERP y prioridades P1–P3. Validación pendiente con operaciones (P-07, P-11) | #20 |
| 1.13.0 | 23/11/2026 | P. Iglesias Peral | F2.7 y F2.7b: `docs/06_costes.md` con precios oficiales consultados el 23/11/2026. Coste técnico de 500 a 1.000 € al mes (menos de 1 céntimo por correo); la revisión humana es más del 90 % del coste total. D5b decidida (ADR-0010). Hallazgo: la API directa de Anthropic no ofrece residencia en la UE; Claude en la UE pasa por Bedrock o Google Cloud | #22, #23 |
