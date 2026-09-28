# Extraído de LectorPdf.ipynb: reglas conservadas.
from ..recursos import pdf_api as pdfplumber, render_api as fitz, cv2, ocr_proxy
from ..configuracion import CONFIG
ocr_profesion_b = ocr_proxy
ocr_empresa_laboral = ocr_proxy
ocr_conyuge = ocr_proxy
import re
from decimal import Decimal
from io import BytesIO
from pdfplumber.utils import extract_text
CAMPOS_FINANCIEROS = CONFIG['financiera']['CAMPOS_FINANCIEROS']
SUMAS_FINANCIERAS = CONFIG['financiera']['SUMAS_FINANCIERAS']

def leer_texto_financiero(pagina, caja):
    caracteres = []
    for caracter in pagina.chars:
        x = (caracter['x0'] + caracter['x1']) / 2
        y = (caracter['top'] + caracter['bottom']) / 2
        fuente = caracter['fontname']
        if caja[0] <= x < caja[2] and caja[1] <= y < caja[3] and ('Arial' not in fuente) and ('Dingbats' not in fuente):
            caracteres.append(caracter)
    texto = extract_text(caracteres, x_tolerance=2, y_tolerance=3) or ''
    return re.sub('\\s+', ' ', texto).strip()

def convertir_importe(texto):
    """
    Devuelve Decimal para conservar precisión.
    Un vacío devuelve None, nunca cero.
    """
    limpio = re.sub('[$\\s]', '', texto)
    if not limpio:
        return None
    if re.fullmatch('-?\\d+', limpio):
        return Decimal(limpio)
    if re.fullmatch('-?\\d{1,3}(?:\\.\\d{3})+', limpio):
        return Decimal(limpio.replace('.', ''))
    if re.fullmatch('-?\\d{1,3}(?:,\\d{3})+', limpio):
        return Decimal(limpio.replace(',', ''))
    if re.fullmatch('-?\\d{1,3}(?:\\.\\d{3})+,\\d{1,2}', limpio):
        return Decimal(limpio.replace('.', '').replace(',', '.'))
    if re.fullmatch('-?\\d{1,3}(?:,\\d{3})+\\.\\d{1,2}', limpio):
        return Decimal(limpio.replace(',', ''))
    if re.fullmatch('-?\\d+[.,]\\d{1,2}', limpio):
        return Decimal(limpio.replace(',', '.'))
    raise ValueError('Formato de importe no reconocido')

def comprobar_operacion(campos, total, componentes, resta=False):
    necesarios = componentes + [total]
    faltantes = [nombre for nombre in necesarios if campos[nombre]['estado'] == 'VACIO']
    ilegibles = [nombre for nombre in necesarios if campos[nombre]['estado'] == 'POR REVISAR']
    if faltantes or ilegibles:
        motivos = []
        if faltantes:
            motivos.append('Campos vacíos: ' + ', '.join(faltantes))
        if ilegibles:
            motivos.append('Importes no reconocidos: ' + ', '.join(ilegibles))
        return {'estado': 'NO VERIFICABLE', 'motivo': '; '.join(motivos), 'valor_pdf': campos[total]['valor'], 'valor_calculado': None, 'diferencia': None}
    valores = [campos[nombre]['valor'] for nombre in componentes]
    if resta:
        calculado = valores[0] - valores[1]
    else:
        calculado = sum(valores, Decimal('0'))
    valor_pdf = campos[total]['valor']
    diferencia = valor_pdf - calculado
    return {'estado': 'OK' if diferencia == 0 else 'POR REVISAR', 'motivo': 'El total coincide' if diferencia == 0 else 'El total del PDF no coincide con el cálculo', 'valor_pdf': valor_pdf, 'valor_calculado': calculado, 'diferencia': diferencia}

def extraer_informacion_financiera(contenido):
    with pdfplumber.open(BytesIO(contenido), pages=[1]) as pdf:
        if not pdf.pages:
            return {'error': 'El PDF no contiene primera página'}
        pagina = pdf.pages[0]
        compatible = abs(pagina.width - 612) < 1 and abs(pagina.height - 935.433) < 1
        if compatible:
            titulo = pagina.crop((45, 574, 570, 591)).extract_text() or ''
            compatible = 'Información financiera del solicitante' in titulo
        if not compatible:
            return {'error': 'POR REVISAR: plantilla no reconocida o PDF escaneado'}
        campos = {}
        for nombre, caja in CAMPOS_FINANCIEROS.items():
            original = leer_texto_financiero(pagina, caja)
            try:
                valor = convertir_importe(original)
                estado = 'VACIO' if valor is None else 'EXTRAIDO'
            except ValueError:
                valor = None
                estado = 'POR REVISAR'
            campos[nombre] = {'original': original, 'valor': valor, 'estado': estado}
        comprobaciones = {}
        for total, componentes in SUMAS_FINANCIERAS.items():
            comprobaciones[total] = comprobar_operacion(campos, total, componentes)
        comprobaciones['Total patrimonio'] = comprobar_operacion(campos, 'Total patrimonio', ['Total activos', 'Total pasivos'], resta=True)
        estados = [comprobacion['estado'] for comprobacion in comprobaciones.values()]
        if 'POR REVISAR' in estados:
            general = 'POR REVISAR'
        elif 'NO VERIFICABLE' in estados:
            general = 'VERIFICACIÓN INCOMPLETA'
        else:
            general = 'OK'
        return {'campos': campos, 'comprobaciones': comprobaciones, 'estado': general}
