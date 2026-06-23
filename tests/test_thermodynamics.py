from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from vle_poc.activity import activity_coefficients
from vle_poc.domain import ActivityModel, CalculationRequest, CalculationType, VaporModel
from vle_poc.fugacity import b0_pitzer, b1_pitzer, phi_mixture, second_virial_matrix
from vle_poc.properties import psat_kpa
from vle_poc.repository import DataRepository
from vle_poc.service import ThermodynamicVLEService
from vle_poc.validation import InputValidationError


def test_antoine_reproduces_normal_boiling_pressures() -> None:
    repo = DataRepository()
    system = repo.get("cyclohexane_n_heptane")
    cyclohexane, n_heptane = system.components

    assert psat_kpa(cyclohexane, 80.7 + 273.15) == pytest.approx(101.325, rel=5e-3)
    assert psat_kpa(n_heptane, 98.4 + 273.15) == pytest.approx(101.325, rel=5e-3)


def test_antoine_rejects_temperature_outside_range() -> None:
    component = DataRepository().get("cyclohexane_n_heptane").components[0]
    with pytest.raises(InputValidationError, match="rango Antoine"):
        psat_kpa(component, 0.0 + 273.15)


def test_wilson_gamma_for_cyclohexane_heptane_is_finite() -> None:
    repo = DataRepository()
    system = repo.get("cyclohexane_n_heptane")
    gamma = activity_coefficients(ActivityModel.WILSON, system, 360.0, np.array([0.5, 0.5]))
    assert gamma.shape == (2,)
    assert np.all(gamma > 0)
    assert gamma[0] == pytest.approx(1.012276, rel=1e-5)


def test_van_laar_without_parameters_is_blocked() -> None:
    repo = DataRepository()
    service = ThermodynamicVLEService(repo)
    request = CalculationRequest(
        CalculationType.BUBL_T,
        "cyclohexane_n_heptane",
        ActivityModel.VAN_LAAR,
        VaporModel.GAMMA_PHI,
        101.325,
        (0.5, 0.5),
    )
    with pytest.raises(InputValidationError, match="Faltan parámetros Van Laar"):
        service.calculate(request)


def test_pitzer_low_pressure_phi_tends_to_one() -> None:
    system = DataRepository().get("cyclohexane_n_heptane")
    y = np.array([0.5, 0.5])
    bij = second_virial_matrix(system.components, 360.0)
    assert bij.shape == (2, 2)
    assert bij[0, 1] == pytest.approx(bij[1, 0])
    assert np.isfinite(b0_pitzer(0.8))
    assert np.isfinite(b1_pitzer(0.8))
    phi = phi_mixture(system.components, 360.0, 1e-6, y, enabled=True)
    assert phi == pytest.approx(np.ones(2))


def test_bubl_t_real_wilson_gamma_phi_is_physical() -> None:
    repo = DataRepository()
    service = ThermodynamicVLEService(repo)
    result = service.calculate(
        CalculationRequest(
            CalculationType.BUBL_T,
            "cyclohexane_n_heptane",
            ActivityModel.WILSON,
            VaporModel.GAMMA_PHI,
            101.325,
            (0.5, 0.5),
        )
    )
    assert result.converged
    assert not result.simulated
    assert 80.7 < result.temperature_k - 273.15 < 98.4
    assert result.temperature_k == pytest.approx(361.344, rel=2e-4)
    assert sum(result.y) == pytest.approx(1.0)


def test_bubl_t_ideal_reference_matches_manual_value(tmp_path: Path) -> None:
    source = json.loads(Path("datos/base_datos_VLE.json").read_text(encoding="utf-8"))
    system = source["systems"][0]
    system["binary_parameters"]["Wilson"]["pairs"] = {
        "cyclohexane|n_heptane": 1.0,
        "n_heptane|cyclohexane": 1.0,
    }
    db_path = tmp_path / "db.json"
    db_path.write_text(json.dumps(source), encoding="utf-8")

    service = ThermodynamicVLEService(DataRepository(db_path))
    result = service.calculate(
        CalculationRequest(
            CalculationType.BUBL_T,
            "cyclohexane_n_heptane",
            ActivityModel.WILSON,
            VaporModel.COMPARE,
            101.325,
            (0.5, 0.5),
        )
    )

    assert result.temperature_k == pytest.approx(361.701, abs=0.02)
    assert result.temperature_k - 273.15 == pytest.approx(88.551, abs=0.02)
    assert result.psat_kpa[0] == pytest.approx(127.473, abs=0.05)
    assert result.psat_kpa[1] == pytest.approx(75.177, abs=0.05)
    assert result.y[0] == pytest.approx(0.629031, abs=5e-4)
    assert result.y[1] == pytest.approx(0.370969, abs=5e-4)
