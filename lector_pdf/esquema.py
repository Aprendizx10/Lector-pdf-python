"""Contrato común v1. Vacío, fallo de lectura y validación son independientes."""
from decimal import Decimal

def serializable(valor):
    if isinstance(valor, Decimal):
        return int(valor) if valor == valor.to_integral_value() else format(valor, 'f')
    if isinstance(valor, dict): return {str(k): serializable(v) for k,v in valor.items()}
    if isinstance(valor, (tuple,list,set)): return [serializable(v) for v in valor]
    return valor

def normalizar_campos(seccion, datos):
    campos = []
    def recorrer(nodo, ruta):
        if isinstance(nodo, dict):
            if 'estado' in nodo and ('valor' in nodo or 'opciones_marcadas' in nodo):
                valor = nodo.get('valor', nodo.get('opciones_marcadas'))
                estado = nodo.get('estado','')
                motivo = nodo.get('motivo', nodo.get('aclaracion',''))
                metodo = nodo.get('metodo', 'texto')
                if 'opciones_marcadas' in nodo or ruta[-1] in (
                    'Tipo de documento','Estado civil','Nivel de estudios','Tipo de vivienda',
                    'Clase de vivienda','Envío de correspondencia','Canal de contacto'):
                    metodo = 'seleccion'
                sin_valor = valor is None or valor == '' or valor == []
                error_ocr = 'no se pudo ejecutar' in motivo.lower()
                lectura = ('error' if error_ocr else 'sin_lectura' if sin_valor and
                           (metodo=='OCR' or estado=='POR REVISAR')
                           else 'vacio' if sin_valor else 'leido')
                original = nodo.get('original', nodo.get('texto_ocr_original'))
                # No inventar un original que el extractor previo no conservó.
                original_disponible = original is not None
                if not original_disponible and isinstance(valor,str) and metodo != 'OCR':
                    original, original_disponible = valor, True
                campos.append({'id':'.'.join([seccion]+ruta), 'seccion':seccion,
                    'campo':ruta[-1], 'pagina':1, 'valor_original':serializable(original),
                    'original_disponible':original_disponible,
                    'valor_normalizado':serializable(None if sin_valor else valor),
                    'lectura':lectura, 'validacion':estado,
                    'motivo':motivo, 'metodo':metodo.lower(),
                    'confianza_ocr':nodo.get('confianza_ocr')})
                return
            for k,v in nodo.items():
                if k not in ('comprobaciones',): recorrer(v,ruta+[str(k)])
        elif isinstance(nodo,list):
            for i,v in enumerate(nodo): recorrer(v,ruta+[str(i+1)])
    recorrer(datos,[])
    return campos
