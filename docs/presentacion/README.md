# Presentación

- `index.html`: la presentación, autocontenida y sin dependencias externas. Se abre en el navegador y se navega con las flechas, `Inicio` y `Fin`. `#N` en la URL abre la diapositiva N.
- `presentacion.pdf`: la misma presentación exportada, en tema claro y con una diapositiva por página.

Todos los ejemplos son sintéticos: la tabla de discrepancias es la salida de `make demo`. Las cifras de la muestra real son agregadas.

Para regenerar el PDF después de cambiar el HTML:

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --no-pdf-header-footer \
  --print-to-pdf=docs/presentacion/presentacion.pdf "file://$PWD/docs/presentacion/index.html"
```
