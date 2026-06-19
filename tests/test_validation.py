from __future__ import annotations

import pytest

from vle_poc.domain import ActivityModel, CalculationRequest, CalculationType, VaporModel
from vle_poc.repository import DataRepository
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
