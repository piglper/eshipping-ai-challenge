# ADR-0006: Modelo de eventos basado en el estándar DCSA

- **Estado:** Aceptado
- **Fecha:** 2026-11-22
- **Decisores:** Pablo Iglesias Peral
- **Referencias:** issues #11 y #12, [taxonomía y ambigüedades](../03_taxonomia_y_ambiguedades.md)

## Contexto y problema

El sistema tiene que guardar los hechos operativos que aparecen en los correos (salidas, llegadas, cargas, cut-offs, documentos, aduanas, incidencias) y compararlos con el ERP. El análisis de la muestra muestra que la mayor fuente de error es la **semántica de las fechas**: «ETA» se usa tanto para la llegada a destino como para la llegada del buque al puerto de carga, las previsiones y los hechos se mezclan, y una misma fecha cambia varias veces en un hilo. El ERP tampoco distingue entre fecha estimada y real.

Hay que decidir el vocabulario de eventos antes de diseñar el modelo de datos (F2.3), los extractores (F3) y la reconciliación.

## Factores de decisión

- Que elimine en el modelo la ambigüedad entre fecha planificada, estimada y real.
- Interoperabilidad: que en producción se puedan ingerir eventos de las API de las navieras sin traducciones ad hoc.
- Que se pueda explicar a los técnicos de EShipping y a los revisores sin un glosario propio.
- Que cubra lo que el estándar no cubre (aduanas españolas, incidencias).

## Opciones consideradas

1. Vocabulario propio basado en las columnas del ERP (`Salida`, `Llegada`, `F. Carga`…).
2. Vocabulario propio libre (una lista de eventos según la muestra).
3. Modelo de eventos de **DCSA** (Track & Trace), con extensiones propias marcadas.

## Decisión

Opción elegida: **3, modelo DCSA con extensiones**. Cada evento tiene un **tipo** (`DEPA`, `ARRI`, `STUF`, `GTIN`, `LOAD`, `DRFT`, `ISSU`…), un **clasificador** (`PLN`, `EST`, `ACT`), un lugar (UN/LOCODE) y, cuando aplica, el buque, el viaje y el contenedor. Las aduanas, las enmiendas de la reserva y las incidencias se modelan como extensiones propias, marcadas con un asterisco en la taxonomía.

La correspondencia con las columnas del ERP se define como una **proyección** (por ejemplo, `Llegada` ← último `ARRI` en POD), no como el modelo en sí.

## Consecuencias

- **Positivas:**
  - La diferencia entre ETD y ATD o entre ETA y ATA es un atributo, no una interpretación.
  - Las llegadas al puerto de carga y al de destino son el mismo tipo con distinto lugar, así que no se confunden.
  - En producción, los eventos de las API de las navieras entran sin traducción; los correos y las API alimentan el mismo modelo.
- **Negativas y riesgos asumidos:**
  - Es un vocabulario más rico que el ERP: la proyección al ERP tiene que mantenerse y probarse.
  - DCSA no cubre las aduanas ni las incidencias; las extensiones propias pueden diverger si el estándar las añade.
- **Seguimiento:** en F3 se comprueba que todos los campos del gold standard caben en el modelo sin forzarlo; si alguno no cabe, se amplía con un ADR nuevo.

## Análisis de las opciones

### Vocabulario basado en el ERP
- ✅ Correspondencia directa con lo que se compara.
- ❌ Hereda la ambigüedad del ERP (sin distinción entre estimada y real) y no tiene sitio para lo que el ERP no guarda (contenedores, cut-offs, B/L).

### Vocabulario libre
- ✅ Ajustado a la muestra.
- ❌ Sin referencia externa: hay que justificar y documentar cada término, y no sirve para integrar otras fuentes.

### Modelo DCSA
- ✅ Estándar del sector, publicado y abierto, que ya resuelve el problema del clasificador.
- ✅ Facilita integrar en el futuro las API de las navieras.
- ❌ Requiere extensiones para aduanas e incidencias.
