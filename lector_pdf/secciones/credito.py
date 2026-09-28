# Extraído de LectorPdf.ipynb: reglas conservadas.
from ..recursos import pdf_api as pdfplumber, render_api as fitz, cv2, ocr_proxy
from ..configuracion import CONFIG
ocr_profesion_b = ocr_proxy
ocr_empresa_laboral = ocr_proxy
ocr_conyuge = ocr_proxy
import json
import re
from io import BytesIO
from pdfplumber.utils import extract_text
CAMPOS = CONFIG['credito']['CAMPOS']
GRUPOS = CONFIG['credito']['GRUPOS']

def centro(caracter):
    return ((caracter['x0'] + caracter['x1']) / 2, (caracter['top'] + caracter['bottom']) / 2)

def leer_campo(pagina, coordenadas):
    izquierda, arriba, derecha, abajo = coordenadas
    caracteres = []
    for caracter in pagina.chars:
        x, y = centro(caracter)
        fuente = caracter['fontname']
        if izquierda <= x < derecha and arriba <= y < abajo and ('Arial' not in fuente) and ('Dingbats' not in fuente):
            caracteres.append(caracter)
    texto = extract_text(caracteres, x_tolerance=2, y_tolerance=3) or ''
    texto = re.sub('\\s+', ' ', texto).strip()
    return {'valor': texto or None, 'estado': 'EXTRAIDO' if texto else 'VACIO'}

def leer_seleccion(pagina, opciones):
    seleccionadas = []
    marca_desconocida = False
    for caracter in pagina.chars:
        if 'Dingbats' not in caracter['fontname']:
            continue
        x, y = centro(caracter)
        opcion = min(opciones, key=lambda nombre: (x - opciones[nombre][0]) ** 2 + (y - opciones[nombre][1]) ** 2)
        casilla_x, casilla_y = opciones[opcion]
        if abs(x - casilla_x) <= 5 and abs(y - casilla_y) <= 5:
            if caracter['text'] in ('8', '4', '✘', '✔', '✓'):
                seleccionadas.append(opcion)
            else:
                marca_desconocida = True
    seleccionadas = list(dict.fromkeys(seleccionadas))
    if marca_desconocida:
        estado = 'POR_REVISAR'
        motivo = 'No se pudo determinar la selección'
    elif not seleccionadas:
        estado = 'RECHAZADO'
        motivo = 'Campo vacío'
    elif len(seleccionadas) > 1:
        estado = 'RECHAZADO'
        motivo = 'Debe seleccionar solo una opción'
    else:
        estado = 'OK'
        motivo = ''
    return {'opciones_marcadas': seleccionadas, 'estado': estado, 'motivo': motivo}

def extraer_informacion_credito(contenido_pdf):
    with pdfplumber.open(BytesIO(contenido_pdf), pages=[1]) as pdf:
        if not pdf.pages:
            raise ValueError('El PDF no contiene una primera página')
        pagina = pdf.pages[0]
        compatible = abs(pagina.width - 612) < 1 and abs(pagina.height - 935.433) < 1
        if compatible:
            titulo = pagina.crop((45, 103, 290, 123)).extract_text() or ''
            compatible = 'Información para el crédito' in titulo
        if not compatible:
            return {'error': 'Formato no reconocido o PDF escaneado'}
        campos = {nombre: leer_campo(pagina, coordenadas) for nombre, coordenadas in CAMPOS.items()}
        selecciones = {nombre: leer_seleccion(pagina, opciones) for nombre, opciones in GRUPOS.items()}
        estados = [seleccion['estado'] for seleccion in selecciones.values()]
        if 'RECHAZADO' in estados:
            estado_selecciones = 'RECHAZADO'
        elif 'POR_REVISAR' in estados:
            estado_selecciones = 'POR_REVISAR'
        else:
            estado_selecciones = 'OK'
        return {**campos, **selecciones, 'estado_selecciones': estado_selecciones}
