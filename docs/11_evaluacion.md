# Evaluación de la PoC frente al gold standard

| Campo | Valor |
|---|---|
| Versión | 0.3.0 |
| Estado | Borrador |
| Responsable | Pablo Iglesias Peral |
| Última actualización | 25/11/2026 |
| Tarea | F4.2 (#40), F4.3 (#41) |
| Requisitos | RF-10, RF-20, RF-52, RNF-01, RNF-10, RNF-11 |
| Documentos relacionados | [01 §6](01_analisis_datos.md#6-gold-standard-f13) (gold standard), [07](07_fiabilidad.md) (qué se mide y por qué), [ADR-0009](adr/0009-politica-de-resolucion-de-discrepancias.md) (veredictos) |

> **Confidencialidad:** sin datos reales. De la muestra real solo se publican cifras agregadas; el informe con los fallos, que nombra expedientes, se queda en `data/output/` (ignorado por git).

## 1. Resumen

- La evaluación mide cuatro cosas: la **asociación** de cada correo a su expediente, su **clase**, el **valor de cada campo** y el **veredicto** frente al ERP. Cada proporción lleva su intervalo de confianza de Wilson al 95 %.
- Es reproducible con un comando: `make evaluate` sobre los datos sintéticos y `make evaluate-real` sobre la muestra real, solo en local.
- Sobre el conjunto sintético, la asociación, la extracción y los veredictos aciertan en todos los casos. La clase principal falla en 2 de 14 correos.
- **Cómo leer las cifras reales.** La muestra son 38 correos que EShipping seleccionó para dar contexto sobre su sistema actual; no es una muestra aleatoria del flujo. Las cifras sirven para ver **cómo se comporta** el sistema y **qué tipos de error** tiene. Las proporciones (por ejemplo, cuántos correos son internos o de la naviera) son de la muestra y no se extrapolan a los 100.000 correos al mes.
- Sobre la **muestra real**, solo con reglas y sin LLM:
  - **Asociación:** todo lo asociado de forma automática es correcto (35 de 35); 3 correos quedan sin asociar.
  - **Extracción:** precisión del 86 % y recall del 76 %. El booking y el levante aciertan siempre; el buque es el campo más débil (recall del 45 %).
  - **Veredictos:** el 74 % son exactos. Las discrepancias se detectan, pero ninguno de los 4 errores claros del ERP sale como `ERP_ERROR`.
  - **Clasificación:** la clase principal acierta en el 63 % de los correos. Antes de corregir la causa principal de error, hallada en el análisis, acertaba en el 47 %.

  El detalle está en la [sección 4](#4-resultados-sobre-la-muestra-real).
- **Análisis de errores** ([sección 5](#5-análisis-de-errores-f43)):
  - **Lo que más importa sale bien:** ninguna asociación automática es errónea.
  - **El 90 % de lo que se acepta sin revisión es correcto en esta muestra.** No basta para el 98 % de RNF-11. Los errores atribuibles ganan por la regla «el más reciente de los fiables».
  - **El fallo más frecuente no es de extracción:** en 8 casos el valor correcto se leyó, pero la proyección eligió otro.
  - **El LLM local pequeño (`llama3.2:3b`) apenas suma.** Con la regla nueva del ADR-0014 ya no empeora lo que resuelven las reglas: la precisión de la extracción pasa del 81,6 % al 84,0 %.
- **Dos decisiones salen del análisis:**
  - el rol del remitente se resuelve en cascada, sin dar de alta los dominios uno a uno ([ADR-0013](adr/0013-rol-del-remitente-en-cascada.md));
  - un valor del LLM rellena un hueco, pero no desplaza a un valor fiable de las reglas ([ADR-0014](adr/0014-el-llm-rellena-huecos-no-sustituye.md)).

## 2. Cómo se mide

### 2.1 Unidades y emparejamiento

| Unidad | Qué dice el gold | Qué se compara del sistema | Cómo se empareja |
|---|---|---|---|
| Correo | Expediente y clases (la primera es la principal) | Clases y asociaciones del mensaje propio del correo (profundidad 0 en su hilo) | Por el fichero contenedor, que lleva el número de expediente en el nombre, y por el orden del correo incrustado (`M1`, `M2`...). Los correos de ficheros sin expediente se emparejan, por orden, con el ruido del gold |
| Campo | El valor que dan los correos, su clasificador (`PLN`, `EST` o `ACT`) y su veredicto | El valor vigente según los correos (`field_state`), el clasificador de la observación ganadora y el veredicto vigente | Por expediente y campo. `cutoff` cubre los tres cut-offs y `equipment`, el número de contenedores |

Para emparejar, la ingesta guarda el origen de cada correo (`source_ref`) y el orden de los correos incrustados (`position`). Son dos campos del modelo de datos que en producción también sirven para trazar un correo hasta su fuente ([05 §2](05_modelo_datos.md)).

### 2.2 Cuándo un valor es correcto

| Campo | Regla |
|---|---|
| Booking | Igual sin separadores ni mayúsculas |
| Buque | Igual sin prefijo (`M/V`, `MV`...), mayúsculas ni espacios repetidos |
| Fechas (salida, llegada, carga, levante y cut-offs) | El mismo día, salvo la tolerancia que fije el gold (`date_tolerance_days`, hoy 0). Los rangos se comparan extremo a extremo, y un rango frente a una fecha suelta no coincide |
| Equipo | El mismo número de contenedores |

La hora, el lugar de carga, el tipo de equipo, los contenedores y los precintos del gold no se puntúan todavía: el sistema los extrae, pero no los proyecta como campo propio.

### 2.3 Métricas

| Métrica | Definición | Requisito |
|---|---|---|
| Precisión de la asociación automática | Correos con el expediente correcto entre los que el sistema asoció sin revisión | RNF-10 |
| Correos resueltos sin revisión | Correos con el expediente correcto (o el ruido sin asociar), sobre el total | Reverso de la carga de revisión |
| Exactitud de la clase principal, y precisión, recall y F1 por clase | Cada clase de cada correo cuenta, principal o secundaria | RF-10 |
| Precisión, recall y F1 por campo | Un valor correcto es un verdadero positivo. Un valor equivocado cuenta a la vez como falso positivo y falso negativo. Un valor que el gold no espera es un falso positivo. Los campos que el gold no menciona para un expediente no se puntúan | RF-20, RNF-11 |
| Acierto del clasificador | Sobre los valores correctos: si el dato es planificado, estimado o real | RNF-11 |
| Veredicto exacto y precisión, recall y F1 por veredicto | Matriz de confusión entre el veredicto del gold y el del sistema | RF-52 |
| Detección de lo que pide acción | Veredictos `ERP_ERROR`, `DISCREPANCY` y `ERP_MISSING`. Un acierto exige el veredicto exacto; una alarma sobre un `MATCH` es un falso positivo | RF-52 |

**Intervalo de Wilson al 95 %:** con muestras pequeñas, una proporción del 100 % no significa nada sin su intervalo. Con 38 correos sin ningún error, el límite inferior es del 90,8 %, como ya avanzaba [07 §6](07_fiabilidad.md#6-evaluación-en-la-poc-f4).

## 3. Resultados sobre el conjunto sintético

Cuatro expedientes y 14 correos inventados que siembran los siete veredictos (`make evaluate`, informe completo en `data_sample/build/evaluacion.md`). Este conjunto sirve para regresión: lo escribió quien escribió las reglas, así que **no estima la precisión real**.

| Métrica | Resultado |
|---|---|
| Precisión de la asociación automática | 13/13 = 100,0 % [77,2 % - 100,0 %] |
| Correos resueltos sin revisión | 14/14 = 100,0 % [78,5 % - 100,0 %] |
| Exactitud de la clase principal | 12/14 = 85,7 % [60,1 % - 96,0 %] |
| Precisión y recall de la extracción | 27/27 = 100,0 % [87,5 % - 100,0 %] |
| Veredicto exacto | 28/28 = 100,0 % [87,9 % - 100,0 %] |
| Detección de lo que pide acción (precisión y recall) | 6/6 = 100,0 % [61,0 % - 100,0 %] |

Los dos fallos de clase son avisos de buque (`VSL`) sin ninguna palabra del vocabulario de buque, que quedan como `OTR`. Antes de la corrección del §5.5 eran tres y salían como reserva (`BKG`).

## 4. Resultados sobre la muestra real

11 expedientes, 38 correos y 85 veredictos (`make evaluate-real`, 25/11/2026). Sin LLM: la cascada se detiene en las reglas.

**Rol de los remitentes.** Lo exigen las reglas de autoridad del ADR-0009. La primera ejecución trató a todos los remitentes como desconocidos (informativos): ningún valor ganó y la reconciliación dio 71 `MAIL_MISSING`. Darlos de alta uno a uno no escala a 100.000 correos al mes, así que el rol se resuelve en cascada ([ADR-0013](adr/0013-rol-del-remitente-en-cascada.md)):

1. el directorio curado del repositorio: el dominio propio de EShipping y un registro público de navieras;
2. las partes del expediente en el ERP;
3. por defecto, informativo.

La única configuración específica de la muestra es el dominio propio. Sale en local del remitente de los correos contenedores, que por construcción son de EShipping. De los 363 mensajes asociados, la cascada resuelve:
- **por el directorio:** 195 (180 internos y 15 de navieras);
- **por las partes del ERP:** 89 (11 agentes de aduanas y 78 clientes);
- **por defecto:** 79.

Ningún transportista coincide con el ERP. La coincidencia es estricta a propósito, y esos mensajes quedan como informativos: el error va hacia el lado seguro. Las métricas coinciden con las de un directorio provisional de los 20 dominios, preparado en una primera ejecución, sin escribir ninguno a mano.

### 4.1 Resumen

| Métrica | Resultado |
|---|---|
| Precisión de la asociación automática | 35/35 = 100,0 % [90,1 % - 100,0 %] |
| Correos resueltos sin revisión | 35/38 = 92,1 % [79,2 % - 97,3 %] |
| Exactitud de la clase principal | 24/38 = 63,2 % [47,3 % - 76,6 %] (antes del §5.5: 18/38 = 47,4 %) |
| Precisión de la extracción | 62/72 = 86,1 % [76,3 % - 92,3 %] |
| Recall de la extracción | 62/82 = 75,6 % [65,3 % - 83,6 %] |
| Veredicto exacto | 63/85 = 74,1 % [63,9 % - 82,2 %] |
| Precisión al detectar lo que pide acción | 11/18 = 61,1 % [38,6 % - 79,7 %] |
| Recall al detectar lo que pide acción | 11/16 = 68,8 % [44,4 % - 85,8 %] |

### 4.2 Extracción por campo

| Campo | Esperados | Dados | Aciertos | Precisión | Recall | Clasificador correcto |
|---|---|---|---|---|---|---|
| Booking | 11 | 11 | 11 | 100,0 % | 100,0 % | — |
| Buque | 11 | 7 | 5 | 71,4 % | 45,5 % | — |
| Salida del buque | 11 | 10 | 9 | 90,0 % | 81,8 % | 9/9 |
| Llegada a destino | 10 | 9 | 7 | 77,8 % | 70,0 % | 7/7 |
| Carga en almacén | 11 | 10 | 6 | 60,0 % | 54,5 % | 4/6 |
| Levante de aduana | 9 | 9 | 9 | 100,0 % | 100,0 % | 9/9 |
| Cut-off | 8 | 6 | 5 | 83,3 % | 62,5 % | 5/5 |
| Equipo (número de contenedores) | 11 | 10 | 10 | 100,0 % | 90,9 % | — |

### 4.3 Veredictos

| Veredicto | En el gold | Del sistema | Aciertos | Precisión | Recall |
|---|---|---|---|---|---|
| `MATCH` | 50 | 42 | 40 | 95,2 % | 80,0 % |
| `NOT_IN_ERP` | 8 | 5 | 5 | 100,0 % | 62,5 % |
| `ERP_NEWER` | 8 | 6 | 6 | 100,0 % | 75,0 % |
| `DISCREPANCY` | 7 | 13 | 6 | 46,2 % | 85,7 % |
| `ERP_MISSING` | 5 | 5 | 5 | 100,0 % | 100,0 % |
| `ERP_ERROR` | 4 | 0 | 0 | — | 0,0 % |
| `MAIL_MISSING` | 3 | 8 | 1 | 12,5 % | 33,3 % |
| Sin veredicto | 0 | 6 | 0 | — | — |

Por campo, el veredicto es exacto en todos los bookings (11/11) y en 10 de 11 levantes, pero solo en 4 de 11 buques.

### 4.4 Clasificación

La clase principal acierta en 24 de 38 correos (18 antes de la corrección del §5.5). Las aduanas se reconocen siempre (`CUS`: 11 de 11, sin falsos positivos), pero el transporte terrestre se queda corto (`TRP`: recall del 31,6 %) y el buque se asigna de más (`VSL`: precisión del 9,1 %).

### 4.5 Qué dicen estas cifras

- **Lo que más importa sale bien.** No hay ninguna asociación automática equivocada, y cuando el sistema afirma que un campo coincide con el ERP, acierta en el 95 % de los casos. Un error de asociación contamina un expediente ajeno sin que nadie lo note ([07 §2.2](07_fiabilidad.md#22-tipos-de-error-y-su-gravedad)).
- **Los fallos se concentran en tres sitios:** el nombre del buque, los errores claros del ERP (que salen como `DISCREPANCY`, de modo que se avisan, pero con un veredicto menos preciso) y la clasificación. La sección 5 explica dónde y por qué.
- **Las cifras son orientativas:** los intervalos son anchos y el gold está pendiente de revisión humana (§6).

## 5. Análisis de errores (F4.3)

Todo el análisis es automático, se hace en local y solo publica categorías y recuentos. El informe de `eshipping evaluate` incluye el diagnóstico (secciones «Diagnóstico»). Las causas finas del §5.2 y del §5.3 salen de comparar, en cada fallo, la observación ganadora con la correcta: regla, rol de la fuente, clasificador y fecha.

Los textos de los correos no se han leído para este análisis. Por eso, donde la explicación va más allá de esos datos, se indica como **hipótesis**, que habría que confirmar con una revisión humana de los casos.

### 5.1 Dónde se pierde cada valor

De los 82 valores que espera el gold (muestra real, solo reglas):

| Etapa | Valores | Qué significa |
|---|---|---|
| Acierto | 62 (75,6 %) | — |
| Leído, no elegido | 8 (9,8 %) | Alguna observación tenía el valor correcto, pero la **proyección** eligió otro o ninguno |
| Extraído mal | 6 (7,3 %) | Las reglas leyeron el campo, pero ninguna lectura es correcta |
| No extraído | 6 (7,3 %) | Ninguna observación del campo |
| De más | 1 | Un cut-off que el gold no recoge |

Por campo, el **buque** reparte sus 6 fallos entre las tres etapas (2 en cada una) y la **carga en almacén** falla sobre todo en la extracción (3 extraídos mal). El booking, el levante y el equipo están casi completos.

### 5.2 Por qué no se elige un valor leído

| Causa | Casos | Etapa responsable |
|---|---|---|
| El valor correcto solo lo dio una fuente informativa (un remitente que la cascada deja como cliente) y espera confirmación | 4 | Rol del remitente: un proveedor que no se reconoce (por ejemplo, un transportista que no coincide con el ERP), o un cliente que de verdad lo comunicó primero. Es el comportamiento previsto: lo informativo espera confirmación |
| Un mensaje interno posterior menciona otro buque u otra fecha, y gana por ser el más reciente entre fuentes fiables | 3 | La regla «el más reciente de los fiables». Hipótesis: el correo interno cita una alternativa o un dato antiguo, y la extracción lo toma por vigente |
| Un mensaje interno gana a una naviera más reciente en la carga en almacén | 1 | Autoridad por campo del ADR-0009 |

### 5.3 Errores aceptados sin revisión

Son los más graves ([07 §2.2](07_fiabilidad.md#22-tipos-de-error-y-su-gravedad)): **6 de 60 valores automáticos son erróneos**, así que lo automático acierta un 90,0 % [79,9 % - 95,3 %]. En los 4 casos que se pueden atribuir, ganó la regla «el más reciente de los fiables». En 3 de ellos la fuente era un **correo interno** (buque, salida y carga) y en 1 una naviera (un cut-off).

En esta muestra casi todo lo que se acepta sin revisión viene de correos internos, porque apenas tiene correos de navieras. En el flujo real no será así, y por eso **no se cambia la autoridad del correo interno con una regla fija**: con estos datos, la regla mandaría a revisión unos 29 valores correctos para atrapar 6 errores, pero esa proporción es de la muestra. La herramienta para decidirlo ya está diseñada: confianza calibrada por rol, campo y corroboración, con umbrales que se ajustan con la auditoría de producción ([07 §3 a §5](07_fiabilidad.md)).

Hipótesis sobre la causa: los correos internos reenvían, resumen y proponen alternativas a los clientes, y la extracción toma por vigente un dato que en el texto es una alternativa o un dato antiguo (A-25, A-16). Esto apunta más a la extracción (cambio 4 del §5.7) que a la autoridad.

### 5.4 Veredictos

De los 22 veredictos erróneos, **16 (73 %) vienen de un valor ya erróneo** y solo 6 de la propia reconciliación:

| Gold | Sistema | Casos | Causa |
|---|---|---|---|
| `ERP_ERROR` | `DISCREPANCY` | 2 | La regla B («error claro») solo reconoce erratas de dígitos y el cambio de día por mes. Hipótesis: estos errores son de otro tipo, así que se avisan como discrepancia sin atribuirla |
| `ERP_ERROR` | `MATCH` | 1 | El sistema da por iguales el valor de los correos y el del ERP. Hay que revisar si lo causa la tolerancia de la comparación o el gold |
| `ERP_NEWER` | `DISCREPANCY` | 1 | Hipótesis: sin la fecha de actualización de cada campo del ERP no se puede saber que es más reciente (pregunta para EShipping, [01 §6.4](01_analisis_datos.md#64-hallazgos-que-afectan-al-diseño)) |
| `MAIL_MISSING` | Sin veredicto | 2 | Campo sin columna en el ERP y sin valor en los correos: el sistema no emite veredicto. Es una diferencia de criterio con el gold, no un error |

### 5.5 Clasificación

La confusión más frecuente era **transporte clasificado como reserva** (9 de 20 fallos). En la muestra real, todo un hilo conserva en el asunto «BKG 12345678», y el asunto pesa el triple que el cuerpo. Así, cualquier respuesta (la orden al transportista, el levante...) sumaba puntos de reserva.

**Corrección aplicada:** la palabra que solo etiqueta el número de booking (`BKG`, `booking nº`) ya no cuenta; «Booking confirmation» sí. La clase principal real pasa del 47,4 % al 63,2 % y la sintética, del 78,6 % al 85,7 %, sin cambiar ninguna otra métrica.

Una advertencia: la regla se ha corregido mirando la misma muestra con la que se evalúa. Es una causa general, no un ajuste a un caso, pero la mejora hay que confirmarla con correos nuevos.

Quedan dos problemas:
- **Buque de más:** 4 reservas salen como `VSL`, porque palabras como «delay» aparecen también en correos de reserva.
- **Transporte de menos:** recall del 31,6 %. Los transportistas reales usan otro vocabulario.

Con 38 correos no compensa seguir afinando palabras: es el caso del escalón de ML de la cascada ([ADR-0008](adr/0008-estrategia-de-ia-cascada-por-etapa.md)), con un clasificador entrenado sobre correos etiquetados.

### 5.6 Porcentaje resuelto en cada escalón

Cada uno de los 82 valores esperados, según quién da el valor vigente:

| Escalón | Zona | Solo reglas | Con LLM (`llama3.2:3b`), antes del ADR-0014 | Con LLM, con el ADR-0014 |
|---|---|---|---|---|
| Reglas | automática, correcto | 54 (65,9 %) | 52 (63,4 %) | 54 (65,9 %) |
| Reglas | automática, **erróneo** | 6 (7,3 %) | 6 (7,3 %) | 6 (7,3 %) |
| Reglas | revisión, correcto | 8 (9,8 %) | 8 (9,8 %) | 8 (9,8 %) |
| Reglas | revisión, erróneo | 3 (3,7 %) | 3 (3,7 %) | 3 (3,7 %) |
| LLM | revisión, correcto | — | 2 (2,4 %) | 1 (1,2 %) |
| LLM | revisión, erróneo | — | 3 (3,7 %) | 1 (1,2 %) |
| Sin resolver (a una persona) | — | 11 (13,4 %) | 8 (9,8 %) | 9 (11,0 %) |
| Plantilla y ML | — | No implementados en la PoC | No implementados en la PoC | No implementados en la PoC |

- **Las reglas resuelven sin intervención humana dos tercios de los valores de la muestra.** El 75,6 % acaba correcto si una persona confirma la zona de revisión. Son proporciones de esta muestra, no la carga de revisión esperada en producción.
- **El escalón del LLM funciona como se diseñó, pero este modelo aporta poco:**
  - Se le pregunta 185 veces y propone valores que se validan; la mayoría de las lecturas se descartan, sobre todo porque la cita no está en el texto (228) o el valor no es válido.
  - Ningún valor del LLM entra sin revisión, porque tiene la confianza fija de su escalón.
  - **Antes del ADR-0014** desplazaba a valores correctos de las reglas: los «leídos, no elegidos» subían de 8 a 11 y la precisión de la extracción bajaba del 86,1 % al 81,6 %.
  - **Con el ADR-0014** solo rellena huecos: las reglas conservan sus 54 aciertos automáticos, la precisión queda en el 84,0 % y el veredicto exacto sube de 63 a 64 de 85. Lo que el LLM lee distinto de las reglas queda pendiente de confirmación, a la vista del operativo.

  La elección del modelo (F4.4b) y la recalibración de costes (F4.4) parten de estos datos: 77.015 tokens de entrada y 20.693 de salida, unos 560 s para los 382 mensajes y unos 400 MB de memoria del proceso en el Mac de la PoC.

### 5.7 Qué cambiar, por orden de impacto

| # | Cambio | Ataca | Estado |
|---|---|---|---|
| 1 | Calibrar la confianza por rol, campo y corroboración (¿lo confirma otra fuente?), y ajustar los umbrales con la auditoría de producción, en lugar de cambiar a mano la autoridad del correo interno | Errores aceptados sin revisión (§5.3) | Diseñado ([07 §3 a §5](07_fiabilidad.md)). No se ajusta con esta muestra: sus proporciones no son las del flujo |
| 2 | Resolver el rol del remitente en cascada, sin dar de alta dominios ([ADR-0013](adr/0013-rol-del-remitente-en-cascada.md)) | Escalabilidad del rol; «leídos, no elegidos» por fuente informativa (§5.2) | **Aplicado** (señales 1, 2 y 4). El perfil aprendido (señal 3) queda diseñado |
| 3 | Que un valor del LLM rellene huecos y no desplace a uno fiable de las reglas ([ADR-0014](adr/0014-el-llm-rellena-huecos-no-sustituye.md)) | Efecto lateral del LLM (§5.6) | **Aplicado** |
| 4 | Tratar las listas de buques alternativos y las menciones a datos antiguos (A-25, A-16) como contexto, no como valor | Buque extraído mal y errores automáticos de correos internos (§5.3) | Propuesto. Esfuerzo medio |
| 5 | Escalón de ML para la clasificación con correos etiquetados | Clasificación (§5.5) | Propuesto. Necesita datos etiquetados |
| 6 | Ampliar la regla B con el patrón de los errores del ERP que se vean en la auditoría | `ERP_ERROR` dado como `DISCREPANCY` | Propuesto, cuando haya casos |

Se han aplicado la corrección del §5.5 y los cambios 2 y 3, que son de diseño y no dependen de la muestra. El resto queda propuesto: con 11 expedientes elegidos para dar contexto, cualquier ajuste más fino sería ajustar la política a la muestra.

## 6. Limitaciones

- **Muestra pequeña.** 11 expedientes, 38 correos y 85 veredictos puntuables: los intervalos son anchos y ninguna cifra demuestra los objetivos de RNF-10 (99,5 %) ni de RNF-11 (98 %). Para eso hacen falta unos 765 y 190 casos sin errores ([07 §6.1](07_fiabilidad.md#61-qué-se-puede-demostrar-con-el-gold-standard)).
- **Gold provisional.** Lo etiquetó Claude Code y está pendiente de revisión humana (`meta.review`), con un solo etiquetador.
- **Un solo tipo de expediente** (exportación marítima FCL desde España).
- **Muestra elegida, no aleatoria.** EShipping la seleccionó para dar contexto. La mezcla de remitentes y de clases (por ejemplo, muchos correos internos y pocos de navieras) es de la muestra; por eso las cifras describen tipos de error y no se usan para calibrar umbrales ni para estimar la carga de revisión en producción.
- **Roles de remitente sin validar.** La cascada del ADR-0013 no tiene, en la muestra, ningún caso en que la parte del ERP coincida con un transportista; el perfil aprendido (señal 3) no está implementado.
- **El orden de los correos incrustados** es el del fichero. Si un mismo correo aparece en dos contenedores, se guarda una vez y cuenta en el primero; en el segundo queda sin emparejar y se cuenta como no encontrado.

## 7. Cómo reproducirlo

```bash
make evaluate                     # datos sintéticos -> data_sample/build/evaluacion.md
make evaluate-real                # muestra real, solo en local -> data/output/evaluacion/real.md
make evaluate-real MODEL=<modelo> # con el escalón del LLM (Ollama)
eshipping evaluate --gold <gold.json> --format json --verbose   # con los fallos, solo en local
```

`make evaluate-real` necesita los datos de la prueba en `data/` y un directorio de remitentes real en `data/config/senders.yaml`, todo ignorado por git.

## Historial

| Versión | Fecha | Cambios |
|---|---|---|
| 0.3.0 | 25/11/2026 | Las cifras reales describen comportamiento y tipos de error, no tasas de producción. Rol del remitente en cascada (ADR-0013), sin directorio manual; el LLM rellena huecos (ADR-0014). Cambios propuestos reordenados: la autoridad del correo interno pasa a calibración en producción |
| 0.2.0 | 25/11/2026 | Análisis de errores (F4.3): etapa que pierde cada valor, causas, errores aceptados sin revisión, veredictos, clasificación con su corrección, porcentaje resuelto en cada escalón con y sin LLM, y cambios propuestos |
| 0.1.0 | 25/11/2026 | Primera versión: metodología, métricas con intervalo de Wilson y resultados sobre el conjunto sintético y la muestra real, solo con reglas (F4.2) |
