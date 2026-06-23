from __future__ import annotations

import pytest

from vle_poc.domain import ActivityModel, CalculationRequest, CalculationType, VaporModel
from vle_poc.repository import DataRepository
from vle_poc.units import celsius_to_kelvin
from vle_poc.validation import InputValidationError, validate_composition, validate_request


def test_valid_composition_is_normalized() -> None:
    assert validate_composition((0.4, 0.6), 2) == pytest.approx((0.4, 0.6))


@pytest.mark.parametrize(
    "composition",
    [(-0.1, 1.1), (0.2, 0.2), (0.0, 0.0), (float("nan"), 1.0)],
)
def test_invalid_compositions_are_rejected(composition: tuple[float, ...]) -> None:
    with pytest.raises(InputValidationError):
        validate_composition(composition, 2)


def test_negative_fixed_variable_is_rejected() -> None:
    repository = DataRepository()
    system = repository.all_systems()[0]
    request = CalculationRequest(
        CalculationType.BUBL_P,
        system.id,
        ActivityModel.WILSON,
        VaporModel.GAMMA_PHI,
        -10.0,
        (0.5, 0.5),
    )
    with pytest.raises(InputValidationError):
        validate_request(request, system)


def test_celsius_temperature_converted_to_kelvin_is_validated() -> None:
    repository = DataRepository()
    system = repository.all_systems()[0]
    request = CalculationRequest(
        CalculationType.BUBL_P,
        system.id,
        ActivityModel.WILSON,
        VaporModel.GAMMA_PHI,
        celsius_to_kelvin(76.85),
        (0.5, 0.5),
    )
    validated = validate_request(request, system)
    assert validated.fixed_value == pytest.approx(350.0)


@pytest.mark.parametrize("temperature_c", [-100.0, 530.0])
def test_celsius_temperature_outside_poc_range_is_rejected_with_celsius_message(
    temperature_c: float,
) -> None:
    repository = DataRepository()
    system = repository.all_systems()[0]
    request = CalculationRequest(
        CalculationType.BUBL_P,
        system.id,
        ActivityModel.WILSON,
        VaporModel.GAMMA_PHI,
        celsius_to_kelvin(temperature_c),
        (0.5, 0.5),
    )
    with pytest.raises(InputValidationError, match="°C"):
        validate_request(request, system)
