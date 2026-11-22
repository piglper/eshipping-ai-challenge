# Requisitos, supuestos y preguntas

| Campo | Valor |
|---|---|
| Versión | 0.1.0 |
| Estado | Borrador |
| Responsable | Pablo Iglesias Peral |
| Última actualización | 22/11/2026 |
| Tareas | F1.6 (#13), F1.7 (#14) |
| Fuentes | Enunciado (apartados 1, 5–8 y 10), [análisis de datos](01_analisis_datos.md), [taxonomía y ambigüedades](03_taxonomia_y_ambiguedades.md) |

> **Confidencialidad:** sin datos reales. Las cifras de la muestra son agregadas.

## 1. Cómo leer este documento

- **Identificadores**: `RF-xx` (funcional), `RNF-xx` (no funcional), `S-xx` (supuesto) y `P-xx` (pregunta). Son estables: si un requisito cambia, se modifica su texto y se anota en el historial; no se renumera.
- **Prioridad** (MoSCoW): **M** imprescindible, **S** importante, **C** deseable, **W** fuera de alcance por ahora.
- **PoC**: ✅ se implementa, 🟡 se implementa de forma simplificada o simulada, 📐 solo se diseña.
- **Origen**: apartado del enunciado (`E5.3` = apartado 5, punto 3) o hallazgo del análisis (`A-xx`, ambigüedad del catálogo).
- Cada requisito tiene un **criterio de aceptación** verificable; en la PoC se comprueba con tests (datos sintéticos) o con la evaluación frente al gold standard (F4).

## 2. Requisitos funcionales

### 2.1 Ingesta (E5.1)

| ID | Requisito | Prioridad | PoC | Criterio de aceptación | Origen |
|---|---|---|---|---|---|
| RF-01 | Ingerir correos en `.msg` y `.eml`, con cuerpo HTML o texto y con adjuntos | M | ✅ | Los 11 `.msg` de la muestra y un `.eml` sintético se ingieren sin errores; se conservan cabeceras, cuerpo y adjuntos | E5.1 |
| RF-02 | Desempaquetar correos incrustados (adjuntos `.msg`/`message/rfc822`) y tratar cada uno como un correo independiente | M | ✅ | Los 38 correos incrustados de la muestra aparecen como correos independientes, con su remitente y fecha originales | Análisis §2.1 |
| RF-03 | Dividir cada hilo en mensajes y fechar cada uno con su propia cabecera | M | ✅ | En los hilos del gold standard, cada dato se atribuye al mensaje que lo escribió (`known_at`) | A-14 |
| RF-04 | Eliminar firmas, avisos legales, imágenes de firma y texto citado repetido antes de extraer | M | ✅ | Ninguna imagen de firma llega a la extracción; el texto que llega al LLM se reduce de forma medible (se informa del porcentaje) | Análisis §2.1 |
| RF-05 | Extraer el texto de los PDF adjuntos y aplicar OCR solo a los que no tienen capa de texto | M | 🟡 | Los PDF con texto se procesan; los escaneados se detectan y se marcan (OCR en la PoC solo si da tiempo) | E1, Análisis §2.4 |
| RF-06 | Ingesta idempotente: el mismo correo procesado dos veces no duplica datos | M | ✅ | Reprocesar la muestra no cambia el número de correos ni de eventos | RNF-04 |
| RF-07 | Ingerir de forma continua desde el buzón corporativo y desde fuentes estructuradas (API y webs de las navieras) | S | 📐 | Diseño con adaptadores de buzón (Microsoft Graph o IMAP) y de API de navieras (DCSA Track & Trace) | E1, ADR-0006 |

### 2.2 Clasificación (E5.2)

| ID | Requisito | Prioridad | PoC | Criterio de aceptación | Origen |
|---|---|---|---|---|---|
| RF-10 | Clasificar cada correo en las clases de la taxonomía (multietiqueta), con una clase principal | M | ✅ | Exactitud de la clase principal y F1 por clase medidas frente al gold standard | E5.2, taxonomía §2 |
| RF-11 | Detectar el tipo de evento o cambio comunicado: confirmación, retraso, cambio de buque, omisión de escala, roleo, transbordo, enmienda | M | ✅ | Los eventos de incidencia del gold standard se detectan; recall medido | E5.2, E6 |
| RF-12 | Filtrar los correos sin relación con un expediente al principio del pipeline, con un coste mínimo | S | ✅ | Un correo sintético de publicidad se descarta sin llegar al LLM | Taxonomía `OTR` |

### 2.3 Extracción (E5.3, E6)

| ID | Requisito | Prioridad | PoC | Criterio de aceptación | Origen |
|---|---|---|---|---|---|
| RF-20 | Extraer identificadores: expediente, booking, B/L y contenedor | M | ✅ | Precisión y recall por identificador frente al gold standard | E6 |
| RF-21 | Validar los contenedores con ISO 6346 completo (cuarta letra `U`/`J`/`Z` y dígito de control) y separarlos de los precintos | M | ✅ | Ningún precinto de la muestra se extrae como contenedor; test con códigos sintéticos válidos e inválidos | A-27 |
| RF-22 | Extraer naviera, buque y viaje | M | ✅ | Buque correcto en los expedientes del gold standard | E6 |
| RF-23 | Extraer puertos de origen, destino y transbordo, normalizados a UN/LOCODE | M | ✅ | Puertos de la muestra normalizados; test con nombres y variantes sintéticas | E6 |
| RF-24 | Extraer los eventos del buque (salida, llegada al puerto de carga, llegada a destino, transbordo) con su clasificador planificado, estimado o real | M | ✅ | Clasificador correcto en el gold standard; la «ETA» de llegada al puerto de carga no se confunde con la de destino | E6, A-01, A-02, ADR-0006 |
| RF-25 | Extraer los cut-offs (documental, VGM, entrega del contenedor) con fecha y hora | M | ✅ | Cut-offs del gold standard extraídos con fecha y hora | E6 |
| RF-26 | Extraer los eventos del contenedor: recogida del vacío, carga en almacén, entrada en terminal, carga a bordo | S | ✅ | Carga en almacén (fecha, hora y lugar) correcta en el gold standard | A-04, taxonomía §3 |
| RF-27 | Extraer los datos de aduanas de los PDF oficiales: levante, autorización de salida, DUA y circuito | S | ✅ | Fecha de levante correcta en todos los PDF con texto de la muestra | Análisis §2.4 |
| RF-28 | Distinguir las opciones de buques ofertadas de la reserva confirmada | M | ✅ | En los hilos con varias opciones, solo la reservada genera eventos del expediente | A-25 |
| RF-29 | Guardar con cada dato su evidencia literal, la fuente (mensaje, remitente y rol), el escalón que lo extrajo y su confianza | M | ✅ | Todo dato mostrado en la interfaz enlaza con el fragmento del que sale | E7 (fiabilidad), taxonomía §3.3 |
| RF-30 | Extracción configurable por proveedor (plantillas para PDF y asuntos estructurados) sin desplegar código | S | 🟡 | Añadir una plantilla sintética nueva no requiere cambiar código (solo un fichero de configuración) | E1, PLAN §7.2 |

### 2.4 Normalización y asociación (E5.4)

| ID | Requisito | Prioridad | PoC | Criterio de aceptación | Origen |
|---|---|---|---|---|---|
| RF-40 | Normalizar fechas (formatos mixtos, sin año, relativas, rangos y aproximadas) a ISO 8601 con zona horaria y precisión | M | ✅ | Tests con todos los formatos de A-05 a A-11; los rangos y aproximadas conservan su precisión | A-05…A-11 |
| RF-41 | Descartar y marcar los datos que no se pueden interpretar sin adivinar | M | ✅ | Una fecha malformada sintética no genera evento y queda registrada como descartada | A-26 |
| RF-42 | Normalizar los tipos de contenedor a ISO 6346 (tamaño y tipo) | S | ✅ | Las notaciones de A-22 se normalizan; TEU coherente | A-22, A-23 |
| RF-43 | Asociar cada correo a su expediente por booking, expediente, contenedor, B/L o referencias ya vistas, por este orden | M | ✅ | Los 38 correos de la muestra se asocian a su expediente | E5.4, análisis §4.1 |
| RF-44 | Gestionar los alias del expediente (booking nuevo tras un roleo o una enmienda, expediente truncado) | S | 🟡 | Un caso sintético de cambio de booking mantiene el expediente | A-17, A-20 |
| RF-45 | Enviar a revisión los correos sin asociación o con asociación a varios expedientes sin contexto | M | ✅ | Un correo sintético sin identificadores aparece en la cola de revisión | A-19 |

### 2.5 Reconciliación con el ERP (E5.5)

| ID | Requisito | Prioridad | PoC | Criterio de aceptación | Origen |
|---|---|---|---|---|---|
| RF-50 | Leer el ERP (CSV en la PoC) y normalizarlo (espacios, formatos de fecha y número, codificación) | M | ✅ | Los 11 expedientes casan por booking sin falsos negativos | A-21 |
| RF-51 | Comparar cada campo del expediente con el ERP mediante reglas deterministas (nunca con LLM), con tolerancias por campo | M | ✅ | Veredictos frente al gold standard: precisión y recall de las discrepancias detectadas | PLAN §7.1 |
| RF-52 | Clasificar cada diferencia: falta en el ERP, error del ERP, ERP más reciente, discrepancia sin atribuir | M | ✅ | Los siete veredictos del gold standard se reproducen | Análisis §6.2 |
| RF-53 | Aplicar la jerarquía de fuentes por campo y la frescura (`known_at`) para decidir el valor vigente | M | ✅ | En los hilos con valores sucesivos se elige el vigente; los conflictos abiertos van a revisión | A-12, A-13, A-15, D6 |
| RF-54 | Detectar incoherencias internas del ERP (fechas en orden imposible, equipo, peso y volumen) | S | ✅ | Los casos de calidad del dato del análisis se detectan | Análisis §4.2 |
| RF-55 | Proponer la corrección al operativo; **no escribir en el ERP sin validación humana** | M | ✅ | Ninguna acción modifica el ERP; las propuestas quedan pendientes de validación | E5.5 |
| RF-56 | Priorizar las discrepancias por impacto operativo (cut-off próximo, salida, llegada) | S | 🟡 | La lista de discrepancias se ordena por prioridad y fecha | E1 |

### 2.6 Almacenamiento y datos para el negocio (E5.6)

| ID | Requisito | Prioridad | PoC | Criterio de aceptación | Origen |
|---|---|---|---|---|---|
| RF-60 | Guardar correos, documentos, eventos, discrepancias y correcciones con linaje completo | M | ✅ | Desde cualquier evento se llega al correo y al fragmento de origen | E5.6 |
| RF-61 | Modelo bitemporal: reconstruir qué se sabía de un expediente en cualquier fecha | S | ✅ | Consulta «estado del expediente a fecha X» sobre la muestra | Taxonomía §3.3 |
| RF-62 | Vista por expediente: línea temporal de eventos, datos enriquecidos y discrepancias | M | ✅ | Interfaz Streamlit con los 11 expedientes | E8 |
| RF-63 | Indicadores de negocio: discrepancias por tipo, proveedor y campo; retrasos por naviera y ruta; cumplimiento de cut-offs; tiempo desde el correo hasta la actualización | S | 🟡 | Informe agregado sobre la muestra (CLI `report`) | E5.6 |
| RF-64 | Exportar el expediente enriquecido para integrarlo con el ERP | C | 📐 | Diseño del contrato de integración | E1 |

### 2.7 Aprendizaje continuo (E5.7)

| ID | Requisito | Prioridad | PoC | Criterio de aceptación | Origen |
|---|---|---|---|---|---|
| RF-70 | El operativo puede validar o corregir cada dato y cada discrepancia desde la interfaz | M | ✅ | Una corrección queda guardada como evento de fuente humana con autor y fecha | E5.7 |
| RF-71 | Las correcciones validadas se reutilizan: ejemplos para el LLM, nuevas plantillas y ajuste de umbrales | S | 🟡 | Tras corregir un caso sintético, un correo equivalente se extrae bien | E5.7 |
| RF-72 | Evitar aprender de errores: control de calidad de las correcciones (doble revisión de una muestra, reglas de coherencia, reversibilidad) | M | 📐 | Diseño en `08_aprendizaje_continuo.md` | E7 |
| RF-73 | Aprender de la relación con clientes y proveedores: perfiles por remitente (formato de fechas, fiabilidad histórica, plantillas) | S | 🟡 | El perfil de un remitente sintético cambia la interpretación de sus fechas | E5.7, A-09 |

## 3. Requisitos no funcionales

### 3.1 Volumen y rendimiento

| ID | Requisito | Prioridad | PoC | Criterio de aceptación | Origen |
|---|---|---|---|---|---|
| RNF-01 | Procesar 100.000 correos al mes con un pico de unos 23 por minuto (S-01, S-02) | M | 📐 | Análisis de capacidad (F2.1b) y prueba de volumen sintético (F4.5) | E5 |
| RNF-02 | Crecer a 150.000 correos al mes o más **solo con configuración y réplicas**, con margen de 2× | M | 📐 | El análisis de capacidad muestra qué se escala en cada etapa sin cambiar código | E7, PLAN §7.2 |
| RNF-03 | Latencia de extremo a extremo (p95): menos de 15 minutos para eventos urgentes (cambio de cut-off, de buque o de salida) y menos de 4 horas para el resto (S-05) | S | 📐 | Diseño con colas por prioridad; latencia por etapa medida en la PoC | E1 |
| RNF-04 | Idempotencia y reprocesado: cualquier etapa se puede repetir sin duplicar | M | ✅ | Test de reprocesado | PLAN §7.2 |

### 3.2 Fiabilidad

| ID | Requisito | Prioridad | PoC | Criterio de aceptación | Origen |
|---|---|---|---|---|---|
| RNF-10 | Asociación correo → expediente: precisión ≥ 99,5 % en lo que se asocia automáticamente; el resto a revisión (S-06) | M | ✅ | Medido frente al gold standard (con la limitación de su tamaño) | E7 |
| RNF-11 | Campos críticos (buque, salida, llegada, cut-offs): precisión ≥ 98 % en lo que se acepta automáticamente; lo que no alcanza el umbral va a revisión | M | ✅ | Precisión por campo frente al gold standard, con intervalo de confianza | E7 |
| RNF-12 | Confianza calibrada por campo y umbrales configurables | M | 🟡 | Curva de calibración y umbral elegido documentados | E7 |
| RNF-13 | Revisión humana objetivo: menos del 15 % de los correos en régimen estable (S-07) | S | 📐 | Proporción medida en la PoC por escalón | E7 |
| RNF-14 | Muestreo de auditoría continuo de lo aceptado automáticamente | S | 📐 | Diseño en `07_fiabilidad.md` | E7 |

### 3.3 Coste

| ID | Requisito | Prioridad | PoC | Criterio de aceptación | Origen |
|---|---|---|---|---|---|
| RNF-20 | Coste expresado por mes y por correo, con supuestos explícitos, para 100.000 y 150.000 correos al mes | M | 📐 | `06_costes.md` | E7 |
| RNF-21 | Minimizar lo que llega al LLM (cascada de técnicas) y medir el porcentaje resuelto en cada escalón | M | ✅ | Porcentaje por escalón medido en la PoC | PLAN §7.1 |

### 3.4 Seguridad, privacidad y cumplimiento

| ID | Requisito | Prioridad | PoC | Criterio de aceptación | Origen |
|---|---|---|---|---|---|
| RNF-30 | Ningún dato real sale del entorno controlado sin autorización; los envíos a servicios externos se declaran y se protegen | M | ✅ | La PoC usa un LLM local; `09_seguridad.md` documenta los proveedores de producción | E4, ADR-0002, ADR-0005 |
| RNF-31 | Cumplimiento del RGPD: base legal, minimización, retención y borrado, seudonimización en logs | M | 📐 | `09_seguridad.md` | E4 |
| RNF-32 | Logs sin datos personales ni contenido de los correos | M | ✅ | Revisión de los logs de la PoC | ADR-0002 |
| RNF-33 | Control de acceso por rol en la interfaz de producción | S | 📐 | Diseño | — |

### 3.5 Mantenibilidad, observabilidad y auditoría

| ID | Requisito | Prioridad | PoC | Criterio de aceptación | Origen |
|---|---|---|---|---|---|
| RNF-40 | Arquitectura hexagonal: cambiar de LLM, OCR, buzón o base de datos es cambiar un adaptador | M | ✅ | El dominio no importa ningún adaptador (comprobado en el CI) | PLAN §7.2 |
| RNF-41 | Versionado de modelos, prompts, plantillas y reglas; cada dato registra con qué versión se obtuvo | M | ✅ | Cada evento guarda la versión de su extractor | PLAN §7.2 |
| RNF-42 | Métricas por etapa (rendimiento, latencia, cola, coste, confianza) y alertas | S | 🟡 | La PoC registra latencia y tokens por correo | PLAN §7.2 |
| RNF-43 | Trazabilidad completa de cada decisión de reconciliación (reglas aplicadas y fuentes) | M | ✅ | Cada discrepancia muestra la regla y las fuentes usadas | E5.5 |
| RNF-44 | Calidad del código: tipado estricto, lint, tests y CI | M | ✅ | CI en verde | PLAN §6 |

## 4. Supuestos

Cada supuesto condiciona algún requisito; si EShipping lo corrige, se revisan los requisitos enlazados.

| ID | Supuesto | Afecta a | Pregunta |
|---|---|---|---|
| S-01 | «100.000 correos o más» del enunciado es un **flujo mensual** de correos operativos (no un histórico ni un total anual) | RNF-01, RNF-02, RNF-20 | P-01 |
| S-02 | Los correos se concentran en unas 10 horas de 22 días laborables, con picos de 3× la media horaria | RNF-01, RNF-03 | P-02 |
| S-03 | La muestra (exportación FCL desde España) es representativa del tipo de correo, aunque no de las proporciones | RF-10, RNF-11 | P-03 |
| S-04 | Una parte relevante de los correos trae PDF; en la muestra, 14 de 38 (no extrapolable) | RNF-20 | P-04 |
| S-05 | Un cambio de cut-off, de buque o de salida necesita avisar en minutos; el resto admite horas | RNF-03 | P-05 |
| S-06 | Una asociación equivocada es más grave que una no hecha (prima la precisión sobre la cobertura) | RNF-10, RNF-11 | P-06 |
| S-07 | El equipo de operaciones acepta revisar una fracción de los casos a cambio de no leer todos los correos | RNF-13 | P-06 |
| S-08 | `SalidaOK`/`LlegadaOK = SI` indican fecha real; `Despacho` es la fecha de solicitud del despacho | RF-52 | P-07, P-08 |
| S-09 | El sistema propone y el operativo valida; no hay escritura automática en el ERP | RF-55 | P-09 |
| S-10 | En producción se podrán usar proveedores externos (LLM, OCR) con contrato de tratamiento de datos y residencia en la UE | RNF-30, RNF-31 | P-10 |

## 5. Preguntas para EShipping

Se priorizan por su efecto en el diseño. Las marcadas con ★ conviene plantearlas antes de la entrega por el canal indicado en el enunciado.

| ID | Pregunta | Por qué importa |
|---|---|---|
| P-01 ★ | ¿Los 100.000 correos son al mes? ¿Cuántos son operativos y cuántos ruido? | Dimensionamiento y coste |
| P-02 | ¿Cómo se distribuyen por hora y por día? ¿Hay picos estacionales? | Capacidad para el pico |
| P-03 | ¿Qué proporción hay de importación, LCL, aéreo y terrestre? ¿Cuántas navieras y transportistas distintos? | Plantillas necesarias y cobertura de reglas |
| P-04 | ¿Qué proporción de correos trae PDF y cuántos son escaneados? | Coste de OCR |
| P-05 | ¿Qué eventos necesitan aviso inmediato y con cuánta antelación sobre el cut-off? | Latencia y prioridades |
| P-06 | ¿Qué coste tiene para operaciones un dato erróneo frente a uno no extraído? ¿Cuánta revisión humana es asumible? | Umbrales de confianza |
| P-07 ★ | ¿Qué significan `SalidaOK` y `LlegadaOK`? ¿Se puede saber cuándo se actualizó cada campo del ERP? | Distinguir errores de actualizaciones (A-28) |
| P-08 | ¿`Despacho` es la fecha de solicitud del despacho o la de levante? ¿Y `F. Carga`? | Comparación correcta de campos (A-04, A-29) |
| P-09 | ¿DEIWORLD tiene API o exportación programable? ¿Se podría escribir en él? | Integración |
| P-10 | ¿Hay restricciones contractuales o de cumplimiento para usar proveedores de IA en la nube? | Elección de proveedor |
| P-11 | ¿Qué jerarquía de fuentes aplica hoy operaciones cuando la naviera y el cliente discrepan? | Política de resolución (D6) |
| P-12 | ¿Se usan ya las API o webs de seguimiento de las navieras? ¿Con cuáles? | Fuentes estructuradas (RF-07) |
| P-13 | El enunciado habla de 10 correos y 10 filas; se han recibido 11 de cada. ¿Es intencionado? | Coherencia del material |

## 6. Trazabilidad con el enunciado

| Apartado del enunciado | Requisitos |
|---|---|
| 5.1 Recibir e ingerir | RF-01 a RF-07 |
| 5.2 Clasificar por tipo | RF-10 a RF-12 |
| 5.3 Extraer datos | RF-20 a RF-30 |
| 5.4 Normalizar y asociar | RF-40 a RF-45 |
| 5.5 Cruzar con el ERP y resolver | RF-50 a RF-56 |
| 5.6 Almacenar y generar datos | RF-60 a RF-64 |
| 5.7 Aprender de forma continua | RF-70 a RF-73 |
| 6 Datos a extraer | RF-20 a RF-28 |
| 7 Fiabilidad | RNF-10 a RNF-14, RF-29 |
| 7 Coste | RNF-20, RNF-21 |
| 7 Escalabilidad (100.000 → 150.000) | RNF-01 a RNF-03 |
| 7 Aprendizaje sin aprender de errores | RF-70 a RF-73 |
| 4 Confidencialidad y servicios externos | RNF-30 a RNF-32 |
| 8 PoC que admite correos nuevos | RF-01, RF-62, RNF-44 |

## Historial

| Versión | Fecha | Cambios |
|---|---|---|
| 0.1.0 | 22/11/2026 | Primera versión: 43 requisitos funcionales y 20 no funcionales (29 imprescindibles, 27 de ellos en la PoC), 10 supuestos y 13 preguntas |
