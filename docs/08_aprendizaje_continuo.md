# Aprendizaje continuo

| Campo | Valor |
|---|---|
| Versión | 0.1.1 |
| Estado | Entregado (`v1.0.0`) |
| Responsable | Pablo Iglesias Peral |
| Última actualización | 23/11/2026 |
| Tarea | F2.8 (#24) |
| Requisitos | RF-70 a RF-73, RNF-13, RNF-21 |
| Relacionado | [Arquitectura §12.3](04_arquitectura.md#123-corrección--aprendizaje) (flujo), [fiabilidad](07_fiabilidad.md) (calibración, auditoría y cambios sin regresiones), [ADR-0008](adr/0008-estrategia-de-ia-cascada-por-etapa.md) (la cascada evoluciona), [ADR-0009](adr/0009-politica-de-resolucion-de-discrepancias.md) (autoridad de las fuentes) |

> **Confidencialidad:** sin datos reales. Los ejemplos son sintéticos.

## 1. Resumen

- **Qué se aprende:** cada corrección validada y cada muestra de auditoría se convierte en algo más barato y más fiable: una calibración mejor, un clasificador clásico mejor entrenado, un ejemplo para el LLM, una plantilla nueva, un perfil de remitente o un alias de expediente (§3).
- **Hacia dónde:** el trabajo **baja por la cascada**: lo que hoy resuelve el LLM lo resolverá mañana una plantilla o el modelo clásico, y lo que hoy va a revisión irá a aceptación automática. Se mide con el porcentaje resuelto en cada escalón y la cobertura automática (§6).
- **Sin aprender de errores** (RF-72): las etiquetas pasan un control de calidad antes de usarse (doble revisión, detección de validaciones apresuradas, reglas de coherencia, cuarentena), el sistema **nunca se entrena con sus propias salidas sin revisar**, y todo lo aprendido está versionado y enlazado con las etiquetas que lo produjeron, para poder deshacerlo (§4).
- **Automático y humano:** lo que solo mejora la estimación (calibración, clasificador, ejemplos) se actualiza solo, tras pasar la evaluación. Lo que cambia reglas de negocio (plantillas, autoridad de las fuentes, bajar umbrales) lo propone el sistema y lo aprueba una persona (§5).

## 2. Señales de las que se aprende

| Señal | Qué dice | Fuerza | Origen |
|---|---|---|---|
| **Corrección** de un operativo | El valor correcto de un campo, la clase o el expediente | Fuerte | Revisión (RF-70) |
| **Validación** de un operativo | El valor propuesto era correcto | Fuerte, si no es apresurada (§4.2) | Revisión |
| **Rechazo con motivo** de una propuesta al ERP | La propuesta era errónea y por qué | Fuerte | Revisión (ADR-0009 §7) |
| **Muestra de auditoría** | Valor aceptado automáticamente, correcto o no | Fuerte y **sin sesgo de selección** | Auditoría ([fiabilidad §5](07_fiabilidad.md#5-auditoría-continua)) |
| Confirmación posterior de un hecho | Un `EST` que acaba en un `ACT` igual (la salida estimada coincide con la real) | Media | Línea temporal del expediente |
| El ERP adopta el valor propuesto | El operativo aplicó la propuesta en el ERP | Media | Lecturas posteriores del ERP |
| Eventos de las API de las navieras | Confirmación estructurada de salidas, llegadas y cargas | Fuerte para esos campos | Futuro (RF-07) |

Las señales **implícitas** (las tres últimas) solo refuerzan o debilitan; no sustituyen a una etiqueta humana en el entrenamiento de los campos críticos.

## 3. Qué cambia con lo aprendido

| Mecanismo | Qué aprende | De qué señal | Frecuencia | Quién lo aplica |
|---|---|---|---|---|
| **Calibración de la confianza** | La probabilidad real de acierto por campo y señal | Auditoría (parte alta) y revisiones (parte media) | Vigilancia diaria, recalibración semanal y por evento ([fiabilidad §3.2](07_fiabilidad.md#32-modelo-de-calibración)) | Automático, tras la evaluación |
| **Clasificador clásico** (TF-IDF + regresión logística) | Las clases de los mensajes | Correcciones de clase | Semanal | Automático, tras la evaluación |
| **Ejemplos para el LLM** (few-shot dinámico) | Cómo extraer de un remitente o formato concreto | Correcciones validadas por doble revisión o auditoría | Continua (banco versionado) | Automático |
| **Plantillas nuevas** | El formato fijo de un proveedor o documento | Formatos que llegan a menudo al LLM con salidas validadas | Cuando se detecta el patrón | Propuesta automática, aprobación del equipo técnico |
| **Perfil de remitente** | Orden día-mes, zona horaria, plantillas, fiabilidad por campo | Correcciones y auditoría por remitente | Continua | Automático para el formato; la fiabilidad solo como señal de confianza |
| **Rol del remitente y autoridad** | El perfil aprendido de cada dominio (señal 3 del [ADR-0013](adr/0013-rol-del-remitente-en-cascada.md)) y el rango de una fuente por campo | Clases de correo que manda cada dominio, expedientes en que aparece, rechazos y correcciones agrupados por rol | Mensual (el perfil, cada noche) | Propuesta automática. Operaciones solo confirma los pocos dominios que concentran el volumen; nunca se dan de alta uno a uno |
| **Alias de expediente** | Bookings nuevos tras un roleo, referencias del cliente | Correcciones de asociación | Inmediata | Automático, al validar la corrección |
| **Reglas de triaje** | Palabras o patrones de urgencia | Mensajes urgentes que no se marcaron como tales | Mensual | Propuesta automática, aprobación del equipo técnico |
| **Umbrales** | Hasta dónde se puede aceptar sin revisión | Calibración y auditoría | Con cada recalibración | Subir: automático. Bajar: persona ([fiabilidad §4.3](07_fiabilidad.md#43-tres-zonas)) |

### 3.1 Ejemplos dinámicos para el LLM

- **Banco de ejemplos:** pares (fragmento del mensaje, salida JSON correcta) tomados de correcciones validadas. Se guardan seudonimizados y versionados.
- **Selección:** para cada llamada se eligen hasta tres ejemplos del mismo remitente o proveedor y la misma clase; si no hay, los más parecidos por similitud de texto (TF-IDF, sin un modelo externo).
- **Coste:** los ejemplos van **después** del prefijo fijo (instrucciones y esquema), para no romper la caché del proveedor ([costes, C-05](06_costes.md#2-supuestos)); unos cientos de tokens más por llamada.
- **Calidad:** solo entran ejemplos con doble revisión o confirmados por auditoría; un ejemplo que después se invalida se retira y se registra qué llamadas lo usaron.

### 3.2 Inducción de plantillas

1. El sistema detecta un **formato estable** que llega a menudo al LLM: mismo remitente o tipo de documento, estructura repetida (mismas etiquetas, mismas posiciones) y salidas del LLM validadas.
2. Propone una plantilla con anclas de texto derivadas de las salidas validadas y la prueba contra los casos históricos de ese formato.
3. El equipo técnico la revisa, añade tests con casos sintéticos y la despliega por PR (configuración versionada).
4. A partir de ese momento, ese formato no llega al LLM: baja el coste y la variabilidad, y sube la confianza.
5. Si la plantilla deja de encajar (el proveedor cambia el formato), la cobertura automática cae, salta la alerta de [fiabilidad §2.3](07_fiabilidad.md#23-métricas) y el LLM vuelve a cubrir ese formato mientras se ajusta.

### 3.3 Más adelante: un modelo propio

Cuando haya miles de ejemplos validados por campo, se evaluará sustituir el LLM externo por un modelo pequeño ajustado con esos datos en los campos más frecuentes, como prevé el [ADR-0008](adr/0008-estrategia-de-ia-cascada-por-etapa.md). Seguiría el mismo camino que cualquier cambio: evaluación, modo sombra y activación gradual.

## 4. Sin aprender de errores (RF-72)

### 4.1 De dónde vienen las etiquetas malas

| Riesgo | Ejemplo |
|---|---|
| Error del operativo | Corrige con la fecha de otro expediente |
| Validación apresurada | Acepta todo lo que se le propone sin leerlo (sesgo de automatización) |
| Desacuerdo entre operativos | Dos personas interpretan distinto «ETA» en el puerto de carga |
| El valor del ERP no es la verdad | Se toma el ERP como corrección y el ERP estaba mal |
| Retroalimentación | El sistema aprende de lo que él mismo aceptó, y confirma sus propios errores |
| Sesgo de selección | Solo se revisa lo de confianza baja, y se calibra la parte alta con datos que no la representan |

### 4.2 Controles

| Control | Cómo funciona |
|---|---|
| **Doble revisión** | El 10 % de las revisiones y de las muestras de auditoría las ve una segunda persona; el acuerdo (kappa de Cohen) se mide por campo y por persona. Los desacuerdos van a una tercera revisión y no se usan hasta resolverse |
| **Detección de validaciones apresuradas** | Se marcan las validaciones con un tiempo por elemento muy por debajo de lo normal o con tasas de aceptación cercanas al 100 % en un periodo. Esas etiquetas pesan menos y la persona recibe más casos de control |
| **Casos de control** | Se intercalan en la cola casos ya conocidos (de la auditoría) para medir el acierto de cada revisor sin que lo sepa en ese momento |
| **Reglas de coherencia** | Una corrección tiene que pasar las mismas validaciones de dominio que un dato extraído (fecha plausible, puerto existente, contenedor válido) y venir con una cita o un motivo |
| **Cuarentena** | Las etiquetas esperan 7 días antes de entrar en un entrenamiento; si en ese tiempo aparece algo que las contradice (un `ACT` distinto, una corrección posterior), se revisan |
| **Peso por fiabilidad del revisor** | El acuerdo histórico de cada persona con la auditoría y la doble revisión pondera sus etiquetas |
| **Nunca de sus propias salidas** | Nada aceptado automáticamente entra en el entrenamiento salvo que lo haya confirmado la auditoría o una señal externa. Corta el bucle de retroalimentación |
| **El ERP no es una etiqueta** | Un valor del ERP solo sirve de etiqueta si una persona lo confirma; si no, es solo una fuente más |
| **Muestra aleatoria para la parte alta** | La calibración de la zona de aceptación automática se hace con la auditoría aleatoria, no con lo revisado ([fiabilidad §3.2](07_fiabilidad.md#32-modelo-de-calibración)) |
| **Conjunto de evaluación protegido** | Una parte del conjunto de referencia no se usa nunca para entrenar; se renueva por bloques, nunca entero |

### 4.3 Reversibilidad

- Cada artefacto aprendido (calibración, clasificador, banco de ejemplos, plantilla, perfil) tiene una **versión** y la lista de las **etiquetas** con las que se generó.
- Si una etiqueta se invalida (por ejemplo, la tercera revisión da la razón al sistema), se sabe qué artefactos la usaron; se regeneran sin ella y se reprocesan los datos afectados si hace falta ([arquitectura §12.5](04_arquitectura.md#125-reprocesado-tras-un-cambio-de-versión)).
- Cualquier versión se puede revertir a la anterior en la configuración, y cada dato registra con qué versión se obtuvo (RNF-41).

## 5. Gobernanza

| Tipo de cambio | Ejemplos | Aplicación |
|---|---|---|
| Mejora la estimación sin cambiar reglas de negocio | Calibración, clasificador, banco de ejemplos, formato de fechas de un remitente | Automática, si pasa la evaluación ([fiabilidad §7](07_fiabilidad.md#7-cambios-sin-regresiones)) |
| Cambia cómo se interpreta un proveedor | Plantilla nueva o modificada, regla de triaje | Propuesta automática; la aprueba el equipo técnico por PR |
| Cambia qué fuente manda o cuánto se revisa | Rango de autoridad, criticidad de un campo, bajar un umbral | Propuesta automática con los datos; la aprueba operaciones |

Toda aplicación queda registrada en `config_version` con quién la aprobó.

## 6. Cómo se sabe que el sistema aprende

| Indicador | Tendencia esperada | Alerta |
|---|---|---|
| Porcentaje resuelto por el LLM | Baja con el tiempo, por proveedor | Sube de forma sostenida (formatos nuevos sin plantilla) |
| Cobertura automática por campo | Sube | Cae tras un cambio (regresión o formato nuevo) |
| Porcentaje en revisión | Baja (del 30 % de arranque hacia el 15 % y menos, [arquitectura §9.6](04_arquitectura.md#96-revisión-humana-el-cuello-de-botella-real)) | Se estanca por encima del objetivo |
| Precisión auditada | **Estable o mejor** mientras sube la cobertura | Baja: el freno automático sube umbrales ([fiabilidad §5.3](07_fiabilidad.md#53-freno-automático)) |
| Curva de aprendizaje por remitente | Las correcciones de un remitente nuevo bajan en sus primeras semanas | Un remitente no mejora: candidato a plantilla o a revisar su rol |
| Acuerdo entre revisores | Alto y estable | Baja: hay ambigüedad en las instrucciones de revisión |

## 7. Aprender de la relación con clientes y proveedores

Además de mejorar la extracción, el histórico da información de negocio (RF-63, RF-73):

- **Fiabilidad de las estimaciones por naviera y ruta:** la diferencia entre la `EST` y la `ACT` de cada salida y llegada. Sirve a operaciones para planificar y al sistema como señal de confianza (una ETA de una naviera que suele acertar pesa más).
- **Hábitos de cada remitente:** formato de fechas, zona horaria, idioma, qué datos suele enviar y cuáles hay que pedirle.
- **Proveedores problemáticos:** tasa de cambios de última hora, roleos y discrepancias por proveedor.

## 8. En la PoC

| Requisito | Qué se implementa | Cómo se demuestra |
|---|---|---|
| RF-70 | Corregir o validar un dato desde la interfaz o la CLI; la corrección queda como observación de fuente humana con autor y fecha | Test con un caso sintético |
| RF-71 (simplificado) | Banco de ejemplos: una corrección validada se usa como ejemplo en las llamadas siguientes del mismo remitente | Un correo sintético equivalente se extrae bien tras la corrección |
| RF-73 (simplificado) | Perfil de remitente con el orden día-mes | El perfil de un remitente sintético cambia la interpretación de sus fechas |
| RF-72 | Solo diseño (este documento) | — |

## 9. Trazabilidad

| Requisito | Dónde se cubre |
|---|---|
| RF-70 | §2, §8 |
| RF-71 | §3, §3.1, §3.2 |
| RF-72 | §4 |
| RF-73 | §3 (perfil de remitente), §7 |
| RNF-13 | §6 (porcentaje en revisión) |
| RNF-21 | §3.2, §6 (porcentaje por escalón) |

## Historial

| Versión | Fecha | Cambios |
|---|---|---|
| 0.1.1 | 25/11/2026 | El rol del remitente se aprende como perfil por dominio, sin directorio manual (ADR-0013) |
| 0.1.0 | 23/11/2026 | Primera versión: señales, mecanismos de aprendizaje, control de calidad de las etiquetas, reversibilidad, gobernanza, indicadores y alcance en la PoC |
