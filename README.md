# eshipping-ai-challenge

Propuesta para la prueba técnica de Ingeniero IA: un sistema que extrae información operativa de correos de transporte marítimo, la estructura, la asocia a su expediente y la cruza con los datos del ERP para detectar discrepancias.

> **Confidencialidad:** este repositorio no contiene datos reales. Los datos de la prueba se guardan solo en local (`data/`, ignorado por git). `data_sample/` contiene únicamente datos sintéticos.

## Estructura

```
src/          Código de la prueba de concepto (paquete eshipping_ai)
tests/        Tests (solo con datos sintéticos)
data_sample/  Datos sintéticos inventados
data/         Datos reales (local, NO versionado)
```

## Puesta en marcha

Requisitos: Python 3.14 y `make`.

```bash
make setup    # entorno virtual, dependencias de desarrollo y hooks (bloqueo de datos reales incluido)
make check    # lint, tipos y tests, igual que el CI
make migrate  # crea o actualiza la base de datos con las migraciones de Alembic
make sample   # genera los datos sintéticos en data_sample/build/ (correos .eml, ERP en CSV y gold)
make demo     # demo de extremo a extremo sobre los datos sintéticos: run, report y evaluate
make ui       # vista para operativos en Streamlit sobre la base de la demo
```

Uso de la CLI sobre cualquier carpeta de correos `.msg` o `.eml` (ver [diseño de la PoC §5.1](docs/10_diseno_poc.md#51-cli)):

```bash
eshipping run <carpeta> --erp <export.csv> --senders <remitentes.yaml>
eshipping report --format md
eshipping evaluate --gold <gold.json> --verbose
```

Ver [CONTRIBUTING.md](CONTRIBUTING.md) para el flujo de trabajo.

## Documentación

- [Plan de actuación](docs/PLAN.md)
- [Índice de documentación](docs/README.md)
- [Registro de decisiones (ADR)](docs/adr/README.md)
- [CHANGELOG](CHANGELOG.md)

## Estado

Fase F3 (PoC): ingesta, extracción por reglas, asociación, reconciliación y CLI implementadas. Ver el [plan](docs/PLAN.md#4-calendario-e-hitos).
