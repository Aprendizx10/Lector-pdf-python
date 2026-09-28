"""Recursos compartidos. Una sesión por PDF y un modelo OCR por motor.

El motor procesa secuencialmente; no compartir un motor entre hilos.
"""
from contextlib import ExitStack, nullcontext
from contextvars import ContextVar
from io import BytesIO
import importlib
import time
import pdfplumber as _pdfplumber

_actual = ContextVar('documento_actual')

class ModuloDiferido:
    def __init__(self, nombre): self.nombre = nombre
    def __getattr__(self, nombre):
        return getattr(importlib.import_module(self.nombre), nombre)

cv2 = ModuloDiferido('cv2')

class ServicioOCR:
    def __init__(self):
        self.modelo = None
        self.error_inicio = None
        self.llamadas = 0
        self.segundos = 0.0
        self.cargas = 0

    def predict(self, imagen):
        inicio = time.perf_counter()
        try:
            if self.error_inicio:
                raise RuntimeError(self.error_inicio)
            if self.modelo is None:
                try:
                    from paddleocr import PaddleOCR
                    self.modelo = PaddleOCR(lang='es', device='cpu', enable_mkldnn=False,
                        use_doc_orientation_classify=False, use_doc_unwarping=False,
                        use_textline_orientation=False)
                    self.cargas += 1
                except Exception as exc:
                    self.error_inicio = str(exc)
                    raise
            self.llamadas += 1
            # Consumir el generador aquí para medir toda la inferencia.
            return list(self.modelo.predict(imagen))
        finally:
            self.segundos += time.perf_counter() - inicio

class SesionPDF:
    def __init__(self, contenido, ocr):
        self.contenido = contenido
        self.ocr = ocr
        self.texto = None
        self.render = None
        self.aperturas_texto = 0
        self.aperturas_render = 0

    def __enter__(self):
        self.stack = ExitStack()
        self.token = _actual.set(self)
        return self

    def __exit__(self, *args):
        try: return self.stack.__exit__(*args)
        finally: _actual.reset(self.token)

    def abrir_texto(self):
        if self.texto is None:
            # Etapa implementada: página 1. Nunca analizar anexos.
            self.texto = self.stack.enter_context(_pdfplumber.open(BytesIO(self.contenido), pages=[1]))
            self.aperturas_texto += 1
        return nullcontext(self.texto)

    def abrir_render(self):
        if self.render is None:
            fitz = importlib.import_module('fitz')
            self.render = self.stack.enter_context(fitz.open(stream=self.contenido, filetype='pdf'))
            self.aperturas_render += 1
        return nullcontext(self.render)

class APITexto:
    def open(self, *args, **kwargs):
        if kwargs.get('pages') != [1]:
            raise ValueError('Esta versión solo permite la primera página')
        return _actual.get().abrir_texto()

class APIRender:
    def open(self, *args, **kwargs): return _actual.get().abrir_render()
    def __getattr__(self, nombre): return getattr(importlib.import_module('fitz'), nombre)

class ProxyOCR:
    def predict(self, imagen): return _actual.get().ocr.predict(imagen)

pdf_api = APITexto()
render_api = APIRender()
ocr_proxy = ProxyOCR()
