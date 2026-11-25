# ADR-0013: El rol del remitente se resuelve en cascada, sin dar de alta los dominios uno a uno

- **Estado:** Aceptado
- **Fecha:** 2026-11-25
- **Decisores:** Pablo Iglesias Peral
- **Referencias:** issue #41, PR #86, [ADR-0009 §1](0009-politica-de-resolucion-de-discrepancias.md#1-rol-de-la-fuente) (sustituye cómo se obtiene el rol), [ADR-0008](0008-estrategia-de-ia-cascada-por-etapa.md), [evaluación §4 y §5](../11_evaluacion.md), RF-73, RNF-01, RNF-02

## Contexto y problema

El rol de quien escribe (naviera, agente de aduanas, transportista, interno o cliente) decide cuánta autoridad tiene cada valor (ADR-0009 §2). El ADR-0009 obtenía el rol de un **directorio de remitentes por dominio, mantenido por operaciones**.

La evaluación sobre la muestra real (F4.2) mostró dos cosas:
- **Sin directorio, ningún valor gana.** Todos los remitentes son desconocidos, es decir, informativos, y la reconciliación da 71 `MAIL_MISSING`.
- **Un directorio manual no escala.** Con 100.000 correos al mes, y creciendo, escribirán cientos o miles de dominios distintos, la mayoría pocas veces. Darlos de alta uno a uno es inviable, y un directorio incompleto degrada el sistema en silencio.

## Factores de decisión

- Escalabilidad: crecer en volumen y en remitentes no debe exigir trabajo manual proporcional (RNF-02).
- Fiabilidad: un rol equivocado hacia arriba da autoridad a quien no la tiene. Es peor que equivocarse hacia abajo, que solo manda el valor a revisión.
- Reutilizar lo que EShipping ya mantiene: el ERP sabe qué naviera, agente de aduanas y transportista lleva cada expediente.
- Explicabilidad: cada rol debe decir de qué señal sale.

## Opciones consideradas

1. Directorio manual de todos los dominios (ADR-0009 §1).
2. Clasificar el rol con un modelo a partir del contenido de cada correo.
3. Cascada de señales: directorio corto y curado, partes del expediente en el ERP, perfil aprendido y, por defecto, informativo.

## Decisión

Opción elegida: **«Cascada de señales»**, de la más segura a la más débil, como el resto de la canalización (ADR-0008):

| # | Señal | Qué resuelve | Mantenimiento |
|---|---|---|---|
| 1 | **Directorio curado**: los dominios propios de EShipping y un **registro público de navieras** (sus dominios corporativos y los de sus plataformas de avisos) | Interno y naviera | Corto y estable: unas decenas de entradas. Lo que mueve casi todo el tráfico son pocas navieras |
| 2 | **Partes del expediente en el ERP** (`Línea Transporte`, `Agente Aduana`, `Transportistas`, `Cliente Op.`, `Shipper`, `Consignee`): si el dominio o el nombre visible del remitente coincide con una de ellas, toma su rol | Agente, transportista, naviera y cliente de cada expediente | Ninguno: lo mantiene ya el ERP |
| 3 | **Perfil aprendido** de cada dominio, con lo que el sistema ya sabe de él: qué clase de correos manda y en qué expedientes. Propone un rol con su confianza | La cola larga | Automático. Operaciones solo confirma los pocos dominios que concentran el volumen, y el sistema se los propone ya resueltos |
| 4 | **Por defecto, informativo** (`customer`) | Todo lo demás | — |

- **Coincidencia estricta con el ERP.** El nombre de la parte, sin tildes, espacios, forma jurídica ni palabras de enlace, debe contener la parte del nombre del dominio (o al revés), o aparecer entero en el nombre visible. Compartir una palabra no basta. Si una misma remitente es varias partes, gana la de más autoridad: naviera, agente, transportista y cliente.
- **Orden de las fechas.** Cada entrada del directorio, y cada rol de parte del ERP, puede fijar `month_first`. Sin ese dato, una fecha como `09/10` queda marcada como ambigua (A-09).
- **Trazabilidad.** Cada mensaje registra el rol y la señal que lo decidió (`directory`, `erp` o `default`). El procesado cuenta cuántos mensajes resuelve cada señal.
- **Escala.** El rol se calcula por dominio y se guarda en caché. El perfil aprendido se recalcula en lote (por ejemplo, cada noche). Ninguna de las señales crece con el número de correos.
- **En la PoC** se implementan las señales 1, 2 y 4 (`config/senders.yaml`). La 3 queda diseñada: con 38 correos aprendería de la misma muestra con la que se evalúa.

## Consecuencias

- **Positivas:**
  - Ningún dominio de cliente o proveedor se da de alta a mano.
  - En la muestra real, el resultado es el mismo que con un directorio de los 20 dominios, sin escribir ninguno (evaluación §4). Las señales resuelven así los 363 mensajes asociados: 195 por el directorio (180 propios y 15 de navieras del registro), 89 por las partes del ERP (11 agentes y 78 clientes) y 79 por defecto.
- **Negativas y riesgos asumidos:**
  - La coincidencia con el ERP depende de cómo se escriban los nombres. En la muestra no reconoce a ningún transportista. Esos mensajes quedan como informativos: el error va hacia el lado seguro, pero resta automatización hasta que el perfil aprendido (señal 3) los cubra.
  - El registro de navieras hay que mantenerlo. Es poco trabajo, porque cambia poco.
  - Un remitente de un dominio genérico (por ejemplo, un correo gratuito) solo se reconoce por su nombre visible.
- **Seguimiento:** el informe de procesado da la proporción de mensajes que resuelve cada señal. Si la parte por defecto crece en producción, se prioriza la señal 3. La auditoría por muestreo (`07 §5`) mide los roles equivocados.

## Análisis de las opciones

### Directorio manual de todos los dominios
- ✅ Simple y explicable.
- ❌ No escala con el volumen ni con los remitentes nuevos, y un directorio incompleto degrada el sistema sin avisar.

### Clasificar el rol con un modelo por correo
- ✅ No necesita configuración.
- ❌ Decide la autoridad, lo más delicado de la reconciliación, con la señal menos explicable, y no aprovecha que el ERP ya sabe quién es quién.

### Cascada de señales
- ✅ Escala: lo manual se limita a una lista corta y estable, y el resto sale del ERP y del historial.
- ✅ Equivocarse lleva a lo seguro (informativo) y cada rol dice de qué señal sale.
- ❌ Depende de la calidad de los nombres en el ERP y necesita la señal 3 para la cola larga.
