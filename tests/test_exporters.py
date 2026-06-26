from __future__ import annotations

from vle_poc.domain import ActivityModel, CalculationRequest, CalculationType, VaporModel
from vle_poc.exporters import format_result_txt
from vle_poc.repository import DataRepository
from vle_poc.properties import psat_kpa
from vle_poc.service import SIMULATION_WARNING, VLLE_1427_WARNING, ThermodynamicVLEService


def test_result_txt_contains_required_sections() -> None:
    repository = DataRepository()
    service = ThermodynamicVLEService(repository)
    system = repository.all_systems()[0]
    result = service.calculate(
        CalculationRequest(
            CalculationType.BUBL_P,
            system.id,
            ActivityModel.WILSON,
            VaporModel.COMPARE,
            350.0,
            (0.45, 0.55),
        )
    )

    text = format_result_txt(result)

    assert "VLE Gamma-Phi - Reporte de resultados" in text
    assert SIMULATION_WARNING in text
    assert "Tipo de calculo: BUBL P" in text
    assert f"Sistema: {system.name}" in text
    assert "Modelo de actividad: Wilson" in text
    assert "Modelo de vapor: Comparar con phi = 1" in text
    assert "Temperatura:" in text
    assert "350.000000 K" in text
    assert "76.850000 °C" in text
    assert "Presion:" in text
    assert "Tabla por componente" in text
    assert "gamma" in text
    assert "phi_sat" in text
    assert "Poynting" in text
    assert "Residuales finales" in text
    assert "Comparacion gamma-phi vs phi = 1" in text
    assert "Presiones de saturacion" in text
    assert "Valores K" in text
    assert "Fuentes de datos" in text
    assert "motor termodinamico" in text


def test_problem_1427_warning_is_exported_to_txt() -> None:
    repository = DataRepository()
    service = ThermodynamicVLEService(repository)
    system = repository.get("water_n_pentane_n_heptane_1427")
    temperature_k = 330.0
    fit_data: dict[str, list[dict[str, object]]] = {}
    for index, first in enumerate(system.components):
        for second in system.components[index + 1 :]:
            x = (0.45, 0.55)
            psat = (psat_kpa(first, temperature_k), psat_kpa(second, temperature_k))
            pressure_kpa = sum(x_i * psat_i for x_i, psat_i in zip(x, psat))
            y = tuple(x_i * psat_i / pressure_kpa for x_i, psat_i in zip(x, psat))
            fit_data[f"{first.id}|{second.id}"] = [
                {
                    "source": "Usuario prueba TXT",
                    "temperature_k": temperature_k,
                    "pressure_kpa": pressure_kpa,
                    "x": list(x),
                    "y": list(y),
                }
            ]
    result = service.calculate(
        CalculationRequest(
            CalculationType.BUBL_P,
            system.id,
            ActivityModel.WILSON,
            VaporModel.COMPARE,
            temperature_k,
            (0.45, 0.30, 0.25),
            user_vle_fit_data=fit_data,
        )
    )

    text = format_result_txt(result)

    assert VLLE_1427_WARNING in text
    assert "water|n_pentane" in text
