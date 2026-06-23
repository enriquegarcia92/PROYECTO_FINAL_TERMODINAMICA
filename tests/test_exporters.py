from __future__ import annotations

from vle_poc.domain import ActivityModel, CalculationRequest, CalculationType, VaporModel
from vle_poc.exporters import format_result_txt
from vle_poc.repository import DataRepository
from vle_poc.service import MockVLEService, SIMULATION_WARNING


def test_result_txt_contains_required_sections() -> None:
    repository = DataRepository()
    service = MockVLEService(repository)
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
    assert "Presion:" in text
    assert "Tabla por componente" in text
    assert "gamma" in text
    assert "phi_sat" in text
    assert "Poynting" in text
    assert "Residuales finales" in text
    assert "Comparacion gamma-phi vs phi = 1" in text
    assert "No contiene calculos termodinamicos reales" in text
