# ADR-0010: Proveedor de LLM de producción: lista corta con residencia en la UE y elección por evaluación

- **Estado:** Aceptado
- **Fecha:** 2026-11-23
- **Decisores:** Pablo Iglesias Peral
- **Referencias:** decisión D5b, issues #22 y #23, [costes y comparativa](../06_costes.md), [ADR-0005](0005-llm-local-ollama-en-la-poc.md), [ADR-0008](0008-estrategia-de-ia-cascada-por-etapa.md)

## Contexto y problema

El [ADR-0008](0008-estrategia-de-ia-cascada-por-etapa.md) limita el LLM al texto libre, con un modelo pequeño por defecto y escalado a uno superior en caso de duda. Falta decidir **qué proveedor y qué modelos** se usan en producción. La PoC usa un modelo local ([ADR-0005](0005-llm-local-ollama-en-la-poc.md)) y no puede medir la calidad de los modelos de pago con los datos reales sin enviarlos fuera, algo que requiere autorización.

La comparativa de [costes §4](../06_costes.md#4-comparativa-de-proveedores-de-llm-f27b) muestra que:

- con modelos pequeños, el LLM cuesta entre 20 y 260 $ al mes con 100.000 correos, frente a unos 7.000 € de revisión humana;
- la API directa de Anthropic no ofrece hoy residencia en la UE (solo `global` y `us`); Claude con residencia en la UE pasa por Amazon Bedrock o Google Cloud con endpoint regional (+10 %);
- OpenAI cobra un 10 % por el procesamiento regional, Google ofrece regiones de la UE en Vertex AI y Mistral es un proveedor europeo.

## Factores de decisión

- **Cumplimiento:** residencia en la UE, contrato de tratamiento de datos, sin uso de los datos para entrenar y retención mínima (RNF-30, RNF-31, S-10).
- **Calidad** de extracción con esquema JSON en correos en español e inglés mezclados (RNF-11).
- **Coste**, secundario a este volumen.
- **Independencia:** poder cambiar de proveedor (puerto `LLMClient`) y tener un respaldo si uno falla.
- **Operación:** latencia compatible con RNF-03 y límites de uso suficientes (unos 90.000 tokens por minuto en el pico con 300.000 correos al mes, arquitectura §9.4).

## Opciones consideradas

1. **Elegir ya un único proveedor por precio** (el más barato de la comparativa).
2. **Elegir ya un único proveedor por reputación de calidad** (un modelo de gama media o alta para todo).
3. **Lista corta con residencia en la UE, elección por evaluación** sobre un conjunto de referencia, con un escenario de referencia para los costes y un respaldo.
4. **Modelo autoalojado** en GPU propia o alquilada en la UE.

## Decisión

Opción elegida: **«Lista corta con residencia en la UE y elección por evaluación»**.

**Lista corta** (modelo pequeño para el flujo normal + modelo intermedio para el escalado):

| Candidato | Pequeño | Escalado | Vía con residencia en la UE |
|---|---|---|---|
| A (escenario de referencia para los costes) | Claude Haiku 5.5 | Claude Sonnet 5.5 | Amazon Bedrock o Google Cloud, endpoint regional de la UE |
| B (proveedor europeo) | Mistral Small 4 | Mistral Large 4 | API de Mistral con región de la UE |
| C | Gemini 3.5 Flash-Lite | Gemini 3.8 Flash | Vertex AI, región de la UE |
| D | GPT-5.4 nano | GPT-5.4 mini | API de OpenAI con procesamiento regional en la UE (+10 %) |

Añadir otro candidato a la evaluación no cambia nada más del sistema.

**Procedimiento de evaluación** (antes de producción):

1. Conjunto de referencia: casos sintéticos de `data_sample/` y de regresión, y, **solo con autorización de EShipping y contrato de tratamiento firmado**, una muestra real seudonimizada.
2. Métricas: precisión y recall por campo, tasa de citas no verificadas (alucinaciones), tasa de escalado, latencia p95 y tokens reales por llamada (cada proveedor tiene su tokenizador).
3. Criterio: se elige el candidato que cumple RNF-11 con **menor tasa de revisión**; el coste solo desempata.
4. El resultado se registra en un ADR nuevo que concreta este.

**Respaldo:** la pasarela de LLM se configura con un segundo candidato de la lista como proveedor de respaldo (arquitectura §7.3). Si EShipping no permite proveedores externos (P-10), se usa el **modelo autoalojado** con el mismo puerto y los mismos controles, asumiendo su coste (unos 1.100 € al mes con alta disponibilidad) y una calidad menor, medida en la PoC (D9, #43).

**Configuración común a cualquier proveedor:** salida con esquema JSON, prefijo fijo (instrucciones y esquema) en caché, sin API por lotes en el flujo normal, contrato de tratamiento con cláusula de no entrenamiento y retención mínima, y registro de tokens y coste por llamada.

## Consecuencias

- **Positivas:**
  - La decisión se basa en la calidad medida y en el cumplimiento, que son lo que de verdad cambia el coste total (a través del porcentaje en revisión).
  - Los cuatro candidatos tienen una vía con residencia en la UE.
  - Cambiar de candidato es configuración del adaptador; el resto del sistema no cambia.
- **Negativas y riesgos asumidos:**
  - La elección final queda pendiente de una evaluación que necesita datos sintéticos de calidad y, para ser concluyente, una muestra real autorizada.
  - La disponibilidad de cada modelo concreto en una región de la UE se tiene que confirmar al contratar; si un modelo no está disponible en la UE, el candidato cambia de modelo o sale de la lista.
  - Los precios pueden cambiar (por ejemplo, Gemini 3.8 Flash dobla su precio el 01/01/2027); se usan los precios ya anunciados y el modelo de costes se revisa cada trimestre.
- **Seguimiento:** recalibrar los costes con los tokens medidos en la PoC (F4.4, #42); repetir la evaluación cuando salga un modelo nuevo de la lista corta o cambie un precio relevante.

## Análisis de las opciones

### Un único proveedor por precio
- ✅ Simple.
- ❌ El ahorro es de unos 200 $ al mes como mucho; una calidad un punto menor cuesta más en horas de revisión que todo el LLM.

### Un único proveedor por reputación de calidad
- ✅ Probablemente la mejor calidad.
- ❌ Sin medir, es una suposición; un modelo intermedio para todo multiplica el coste del LLM por 7 a 15 sin saber si hace falta.

### Lista corta y evaluación
- ✅ Decide con datos y con el cumplimiento como filtro previo.
- ✅ Deja preparado el respaldo.
- ❌ Requiere una evaluación antes de producción.

### Autoalojado
- ✅ Los datos no salen del entorno; sin dependencia de un proveedor.
- ❌ Entre 4 y 40 veces más caro que la API a este volumen, más la operación de las GPU.
- ❌ Calidad menor con los modelos que caben en una GPU de este tamaño.
- ➡️ Se mantiene como contingencia (P-10) y como respaldo.
