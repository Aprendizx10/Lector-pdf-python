# Extraído de LectorPdf.ipynb: reglas conservadas.
from ..recursos import pdf_api as pdfplumber, render_api as fitz, cv2, ocr_proxy
from ..configuracion import CONFIG
ocr_profesion_b = ocr_proxy
ocr_empresa_laboral = ocr_proxy
ocr_conyuge = ocr_proxy
import re
import unicodedata
from io import BytesIO
import numpy as np
from pdfplumber.utils import extract_text
CAMPOS_B = CONFIG['basica']['CAMPOS_B']
GRUPOS_B = CONFIG['basica']['GRUPOS_B']
OPCIONALES_B = CONFIG['basica']['OPCIONALES_B']

def normalizar_b(texto):
    texto = ''.join((caracter for caracter in unicodedata.normalize('NFD', texto.upper()) if unicodedata.category(caracter) != 'Mn'))
    return re.sub('\\s+', ' ', texto).strip()

def validar_direccion_b(texto):
    if not texto:
        return ('RECHAZADO', 'Campo vacío')
    if '@' in texto:
        return ('RECHAZADO', 'El campo contiene un correo')
    texto_validacion = normalizar_b(texto)
    texto_validacion = texto_validacion.replace('.', '')
    texto_validacion = texto_validacion.replace('–', '-')
    texto_validacion = re.sub('^CALL\\s+(?=\\d)', 'CALLE ', texto_validacion)
    via = '(?:AVENIDA(?:\\s+(?:CALLE|CARRERA))?|AV(?:\\s+(?:CL|CR|KR))?|CALLE|CL|CARRERA|CRA|CR|KR|DIAGONAL|DG|TRANSVERSAL|TRV|TV|AC|AK)'
    numero = '\\d{1,3}(?:\\s*[A-Z](?![A-Z]))?(?:\\s*BIS(?:\\s*[A-Z](?![A-Z]))?)?'
    orientacion = '(?:\\s+(?:SUR|NORTE|ESTE|OESTE))?'
    patron = f'{via}\\s+{numero}{orientacion}\\s*(?:#\\s*|\\s+){numero}\\s*(?:-\\s*|\\s+)\\d{{1,3}}{orientacion}'
    if re.fullmatch(patron, texto_validacion):
        return ('OK', 'Estructura reconocida')
    return ('POR REVISAR', 'Estructura no reconocida')

def formatear_direccion_excel(texto):
    if validar_direccion_b(texto)[0] != 'OK':
        return texto
    direccion = normalizar_b(texto).replace('.', '')
    direccion = direccion.replace('–', '-')
    direccion = re.sub('^CALL\\s+(?=\\d)', 'CALLE ', direccion)
    direccion = re.sub('(\\d)\\s+([A-Z])\\b', '\\1\\2', direccion)
    direccion = re.sub('\\s*#\\s*', ' # ', direccion)
    direccion = re.sub('\\s*-\\s*', '-', direccion)
    direccion = re.sub('(# \\d+[A-Z]?(?:\\s*BIS[A-Z]?)?)\\s+(\\d+)(?=\\s*(?:SUR|NORTE|ESTE|OESTE)?$)', '\\1-\\2', direccion)
    return direccion.strip()

def centro_b(caracter):
    return ((caracter['x0'] + caracter['x1']) / 2, (caracter['top'] + caracter['bottom']) / 2)

def texto_b(pagina, caja):
    caracteres = []
    for caracter in pagina.chars:
        x, y = centro_b(caracter)
        fuente = caracter['fontname']
        if caja[0] <= x < caja[2] and caja[1] <= y < caja[3] and ('Arial' not in fuente) and ('Dingbats' not in fuente):
            caracteres.append(caracter)
    texto = extract_text(caracteres, x_tolerance=2, y_tolerance=3) or ''
    return re.sub('\\s+', ' ', texto).strip()

def leer_profesion_ocr_b(contenido):
    try:
        with fitz.open(stream=contenido, filetype='pdf') as documento:
            pagina = documento[0]
            pixmap = pagina.get_pixmap(matrix=fitz.Matrix(4, 4), clip=fitz.Rect(416, 246, 574, 266), colorspace=fitz.csRGB, alpha=False)
            imagen = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width, 3).copy()
        gris = cv2.cvtColor(imagen, cv2.COLOR_RGB2GRAY)
        gris = cv2.copyMakeBorder(gris, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)
        imagen_ocr = cv2.cvtColor(gris, cv2.COLOR_GRAY2BGR)
        textos = []
        puntuaciones = []
        for lectura in ocr_profesion_b.predict(imagen_ocr):
            for texto, puntuacion in zip(lectura['rec_texts'], lectura['rec_scores']):
                texto = re.sub('\\s+', ' ', texto).strip()
                texto = re.sub('^\\s*profesi[oó]n\\s*:?\\s*', '', texto, flags=re.IGNORECASE).strip()
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

