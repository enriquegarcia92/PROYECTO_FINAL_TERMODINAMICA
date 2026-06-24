from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from vle_poc.activity import activity_coefficients
from vle_poc.domain import ActivityModel, CalculationRequest, CalculationType, VaporModel
from vle_poc.properties import psat_kpa
from vle_poc.repository import DataRepository
from vle_poc.service import ThermodynamicVLEService
from vle_poc.validation import InputValidationError
from vle_poc.van_laar_fit import fit_van_laar_binary_from_vle


def _source_with_van_laar(a12: float = 0.70, a21: float = 1.10) -> dict:
    source = json.loads(Path("datos/base_datos_VLE.json").read_text(encoding="utf-8"))
    source["binary_parameters"]["Van Laar"]["cyclohexane|n_heptane"] = {
        "source": "Prueba controlada Van Laar",
        "type": "dimensionless_a",
        "value": a12,
    }
    source["binary_parameters"]["Van Laar"]["n_heptane|cyclohexane"] = {
        "source": "Prueba controlada Van Laar",
        "type": "dimensionless_a",
        "value": a21,
    }
    return source


def _repository_from_source(tmp_path: Path, source: dict) -> DataRepository:
    db_path = tmp_path / "db.json"
    db_path.write_text(json.dumps(source), encoding="utf-8")
    return DataRepository(db_path)


def test_van_laar_gamma_uses_direct_model_formula(tmp_path: Path) -> None:
    repository = _repository_from_source(tmp_path, _source_with_van_laar(0.70, 1.10))
    system = repository.get("cyclohexane_n_heptane")
    x = np.array([0.40, 0.60])

    gamma = activity_coefficients(ActivityModel.VAN_LAAR, system, 360.0, x)

    denominator = 0.70 * x[0] + 1.10 * x[1]
    ln_gamma_1 = 0.70 * ((1.10 * x[1]) / denominator) ** 2
    ln_gamma_2 = 1.10 * ((0.70 * x[0]) / denominator) ** 2
    assert gamma == pytest.approx(np.exp([ln_gamma_1, ln_gamma_2]))


def test_van_laar_fit_recovers_a12_a21_from_synthetic_vle_point(tmp_path: Path) -> None:
    a12 = 0.70
    a21 = 1.10
    repository = _repository_from_source(tmp_path, _source_with_van_laar(a12, a21))
    system = repository.get("cyclohexane_n_heptane")
    temperature_k = 360.0
    x = np.array([0.40, 0.60])
    gamma = activity_coefficients(ActivityModel.VAN_LAAR, system, temperature_k, x)
    psat = np.array([psat_kpa(component, temperature_k) for component in system.components])
    pressure_kpa = float(np.dot(x, gamma * psat))
    y = tuple((x * gamma * psat / pressure_kpa).tolist())

    result = fit_van_laar_binary_from_vle(
        system,
        temperature_k=temperature_k,
        pressure_kpa=pressure_kpa,
        x=tuple(x.tolist()),
        y=y,
    )

    assert result.a12 == pytest.approx(a12)
    assert result.a21 == pytest.approx(a21)
    assert result.gamma == pytest.approx(tuple(gamma.tolist()))
    assert result.residuals["ln_gamma_1"] <= 1e-12
    assert result.residuals["ln_gamma_2"] <= 1e-12


def test_van_laar_fit_rejects_non_binary_system() -> None:
    system = DataRepository().get("acetone_methanol_benzene")

    with pytest.raises(InputValidationError, match="sistemas binarios"):
        fit_van_laar_binary_from_vle(system, 330.0, 101.325, (0.5, 0.5), (0.5, 0.5))


def test_van_laar_fit_rejects_invalid_compositions() -> None:
    system = DataRepository().get("cyclohexane_n_heptane")

    with pytest.raises(InputValidationError, match="sumar 1"):
        fit_van_laar_binary_from_vle(system, 360.0, 101.325, (0.4, 0.4), (0.5, 0.5))
    with pytest.raises(InputValidationError, match="x_i > 0"):
        fit_van_laar_binary_from_vle(system, 360.0, 101.325, (0.0, 1.0), (0.5, 0.5))
    with pytest.raises(InputValidationError, match="y_i > 0"):
        fit_van_laar_binary_from_vle(system, 360.0, 101.325, (0.5, 0.5), (0.0, 1.0))


def test_van_laar_fit_rejects_negative_pressure_and_antoine_range() -> None:
    system = DataRepository().get("cyclohexane_n_heptane")

    with pytest.raises(InputValidationError, match="presión VLE"):
        fit_van_laar_binary_from_vle(system, 360.0, -1.0, (0.5, 0.5), (0.5, 0.5))
    with pytest.raises(InputValidationError, match="rango Antoine"):
        fit_van_laar_binary_from_vle(system, 100.0, 101.325, (0.5, 0.5), (0.5, 0.5))


def test_van_laar_fit_rejects_non_positive_ln_gamma() -> None:
    system = DataRepository().get("cyclohexane_n_heptane")
    temperature_k = 360.0
    psat = np.array([psat_kpa(component, temperature_k) for component in system.components])
    x = np.array([0.5, 0.5])
    pressure_kpa = float(np.dot(x, psat))
    y = tuple((x * psat / pressure_kpa).tolist())

    with pytest.raises(InputValidationError, match="ln\\(gamma1\\) y ln\\(gamma2\\) positivos"):
        fit_van_laar_binary_from_vle(
            system,
            temperature_k=temperature_k,
            pressure_kpa=pressure_kpa,
            x=tuple(x.tolist()),
            y=y,
        )


def test_van_laar_without_vle_fit_data_stays_blocked() -> None:
    service = ThermodynamicVLEService(DataRepository())
    request = CalculationRequest(
        CalculationType.BUBL_T,
        "ethanol_toluene",
        ActivityModel.VAN_LAAR,
        VaporModel.GAMMA_PHI,
        101.325,
        (0.5, 0.5),
    )

    with pytest.raises(InputValidationError, match="Faltan datos VLE"):
        service.calculate(request)


@pytest.mark.parametrize("calculation_type", list(CalculationType))
def test_van_laar_documented_parameters_run_all_solvers(tmp_path: Path, calculation_type: CalculationType) -> None:
    repository = _repository_from_source(tmp_path, _source_with_van_laar())
    service = ThermodynamicVLEService(repository)
    fixed = 360.0 if calculation_type.fixed_variable == "temperatura" else 101.325

    result = service.calculate(
        CalculationRequest(
            calculation_type,
            "cyclohexane_n_heptane",
            ActivityModel.VAN_LAAR,
            VaporModel.COMPARE,
            fixed,
            (0.45, 0.55),
        )
    )

    assert result.converged
    assert result.activity_model == "Van Laar"
    assert sum(result.x) == pytest.approx(1.0)
    assert sum(result.y) == pytest.approx(1.0)
