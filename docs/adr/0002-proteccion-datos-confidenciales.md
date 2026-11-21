# ADR-0002: Protección de los datos confidenciales

- **Estado:** Aceptado
- **Fecha:** 2026-11-21
- **Decisores:** Pablo Iglesias Peral
- **Referencias:** apartado 4 del enunciado (Confidencialidad), `CLAUDE.md`

## Contexto y problema

Los correos y el CSV contienen información real de EShipping, de sus clientes y de sus proveedores. El enunciado prohíbe publicarlos o compartirlos, total o parcialmente, y obliga a declarar cualquier envío a servicios externos y a borrar todas las copias al terminar. Al mismo tiempo, el repositorio debe poder mostrarse a los técnicos.

## Factores de decisión

- Riesgo cero de que los datos reales lleguen al repositorio remoto.
- Poder hacer una demo y tests reproducibles sin datos reales.
- Defensa en profundidad: que un único error humano no provoque una fuga.

## Opciones consideradas

1. Datos solo en local (`data/`, ignorado), con controles automáticos en git y datos sintéticos para tests y demo.
2. Cifrar los datos dentro del repositorio (git-crypt, SOPS).
3. Disciplina manual, sin controles.

## Decisión

Opción elegida: **datos solo en local, con controles en varias capas**:

1. `.gitignore`: `data/`, `*.csv`, `*.eml`, `*.msg`, `*.pst`, `*.mbox`, `.env`.
2. Hook de pre-commit versionado (`.githooks/`) que bloquea esos ficheros aunque se fuercen con `git add -f`.
3. Detección de secretos en el pre-commit (se añade en F0.5).
4. Las salidas derivadas de datos reales se guardan en `data/output/`.
5. Tests, demo y capturas solo con datos sintéticos (`data_sample/`).
6. Los mensajes de commit, las issues, los PR y la documentación describen patrones, nunca contenido real.
7. Se prohíbe `--no-verify`. Se revisa `git status` y el diff antes de cada push.
8. Borrado de todas las copias al cerrar el proceso (F6 del plan).

## Consecuencias

- **Positivas:** el repositorio se puede compartir sin riesgo; la demo es reproducible por terceros.
- **Negativas:** los datos sintéticos hay que crearlos, y las métricas sobre datos reales solo se pueden reproducir en local.
- **Seguimiento:** auditoría de confidencialidad en F5 (búsqueda en el repositorio y en su historial).

## Análisis de las opciones

### Cifrado dentro del repositorio
- ✅ Los datos viajan con el repositorio.
- ❌ Sigue siendo «subir los datos», en contra del espíritu del enunciado; riesgo si se filtra la clave.

### Disciplina manual
- ✅ Sin coste de configuración.
- ❌ Un solo `git add .` provoca una fuga irreversible.
