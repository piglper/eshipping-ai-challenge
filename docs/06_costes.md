# Costes: LLM e infraestructura

| Campo | Valor |
|---|---|
| Versión | 0.1.0 |
| Estado | Borrador (se recalibra en F4.4 con las mediciones de la PoC) |
| Responsable | Pablo Iglesias Peral |
| Última actualización | 23/11/2026 |
| Tareas | F2.7 (#22), F2.7b (#23) |
| Decisiones | [ADR-0010](adr/0010-proveedor-de-llm-de-produccion.md) (D5b); se apoya en [ADR-0005](adr/0005-llm-local-ollama-en-la-poc.md), [ADR-0007](adr/0007-monolito-modular-con-workers-por-etapa.md) y [ADR-0008](adr/0008-estrategia-de-ia-cascada-por-etapa.md) |
| Fuentes | [Arquitectura §9](04_arquitectura.md#9-análisis-de-capacidad-f21b) (volúmenes, tokens y cómputo), precios oficiales consultados el **23/11/2026** (§6) |

> **Confidencialidad:** sin datos reales. Todas las cifras de volumen son supuestos explícitos.

## 1. Resumen

- **Alcance:** el coste técnico de la solución, es decir, el **LLM** y las **máquinas** necesarias para la infraestructura. El trabajo de revisión del equipo de operaciones no se valora en euros: depende de EShipping. El sistema lo mide como volumen (elementos y horas estimadas, [arquitectura §9.6](04_arquitectura.md#96-revisión-humana-el-cuello-de-botella-real)).
- **LLM:** con la cascada y modelos pequeños, **entre 20 y 260 $ al mes** con 100.000 correos y entre 30 y 390 $ con 150.000, según el proveedor (§3.3). Escenario de referencia: unos **62 $ y 94 $**.
- **Máquinas:** la carga cabe en **dos servidores de aplicación de 4 vCPU y 16 GB**, **dos servidores de base de datos de 2 vCPU y 8 GB** y **un servidor de monitorización**, más almacenamiento de objetos. Con precios de un proveedor europeo, unos **300 € al mes**, iguales para 100.000 y 150.000 correos (§4).
- **Total técnico:** unos **360 € al mes con 100.000 correos (0,36 céntimos por correo)** y **unos 390 € con 150.000 (0,26 céntimos)**. Con 300.000 basta añadir un servidor de aplicación: unos 560 € (§5).
- **LLM autoalojado:** requiere una GPU de 24 GB (por ejemplo, NVIDIA L4) por réplica; con alta disponibilidad, unos 1.100 € al mes. Es más caro que la API a este volumen y solo se justifica si los datos no pueden salir del entorno de EShipping (P-10).
- **Residencia en la UE:** la API directa de Anthropic no ofrece hoy inferencia ni almacenamiento en la UE (solo `global` y `us`); Claude con residencia en la UE pasa por **Amazon Bedrock o Google Cloud** con endpoint regional (+10 %). OpenAI cobra un 10 % más por el procesamiento regional. Mistral es un proveedor europeo (§3.4).

## 2. Supuestos

Además de los de la [arquitectura §9.1](04_arquitectura.md#91-parámetros) (volumen, 25 % de ruido, 50 % de correos operativos con LLM, tiempos de CPU por unidad):

| ID | Supuesto | Valor | Cómo se valida |
|---|---|---|---|
| C-01 | Llamadas al LLM al mes | 37.500 (100.000 correos) y 56.250 (150.000) | Porcentaje por escalón en la PoC (F4.3) |
| C-02 | Tokens por llamada | 3.000 de entrada (1.200 de instrucciones y esquema, fijos y cacheables; 1.800 del mensaje) y 400 de salida | Medición en la PoC (F4.4) |
| C-03 | Llamadas que escalan al modelo superior | 10 % | Medición en la PoC |
| C-04 | Diferencia de tokenizador | Los modelos Claude 4.7 y posteriores generan unos 30 % más tokens para el mismo texto, según Anthropic; se aplica ×1,3 a Claude. Para el resto se usa el recuento base (incertidumbre de ±30 %) | Recuento real por proveedor en la evaluación (ADR-0010) |
| C-05 | Caché del prefijo fijo | Activa en horario laboral (con 8 o más llamadas por minuto en el pico, la caché de 5 minutos se mantiene). Se ignora el coste de escritura en caché | — |
| C-06 | Residencia en la UE | Se aplica la prima regional publicada por cada proveedor cuando la hay | Contrato (P-10) |
| C-07 | Tipo de cambio | 1 $ = 0,90 € (solo para los totales; los precios del LLM se dan en dólares, como los publica cada proveedor) | — |
| C-08 | Precios de máquinas | Hetzner (centros de datos en Alemania y Finlandia) como **referencia de precio europeo**, sin IVA. No es la elección de plataforma: eso se decide en D8 (#28) | — |

## 3. Coste del LLM

### 3.1 Precios oficiales

Dólares por millón de tokens, tarifa estándar, consultados el **23/11/2026** (§6).

| Proveedor | Modelo | Entrada | Entrada en caché | Salida | Lotes | Residencia en la UE |
|---|---|---|---|---|---|---|
| Anthropic | Claude Haiku 5.5 (hasta 100.000 tokens de entrada) | 0,10 | 0,01 | 0,50 | −50 % | API directa: no; Bedrock y Google Cloud con endpoint regional: +10 % |
| Anthropic | Claude Sonnet 5.5 | 2,00 | 0,10 | 10,00 | −50 % | Igual |
| OpenAI | GPT-5.4 nano | 0,20 | 0,02 | 1,25 | −50 % | Procesamiento regional: +10 % |
| OpenAI | GPT-5.4 mini | 0,75 | 0,075 | 4,50 | −50 % | +10 % |
| OpenAI | GPT-6.2 sol | 2,00 | 0,10 | 10,00 | −50 % | +10 % |
| Google | Gemini 3.5 Flash-Lite | 0,30 | 0,03 | 2,50 | −50 % | Regiones de la UE en Vertex AI |
| Google | Gemini 3.8 Flash (desde el 01/01/2027; hasta el 31/12/2026, 0,75 / 3,75) | 1,50 | 0,15 | 7,50 | −50 % | Igual |
| Mistral | Mistral Small 4 | 0,15 | 0,015 | 0,60 | −50 % | Proveedor europeo |
| Mistral | Mistral Large 4 | 0,70 | 0,07 | 2,10 | −50 % | Igual |

Para cada proveedor se comparan dos gamas: un modelo **pequeño** para el flujo normal y uno **intermedio** para el escalado ([ADR-0008](adr/0008-estrategia-de-ia-cascada-por-etapa.md), control 6). Los modelos de gama alta (por ejemplo, Claude Opus 5.5 a 4 / 20 $ o GPT-6.2 astra a 8 / 40 $) no se justifican para extracción con esquema.

### 3.2 Coste mensual por modelo

Con los supuestos C-01 a C-06 y residencia en la UE:

| Modelo | Por 1.000 llamadas | 100.000 correos/mes | 150.000 correos/mes |
|---|---|---|---|
| Mistral Small 4 | 0,53 $ | 20 $ | 30 $ |
| Claude Haiku 5.5 | 0,56 $ | 21 $ | 32 $ |
| GPT-5.4 nano | 0,97 $ | 36 $ | 55 $ |
| Gemini 3.5 Flash-Lite | 1,58 $ | 59 $ | 89 $ |
| Mistral Large 4 | 2,18 $ | 82 $ | 123 $ |
| GPT-5.4 mini | 3,56 $ | 134 $ | 200 $ |
| Gemini 3.8 Flash (precio de 2027) | 5,88 $ | 220 $ | 331 $ |
| GPT-6.2 sol | 8,49 $ | 318 $ | 478 $ |
| Claude Sonnet 5.5 | 11,04 $ | 414 $ | 621 $ |

### 3.3 Escenarios

| Escenario (modelo principal + 10 % de escalado) | 100.000 correos/mes | 150.000 correos/mes |
|---|---|---|
| **Referencia:** Claude Haiku 5.5 + Claude Sonnet 5.5 (Bedrock o Google Cloud, región de la UE) | 62 $ | 94 $ |
| **Europeo:** Mistral Small 4 + Mistral Large 4 | 28 $ | 42 $ |
| GPT-5.4 nano + GPT-5.4 mini | 49 $ | 75 $ |
| Gemini 3.5 Flash-Lite + Gemini 3.8 Flash (2027) | 81 $ | 122 $ |
| Conservador: Gemini 3.8 Flash (2027) + Claude Sonnet 5.5 | 262 $ | 393 $ |
| **Sin cascada:** todo el correo (≈ 6.500 tokens de entrada y 500 de salida) a Claude Sonnet 5.5 | ≈ 2.574 $ | ≈ 3.861 $ |

- Entre los escenarios con modelos pequeños, la diferencia es de unos 50 $ al mes: **el precio no decide el proveedor**; deciden la calidad medida y el cumplimiento ([ADR-0010](adr/0010-proveedor-de-llm-de-produccion.md)).
- Sin cascada, el coste se multiplica por unas 40. El argumento principal de la cascada sigue siendo la fiabilidad y la auditabilidad ([ADR-0008](adr/0008-estrategia-de-ia-cascada-por-etapa.md)), pero el ahorro también es real.
- Los descuentos por lotes (−50 %) no se aplican al flujo normal por el plazo de RNF-03 (arquitectura §7.1); sí a los reprocesados y a las evaluaciones.

**Sensibilidad** del escenario de referencia con 100.000 correos al mes (base: 62 $):

| Cambio | Coste del LLM |
|---|---|
| Llega al LLM el 25 % de los correos operativos en lugar del 50 % | ≈ 31 $ |
| Llega al LLM el 100 % | ≈ 124 $ |
| El doble de tokens por llamada | ≈ 124 $ |
| Escalado del 30 % en lugar del 10 % | ≈ 145 $ |
| Todo lo anterior a la vez | ≈ 580 $ |

### 3.4 Criterios no económicos

| Criterio | Anthropic (API directa) | Anthropic en Bedrock o Google Cloud | OpenAI | Google (Vertex AI) | Mistral |
|---|---|---|---|---|---|
| Inferencia en la UE | No (solo `global` o `us`) | Sí, endpoint regional (+10 %); disponibilidad del modelo concreto en región de la UE a confirmar | Sí, procesamiento regional (+10 %) | Sí, regiones de la UE | Proveedor europeo; región y contrato de tratamiento a confirmar |
| Uso de los datos para entrenar | No sin permiso expreso | Lo rige el proveedor de nube, que es el encargado del tratamiento | No verificado en esta consulta; se revisa en el contrato | Nivel de pago: «el contenido no se usa para mejorar los productos» | No verificado en esta consulta |
| Retención | Sin retención del contenido por defecto (salvo los modelos Fable y Mythos); retención cero bajo acuerdo; la API por lotes retiene 29 días | Política del proveedor de nube | Se revisa en el contrato | Se revisa en el contrato | Se revisa en el contrato |
| Salida con esquema JSON | Sí | Sí | Sí | Sí | Sí |
| Calidad en extracción en español e inglés | A medir en la evaluación (ADR-0010) | A medir | A medir | A medir | A medir |

La calidad no se puede comparar con los datos reales sin enviarlos a cada proveedor, y eso requiere autorización (ADR-0002, ADR-0005).

## 4. Requisitos de máquina

### 4.1 Recursos por rol

A partir del cómputo en el pico ([arquitectura §9.3](04_arquitectura.md#93-cómputo-por-etapa-en-el-pico)): incluso con 300.000 correos al mes, el procesado sin LLM ocupa menos de 1,5 núcleos. Los recursos los fijan la **memoria de cada proceso** y la **disponibilidad** (dos réplicas por rol), no la carga.

| Rol ([ADR-0007](adr/0007-monolito-modular-con-workers-por-etapa.md)) | Réplicas | CPU por réplica | Memoria por réplica | Por qué |
|---|---|---|---|---|
| `ingest` (conector de buzón) | 2 | 0,5 vCPU | 0,5 GB | Limitado por la API del buzón |
| `parse` (parseo y división) | 2 | 0,5 vCPU | 1 GB | Correos de hasta ≈ 130.000 caracteres y adjuntos en memoria |
| `document` (texto de PDF y OCR) | 2 | 1 vCPU | 2 GB | Tesseract y el renderizado de páginas a imagen son la etapa con más CPU y memoria |
| `extract` (cascada, pasarela de LLM) | 2 | 0,5 vCPU | 1 GB | Reglas, diccionarios (UN/LOCODE, buques) y el modelo clásico en memoria; el LLM es externo |
| `reconcile` (asociación y reconciliación) | 2 | 0,5 vCPU | 1 GB | Acceso a la base de datos |
| `erp-sync` (sincronización del ERP) | 1 | 0,5 vCPU | 0,5 GB | Proceso programado |
| `api` (API y aplicación de revisión) | 2 | 1 vCPU | 1 GB | Usuarios del equipo de operaciones |
| **Total aplicación** | 13 procesos | **≈ 9 vCPU** | **≈ 15 GB** | |

Las colas se implementan sobre PostgreSQL (`SELECT … FOR UPDATE SKIP LOCKED`): con unas decenas de tareas por minuto no hace falta un servidor de colas aparte. Si D8 elige un servicio de colas gestionado, el cambio es un adaptador del puerto `TaskQueue`.

### 4.2 Máquinas

| Máquina | Cantidad | Tipo de referencia (Hetzner) | Recursos por máquina | Uso |
|---|---|---|---|---|
| Servidor de aplicación | 2 | CCX23 (vCPU dedicada) | 4 vCPU, 16 GB, 160 GB NVMe | Todos los roles en contenedores, repartidos entre las dos máquinas: si una cae, la otra sigue procesando |
| Servidor de base de datos | 2 | CCX13 (vCPU dedicada) | 2 vCPU, 8 GB, 80 GB NVMe | PostgreSQL principal y réplica en espera (alta disponibilidad y lecturas de la interfaz y la analítica) |
| Servidor de monitorización | 1 | CPX32 | 4 vCPU, 8 GB, 160 GB NVMe | Métricas, logs, trazas y alertas (§5 de la arquitectura) |
| Almacenamiento de objetos | 1 | Object Storage | 1 TB y 1 TB de tráfico de salida incluidos | Correos originales y adjuntos |

Notas de dimensionamiento:

- Se usan vCPU **dedicadas** en aplicación y base de datos para tener un rendimiento predecible; la monitorización puede ir en vCPU compartida.
- Los dos servidores de aplicación suman 8 vCPU y 32 GB frente a unos 9 vCPU y 15 GB solicitados: la CPU solicitada es una reserva, no un consumo (el consumo en el pico es inferior a 1,5 núcleos) y hay margen de memoria para picos de OCR.
- **Base de datos:** crece unos 10–25 GB al año con 100.000 correos (arquitectura §9.5); los 80 GB del disco local bastan para unos 3 años, y después se añade un volumen o se archivan particiones.
- **Almacenamiento de objetos:** 300 GB al año con 100.000 correos y 450 GB con 150.000; el terabyte incluido cubre entre 2 y 3 años. Después, unos 6,50 € por terabyte adicional al mes.
- **Copias de seguridad** de la base de datos en el almacenamiento de objetos, en otra ubicación del mismo proveedor.

### 4.3 GPU (solo si el LLM se autoaloja)

| Requisito | Valor | Por qué |
|---|---|---|
| Modelo | Abierto, de 4 a 8 mil millones de parámetros | Los de la PoC (`qwen3.5:4b`, `gemma4:e4b`, `llama3.2:3b`, D9) o uno algo mayor si la evaluación lo pide |
| Memoria de la GPU | 24 GB | Un modelo de 8 mil millones de parámetros ocupa unos 16 GB en 16 bits y unos 5 GB cuantizado a 4 bits; el resto queda para la caché de contexto de varias peticiones simultáneas |
| Rendimiento necesario | Unas 3–4 peticiones simultáneas y unos 1.500 tokens por segundo de lectura de entrada en el pico con 300.000 correos al mes (arquitectura §9.4) | Al alcance de una GPU de esta gama con un servidor de inferencia con agrupación de peticiones (por ejemplo, vLLM); se comprueba en F4.4 |
| Réplicas | 2 para alta disponibilidad, o 1 con la API como respaldo | — |
| Tipo de referencia | NVIDIA L4 de 24 GB (por ejemplo, Scaleway L4-1-24G en París a 0,75 € por hora) | ≈ 548 € al mes por GPU las 24 horas; ≈ 1.095 € con dos |

Con el LLM autoalojado, la GPU es la partida más cara de la infraestructura: entre 4 y 40 veces lo que cuesta la API en los escenarios de §3.3.

## 5. Coste técnico mensual

Precios de Hetzner sin IVA (C-08) y escenario de referencia del LLM (C-07: 1 $ = 0,90 €):

| Partida | 100.000 correos/mes | 150.000 correos/mes | 300.000 correos/mes |
|---|---|---|---|
| 2 servidores de aplicación (CCX23, 86,49 € cada uno) | 172,98 € | 172,98 € | 259,47 € (3 servidores) |
| 2 servidores de base de datos (CCX13, 43,49 € cada uno) | 86,98 € | 86,98 € | 86,98 € (tamaño mayor si hace falta) |
| 1 servidor de monitorización (CPX32) | 35,99 € | 35,99 € | 35,99 € |
| Almacenamiento de objetos (1 TB incluido) | 6,49 € | 6,49 € | 6,49 € a 12,96 € |
| **Infraestructura** | **≈ 302 €** | **≈ 302 €** | **≈ 395 €** |
| LLM (escenario de referencia) | ≈ 56 € (62 $) | ≈ 85 € (94 $) | ≈ 170 € (188 $) |
| **Total técnico** | **≈ 360 €** | **≈ 390 €** | **≈ 565 €** |
| **Por correo** | **≈ 0,36 céntimos** | **≈ 0,26 céntimos** | **≈ 0,19 céntimos** |
| Alternativa: LLM autoalojado (2 GPU L4) en lugar de la API | ≈ 1.400 € | ≈ 1.400 € | ≈ 1.490 € |

- La infraestructura es **casi fija**: el paso de 100.000 a 150.000 correos no cambia ninguna máquina, y el de 150.000 a 300.000 añade un servidor de aplicación. Solo el LLM crece de forma lineal.
- Con servicios gestionados de un proveedor de nube grande (base de datos, colas y monitorización gestionadas) la infraestructura cuesta más a cambio de menos operación; la elección se hace en D8 (#28). No cambia el dimensionamiento de §4.
- No incluye el IVA, la transferencia por encima de la incluida, las copias de seguridad fuera del proveedor ni el trabajo de operación.

## 6. Fuentes (consultadas el 23/11/2026)

| Fuente | URL |
|---|---|
| Anthropic: precios | <https://platform.claude.com/docs/en/about-claude/pricing> |
| Anthropic: residencia de datos | <https://platform.claude.com/docs/en/manage-claude/data-residency> |
| Anthropic: retención de datos de la API | <https://platform.claude.com/docs/en/manage-claude/api-and-data-retention> |
| OpenAI: precios | <https://developers.openai.com/api/docs/pricing> |
| Google: precios de la API de Gemini | <https://aistudio.google.com/docs/pricing> |
| Mistral: precios | <https://docs.mistral.ai/models/pricing> |
| Mistral: API por lotes | <https://docs.mistral.ai/capabilities/batch> |
| Hetzner: servidores en la nube (vCPU dedicada y compartida) | <https://www.hetzner.com/cloud/general-purpose/>, <https://www.hetzner.com/cloud/regular-performance/> |
| Hetzner: almacenamiento de objetos | <https://www.hetzner.com/storage/object-storage> |
| Scaleway: GPU (la página no admite lectura automática; el precio se tomó de su página oficial a través del buscador) | <https://www.scaleway.com/en/pricing/gpu> |

Los precios cambian con frecuencia; antes de contratar se vuelven a consultar.

## Historial

| Versión | Fecha | Cambios |
|---|---|---|
| 0.1.0 | 23/11/2026 | Primera versión: coste del LLM por proveedor y escenario con precios oficiales, requisitos de máquina por rol, máquinas de referencia y coste técnico mensual a 100.000, 150.000 y 300.000 correos |
