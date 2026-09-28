from pathlib import Path
from hashlib import sha256
from datetime import datetime, timezone
import time
from .recursos import SesionPDF, ServicioOCR
from .esquema import normalizar_campos, serializable
from .secciones import credito, basica, laboral, actividad, conyuge, financiera, bienes, internacionales

SECCIONES = [
    ('credito', credito.extraer_informacion_credito),
    ('basica', basica.extraer_basica),
    ('laboral', laboral.extraer_informacion_laboral),
    ('actividad', actividad.extraer_actividad_economica),
    ('conyuge', conyuge.extraer_datos_conyuge),
    ('financiera', financiera.extraer_informacion_financiera),
    ('bienes', bienes.extraer_inmuebles_y_vehiculos),
    ('internacionales', internacionales.extraer_operaciones_internacionales),
]

class MotorPDF:
    def __init__(self): self.ocr = ServicioOCR()

    def procesar_pdf(self, ruta):
        inicio = time.perf_counter()
        ruta = Path(ruta)
        resultado = {'version_esquema':'1.0', 'plantilla':'unimos_v1', 'archivo':ruta.name,
                     'paginas_implementadas':[1], 'segunda_pagina_implementada':False,
                     'fecha_proceso':datetime.now(timezone.utc).isoformat(),
                     'secciones':{}, 'campos':[], 'errores':[], 'metricas':{}}
        try:
            contenido = ruta.read_bytes()
            resultado['documento_id'] = sha256(contenido).hexdigest()
            llamadas, segundos = self.ocr.llamadas, self.ocr.segundos
            with SesionPDF(contenido,self.ocr) as sesion:
                # Detectar PDF inválido una sola vez.
                with sesion.abrir_texto() as pdf:
                    if not pdf.pages: raise ValueError('El documento no tiene primera página')
                for nombre,extraer in SECCIONES:
                    t = time.perf_counter()
                    try:
                        datos = extraer(contenido)
                    except Exception as exc:
                        datos = {'error':f'{type(exc).__name__}: {exc}'}
                    resultado['secciones'][nombre] = serializable(datos)
                    resultado['campos'].extend(normalizar_campos(nombre,datos))
                    if 'error' in datos: resultado['errores'].append({'seccion':nombre,'mensaje':datos['error']})
                    resultado['metricas'][nombre+'_segundos'] = round(time.perf_counter()-t,4)
                resultado['metricas'].update(aperturas_pdf_texto=sesion.aperturas_texto,
                    aperturas_pdf_render=sesion.aperturas_render,
                    llamadas_ocr=self.ocr.llamadas-llamadas,
                    ocr_segundos=round(self.ocr.segundos-segundos,4))
            # Fallos OCR capturados dentro de los lectores también son errores técnicos.
            for c in resultado['campos']:
                if c['lectura']=='error':
                    resultado['errores'].append({'campo':c['id'],'mensaje':c['motivo']})
            resultado['estado_proceso'] = 'PARCIAL' if resultado['errores'] else 'COMPLETADO'
        except Exception as exc:
            resultado['estado_proceso'] = 'ERROR'
            resultado['errores'].append({'mensaje':f'{type(exc).__name__}: {exc}'})
        resultado['metricas']['total_segundos'] = round(time.perf_counter()-inicio,4)
        return resultado

    def procesar_lote(self, rutas):
        # Modelo compartido durante todo el lote. Un fallo no detiene los demás PDF.
        return [self.procesar_pdf(ruta) for ruta in rutas]
