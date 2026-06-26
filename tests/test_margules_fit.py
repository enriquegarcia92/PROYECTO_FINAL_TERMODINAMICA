from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from vle_poc.activity import activity_coefficients
from vle_poc.domain import ActivityModel, CalculationRequest, CalculationType, VaporModel
from vle_poc.margules_fit import fit_margules_binary_from_vle
from vle_poc.properties import psat_kpa
from vle_poc.repository import DataRepository
from vle_poc.service import ThermodynamicVLEService
from vle_poc.validation import InputValidationError


def _source_with_margules(a12: float = 0.35, a21: float = 0.80) -> dict:
    source = json.loads(Path("datos/base_datos_VLE.json").read_text(encoding="utf-8"))
    source["binary_parameters"]["Margules"]["cyclohexane|n_heptane"] = {
        "source": "Prueba controlada Margules",
        "type": "dimensionless_a",
        "value": a12,
    }
    source["binary_parameters"]["Margules"]["n_heptane|cyclohexane"] = {
        "source": "Prueba controlada Margules",
        "type": "dimensionless_a",
        "value": a21,
    }
    return source


def _repository_from_source(tmp_path: Path, source: dict) -> DataRepository:
    db_path = tmp_path / "db.json"
    db_path.write_text(json.dumps(source), encoding="utf-8")
    return DataRepository(db_path)


def test_margules_gamma_uses_sel_formula_from_image(tmp_path: Path) -> None:
    repository = _repository_from_source(tmp_path, _source_with_margules(0.35, 0.80))
    system = repository.get("cyclohexane_n_heptane")
    x = np.array([0.40, 0.60])

    gamma = activity_coefficients(ActivityModel.MARGULES, system, 360.0, x)

    ln_gamma_1 = x[1] ** 2 * (0.35 + 2.0 * (0.80 - 0.35) * x[1])
    ln_gamma_2 = x[0] ** 2 * (0.80 + 2.0 * (0.35 - 0.80) * x[0])
    assert gamma == pytest.approx(np.exp([ln_gamma_1, ln_gamma_2]))


def test_margules_fit_recovers_a12_a21_from_synthetic_vle_point(tmp_path: Path) -> None:
    a12 = 0.35
    a21 = 0.80
    repository = _repository_from_source(tmp_path, _source_with_margules(a12, a21))
    system = repository.get("cyclohexane_n_heptane")
    temperature_k = 360.0
    x = np.array([0.40, 0.60])
    gamma = activity_coefficients(ActivityModel.MARGULES, system, temperature_k, x)
    psat = np.array([psat_kpa(component, temperature_k) for component in system.components])
    pressure_kpa = float(np.dot(x, gamma * psat))
    y = tuple((x * gamma * psat / pressure_kpa).tolist())

    result = fit_margules_binary_from_vle(
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


def test_margules_fit_rejects_non_binary_system() -> None:
    system = DataRepository().build_system(("acetone", "methanol", "benzene"))

    with pytest.raises(InputValidationError, match="sistemas binarios"):
        fit_margules_binary_from_vle(system, 330.0, 101.325, (0.5, 0.5), (0.5, 0.5))


def test_margules_fit_rejects_invalid_compositions() -> None:
    system = DataRepository().get("cyclohexane_n_heptane")

    with pytest.raises(InputValidationError, match="sumar 1"):
        fit_margules_binary_from_vle(system, 360.0, 101.325, (0.4, 0.4), (0.5, 0.5))
    with pytest.raises(InputValidationError, match="x_i > 0"):
        fit_margules_binary_from_vle(system, 360.0, 101.325, (0.0, 1.0), (0.5, 0.5))
    with pytest.raises(InputValidationError, match="y_i > 0"):
        fit_margules_binary_from_vle(system, 360.0, 101.325, (0.5, 0.5), (0.0, 1.0))


def test_margules_fit_rejects_negative_pressure_and_antoine_range() -> None:
    system = DataRepository().get("cyclohexane_n_heptane")

    with pytest.raises(InputValidationError, match="presión VLE"):
        fit_margules_binary_from_vle(system, 360.0, -1.0, (0.5, 0.5), (0.5, 0.5))
    with pytest.raises(InputValidationError, match="rango Antoine"):
        fit_margules_binary_from_vle(system, 100.0, 101.325, (0.5, 0.5), (0.5, 0.5))


def test_margules_without_vle_fit_data_stays_blocked() -> None:
    service = ThermodynamicVLEService(DataRepository())
    request = CalculationRequest(
        CalculationType.BUBL_T,
        "benzene_n_hexane",
        ActivityModel.MARGULES,
        VaporModel.GAMMA_PHI,
        101.325,
        (0.5, 0.5),
    )

    with pytest.raises(InputValidationError, match="no está disponible"):
        service.calculate(request)


@pytest.mark.parametrize("calculation_type", list(CalculationType))
def test_margules_documented_parameters_run_all_solvers(tmp_path: Path, calculation_type: CalculationType) -> None:
    repository = _repository_from_source(tmp_path, _source_with_margules())
    service = ThermodynamicVLEService(repository)
    fixed = 360.0 if calculation_type.fixed_variable == "temperatura" else 101.325

    result = service.calculate(
        CalculationRequest(
            calculation_type,
            "cyclohexane_n_heptane",
            ActivityModel.MARGULES,
            VaporModel.COMPARE,
            fixed,
            (0.45, 0.55),
        )
    )

    assert result.converged
    assert result.activity_model == "Margules"
    assert sum(result.x) == pytest.approx(1.0)
    assert sum(result.y) == pytest.approx(1.0)
