"""Propiedades puras con unidades explícitas."""

from __future__ import annotations

import math

from scipy.optimize import brentq

from .domain import Component
from .units import kelvin_to_celsius
from .validation import InputValidationError


def psat_kpa(component: Component, temperature_k: float, *, strict: bool = True) -> float:
    """Presión de saturación por Antoine.

    Convención del proyecto:
    ln(Psat [kPa]) = A - B / (T [°C] + C)
    """

    if component.antoine is None:
        raise InputValidationError(f"Faltan constantes de Antoine para {component.name}.")
    params = component.antoine
    if params.convention != "ln_kpa_celsius":
        raise InputValidationError(
            f"Convención Antoine no soportada para {component.name}: {params.convention}."
        )
    temperature_c = kelvin_to_celsius(temperature_k)
    if strict and not (params.t_min_c <= temperature_c <= params.t_max_c):
        raise InputValidationError(
            f"Temperatura {temperature_c:.3f} °C fuera del rango Antoine de {component.name} "
            f"({params.t_min_c:.3f} °C a {params.t_max_c:.3f} °C)."
        )
    denominator = temperature_c + params.c
    if denominator == 0:
        raise InputValidationError(f"Singularidad Antoine para {component.name}.")
    return math.exp(params.a - params.b / denominator)


def tsat_k_at_pressure(component: Component, pressure_kpa: float) -> float:
    if pressure_kpa <= 0 or not math.isfinite(pressure_kpa):
        raise InputValidationError("La presión debe ser positiva para invertir Antoine.")
    if component.antoine is None:
        raise InputValidationError(f"Faltan constantes de Antoine para {component.name}.")
    params = component.antoine
    lower = params.t_min_c + 273.15
    upper = params.t_max_c + 273.15

    def residual(temperature_k: float) -> float:
        return psat_kpa(component, temperature_k, strict=False) - pressure_kpa

    try:
        return brentq(residual, lower, upper, xtol=1e-10, rtol=1e-10, maxiter=100)
    except ValueError as exc:
        raise InputValidationError(
            f"No se encontró temperatura de saturación de {component.name} a {pressure_kpa:.3f} kPa "
            f"dentro del rango Antoine."
        ) from exc
