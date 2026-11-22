# Taxonomía de correos y eventos, y catálogo de ambigüedades

| Campo | Valor |
|---|---|
| Versión | 0.1.0 |
| Estado | Borrador |
| Responsable | Pablo Iglesias Peral |
| Última actualización | 22/11/2026 |
| Tareas | F1.5 (#12), F1.4 (#11) |
| Decisiones | [ADR-0006](adr/0006-modelo-de-eventos-basado-en-dcsa.md) |

> **Confidencialidad:** todos los ejemplos son **sintéticos** (identificadores, buques, fechas y lugares inventados). Las frecuencias son agregadas sobre los 38 correos de la muestra ([análisis](01_analisis_datos.md)).

## 1. Enfoque

La taxonomía tiene dos niveles independientes:

1. **Clase de correo** (§2): de qué trata un mensaje. Sirve para enrutar el mensaje al extractor adecuado y para priorizar. Es **multietiqueta**: un hilo largo puede tratar de transporte terrestre y de documentación a la vez.
2. **Evento** (§3): el hecho operativo que se extrae, con su fecha, su lugar y su estado. Es lo que se guarda en el expediente y se compara con el ERP.

Los eventos siguen el modelo del estándar **DCSA** (Digital Container Shipping Association), que usan las grandes navieras en sus API: cada evento tiene un **tipo** y un **clasificador** que dice si la fecha es **planificada, estimada o real**. Así se elimina en el modelo la confusión entre ETD/ATD o ETA/ATA (ver el [ADR-0006](adr/0006-modelo-de-eventos-basado-en-dcsa.md)).

## 2. Clases de correo

| Código | Clase | Emisor habitual | Señales para clasificar | Eventos que suele aportar | Técnica prevista |
|---|---|---|---|---|---|
| `BKG` | Reserva con la naviera: solicitud, confirmación, enmienda o cancelación | Naviera, interno | `BOOKING`, `AMENDMENT`, `AVISO BOOKING`, plataforma de reservas | Buque y viaje, ETD/ETA, cut-offs | Plantilla por naviera; LLM en hilos |
| `VSL` | Cambios en la planificación del buque: retraso, cambio de buque, omisión de escala, roleo | Naviera, interno | «retrasa su salida», «omite escala», «rolled», «nuevo barco» | Nuevas ETD/ETA, nuevo buque, `ROLL` | LLM con evidencia |
| `TRP` | Transporte terrestre: orden, programación y confirmación de la carga del contenedor | Transportista de acarreo | `ORDEN DE TRANSPORTE`, `RESERVA … TRANSPORTE`, «ventana de carga» | Recogida del vacío, carga en almacén, entrada en terminal, cut-off de entrega | Asunto con plantilla; cuerpo con reglas + LLM |
| `DOC` | Documentación: instrucciones de embarque, VGM, borrador y emisión del B/L | Naviera, cliente, interno | `SHIPPING INSTRUCTION`, `VGM`, `BL DRAFT`, `TELEX`, `SWB` | Envío de SI y VGM, B/L en borrador, emitido o liberado, cut-off documental | Asunto EDI con reglas; LLM en hilos |
| `CUS` | Aduanas: solicitud de despacho, DUA, levante, autorización de salida | Agente de aduanas, interno | `LEVANTE`, `Solicitud Despacho`, `DUA`, PDF oficial | Despacho solicitado, levante concedido, circuito de control | Plantilla sobre el PDF oficial |
| `INS` | Inspección y certificados | Agencia de inspección | `INSPECTION`, certificado en PDF | Inspección realizada | Reglas; LLM si hace falta |
| `COM` | Comercial: cotización, tarifa, condiciones | Cliente, interno | `COTIZACIÓN`, `TARIFA`, `OFERTA` | Ninguno operativo; datos de contexto (días libres, naviera prevista) | Solo clasificación |
| `FIN` | Facturación y costes: flete, demoras, estadías | Naviera, interno | `INVOICE`, `FACTURA`, `DEMURRAGE` | Ninguno de la línea temporal; posibles incidencias | Solo clasificación |
| `OTR` | Sin relación con un expediente: avisos, publicidad, notificaciones | Varios | Sin identificadores, remitentes masivos | Ninguno | Filtro barato al principio |

**En la muestra:** las clases `TRP`, `CUS` y `DOC` aparecen en casi todos los expedientes; `BKG` y `VSL` vienen sobre todo dentro de los hilos largos con el cliente o la naviera; `OTR` no aparece, porque la muestra se seleccionó a mano (en producción sí habrá ruido).

## 3. Eventos

### 3.1 Clasificador del evento

| Clasificador | Significado | Ejemplos en los correos |
|---|---|---|
| `PLN` (planificado) | Lo que dice el plan o la reserva | «ventana de carga del 07/09 al 10/09», horario de la naviera |
| `EST` (estimado) | Previsión actualizada | «ETD 19/09», «la nueva ETA está prevista para el 04/10» |
| `ACT` (real) | Ha ocurrido | «el contenedor se cargó ayer», «zarpó el 20/09», levante concedido |

Un mismo evento (por ejemplo, la salida del buque) puede tener varias versiones `PLN` y `EST` a lo largo del hilo y, como mucho, una `ACT`.

### 3.2 Catálogo de eventos

Los códigos entre paréntesis son los equivalentes en DCSA.

| Grupo | Evento | Código | Dónde se informa | Columna del ERP |
|---|---|---|---|---|
| **Transporte** (buque) | Salida del puerto de carga | `DEPA` en POL | `BKG`, `VSL` | `Salida` / `Fecha Dep.` (+ `SalidaOK`) |
| | Llegada al puerto de carga | `ARRI` en POL | `BKG`, `VSL` | — |
| | Llegada al puerto de destino | `ARRI` en POD | `BKG`, `VSL` | `Llegada` (+ `LlegadaOK`) |
| | Transbordo (salida y llegada en el puerto intermedio) | `DEPA`/`ARRI` en puerto T/S | `BKG`, `VSL` | — |
| **Equipo** (contenedor) | Recogida del contenedor vacío | `GTOT` vacío | `TRP` | — |
| | Carga de la mercancía en el almacén del cliente | `STUF` | `TRP` | `F. Carga`, `Lugar Recogida` |
| | Entrada del lleno en la terminal | `GTIN` | `TRP` | — |
| | Carga a bordo | `LOAD` | `BKG`, `DOC` | — |
| | Descarga en destino | `DISC` | `BKG` | — |
| **Envío** (documentos y reserva) | Reserva confirmada | `CONF` | `BKG` | `Booking`, `Buque` |
| | Reserva modificada (enmienda) | `AMND`* | `BKG` | `Booking`, `Buque` |
| | Instrucciones de embarque enviadas | `SUBM` (SI) | `DOC` | — |
| | VGM enviado | `SUBM` (VGM) | `DOC` | — |
| | B/L en borrador, emitido o liberado | `DRFT` / `ISSU` / `RELS` | `DOC` | `SWB / OBL Evento`, `Master` |
| **Aduanas** | Despacho solicitado | `CUS-REQ`* | `CUS` | — |
| | Levante concedido (con circuito verde, naranja o rojo) | `CUS-REL`* | `CUS` | `Despacho` |
| **Plazos** (cut-offs) | Documental | `DCO` | `BKG`, `TRP` | — |
| | VGM | `VCO` | `BKG`, `DOC` | — |
| | Entrega del contenedor lleno en terminal | `FCO` | `BKG`, `TRP` | — |
| **Incidencias** | Retraso | `DLAY`* | `VSL` | `Tipo Producto` (texto libre) |
| | Roleo (la carga pasa a otro buque) | `ROLL`* | `VSL` | `Tipo Producto` (texto libre) |
| | Cambio de buque u omisión de escala | `VCHG`* | `VSL` | `Buque` |
| | Inspección de la mercancía o del contenedor | `INSP` | `INS`, `CUS` | — |

\* Extensiones propias: DCSA no cubre como eventos las aduanas españolas, las enmiendas de la reserva ni las incidencias.

### 3.3 Atributos de cada evento extraído

| Atributo | Descripción |
|---|---|
| `type`, `classifier` | Tipo (§3.2) y `PLN`/`EST`/`ACT` |
| `event_time` | Fecha y hora normalizadas en ISO 8601 con zona |
| `time_precision` | `datetime`, `date`, `range` (con inicio y fin) o `approx` («sobre el 27») |
| `location` | UN/LOCODE (puerto o municipio) y texto original |
| `vessel`, `voyage` | Buque y viaje, si aplica |
| `equipment` | Contenedores (ISO 6346 validado) o número y tipo (`2x40HC`) |
| `source` | Mensaje (identificador, remitente, rol del remitente) y adjunto |
| `evidence` | Fragmento literal del que sale el dato |
| `known_at` | Cuándo se supo: fecha del mensaje que lo aporta, no la del correo que lo reenvía |
| `extractor`, `confidence` | Escalón que lo extrajo (regla, plantilla, ML, LLM, humano) y confianza calibrada |

`event_time` y `known_at` hacen el modelo **bitemporal**: se puede reconstruir qué sabía el sistema en cada momento, algo necesario para explicar una discrepancia y para auditar (F2.3).

## 4. Catálogo de ambigüedades (F1.4)

Cada ambigüedad tiene una regla de resolución **propuesta**. La política definitiva se fija en F2 (decisión D6).

### 4.1 Semántica de las fechas

| ID | Ambigüedad | Ejemplo sintético | Riesgo | Resolución propuesta |
|---|---|---|---|---|
| A-01 | **«ETA» de llegada al puerto de carga**, no de llegada a destino | «Barco NORDIC STAR eta prevista el 20/09, closing 17/09» | Discrepancia falsa contra `Llegada` del ERP | Determinar el puerto por contexto (cut-off cercano, POL mencionado, hilo con la naviera en origen). Si no se puede saber, `ARRI` con puerto desconocido y **no se cruza** con `Llegada` |
| A-02 | Estimada o real sin marcar | «Sale el 20/09» (¿plan o hecho?) | Dar por real una previsión | Tiempo verbal y vocabulario («zarpó», «sailed» → `ACT`; «prevista», «ETD» → `EST`). Si hay duda, `EST` |
| A-03 | El ERP no distingue estimada de real | `Salida` con `SalidaOK = NO` | Comparar una real con una estimada | Hipótesis: `SalidaOK`/`LlegadaOK` = `SI` indica fecha real. **Pregunta para EShipping** |
| A-04 | Varias «cargas» | Ventana de carga, carga programada, carga en almacén, carga a bordo | Comparar la carga en almacén con la carga a bordo | Eventos distintos (`STUF` frente a `LOAD`). `F. Carga` del ERP se compara con `STUF` |
| A-05 | Ventanas y rangos | «Ventana de carga del 07/09 al 10/09», «29/07 – 03/08» | Tomar el inicio como fecha | `time_precision = range`; un rango es `PLN` y no genera discrepancia si la fecha del ERP cae dentro |
| A-06 | Fechas aproximadas | «La ETA es sobre el 27/10» | Falsa precisión | `approx`, tolerancia de ±2 días en la comparación |

### 4.2 Formato de las fechas

| ID | Ambigüedad | Ejemplo sintético | Resolución propuesta |
|---|---|---|---|
| A-07 | Sin año | «el 11/09», «9-9» | Año que deje la fecha más cerca de la del mensaje, dentro de una ventana de −60 a +180 días |
| A-08 | Formatos y separadores mezclados | `26.08.2026`, `08-09`, `martes 08-09`, `2nd Sep` | Parser con orden día-mes por defecto (español); el día de la semana, si aparece, valida la fecha |
| A-09 | Día-mes frente a mes-día | `09/10` de una naviera con formato estadounidense | Día-mes por defecto; mes-día solo si el día > 12 o el remitente lo usa siempre (perfil por remitente) |
| A-10 | Relativas | «mañana», «el viernes», «la semana que viene» | Ancladas a la fecha del **mensaje citado**, no a la del reenvío |
| A-11 | Horas sin zona horaria | «closing 16/09 a las 10:00» | Hora local del puerto o municipio del evento (UN/LOCODE → zona); se guarda la zona inferida |

### 4.3 Hilos y fuentes

| ID | Ambigüedad | Ejemplo sintético | Resolución propuesta |
|---|---|---|---|
| A-12 | Valores sucesivos del mismo dato en un hilo | La ETD pasa del 15/09 al 18/09 y luego al 22/09 | Vale la versión con mayor `known_at`; las anteriores se guardan en el historial, no se borran |
| A-13 | Contradicciones abiertas | «¿ETD 22/09? Por teléfono nos dijisteis 18/09» | Pregunta sin respuesta → no se actualiza el dato; se marca como **en conflicto** y va a revisión |
| A-14 | Cita frente a mensaje nuevo | El dato está en la parte citada de una respuesta | Dividir el hilo; cada dato hereda el `known_at` del mensaje donde se escribió |
| A-15 | Fiabilidad según la fuente | El cliente dice una fecha y la naviera otra | Jerarquía por campo (por ejemplo, para salida y llegada: naviera > transitario > cliente). Se decide en F2.5 (D6) |
| A-16 | Reenvíos internos | Un compañero reenvía un aviso antiguo de la naviera | El rol de la fuente es el del autor original, no el de quien reenvía |

### 4.4 Identificadores y asociación

| ID | Ambigüedad | Ejemplo sintético | Resolución propuesta |
|---|---|---|---|
| A-17 | Expediente truncado | `Exp. ES1234` en lugar de `ES12345678` | Usar el booking del mismo asunto; el expediente truncado solo como confirmación por prefijo |
| A-18 | Booking confundible con otros números | `123456789` puede ser un pedido o un teléfono | Exigir contexto (`BKG`, `Booking:`, posición en el asunto) o que exista en el ERP |
| A-19 | Varios expedientes en un correo | Una naviera agrupa varios bookings | El correo se asocia a todos; cada evento solo al expediente cuyo identificador aparece en su contexto |
| A-20 | Cambio de booking | Una enmienda o un roleo genera un booking nuevo | Guardar los alias del expediente (booking anterior → nuevo) |
| A-21 | Espacios y formato en el ERP | Booking con espacio al final | Normalizar los dos lados antes de comparar |

### 4.5 Equipo y cantidades

| ID | Ambigüedad | Ejemplo sintético | Resolución propuesta |
|---|---|---|---|
| A-22 | Notaciones del tipo de contenedor | `40HC`, `40'HC`, `1x40´`, `M40HC`, `40 DH` | Tabla de equivalencias a ISO 6346 (código de tamaño y tipo, p. ej. `45G1`) |
| A-23 | El ERP solo tiene número de contenedores y TEU | `Cont = 1`, `TEUS = 2` | Comparar contra el número y tipo extraídos; regla de coherencia TEU = Σ(tamaño/20) |
| A-24 | Contenedores parciales en un correo | La orden de transporte cubre 2 de 5 contenedores | Acumular por contenedor (matrícula) a lo largo del expediente |

## 5. Ambigüedad residual: cuándo interviene una persona

Un dato va a **revisión humana** cuando:

- la confianza calibrada está por debajo del umbral de su campo (F2.6),
- hay un conflicto abierto (A-13) o fuentes del mismo rango que discrepan (A-15),
- el correo no se puede asociar a un expediente o se asocia a varios sin contexto (A-19),
- la discrepancia con el ERP afecta a un campo crítico (salida, llegada, cut-offs).

Cada corrección humana se guarda como un evento `ACT` de fuente `humano` y alimenta el aprendizaje continuo (F2.8).

## 6. Preguntas para EShipping (se completan en F1.7, #14)

1. ¿`SalidaOK` y `LlegadaOK` = `SI` significan que la fecha es real?
2. ¿`F. Carga` es la carga en el almacén del cliente o la entrada en terminal?
3. ¿Qué jerarquía de fuentes aplica hoy el equipo de operaciones cuando la naviera y el cliente dicen cosas distintas?
4. ¿Qué cut-offs importan más para la operación y con cuánta antelación hay que avisar?

## Historial

| Versión | Fecha | Cambios |
|---|---|---|
| 0.1.0 | 22/11/2026 | Taxonomía de correos y eventos (F1.5) y catálogo de ambigüedades A-01 a A-24 (F1.4) |
