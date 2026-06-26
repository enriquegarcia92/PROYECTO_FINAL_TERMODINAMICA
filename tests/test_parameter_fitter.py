from __future__ import annotations

import json
from pathlib import Path

import pytest

from vle_poc.domain import ActivityModel, CalculationRequest, CalculationType, VaporModel
from vle_poc.parameter_fitter import ActivityParameterFitter
from vle_poc.repository import DataRepository
from vle_poc.service import ThermodynamicVLEService
from vle_poc.validation import InputValidationError


def _copy_database(tmp_path: Path, *, clear_binary_parameters: bool = False) -> Path:
    source = json.loads(Path("datos/base_datos_VLE.json").read_text(encoding="utf-8"))
    if clear_binary_parameters:
        source["binary_parameters"] = {"Wilson": {}, "Margules": {}, "Van Laar": {}}
    db_path = tmp_path / "db.json"
    db_path.write_text(json.dumps(source, indent=2, ensure_ascii=False), encoding="utf-8")
    return db_path


def test_repository_loads_vle_fit_data() -> None:
    repository = DataRepository()
    fit_data = repository.fit_data_for(("cyclohexane", "n_heptane"))

    assert "cyclohexane|n_heptane" in fit_data
    assert fit_data["cyclohexane|n_heptane"][0]["pressure_kpa"] == pytest.approx(94.85152995052616)


def test_common_fitter_calculates_all_three_models() -> None:
    repository = DataRepository()
    system = repository.get("cyclohexane_n_heptane")
    fit_data = repository.fit_data_for(("cyclohexane", "n_heptane"))
    fitter = ActivityParameterFitter()

    for model in (ActivityModel.WILSON, ActivityModel.MARGULES, ActivityModel.VAN_LAAR):
        fitted = fitter.fit(system, model, fit_data)
        assert fitted.parameters["pairs"]["cyclohexane|n_heptane"]["calculated_from_vle"] is True
        assert fitted.parameters["pairs"]["n_heptane|cyclohexane"]["calculated_from_vle"] is True


def test_service_persists_automatic_parameters_to_json(tmp_path: Path) -> None:
    db_path = _copy_database(tmp_path, clear_binary_parameters=True)
    service = ThermodynamicVLEService(DataRepository(db_path))

    result = service.calculate(
        CalculationRequest(
            CalculationType.BUBL_P,
            "cyclohexane_n_heptane",
            ActivityModel.MARGULES,
            VaporModel.COMPARE,
            360.0,
            (0.45, 0.55),
        )
    )

    updated = json.loads(db_path.read_text(encoding="utf-8"))
    record = updated["binary_parameters"]["Margules"]["cyclohexane|n_heptane"]
    assert result.converged
    assert record["calculated_from_vle"] is True
    assert record["points_used"] == 1
    assert record["type"] == "dimensionless_a"


def test_service_blocks_when_vle_fit_data_is_missing(tmp_path: Path) -> None:
    db_path = _copy_database(tmp_path, clear_binary_parameters=True)
    source = json.loads(db_path.read_text(encoding="utf-8"))
    source["vle_fit_data"] = {}
    db_path.write_text(json.dumps(source, indent=2, ensure_ascii=False), encoding="utf-8")
    service = ThermodynamicVLEService(DataRepository(db_path))

    with pytest.raises(InputValidationError, match="Ingrese datos VLE"):
        service.calculate(
            CalculationRequest(
                CalculationType.BUBL_P,
                "cyclohexane_n_heptane",
                ActivityModel.MARGULES,
                VaporModel.COMPARE,
                360.0,
                (0.45, 0.55),
            )
        )


def test_user_vle_fit_data_does_not_persist_to_json(tmp_path: Path) -> None:
    db_path = _copy_database(tmp_path, clear_binary_parameters=True)
    service = ThermodynamicVLEService(DataRepository(db_path))
    user_fit_data = {
        "cyclohexane|n_heptane": [
            {
                "source": "Usuario prueba",
                "temperature_k": 360.0,
                "pressure_kpa": 94.85152995052616,
                "x": [0.45, 0.55],
                "y": [0.5842238765160485, 0.41577612348395143],
            }
        ]
    }

    result = service.calculate(
        CalculationRequest(
            CalculationType.BUBL_P,
            "cyclohexane_n_heptane",
            ActivityModel.MARGULES,
            VaporModel.COMPARE,
            360.0,
            (0.45, 0.55),
            user_vle_fit_data=user_fit_data,
        )
    )

    updated = json.loads(db_path.read_text(encoding="utf-8"))
    assert result.converged
    assert result.vle_fit_data_used[0]["source"] == "Usuario prueba"
    assert updated["binary_parameters"]["Margules"] == {}
