"""Ajuste de parámetros binarios Van Laar desde un punto VLE."""

from __future__ import annotations

from dataclasses import dataclass
import math

from .domain import SystemDefinition
from .properties import psat_kpa
from .validation import InputValidationError, validate_composition


@dataclass(frozen=True)
class VanLaarFitResult:
    """Resultado del ajuste inverso para Van Laar binario."""

    a12: float
    a21: float
    gamma: tuple[float, float]
    ln_gamma: tuple[float, float]
    psat_kpa: tuple[float, float]
    residuals: dict[str, float]


def fit_van_laar_binary_from_vle(
    system: SystemDefinition,
    temperature_k: float,
    pressure_kpa: float,
    x: tuple[float, float],
    y: tuple[float, float],
) -> VanLaarFitResult:
    """Calcula A12/A21 de Van Laar desde un punto VLE binario.

    Usa:
    gamma_i = y_i P / (x_i Psat_i)

    y la forma inversa estándar:
    A12 = ln(gamma1) * [1 + x2 ln(gamma2)/(x1 ln(gamma1))]^2
    A21 = ln(gamma2) * [1 + x1 ln(gamma1)/(x2 ln(gamma2))]^2
    """

    if len(system.components) != 2:
        raise InputValidationError("El ajuste Van Laar solo está definido para sistemas binarios.")
    if pressure_kpa <= 0 or not math.isfinite(pressure_kpa):
        raise InputValidationError("La presión VLE para ajustar Van Laar debe ser positiva y finita.")
    if temperature_k <= 0 or not math.isfinite(temperature_k):
        raise InputValidationError("La temperatura VLE para ajustar Van Laar debe ser positiva y finita.")

    liquid = validate_composition(tuple(x), 2)
    vapor = validate_composition(tuple(y), 2)
    if any(value <= 0 for value in liquid):
        raise InputValidationError("El ajuste Van Laar requiere x_i > 0 para ambos componentes.")
    if any(value <= 0 for value in vapor):
        raise InputValidationError("El ajuste Van Laar requiere y_i > 0 para ambos componentes.")

    psat = tuple(psat_kpa(component, temperature_k) for component in system.components)
    if any(value <= 0 or not math.isfinite(value) for value in psat):
        raise InputValidationError("Las presiones de saturación para ajustar Van Laar deben ser positivas.")

    gamma = tuple(
        vapor_i * pressure_kpa / (liquid_i * psat_i)
        for liquid_i, vapor_i, psat_i in zip(liquid, vapor, psat)
    )
    if any(value <= 0 or not math.isfinite(value) for value in gamma):
        raise InputValidationError("Los coeficientes gamma calculados para Van Laar deben ser positivos.")

    ln_gamma = tuple(math.log(value) for value in gamma)
    if any(value <= 0 or not math.isfinite(value) for value in ln_gamma):
        raise InputValidationError(
            "El ajuste Van Laar requiere ln(gamma1) y ln(gamma2) positivos y finitos."
        )

    x1, x2 = liquid
    ln_g1, ln_g2 = ln_gamma
    a12 = ln_g1 * (1.0 + (x2 * ln_g2) / (x1 * ln_g1)) ** 2
    a21 = ln_g2 * (1.0 + (x1 * ln_g1) / (x2 * ln_g2)) ** 2
    if a12 <= 0 or a21 <= 0 or not math.isfinite(a12) or not math.isfinite(a21):
        raise InputValidationError("El ajuste Van Laar generó parámetros no positivos o no finitos.")

    denominator = a12 * x1 + a21 * x2
    predicted_ln_g1 = a12 * ((a21 * x2) / denominator) ** 2
    predicted_ln_g2 = a21 * ((a12 * x1) / denominator) ** 2
    return VanLaarFitResult(
        a12=float(a12),
        a21=float(a21),
        gamma=(float(gamma[0]), float(gamma[1])),
        ln_gamma=(float(ln_gamma[0]), float(ln_gamma[1])),
        psat_kpa=(float(psat[0]), float(psat[1])),
        residuals={
            "ln_gamma_1": float(abs(predicted_ln_g1 - ln_g1)),
            "ln_gamma_2": float(abs(predicted_ln_g2 - ln_g2)),
        },
    )
