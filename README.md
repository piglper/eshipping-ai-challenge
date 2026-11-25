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
make volume   # prueba de volumen: ~10.000 mensajes sintéticos sin LLM
```

Uso de la CLI sobre cualquier carpeta de correos `.msg` o `.eml` (ver [diseño de la PoC §5.1](docs/10_diseno_poc.md#51-cli)):

```bash
eshipping run <carpeta> --erp <export.csv> --senders <remitentes.yaml>
eshipping report --format md
eshipping evaluate --gold <gold.json> --verbose
```

### Cómo probarlo

Todo funciona con los datos sintéticos de `data_sample/` y sin conexión; el LLM es opcional.

1. **Comprobar el código:** `make check` ejecuta lint, tipos y los tests con cobertura, como el CI. `make test-unit` lanza solo los tests rápidos y `make test-integration`, los de extremo a extremo sobre los datos sintéticos. `HYPOTHESIS_PROFILE=thorough make test` ejecuta los tests de propiedades con 5.000 ejemplos cada uno.
2. **Ver la canalización completa:** `make demo` genera los datos sintéticos (cuatro expedientes y un correo de ruido) y los procesa. Después muestra el informe de discrepancias, con lo urgente primero, y el acierto frente al gold. El resultado esperado es un `URGENTE ES26900002: vessel DISCREPANCY` y un 100 % de acierto del veredicto.
3. **Revisar como un operativo:** `make ui` abre en el navegador la vista para operativos sobre la base de la demo, con las discrepancias por prioridad, el expediente con su línea temporal y la corrección.
4. **Con el LLM local (opcional):** con [Ollama](https://ollama.com) en marcha y el modelo descargado (`ollama pull qwen3.5:4b`, el de por defecto), `make demo-llm` repite la demo con el escalón del LLM para los campos que las reglas no resuelven. Con `MODEL=<modelo>` se usa otro.
5. **Prueba de volumen:** `make volume` genera unos 10.000 mensajes sintéticos (2.860 expedientes) y los procesa en alrededor de un minuto. Informa de los segundos por etapa y deja la evaluación en `data_sample/build/volume/evaluacion.md`, que debe dar el mismo acierto que la demo.
5. **Sobre otra carpeta de correos:** `eshipping run <carpeta> --erp <export.csv> --no-llm`, seguido de `eshipping report`. Los resultados de datos reales deben guardarse con `--workdir data/output/...`, que está ignorado por git.

Ver [CONTRIBUTING.md](CONTRIBUTING.md) para el flujo de trabajo.

## Documentación

- [Plan de actuación](docs/PLAN.md)
- [Índice de documentación](docs/README.md)
- [Registro de decisiones (ADR)](docs/adr/README.md)
- [CHANGELOG](CHANGELOG.md)

## Estado

Fase F3 (PoC) cerrada con `v0.4.0`: canalización de extremo a extremo con CLI, escalón del LLM local y vista para operativos. Siguiente: F4 (evaluación). Ver el [plan](docs/PLAN.md#4-calendario-e-hitos).
