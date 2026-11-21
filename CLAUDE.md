# CLAUDE.md — Prueba técnica EShipping (Ingeniero IA)

## Reglas de confidencialidad (OBLIGATORIAS)

`data/` contiene datos reales y confidenciales de EShipping (correos `.msg`, CSV del ERP DEIWORLD y el enunciado de la prueba).

1. **Nunca** versionar, subir ni compartir nada de `data/`, ni ficheros `*.csv`, `*.eml`, `*.msg`.
2. **No copiar datos reales fuera de `data/`**: ni a `src/`, `tests/`, `data_sample/`, README, docs, logs, fixtures, prompts de ejemplo ni mensajes de commit. Esto incluye nombres de clientes, números de expediente, bookings, B/L, contenedores, buques, correos y personas.
3. `data_sample/` y los tests solo contienen **datos sintéticos inventados**.
4. No modificar los ficheros de `data/`. Los resultados del procesado de datos reales van a una carpeta ignorada por git (dentro de `data/`, p. ej. `data/output/`).
5. No enviar datos reales a servicios externos (APIs de LLM, la nube, webs) sin que el usuario lo autorice explícitamente; si se hace, documentarlo en la propuesta junto con cómo se protegen.
6. Antes de cada commit/push, revisar `git status` y el diff. El hook `.githooks/pre-commit` (activado con `git config core.hooksPath .githooks`) bloquea esos ficheros; no saltárselo (`--no-verify` prohibido).
7. Al terminar el proceso de selección hay que borrar todas las copias de los datos reales (incluidas las salidas derivadas y el entorno local).

## Enfoque del trabajo

- La prioridad es el **planteamiento del problema y la solución** (arquitectura, justificación, costes, fiabilidad, ambigüedad entre fuentes), no una PoC espectacular.
- La PoC debe ser sencilla y funcional: extracción, clasificación, asociación a expediente, cruce con el ERP y discrepancias.

## Entorno

- macOS, Python en `.venv/` (`source .venv/bin/activate`).
- Estructura: `src/` (código), `tests/` (tests con datos sintéticos), `data_sample/` (datos sintéticos), `data/` (real, ignorado).

## Proceso y documentación (ver `docs/PLAN.md`)

- Seguir el plan `docs/PLAN.md` y mantenerlo al día: todo cambio del plan se apunta en su historial de revisiones (§15).
- Toda decisión relevante → ADR nuevo en `docs/adr/` (plantilla MADR) y actualizar el índice. Los ADR aceptados no se reescriben: se sustituyen.
- Cambios del producto → `CHANGELOG.md` (Keep a Changelog + SemVer).
- GitHub Flow: nunca push directo a `main`; rama `tipo/<issue>-<tema>`, PR con plantilla, fusión squash.
- Conventional Commits en español, con referencia a la issue. Código en inglés, documentación en español.
- Estándares: arquitectura hexagonal, tipado estricto, ruff, mypy, pytest. Calidad de nivel profesional: el repositorio lo pueden revisar los técnicos de EShipping.
