# Documentación

Índice de la documentación del proyecto. Toda la documentación sigue el enfoque *docs-as-code* descrito en el [plan](PLAN.md#8-estándares-de-documentación).

| Documento | Contenido | Fase | Estado |
|---|---|---|---|
| [00_resumen_ejecutivo.md](00_resumen_ejecutivo.md) | Resumen ejecutivo de una página: la respuesta a cada pregunta del enunciado | F5 | ✅ |
| [presentacion/](presentacion/index.html) | Presentación final: HTML autocontenido y su PDF ([cómo se regenera](presentacion/README.md)) | F5 | ✅ |
| [PLAN.md](PLAN.md) | Plan de actuación, estándares e historial de revisiones | F0 | ✅ |
| [adr/](adr/README.md) | Registro de decisiones de arquitectura y de proyecto | Todas | 🔄 En curso |
| [../CHANGELOG.md](../CHANGELOG.md) | Cambios del proyecto por versión | Todas | 🔄 En curso |
| [01_analisis_datos.md](01_analisis_datos.md) | Análisis de los correos y del ERP (sin datos reales) | F1 | ✅ |
| [02_requisitos.md](02_requisitos.md) | Requisitos funcionales y no funcionales, supuestos y preguntas para EShipping | F1 | ✅ |
| [03_taxonomia_y_ambiguedades.md](03_taxonomia_y_ambiguedades.md) | Taxonomía de correos y eventos (DCSA) y catálogo de ambigüedades | F1 | ✅ |
| [glosario.md](glosario.md) | Glosario de dominio | F1 | ✅ |
| [04_arquitectura.md](04_arquitectura.md) | Arquitectura (C4), funcionamiento de la canalización y análisis de capacidad | F2 | ✅ |
| [05_modelo_datos.md](05_modelo_datos.md) | Modelo de datos, linaje y bitemporalidad | F2 | ✅ |
| [06_costes.md](06_costes.md) | Coste del LLM por proveedor, requisitos de máquina y coste técnico mensual y por correo | F2, F4 | ✅ |
| [07_fiabilidad.md](07_fiabilidad.md) | Métricas, confianza calibrada, umbrales y auditoría | F2 | ✅ |
| [08_aprendizaje_continuo.md](08_aprendizaje_continuo.md) | Aprendizaje continuo sin aprender de errores | F2 | ✅ |
| [09_seguridad.md](09_seguridad.md) | Seguridad, privacidad y servicios externos | F2 | ✅ |
| [10_diseno_poc.md](10_diseno_poc.md) | Diseño de la PoC: qué se implementa, qué se simplifica y orden de implementación | F2 | ✅ |
| [11_evaluacion.md](11_evaluacion.md) | Metodología y resultados de la evaluación de la PoC frente al gold standard | F4 | ✅ |

> Ningún documento contiene datos reales de EShipping. Ver el [ADR-0002](adr/0002-proteccion-datos-confidenciales.md).
