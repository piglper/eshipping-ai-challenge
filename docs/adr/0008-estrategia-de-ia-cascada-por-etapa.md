# ADR-0008: Estrategia de IA: cascada de técnicas por etapa, con el LLM acotado al texto libre

- **Estado:** Aceptado
- **Fecha:** 2026-11-23
- **Decisores:** Pablo Iglesias Peral
- **Referencias:** decisión D5, issue #19, [plan §7.1](../PLAN.md#71-selección-de-técnica-por-etapa), [arquitectura §6.1](../04_arquitectura.md#61-worker-de-clasificación-y-extracción), [análisis de datos](../01_analisis_datos.md), [ADR-0005](0005-llm-local-ollama-en-la-poc.md)

## Contexto y problema

El sistema tiene que clasificar los correos, extraer de ellos los datos operativos y cruzarlos con el ERP con una fiabilidad alta (RNF-10, RNF-11), un coste proporcional al volumen (RNF-20, RNF-21) y trazabilidad completa (RF-29, RNF-43). Hay que decidir **qué técnica se usa en cada etapa** y, en particular, **qué papel tiene el LLM**.

El plan propuso una cascada de técnicas (§7.1) antes de ver los datos. El análisis de la muestra (F1) permite ahora validarla con evidencia:

| Hallazgo de F1 | Implicación |
|---|---|
| El booking aparece en el asunto de 37 de 38 correos; el contenedor cumple ISO 6346 con dígito de control | La asociación y los identificadores se resuelven con reglas; un LLM puede alterar un dígito, una regla no |
| Los PDF de aduanas (levante, DUA, autorización de salida) siguen plantillas oficiales fijas; 20 de 23 PDF tienen capa de texto | Plantillas, sin LLM; OCR solo para una minoría |
| Las órdenes de transporte y los asuntos de la naviera son muy estructurados (`clave=valor`, patrones fijos) | Plantillas por proveedor |
| Los cambios de fecha, retrasos, roleos, opciones de buques y conflictos viven en texto libre, mezclando español e inglés, en hilos largos (mediana de 17.000 caracteres) | Aquí las reglas fallan y el LLM aporta valor (A-02, A-13, A-25) |
| Los cuatro errores claros del ERP de la muestra se detectan comparando campos con reglas | La reconciliación no necesita LLM |
| El gold standard tiene 38 correos | No hay datos para entrenar un modelo propio todavía |

## Factores de decisión

- **Fiabilidad**: precisión ≥ 98 % en los campos críticos aceptados automáticamente; nada de datos inventados.
- **Auditabilidad**: cada dato y cada veredicto se tiene que poder explicar (regla, plantilla o cita literal).
- **Coste**: que crezca lo menos posible con el volumen.
- **Mantenibilidad**: que un formato nuevo no obligue a reescribir reglas sin fin.
- **Arranque**: funcionar desde el primer día sin un histórico etiquetado.
- **Independencia del proveedor**: poder cambiar de modelo sin tocar el dominio.

## Opciones consideradas

1. **Todo con reglas**: expresiones regulares, plantillas y diccionarios para todo, sin modelos.
2. **Todo con LLM**: un prompt por correo completo que devuelve todos los campos y la clase.
3. **Cascada por etapa**: determinista → plantilla → ML clásico → LLM → persona; cada escalón solo recibe lo que el anterior no resuelve.
4. **Modelo propio ajustado** (por ejemplo, un modelo de reconocimiento de entidades o un modelo pequeño ajustado) entrenado para la extracción desde el inicio.

## Decisión

Opción elegida: **«Cascada por etapa»**, con el LLM limitado a lo que solo él resuelve bien y rodeado de controles deterministas.

### Técnica por etapa

