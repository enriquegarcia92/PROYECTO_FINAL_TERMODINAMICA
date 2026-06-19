from __future__ import annotations

import pytest

from vle_poc.domain import ActivityModel, CalculationRequest, CalculationType, VaporModel
from vle_poc.repository import DataRepository
from vle_poc.service import MockVLEService


@pytest.mark.parametrize("calculation_type", list(CalculationType))
def test_all_calculation_flows_return_uniform_result(calculation_type: CalculationType) -> None:
    repository = DataRepository()
    service = MockVLEService(repository)
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
    assert result.simulated
    assert sum(result.x) == pytest.approx(1.0)
    assert sum(result.y) == pytest.approx(1.0)
    assert result.comparison_value is not None


def test_multicomponent_result_has_three_rows() -> None:
    repository = DataRepository()
    service = MockVLEService(repository)
    system = repository.get("acetone_methanol_benzene")
    result = service.calculate(
        CalculationRequest(
            CalculationType.DEW_T,
            system.id,
            ActivityModel.MARGULES,
            VaporModel.GAMMA_PHI,
            101.325,
            (0.2, 0.3, 0.5),
        )
    )
    assert len(result.component_names) == 3
