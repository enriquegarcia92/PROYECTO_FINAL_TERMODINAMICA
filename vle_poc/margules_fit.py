"""Ajuste de parámetros binarios Margules desde un punto VLE."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from .domain import SystemDefinition
from .properties import psat_kpa
from .validation import InputValidationError, validate_composition


@dataclass(frozen=True)
class MargulesFitResult:
    """Resultado del SEL para Margules binario."""

    a12: float
    a21: float
    gamma: tuple[float, float]
    ln_gamma: tuple[float, float]
    psat_kpa: tuple[float, float]
    residuals: dict[str, float]


def fit_margules_binary_from_vle(
    system: SystemDefinition,
    temperature_k: float,
    pressure_kpa: float,
    x: tuple[float, float],
    y: tuple[float, float],
) -> MargulesFitResult:
    """Calcula A12/A21 de Margules desde un punto VLE binario.

    Usa:
    gamma_i = y_i P / (x_i Psat_i)

    y resuelve el sistema:
    ln(gamma1) = x2^2 [A12 + 2(A21 - A12)x2]
    ln(gamma2) = x1^2 [A21 + 2(A12 - A21)x1]
    """

    if len(system.components) != 2:
        raise InputValidationError("El ajuste Margules por SEL solo está definido para sistemas binarios.")
    if pressure_kpa <= 0 or not math.isfinite(pressure_kpa):
        raise InputValidationError("La presión VLE para ajustar Margules debe ser positiva y finita.")
    if temperature_k <= 0 or not math.isfinite(temperature_k):
        raise InputValidationError("La temperatura VLE para ajustar Margules debe ser positiva y finita.")

    liquid = validate_composition(tuple(x), 2)
    vapor = validate_composition(tuple(y), 2)
    if any(value <= 0 for value in liquid):
        raise InputValidationError("El ajuste Margules requiere x_i > 0 para ambos componentes.")
    if any(value <= 0 for value in vapor):
        raise InputValidationError("El ajuste Margules requiere y_i > 0 para ambos componentes.")

    psat = tuple(psat_kpa(component, temperature_k) for component in system.components)
    if any(value <= 0 or not math.isfinite(value) for value in psat):
        raise InputValidationError("Las presiones de saturación para ajustar Margules deben ser positivas.")

    gamma = tuple(
        vapor_i * pressure_kpa / (liquid_i * psat_i)
        for liquid_i, vapor_i, psat_i in zip(liquid, vapor, psat)
    )
    if any(value <= 0 or not math.isfinite(value) for value in gamma):
        raise InputValidationError("Los coeficientes gamma calculados para Margules deben ser positivos.")
    ln_gamma = tuple(math.log(value) for value in gamma)

    x1, x2 = liquid
    matrix = np.array(
        [
            [x2**2 * (1.0 - 2.0 * x2), x2**2 * (2.0 * x2)],
            [x1**2 * (2.0 * x1), x1**2 * (1.0 - 2.0 * x1)],
        ],
        dtype=float,
    )
    rhs = np.array(ln_gamma, dtype=float)
    try:
        a12, a21 = np.linalg.solve(matrix, rhs)
    except np.linalg.LinAlgError as exc:
        raise InputValidationError("El SEL de Margules no pudo resolverse con este punto VLE.") from exc

    predicted = matrix @ np.array([a12, a21], dtype=float)
    residual = predicted - rhs
    return MargulesFitResult(
        a12=float(a12),
        a21=float(a21),
        gamma=(float(gamma[0]), float(gamma[1])),
        ln_gamma=(float(ln_gamma[0]), float(ln_gamma[1])),
        psat_kpa=(float(psat[0]), float(psat[1])),
        residuals={
            "ln_gamma_1": float(abs(residual[0])),
            "ln_gamma_2": float(abs(residual[1])),
        },
    )
