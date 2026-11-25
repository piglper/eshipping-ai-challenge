# ADR-0014: Un valor del LLM rellena un hueco, pero no desplaza a un valor fiable de las reglas

- **Estado:** Aceptado
- **Fecha:** 2026-11-25
- **Decisores:** Pablo Iglesias Peral
- **Referencias:** issue #41, PR #86, [ADR-0008](0008-estrategia-de-ia-cascada-por-etapa.md), [ADR-0009 §3](0009-politica-de-resolucion-de-discrepancias.md#3-valor-vigente-de-un-campo-según-los-correos) (lo amplía), [evaluación §5.6](../11_evaluacion.md)

## Contexto y problema

En la cascada (ADR-0008), al LLM se le pregunta por los campos que las reglas no encontraron en **un mensaje**. Pero el expediente puede tener ya ese campo, leído por las reglas en otro mensaje. Con la regla de frescura del ADR-0009 §3, un valor del LLM más reciente desplaza al de las reglas aunque sea menos fiable.

En la muestra real, con `llama3.2:3b`, los valores «leídos bien, pero no elegidos» suben de 8 a 11, y la precisión de la extracción baja del 86,1 % al 81,6 %.

## Factores de decisión

- Fiabilidad: el LLM es el escalón menos explicable y con más errores de la cascada.
- No perder información: si el LLM lee una actualización real que las reglas no vieron, alguien tiene que verla.
- Coste: no hay que preguntar más al LLM para corregir esto.

## Opciones consideradas

1. Mantener la frescura sin distinguir escalones (ADR-0009 §3 tal cual).
2. No preguntar al LLM por los campos que el expediente ya tiene.
3. Preguntar igual, pero en la proyección el valor del LLM solo rellena huecos: si discrepa de un valor fiable de las reglas, queda **pendiente de confirmación**.

## Decisión

Opción elegida: **«El LLM rellena huecos»** (opción 3). Se añade una regla al ADR-0009 §3: entre las fuentes fiables (rango A o B), un valor del escalón LLM solo entra en la competición por la frescura si **ninguna** regla ha dado un valor fiable para ese campo. Si lo ha dado y el del LLM es distinto, el del LLM se registra como pendiente de confirmación, igual que el de una fuente informativa (regla 4), y el operativo lo ve en la revisión.

La opción 2 se descarta porque el LLM dejaría de ver las actualizaciones que las reglas no leen, que son justo el texto libre para el que existe ese escalón.

## Consecuencias

- **Positivas:** el LLM ya no empeora lo que las reglas resuelven bien. Lo que lee de nuevo no se pierde: queda a la vista para confirmar. No cambia el número de llamadas. En la muestra real, con `llama3.2:3b`, las reglas conservan sus 54 aciertos automáticos, la precisión de la extracción sube del 81,6 % al 84,0 % y el veredicto exacto, de 63 a 64 de 85 (evaluación §5.6).
- **Negativas y riesgos asumidos:** una actualización real que solo lee el LLM no se aplica sola; espera a que una persona la confirme. Es coherente con dar prioridad a la precisión sobre la cobertura (`07 §1`).
- **Seguimiento:** la evaluación cuenta los valores pendientes que venían del LLM y cuántos eran correctos. Si con un modelo mejor (F4.4b, ADR-0010) lo pendiente del LLM resulta casi siempre correcto, se puede dar al LLM una confianza calibrada por campo (`07 §3`) en lugar de esta regla fija.

## Análisis de las opciones

### Frescura sin distinguir escalones
- ✅ Una regla menos.
- ❌ El escalón menos fiable desplaza al más fiable solo por llegar después.

### No preguntar por los campos que el expediente ya tiene
- ✅ Menos llamadas.
- ❌ El LLM no ve las actualizaciones en texto libre, que son su razón de ser.

### El LLM rellena huecos
- ✅ No empeora lo que hacen las reglas y no pierde lo que lee el LLM.
- ❌ Sus actualizaciones esperan confirmación.
