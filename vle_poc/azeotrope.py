"""Detección ligera de azeótropos en resultados y curvas VLE."""

from __future__ import annotations

from typing import Any

import numpy as np

from .domain import CalculationResult


POINT_TOLERANCE = 1e-3
INTERIOR_MIN = 0.02
INTERIOR_MAX = 0.98


def analyze_result_point(result: CalculationResult, tolerance: float = POINT_TOLERANCE) -> dict[str, Any]:
    """Evalúa si el punto calculado está cerca de x_i = y_i."""

    if not result.x or not result.y or len(result.x) != len(result.y):
        return {
            "applicable": False,
            "status": "No aplicable",
            "message": "No hay composiciones líquido/vapor comparables.",
            "tolerance": tolerance,
        }

    deviations = [abs(x_i - y_i) for x_i, y_i in zip(result.x, result.y)]
    max_deviation = max(deviations)
    near = max_deviation <= tolerance
    analysis: dict[str, Any] = {
        "applicable": True,
        "near_azeotrope": near,
        "max_abs_x_minus_y": float(max_deviation),
        "tolerance": tolerance,
        "status": "Punto cercano a azeótropo" if near else "Punto no azeotrópico",
        "message": (
            "El punto calculado está cerca de condición azeotrópica."
            if near
            else "El punto calculado no es azeotrópico."
        ),
    }
    if len(result.x) == 2:
        analysis["abs_x1_minus_y1"] = float(abs(result.x[0] - result.y[0]))
    return analysis


def detect_binary_curve_azeotrope(data: dict[str, Any]) -> dict[str, Any]:
    """Busca cruces interiores de y1 - x1 en una curva Pxy/Txy binaria."""

    diagram_type = str(_first(data.get("diagram_type"), ""))
    if diagram_type not in {"Pxy", "Txy"}:
        return {
            "applicable": False,
            "detected": False,
            "status": "No aplicable",
            "message": "No aplicable: este cálculo no corresponde a un diagrama Pxy/Txy gamma-phi.",
        }
    if int(_first(data.get("is_cut"), 0) or 0) == 1:
        return {
            "applicable": False,
            "detected": False,
            "status": "No aplicable en corte multicomponente",
            "message": "No aplicable globalmente: el diagrama es un corte composicional multicomponente.",
        }

    x_values = np.asarray(data.get("x", []), dtype=float)
    y_values = np.asarray(data.get("y", []), dtype=float)
    values = np.asarray(data.get("liquid", []), dtype=float)
    if len(x_values) < 2 or len(x_values) != len(y_values) or len(x_values) != len(values):
        return {
            "applicable": True,
            "detected": False,
            "status": "No detectado",
            "message": "No hay suficientes puntos de curva para evaluar cruces x=y.",
        }

    deviations = y_values - x_values
    best: dict[str, Any] | None = None
    for idx in range(len(x_values) - 1):
        x0, x1 = float(x_values[idx]), float(x_values[idx + 1])
        d0, d1 = float(deviations[idx]), float(deviations[idx + 1])
        if not all(np.isfinite([x0, x1, d0, d1, values[idx], values[idx + 1]])):
            continue
        if not (INTERIOR_MIN <= x0 <= INTERIOR_MAX and INTERIOR_MIN <= x1 <= INTERIOR_MAX):
            continue
        if d0 == 0.0:
            fraction = 0.0
        elif d0 * d1 > 0:
            continue
        else:
            denominator = d0 - d1
            if denominator == 0.0:
                continue
            fraction = d0 / denominator
        if not (0.0 <= fraction <= 1.0):
            continue
        x_az = x0 + fraction * (x1 - x0)
        value_az = float(values[idx]) + fraction * (float(values[idx + 1]) - float(values[idx]))
        best = {
            "applicable": True,
            "detected": True,
            "status": "Azeótropo predicho por la curva",
            "message": "Azeótropo predicho/detectado por el modelo en la curva generada.",
            "x1": float(x_az),
            "y1": float(x_az),
            "value": float(value_az),
            "value_label": "Presión (kPa)" if diagram_type == "Pxy" else "Temperatura (K)",
            "diagram_type": diagram_type,
            "tolerance": POINT_TOLERANCE,
        }
        break

    if best is not None:
        return best
    return {
        "applicable": True,
        "detected": False,
        "status": "No detectado",
        "message": "No se detectó cruce interior x1≈y1 en la curva generada.",
        "tolerance": POINT_TOLERANCE,
    }


def _first(value: Any, default: Any) -> Any:
    try:
        return value[0]
    except (TypeError, IndexError, KeyError):
        return default
