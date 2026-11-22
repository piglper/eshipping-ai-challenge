## Contexto

<!-- Qué problema resuelve y por qué. Issue relacionada: Closes #<n> -->

## Cambios

-

## Cómo probarlo

```bash
make check
```

## Decisiones

<!-- ADR nuevos o afectados. Si no hay, borrar la sección. -->

## Checklist de confidencialidad

- [ ] Ningún fichero de `data/` ni `*.csv`, `*.eml` o `*.msg`
- [ ] Sin identificadores reales (expedientes, bookings, B/L, contenedores, buques, clientes, personas) en código, tests, docs ni commits
- [ ] Los datos de tests y ejemplos son sintéticos

## Definición de hecho

- [ ] `make check` pasa (ruff, mypy y tests) y el CI está en verde
- [ ] Tests nuevos para la lógica nueva
- [ ] Documentación, plan, ADR y `CHANGELOG.md` actualizados si aplica
