"""Modelos de coeficiente de actividad."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from .domain import ActivityModel, SystemDefinition
from .validation import InputValidationError


def ideal_gamma(size: int) -> np.ndarray:
    return np.ones(size, dtype=float)


def activity_coefficients(
    model: ActivityModel,
    system: SystemDefinition,
    temperature_k: float,
    x: np.ndarray,
) -> np.ndarray:
    if np.any(x < 0) or not np.isclose(float(np.sum(x)), 1.0, atol=1e-6):
        raise InputValidationError("La composición líquida para gamma debe estar normalizada.")
    parameters = system.binary_parameters.get(model.value)
    if not parameters:
        raise InputValidationError(
            f"Faltan parámetros {model.value} para {system.name}. "
            "Seleccione un modelo con datos documentados o complete la base de datos."
        )
    if model is ActivityModel.WILSON:
        return wilson_gamma(system, x, parameters)
    if model is ActivityModel.MARGULES:
        return margules_gamma(system, x, parameters)
    if model is ActivityModel.VAN_LAAR:
        return van_laar_gamma(system, x, parameters)
    raise InputValidationError(f"Modelo de actividad no soportado: {model.value}.")


def _pair_value(parameters: dict[str, Any], first: str, second: str) -> float:
    key = f"{first}|{second}"
    try:
        return float(parameters["pairs"][key])
    except KeyError as exc:
        raise InputValidationError(f"Falta parámetro binario {key}.") from exc


def wilson_gamma(system: SystemDefinition, x: np.ndarray, parameters: dict[str, Any]) -> np.ndarray:
    size = len(system.components)
    lambdas = np.eye(size)
    for i, component_i in enumerate(system.components):
        for j, component_j in enumerate(system.components):
            if i != j:
                lambdas[i, j] = _pair_value(parameters, component_i.id, component_j.id)
    row_sums = lambdas @ x
    if np.any(row_sums <= 0):
        raise InputValidationError("Parámetros Wilson generan sumas no positivas.")
    ln_gamma = np.zeros(size)
    for i in range(size):
        second = 0.0
        for j in range(size):
            denominator = float(np.dot(x, lambdas[j, :]))
            second += x[j] * lambdas[j, i] / denominator
        ln_gamma[i] = 1.0 - math.log(row_sums[i]) - second
    return np.exp(ln_gamma)


def margules_gamma(system: SystemDefinition, x: np.ndarray, parameters: dict[str, Any]) -> np.ndarray:
    if len(system.components) != 2:
        raise InputValidationError("Margules solo está habilitado para sistemas binarios con parámetros.")
    c1, c2 = system.components
    a12 = _pair_value(parameters, c1.id, c2.id)
    a21 = _pair_value(parameters, c2.id, c1.id)
    x1, x2 = float(x[0]), float(x[1])
    ln_g1 = x2**2 * (a12 + 2.0 * (a21 - a12) * x1)
    ln_g2 = x1**2 * (a21 + 2.0 * (a12 - a21) * x2)
    return np.exp(np.array([ln_g1, ln_g2], dtype=float))


def van_laar_gamma(system: SystemDefinition, x: np.ndarray, parameters: dict[str, Any]) -> np.ndarray:
    if len(system.components) != 2:
        raise InputValidationError("Van Laar solo está habilitado para sistemas binarios con parámetros.")
    c1, c2 = system.components
    a12 = _pair_value(parameters, c1.id, c2.id)
    a21 = _pair_value(parameters, c2.id, c1.id)
    x1, x2 = float(x[0]), float(x[1])
    denominator = a12 * x1 + a21 * x2
    if denominator <= 0:
        raise InputValidationError("Parámetros Van Laar generan denominador no positivo.")
    ln_g1 = a12 * ((a21 * x2) / denominator) ** 2
    ln_g2 = a21 * ((a12 * x1) / denominator) ** 2
    return np.exp(np.array([ln_g1, ln_g2], dtype=float))
