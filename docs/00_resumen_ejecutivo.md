# Resumen ejecutivo

| Campo | Valor |
|---|---|
| Versión | 1.0.0 |
| Responsable | Pablo Iglesias Peral |
| Fecha | 25/11/2026 |
| Tarea | F5.1 (#45) |

> Sin datos reales de EShipping. Las cifras de la muestra real son agregadas.

**El problema.** Los correos de navieras, agentes, transportistas, clientes y del propio equipo dicen cosas distintas sobre el mismo expediente, y no siempre coinciden con el ERP. El sistema debe leerlos, saber a qué expediente pertenecen, decidir cuál es el dato vigente y avisar de lo que no cuadra con el ERP. Todo ello con un flujo de 100.000 correos al mes, que puede crecer a 150.000 o más.

**La propuesta.** Cada correo se convierte en **eventos del expediente con su evidencia** (modelo DCSA). Esos eventos se comparan con el ERP mediante reglas deterministas, y una persona valida las correcciones: **el sistema nunca escribe en el ERP por su cuenta.** [Arquitectura](04_arquitectura.md).

| Pregunta del enunciado | Respuesta |
|---|---|
| **Modelo de IA** | **Híbrido en cascada**: reglas, después plantillas, ML clásico, LLM y, al final, una persona. Cada escalón solo recibe lo que el anterior no resuelve. El LLM se limita al texto libre, con salida JSON validada y cita literal comprobada, y **nunca** decide la asociación ni la reconciliación. En la muestra, las reglas resuelven la mayor parte. El LLM local (`qwen3.5:4b`, elegido por benchmark) aporta poco, y su valor nunca desplaza a uno de las reglas. [ADR-0008](adr/0008-estrategia-de-ia-cascada-por-etapa.md), [ADR-0014](adr/0014-el-llm-rellena-huecos-no-sustituye.md), [ADR-0015](adr/0015-modelo-local-de-la-poc.md) |
| **Coste** | Medido en la PoC y recalibrado: unos **330 € al mes con 100.000 correos (0,33 céntimos por correo)** y unos **340 € con 150.000**. El 90 % son máquinas (dos de aplicación, dos de base de datos y una de monitorización). El LLM, con un proveedor de pago en la UE, cuesta unos 28 $ y 42 $ al mes. Con el peor caso de la sensibilidad, sigue costando menos que las máquinas. [Costes](06_costes.md) |
| **Datos y estructura** | Expediente, booking, B/L, contenedor (con dígito de control), buque y viaje, puertos (UN/LOCODE), salida y llegada, cut-offs, carga, levante y tipo de evento. Cada dato es un **evento con su estado** (planificado, estimado o real), la cita literal, el remitente y su rol, el escalón que lo extrajo y su confianza. La historia se conserva entera y el valor vigente se proyecta a partir de ella. [Modelo de datos](05_modelo_datos.md) |
| **Fiabilidad** | Se prioriza la precisión sobre la cobertura. **La precisión de lo automático es un objetivo que se impone** con umbrales por campo y auditoría por muestreo: 98 % en los campos críticos y 99,5 % en la asociación. Lo que se mide es qué parte se automatiza. En la muestra real, solo con reglas, **todas las asociaciones automáticas son correctas (35 de 35)** y lo aceptado sin revisión acierta el 90 %. Con los umbrales de producción, una parte más iría a revisión. Lo de baja confianza nunca se acepta solo: va a revisión con su evidencia y por prioridad. [Fiabilidad](07_fiabilidad.md), [Evaluación](11_evaluacion.md) |
| **Escalabilidad** | **Crecer es configuración y réplicas, no rediseño.** Prueba de volumen: 10.010 mensajes sintéticos en 66 s en un solo proceso, con coste lineal y la misma calidad. Eso da un margen de unas 195 veces sobre el pico de 150.000 correos al mes. Los límites reales son la revisión humana, el LLM, el OCR y la frescura del ERP. [Capacidad](04_arquitectura.md#9-análisis-de-capacidad-f21b) |
| **Aprendizaje continuo** | Cada corrección validada se convierte en algo más barato y fiable: calibración, ejemplos, plantillas, perfiles de remitente y alias. El trabajo **baja por la cascada**. Para **no aprender de errores**, las etiquetas pasan un control de calidad (doble revisión de una muestra, reglas de coherencia, cuarentena), el sistema nunca se entrena con sus propias salidas sin revisar y todo es reversible. [Aprendizaje](08_aprendizaje_continuo.md) |

**La ambigüedad entre fuentes** se resuelve con reglas explícitas y explicables ([ADR-0009](adr/0009-politica-de-resolucion-de-discrepancias.md)):
- **Autoridad por campo:** la naviera manda en el buque, el agente en el levante y el transportista en la carga.
- **Lo real manda sobre lo estimado.**
- **Entre fuentes fiables, gana la más reciente.**
- **Lo informativo espera confirmación.**
- **Dos fuentes de autoridad que discrepan casi a la vez van a revisión.**

El rol del remitente **no exige dar de alta los dominios**. Sale de una lista corta (dominios propios y navieras), de las partes del expediente que ya tiene el ERP y, en producción, de un perfil aprendido. Si no se sabe, el remitente es informativo, que es el lado seguro ([ADR-0013](adr/0013-rol-del-remitente-en-cascada.md)).

**Confidencialidad.**
- En la PoC todo es local: datos en `data/`, ignorado por git; LLM en Ollama; controles en el commit y en la CI; y la auditoría `make audit`.
- La auditoría encontró y se corrigió un incidente: un booking real en un test, eliminado también del historial ([seguridad §9](09_seguridad.md#9-en-la-poc-prueba-técnica)).
- En producción, el único servicio externo sería el LLM, en la UE, sin retención y con el texto seudonimizado ([ADR-0010](adr/0010-proveedor-de-llm-de-produccion.md)).

**La PoC** procesa los correos de la muestra y cualquier `.eml` o `.msg` nuevo: ingesta, clasificación, asociación, extracción, cruce con el ERP, discrepancias priorizadas y vista para operativos. Se prueba con `make demo`, `make ui` y `make volume` ([README](../README.md#cómo-probarlo)).

**Límites y siguientes pasos.**
- La muestra (38 correos y 11 expedientes) la eligió EShipping para dar contexto. Sus cifras describen comportamiento y tipos de error, no tasas de producción.
- El gold standard está pendiente de revisión humana.
- Para demostrar los objetivos hace falta un **piloto** con unos cientos de casos etiquetados.
- Antes del piloto conviene responder las [preguntas a EShipping](02_requisitos.md#5-preguntas-para-eshipping), sobre todo la autorización de un LLM externo y el acceso al ERP.
