# Extraído de LectorPdf.ipynb: reglas conservadas.
from ..recursos import pdf_api as pdfplumber, render_api as fitz, cv2, ocr_proxy
from ..configuracion import CONFIG
ocr_profesion_b = ocr_proxy
ocr_empresa_laboral = ocr_proxy
ocr_conyuge = ocr_proxy
import re
from io import BytesIO
from pdfplumber.utils import extract_text
OCUPACIONES_AE = CONFIG['actividad']['OCUPACIONES_AE']
CAMPOS_AE = CONFIG['actividad']['CAMPOS_AE']

def centro_ae(caracter):
    return ((caracter['x0'] + caracter['x1']) / 2, (caracter['top'] + caracter['bottom']) / 2)

def leer_texto_ae(pagina, caja):
    caracteres = []
    for caracter in pagina.chars:
        x, y = centro_ae(caracter)
        fuente = caracter['fontname']
        if caja[0] <= x < caja[2] and caja[1] <= y < caja[3] and ('Arial' not in fuente) and ('Dingbats' not in fuente):
            caracteres.append(caracter)
    texto = extract_text(caracteres, x_tolerance=2, y_tolerance=3) or ''
    return re.sub('\\s+', ' ', texto).strip()

def detectar_marcas_ae(pagina, opciones):
    marcadas = []
    desconocida = False
    for caracter in pagina.chars:
        if 'Dingbats' not in caracter['fontname']:
            continue
        x, y = centro_ae(caracter)
        opcion = min(opciones, key=lambda nombre: (x - opciones[nombre][0]) ** 2 + (y - opciones[nombre][1]) ** 2)
        casilla_x, casilla_y = opciones[opcion]
        if abs(x - casilla_x) <= 5 and abs(y - casilla_y) <= 5:
            if caracter['text'] in ('8', '4', '✘', '✔', '✓'):
                marcadas.append(opcion)
            else:
                desconocida = True
    return (list(dict.fromkeys(marcadas)), desconocida)

def campo_ae(valor, estado='OK', motivo=''):
    return {'valor': valor, 'estado': estado, 'motivo': motivo}

def extraer_actividad_economica(contenido):
    with pdfplumber.open(BytesIO(contenido), pages=[1]) as pdf:
        if not pdf.pages:
            return {'error': 'El PDF no contiene primera página'}
        pagina = pdf.pages[0]
        compatible = abs(pagina.width - 612) < 1 and abs(pagina.height - 935.433) < 1
        if compatible:
            titulo = pagina.crop((45, 443, 238, 461)).extract_text() or ''
            compatible = 'Actividad económica' in titulo
        if not compatible:
            return {'error': 'POR REVISAR: plantilla no reconocida o PDF escaneado'}
        resultado = {}
        marcas, duda_independiente = detectar_marcas_ae(pagina, {'Independiente': (239, 452)})
        independiente = bool(marcas)
        if duda_independiente:
            resultado['Independiente'] = campo_ae('No se pudo determinar', 'POR REVISAR', 'Marca no reconocida')
        else:
            resultado['Independiente'] = campo_ae('Marcado' if independiente else 'Sin marcar')
        ocupaciones, duda_ocupacion = detectar_marcas_ae(pagina, OCUPACIONES_AE)
        valor_ocupacion = ' / '.join(ocupaciones)
        if duda_ocupacion:
            resultado['Ocupación'] = campo_ae(valor_ocupacion or 'No se pudo determinar', 'POR REVISAR', 'Marca no reconocida')
        elif len(ocupaciones) > 1:
            resultado['Ocupación'] = campo_ae(valor_ocupacion, 'RECHAZADO', 'Debe elegir solo una opción')
        elif len(ocupaciones) == 1:
            resultado['Ocupación'] = campo_ae(valor_ocupacion)
        elif duda_independiente:
            resultado['Ocupación'] = campo_ae('', 'POR REVISAR', 'No se pudo determinar si es obligatoria')
        elif independiente:
            resultado['Ocupación'] = campo_ae('', 'RECHAZADO', 'Campo vacío')
        else:
            resultado['Ocupación'] = campo_ae('', 'NO APLICA', 'Independiente sin marcar')
        especifique = leer_texto_ae(pagina, CAMPOS_AE['Especifique'])
        if 'Otro' in ocupaciones:
            resultado['Especifique'] = campo_ae(especifique, 'OK' if especifique else 'RECHAZADO', '' if especifique else 'Campo vacío')
        elif duda_ocupacion and (not especifique):
            resultado['Especifique'] = campo_ae('', 'POR REVISAR', 'Revisar si se seleccionó Otro')
        else:
            resultado['Especifique'] = campo_ae(especifique, 'OK' if especifique else 'NO APLICA', '' if especifique else 'Otro no seleccionado')
        descripcion = leer_texto_ae(pagina, CAMPOS_AE['Descripción'])
        resultado['Descripción'] = campo_ae(descripcion, 'OK' if descripcion else 'OPCIONAL', '' if descripcion else 'Campo vacío')
        ciiu = leer_texto_ae(pagina, CAMPOS_AE['Código CIIU'])
        if not ciiu:
            resultado['Código CIIU'] = campo_ae('', 'RECHAZADO', 'Campo vacío')
        elif ciiu.upper() in ('NO APLICA', 'N/A', 'NA'):
            resultado['Código CIIU'] = campo_ae(ciiu, 'RECHAZADO', 'El código CIIU es obligatorio')
        else:
            resultado['Código CIIU'] = campo_ae(ciiu)
        for nombre_campo in ('Ocupación', 'Especifique', 'Descripción', 'Código CIIU'):
            campo = resultado[nombre_campo]
            if duda_independiente:
                campo['estado'] = 'POR REVISAR'
                campo['motivo'] = 'No se pudo determinar si Independiente está marcado'
            elif not independiente:
                campo['estado'] = 'NO APLICA'
                campo['motivo'] = 'Independiente sin marcar'
        estados = [campo['estado'] for campo in resultado.values()]
        if 'RECHAZADO' in estados:
            general = 'RECHAZADO'
        elif 'POR REVISAR' in estados:
            general = 'POR REVISAR'
        else:
            general = 'OK'
        return {'campos': resultado, 'estado': general}
