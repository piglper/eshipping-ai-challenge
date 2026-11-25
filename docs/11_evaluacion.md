# Evaluación de la PoC frente al gold standard

| Campo | Valor |
|---|---|
| Versión | 0.1.0 |
| Estado | Borrador |
| Responsable | Pablo Iglesias Peral |
| Última actualización | 25/11/2026 |
| Tarea | F4.2 (#40) |
| Requisitos | RF-10, RF-20, RF-52, RNF-01, RNF-10, RNF-11 |
| Documentos relacionados | [01 §6](01_analisis_datos.md#6-gold-standard-f13) (gold standard), [07](07_fiabilidad.md) (qué se mide y por qué), [ADR-0009](adr/0009-politica-de-resolucion-de-discrepancias.md) (veredictos) |

> **Confidencialidad:** sin datos reales. De la muestra real solo se publican cifras agregadas; el informe con los fallos, que nombra expedientes, se queda en `data/output/` (ignorado por git).

## 1. Resumen

- La evaluación mide cuatro cosas: la **asociación** de cada correo a su expediente, su **clase**, el **valor de cada campo** y el **veredicto** frente al ERP. Cada proporción lleva su intervalo de confianza de Wilson al 95 %.
- Es reproducible con un comando: `make evaluate` sobre los datos sintéticos y `make evaluate-real` sobre la muestra real, solo en local.
- Sobre el conjunto sintético, la asociación, la extracción y los veredictos aciertan en todos los casos. La clase principal falla en 3 de 14 correos: los avisos de buque se toman por reservas. Ese fallo se analiza en la F4.3.
- Los resultados de la muestra real están en la [sección 4](#4-resultados-sobre-la-muestra-real).

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
| Exactitud de la clase principal | 11/14 = 78,6 % [52,4 % - 92,4 %] |
| Precisión y recall de la extracción | 27/27 = 100,0 % [87,5 % - 100,0 %] |
| Veredicto exacto | 28/28 = 100,0 % [87,9 % - 100,0 %] |
| Detección de lo que pide acción (precisión y recall) | 6/6 = 100,0 % [61,0 % - 100,0 %] |

Los tres fallos de clase son avisos de buque (`VSL`) y un correo de otro tipo (`OTR`) que las reglas clasifican como reserva (`BKG`). Esos correos mencionan el booking, y la palabra «booking» pesa más que el vocabulario del buque.

## 4. Resultados sobre la muestra real

*Pendiente: se completa al ejecutar `make evaluate-real` con el directorio de remitentes real.*

## 5. Limitaciones

- **Muestra pequeña.** 11 expedientes, 38 correos y 85 veredictos puntuables: los intervalos son anchos y ninguna cifra demuestra los objetivos de RNF-10 (99,5 %) ni de RNF-11 (98 %). Para eso hacen falta unos 765 y 190 casos sin errores ([07 §6.1](07_fiabilidad.md#61-qué-se-puede-demostrar-con-el-gold-standard)).
- **Gold provisional.** Lo etiquetó Claude Code y está pendiente de revisión humana (`meta.review`), con un solo etiquetador.
- **Un solo tipo de expediente** (exportación marítima FCL desde España).
- **El orden de los correos incrustados** es el del fichero. Si un mismo correo aparece en dos contenedores, se guarda una vez y cuenta en el primero; en el segundo queda sin emparejar y se cuenta como no encontrado.

## 6. Cómo reproducirlo

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
| 0.1.0 | 25/11/2026 | Primera versión: metodología, métricas con intervalo de Wilson y resultados sobre el conjunto sintético (F4.2) |
