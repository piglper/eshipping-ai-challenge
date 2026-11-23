# Fiabilidad: métricas, calibración, umbrales y auditoría

| Campo | Valor |
|---|---|
| Versión | 0.1.0 |
| Estado | Borrador |
| Responsable | Pablo Iglesias Peral |
| Última actualización | 23/11/2026 |
| Tarea | F2.6 (#21) |
| Requisitos | RNF-10 a RNF-14, RF-29, RF-41, RF-72 |
| Decisiones relacionadas | [ADR-0008](adr/0008-estrategia-de-ia-cascada-por-etapa.md) (controles sobre el LLM), [ADR-0009](adr/0009-politica-de-resolucion-de-discrepancias.md) (veredictos y prioridades), [ADR-0010](adr/0010-proveedor-de-llm-de-produccion.md) (evaluación de proveedores) |

> **Confidencialidad:** sin datos reales. Las cifras del gold standard son agregadas.

## 1. Resumen

- **Fiable significa que lo que el sistema acepta sin revisión es correcto** con una probabilidad conocida y alta. Se prioriza la precisión sobre la cobertura (S-06): un dato erróneo aceptado es peor que un dato enviado a revisión.
- Cada dato lleva una **confianza calibrada**, que es la probabilidad estimada de que sea correcto. No es la que declara el modelo, sino un modelo por campo sobre señales comprobables (§3).
- Cada campo tiene un **objetivo de precisión** y un **umbral** que lo garantiza con un margen estadístico. Por encima del umbral, el dato se acepta; por debajo, va a revisión; muy por debajo, no se propone (§4).
- Lo aceptado automáticamente se **audita por muestreo** de forma continua. Si la precisión auditada cae por debajo del objetivo, el umbral de ese campo se endurece de forma automática y solo una persona lo puede relajar (§5).
- **Límite honesto de la PoC:** el gold standard (38 correos y 89 comparaciones) no permite demostrar una precisión del 98 %. Aunque no hubiera ningún error, el límite inferior del intervalo de confianza sería del 95,9 %. Hacen falta unos 190 casos sin errores por campo para el 98 % y unos 765 para el 99,5 % (§6).

## 2. Qué se mide

### 2.1 Unidades de medida

| Unidad | Qué es correcto | Requisito |
|---|---|---|
| **Asociación** de un mensaje a un expediente | El expediente es el del gold standard | RNF-10 (≥ 99,5 % en lo asociado automáticamente) |
| **Clase** de un mensaje | La clase principal coincide; las secundarias se miden aparte | RF-10 |
| **Campo** de un evento (fecha, lugar, buque, contenedor, etc.) | El valor coincide con el del gold standard según las tolerancias del [ADR-0009 §4](adr/0009-politica-de-resolucion-de-discrepancias.md#4-comparación-con-el-erp), y el clasificador (`PLN`/`EST`/`ACT`) también | RNF-11 (≥ 98 % en los campos críticos aceptados) |
| **Veredicto** frente al ERP | El veredicto coincide con el del gold standard | RF-52 |
| **Cita** de un valor del LLM | La cita aparece literalmente en el texto de origen y respalda el valor | RF-29, ADR-0008 |

**Campos críticos** (los mismos que en el ADR-0009): buque, salida y llegada del buque, cut-offs y carga en almacén. El resto son no críticos.

### 2.2 Tipos de error y su gravedad

| Error | Ejemplo | Gravedad | Qué lo controla |
|---|---|---|---|
| Asociación equivocada | Un retraso se apunta en otro expediente | Muy alta: contamina un expediente ajeno sin que nadie lo note | Claves deterministas; sin clave segura, revisión |
| Valor erróneo aceptado | Se acepta una ETD equivocada | Alta | Umbral por campo, auditoría |
| Clasificador erróneo | Una previsión se toma por un hecho real | Alta: cambia la reconciliación | Reglas de tiempo verbal, LLM con evidencia, umbral |
| Falsa discrepancia | Se alerta de un error del ERP que no existe | Media: gasta tiempo de revisión y desgasta la confianza en el sistema | Regla «ERP más reciente», tolerancias |
| Discrepancia no detectada | El ERP tiene un error y no se alerta | Media | Recall de los veredictos |
| Dato no extraído | No se encuentra un cut-off que sí está | Baja: el dato va a revisión o no se completa | Recall por campo |

### 2.3 Métricas

**En la evaluación (con el gold standard, el conjunto sintético y, en producción, la auditoría):**

| Métrica | Definición | Para qué |
|---|---|---|
| Precisión y recall por campo y por escalón | Sobre los valores extraídos frente a los del conjunto de referencia | Saber qué escalón falla y dónde |
| **Precisión en lo aceptado automáticamente** | Precisión solo de los valores con confianza ≥ umbral | Es la métrica de RNF-11 |
| **Cobertura automática** | Porcentaje de valores aceptados sin revisión | Es el reverso de la carga de revisión |
| Exactitud y F1 por clase | Clasificación de mensajes | RF-10 |
| Precisión y recall por veredicto | Especialmente `ERP_ERROR` y `DISCREPANCY` | RF-52 |
| **Tasa de citas no verificadas** | Valores del LLM cuya cita no está en el texto | Indicador de alucinación; se descartan, pero su tasa mide la salud del modelo |
| Error de calibración (ECE) y puntuación de Brier | Diferencia entre la confianza y el acierto real | Saber si la confianza es creíble (§3.3) |
| Porcentaje resuelto en cada escalón | Determinista, plantilla, ML, LLM, persona | RNF-21; alimenta los costes |

Todas las proporciones se publican con su **intervalo de confianza al 95 % (Wilson)**, nunca como un número suelto.

**En producción (de forma continua):**

| Métrica | Fuente | Alerta si |
|---|---|---|
| Precisión auditada por campo | Muestreo de auditoría (§5) | El límite inferior del intervalo cae por debajo del objetivo |
| Tasa de corrección en revisión por campo, escalón y remitente | Correcciones de los operativos | Sube de forma sostenida (indicador de deriva) |
| Tasa de rechazo de propuestas al ERP | Propuestas rechazadas por regla y rol de fuente (ADR-0009 §7) | Una regla concreta supera un umbral |
| Cobertura automática por campo | Proyección | Cae de forma brusca (por ejemplo, una plantilla deja de encajar) |
| Distribución de clases, de confianza y de escalones | Extracción | Cambia de forma significativa frente a la semana anterior (remitente nuevo, formato nuevo) |
| Tasa de citas no verificadas | Validador | Sube tras un cambio de modelo o de prompt |
| Latencia p95 por prioridad | Observabilidad | Supera RNF-03 |

## 3. Confianza calibrada

### 3.1 Señales

La confianza de cada valor se calcula a partir de señales que se pueden comprobar, no de lo que el modelo dice de sí mismo:

| Señal | Ejemplo |
|---|---|
| Escalón que lo extrajo | Regla con validación ISO 6346 > plantilla > ML > LLM |
| Validaciones superadas | Dígito de control, UN/LOCODE existente, fecha plausible respecto al mensaje |
| Cita verificada | La cita existe en el texto y contiene el valor |
| Acuerdo entre escalones | El LLM y una regla dan el mismo valor |
| Rango de la fuente para el campo | A, B o C según el [ADR-0009 §2](adr/0009-politica-de-resolucion-de-discrepancias.md#2-autoridad-por-campo) |
| Coherencia con el expediente | La nueva ETD no está a meses de distancia de la anterior sin un motivo (roleo, cambio de buque) |
| Marcas de ambigüedad | El valor cae en un caso del catálogo (fecha sin año, día-mes frente a mes-día, «ETA» en el puerto de carga) |
| Historial del remitente | Tasa de acierto de sus datos en revisiones y auditorías anteriores |

### 3.2 Modelo de calibración

- **Arranque (sin datos):** una tabla de confianzas iniciales por escalón y señal, **conservadora a propósito** (por ejemplo, ningún valor del LLM supera el umbral de un campo crítico sin el acuerdo de otra señal). Con ella, la cobertura automática inicial es baja y la revisión alta (el 30 % de arranque de la [arquitectura §9.6](04_arquitectura.md#96-revisión-humana-el-cuello-de-botella-real)).
- **Con datos:** por cada campo, una **regresión logística** sobre las señales, entrenada con los valores revisados y auditados (correcto o incorrecto). Es simple, explicable y se calibra bien; si la curva de calibración lo pide, se ajusta con regresión isotónica.
- **Cuándo se pasa de la tabla al modelo:** cuando un campo tiene al menos 200 valores etiquetados con al menos 20 errores. Por debajo, el modelo no es fiable.
- **Recalibración:** mensual, y siempre que cambie la versión de un extractor, un prompt, un modelo o una plantilla, porque la calibración es de una versión concreta.

### 3.3 Cómo se comprueba la calibración

- **Diagrama de fiabilidad** por campo: en el tramo de confianza del 0,9 al 0,95, el acierto real debe estar entre el 90 % y el 95 %.
- **ECE** (error de calibración esperado) y **Brier** en cada recalibración, con un conjunto separado del de entrenamiento.
- Lo que importa operativamente es la parte alta de la curva, donde están los umbrales: se informa aparte.

## 4. Umbrales

### 4.1 Objetivos por campo

| Tipo de dato | Objetivo de precisión en lo aceptado automáticamente | Origen |
|---|---|---|
| Asociación mensaje → expediente | 99,5 % | RNF-10 |
| Campos críticos | 98 % | RNF-11 |
| Campos no críticos (levante, B/L, equipo, contenedores) | 95 % (propuesta) | Pregunta para EShipping (P-06) |
| Veredicto `ERP_ERROR` (propuesta de corrección) | 95 % (propuesta) | Una propuesta errónea se rechaza en revisión, pero gasta tiempo |

### 4.2 Cómo se elige el umbral

Para cada campo, sobre el conjunto de calibración:

1. Se ordenan los valores por confianza.
2. Se elige el **umbral más bajo** tal que, entre los valores con confianza mayor o igual, el **límite inferior del intervalo de confianza al 95 %** de la precisión sea mayor o igual que el objetivo.
3. Se calcula la cobertura automática resultante y se publica la curva precisión-cobertura, para que se vea lo que cuesta subir o bajar el objetivo.

Usar el límite inferior, y no la precisión observada, evita que un conjunto pequeño con pocos errores fije un umbral demasiado optimista.

### 4.3 Tres zonas

| Zona | Condición | Qué se hace |
|---|---|---|
| **Aceptación automática** | Confianza ≥ umbral del campo y sin conflicto (ADR-0009) | El valor entra en el expediente; entra en el muestreo de auditoría |
| **Revisión** | Entre el umbral inferior y el umbral del campo, o en conflicto | Tarea de revisión con su prioridad (ADR-0009 §6) |
| **No propuesto** | Confianza por debajo del umbral inferior | No se propone como valor (sería ruido en la revisión); queda registrado con su cita y su motivo. Si el campo es crítico y no hay otro valor, el expediente se marca como «dato pendiente» |

Los umbrales son configuración versionada (arquitectura §7.4). **Bajar un umbral** requiere datos de auditoría que lo justifiquen y la aprobación de una persona; **subirlo** puede hacerlo el propio sistema (§5.3).

## 5. Auditoría continua

### 5.1 Qué se muestrea

- **Aleatorio y estratificado** entre lo aceptado automáticamente, con estratos por campo, escalón y proveedor o remitente.
- **Sobremuestreo** de lo nuevo: remitentes vistos por primera vez, plantillas nuevas y la primera semana de cualquier versión nueva de un extractor, un prompt o un modelo.
- **Todos los veredictos `ERP_NEWER`** de una muestra semanal, porque la regla del ADR-0009 es una heurística cuando no se conoce la fecha de actualización del ERP.

### 5.2 Tamaño

Para estimar una precisión en torno al 99 % con un margen de ±1 punto al 95 % de confianza hacen falta unas **380 muestras por estrato**. Propuesta:

| Estrato | Muestras al mes |
|---|---|
| Cada campo crítico (5) | 400 |
| Cada campo no crítico | 100 |
| Asociación | 400 |
| Remitentes y plantillas nuevos | 20 por remitente o plantilla, durante el primer mes |

En total, unas 2.800 a 3.200 muestras al mes (con unos cuatro campos no críticos); con 1,5 minutos por muestra, unas **70 a 80 horas al mes** de revisión de auditoría, que se pueden repartir a lo largo del mes. Es la parte del trabajo humano que convierte la confianza en una cifra demostrable; con 150.000 correos al mes no crece, porque el tamaño de la muestra no depende del volumen.

**Doble revisión:** el 10 % de las muestras las revisa una segunda persona. El acuerdo entre las dos (kappa de Cohen) mide la calidad de las etiquetas que alimentan la calibración y el aprendizaje continuo (RF-72, F2.8).

### 5.3 Freno automático

- Si el límite inferior de la precisión auditada de un estrato cae por debajo de su objetivo, el sistema **sube el umbral** de ese estrato (o envía todo el estrato a revisión) y avisa.
- Volver al umbral anterior requiere que una persona lo apruebe, con los datos de auditoría a la vista.
- Así, un cambio de formato de una naviera o una regresión de un modelo se traduce en más revisión, no en datos erróneos aceptados en silencio.

## 6. Evaluación en la PoC (F4)

### 6.1 Qué se puede demostrar con el gold standard

| Conjunto | Casos | Límite inferior al 95 % si no hay ningún error | Límite si hay un error |
|---|---|---|---|
| Asociación (correos) | 38 | 90,8 % | — |
| Comparaciones de campo | 89 | 95,9 % | 93,9 % |

Casos necesarios **sin ningún error** para que el límite inferior alcance el objetivo:

| Objetivo | Casos necesarios |
|---|---|
| 98 % (campos críticos) | ≈ 190 por campo |
| 99,5 % (asociación) | ≈ 765 |

**Conclusión:** la PoC puede mostrar que el enfoque funciona y dónde falla, pero **no demostrar** los objetivos de RNF-10 y RNF-11. Eso se hace en un piloto con una muestra real etiquetada de al menos esos tamaños, o con la auditoría de los primeros meses en producción. Los informes de F4 lo dirán así, con sus intervalos.

### 6.2 Otras limitaciones

- El gold standard lo etiquetó Claude Code y está **pendiente de revisión humana** (riesgo R10): las métricas de F4 son provisionales.
- Un solo etiquetador: no hay acuerdo entre anotadores.
- Once expedientes de un mismo tipo (exportación marítima FCL desde España): no cubren importación, LCL ni otros modos (S-03).
- El conjunto sintético (F3.10) sirve para regresión y casos límite, no para estimar la precisión real.

## 7. Cambios sin regresiones

Cualquier cambio que afecte al resultado (modelo, prompt, plantilla, reglas, umbrales) sigue este camino:

1. **Evaluación** contra el conjunto de referencia y el de regresión: ninguna métrica de campo crítico puede empeorar por encima de su intervalo.
2. **Modo sombra:** la nueva versión procesa en paralelo una muestra del tráfico real sin efecto en los expedientes; se comparan sus resultados con los de la versión vigente.
3. **Activación gradual** por proveedor o por clase de correo, con sobremuestreo de auditoría la primera semana (§5.1).
4. La versión queda registrada en cada dato que produce (RNF-41), así que se puede reprocesar o revertir.

## 8. Trazabilidad

| Requisito | Dónde se cubre |
|---|---|
| RNF-10 | §4.1 (objetivo), §5.2 (auditoría de la asociación), §6.1 (límite de la PoC) |
| RNF-11 | §2.3, §4 |
| RNF-12 | §3 |
| RNF-13 | §4.3 (zonas) y cobertura automática (§2.3) |
| RNF-14 | §5 |
| RF-29 | §2.1 (citas), §3.1 (señales) |
| RF-41 | §4.3 (zona «no propuesto») |
| RF-72 | §5.2 (doble revisión) |

## Historial

| Versión | Fecha | Cambios |
|---|---|---|
| 0.1.0 | 23/11/2026 | Primera versión: unidades y tipos de error, métricas, confianza calibrada, umbrales por campo, auditoría continua con freno automático, límites estadísticos de la PoC y cambios sin regresiones |
