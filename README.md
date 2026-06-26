# VLE Gamma-Phi — Motor termodinámico para Windows

Aplicación de escritorio BETA para resolver cálculos VLE gamma-phi en sistemas documentados disponibles.

> **Advertencia:** esta versión ya incluye cálculos termodinámicos reales para sistemas con datos completos documentados. Si faltan parámetros, el cálculo se bloquea en vez de inventar valores.

## Usuarios destino

Esta documentación está escrita para Windows. Aunque el código pueda ejecutarse en otros sistemas durante desarrollo, las instrucciones de uso, instalación y distribución del proyecto final se enfocan exclusivamente en computadoras Windows.

## Qué incluye

- Siete vistas: Inicio, Nuevo cálculo, Resultados, Diagrama, Validaciones, Base de datos y Acerca de.
- Flujos BUBL P, DEW P, BUBL T y DEW T con motor termodinámico real.
- Antoine con convención `ln(Psat[kPa]) = A - B/(T[°C] + C)`.
- Corrección gamma-phi con Pitzer/virial, `phi_i`, `phi_i_sat` y Poynting.
- Modo separado EOS cúbica / phi-phi para gases ligeros del capítulo 14.
- Selector de sistemas fijos documentados; no permite combinaciones custom.
- Entrada de datos VLE `x/y/P/T` por usuario para ajustar Wilson, Margules y Van Laar cuando aplique.
- Ejemplos VLE precargados para algunos sistemas; se cargan explícitamente desde la interfaz si el usuario desea usarlos.
- Comparación visual con `phi = 1`.
- Diagramas Pxy/Txy generados automáticamente con cada cálculo y exportables a PNG/PDF mediante ventana “Guardar como”.
- Resultados exportables a TXT mediante ventana “Guardar como”.
- Validaciones reales de composiciones, presión, temperatura y disponibilidad de parámetros.
- CLI que consume el mismo contrato de dominio.
- Pruebas automatizadas y configuración PyInstaller para generar `.exe` en Windows.

## Regla de unidades de temperatura

El usuario ingresa temperaturas en grados Celsius (`°C`). Internamente, la aplicación convierte esas temperaturas a Kelvin (`K`) antes de enviarlas al servicio de cálculo, porque las fórmulas termodinámicas requieren temperatura absoluta. Los resultados y reportes pueden mostrar ambas unidades para trazabilidad.

## Sistemas disponibles en la BETA

En la vista **Nuevo cálculo**, el usuario selecciona un sistema documentado desde una lista fija. Ya no existe el botón **Agregar componente**, no se permiten sustancias custom y no se prometen combinaciones arbitrarias.

Sistemas Wilson directos del problema 14.54:

- Benceno / Tetracloruro de carbono.
- Benceno / Ciclohexano.
- Benceno / n-Heptano.
- Benceno / n-Hexano.
- Tetracloruro de carbono / Ciclohexano.
- Tetracloruro de carbono / n-Heptano.
- Tetracloruro de carbono / n-Hexano.
- Ciclohexano / n-Heptano.
- Ciclohexano / n-Hexano.

Sistemas con ejemplos VLE precargados:

- Ciclohexano / n-Heptano, con punto VLE limitado de validación.
- Acetona / Metanol, con datos VLE del problema 12.3.

Sistemas ternarios Wilson documentados:

- Acetona / Metanol / Agua, problemas 12.20 y 12.22, con parámetros energéticos Wilson de la Tabla 12.5.

Sistemas EOS cúbica / phi-phi del capítulo 14:

- Metano / n-Butano, Ejemplo 14.2, resuelto con Soave-Redlich-Kwong para reproducir el diagrama P-x-y a `100 °F = 310.93 K`.
- Nitrógeno / Metano, Ejemplo 14.1, resuelto con Redlich-Kwong para coeficientes de fugacidad en vapor y factor de compresibilidad `Z`.

Estos sistemas no usan Wilson, Margules, Van Laar, Antoine ni datos VLE de ajuste de usuario. Se separan del motor gamma-phi porque metano y nitrógeno son gases ligeros/criogénicos y pueden estar por encima de su temperatura crítica; forzarlos al enfoque Antoine + gamma sería científicamente falso.

Sistema especial del problema 14.27:

- Agua / n-Pentano / n-Heptano aparece únicamente con Wilson. Este problema describe dos fases líquidas inmiscibles; el método físicamente recomendado por el enunciado es fase vapor ideal + agua como fase líquida separada + ley de Raoult ideal para la fase hidrocarburo. Wilson se habilita solo por requerimiento del proyecto y no debe interpretarse como el modelo correcto para LLE/VLLE.

Reglas actuales:

