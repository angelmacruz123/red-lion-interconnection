@echo off
chcp 65001 >nul
title RED-LION-INTERCONNECTION
cd /d "%~dp0"

echo ==========================================================
echo   RED-LION-INTERCONNECTION - inicio automatico
echo ==========================================================

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo.
  echo [ERROR] No se encontro Python en este equipo.
  echo Instalelo desde https://www.python.org/downloads/ marcando
  echo "Add Python to PATH" y vuelva a ejecutar este archivo.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Creando entorno virtual .venv ...
  %PY% -m venv .venv || (echo [ERROR] No se pudo crear el entorno. & pause & exit /b 1)
)

echo [2/3] Instalando/verificando dependencias (la primera vez tarda 1-3 min)...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt || (echo [ERROR] Fallo la instalacion. & pause & exit /b 1)

if not exist ".env" copy ".env.example" ".env" >nul

echo [3/3] Abriendo la aplicacion en http://localhost:8501
echo       (para detenerla cierre esta ventana o presione Ctrl+C)
echo.
".venv\Scripts\python.exe" -m streamlit run app.py --server.headless false --browser.gatherUsageStats false
pause
