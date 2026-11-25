# ADR-0015: Modelo local de la PoC: `qwen3.5:4b` por defecto

- **Estado:** Aceptado
- **Fecha:** 2026-11-25
- **Decisores:** Pablo Iglesias Peral
- **Referencias:** decisión D9, issue #43, [ADR-0005](0005-llm-local-ollama-en-la-poc.md), [ADR-0008](0008-estrategia-de-ia-cascada-por-etapa.md), [ADR-0010](0010-proveedor-de-llm-de-produccion.md), [evaluación §5.8](../11_evaluacion.md#58-comparativa-de-modelos-locales-f44b)

## Contexto y problema

La PoC ejecuta el escalón del LLM en local con Ollama (ADR-0005), en un Mac con 16 GB de memoria unificada. En la F0.10 se eligieron tres candidatos, los únicos de 3 a 8B parámetros de las familias recientes que caben en esa máquina: `llama3.2:3b`, `qwen3.5:4b` y `gemma4:e4b`. Hasta ahora el modelo por defecto era `llama3.2:3b`, de forma provisional. Hay que elegir uno con datos.

## Factores de decisión

- Calidad sobre el gold standard: lo que el LLM aporta al resultado final.
- Fiabilidad de las respuestas: un modelo que inventa citas depende por completo de que la validación no falle (ADR-0008, control 3).
- Eficiencia en la máquina de la PoC: memoria con margen para el resto del sistema y tiempo de procesado (ADR-0005).
- Robustez del formato: respuestas que se puedan interpretar sin fallos.

## Opciones consideradas

1. `llama3.2:3b`
2. `qwen3.5:4b`
3. `gemma4:e4b`

## Decisión

Opción elegida: **`qwen3.5:4b`** como modelo por defecto de la PoC (`--model`). `gemma4:e4b` queda como alternativa en máquinas con 24 GB o más. `llama3.2:3b` solo para máquinas con muy poca memoria.

Resultados sobre la muestra real (evaluación §5.8):

| | `llama3.2:3b` | `qwen3.5:4b` | `gemma4:e4b` |
|---|---|---|---|
| Propuestas que pasan la validación | 15 % | 39 % | 46 % |
| Valores vigentes del LLM, correctos / erróneos | 1 / 1 | 1 / 1 | 1 / 1 |
| Precisión de la extracción | 84,0 % | 85,1 % | 84,0 % |
| Memoria del modelo | 2,7 GB | 5,2–6,2 GB | 11 GB |
| Tiempo para 382 mensajes | ≈ 570 s | ≈ 350–440 s | ≈ 300 s |

En resultado final los tres empatan, y la diferencia de un valor no es significativa. La elección se apoya en el comportamiento:
- `qwen3.5:4b` propone poco y bien.
- `gemma4:e4b` es algo más preciso al proponer, pero ocupa el 70 % de la memoria de la máquina.
- `llama3.2:3b` inventa la mitad de sus citas.

## Consecuencias

- **Positivas:** el modelo por defecto deja margen de memoria y genera 3,5 veces menos tokens de salida que `llama3.2:3b`. Sus errores son de valor, que la validación detecta, y no citas inventadas.
- **Negativas y riesgos asumidos:**
  - Con cualquier modelo local, el escalón del LLM aporta muy poco en esta muestra: lo que queda después de las reglas es poco y difícil.
  - El benchmark usa la misma muestra que el resto de la evaluación (sesgo de selección). Se acepta porque la elección no depende de diferencias de resultado, que son nulas.
  - `qwen3.5:4b` no admite el esquema en `format` con Ollama 0.40, así que lo lleva en las instrucciones y gasta unos 150 tokens más por llamada.
- **Seguimiento:**
  - El modelo de producción es una API (ADR-0010) y se elige con este mismo procedimiento (`make evaluate-real MODEL=…`), con autorización para enviar datos.
  - Si aparece un modelo local nuevo que quepa en 16 GB, se compara igual.

## Análisis de las opciones

### `llama3.2:3b`
- ✅ El más ligero (2,7 GB) y el único que admite el esquema en `format`.
- ❌ El 85 % de sus propuestas no pasa la validación; la mitad cita texto que no existe. Es el más lento en total, porque genera mucho más texto.

### `qwen3.5:4b`
- ✅ Propone poco y bien, deja margen de memoria y tiene la mejor precisión de extracción, aunque por un margen no significativo.
- ❌ Esquema en las instrucciones y alguna llamada fallida (2 de 185).

### `gemma4:e4b`
- ✅ La mejor proporción de propuestas válidas y el más rápido.
- ❌ Ocupa 11 GB de 16. En una de cada seis llamadas respondía con la lista sin envolver, que ahora corrige el adaptador.