| Etapa | Técnica principal | Respaldo | Papel del LLM | Evidencia de F1 |
|---|---|---|---|---|
| Parseo, desempaquetado y división de hilos | Parsers estándar y reglas de cabeceras citadas | — | Ninguno | Estructura de los `.msg` (análisis §2.1) |
| Limpieza (firmas, avisos legales, citas ya vistas) | Reglas y deduplicación por hash | — | Ninguno | ≈ 380 imágenes de firma; hilos de hasta 34 respuestas |
| Texto de PDF | Extracción de la capa de texto | OCR si no hay capa | Ninguno | 3 de 23 escaneados |
| Documentos oficiales y asuntos estructurados | Plantillas por tipo y proveedor (YAML) | LLM si el formato es desconocido; su salida validada sirve para crear la plantilla | Respaldo | Plantillas oficiales de aduanas; asuntos `clave=valor` |
| Identificadores y contenedores | Expresiones regulares con contexto e ISO 6346 completo | Validación contra el ERP | **Nunca** | A-18, A-27 |
| Fechas | Parser con formatos conocidos, perfil del remitente y zona por UN/LOCODE | LLM solo para expresiones relativas o ambiguas, siempre anclado a la fecha del mensaje | Solo casos ambiguos | A-05 a A-11 |
| Puertos y buques | Diccionarios (UN/LOCODE, buques del ERP y del histórico) con coincidencia aproximada | Revisión | Ninguno | — |
| Triaje (prioridad y ruido) | Reglas de asunto, remitente y palabras clave | — | **Nunca** (tiene que ser instantáneo y barato) | Taxonomía `OTR`, RNF-03 |
| Clasificación | Reglas → TF-IDF + regresión logística en cuanto haya correcciones suficientes | LLM si las anteriores no llegan al umbral | Respaldo | Taxonomía §2 |
| Texto libre: cambios, retrasos, roleos, opciones frente a reserva, clasificador `PLN`/`EST`/`ACT` | **LLM** con esquema JSON, solo los campos pendientes y con la cita literal | Persona | **Principal** | A-01, A-02, A-13, A-25 |
| Asociación correo → expediente | Claves deterministas en orden (booking, expediente, contenedor, B/L, referencias vistas) | Persona | **Nunca** | 37 de 38 por booking |
| Valor vigente y reconciliación con el ERP | Motor de reglas con jerarquía de fuentes y tolerancias (D6) | Persona | **Nunca** | Errores del ERP detectados con reglas |
| Conflictos y casos dudosos | Persona | — | Puede **sugerir** con su justificación; decide la persona | A-13, A-15 |

### Controles sobre el LLM

