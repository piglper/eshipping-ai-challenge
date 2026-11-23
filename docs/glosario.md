# Glosario

Términos del dominio y del proyecto, en orden alfabético. Amplía el glosario del enunciado con lo que aparece en los correos, en el ERP y en el diseño.

| Término | Significado |
|---|---|
| **Acarreo** | Transporte por carretera del contenedor entre el almacén del cliente y la terminal portuaria |
| **ATA / ATD** | *Actual Time of Arrival / Departure*: fecha **real** de llegada o salida. En el modelo de eventos, clasificador `ACT` |
| **Booking** | Reserva de espacio en un buque hecha con la naviera; tiene número propio. Es la clave principal para asociar los correos al expediente |
| **B/L (Bill of Lading)** | Conocimiento de embarque. Puede ser original (**OBL**), *Sea Waybill* (**SWB**, no negociable) o liberado por *telex release*. Pasa por borrador (*draft*) antes de emitirse |
| **Circuito (verde, naranja, rojo)** | Nivel de control aduanero de una declaración: sin control, control documental o control físico |
| **Clasificador (`PLN`, `EST`, `ACT`)** | Atributo de cada evento que indica si su fecha es planificada, estimada o real ([ADR-0006](adr/0006-modelo-de-eventos-basado-en-dcsa.md)) |
| **Closing / cut-off** | Fecha y hora límite para entregar la documentación (**DCO**), el VGM (**VCO**) o el contenedor lleno en terminal (**FCO**). Si se pasa, la mercancía no embarca |
| **Contenedor** | Caja estándar identificada por un código ISO 6346: 3 letras del propietario, la categoría (`U`, `J` o `Z`), 6 dígitos de serie y un dígito de control |
| **DCSA** | *Digital Container Shipping Association*: estándares abiertos de las navieras para reservas, B/L y seguimiento de eventos |
| **DUA** | Documento Único Administrativo: declaración aduanera de exportación |
| **Enmienda** (*amendment*) | Modificación de una reserva ya hecha (buque, fecha, equipo…) |
| **ETA / ETD** | *Estimated Time of Arrival / Departure*: fecha **estimada** de llegada o salida. Cambia varias veces; en los correos, «ETA» también se usa para la llegada del buque al **puerto de carga** (A-01) |
| **Evidencia** | Fragmento literal del correo o del PDF del que sale un dato extraído |
| **Expediente** | Cada envío gestionado para un cliente; número único (`ES` + 8 dígitos) en el ERP y en los correos |
| **FCL / LCL** | *Full / Less than Container Load*: contenedor completo o carga agrupada |
| **Gold standard** | Conjunto de referencia etiquetado a mano con el que se mide la PoC; solo existe en local |
| **HC (High Cube)** | Contenedor de mayor altura (9'6"); `40HC` es el tipo más frecuente en la muestra |
| **`known_at`** | Cuándo se supo un dato: fecha del mensaje que lo escribió. Junto con la fecha del evento, hace el modelo bitemporal |
| **Levante** | Autorización de la aduana para que la mercancía salga; se acredita con un documento oficial en PDF |
| **Naviera** | Compañía propietaria de los buques que transportan los contenedores |
| **Omisión de escala** | El buque no hace escala en un puerto previsto; obliga a cambiar la carga a otro buque |
| **POL / POD** | *Port of Loading / Discharge*: puerto de carga y de descarga |
| **Precinto** (*seal*) | Sello numerado que cierra el contenedor; algunos tienen formato parecido al de un contenedor (A-27) |
| **RMT** | Relación de medio de transporte: documento aduanero que agrupa las declaraciones de un buque |
| **Roleo** (*rolled*) | La naviera pasa la carga a un buque posterior por falta de espacio u otros motivos |
| **SI (Shipping Instruction)** | Instrucciones de embarque que envía el cargador para emitir el B/L |
| **TEU** | Unidad equivalente a un contenedor de 20 pies; un 40' son 2 TEU |
| **Transbordo** | Cambio de buque en un puerto intermedio antes de llegar a destino |
| **Transitario** | Empresa que organiza el transporte contratando a navieras, transportistas y otros proveedores |
| **Transportista** | Empresa que mueve la mercancía por carretera |
| **UN/LOCODE** | Código de 5 caracteres de puertos y localidades de Naciones Unidas (país + lugar) |
| **Ventana de carga** | Rango de fechas en el que se puede cargar el contenedor; es un plan (`PLN`), no una fecha |
| **VGM** | *Verified Gross Mass*: peso bruto verificado del contenedor, obligatorio antes de embarcar (SOLAS) |
| **Veredicto** | Resultado de comparar un campo con el ERP: coincide, falta en el ERP, error del ERP, ERP más reciente, discrepancia, falta en el correo o sin columna en el ERP |
