# Lector PDF — motor conjunto, etapa 1

Primera refactorización de `LectorPdf.ipynb`. Se separan las ocho secciones, la
configuración de la plantilla, los recursos compartidos y el contrato de salida.
El cuaderno original se conserva intacto. No incluye todavía aplicación de
escritorio, exportación Excel ni lectura de la segunda página.

## Alcance

Crédito, información básica, laboral, actividad económica, cónyuge, información
financiera, inmuebles/vehículos y operaciones internacionales. Conserva las reglas
del cuaderno recibido, incluida la dependencia de Independiente, campos opcionales
y las operaciones financieras no verificables por componentes vacíos.

Solo analiza el contenido de la página 1. La página 2 está pendiente; el límite
final del proyecto seguirá siendo las primeras dos páginas. Un archivo con diseño
diferente no debe considerarse automáticamente compatible.

## Estructura

```text
lector_pdf/
  motor.py                 Procesar PDF y lotes
  recursos.py              Sesión PDF y servicio OCR compartidos
  esquema.py               Resultado común y serialización
  configuracion.py         Carga de coordenadas y opciones
  plantillas/unimos_v1.json
  secciones/               Las ocho secciones del cuaderno
tests/test_motor.py
Colab_Motor_Unificado.ipynb
requirements.txt
```

Las secciones conservan inicialmente sus validadores específicos para evitar
cambiar resultados durante la migración. La consolidación adicional de funciones
de casillas, importes y normalización queda como siguiente refactorización, guiada
por pruebas de equivalencia. Todavía no es un instalador de producción.

## Probar en Colab

Suba `Colab_Motor_Unificado.ipynb` y ejecute sus celdas en orden. El cuaderno incluye
el código del paquete: no necesita subir los archivos Python por separado.
Instala dependencias, carga una sola vez los PDF del lote, procesa todas sus secciones
y permite descargar resultados JSON y versiones instaladas. No contiene datos de
solicitantes ni salidas guardadas.

El modelo OCR se descarga al usarlo por primera vez. Los documentos se procesan
en la sesión de Colab. Una ejecución local utiliza los archivos del equipo.

## Ejecución local

Desde esta carpeta, en un entorno virtual:

```powershell
python -m pip install -r requirements.txt
python -m lector_pdf "C:\carpeta\pdfs" --salida resultados.json
```

También acepta varias rutas individuales. Instale una versión de Python compatible
con las ruedas de PaddlePaddle para su plataforma. Las dependencias aún no están
congeladas: capture primero las versiones del entorno donde se valide el OCR.

## Uso desde otra aplicación

```python
from lector_pdf.motor import MotorPDF

motor = MotorPDF()
resultado = motor.procesar_pdf("solicitud.pdf")
resultados = motor.procesar_lote(["solicitud_1.pdf", "solicitud_2.pdf"])
```

Reutilice el mismo motor para compartir el modelo OCR. El procesamiento es
secuencial; no use el mismo motor simultáneamente desde varios hilos.

## Resultado común

Cada documento incluye identificador SHA-256 del contenido, versión de esquema,
plantilla, secciones, campos, errores y métricas. Un archivo idéntico tendrá el mismo
identificador; no se eliminan duplicados automáticamente.

Cada campo incluye:

- `id`, `seccion`, `campo`, `pagina`.
- `valor_original`, `original_disponible`, `valor_normalizado`.
- `lectura`: leido, vacio, sin_lectura o error.
- `validacion`: conserva el estado de la regla del cuaderno.
- `motivo`, `metodo`, `confianza_ocr`.

Los importes enteros se serializan como números. Los decimales no enteros se
serializan como texto decimal exacto para evitar pérdida de precisión al generar
JSON. El exportador Excel deberá convertirlos explícitamente a su tipo de celda.
Identificaciones y códigos continúan como texto; un vacío es null, distinto de cero.

Cuando el extractor anterior no conservaba la transcripción original, no se inventa:
`original_disponible` es false. El futuro enriquecimiento deberá recuperar esa
evidencia desde la lectura. `secciones` conserva además los resultados originales
de los extractores para auditar la migración y mantener las comprobaciones financieras.

`estado_proceso` indica COMPLETADO, PARCIAL o ERROR técnico. COMPLETADO **no significa**
que la solicitud cumpla todas las reglas: consulte las validaciones de campos y
secciones. RECHAZADO describe incumplimiento de diligenciamiento, no una decisión
de aprobación crediticia. Un OCR sin lectura puede seguir siendo opcional, pero
`lectura=sin_lectura` evita presentarlo como vacío confirmado.

## Optimización incorporada

- Una carga de archivos por lote.
- Una apertura de pdfplumber por documento, compartida por las ocho secciones.
- Una apertura de PyMuPDF por documento cuando el OCR la necesita.
- Caché de páginas y caracteres de pdfplumber al compartir el documento.
- Un modelo OCR por motor, inicializado al primer uso; `enable_mkldnn=False`.
- Cuatro recortes OCR: profesión, empresa del solicitante, nombre y empresa del cónyuge.
- Fallos aislados por archivo/sección y métricas de tiempo, aperturas y llamadas OCR.

No se ha implementado todavía un índice espacial de caracteres, caché persistente,
paralelismo ni medición de memoria. No se promete una mejora porcentual de velocidad
sin medir OCR en el entorno final. El primer archivo puede tardar más por carga del modelo.

## Pruebas y límites de verificación

```powershell
python -m unittest discover -s tests -v
```

Para verificar también las muestras y compararlas con el cuaderno original:

```powershell
$env:PDF_TEST_DIR = "C:\carpeta\muestras"
$env:NOTEBOOK_TEST_PATH = "C:\carpeta\LectorPdf.ipynb"
python -m unittest discover -s tests -v
```

Se ejecutaron ocho pruebas, incluidas las cinco muestras originales. Se comprobó
igualdad con el cuaderno para las cinco secciones sin OCR, apertura digital única,
distinción cero/vacío y manejo de errores. En el entorno local de esta entrega no
están instalados PyMuPDF/OpenCV/PaddleOCR: la inferencia real de la versión conjunta
está pendiente de ejecución en Colab. Se comprobó que esa ausencia se reporta como
fallo OCR y produce resultado PARCIAL, sin detener las otras secciones.

Las marcas positivas de operaciones internacionales requieren ejemplos reales
adicionales. Esta plantilla no incorpora OCR general para escaneos ni detección
universal de casillas manuscritas.

## Siguiente entrega

Tras validar el cuaderno conjunto: fijar dependencias, ampliar regresión OCR con
documentos diligenciados y desarrollar la exportación Excel sobre `campos`, sin
cambiar los lectores. Después se añadirá la interfaz de escritorio.
