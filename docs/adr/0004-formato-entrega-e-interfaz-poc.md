# ADR-0004: Formato de entrega e interfaz de la PoC

- **Estado:** Aceptado
- **Fecha:** 2026-11-21
- **Decisores:** Pablo Iglesias Peral
- **Referencias:** apartado 8 del enunciado (Entregables), decisiones D2 y D3

## Contexto y problema

El enunciado pide documentos (arquitectura, justificación, costes, fiabilidad) y una PoC funcional que admita correos nuevos y muestre la extracción, la clasificación, la organización por expediente, el cruce con el ERP y las discrepancias. Hay que decidir cómo se presenta todo y con qué interfaz se demuestra la PoC.

## Factores de decisión

- Claridad para un público mixto: negocio y técnicos.
- Que la demo sea visual en la entrevista y además reproducible.
- Demostrar el flujo con el humano en el bucle (validación del operativo), que es la base del aprendizaje continuo.

## Opciones consideradas

**Entrega:** a) presentación en PDF o HTML con acceso opcional al repositorio · b) solo el repositorio · c) solo un documento.

**Interfaz:** a) CLI y Streamlit · b) solo CLI · c) aplicación web completa.

## Decisión

- **Entrega:** una **presentación final en PDF o HTML** (el formato lo elige el responsable) generada a partir de la documentación del repositorio. Se ofrece **acceso al repositorio privado** a los técnicos que quieran revisar el código y el proceso.
- **Interfaz:** **CLI y Streamlit**. La CLI es la interfaz principal, scriptable y reproducible (procesar, informar, evaluar). Streamlit ofrece una vista para operativos: expedientes, línea temporal de eventos, discrepancias, y validar o corregir.

## Consecuencias

- **Positivas:** la demo es visual y la PoC sigue siendo comprobable por línea de comandos. Streamlit permite enseñar en vivo cómo las correcciones alimentan el aprendizaje.
- **Negativas:** Streamlit añade algo de trabajo en F3. Si hay retraso, se reduce a una sola vista (principio de alcance protegido).
- **Seguimiento:** las capturas para la presentación se hacen solo con `data_sample/` (ADR-0002).
