from __future__ import annotations

import pytest

from vle_poc.domain import ActivityModel, CalculationRequest, CalculationType, VaporModel
from vle_poc.properties import psat_kpa
from vle_poc.repository import DataRepository
from vle_poc.service import VLLE_1427_WARNING, ThermodynamicVLEService
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


def test_system_without_model_does_not_accept_margules() -> None:
    repository = DataRepository()
    service = ThermodynamicVLEService(repository)
    system = repository.get("benzene_n_hexane")
    with pytest.raises(InputValidationError, match="no está disponible"):
        service.calculate(
            CalculationRequest(
                CalculationType.DEW_T,
                system.id,
                ActivityModel.MARGULES,
                VaporModel.GAMMA_PHI,
                101.325,
                (0.5, 0.5),
            )
        )


def test_user_vle_data_unlocks_applicable_binary_model() -> None:
    repository = DataRepository()
    service = ThermodynamicVLEService(repository)
    system = repository.get("benzene_n_hexane")
    temperature_k = 350.0
    x = (0.45, 0.55)
    psat = tuple(psat_kpa(component, temperature_k) for component in system.components)
    pressure_kpa = sum(x_i * psat_i for x_i, psat_i in zip(x, psat))
    y = tuple(x_i * psat_i / pressure_kpa for x_i, psat_i in zip(x, psat))
    user_vle_fit_data = {
        "benzene|n_hexane": [
            {
                "source": "Usuario prueba Raoult",
                "temperature_k": temperature_k,
                "pressure_kpa": pressure_kpa,
                "x": list(x),
                "y": list(y),
            }
        ]
    }

    result = service.calculate(
        CalculationRequest(
            CalculationType.BUBL_P,
            system.id,
            ActivityModel.MARGULES,
            VaporModel.COMPARE,
            temperature_k,
            x,
            user_vle_fit_data=user_vle_fit_data,
        )
    )

    assert result.converged
    assert result.activity_model == "Margules"
    assert result.vle_fit_data_used[0]["source"] == "Usuario prueba Raoult"


def _ideal_pair_vle_data(repository: DataRepository, system_id: str, temperature_k: float) -> dict[str, list[dict[str, object]]]:
    system = repository.get(system_id)
    fit_data: dict[str, list[dict[str, object]]] = {}
    for index, first in enumerate(system.components):
        for second in system.components[index + 1 :]:
            x = (0.45, 0.55)
            psat = (psat_kpa(first, temperature_k), psat_kpa(second, temperature_k))
            pressure_kpa = sum(x_i * psat_i for x_i, psat_i in zip(x, psat))
            y = tuple(x_i * psat_i / pressure_kpa for x_i, psat_i in zip(x, psat))
            fit_data[f"{first.id}|{second.id}"] = [
                {
                    "source": "Usuario prueba Wilson multicomponente",
                    "temperature_k": temperature_k,
                    "pressure_kpa": pressure_kpa,
                    "x": list(x),
                    "y": list(y),
                }
            ]
    return fit_data


def test_problem_1427_blocks_without_wilson_vle_data() -> None:
    repository = DataRepository()
    service = ThermodynamicVLEService(repository)
    with pytest.raises(InputValidationError, match="Ingrese datos VLE"):
        service.calculate(
            CalculationRequest(
                CalculationType.BUBL_P,
                "water_n_pentane_n_heptane_1427",
                ActivityModel.WILSON,
                VaporModel.COMPARE,
                330.0,
                (0.45, 0.30, 0.25),
            )
        )


def test_problem_1427_runs_with_user_vle_data_and_warns() -> None:
    repository = DataRepository()
    service = ThermodynamicVLEService(repository)
    user_vle_fit_data = _ideal_pair_vle_data(repository, "water_n_pentane_n_heptane_1427", 330.0)
    result = service.calculate(
        CalculationRequest(
            CalculationType.BUBL_P,
            "water_n_pentane_n_heptane_1427",
            ActivityModel.WILSON,
            VaporModel.COMPARE,
            330.0,
            (0.45, 0.30, 0.25),
            user_vle_fit_data=user_vle_fit_data,
        )
    )

    assert result.converged
    assert result.activity_model == "Wilson"
    assert len(result.component_names) == 3
    assert VLLE_1427_WARNING in result.warnings
    assert len(result.vle_fit_data_used) == 3


