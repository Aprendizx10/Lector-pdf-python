# Extraído de LectorPdf.ipynb: reglas conservadas.
from ..recursos import pdf_api as pdfplumber, render_api as fitz, cv2, ocr_proxy
from ..configuracion import CONFIG
ocr_profesion_b = ocr_proxy
ocr_empresa_laboral = ocr_proxy
ocr_conyuge = ocr_proxy
import re
from io import BytesIO
from pdfplumber.utils import extract_text
PREGUNTAS_OI = CONFIG['internacionales']['PREGUNTAS_OI']
TRANSACCIONES_OI = CONFIG['internacionales']['TRANSACCIONES_OI']
PRODUCTOS_OI = CONFIG['internacionales']['PRODUCTOS_OI']
CAMPOS_OI = CONFIG['internacionales']['CAMPOS_OI']
DATOS_CUENTA_OI = CONFIG['internacionales']['DATOS_CUENTA_OI']

def centro_oi(caracter):
    return ((caracter['x0'] + caracter['x1']) / 2, (caracter['top'] + caracter['bottom']) / 2)

def dentro_oi(caracter, caja):
    x, y = centro_oi(caracter)
    return caja[0] <= x < caja[2] and caja[1] <= y < caja[3]

def leer_texto_oi(pagina, caja):
    caracteres = [caracter for caracter in pagina.chars if dentro_oi(caracter, caja) and 'Arial' not in caracter['fontname'] and ('Dingbats' not in caracter['fontname'])]
    texto = extract_text(caracteres, x_tolerance=2, y_tolerance=3) or ''
    return re.sub('\\s+', ' ', texto).strip()

def detectar_opciones_oi(pagina, opciones):
    marcadas = []
    dudosa = False
    for caracter in pagina.chars:
        if 'Dingbats' not in caracter['fontname']:
            continue
        for nombre, caja in opciones.items():
            if dentro_oi(caracter, caja):
                if caracter['text'] in ('8', '4', '✘', '✔', '✓'):
                    marcadas.append(nombre)
                else:
                    dudosa = True
                break
    return (list(dict.fromkeys(marcadas)), dudosa)

def campo_oi(valor, estado='OK', motivo=''):
    return {'valor': valor, 'estado': estado, 'motivo': motivo}

def validar_seleccion_oi(marcadas, dudosa, multiple=False):
    if dudosa:
        estado = 'POR REVISAR'
        motivo = 'No se pudo determinar la selección'
    elif not marcadas:
        estado = 'RECHAZADO'
        motivo = 'Campo vacío'
    elif not multiple and len(marcadas) > 1:
        estado = 'RECHAZADO'
        motivo = 'Debe elegir solo una opción'
    else:
        estado = 'OK'
        motivo = ''
    resultado = campo_oi(' / '.join(marcadas), estado, motivo)
    resultado['opciones_marcadas'] = marcadas
    return resultado

def aplicar_dependencia_oi(campo, respuesta):
    """
    Sí: mantiene la validación del campo.
    No: conserva lo leído sin exigirlo ni rechazarlo.
    Pregunta dudosa/inválida: campo relacionado por revisar.
    """
    if respuesta['estado'] != 'OK':
        campo['estado'] = 'POR REVISAR'
        campo['motivo'] = 'Primero debe resolverse la pregunta Sí / No'
    elif respuesta['valor'] == 'No':
        campo['estado'] = 'NO APLICA'
        campo['motivo'] = 'Sin obligación por respuesta No'
    return campo

def extraer_operaciones_internacionales(contenido):
    with pdfplumber.open(BytesIO(contenido), pages=[1]) as pdf:
        if not pdf.pages:
            return {'error': 'El PDF no contiene primera página'}
        pagina = pdf.pages[0]
        compatible = abs(pagina.width - 612) < 1 and abs(pagina.height - 935.433) < 1
        if compatible:
            titulo = pagina.crop((42, 817, 575, 834)).extract_text() or ''
            compatible = 'Operaciones internacionales' in titulo
        if not compatible:
            return {'error': 'POR REVISAR: plantilla no reconocida o PDF escaneado'}
        campos = {}
        for nombre, opciones in PREGUNTAS_OI.items():
            marcadas, dudosa = detectar_opciones_oi(pagina, opciones)
            campos[nombre] = validar_seleccion_oi(marcadas, dudosa)
        respuesta_transacciones = campos['Realiza transacciones en moneda extranjera']
        respuesta_cuenta = campos['Posee cuenta en moneda extranjera']
        tipos, duda_tipos = detectar_opciones_oi(pagina, TRANSACCIONES_OI)
        campos['Tipo de transacción'] = aplicar_dependencia_oi(validar_seleccion_oi(tipos, duda_tipos, multiple=True), respuesta_transacciones)
        detalle = leer_texto_oi(pagina, CAMPOS_OI['Otras, ¿cuáles?'])
        if 'Otras' in tipos:
            campo_detalle = campo_oi(detalle, 'OK' if detalle else 'RECHAZADO', '' if detalle else 'Debe indicar cuáles')
        elif duda_tipos:
            campo_detalle = campo_oi(detalle, 'POR REVISAR', 'No se pudo determinar si seleccionó Otras')
        else:
            campo_detalle = campo_oi(detalle, 'NO APLICA', 'Otras no seleccionada')
        campos['Otras, ¿cuáles?'] = aplicar_dependencia_oi(campo_detalle, respuesta_transacciones)
        for nombre in DATOS_CUENTA_OI:
            texto = leer_texto_oi(pagina, CAMPOS_OI[nombre])
            dato = campo_oi(texto, 'OK' if texto else 'RECHAZADO', '' if texto else 'Campo vacío')
            campos[nombre] = aplicar_dependencia_oi(dato, respuesta_cuenta)
        productos, duda_producto = detectar_opciones_oi(pagina, PRODUCTOS_OI)
        campos['Tipo de producto'] = aplicar_dependencia_oi(validar_seleccion_oi(productos, duda_producto), respuesta_cuenta)
        for nombre in ('Efectivo', 'Cheque'):
            texto = leer_texto_oi(pagina, CAMPOS_OI[nombre])
            if not re.sub('[$\\s]', '', texto):
                texto = ''
            campos[nombre] = campo_oi(texto, 'OK' if texto else 'OPCIONAL', '' if texto else 'Campo vacío')
        estados = [campo['estado'] for campo in campos.values()]
        if 'RECHAZADO' in estados:
            general = 'RECHAZADO'
        elif 'POR REVISAR' in estados:
            general = 'POR REVISAR'
        else:
            general = 'OK'
        return {'campos': campos, 'estado': general}
