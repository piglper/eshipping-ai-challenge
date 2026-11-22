# Guía de contribución

Resumen práctico del proceso descrito en el [plan](docs/PLAN.md#9-flujo-de-trabajo-en-git-y-github) y en el [ADR-0003](docs/adr/0003-flujo-de-trabajo-git.md).

## Confidencialidad (lo primero)

`data/` contiene datos reales de EShipping y **nunca** se versiona. No se copian datos reales (clientes, expedientes, bookings, B/L, contenedores, buques, correos ni personas) a código, tests, documentación, issues ni commits. Los tests y `data_sample/` usan solo datos sintéticos. Las reglas completas están en el [ADR-0002](docs/adr/0002-proteccion-datos-confidenciales.md).

Hay tres barreras automáticas: `.gitignore`, el hook de pre-commit y un job del CI que falla si se versiona un fichero confidencial. **Prohibido** saltarse el hook con `--no-verify`.

## Entorno

Requisitos: Python 3.14 y `make`.

```bash
make setup    # crea .venv, instala dependencias de desarrollo y activa los hooks
make check    # lint, tipos y tests: lo mismo que el CI
make help     # resto de comandos
```

El hook `.githooks/pre-commit` comprueba primero la confidencialidad (sin dependencias) y después ejecuta `pre-commit`: ruff, mypy, detección de secretos (gitleaks) y comprobaciones de ficheros.

## Flujo de trabajo

1. **Issue**: toda tarea parte de una issue (plantillas *Tarea*, *Bug* o *Decisión*), con milestone de su fase y etiquetas `type:`, `area:` y `priority:`.
2. **Rama** desde `main`: `tipo/<issue>-<tema>`, con `tipo` en `feat`, `fix`, `docs`, `test` o `chore`. Ejemplo: `feat/31-extractor-contenedores`.
3. **Commits**: [Conventional Commits](https://www.conventionalcommits.org/es/v1.0.0/) en español, atómicos y con referencia a la issue:

   ```
   feat(extraccion): validar el dígito de control ISO 6346

   Refs #31
   ```

4. **Pull request** con la plantilla, CI en verde y autorrevisión del diff. Fusión *squash*; el título del PR es el mensaje final del commit.
5. **Nunca** se hace push directo a `main`.

## Estándares de código

- Código e identificadores en inglés; documentación, commits e issues en español.
- Arquitectura hexagonal: el dominio no depende de adaptadores (ver [PLAN §7](docs/PLAN.md#7-estándares-de-arquitectura)).
- Tipado estricto (mypy `strict`), ruff para lint y formato, docstrings estilo Google.
- Tests con pytest; la lógica nueva llega con sus tests.
- Dependencias con versión fijada en `pyproject.toml`, solo las necesarias.

## Documentación y decisiones

- Toda decisión relevante → ADR nuevo en `docs/adr/` con la [plantilla](docs/adr/template.md) y actualizar el índice. Un ADR aceptado no se reescribe: se sustituye por otro.
- Cambios del plan → historial de revisiones de `docs/PLAN.md` (§15).
- Cambios del producto → `CHANGELOG.md` en `[Unreleased]`.

## Definición de hecho

Ver [PLAN §10](docs/PLAN.md#10-gestión-de-la-calidad).
