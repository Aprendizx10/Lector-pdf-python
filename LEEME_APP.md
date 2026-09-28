# Aplicación de escritorio

1. Ejecute **Instalar.bat** una sola vez si las dependencias no están instaladas.
2. Abra **Abrir lector.bat**.
3. Pulse **Seleccionar PDF** y seleccione uno o varios archivos.
4. Pulse **Procesar**. La primera lectura puede descargar los modelos OCR.
5. Al finalizar, pulse **Guardar Excel** y elija dónde guardarlo.

El libro contiene Datos, Detalle, Errores y Comprobaciones. Un documento con errores
no detiene el resto del lote. El botón Detener actúa al terminar el archivo actual;
los resultados procesados se pueden exportar. Un lote detenido no incluye los
archivos pendientes en Excel. El estado Procesado indica ejecución, no aprobación
de las reglas. Las validaciones están en Detalle y las sumas/restas en Comprobaciones.

La aplicación utiliza el motor ya desarrollado: analiza la primera página de la
plantilla UNIMOS y aplica OCR en cuatro campos. La segunda página sigue pendiente.
Los PDF originales no se modifican. La primera descarga de modelos requiere Internet;
los recortes se procesan localmente. Las versiones instaladas deben validarse antes
de distribuir a otros equipos.

Esta entrega es una aplicación Python con lanzador de Windows; no es todavía un
ejecutable autónomo. Para instalar desde cero en otro equipo se requiere Python
3.12 de 64 bits, con Tcl/Tk y el lanzador `py`, y conexión para descargar paquetes.
No copie `.venv` a otro equipo: ejecute allí Instalar.bat para crear su entorno.

Si la ventana no abre, ejecute `.venv\Scripts\python.exe app_escritorio.py` desde
esta carpeta para ver el error. Cuando se abre sin consola, los mensajes del OCR
se guardan en `logs/aplicacion.log`.
