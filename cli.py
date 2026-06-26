"""Menú de consola mínimo para sistemas VLE documentados."""

from vle_poc.domain import ActivityModel, CalculationRequest, CalculationType, VaporModel
from vle_poc.repository import DataRepository
from vle_poc.service import SIMULATION_WARNING, VLLE_1427_SYSTEM_ID, VLLE_1427_WARNING, ThermodynamicVLEService
from vle_poc.units import celsius_to_kelvin, kelvin_to_celsius
from vle_poc.validation import InputValidationError


EOS_MODELS = {ActivityModel.REDLICH_KWONG, ActivityModel.SOAVE_REDLICH_KWONG}
EOS_MODEL_NAMES = {model.value for model in EOS_MODELS}


def choose(title: str, options: list[tuple[str, object]]) -> object:
    print(f"\n{title}")
    for index, (label, _) in enumerate(options, 1):
        print(f"  {index}. {label}")
    selected = int(input("Seleccione una opción: ")) - 1
    if selected < 0 or selected >= len(options):
        raise InputValidationError("Opción fuera de rango.")
    return options[selected][1]


def read_vle_fit_data(system) -> dict[str, list[dict[str, object]]]:
    fit_data: dict[str, list[dict[str, object]]] = {}
    components = system.components
    for pair_index, first in enumerate(components):
        for second in components[pair_index + 1 :]:
            pair_key = f"{first.id}|{second.id}"
            print(f"\nDatos VLE para {first.name} / {second.name}")
            print("Ingrese x1 e y1 para el primer componente del par. x2 e y2 se calculan como 1-x1 y 1-y1.")
            count = int(input("Cantidad de puntos VLE a ingresar para este par: "))
            if count <= 0:
                raise InputValidationError(f"Debe ingresar al menos un punto VLE para {pair_key}.")
            points: list[dict[str, object]] = []
            for index in range(count):
                print(f"\nPunto VLE {index + 1} de {pair_key}")
                temperature_c = float(input("  Temperatura (°C): "))
                pressure_kpa = float(input("  Presión (kPa): "))
                x1 = float(input(f"  x1 ({first.name}): "))
                y1 = float(input(f"  y1 ({first.name}): "))
                if pressure_kpa <= 0:
                    raise InputValidationError("La presión VLE debe ser positiva.")
                if not (0.0 < x1 < 1.0) or not (0.0 < y1 < 1.0):
                    raise InputValidationError("x1 e y1 deben estar entre 0 y 1, sin extremos.")
                points.append(
                    {
                        "source": "Usuario CLI",
                        "temperature_c": temperature_c,
                        "pressure_kpa": pressure_kpa,
                        "x": [x1, 1.0 - x1],
                        "y": [y1, 1.0 - y1],
                    }
                )
            fit_data[pair_key] = points
    return fit_data


def has_required_parameters(system, model: ActivityModel) -> bool:
    if model in EOS_MODELS:
        return True
    parameters = system.binary_parameters.get(model.value, {})
    pairs = parameters.get("pairs", {}) if isinstance(parameters, dict) else {}
    if not isinstance(pairs, dict):
        return False
    component_ids = tuple(component.id for component in system.components)
    if model in {ActivityModel.MARGULES, ActivityModel.VAN_LAAR} and len(component_ids) != 2:
        return False
    return all(
        f"{first}|{second}" in pairs
        for first in component_ids
        for second in component_ids
        if first != second
    )


def main() -> int:
    repository = DataRepository()
    service = ThermodynamicVLEService(repository)
    print("VLE Gamma-Phi · CLI termodinámica")
    print(SIMULATION_WARNING)
    try:
        calculation = choose("Tipo de cálculo", [(item.value, item) for item in CalculationType])
        system = choose("Sistema documentado", [(item.name, item) for item in repository.all_systems()])
        if system.id == VLLE_1427_SYSTEM_ID:
            print(f"\nAdvertencia 14.27: {VLLE_1427_WARNING}")
        if any(model in EOS_MODEL_NAMES for model in system.available_models):
            print(
                "\nModo EOS cúbica phi-phi: este sistema no usa Wilson/Margules/Van Laar "
                "ni requiere datos VLE de ajuste."
            )
            available_models = [ActivityModel(model) for model in system.available_models]
        elif len(system.components) == 2:
            available_models = [ActivityModel.WILSON, ActivityModel.MARGULES, ActivityModel.VAN_LAAR]
        else:
            available_models = [ActivityModel.WILSON]
        activity = choose(
            "Modelo de actividad",
            [(model.value, model) for model in available_models],
        )
        vapor = choose("Modelo de vapor", [(item.value, item) for item in VaporModel])
        user_vle_fit_data = {}
        if has_required_parameters(system, activity):
            print("\nEste sistema ya tiene parámetros documentados para el modelo seleccionado.")
        else:
            user_vle_fit_data = read_vle_fit_data(system)
        variable = calculation.fixed_variable
        unit = "°C" if variable == "temperatura" else "kPa"
        fixed_value = float(input(f"Ingrese {variable} ({unit}): "))
        if variable == "temperatura":
            fixed_value = celsius_to_kelvin(fixed_value)
        raw = input(f"Ingrese {len(system.components)} fracciones molares separadas por coma: ")
        composition = tuple(float(value.strip()) for value in raw.split(","))
        result = service.calculate(
            CalculationRequest(
                calculation,
                system.id,
                activity,
                vapor,
                fixed_value,
                composition,
                user_vle_fit_data=user_vle_fit_data,
            )
        )
    except (ValueError, InputValidationError) as exc:
        print(f"Error: {exc}")
        return 1
    print(f"\nEstado: {'convergió' if result.converged else 'no convergió'}")
    print(
        f"T = {result.temperature_k:.3f} K ({kelvin_to_celsius(result.temperature_k):.3f} °C) "
        f"| P = {result.pressure_kpa:.3f} kPa"
    )
    for name, x_value, y_value in zip(result.component_names, result.x, result.y):
        print(f"  {name}: x={x_value:.6f}, y={y_value:.6f}")
    print(SIMULATION_WARNING)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
