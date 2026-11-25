# Presentación

- `index.html`: la presentación para la entrevista, con 21 diapositivas en el estilo corporativo de EShipping. Está organizada por público (operativa, arquitectura, sistemas y RRHH) y dedica una diapositiva o más a cada pregunta del enunciado (§7). Se abre en el navegador y se navega con las flechas, `Inicio` y `Fin`; `#N` en la URL abre la diapositiva N.
- `presentacion.pdf`: la misma presentación exportada, con una diapositiva por página y **sin el logo**.
- `img/`: capturas de `make ui` sobre la base de `make demo`, con datos sintéticos.
- `fonts/`: IBM Plex Sans, la tipografía de los documentos de EShipping, con licencia SIL Open Font License (`fonts/OFL.txt`). La presentación funciona sin conexión.

## El logo no se versiona

El logo sale del PDF del enunciado, que está en `data/`, y la regla 1 de confidencialidad prohíbe versionar nada de esa carpeta. Por eso:

- La presentación carga el logo desde `data/output/presentacion/logo.png`, que está ignorado por git. Si no existe, muestra el nombre «EShipping» en texto.
- Con `?sinlogo` en la URL se fuerza la versión sin logo. Así se exporta el PDF versionado.
- La copia con logo para presentar, `data/output/presentacion/presentacion_eshipping.pdf`, tampoco se versiona, y se borra con el resto de `data/` al terminar el proceso de selección.

## Regenerar los PDF

```bash
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
# Versionado, sin logo
"$CHROME" --headless=new --no-pdf-header-footer --virtual-time-budget=4000 \
  --print-to-pdf=docs/presentacion/presentacion.pdf "file://$PWD/docs/presentacion/index.html?sinlogo"
# Local, con logo (no se versiona)
"$CHROME" --headless=new --no-pdf-header-footer --virtual-time-budget=4000 \
  --print-to-pdf=data/output/presentacion/presentacion_eshipping.pdf "file://$PWD/docs/presentacion/index.html"
```
