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
CAMPOS_CONYUGE = CONFIG['conyuge']['CAMPOS_CONYUGE']
DOCUMENTOS_CONYUGE = CONFIG['conyuge']['DOCUMENTOS_CONYUGE']
CAMPOS_OCR_CONYUGE = CONFIG['conyuge']['CAMPOS_OCR_CONYUGE']

def centro_conyuge(caracter):
    return ((caracter['x0'] + caracter['x1']) / 2, (caracter['top'] + caracter['bottom']) / 2)

def leer_texto_conyuge(pagina, caja):
    caracteres = []
    for caracter in pagina.chars:
        x, y = centro_conyuge(caracter)
        fuente = caracter['fontname']
        if caja[0] <= x < caja[2] and caja[1] <= y < caja[3] and ('Arial' not in fuente) and ('Dingbats' not in fuente):
            caracteres.append(caracter)
    texto = extract_text(caracteres, x_tolerance=2, y_tolerance=3) or ''
    texto = re.sub('\\s+', ' ', texto).strip()
    return {'valor': texto, 'estado': 'OK' if texto else 'OPCIONAL', 'motivo': '' if texto else 'Campo vacío'}

def reconocer_campo_conyuge(pagina, configuracion):
    pixmap = pagina.get_pixmap(matrix=fitz.Matrix(4, 4), clip=fitz.Rect(configuracion['caja']), colorspace=fitz.csRGB, alpha=False)
    imagen = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width, 3).copy()
    gris = cv2.cvtColor(imagen, cv2.COLOR_RGB2GRAY)
    gris = cv2.copyMakeBorder(gris, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)
    imagen_ocr = cv2.cvtColor(gris, cv2.COLOR_GRAY2BGR)
    textos = []
    puntuaciones = []
    for lectura in ocr_conyuge.predict(imagen_ocr):
        for texto, puntuacion in zip(lectura['rec_texts'], lectura['rec_scores']):
            texto = re.sub('\\s+', ' ', texto).strip()
            if texto:
                textos.append(texto)
                puntuaciones.append(float(puntuacion))
    texto_completo = ' '.join(textos)
    valor = re.sub(configuracion['etiqueta'], '', texto_completo, flags=re.IGNORECASE).strip()
    if not valor:
        return {'valor': '', 'estado': 'OPCIONAL', 'motivo': 'Sin texto reconocido mediante OCR', 'metodo': 'OCR', 'confianza_ocr': None, 'texto_ocr_original': texto_completo}
    confianza = min(puntuaciones) if puntuaciones else 0.0
    etiqueta_residual = bool(re.match(configuracion['residuo'], valor, flags=re.IGNORECASE))
    if etiqueta_residual:
        estado = 'POR REVISAR'
        motivo = 'El OCR pudo conservar parte de la etiqueta'
    elif confianza < 0.8:
        estado = 'POR REVISAR'
        motivo = 'Lectura OCR dudosa; verificar en el documento'
    else:
        estado = 'OK'
        motivo = ''
    return {'valor': valor, 'estado': estado, 'motivo': motivo, 'metodo': 'OCR', 'confianza_ocr': confianza, 'texto_ocr_original': texto_completo}

def leer_campos_ocr_conyuge(contenido):
    resultados = {}

    def error_ocr(error):
        return {'valor': '', 'estado': 'POR REVISAR', 'motivo': f'No se pudo ejecutar el OCR: {error}', 'metodo': 'OCR', 'confianza_ocr': None}
    try:
        with fitz.open(stream=contenido, filetype='pdf') as documento:
            pagina = documento[0]
            for nombre, configuracion in CAMPOS_OCR_CONYUGE.items():
                try:
                    resultados[nombre] = reconocer_campo_conyuge(pagina, configuracion)
                except Exception as error:
                    resultados[nombre] = error_ocr(error)
    except Exception as error:
        for nombre in CAMPOS_OCR_CONYUGE:
            resultados[nombre] = error_ocr(error)
    return resultados

def leer_documento_conyuge(pagina):
    marcadas = []
    desconocida = False
    for caracter in pagina.chars:
        if 'Dingbats' not in caracter['fontname']:
            continue
        x, y = centro_conyuge(caracter)
        opcion = min(DOCUMENTOS_CONYUGE, key=lambda nombre: (x - DOCUMENTOS_CONYUGE[nombre][0]) ** 2 + (y - DOCUMENTOS_CONYUGE[nombre][1]) ** 2)
        casilla_x, casilla_y = DOCUMENTOS_CONYUGE[opcion]
        if abs(x - casilla_x) <= 5 and abs(y - casilla_y) <= 5:
            if caracter['text'] in ('8', '4', '✘', '✔', '✓'):
                marcadas.append(opcion)
            else:
                desconocida = True
    marcadas = list(dict.fromkeys(marcadas))
    if desconocida:
        estado = 'POR REVISAR'
        motivo = 'No se pudo determinar la selección'
    elif len(marcadas) > 1:
        estado = 'POR REVISAR'
        motivo = 'Hay varios tipos de documento marcados'
    elif not marcadas:
        estado = 'OPCIONAL'
        motivo = 'Campo vacío'
    else:
        estado = 'OK'
        motivo = ''
    return {'valor': ' / '.join(marcadas), 'estado': estado, 'motivo': motivo}

def extraer_datos_conyuge(contenido):
    with pdfplumber.open(BytesIO(contenido), pages=[1]) as pdf:
        if not pdf.pages:
            return {'error': 'El PDF no contiene primera página'}
        pagina = pdf.pages[0]
        compatible = abs(pagina.width - 612) < 1 and abs(pagina.height - 935.433) < 1
        if compatible:
            titulo = pagina.crop((45, 512, 570, 527)).extract_text() or ''
            compatible = 'Datos del cónyuge' in titulo
        if not compatible:
            return {'error': 'POR REVISAR: plantilla no reconocida o PDF escaneado'}
        campos_ocr = leer_campos_ocr_conyuge(contenido)
        resultado = {}
        for nombre, caja in CAMPOS_CONYUGE.items():
            if nombre in campos_ocr:
                resultado[nombre] = campos_ocr[nombre]
            else:
                resultado[nombre] = leer_texto_conyuge(pagina, caja)
        resultado['Tipo de documento'] = leer_documento_conyuge(pagina)
        estados = [campo['estado'] for campo in resultado.values()]
        if 'POR REVISAR' in estados:
            general = 'POR REVISAR'
        elif all((estado == 'OPCIONAL' for estado in estados)):
            general = 'OK — Sin datos detectados; bloque opcional'
        else:
            general = 'OK'
        return {'campos': resultado, 'estado': general}
