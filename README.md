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
- Constructor dinámico de sistemas: el usuario elige sustancias desde el catálogo global y arma el sistema componente por componente.
- Plantillas demostrativas internas para validación rápida, sin duplicar propiedades puras.
- Selección de Wilson, Margules y Van Laar.
- Comparación visual con `phi = 1`.
- Diagramas Pxy/Txy generados automáticamente con cada cálculo y exportables a PNG/PDF mediante ventana “Guardar como”.
- Resultados exportables a TXT mediante ventana “Guardar como”.
- Validaciones reales de composiciones, presión, temperatura y disponibilidad de parámetros.
- CLI que consume el mismo contrato de dominio.
- Pruebas automatizadas y configuración PyInstaller para generar `.exe` en Windows.

## Regla de unidades de temperatura

El usuario ingresa temperaturas en grados Celsius (`°C`). Internamente, la aplicación convierte esas temperaturas a Kelvin (`K`) antes de enviarlas al servicio de cálculo, porque las fórmulas termodinámicas requieren temperatura absoluta. Los resultados y reportes pueden mostrar ambas unidades para trazabilidad.

## Construcción dinámica del sistema VLE

En la vista **Nuevo cálculo**, el sistema ya no se selecciona como una mezcla fija. Ahora se construye así:

1. Seleccione la primera sustancia desde el catálogo.
2. Use **Agregar componente** para incorporar la segunda sustancia.
3. Repita el proceso si necesita una mezcla de más componentes.
4. Complete la tabla de composición.
5. Ejecute el cálculo cuando el sistema tenga al menos 2 componentes válidos.

Reglas actuales:

- Mínimo para ejecutar VLE: 2 componentes.
- Máximo recomendado y programado para esta versión: 5 componentes.
- No se permiten sustancias repetidas.
- Wilson se permite de 2 a 5 componentes solo si existen datos VLE para ajustar todos los pares binarios requeridos.
- Margules y Van Laar se permiten únicamente para sistemas binarios con datos VLE suficientes para ajustar `A12/A21`.
- Los diagramas se generan automáticamente: Pxy/Txy para binarios y cortes composicionales equivalentes para 3 a 5 componentes cuando el modelo lo permite.
- Si faltan Antoine, propiedades críticas, volumen líquido o parámetros binarios, el cálculo se bloquea con un mensaje amigable. El programa no inventa datos.

## Parámetros Wilson

Wilson puede usar dos formatos internos de parámetros binarios calculados:

- `dimensionless_lambda`: `Λij` directo, positivo y adimensional.
- `energy_difference`: energía `λij−λii` en `J/mol` o `cal/mol`, con la cual el programa calcula `Λij(T)` usando los volúmenes líquidos y la temperatura absoluta interna en Kelvin.

En el flujo principal, el programa ajusta automáticamente las energías Wilson desde `vle_fit_data` antes de cada cálculo y las guarda con trazabilidad en `binary_parameters`. Si no hay datos VLE para un par, el cálculo se bloquea.

## Parámetros Margules

Margules usa parámetros binarios adimensionales `A12` y `A21`. El motor los ajusta automáticamente desde puntos VLE binarios con `x`, `y`, `P` y `T`:

```text
gamma_i = y_i P / (x_i Psat_i)
```

El ajuste resuelve el SEL de Margules y escribe los parámetros calculados en `binary_parameters` con fuente, residuales y número de puntos usados. `vle_fit_data` sigue siendo la fuente auditable.

## Parámetros Van Laar

Van Laar también usa parámetros binarios adimensionales `A12` y `A21`. El motor los ajusta automáticamente desde `vle_fit_data` antes de cada cálculo binario.

El ajuste usa `gamma_i = y_i P / (x_i Psat_i)` y la forma inversa estándar con corchetes al cuadrado. Si los datos VLE faltan o producen `ln(gamma)` no válido, el cálculo se bloquea con mensaje amigable.

## Datos VLE para ajuste automático

La sección `vle_fit_data` de la base JSON contiene los puntos usados para ajustar modelos de actividad. Cada punto define par binario, fuente, temperatura, presión, composición líquida `x` y composición vapor `y`.

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
