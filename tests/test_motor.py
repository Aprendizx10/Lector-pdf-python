import ast
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch
from tempfile import TemporaryDirectory
from decimal import Decimal
from lector_pdf.motor import MotorPDF, SECCIONES
from lector_pdf.recursos import ServicioOCR
from lector_pdf.esquema import normalizar_campos, serializable

class TestContrato(unittest.TestCase):
    def test_cero_y_vacio(self):
        c=normalizar_campos('prueba',{'cero':{'valor':Decimal('0'),'estado':'EXTRAIDO'},
                                    'vacio':{'valor':None,'estado':'VACIO'}})
        self.assertEqual(c[0]['valor_normalizado'],0)
        self.assertEqual(c[0]['lectura'],'leido')
        self.assertIsNone(c[1]['valor_normalizado'])
        self.assertEqual(c[1]['lectura'],'vacio')

    def test_ocr_no_es_vacio_confirmado(self):
        c=normalizar_campos('prueba',{'p':{'valor':'','estado':'OPCIONAL','metodo':'OCR'}})[0]
        self.assertEqual(c['lectura'],'sin_lectura')
        self.assertEqual(c['validacion'],'OPCIONAL')

    def test_importe_ilegible(self):
        c=normalizar_campos('prueba',{'p':{'valor':None,'original':'ABC','estado':'POR REVISAR'}})[0]
        self.assertEqual(c['lectura'],'sin_lectura')

    def test_precision_decimal(self):
        self.assertEqual(serializable(Decimal('1234.50')),'1234.50')

    def test_error_no_detiene_lote(self):
        with TemporaryDirectory() as d:
            resultados=MotorPDF().procesar_lote([Path(d)/'a.pdf',Path(d)/'b.pdf'])
            self.assertEqual([r['estado_proceso'] for r in resultados],['ERROR','ERROR'])

    def test_modelo_reutilizado(self):
        class Modelo:
            def predict(self, imagen): return iter([{'rec_texts':['Ejemplo']}])
        servicio=ServicioOCR()
        servicio.modelo=Modelo()
        servicio.predict(None)
        servicio.predict(None)
        self.assertEqual(servicio.llamadas,2)
        self.assertEqual(servicio.cargas,0)

    @unittest.skipUnless(os.environ.get('PDF_TEST_DIR'),'Requiere PDF_TEST_DIR')
    def test_muestras_y_apertura_unica(self):
        rutas=sorted(Path(os.environ['PDF_TEST_DIR']).glob('*.pdf'))
        self.assertEqual(len(rutas),5)
        motor=MotorPDF()
        for ruta in rutas:
            r=motor.procesar_pdf(ruta)
            self.assertEqual(r['metricas']['aperturas_pdf_texto'],1)
            self.assertEqual(len(r['secciones']),8)
            self.assertGreater(len(r['campos']),100)
            self.assertTrue(all(c['pagina']==1 for c in r['campos']))
            self.assertEqual(r['secciones']['credito']['estado_selecciones'],
                             'RECHAZADO' if '42' in ruta.name else 'OK')
            json.dumps(r)

    @unittest.skipUnless(os.environ.get('PDF_TEST_DIR') and os.environ.get('NOTEBOOK_TEST_PATH'),
                         'Requiere las muestras y el cuaderno original')
    def test_regresion_secciones_sin_ocr(self):
        notebook=json.loads(Path(os.environ['NOTEBOOK_TEST_PATH']).read_text(encoding='utf-8'))
        indices={'credito':2,'actividad':8,'financiera':12,'bienes':14,'internacionales':16}
        referencias={}
        for nombre,idx in indices.items():
            tree=ast.parse(''.join(notebook['cells'][idx]['source']))
            nodes=[]
            for node in tree.body:
                if isinstance(node,(ast.Import,ast.FunctionDef)):nodes.append(node)
                elif isinstance(node,ast.ImportFrom) and node.module!='google.colab':nodes.append(node)
                elif isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name) and node.targets[0].id.isupper():nodes.append(node)
            namespace={}
            exec(compile(ast.Module(body=nodes,type_ignores=[]),'<cuaderno>','exec'),namespace)
            funcion=dict(SECCIONES)[nombre].__name__
            referencias[nombre]=namespace[funcion]
        motor=MotorPDF()
        for ruta in sorted(Path(os.environ['PDF_TEST_DIR']).glob('*.pdf')):
            resultado=motor.procesar_pdf(ruta)
            for nombre,extraer in referencias.items():
                self.assertEqual(resultado['secciones'][nombre],serializable(extraer(ruta.read_bytes())),
                                 (ruta.name,nombre))

if __name__=='__main__': unittest.main()
