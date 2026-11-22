# ADR-0005: LLM local (Ollama) en la PoC y comparativa de proveedores de pago para producción

- **Estado:** Aceptado
- **Fecha:** 2026-11-21
- **Decisores:** Pablo Iglesias Peral
- **Referencias:** decisión D1, [ADR-0002](0002-proteccion-datos-confidenciales.md), apartados 4 y 7 del enunciado

## Contexto y problema

La PoC necesita un LLM para clasificar los correos y extraer el texto libre. Los datos son reales y confidenciales, y el enunciado obliga a declarar cualquier envío a servicios externos. La suscripción disponible (Claude Pro) no incluye acceso a la API, y los niveles gratuitos de las APIs comerciales suelen permitir el uso de los datos para entrenar sus modelos. Además, el enunciado pide justificar el modelo elegido y el coste para más de 100.000 correos.

## Factores de decisión

- Confidencialidad: ningún dato real fuera del equipo.
- Coste cero durante la prueba.
- Poder medir el rendimiento real (calidad, latencia, consumo) y no suponerlo.
- Una justificación sólida para producción, donde la calidad puede compensar el coste.

## Opciones consideradas

1. Ollama en local para la PoC, con comparativa documentada de proveedores de pago para producción.
2. API de pago (Claude) en la PoC, declarando el envío.
3. Niveles gratuitos de APIs comerciales (Gemini, Mistral, Groq).
4. Sin LLM: solo reglas y NLP clásico.

## Decisión

Opción elegida: **Ollama en local para la PoC**, junto con una **comparativa de uso y coste de proveedores de pago** que justifique la recomendación para producción.

**Criterios de eficiencia para el LLM local** (hardware: Apple M5, 16 GB de memoria unificada):
- **Cascada de coste**: las reglas y las plantillas resuelven primero lo determinista (identificadores, fechas, PDF de formato fijo). El LLM solo procesa lo que queda sin resolver.
- **Entrada mínima**: limpiar el cuerpo del correo (firmas, avisos legales, HTML, citas repetidas del hilo) antes de enviarlo, para reducir tokens y latencia.
- **Modelos pequeños y cuantizados**: entre 3 y 8B parámetros, en Q4 o Q5. Se elige uno por benchmark sobre el gold standard; se puede usar uno distinto para clasificar y para extraer.
- **Salida estructurada**: un esquema JSON impuesto (`format` de Ollama) y temperatura 0, para que la salida sea determinista y validable.
- **Contexto acotado**: un `num_ctx` ajustado al tamaño real de los correos limpios, y el modelo cargado entre llamadas (`keep_alive`).
- **Medición**: tokens por segundo, latencia por correo, memoria y acierto, registrados en cada ejecución.

**Comparativa para producción** (se elabora en F2 y se recalibra en F4): proveedores y modelos de varios niveles (por ejemplo, Anthropic, OpenAI, Google y Mistral, además de autoalojar modelos abiertos en GPU). Para cada uno se indica el precio por millón de tokens de entrada y de salida, el descuento por lotes y por caché, el coste estimado para 100.000 y 150.000 correos, la calidad esperada, la latencia, la residencia de los datos en la UE y la política de retención y de entrenamiento. Los precios se toman de fuentes oficiales, con su fecha de consulta.

## Consecuencias

- **Positivas:** riesgo cero de fuga; coste cero; métricas reales de un modelo abierto; un argumento sólido de que la arquitectura no depende de un proveedor (puerto `LLMClient`).
- **Negativas:** un modelo local pequeño acierta menos que los modelos de pago grandes, sobre todo en correos largos o ambiguos. La latencia en un portátil no es representativa de producción.
- **Riesgo asumido:** se documenta la diferencia de calidad esperada en lugar de medirla con un modelo de pago sobre los datos reales.
- **Seguimiento:** benchmark de modelos locales en F4; la comparativa se actualiza con las mediciones de tokens por correo de la PoC.

## Análisis de las opciones

### API de pago (Claude) en la PoC
- ✅ Máxima calidad de extracción.
- ❌ Coste y envío de datos reales a un tercero (se puede, pero hay que declararlo); no hay suscripción de API disponible.

### Niveles gratuitos de APIs comerciales
- ✅ Gratis y con buena calidad.
- ❌ Sus términos suelen permitir usar los datos para entrenar y la revisión humana: incompatible con la confidencialidad.

### Sin LLM
- ✅ Determinista y barato.
- ❌ No cubre bien el texto libre, la variedad de redacción ni los idiomas. Se usará como primer escalón de la cascada, no como solución única.