- En sistemas binarios, la interfaz permite Wilson, Margules y Van Laar si el usuario proporciona datos VLE válidos.
- Margules y Van Laar se permiten únicamente para sistemas binarios.
- Wilson multicomponente requiere datos VLE binarios para todos los pares del sistema. En Agua / n-Pentano / n-Heptano se necesitan puntos para `water|n_pentane`, `water|n_heptane` y `n_pentane|n_heptane` si no existen parámetros bibliográficos cargados.
- Los datos VLE ingresados por el usuario se usan solo en la corrida actual y no modifican `base_datos_VLE.json`.
- Los diagramas se generan automáticamente como Pxy/Txy para sistemas binarios y como corte composicional equivalente para sistemas ternarios.
- En Metano / n-Butano el diagrama automático es P-x-y SRK a la temperatura ingresada; para reproducir el Ejemplo 14.2 use `37.78 °C` (`100 °F`).
- En Nitrógeno / Metano el gráfico automático no es Pxy/Txy: muestra `φ_N2`, `φ_CH4` y `Z` contra composición de vapor. Si no hay valor tabulado de `Z` en la base, el programa lo calcula resolviendo la cúbica Redlich-Kwong `Z^3 - Z^2 + (A-B-B^2)Z - AB = 0`.
- Si faltan Antoine, propiedades críticas, volumen líquido o parámetros binarios, el cálculo se bloquea con un mensaje amigable. El programa no inventa datos.

## Parámetros Wilson

Wilson puede usar dos formatos internos de parámetros binarios calculados desde datos VLE:

- `dimensionless_lambda`: `Λij` directo, positivo y adimensional.
- `energy_difference`: energía `λij−λii` en `J/mol` o `cal/mol`, con la cual el programa calcula `Λij(T)` usando los volúmenes líquidos y la temperatura absoluta interna en Kelvin.

En la interfaz principal, el usuario ingresa puntos VLE y el programa ajusta Wilson en memoria. Los parámetros directos `Λij` del problema 14.54 quedan como datos de referencia/compatibilidad, pero no reemplazan la necesidad de validar con datos proporcionados por el usuario cuando se haga una corrida formal.

## Parámetros Margules

Margules usa parámetros binarios adimensionales `A12` y `A21`. El motor los ajusta automáticamente desde puntos VLE binarios con `x`, `y`, `P` y `T`:

```text
gamma_i = y_i P / (x_i Psat_i)
```

El ajuste resuelve el SEL de Margules. Si los puntos fueron ingresados por el usuario, los parámetros calculados se usan solo en memoria y no se escriben en `binary_parameters`.

## Parámetros Van Laar

Van Laar también usa parámetros binarios adimensionales `A12` y `A21`. El motor los ajusta automáticamente desde los puntos VLE ingresados antes de cada cálculo binario.

El ajuste usa `gamma_i = y_i P / (x_i Psat_i)` y la forma inversa estándar con corchetes al cuadrado. Si los datos VLE faltan o producen `ln(gamma)` no válido, el cálculo se bloquea con mensaje amigable.

## Datos VLE para ajuste automático

En **Nuevo cálculo**, el usuario debe proporcionar puntos VLE para ajustar los modelos de actividad. Para sistemas binarios se ingresa:

- `T (°C)`.
- `P (kPa)`.
- `x1`, fracción líquida del primer componente.
- `y1`, fracción vapor del primer componente.
- Fuente o nota.

El programa calcula internamente `x2 = 1 - x1` y `y2 = 1 - y1`.

Para Wilson multicomponente, la tabla incluye una columna **Par**. Se debe ingresar al menos un punto VLE para cada par binario requerido; en cada fila, `x1` e `y1` pertenecen al primer componente escrito en esa columna.

La sección `vle_fit_data` de la base JSON puede contener ejemplos para algunos sistemas. Esos ejemplos no se aplican automáticamente: se cargan con el botón **Cargar ejemplo del sistema**.

El programa no obtiene parámetros desde la nada ni desde el resultado que está resolviendo. Primero lee datos VLE conocidos, calcula `Psat_i`, obtiene `gamma_i` y ajusta parámetros. Luego usa esos parámetros dentro del solver.

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

- Después de ejecutar un cálculo, la vista **Resultados** muestra automáticamente el diagrama asociado.
- En **Resultados** o **Diagrama**, use `Guardar PNG` o `Guardar PDF` para exportar el gráfico del último cálculo.
- En la vista **Resultados**, use `Guardar resultados TXT` para exportar el reporte numérico.

En todos los casos se abre una ventana de Windows para elegir carpeta y nombre de archivo. La aplicación no obliga al usuario a guardar en una carpeta fija.

## Pruebas en Windows

Para validar la BETA desde PowerShell:

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
