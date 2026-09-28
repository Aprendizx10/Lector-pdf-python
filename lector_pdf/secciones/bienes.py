# Extraído de LectorPdf.ipynb: reglas conservadas.
from ..recursos import pdf_api as pdfplumber, render_api as fitz, cv2, ocr_proxy
from ..configuracion import CONFIG
ocr_profesion_b = ocr_proxy
ocr_empresa_laboral = ocr_proxy
ocr_conyuge = ocr_proxy
import re
import unicodedata
from decimal import Decimal
from io import BytesIO
from pdfplumber.utils import extract_text
TABLAS_BIENES = CONFIG['bienes']['TABLAS_BIENES']

def leer_texto_bienes(pagina, caja):
    caracteres = []
    for caracter in pagina.chars:
        x = (caracter['x0'] + caracter['x1']) / 2
        y = (caracter['top'] + caracter['bottom']) / 2
        fuente = caracter['fontname']
        if caja[0] <= x < caja[2] and caja[1] <= y < caja[3] and ('Arial' not in fuente) and ('Dingbats' not in fuente):
            caracteres.append(caracter)
    texto = extract_text(caracteres, x_tolerance=2, y_tolerance=3) or ''
    return re.sub('\\s+', ' ', texto).strip()

def normalizar_direccion_bienes(original):
    texto = ''.join((caracter for caracter in unicodedata.normalize('NFD', original.upper()) if unicodedata.category(caracter) != 'Mn'))
    texto = re.sub('\\s+', ' ', texto).strip()
    texto = texto.replace('.', '').replace('–', '-')
    texto = re.sub('^CALL\\s+(?=\\d)', 'CALLE ', texto)
    if '@' in texto:
        return (original, 'POR REVISAR', 'La dirección contiene un correo')
    via = '(?:AVENIDA(?:\\s+(?:CALLE|CARRERA))?|AV(?:\\s+(?:CL|CR|KR))?|CALLE|CL|CARRERA|CRA|CR|KR|DIAGONAL|DG|TRANSVERSAL|TRV|TV|AC|AK)'
    numero = '\\d{1,3}(?:\\s*[A-Z](?![A-Z]))?(?:\\s*BIS(?:\\s*[A-Z](?![A-Z]))?)?'
    orientacion = '(?:\\s+(?:SUR|NORTE|ESTE|OESTE))?'
    patron = f'(?P<via>{via})\\s+(?P<principal>{numero}{orientacion})\\s*(?:#\\s*|\\s+)(?P<secundaria>{numero})\\s*(?:-\\s*|\\s+)(?P<placa>\\d{{1,3}}{orientacion})'
    coincidencia = re.fullmatch(patron, texto)
    if not coincidencia:
        return (original, 'POR REVISAR', 'Estructura no reconocida')
    partes = coincidencia.groupdict()
    for clave in ('principal', 'secundaria', 'placa'):
        partes[clave] = re.sub('(\\d)\\s+([A-Z])\\b', '\\1\\2', partes[clave]).strip()
    direccion = f"{partes['via']} {partes['principal']} # {partes['secundaria']}-{partes['placa']}"
    return (direccion, 'OK', '')

def convertir_importe_bienes(texto):
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
    raise ValueError('Importe no reconocido')

def extraer_tabla_bienes(pagina, nombre_tabla, configuracion):
    titulo = pagina.crop(configuracion['titulo_caja']).extract_text() or ''
    if nombre_tabla not in titulo:
        return {'error': f'POR REVISAR: no se reconoció la tabla {nombre_tabla}'}
    filas = []
    for numero_fila, (arriba, abajo) in enumerate(configuracion['filas'], start=1):
        campos = {}
        for nombre, (izquierda, derecha) in configuracion['columnas'].items():
            original = leer_texto_bienes(pagina, (izquierda, arriba, derecha, abajo))
            vacio = not original
            if nombre in configuracion['importes']:
                vacio = not re.sub('[$\\s]', '', original)
            campos[nombre] = {'original': original, 'valor': None if vacio else original, 'estado': 'VACIO' if vacio else 'OK', 'motivo': ''}
        fila_vacia = all((campo['estado'] == 'VACIO' for campo in campos.values()))
        if fila_vacia:
            for campo in campos.values():
                campo['estado'] = 'OPCIONAL'
            filas.append({'fila': numero_fila, 'campos': campos, 'estado': 'OPCIONAL'})
            continue
        for nombre, campo in campos.items():
            if campo['estado'] == 'VACIO':
                campo['estado'] = 'RECHAZADO'
                campo['motivo'] = 'Debe completar toda la fila'
                continue
            if nombre == 'Dirección':
                valor, estado, motivo = normalizar_direccion_bienes(campo['original'])
                campo['valor'] = valor
                campo['estado'] = estado
                campo['motivo'] = motivo
            elif nombre in configuracion['importes']:
                try:
                    campo['valor'] = convertir_importe_bienes(campo['original'])
                except ValueError:
                    campo['valor'] = None
                    campo['estado'] = 'POR REVISAR'
                    campo['motivo'] = 'Importe no reconocido'
        estados = [campo['estado'] for campo in campos.values()]
        if 'RECHAZADO' in estados:
            estado_fila = 'RECHAZADO'
        elif 'POR REVISAR' in estados:
            estado_fila = 'POR REVISAR'
        else:
            estado_fila = 'OK'
        filas.append({'fila': numero_fila, 'campos': campos, 'estado': estado_fila})
    estados_filas = [fila['estado'] for fila in filas]
    if 'RECHAZADO' in estados_filas:
        general = 'RECHAZADO'
    elif 'POR REVISAR' in estados_filas:
        general = 'POR REVISAR'
    elif all((estado == 'OPCIONAL' for estado in estados_filas)):
        general = 'OK — Bloque opcional sin diligenciar'
    else:
        general = 'OK'
    return {'filas': filas, 'estado': general}

def extraer_inmuebles_y_vehiculos(contenido):
    with pdfplumber.open(BytesIO(contenido), pages=[1]) as pdf:
        if not pdf.pages:
            return {'error': 'El PDF no contiene primera página'}
        pagina = pdf.pages[0]
        compatible = abs(pagina.width - 612) < 1 and abs(pagina.height - 935.433) < 1
        if not compatible:
            return {'error': 'POR REVISAR: tamaño de plantilla no reconocido'}
        return {nombre: extraer_tabla_bienes(pagina, nombre, configuracion) for nombre, configuracion in TABLAS_BIENES.items()}
