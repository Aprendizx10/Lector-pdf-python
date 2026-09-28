import argparse
import json
from pathlib import Path
from .motor import MotorPDF

def main():
    parser = argparse.ArgumentParser(description='Extractor UNIMOS: motor sin interfaz ni Excel')
    parser.add_argument('entradas',nargs='+',type=Path)
    parser.add_argument('--salida',type=Path,default=Path('resultados.json'))
    args = parser.parse_args()
    rutas = [p for entrada in args.entradas for p in
             (sorted(entrada.glob('*.pdf')) if entrada.is_dir() else [entrada])]
    if not rutas: parser.error('No se encontraron archivos PDF')
    resultados = MotorPDF().procesar_lote(rutas)
    args.salida.parent.mkdir(parents=True,exist_ok=True)
    args.salida.write_text(json.dumps(resultados,ensure_ascii=False,indent=2),encoding='utf-8')
    for r in resultados: print(f"{r['archivo']}: {r['estado_proceso']}")
    print(f'Salida: {args.salida.resolve()}')

if __name__ == '__main__': main()