def test_problem_1427_phase_curve_reuses_user_vle_fit_data() -> None:
    repository = DataRepository()
    service = ThermodynamicVLEService(repository)
    user_vle_fit_data = _ideal_pair_vle_data(repository, "water_n_pentane_n_heptane_1427", 330.0)
    result = service.calculate(
        CalculationRequest(
            CalculationType.BUBL_P,
            "water_n_pentane_n_heptane_1427",
            ActivityModel.WILSON,
            VaporModel.COMPARE,
            330.0,
            (0.45, 0.30, 0.25),
            user_vle_fit_data=user_vle_fit_data,
        )
    )

    data = service.phase_curve_for_result(result)

    assert data["is_cut"][0] == 1
    assert len(data["x"]) == 21


def test_acetone_methanol_water_wilson_runs_without_user_vle_data() -> None:
    repository = DataRepository()
    service = ThermodynamicVLEService(repository)
    cases = (
        (CalculationType.BUBL_P, 338.15, (0.3, 0.4, 0.3)),
        (CalculationType.DEW_P, 338.15, (0.3, 0.4, 0.3)),
        (CalculationType.BUBL_T, 101.33, (0.3, 0.4, 0.3)),
    )
    for calculation_type, fixed_value, composition in cases:
        result = service.calculate(
            CalculationRequest(
                calculation_type,
                "acetone_methanol_water_1220_1222",
                ActivityModel.WILSON,
                VaporModel.COMPARE,
                fixed_value,
                composition,
            )
        )
        assert result.converged
        assert result.activity_model == "Wilson"
        assert result.component_names == ("Acetona", "Metanol", "Agua")
        assert result.vle_fit_data_used == ()
        assert sum(result.x) == pytest.approx(1.0)
        assert sum(result.y) == pytest.approx(1.0)
        assert VLLE_1427_WARNING not in result.warnings


def test_acetone_methanol_water_phase_curve_is_ternary_cut() -> None:
    repository = DataRepository()
    service = ThermodynamicVLEService(repository)
    result = service.calculate(
        CalculationRequest(
            CalculationType.BUBL_P,
            "acetone_methanol_water_1220_1222",
            ActivityModel.WILSON,
            VaporModel.COMPARE,
            338.15,
            (0.3, 0.4, 0.3),
        )
    )

    data = service.phase_curve_for_result(result)

    assert data["is_cut"][0] == 1
    assert len(data["x"]) == 21


def test_vle_fit_system_runs_margules_and_van_laar() -> None:
    repository = DataRepository()
    service = ThermodynamicVLEService(repository)
    for model in (ActivityModel.MARGULES, ActivityModel.VAN_LAAR):
        result = service.calculate(
            CalculationRequest(
                CalculationType.BUBL_T,
                "cyclohexane_n_heptane",
                model,
                VaporModel.COMPARE,
                101.325,
                (0.5, 0.5),
            )
        )
        assert result.converged


def test_phase_curve_for_result_generates_pxy_for_temperature_fixed_calculation() -> None:
    repository = DataRepository()
    service = ThermodynamicVLEService(repository)
    result = service.calculate(
        CalculationRequest(
            CalculationType.BUBL_P,
            "cyclohexane_n_heptane",
            ActivityModel.WILSON,
            VaporModel.COMPARE,
            350.0,
            (0.45, 0.55),
        )
    )

    data = service.phase_curve_for_result(result)

    assert data["diagram_type"][0] == "Pxy"
    assert len(data["x"]) == 21
    assert len(data["y"]) == 21
    assert data["point_x"][0] == pytest.approx(result.x[0])
    assert data["point_y"][0] == pytest.approx(result.y[0])


def test_phase_curve_for_result_generates_txy_for_pressure_fixed_calculation() -> None:
    repository = DataRepository()
    service = ThermodynamicVLEService(repository)
    result = service.calculate(
        CalculationRequest(
            CalculationType.BUBL_T,
            "cyclohexane_n_heptane",
            ActivityModel.WILSON,
            VaporModel.COMPARE,
            101.325,
            (0.45, 0.55),
        )
    )

    data = service.phase_curve_for_result(result)

    assert data["diagram_type"][0] == "Txy"
    assert data["point_value"][0] == pytest.approx(result.temperature_k)
