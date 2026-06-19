"""Menú de consola mínimo que consume el mismo contrato que la GUI."""

from vle_poc.domain import ActivityModel, CalculationRequest, CalculationType, VaporModel
from vle_poc.repository import DataRepository
from vle_poc.service import MockVLEService, SIMULATION_WARNING
from vle_poc.validation import InputValidationError


def choose(title: str, options: list[tuple[str, object]]) -> object:
    print(f"\n{title}")
    for index, (label, _) in enumerate(options, 1):
        print(f"  {index}. {label}")
    selected = int(input("Seleccione una opción: ")) - 1
    if selected < 0 or selected >= len(options):
        raise InputValidationError("Opción fuera de rango.")
    return options[selected][1]


def main() -> int:
    repository = DataRepository()
    service = MockVLEService(repository)
    print("VLE Gamma-Phi · CLI POC")
    print(SIMULATION_WARNING)
    try:
        calculation = choose("Tipo de cálculo", [(item.value, item) for item in CalculationType])
        system = choose("Sistema", [(item.name, item) for item in repository.all_systems()])
        activity = choose("Modelo de actividad", [(item.value, item) for item in ActivityModel])
        vapor = choose("Modelo de vapor", [(item.value, item) for item in VaporModel])
        variable = calculation.fixed_variable
        unit = "K" if variable == "temperatura" else "kPa"
        fixed_value = float(input(f"Ingrese {variable} ({unit}): "))
        raw = input(f"Ingrese {len(system.components)} fracciones molares separadas por coma: ")
        composition = tuple(float(value.strip()) for value in raw.split(","))
        result = service.calculate(
            CalculationRequest(calculation, system.id, activity, vapor, fixed_value, composition)
        )
    except (ValueError, InputValidationError) as exc:
        print(f"Error: {exc}")
        return 1
    print(f"\nEstado: {'convergió' if result.converged else 'no convergió'}")
    print(f"T = {result.temperature_k:.3f} K | P = {result.pressure_kpa:.3f} kPa")
    for name, x_value, y_value in zip(result.component_names, result.x, result.y):
        print(f"  {name}: x={x_value:.6f}, y={y_value:.6f}")
    print(SIMULATION_WARNING)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
