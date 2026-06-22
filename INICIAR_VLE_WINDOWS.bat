@echo off
setlocal EnableExtensions
chcp 65001 >nul
title VLE Gamma-Phi - Inicio para Windows

rem Trabajar siempre desde la carpeta donde se encuentra este archivo.
cd /d "%~dp0"

echo ============================================================
echo              VLE Gamma-Phi - Inicio para Windows
echo ============================================================
echo.

if not exist "main.py" (
    echo [ERROR] No se encontro main.py.
    echo.
    echo Mantenga INICIAR_VLE_WINDOWS.bat en la carpeta principal
    echo del proyecto, junto a main.py y requirements.txt.
    goto :error
)

if not exist "requirements.txt" (
    echo [ERROR] No se encontro requirements.txt.
    echo El proyecto parece estar incompleto o dentro de un ZIP.
    echo Extraiga nuevamente todos los archivos antes de continuar.
    goto :error
)

rem En la primera ejecucion se crea el entorno virtual y se instalan paquetes.
if not exist ".venv\Scripts\python.exe" (
    echo No se encontro el entorno virtual .venv.
    echo Se preparara automaticamente. Esto solo ocurre la primera vez.
    echo Se necesita conexion a Internet y puede tardar varios minutos.
    echo.

    where py >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python no esta instalado o el comando py no esta disponible.
        echo.
        echo Instale Python 3.14 desde Microsoft Store o python.org,
        echo cierre esta ventana y vuelva a ejecutar este archivo.
        goto :error
    )

    echo [1/3] Creando el entorno virtual...
    py -3.14 -m venv ".venv" >nul 2>&1
    if errorlevel 1 (
        echo Python 3.14 no esta disponible. Intentando con Python 3...
        py -3 -m venv ".venv"
        if errorlevel 1 (
            echo [ERROR] No fue posible crear el entorno virtual.
            goto :error
        )
    )

    echo [2/3] Actualizando el instalador de paquetes...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    if errorlevel 1 (
        echo [ERROR] No fue posible actualizar pip.
        echo Revise la conexion a Internet e intentelo nuevamente.
        goto :error
    )

    echo [3/3] Instalando las dependencias del proyecto...
    ".venv\Scripts\python.exe" -m pip install -r "requirements.txt"
    if errorlevel 1 (
        echo [ERROR] No fue posible instalar las dependencias.
        echo Revise la conexion a Internet y los mensajes anteriores.
        goto :error
    )

    echo.
    echo Entorno preparado correctamente.
    echo.
)

echo Activando el entorno virtual...
call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] No fue posible activar el entorno virtual.
    goto :error
)

echo Abriendo VLE Gamma-Phi...
echo No cierre esta ventana mientras utiliza la aplicacion.
echo.

python "main.py"
set "APP_EXIT_CODE=%ERRORLEVEL%"

call deactivate >nul 2>&1

if not "%APP_EXIT_CODE%"=="0" (
    echo.
    echo [ERROR] La aplicacion termino con el codigo %APP_EXIT_CODE%.
    echo Tome una captura de esta ventana y enviela al equipo de soporte.
    goto :error
)

echo.
echo La aplicacion se cerro correctamente.
timeout /t 2 /nobreak >nul
exit /b 0

:error
echo.
echo ============================================================
echo La aplicacion no pudo iniciarse.
echo Revise el mensaje anterior o consulte el manual de instalacion.
echo ============================================================
echo.
pause
exit /b 1
