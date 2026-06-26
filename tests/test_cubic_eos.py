from __future__ import annotations

import math

from vle_poc.cubic_eos import bubble_pressure_phi_phi, fugacity_coefficients, pure_parameters
from vle_poc.domain import ActivityModel
from vle_poc.repository import DataRepository


def test_srk_pure_parameters_match_expected_order_of_magnitude() -> None:
    repository = DataRepository()
    system = repository.get("methane_n_butane_1402")

    methane = pure_parameters(system.components[0], 310.93, ActivityModel.SOAVE_REDLICH_KWONG)
    n_butane = pure_parameters(system.components[1], 310.93, ActivityModel.SOAVE_REDLICH_KWONG)

    assert math.isclose(methane.b * 1_000_000, 29.85, rel_tol=0.02)
    assert math.isclose(n_butane.b * 1_000_000, 80.67, rel_tol=0.02)
    assert methane.a > 0
    assert n_butane.a > methane.a


def test_redlich_kwong_nitrogen_methane_fugacity_is_positive() -> None:
    system = DataRepository().get("nitrogen_methane_1401")

    state = fugacity_coefficients(
        system,
        200.0,
        3000.0,
        (0.40, 0.60),
        ActivityModel.REDLICH_KWONG,
        phase="vapor",
    )

    assert state.z > 0
    assert len(state.phi) == 2
    assert all(math.isfinite(value) and value > 0 for value in state.phi)


def test_srk_methane_n_butane_bubble_pressure_converges() -> None:
    system = DataRepository().get("methane_n_butane_1402")

    result = bubble_pressure_phi_phi(
        system,
        310.93,
        (0.10, 0.90),
        ActivityModel.SOAVE_REDLICH_KWONG,
    )

    assert result.pressure_kpa > 0
    assert abs(sum(result.y) - 1.0) < 1e-6
    assert all(value > 0 for value in result.phi_liquid)
    assert all(value > 0 for value in result.phi_vapor)
    assert result.residual < 1e-4