def seleccion_b(pagina, opciones, permite_dos=False):
    marcadas = []
    desconocida = False
    for caracter in pagina.chars:
        if 'Dingbats' not in caracter['fontname']:
            continue
        x, y = centro_b(caracter)
        opcion = min(opciones, key=lambda nombre: (x - opciones[nombre][0]) ** 2 + (y - opciones[nombre][1]) ** 2)
        casilla_x, casilla_y = opciones[opcion]
        if abs(x - casilla_x) <= 5 and abs(y - casilla_y) <= 5:
            if caracter['text'] in ('8', '4', '✘', '✔', '✓'):
                marcadas.append(opcion)
            else:
                desconocida = True
    marcadas = list(dict.fromkeys(marcadas))
    maximo = 2 if permite_dos else 1
    if desconocida:
        estado = 'POR REVISAR'
        motivo = 'No se pudo determinar la selección'
    elif not marcadas:
        estado = 'RECHAZADO'
        motivo = 'Campo vacío'
    elif len(marcadas) > maximo:
        estado = 'RECHAZADO'
        motivo = 'Debe elegir solo una opción'
    else:
        estado = 'OK'
        motivo = ''
    return {'valor': ' / '.join(marcadas), 'estado': estado, 'motivo': motivo}

def extraer_basica(contenido):
    with pdfplumber.open(BytesIO(contenido), pages=[1]) as pdf:
        if not pdf.pages:
            return {'error': 'El PDF no contiene primera página'}
        pagina = pdf.pages[0]
        compatible = abs(pagina.width - 612) < 1 and abs(pagina.height - 935.433) < 1
        if compatible:
            titulo = pagina.crop((45, 158, 280, 178)).extract_text() or ''
            compatible = 'Información básica solicitante' in titulo
        if not compatible:
            return {'error': 'POR REVISAR: plantilla no reconocida o PDF escaneado'}
        resultado = {}
        for nombre, caja in CAMPOS_B.items():
            if nombre == 'Profesión':
                resultado[nombre] = leer_profesion_ocr_b(contenido)
                continue
            valor = texto_b(pagina, caja)
            estado = 'OK'
            motivo = ''
            if not valor:
                if nombre in OPCIONALES_B:
                    estado = 'OPCIONAL'
                    motivo = 'Campo vacío'
                else:
                    estado = 'RECHAZADO'
                    motivo = 'Campo vacío'
            elif normalizar_b(valor) in ('NO APLICA', 'N/A', 'NA'):
                if nombre in OPCIONALES_B:
                    estado = 'NO APLICA'
                else:
                    estado = 'POR REVISAR'
                    motivo = 'Verificar dato obligatorio'
            if nombre == 'Dirección de residencia':
                estado, motivo = validar_direccion_b(valor)
            resultado[nombre] = {'valor': valor, 'estado': estado, 'motivo': motivo}
            if nombre == 'Dirección de residencia':
                resultado[nombre]['original'] = valor
                resultado[nombre]['valor'] = formatear_direccion_excel(valor)
        for nombre, opciones in GRUPOS_B.items():
            resultado[nombre] = seleccion_b(pagina, opciones, permite_dos=nombre == 'Canal de contacto')
        otro = texto_b(pagina, (493, 279, 575, 292))
        clase = resultado['Clase de vivienda']
        if clase['estado'] == 'OK' and clase['valor'] == 'Otro':
            if otro:
                estado, motivo = ('OK', '')
            else:
                estado, motivo = ('RECHAZADO', 'Campo vacío')
        elif clase['estado'] != 'OK':
            estado = 'POR REVISAR'
            motivo = 'Revisar selección de clase de vivienda'
        else:
            estado = 'NO APLICA'
            motivo = 'Otro no seleccionado'
        resultado['Vivienda, otro detalle'] = {'valor': otro, 'estado': estado, 'motivo': motivo}
        estados = [campo['estado'] for campo in resultado.values()]
        if 'RECHAZADO' in estados:
            general = 'RECHAZADO'
        elif 'POR REVISAR' in estados:
            general = 'POR REVISAR'
        else:
            general = 'OK'
        return {'campos': resultado, 'estado': general}
