# Extraído de LectorPdf.ipynb: reglas conservadas.
from ..recursos import pdf_api as pdfplumber, render_api as fitz, cv2, ocr_proxy
from ..configuracion import CONFIG
ocr_profesion_b = ocr_proxy
ocr_empresa_laboral = ocr_proxy
ocr_conyuge = ocr_proxy
import re
from io import BytesIO
import numpy as np
from pdfplumber.utils import extract_text
CAMPOS_LABORALES = CONFIG['laboral']['CAMPOS_LABORALES']
PREGUNTAS_LABORALES = CONFIG['laboral']['PREGUNTAS_LABORALES']

def centro_laboral(caracter):
    return ((caracter['x0'] + caracter['x1']) / 2, (caracter['top'] + caracter['bottom']) / 2)

def leer_texto_laboral(pagina, caja):
    caracteres = []
    for caracter in pagina.chars:
        x, y = centro_laboral(caracter)
        fuente = caracter['fontname']
        if caja[0] <= x < caja[2] and caja[1] <= y < caja[3] and ('Arial' not in fuente) and ('Dingbats' not in fuente):
            caracteres.append(caracter)
    texto = extract_text(caracteres, x_tolerance=2, y_tolerance=3) or ''
    texto = re.sub('\\s+', ' ', texto).strip()
    return {'valor': texto, 'estado': 'OK' if texto else 'OPCIONAL', 'motivo': '' if texto else 'Campo vacío'}

def leer_empresa_ocr_laboral(contenido):
    try:
        with fitz.open(stream=contenido, filetype='pdf') as documento:
            pagina = documento[0]
            pixmap = pagina.get_pixmap(matrix=fitz.Matrix(4, 4), clip=fitz.Rect(44, 400, 370, 420), colorspace=fitz.csRGB, alpha=False)
            imagen = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width, 3).copy()
        gris = cv2.cvtColor(imagen, cv2.COLOR_RGB2GRAY)
        gris = cv2.copyMakeBorder(gris, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)
        imagen_ocr = cv2.cvtColor(gris, cv2.COLOR_GRAY2BGR)
        textos = []
        puntuaciones = []
        for lectura in ocr_empresa_laboral.predict(imagen_ocr):
            for texto, puntuacion in zip(lectura['rec_texts'], lectura['rec_scores']):
                texto = re.sub('\\s+', ' ', texto).strip()
                texto = re.sub('^\\s*empresa\\s+donde\\s+labora(?:\\s*[/o]\\s*negocio)?\\s*:?\\s*', '', texto, flags=re.IGNORECASE).strip()
                if texto:
                    textos.append(texto)
                    puntuaciones.append(float(puntuacion))
        if not textos:
            return {'valor': '', 'estado': 'OPCIONAL', 'motivo': 'Sin texto reconocido mediante OCR', 'metodo': 'OCR', 'confianza_ocr': None}
        valor = ' '.join(textos)
        confianza = min(puntuaciones)
        return {'valor': valor, 'estado': 'OK' if confianza >= 0.8 else 'POR REVISAR', 'motivo': '' if confianza >= 0.8 else 'Lectura OCR dudosa; verificar en el documento', 'metodo': 'OCR', 'confianza_ocr': confianza}
    except Exception as error:
        return {'valor': '', 'estado': 'POR REVISAR', 'motivo': f'No se pudo ejecutar el OCR: {error}', 'metodo': 'OCR', 'confianza_ocr': None}

def leer_seleccion_laboral(pagina, opciones):
    marcadas = []
    marca_desconocida = False
    for caracter in pagina.chars:
        if 'Dingbats' not in caracter['fontname']:
            continue
        x, y = centro_laboral(caracter)
        opcion = min(opciones, key=lambda nombre: (x - opciones[nombre][0]) ** 2 + (y - opciones[nombre][1]) ** 2)
        casilla_x, casilla_y = opciones[opcion]
        if abs(x - casilla_x) <= 5 and abs(y - casilla_y) <= 5:
            if caracter['text'] in ('8', '4', '✘', '✔', '✓'):
                marcadas.append(opcion)
            else:
                marca_desconocida = True
    marcadas = list(dict.fromkeys(marcadas))
    if marca_desconocida:
        estado = 'POR REVISAR'
        motivo = 'No se pudo determinar la selección'
    elif not marcadas:
        estado = 'RECHAZADO'
        motivo = 'Campo vacío'
    elif len(marcadas) > 1:
        estado = 'RECHAZADO'
        motivo = 'Debe seleccionar solo una opción'
    else:
        estado = 'OK'
        motivo = ''
    return {'valor': ' / '.join(marcadas), 'opciones_marcadas': marcadas, 'estado': estado, 'motivo': motivo}

def extraer_informacion_laboral(contenido):
    with pdfplumber.open(BytesIO(contenido), pages=[1]) as pdf:
        if not pdf.pages:
            return {'error': 'El PDF no contiene primera página'}
        pagina = pdf.pages[0]
        compatible = abs(pagina.width - 612) < 1 and abs(pagina.height - 935.433) < 1
        if compatible:
            titulo = pagina.crop((45, 380, 370, 399)).extract_text() or ''
            compatible = 'Información laboral' in titulo
        if not compatible:
            return {'error': 'POR REVISAR: plantilla no reconocida o PDF escaneado'}
        resultado = {}
        for nombre, caja in CAMPOS_LABORALES.items():
            if nombre == 'Empresa donde labora o negocio':
                resultado[nombre] = leer_empresa_ocr_laboral(contenido)
            else:
                resultado[nombre] = leer_texto_laboral(pagina, caja)
        for nombre, opciones in PREGUNTAS_LABORALES.items():
            resultado[nombre] = leer_seleccion_laboral(pagina, opciones)
        estados = [campo['estado'] for campo in resultado.values()]
        if 'RECHAZADO' in estados:
            estado_general = 'RECHAZADO'
        elif 'POR REVISAR' in estados:
            estado_general = 'POR REVISAR'
        else:
            estado_general = 'OK'
        return {'campos': resultado, 'estado': estado_general}
