# ADR-0012: Despliegue en contenedores portables sobre un servicio gestionado de la UE, sin Kubernetes

- **Estado:** Aceptado
- **Fecha:** 2026-11-23
- **Decisores:** Pablo Iglesias Peral
- **Referencias:** decisión D8, issue #28, [arquitectura §5 y §9](../04_arquitectura.md), [costes §4 y §5](../06_costes.md#4-requisitos-de-máquina), [seguridad](../09_seguridad.md), [ADR-0007](0007-monolito-modular-con-workers-por-etapa.md), [ADR-0010](0010-proveedor-de-llm-de-produccion.md), [ADR-0011](0011-almacenamiento-postgresql-y-almacen-de-objetos.md)

## Contexto y problema

El [ADR-0007](0007-monolito-modular-con-workers-por-etapa.md) despliega una sola imagen con roles por etapa (`ingest`, `parse`, `document`, `extract`, `reconcile`, `erp-sync`, `api`) detrás de colas. El análisis de capacidad (arquitectura §9) muestra una carga pequeña: menos de 1,5 núcleos en el pico con 300.000 correos al mes, unos 9 vCPU y 15 GB en total contando las réplicas por disponibilidad (costes §4). Falta decidir dónde y cómo se despliega, y con qué servicio de colas.

No se sabe qué nube usa EShipping ni si tiene alguna (pregunta añadida en [seguridad §10](../09_seguridad.md#10-preguntas-para-eshipping)). Los correos `.msg` y los avisos por Teams sugieren Microsoft 365, lo que haría natural Azure, pero es una suposición.

## Factores de decisión

- **Residencia en la UE** y contratos de encargado (RNF-30, RNF-31).
- **Poca operación** para el equipo de EShipping: parches, copias, alta disponibilidad.
- **Escalado por configuración y réplicas** (PLAN §7.2): cada rol escala por la cola pendiente.
- **Portabilidad** entre nubes y a local: no depender de servicios propietarios en el núcleo.
- **Coste** proporcionado a una carga pequeña.
- **Integración** con el buzón (Microsoft Graph), el directorio corporativo (inicio de sesión único) y el proveedor de LLM (ADR-0010).

## Opciones consideradas

1. **Kubernetes gestionado** (AKS, EKS o GKE) con Helm.
2. **Servicio gestionado de contenedores sin Kubernetes** (Azure Container Apps, AWS ECS con Fargate o Google Cloud Run) con base de datos y almacén de objetos gestionados, en la nube que ya use EShipping.
3. **Máquinas virtuales en un proveedor europeo** con Docker Compose (la referencia de precio de [costes C-08](../06_costes.md#2-supuestos)).
4. **Servidores propios** de EShipping.

## Decisión

Opción elegida: **«Contenedores portables; despliegue de referencia en un servicio gestionado de contenedores, en una región de la UE de la nube que ya use EShipping»**, con la opción 3 como alternativa documentada.

- **Artefactos portables:** una imagen OCI única, configuración por variables y ficheros versionados, e infraestructura como código (Terraform u OpenTofu). Nada del núcleo depende de un servicio propietario: los adaptadores (`TaskQueue`, `Repository`, almacén de objetos, `LLMClient`) aíslan esas diferencias.
- **Referencia:** cada rol es una aplicación del servicio gestionado de contenedores, con escalado por la cola pendiente (en Azure Container Apps, con KEDA y su escalador de PostgreSQL; en las otras nubes, el equivalente), mínimo dos réplicas en los roles con disponibilidad, PostgreSQL gestionado con alta disponibilidad ([ADR-0011](0011-almacenamiento-postgresql-y-almacen-de-objetos.md)), almacén de objetos gestionado y gestor de secretos de la nube.
- **Si EShipping no tiene nube**, o prefiere un coste mínimo: máquinas virtuales en un proveedor europeo con Docker Compose y las mismas imágenes; es el escenario de coste de [costes §5](../06_costes.md#5-coste-técnico-mensual) (unos 300 € al mes de infraestructura).
- **Sin Kubernetes:** a esta escala (unos 13 procesos) su operación cuesta más que lo que aporta. Se reconsidera si EShipping ya opera un clúster o si se superan unas decenas de servicios.
- **Colas:** sobre PostgreSQL con `SKIP LOCKED` ([ADR-0011](0011-almacenamiento-postgresql-y-almacen-de-objetos.md)). Se cambia a una cola gestionada (Azure Service Bus, Amazon SQS o Pub/Sub) mediante un adaptador si se superan unas 500 tareas por segundo o si se necesita entregar eventos a otros sistemas.
- **Entornos:** desarrollo (datos sintéticos), preproducción y producción, cada uno con sus secretos y su cuenta de servicio.
- **Entrega continua:** la CI construye y firma la imagen; el despliegue es gradual por rol, con vuelta atrás a la versión anterior.
- **Observabilidad:** OpenTelemetry para métricas y trazas, con el servicio de la nube o Prometheus y Grafana en la opción 3.

## Consecuencias

- **Positivas:**
  - Escalado por rol y por cola sin operar un orquestador; parches, copias y alta disponibilidad a cargo del proveedor.
  - Se puede desplegar en cualquier nube o en máquinas propias con las mismas imágenes.
  - Encaja con la vía de residencia en la UE del LLM: si EShipping usa AWS o Google Cloud, el escenario de referencia del [ADR-0010](0010-proveedor-de-llm-de-produccion.md) (Claude vía Bedrock o Vertex en la UE) queda en la misma nube.
- **Negativas y riesgos asumidos:**
  - Los servicios gestionados cuestan más que la opción 3 a cambio de menos operación; el coste concreto depende de la nube y no se ha calculado para cada una.
  - Cada servicio gestionado tiene sus límites (tiempo máximo de ejecución, tamaño de imagen, red): se confirman al elegir la nube.
  - La elección final de la nube depende de la respuesta de EShipping.
- **Seguimiento:** cuando se conozca la nube de EShipping, concretar los servicios y el coste en un ADR que concrete este.

## Análisis de las opciones

### Kubernetes gestionado
- ✅ Estándar, portable, escalado fino.
- ❌ Para 13 procesos, la operación (actualizaciones del clúster, red, políticas, Helm) supera el beneficio, salvo que EShipping ya lo opere.

### Servicio gestionado de contenedores
- ✅ Escalado por cola, poca operación, integración con la identidad y los secretos de la nube.
- ❌ Algo de dependencia del proveedor en el despliegue (no en el código).

### Máquinas virtuales europeas con Docker Compose
- ✅ La opción más barata y simple; proveedor europeo.
- ❌ Alta disponibilidad, parches, copias y escalado son trabajo del equipo; sin integración con la identidad corporativa de serie.

### Servidores propios
- ✅ Control total de los datos.
- ❌ Hardware, alta disponibilidad y seguridad física a cargo de EShipping; solo tiene sentido si P-10 obliga a no usar la nube, y entonces con el LLM autoalojado.
