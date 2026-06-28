from __future__ import annotations

import numpy as np
import pytest

from vle_poc.azeotrope import analyze_result_point, detect_binary_curve_azeotrope
from vle_poc.domain import CalculationResult


def _result(x: tuple[float, ...], y: tuple[float, ...]) -> CalculationResult:
    size = len(x)
    return CalculationResult(
        calculation_type="BUBL P",
        system_name="Sistema prueba",
        component_names=tuple(f"C{i + 1}" for i in range(size)),
        temperature_k=350.0,
        pressure_kpa=101.325,
        x=x,
        y=y,
        gamma=tuple(1.0 for _ in range(size)),
        phi=tuple(1.0 for _ in range(size)),
        phi_sat=tuple(1.0 for _ in range(size)),
        poynting=tuple(1.0 for _ in range(size)),
        iterations=1,
        converged=True,
        residuals={},
        warnings=(),
        message="prueba",
        activity_model="Wilson",
        vapor_model="Gamma-phi completo",
    )


def test_result_point_marks_near_azeotrope() -> None:
    analysis = analyze_result_point(_result((0.5, 0.5), (0.5004, 0.4996)))

    assert analysis["near_azeotrope"] is True
    assert analysis["abs_x1_minus_y1"] == pytest.approx(4e-4)


def test_result_point_marks_non_azeotropic_point() -> None:
    analysis = analyze_result_point(_result((0.5, 0.5), (0.7, 0.3)))

    assert analysis["near_azeotrope"] is False
    assert "no es azeotrópico" in analysis["message"]


def test_curve_detector_returns_no_detection_without_crossing() -> None:
    data = {
        "diagram_type": np.asarray(["Pxy"]),
        "is_cut": np.asarray([0]),
        "x": np.asarray([0.1, 0.2, 0.3]),
        "y": np.asarray([0.4, 0.5, 0.6]),
        "liquid": np.asarray([100.0, 110.0, 120.0]),
    }

    analysis = detect_binary_curve_azeotrope(data)

    assert analysis["applicable"] is True
    assert analysis["detected"] is False


def test_curve_detector_interpolates_interior_crossing() -> None:
    data = {
        "diagram_type": np.asarray(["Pxy"]),
        "is_cut": np.asarray([0]),
        "x": np.asarray([0.2, 0.6]),
        "y": np.asarray([0.3, 0.5]),
        "liquid": np.asarray([90.0, 110.0]),
    }

    analysis = detect_binary_curve_azeotrope(data)

    assert analysis["detected"] is True
    assert analysis["x1"] == pytest.approx(0.4)
    assert analysis["y1"] == pytest.approx(0.4)
    assert analysis["value"] == pytest.approx(100.0)


def test_curve_detector_ignores_endpoint_crossing() -> None:
    data = {
        "diagram_type": np.asarray(["Txy"]),
        "is_cut": np.asarray([0]),
        "x": np.asarray([0.0, 0.01]),
        "y": np.asarray([0.0, 0.02]),
        "liquid": np.asarray([300.0, 301.0]),
    }

    analysis = detect_binary_curve_azeotrope(data)

    assert analysis["detected"] is False


def test_curve_detector_is_not_applicable_for_fugacity_diagram() -> None:
    analysis = detect_binary_curve_azeotrope({"diagram_type": np.asarray(["Fugacidad RK"])})

    assert analysis["applicable"] is False
    assert "No aplicable" in analysis["status"]
