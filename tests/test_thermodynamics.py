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


def _repository_from_source(tmp_path: Path, source: dict) -> DataRepository:
    tmp_path.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "db.json"
    db_path.write_text(json.dumps(source), encoding="utf-8")
    return DataRepository(db_path)


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


def test_wilson_energy_difference_calculates_lambdas_from_temperature(tmp_path: Path) -> None:
    source = json.loads(Path("datos/base_datos_VLE.json").read_text(encoding="utf-8"))
    source["binary_parameters"]["Wilson"]["cyclohexane|n_heptane"] = {
        "source": "Prueba controlada de energía Wilson",
        "type": "energy_difference",
        "value": 0.0,
        "units": "J/mol",
    }
    source["binary_parameters"]["Wilson"]["n_heptane|cyclohexane"] = {
        "source": "Prueba controlada de energía Wilson",
        "type": "energy_difference",
        "value": 0.0,
        "units": "J/mol",
    }
    system = _repository_from_source(tmp_path, source).get("cyclohexane_n_heptane")

    gamma = activity_coefficients(ActivityModel.WILSON, system, 360.0, np.array([0.5, 0.5]))

    lambda_12 = system.components[1].liquid_molar_volume_m3_mol / system.components[0].liquid_molar_volume_m3_mol
    lambda_21 = system.components[0].liquid_molar_volume_m3_mol / system.components[1].liquid_molar_volume_m3_mol
    row_1 = 0.5 + lambda_12 * 0.5
    row_2 = lambda_21 * 0.5 + 0.5
    ln_gamma_1 = 1.0 - np.log(row_1) - (0.5 / row_1 + 0.5 * lambda_21 / row_2)
    ln_gamma_2 = 1.0 - np.log(row_2) - (0.5 * lambda_12 / row_1 + 0.5 / row_2)
    assert gamma == pytest.approx(np.exp([ln_gamma_1, ln_gamma_2]))


def test_wilson_energy_difference_accepts_cal_per_mol(tmp_path: Path) -> None:
    source_j = json.loads(Path("datos/base_datos_VLE.json").read_text(encoding="utf-8"))
    source_cal = json.loads(Path("datos/base_datos_VLE.json").read_text(encoding="utf-8"))
    for source, value, units in [(source_j, 418.4, "J/mol"), (source_cal, 100.0, "cal/mol")]:
        source["binary_parameters"]["Wilson"]["cyclohexane|n_heptane"] = {
            "source": "Prueba controlada de conversión",
            "type": "energy_difference",
            "value": value,
            "units": units,
        }
        source["binary_parameters"]["Wilson"]["n_heptane|cyclohexane"] = {
            "source": "Prueba controlada de conversión",
            "type": "energy_difference",
            "value": value,
            "units": units,
        }

    gamma_j = activity_coefficients(
        ActivityModel.WILSON,
        _repository_from_source(tmp_path / "j", source_j).get("cyclohexane_n_heptane"),
        360.0,
        np.array([0.5, 0.5]),
    )
    gamma_cal = activity_coefficients(
        ActivityModel.WILSON,
        _repository_from_source(tmp_path / "cal", source_cal).get("cyclohexane_n_heptane"),
        360.0,
        np.array([0.5, 0.5]),
    )
    assert gamma_cal == pytest.approx(gamma_j)


def test_wilson_reports_missing_directed_pair(tmp_path: Path) -> None:
    source = json.loads(Path("datos/base_datos_VLE.json").read_text(encoding="utf-8"))
    source["binary_parameters"]["Wilson"]["cyclohexane|ethanol"] = {
        "source": "Prueba incompleta",
        "type": "dimensionless_lambda",
        "value": 1.2,
    }
    system = _repository_from_source(tmp_path, source).build_system(("cyclohexane", "ethanol"))

    with pytest.raises(InputValidationError, match="ethanol\\|cyclohexane"):
        activity_coefficients(ActivityModel.WILSON, system, 360.0, np.array([0.5, 0.5]))


def test_wilson_energy_difference_requires_liquid_volume(tmp_path: Path) -> None:
    source = json.loads(Path("datos/base_datos_VLE.json").read_text(encoding="utf-8"))
    for component in source["components"]:
        if component["id"] == "cyclohexane":
            component["liquid_molar_volume_m3_mol"] = None
    source["binary_parameters"]["Wilson"]["cyclohexane|n_heptane"] = {
        "source": "Prueba sin volumen",
        "type": "energy_difference",
        "value": 0.0,
        "units": "J/mol",
    }
    source["binary_parameters"]["Wilson"]["n_heptane|cyclohexane"] = {
        "source": "Prueba sin volumen",
        "type": "energy_difference",
        "value": 0.0,
        "units": "J/mol",
    }
    system = _repository_from_source(tmp_path, source).get("cyclohexane_n_heptane")

    with pytest.raises(InputValidationError, match="falta volumen líquido"):
        activity_coefficients(ActivityModel.WILSON, system, 360.0, np.array([0.5, 0.5]))


def test_wilson_energy_difference_rejects_unsupported_units(tmp_path: Path) -> None:
    source = json.loads(Path("datos/base_datos_VLE.json").read_text(encoding="utf-8"))
    source["binary_parameters"]["Wilson"]["cyclohexane|n_heptane"] = {
        "source": "Prueba unidad inválida",
        "type": "energy_difference",
        "value": 0.0,
        "units": "BTU/lbmol",
    }
    system = _repository_from_source(tmp_path, source).get("cyclohexane_n_heptane")

    with pytest.raises(InputValidationError, match="Unidad energética Wilson no soportada"):
        activity_coefficients(ActivityModel.WILSON, system, 360.0, np.array([0.5, 0.5]))


def test_van_laar_without_vle_fit_data_is_blocked() -> None:
    repo = DataRepository()
    service = ThermodynamicVLEService(repo)
    request = CalculationRequest(
        CalculationType.BUBL_T,
        "benzene_n_hexane",
        ActivityModel.VAN_LAAR,
        VaporModel.GAMMA_PHI,
        101.325,
        (0.5, 0.5),
    )
    with pytest.raises(InputValidationError, match="no está disponible"):
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


def test_bubl_t_uses_documented_wilson_direct_parameters() -> None:
    service = ThermodynamicVLEService(DataRepository())
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

    assert result.temperature_k == pytest.approx(361.345, abs=0.03)
    assert result.temperature_k - 273.15 == pytest.approx(88.195, abs=0.03)
    assert result.y[0] == pytest.approx(0.630233, abs=2e-3)
    assert result.y[1] == pytest.approx(0.369767, abs=2e-3)
    assert any("problema 14.54" in source for source in result.data_sources)
