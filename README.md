# VLE Gamma-Phi — POC PySide6

Aplicación de escritorio para validar el flujo, la arquitectura y la experiencia de usuario del proyecto VLE gamma-phi.

> **Advertencia:** todos los resultados termodinámicos y diagramas de esta versión son simulados. No deben utilizarse para cálculos ni decisiones de ingeniería.

## Qué incluye

- Siete vistas: Inicio, Nuevo cálculo, Resultados, Diagrama, Validaciones, Base de datos y Acerca de.
- Flujos BUBL P, DEW P, BUBL T y DEW T con un servicio determinista simulado.
- Sistemas binarios y ternario demostrativos.
- Selección de Wilson, Margules y Van Laar.
- Comparación visual con `phi = 1`.
- Diagramas Pxy/Txy exportables a PNG/PDF.
- Validaciones reales de composiciones, presión, temperatura y disponibilidad de parámetros.
- CLI que consume el mismo contrato de dominio.
- Pruebas automatizadas y configuración PyInstaller.

## Requisitos

- Python 3.12–3.14.
- macOS para ejecutar esta POC local o Windows para generar el `.exe`.

## Instalación en macOS/Linux

```bash
cd PROYECTO_FINAL_TERMODINAMICA
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```

`requirements-lock.txt` conserva las versiones exactas verificadas con Python 3.14.5 en esta POC.

## Ejecución

GUI:

```bash
.venv/bin/python main.py
```

CLI:

```bash
.venv/bin/python cli.py
```

Pruebas:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest
```

## Diagramas y resultados

Durante el desarrollo se guardan en `resultados/`. En el ejecutable se guardarán en `Documentos/VLE Gamma-Phi/resultados/`, porque los recursos internos de PyInstaller no son escribibles de forma permanente.

## Build Windows

PyInstaller no genera un `.exe` de Windows desde macOS. En una computadora Windows, abra PowerShell dentro del proyecto y ejecute:

```powershell
.\scripts\build_windows.ps1
```

El primer entregable de empaquetado será `dist\VLE_GammaPhi\VLE_GammaPhi.exe` en modo `onedir`, más fácil de diagnosticar. Después de validarlo se preparará la variante `onefile --windowed`.

Tras validar `onedir`, el ejecutable único se genera con:

```powershell
.\scripts\build_windows_onefile.ps1
```

## Arquitectura

- `vle_poc/domain.py`: contratos independientes de la interfaz.
- `vle_poc/repository.py`: carga del JSON demostrativo.
- `vle_poc/validation.py`: reglas reales de entrada.
- `vle_poc/service.py`: servicio simulado reemplazable.
- `vle_poc/ui.py`: aplicación PySide6.
- `main.py` y `cli.py`: interfaces gráfica y de consola.

El núcleo real deberá implementar el mismo método `calculate(request) -> CalculationResult`, permitiendo reemplazar la simulación sin reconstruir la GUI.

## Próxima etapa

Implementar Antoine, Pitzer, Wilson, Margules, Van Laar y los cuatro algoritmos iterativos; después sustituir `MockVLEService` por el servicio termodinámico validado contra el capítulo 14.
