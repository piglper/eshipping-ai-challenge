# ADR-0007: Monolito modular desplegado como workers por etapa detrás de colas

- **Estado:** Aceptado
- **Fecha:** 2026-11-23
- **Decisores:** Pablo Iglesias Peral
- **Referencias:** issues #15 y #16, [arquitectura](../04_arquitectura.md)

## Contexto y problema

Hay que decidir cómo se estructura y se despliega el sistema que procesa los correos: un único proceso, varios servicios o funciones independientes. La decisión condiciona la escalabilidad (RNF-01, RNF-02), la latencia de los urgentes (RNF-03), la idempotencia (RNF-04), la mantenibilidad (RNF-40) y el coste de operación.

El análisis de capacidad ([arquitectura §9](../04_arquitectura.md#9-análisis-de-capacidad-f21b)) muestra que el volumen es modesto en cómputo: unos 23 correos por minuto en el pico con 100.000 al mes y menos de 1,5 núcleos en el pico con 300.000 al mes. Las etapas tienen perfiles distintos (OCR intensivo en CPU, LLM limitado por un proveedor externo, reconciliación que se serializa por expediente) y fallan de forma distinta.

## Factores de decisión

- Crecer de 100.000 a 150.000 o 300.000 correos al mes solo con configuración y réplicas.
- Aislar los fallos de una etapa (proveedor de LLM caído, PDF corrupto) para que no paren las demás.
- Un único modelo de dominio y un único lugar donde cambiar las reglas.
- Coste y complejidad de operación acordes a un equipo pequeño.
- Que la PoC y la producción compartan el código, cambiando solo los adaptadores.

## Opciones consideradas

1. **Proceso único por lotes** (un script programado que procesa todo lo pendiente).
2. **Monolito modular desplegado como workers por etapa detrás de colas.**
3. **Microservicios** por etapa, con su propio repositorio, despliegue y almacenamiento.
4. **Funciones sin servidor** por etapa, encadenadas por eventos de la nube.

## Decisión

Opción elegida: **«Monolito modular desplegado como workers por etapa detrás de colas»**.

Un único paquete con arquitectura hexagonal y varios puntos de entrada (`worker --stage=parse|document|extract|reconcile`, `ingest`, `erp-sync`, `api`). Se construye una sola imagen y cada rol se despliega con su número de réplicas. Las etapas se comunican por colas a través del puerto `TaskQueue`; en la PoC, el adaptador es una cola en proceso, síncrona, con el mismo contrato.

Es la opción más simple que cumple a la vez el aislamiento de fallos, el escalado por etapa y la latencia de los urgentes, sin el coste de operar microservicios para un volumen que no los necesita.

## Consecuencias

- **Positivas:**
  - Crecer es cambiar réplicas y concurrencia por rol; ninguna etapa limita a las demás.
  - Un solo modelo de dominio, un solo repositorio y un solo flujo de CI.
  - La PoC ejecuta el mismo código de dominio y aplicación que producción.
  - Si en el futuro una etapa necesita separarse (por ejemplo, el OCR en máquinas con GPU), ya está aislada detrás de una cola y un puerto: separarla es un cambio de despliegue.
- **Negativas y riesgos asumidos:**
  - Hay que operar un servicio de colas (D8, #28) y vigilar su cola pendiente y sus mensajes fallidos.
  - Un cambio de código redespliega todos los roles a la vez (aceptable con este tamaño de equipo y despliegues sin corte).
  - Hay que mantener la disciplina de las fronteras entre módulos; se comprueba con contratos de importación en el CI.
- **Seguimiento:** la prueba de volumen (F4.5, #44) confirma el rendimiento por worker; en producción, las métricas de cola pendiente y de latencia por etapa indican si algún rol necesita más réplicas o separarse.

## Análisis de las opciones

### Proceso único por lotes
- ✅ Lo más simple de construir y operar.
- ❌ No cumple la latencia de los urgentes (RNF-03) salvo ejecutándolo cada pocos minutos, y entonces se convierte en un sondeo frágil.
- ❌ Un fallo (proveedor de LLM caído, un PDF corrupto) para todo el lote.
- ❌ Escalar es hacer el proceso más grande, no repartirlo.

### Monolito modular con workers por etapa
- ✅ Escalado y aislamiento por etapa con un solo código.
- ✅ Prioridades por cola y reintentos por tarea.
- ✅ Encaja con la arquitectura hexagonal: la cola es otro puerto.
- ❌ Necesita un servicio de colas y observabilidad por etapa.

### Microservicios
- ✅ Despliegue y escalado totalmente independientes.
- ❌ Varios repositorios, contratos entre servicios versionados y bases de datos separadas: mucho coste de operación para menos de 2 núcleos de carga.
- ❌ El modelo de dominio (expediente, evento) se reparte entre servicios o se duplica.

### Funciones sin servidor
- ✅ Sin servidores que gestionar; pago por uso.
- ❌ Límites de duración y memoria poco adecuados para OCR y para el LLM autoalojado.
- ❌ Más acoplamiento a una nube concreta y pruebas locales más difíciles.
- ❌ El ahorro es pequeño con una carga continua durante todo el horario laboral.
