# Costes y comparativa de proveedores de LLM

| Campo | Valor |
|---|---|
| Versión | 0.1.0 |
| Estado | Borrador (se recalibra en F4.4 con las mediciones de la PoC) |
| Responsable | Pablo Iglesias Peral |
| Última actualización | 23/11/2026 |
| Tareas | F2.7 (#22), F2.7b (#23) |
| Decisiones | [ADR-0010](adr/0010-proveedor-de-llm-de-produccion.md) (D5b); se apoya en [ADR-0005](adr/0005-llm-local-ollama-en-la-poc.md) y [ADR-0008](adr/0008-estrategia-de-ia-cascada-por-etapa.md) |
| Fuentes | [Arquitectura §9](04_arquitectura.md#9-análisis-de-capacidad-f21b) (volúmenes y tokens), precios oficiales consultados el **23/11/2026** (§6) |

> **Confidencialidad:** sin datos reales. Todas las cifras de volumen son supuestos explícitos.

## 1. Resumen

- **Coste técnico total: del orden de 500 a 1.000 € al mes** con 100.000 correos y con 150.000, es decir, **menos de 1 céntimo por correo**. El LLM es una parte pequeña: entre 30 y 250 € al mes según el proveedor (§4).
- **El coste dominante es la revisión humana**: con el objetivo del 15 % de correos en revisión, unos 7.000 € al mes con 100.000 correos y 10.500 € con 150.000 (§3.4). Es más del 90 % del coste del sistema. La palanca de coste es **bajar el porcentaje en revisión** (aprendizaje continuo, F2.8), no el precio por token.
- **Con los precios actuales de los modelos pequeños, el proveedor de LLM se debe elegir por calidad y cumplimiento, no por precio**: la diferencia entre el más barato y el más caro de la lista corta es de unos 200 € al mes.
- **Residencia en la UE:** la API directa de Anthropic no ofrece hoy inferencia ni almacenamiento en la UE (solo `global` y `us`); para usar Claude con residencia en la UE hay que ir por **Amazon Bedrock o Google Cloud** con endpoint regional (prima del 10 %). OpenAI cobra un 10 % más por el procesamiento regional. Mistral es un proveedor europeo (§5).
- **Recomendación (ADR-0010):** elegir entre una lista corta de cuatro candidatos con residencia en la UE (Anthropic vía Bedrock o Google Cloud, Mistral, Google y OpenAI) mediante una prueba con el conjunto de referencia; escenario de referencia para los costes, Claude Haiku 5.5 en endpoint regional de la UE con escalado a Claude Sonnet 5.5; alternativa europea, Mistral Small 4 con escalado a Mistral Large 4; modelo autoalojado solo si EShipping no permite proveedores externos (P-10).
- **Sin cascada** (todo el correo a un modelo de gama media), el LLM costaría unos 2.600 $ al mes con 100.000 correos: unas 40 veces más que el escenario de referencia (§4.3). Aun así, el argumento principal de la cascada sigue siendo la fiabilidad y la auditabilidad ([ADR-0008](adr/0008-estrategia-de-ia-cascada-por-etapa.md)); el ahorro es secundario.

## 2. Supuestos

Además de los de la [arquitectura §9.1](04_arquitectura.md#91-parámetros) (volumen, 25 % de ruido, 50 % de correos operativos con LLM, tamaño de los correos):

| ID | Supuesto | Valor | Cómo se valida |
|---|---|---|---|
| C-01 | Llamadas al LLM al mes | 37.500 (100.000 correos) y 56.250 (150.000) | Porcentaje por escalón en la PoC (F4.3) |
| C-02 | Tokens por llamada | 3.000 de entrada (1.200 de instrucciones y esquema, fijos y cacheables; 1.800 del mensaje) y 400 de salida | Medición en la PoC (F4.4) |
| C-03 | Llamadas que escalan al modelo superior | 10 % | Medición en la PoC |
| C-04 | Diferencia de tokenizador | Los modelos Claude 4.7 y posteriores generan unos 30 % más tokens para el mismo texto, según Anthropic; se aplica ×1,3 a Claude. Para el resto se usa el recuento base (incertidumbre de ±30 %) | Recuento real por proveedor en la prueba (ADR-0010) |
| C-05 | Caché del prefijo fijo | Siempre activa en horario laboral (con 8 o más llamadas por minuto en el pico, la caché de 5 minutos se mantiene). Se ignora el coste de escritura en caché | — |
| C-06 | Residencia en la UE | Se aplica la prima regional publicada por cada proveedor cuando la hay | Contrato (P-10) |
| C-07 | Tipo de cambio | 1 $ = 0,90 € (solo para el total; los precios del LLM se dan en dólares, como los publica cada proveedor) | — |
| C-08 | Coste por hora de un operativo (coste de empresa) | 25 € | **Pregunta para EShipping** |
| C-09 | Tiempo medio por elemento revisado | 1,5 minutos | Medición en un piloto con la interfaz de revisión |

## 3. Coste mensual y por correo

### 3.1 Desglose

Escenario de referencia (ADR-0010), con residencia en la UE:

| Partida | 100.000 correos/mes | 150.000 correos/mes | Notas |
|---|---|---|---|
| LLM | ≈ 56 € (62 $) | ≈ 85 € (94 $) | Claude Haiku 5.5 + 10 % de escalado a Sonnet 5.5, endpoint regional de la UE (§4) |
| Cómputo (workers, API, sincronización del ERP) | 250–400 € | 250–400 € | Dos réplicas por rol por disponibilidad; la carga no obliga a más (arquitectura §9.3) |
| Base de datos PostgreSQL gestionada con alta disponibilidad | 150–300 € | 150–300 € | Instancia pequeña; crece unos 10–25 GB al año |
| Almacén de objetos | 5–20 € | 5–30 € | 25–38 GB nuevos al mes; niveles de archivo para lo antiguo |
| OCR | 0 € adicional | 0 € adicional | Tesseract dentro de los workers |
| Observabilidad | 50–150 € | 50–150 € | Métricas, logs y trazas |
| **Total técnico** | **≈ 510–925 €** | **≈ 540–965 €** | |
| **Por correo** | **≈ 0,5–0,9 céntimos** | **≈ 0,4–0,6 céntimos** | |
| Revisión humana (15 %, objetivo RNF-13) | ≈ 7.025 € (281 h) | ≈ 10.550 € (422 h) | §3.4 |
| **Total con revisión** | **≈ 7.500–8.000 €** | **≈ 11.100–11.500 €** | |
| **Por correo, con revisión** | **≈ 7,5–8 céntimos** | **≈ 7,4–7,7 céntimos** | |

Las partidas de infraestructura son **órdenes de magnitud** de servicios gestionados equivalentes en la UE, sin ofertas concretas; se precisan cuando se decida la plataforma (D8, #28). Su incertidumbre no cambia las conclusiones, porque la revisión humana es más de diez veces mayor.

### 3.2 Paso de 100.000 a 150.000 correos al mes

- El **LLM y la revisión crecen de forma lineal** (×1,5).
- La **infraestructura apenas cambia**: el mínimo de réplicas cubre los dos volúmenes (arquitectura §9.3); solo crecen el almacén de objetos y la base de datos.
- Por eso el coste técnico por correo **baja** al crecer, y el coste total por correo lo marca el porcentaje en revisión.

### 3.3 Sensibilidad

Variación del coste del LLM en el escenario de referencia con 100.000 correos al mes (base: 62 $):

| Cambio | Coste del LLM |
|---|---|
| Llega al LLM el 25 % de los correos operativos en lugar del 50 % | ≈ 31 $ |
| Llega al LLM el 100 % | ≈ 124 $ |
| El doble de tokens por llamada | ≈ 124 $ |
| Escalado del 30 % en lugar del 10 % | ≈ 145 $ |
| Todo lo anterior a la vez (100 %, el doble de tokens y un 30 % de escalado) | ≈ 580 $ |

Incluso en el peor caso combinado, el LLM sigue por debajo del 10 % del coste de la revisión humana.

### 3.4 Revisión humana

| Porcentaje en revisión | 100.000 correos/mes | 150.000 correos/mes |
|---|---|---|
| 30 % (arranque) | 562 h ≈ 14.050 € | 844 h ≈ 21.100 € |
| 15 % (objetivo RNF-13) | 281 h ≈ 7.025 € | 422 h ≈ 10.550 € |
| 8 % (régimen maduro) | 150 h ≈ 3.750 € | 225 h ≈ 5.625 € |

Horas calculadas en la [arquitectura §9.6](04_arquitectura.md#96-revisión-humana-el-cuello-de-botella-real), con C-08 y C-09.

**Comparación con la situación actual (ilustrativa).** Hoy el equipo de operaciones lee todos los correos para actualizar el ERP. Si se supone el mismo minuto y medio por correo operativo, 75.000 correos al mes son unas 1.875 horas, unos **47.000 € al mes**. El sistema no elimina ese trabajo, pero lo concentra en el 15 % de los casos que lo necesitan y deja trazado el resto. La cifra real depende de cómo trabaja hoy el equipo (P-06) y es la base del caso de negocio.

## 4. Comparativa de proveedores de LLM (F2.7b)

### 4.1 Precios oficiales

Precios en dólares por millón de tokens, tarifa estándar, consultados el **23/11/2026** en las páginas oficiales (§6).

| Proveedor | Modelo | Entrada | Entrada en caché | Salida | Lotes | Prima por residencia regional |
|---|---|---|---|---|---|---|
| Anthropic | Claude Haiku 5.5 (hasta 100.000 tokens de entrada) | 0,10 | 0,01 | 0,50 | −50 % | API directa: sin opción UE; Bedrock y Google Cloud regionales: +10 % |
| Anthropic | Claude Sonnet 5.5 | 2,00 | 0,10 | 10,00 | −50 % | Igual |
| OpenAI | GPT-5.4 nano | 0,20 | 0,02 | 1,25 | −50 % | +10 % (procesamiento regional) |
| OpenAI | GPT-5.4 mini | 0,75 | 0,075 | 4,50 | −50 % | +10 % |
| OpenAI | GPT-6.2 sol | 2,00 | 0,10 | 10,00 | −50 % | +10 % |
| Google | Gemini 3.5 Flash-Lite | 0,30 | 0,03 | 2,50 | −50 % | Regiones de la UE en Vertex AI |
| Google | Gemini 3.8 Flash (precio desde el 01/01/2027; hasta el 31/12/2026, 0,75 / 3,75) | 1,50 | 0,15 | 7,50 | −50 % | Igual |
| Mistral | Mistral Small 4 | 0,15 | 0,015 | 0,60 | −50 % | Proveedor europeo |
| Mistral | Mistral Large 4 | 0,70 | 0,07 | 2,10 | −50 % | Igual |
| Autoalojado | Modelo abierto de 4 a 8 mil millones de parámetros en una GPU NVIDIA L4 (Scaleway, París) | — | — | — | — | Infraestructura propia en la UE; 0,75 € por GPU y hora |

Se comparan dos gamas por proveedor: un modelo **pequeño** para el flujo normal y uno **intermedio** para el escalado ([ADR-0008](adr/0008-estrategia-de-ia-cascada-por-etapa.md), control 6). Los modelos de gama alta (por ejemplo, Claude Opus 5.5 a 4 / 20 $ o GPT-6.2 astra a 8 / 40 $) no se justifican para extracción con esquema y se dejan fuera.

### 4.2 Coste mensual del LLM por modelo

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

### 4.3 Escenarios

| Escenario (modelo principal + 10 % de escalado) | 100.000 correos/mes | 150.000 correos/mes |
|---|---|---|
| **Referencia:** Claude Haiku 5.5 + Claude Sonnet 5.5 (Bedrock o Google Cloud, región de la UE) | 62 $ | 94 $ |
| **Europeo:** Mistral Small 4 + Mistral Large 4 | 28 $ | 42 $ |
| Conservador: GPT-5.4 mini + GPT-6.2 sol | 165 $ | 248 $ |
| Conservador: Gemini 3.8 Flash (2027) + Claude Sonnet 5.5 | 262 $ | 393 $ |
| **Autoalojado:** 2 GPU L4 24 horas al día (alta disponibilidad) | ≈ 1.095 € | ≈ 1.095 € |
| Autoalojado: 1 GPU L4 en horario laboral (22 días × 12 h) + API de respaldo fuera de horario | ≈ 200 € + API | ≈ 200 € + API |
| **Sin cascada:** todo el correo (≈ 6.500 tokens de entrada y 500 de salida) a Claude Sonnet 5.5 | ≈ 2.574 $ | ≈ 3.861 $ |

Lecturas:

- Entre los escenarios con API, la diferencia es de unos 200 $ al mes como mucho: **el precio no decide**.
- El autoalojado con alta disponibilidad cuesta entre 4 y 40 veces más que la API a este volumen, según el escenario con el que se compare, y suma la operación de las GPU. Solo se justifica si los datos no pueden salir del entorno de EShipping (P-10) o como respaldo ante la caída de un proveedor.
- Los descuentos por lotes (−50 %) no se aplican al flujo normal por el plazo de RNF-03 (arquitectura §7.1); sí a los reprocesados y a las evaluaciones.

### 4.4 Criterios no económicos

| Criterio | Anthropic (API directa) | Anthropic en Bedrock o Google Cloud | OpenAI | Google (Vertex AI) | Mistral | Autoalojado |
|---|---|---|---|---|---|---|
| Residencia de la inferencia en la UE | No (solo `global` o `us`) | Sí, endpoint regional (+10 %); disponibilidad del modelo en región de la UE a confirmar | Sí, procesamiento regional (+10 %) | Sí, regiones de la UE | Proveedor europeo; región y contrato de tratamiento a confirmar | Sí, total |
| Uso de los datos para entrenar | No sin permiso expreso | Lo rige el proveedor de nube, que es el encargado del tratamiento | No verificado en esta consulta; se revisa en el contrato | Nivel de pago: «el contenido no se usa para mejorar los productos» | No verificado en esta consulta | No aplica |
| Retención | Sin retención del contenido por defecto (salvo los modelos de la gama Fable y Mythos); retención cero bajo acuerdo; la API por lotes retiene 29 días | Política del proveedor de nube | Se revisa en el contrato | Se revisa en el contrato | Se revisa en el contrato | Propia |
| Salida con esquema JSON | Sí | Sí | Sí | Sí | Sí | Sí, con el motor de inferencia |
| Calidad esperada en extracción en español e inglés | A medir | A medir | A medir | A medir | A medir | Menor (modelos de 4 a 8 mil millones de parámetros); se mide en la PoC (D9) |
| Dependencia | Un proveedor | Proveedor + nube | Un proveedor | Un proveedor | Un proveedor | Ninguna externa; operación propia |

La calidad **no se puede comparar con los datos reales** sin enviarlos a cada proveedor, y eso requiere autorización (CLAUDE.md, ADR-0005). Por eso el [ADR-0010](adr/0010-proveedor-de-llm-de-produccion.md) decide con una prueba sobre datos sintéticos y, si EShipping lo autoriza, sobre una muestra real con contrato de tratamiento.

## 5. Conclusiones para el diseño

1. El coste del sistema lo marca la **revisión humana**: las métricas que importan son el porcentaje en revisión y el tiempo por elemento, y la interfaz de revisión merece tanto cuidado como la extracción.
2. El LLM es barato con modelos pequeños: esto permite **ser prudente** (umbrales altos, escalado al modelo superior en caso de duda) sin un impacto apreciable en el coste.
3. La **residencia en la UE** condiciona más que el precio: con Claude implica ir por un proveedor de nube con endpoint regional.
4. El modelo de costes se recalcula en F4.4 (#42) con los tokens y el porcentaje por escalón medidos en la PoC.

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
| Scaleway: precios de GPU | <https://www.scaleway.com/en/pricing/gpu> |

Los precios cambian con frecuencia; antes de contratar se vuelven a consultar.

## Historial

| Versión | Fecha | Cambios |
|---|---|---|
| 0.1.0 | 23/11/2026 | Primera versión: supuestos, coste mensual y por correo a 100.000 y 150.000 correos, sensibilidad, revisión humana y comparativa de proveedores con precios oficiales |
