"""Ventana sencilla para el motor UNIMOS. Ejecutar con python app_escritorio.py."""
import importlib.util
from pathlib import Path
import queue
import threading
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

class Aplicacion(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Lector de solicitudes PDF')
        self.geometry('930x630')
        self.minsize(760,530)
        self.rutas=[]
        self.resultados=[]
        self.motor=None
        self.ocupado=False
        self.eventos=queue.Queue()
        self.detener=threading.Event()
        self.protocol('WM_DELETE_WINDOW',self.cerrar)
        estilo=ttk.Style(self)
        if 'vista' in estilo.theme_names(): estilo.theme_use('vista')
        estilo.configure('Treeview',rowheight=28)
        marco=ttk.Frame(self,padding=20)
        marco.pack(fill='both',expand=True)
        ttk.Label(marco,text='Lector de solicitudes PDF',font=('Segoe UI',19,'bold')).pack(anchor='w')
        ttk.Label(marco,text='Selecciona los archivos, procesa el lote y guarda un Excel con los resultados.').pack(anchor='w',pady=(6,3))
        ttk.Label(marco,text='Primera página · Cuatro campos con OCR').pack(anchor='w',pady=(0,15))
        botones=ttk.Frame(marco)
        botones.pack(fill='x',pady=(0,12))
        self.agregar=ttk.Button(botones,text='1. Seleccionar PDF',command=self.seleccionar)
        self.agregar.pack(side='left')
        self.limpiar=ttk.Button(botones,text='Limpiar lista',command=self.vaciar)
        self.limpiar.pack(side='left',padx=8)
        self.procesar=ttk.Button(botones,text='2. Procesar',command=self.iniciar,state='disabled')
        self.procesar.pack(side='left',padx=8)
        self.guardar=ttk.Button(botones,text='3. Guardar Excel',command=self.exportar,state='disabled')
        self.guardar.pack(side='right')
        tabla_marco=ttk.Frame(marco)
        tabla_marco.pack(fill='both',expand=True)
        self.tabla=ttk.Treeview(tabla_marco,columns=('archivo','proceso','validacion'),show='headings',height=9)
        for key,titulo,ancho in [('archivo','Archivo',420),('proceso','Procesamiento',170),('validacion','Campos por revisar',150)]:
            self.tabla.heading(key,text=titulo)
            self.tabla.column(key,width=ancho,minwidth=90)
        scroll=ttk.Scrollbar(tabla_marco,orient='vertical',command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=scroll.set)
        self.tabla.pack(side='left',fill='both',expand=True)
        scroll.pack(side='right',fill='y')
        self.barra=ttk.Progressbar(marco,mode='determinate')
        self.barra.pack(fill='x',pady=(15,6))
        self.estado=tk.StringVar(value='Selecciona uno o varios PDF para comenzar.')
        ttk.Label(marco,textvariable=self.estado,wraplength=850).pack(anchor='w')
        self.cancelar=ttk.Button(marco,text='Detener después del archivo actual',command=self.pedir_detener,state='disabled')
        self.cancelar.pack(anchor='w',pady=8)
        self.mensajes=tk.Text(marco,height=6,wrap='word',font=('Segoe UI',9),state='disabled')
        self.mensajes.pack(fill='x')
        ttk.Label(marco,text='Los avisos y reglas de validación se incluyen en Excel. Procesado no significa aprobado.').pack(anchor='w',pady=(8,0))
        self.after(150,self.recibir)

    def anotar(self,texto):
        self.mensajes.configure(state='normal')
        self.mensajes.insert('end',texto+'\n')
        self.mensajes.see('end')
        self.mensajes.configure(state='disabled')

    def seleccionar(self):
        rutas=filedialog.askopenfilenames(parent=self,title='Seleccionar solicitudes PDF',filetypes=[('Documentos PDF','*.pdf')])
        if not rutas: return
        if self.resultados and not messagebox.askyesno('Nuevo lote','Se descartarán los resultados en memoria. ¿Continuar?',parent=self):return
        existentes={str(p).casefold() for p in self.rutas}
        for ruta in rutas:
            p=Path(ruta).resolve()
            if str(p).casefold() not in existentes:
                self.rutas.append(p)
                existentes.add(str(p).casefold())
        self.resultados=[]
        self.refrescar()

    def refrescar(self):
        self.tabla.delete(*self.tabla.get_children())
        for i,p in enumerate(self.rutas):self.tabla.insert('', 'end', iid=str(i),values=(p.name,'Pendiente','—'))
        self.procesar.configure(state='normal' if self.rutas else 'disabled')
        self.guardar.configure(state='disabled')
        self.barra['value']=0
        self.estado.set(f'{len(self.rutas)} archivos seleccionados.')

    def vaciar(self):
        if self.resultados and not messagebox.askyesno('Limpiar','¿Descartar los resultados en memoria?',parent=self):return
        self.rutas=[]
        self.resultados=[]
        self.refrescar()

    def iniciar(self):
        if self.ocupado or not self.rutas:return
        faltan=[m for m in ('pdfplumber','numpy','fitz','cv2','paddleocr','paddle','openpyxl') if importlib.util.find_spec(m) is None]
        if faltan:
            messagebox.showerror('Falta instalar dependencias','Ejecuta Instalar.bat y vuelve a abrir la aplicación.\n\nFaltan: '+', '.join(faltan),parent=self)
            return
        self.resultados=[]
        self.ocupado=True
        self.detener.clear()
        for boton in (self.agregar,self.limpiar,self.procesar,self.guardar):boton.configure(state='disabled')
        self.cancelar.configure(state='normal')
        self.barra.configure(maximum=len(self.rutas),value=0)
        self.estado.set('Preparando el motor. La primera ejecución puede descargar los modelos OCR.')
        self.anotar('Inicio del lote. La ventana seguirá respondiendo durante la lectura.')
        threading.Thread(target=self.trabajar,args=(list(self.rutas),),daemon=True).start()

    def trabajar(self,rutas):
        try:
            if self.motor is None:
                from lector_pdf.motor import MotorPDF
                self.motor=MotorPDF()
            elif self.motor.ocr.modelo is None:
                self.motor.ocr.error_inicio=None  # Permitir reintentar tras corregir la conexión.
            for i,ruta in enumerate(rutas):
                if self.detener.is_set():break
                self.eventos.put(('inicio',i,ruta.name))
                try:resultado=self.motor.procesar_pdf(ruta)
                except Exception as exc:
                    resultado={'archivo':ruta.name,'estado_proceso':'ERROR','campos':[],
                               'errores':[{'mensaje':str(exc)}]}
                self.eventos.put(('resultado',i,resultado))
        except Exception as exc:self.eventos.put(('error',str(exc)))
        finally:self.eventos.put(('fin',))

    def pedir_detener(self):
        self.detener.set()
        self.cancelar.configure(state='disabled')
        self.estado.set('Se detendrá al finalizar el archivo actual; podrás guardar lo procesado.')

    def recibir(self):
        try:
            while True:
                evento=self.eventos.get_nowait()
                if evento[0]=='inicio':
                    _,i,nombre=evento
                    self.tabla.set(str(i),'proceso','Procesando…')
                    self.estado.set(f'Procesando {i+1}/{len(self.rutas)}: {nombre}')
                elif evento[0]=='resultado':
                    _,i,r=evento
                    self.resultados.append(r)
                    estado={'COMPLETADO':'Procesado','PARCIAL':'Procesado con errores','ERROR':'Error'}.get(r['estado_proceso'],r['estado_proceso'])
                    avisos=sum(c.get('validacion') in ('RECHAZADO','POR REVISAR','NO VERIFICABLE') for c in r.get('campos',[]))
                    self.tabla.set(str(i),'proceso',estado)
                    self.tabla.set(str(i),'validacion',avisos)
                    self.barra['value']=len(self.resultados)
                    self.anotar(f"{r['archivo']}: {estado}.")
                    for error in r.get('errores',[]):self.anotar('  '+error.get('mensaje','Error de lectura'))
                elif evento[0]=='error':self.anotar('Error: '+evento[1])
                elif evento[0]=='fin':
                    self.ocupado=False
                    for boton in (self.agregar,self.limpiar,self.procesar):boton.configure(state='normal')
                    self.cancelar.configure(state='disabled')
                    self.guardar.configure(state='normal' if self.resultados else 'disabled')
                    self.estado.set(f'{len(self.resultados)} de {len(self.rutas)} archivos procesados. Guarda el Excel para consultar los resultados.')
        except queue.Empty:pass
        self.after(150,self.recibir)

    def exportar(self):
        if not self.resultados:return
        destino=filedialog.asksaveasfilename(parent=self,title='Guardar resultados',defaultextension='.xlsx',
                    initialfile='Informacion_extraida.xlsx',filetypes=[('Libro de Excel','*.xlsx')])
        if not destino:return
        try:
            from lector_pdf.excel import exportar_excel
            exportar_excel(self.resultados,destino)
            self.estado.set('Excel guardado: '+destino)
            messagebox.showinfo('Excel guardado','El archivo se guardó correctamente.\n\n'+destino,parent=self)
        except PermissionError:messagebox.showerror('No se pudo guardar','Cierra el archivo en Excel o elige otra ubicación.',parent=self)
        except Exception as exc:messagebox.showerror('No se pudo guardar',str(exc),parent=self)

    def cerrar(self):
        if self.ocupado:
            messagebox.showinfo('Procesamiento en curso','Pulsa Detener y espera a que termine el archivo actual antes de cerrar.',parent=self)
            return
        self.destroy()

if __name__=='__main__':
    if sys.stdout is None or sys.stderr is None:
        carpeta_logs=Path(__file__).parent/'logs'
        carpeta_logs.mkdir(exist_ok=True)
        registro=(carpeta_logs/'aplicacion.log').open('a',encoding='utf-8',buffering=1)
        if sys.stdout is None:sys.stdout=registro
        if sys.stderr is None:sys.stderr=registro
    Aplicacion().mainloop()
