# eshipping-ai-challenge

Propuesta para la prueba técnica de Ingeniero IA: un sistema que extrae información operativa de correos de transporte marítimo, la estructura, la asocia a su expediente y la cruza con los datos del ERP para detectar discrepancias.

> **Confidencialidad:** este repositorio no contiene datos reales. Los datos de la prueba se guardan solo en local (`data/`, ignorado por git). `data_sample/` contiene únicamente datos sintéticos.

## Estructura

```
src/          Código de la prueba de concepto
tests/        Tests (solo con datos sintéticos)
data_sample/  Datos sintéticos inventados
data/         Datos reales (local, NO versionado)
```

## Puesta en marcha

```bash
python3 -m venv .venv
source .venv/bin/activate
git config core.hooksPath .githooks   # activa el hook que bloquea datos reales
```

## Estado

En preparación: arquitectura, justificación técnica, estimación de costes, medición de fiabilidad y PoC.
