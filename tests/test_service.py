from __future__ import annotations

import pytest

from vle_poc.domain import ActivityModel, CalculationRequest, CalculationType, VaporModel
from vle_poc.repository import DataRepository
from vle_poc.service import ThermodynamicVLEService
from vle_poc.validation import InputValidationError


@pytest.mark.parametrize("calculation_type", list(CalculationType))
def test_all_calculation_flows_return_uniform_result(calculation_type: CalculationType) -> None:
    repository = DataRepository()
    service = ThermodynamicVLEService(repository)
    system = repository.all_systems()[0]
    fixed = 350.0 if calculation_type.fixed_variable == "temperatura" else 101.325
    result = service.calculate(
        CalculationRequest(
            calculation_type,
            system.id,
            ActivityModel.WILSON,
            VaporModel.COMPARE,
            fixed,
            (0.45, 0.55),
        )
    )
    result.assert_shape()
    assert result.converged
    assert not result.simulated
    assert sum(result.x) == pytest.approx(1.0)
    assert sum(result.y) == pytest.approx(1.0)
    assert result.comparison_value is not None


def test_multicomponent_result_has_three_rows() -> None:
    repository = DataRepository()
    service = ThermodynamicVLEService(repository)
    system = repository.get("acetone_methanol_benzene")
    with pytest.raises(InputValidationError, match="Faltan parámetros Margules"):
        service.calculate(
            CalculationRequest(
                CalculationType.DEW_T,
                system.id,
                ActivityModel.MARGULES,
                VaporModel.GAMMA_PHI,
                101.325,
                (0.2, 0.3, 0.5),
            )
        )


def test_dynamic_components_reproduce_template_bubl_t() -> None:
    repository = DataRepository()
    service = ThermodynamicVLEService(repository)
    template_result = service.calculate(
        CalculationRequest(
            CalculationType.BUBL_T,
            "cyclohexane_n_heptane",
            ActivityModel.WILSON,
            VaporModel.GAMMA_PHI,
            101.325,
            (0.5, 0.5),
        )
    )
    dynamic_result = service.calculate(
        CalculationRequest(
            CalculationType.BUBL_T,
            "dynamic",
            ActivityModel.WILSON,
            VaporModel.GAMMA_PHI,
            101.325,
            (0.5, 0.5),
            component_ids=("cyclohexane", "n_heptane"),
        )
    )
    assert dynamic_result.temperature_k == pytest.approx(template_result.temperature_k)
    assert dynamic_result.y == pytest.approx(template_result.y)
