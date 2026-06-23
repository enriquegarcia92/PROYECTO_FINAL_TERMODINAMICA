# VLE Gamma-Phi — Motor termodinámico para Windows

Aplicación de escritorio para validar el flujo, la arquitectura y la experiencia de usuario del proyecto VLE gamma-phi.

> **Advertencia:** esta versión ya incluye cálculos termodinámicos reales para sistemas con datos completos documentados. Si faltan parámetros, el cálculo se bloquea en vez de inventar valores.

## Usuarios destino

Esta documentación está escrita para Windows. Aunque el código pueda ejecutarse en otros sistemas durante desarrollo, las instrucciones de uso, instalación y distribución del proyecto final se enfocan exclusivamente en computadoras Windows.

## Qué incluye

- Siete vistas: Inicio, Nuevo cálculo, Resultados, Diagrama, Validaciones, Base de datos y Acerca de.
- Flujos BUBL P, DEW P, BUBL T y DEW T con motor termodinámico real.
- Antoine con convención `ln(Psat[kPa]) = A - B/(T[°C] + C)`.
- Corrección gamma-phi con Pitzer/virial, `phi_i`, `phi_i_sat` y Poynting.
- Sistemas binarios y ternario demostrativos.
- Selección de Wilson, Margules y Van Laar.
- Comparación visual con `phi = 1`.
- Diagramas Pxy/Txy exportables a PNG/PDF mediante ventana “Guardar como”.
- Resultados exportables a TXT mediante ventana “Guardar como”.
- Validaciones reales de composiciones, presión, temperatura y disponibilidad de parámetros.
- CLI que consume el mismo contrato de dominio.
- Pruebas automatizadas y configuración PyInstaller para generar `.exe` en Windows.

## Regla de unidades de temperatura

El usuario ingresa temperaturas en grados Celsius (`°C`). Internamente, la aplicación convierte esas temperaturas a Kelvin (`K`) antes de enviarlas al servicio de cálculo, porque las fórmulas termodinámicas requieren temperatura absoluta. Los resultados y reportes pueden mostrar ambas unidades para trazabilidad.

## Opción recomendada para usuarios: ejecutar con doble clic

1. Extraiga el proyecto completo en una carpeta conocida, por ejemplo:

   ```text
   C:\Users\SuUsuario\Documents\PROYECTO_FINAL_TERMODINAMICA
   ```

2. Abra la carpeta del proyecto.

3. Haga doble clic en:

   ```text
   INICIAR_VLE_WINDOWS.bat
   ```

4. En la primera ejecución, el archivo prepara automáticamente el entorno `.venv` e instala las dependencias desde `requirements.txt`.

5. Cuando termine la preparación, se abrirá la aplicación.

No cierre la ventana negra mientras la aplicación esté abierta. Si ocurre un error, tome una captura de esa ventana y envíela al equipo de soporte.

## Requisitos para ejecutar desde código fuente en Windows

- Windows 10 u 11.
- Python 3.12, 3.13 o 3.14 instalado.
- Conexión a Internet durante la primera instalación de dependencias.
- Permiso para ejecutar archivos `.bat`.

Si Windows no reconoce Python, instálelo desde Microsoft Store o desde [python.org](https://www.python.org/downloads/windows/). Después cierre y vuelva a abrir la carpeta del proyecto antes de intentar nuevamente.

## Ejecución manual en Windows

Use esta ruta solo si el doble clic en `INICIAR_VLE_WINDOWS.bat` no es suficiente o si necesita depurar.

Abra PowerShell dentro de la carpeta del proyecto y ejecute:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Si no tiene Python 3.14, use:

```powershell
py -3 -m venv .venv
```

## CLI de consola

La aplicación también conserva una interfaz mínima de consola, requerida por el proyecto:

```powershell
.\.venv\Scripts\python.exe cli.py
```

## Exportación de diagramas y resultados

Desde la interfaz:

- En la vista **Diagrama**, use `Guardar PNG` o `Guardar PDF`.
- En la vista **Resultados**, después de ejecutar un cálculo, use `Guardar resultados TXT`.

En todos los casos se abre una ventana de Windows para elegir carpeta y nombre de archivo. La aplicación no obliga al usuario a guardar en una carpeta fija.

## Pruebas en Windows

Para validar la POC desde PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Las pruebas revisan validaciones, carga de datos, Antoine, modelos gamma, Pitzer, solvers VLE, estructura de resultados, exportación TXT y humo de interfaz.

## Generar el ejecutable `.exe` en Windows

PyInstaller debe ejecutarse en Windows para generar un `.exe` de Windows.

Primero genere la versión diagnosticable `onedir`:

```powershell
.\scripts\build_windows.ps1
```

El resultado esperado es:

```text
dist\VLE_GammaPhi\VLE_GammaPhi.exe
```

Después de validar esa carpeta, genere la versión final de archivo único:

```powershell
.\scripts\build_windows_onefile.ps1
```

El resultado esperado es:

```text
dist\VLE_GammaPhi.exe
```

## Arquitectura

- `vle_poc/domain.py`: contratos independientes de la interfaz.
- `vle_poc/repository.py`: carga del JSON demostrativo.
- `vle_poc/validation.py`: reglas reales de entrada.
- `vle_poc/properties.py`: Antoine y propiedades puras.
- `vle_poc/activity.py`: Wilson, Margules y Van Laar.
- `vle_poc/fugacity.py`: Pitzer/virial, fugacidad y Poynting.
- `vle_poc/service.py`: motor real de BUBL P, DEW P, BUBL T y DEW T.
- `vle_poc/exporters.py`: exportación TXT de resultados.
- `vle_poc/ui.py`: aplicación PySide6.
- `main.py` y `cli.py`: interfaces gráfica y de consola.

El motor expone `calculate(request) -> CalculationResult`. Los sistemas o modelos sin parámetros documentados se rechazan con un mensaje claro.

## Próxima etapa

Completar parámetros binarios documentados para más sistemas, robustecer validaciones bibliográficas y ampliar la batería contra ejemplos del capítulo 14.
