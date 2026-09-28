@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    py -3.12 -m venv .venv
    if errorlevel 1 (
        echo Instala Python 3.12 de 64 bits con el lanzador py y vuelve a ejecutar este archivo.
        pause
        exit /b 1
    )
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo No se pudo completar la instalacion. Revisa los mensajes anteriores.
    pause
    exit /b 1
)
echo Instalacion completada. Abre "Abrir lector.bat".
pause