1. **Entrada mínima:** solo el mensaje nuevo ya limpio (y, si hace falta, el texto del adjunto), más la lista de campos pendientes. Nunca el hilo completo ya procesado ni las imágenes.
2. **Salida restringida:** esquema JSON impuesto por el proveedor o por el motor local, temperatura 0 y versión del prompt registrada.
3. **Evidencia verificable:** cada valor trae la cita literal de la que sale. El validador comprueba que la cita **existe en el texto de origen** y que el valor se deduce de ella (por ejemplo, la fecha aparece en la cita); si no, el valor se descarta. Es el control principal contra las alucinaciones.
4. **Validación de dominio:** las mismas reglas que al resto de escalones (fechas plausibles respecto al mensaje, puertos existentes, coherencia salida < llegada).
5. **Confianza no autodeclarada:** la confianza no es la que dice el modelo, sino una puntuación calibrada a partir de señales comprobables (cita verificada, acuerdo con los escalones deterministas, rol de la fuente, historial del remitente). La calibración se diseña en F2.6 (#21).
6. **Escalado de modelo:** se usa por defecto el modelo más barato que cumpla; solo si la validación falla o la confianza no llega al umbral, el caso pasa a un modelo superior o a una persona. El proveedor y los modelos de producción se eligen en la comparativa F2.7b (#23); los de la PoC, por benchmark (D9, #43).
7. **Evaluación antes de cambiar:** cualquier cambio de modelo o de prompt se evalúa contra el conjunto de referencia (gold standard y casos sintéticos de regresión) antes de desplegarse.

### Evolución: el LLM baja por la cascada

La cascada no es estática. Lo que el LLM resuelve y una persona valida se convierte con el tiempo en técnicas más baratas (F2.8, #24):

- Un formato de proveedor que llega a menudo al LLM pasa a tener **plantilla**.
- Las correcciones de clasificación entrenan el **modelo clásico**, que absorbe la clasificación del LLM.
- Cuando haya miles de ejemplos validados, se reevalúa la opción 4 (modelo propio ajustado) como sustituto del LLM externo en los campos más frecuentes.

El indicador de esta evolución es el **porcentaje resuelto en cada escalón** (RNF-21), que se mide desde la PoC (F4.3, #41) y debería bajar en el escalón LLM y en el humano con el tiempo.

## Consecuencias

- **Positivas:**
  - Los identificadores, la asociación y la reconciliación son deterministas y auditables; el LLM no puede provocar una asociación equivocada ni un veredicto inventado.
  - El coste del LLM depende de la fracción que llega a él, no del volumen total. Con las hipótesis de la arquitectura (§9.1), la cascada envía unos 112 millones de tokens de entrada al mes a 100.000 correos. Enviar cada correo completo a un LLM (opción 2) supondría del orden de 5 a 7 veces más tokens (correos de 17.000 caracteres de mediana y percentil 90 de 77.000, y el 100 % de los correos en lugar del 37,5 %). El cálculo en euros se hace en `06_costes.md` (#22).
  - Funciona desde el primer día: las reglas y las plantillas no necesitan entrenamiento, y el LLM cubre el texto libre sin datos etiquetados.
  - Cambiar de proveedor de LLM es cambiar un adaptador (`LLMClient`).
- **Negativas y riesgos asumidos:**
  - Hay que mantener reglas y plantillas. Se mitiga con plantillas como configuración, tests sintéticos por plantilla y el LLM como respaldo cuando una plantilla deja de encajar (el fallo se nota, no es silencioso).
  - Más piezas que en la opción 2: más componentes que probar y observar.
  - La calidad del LLM local de la PoC será menor que la de un modelo de pago; las métricas de la PoC serán una cota inferior.
- **Seguimiento:** en F4 se mide la precisión por campo y por escalón y el porcentaje que resuelve cada escalón. Si el escalón LLM resuelve mucho más o mucho menos del 50 % supuesto, se recalibran los costes y se revisa este ADR.

## Análisis de las opciones

### Todo con reglas
- ✅ Determinista, barato y explicable.
- ❌ El texto libre de los hilos (cambios de fecha, roleos, opciones de buques, mezcla de idiomas) no se cubre con reglas sin una explosión de casos imposible de mantener.
- ❌ Cada redacción nueva es un fallo silencioso: el dato simplemente no se extrae.

### Todo con LLM
- ✅ Lo más rápido de construir; cubre bien la variedad de redacción.
- ❌ Coste de 5 a 7 veces mayor en tokens y que crece con todo el volumen.
- ❌ Riesgo de alterar identificadores (un dígito del booking o del contenedor) o de inventar fechas; obliga a validar con reglas de todas formas.
- ❌ Menos auditable: una reconciliación hecha por el LLM no se puede explicar con una regla.
- ❌ Dependencia total de un proveedor y de su disponibilidad.

### Cascada por etapa
- ✅ Cada etapa usa la técnica más simple que cumple; el LLM solo donde aporta.
- ✅ Coste y revisión decrecientes con el aprendizaje.
- ✅ Deterministas los pasos donde un error es más caro (asociación y reconciliación).
- ❌ Más componentes y más configuración que mantener.

### Modelo propio ajustado
- ✅ A largo plazo puede ser el más barato y el más rápido, y no depende de un tercero.
- ❌ No hay datos etiquetados para entrenarlo (38 correos); necesita miles.
- ❌ Hay que mantener el ciclo de entrenamiento, evaluación y despliegue del modelo.
- ➡️ Se descarta ahora y se reevalúa cuando las correcciones acumuladas lo permitan.
