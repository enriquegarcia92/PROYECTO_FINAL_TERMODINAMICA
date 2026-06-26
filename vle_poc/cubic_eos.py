"""EOS cúbicas RK/SRK para casos phi-phi del capítulo 14.

El módulo se mantiene separado del motor gamma-phi porque los sistemas ligeros
como N2/CH4 y CH4/n-butano no deben forzarse a Antoine + coeficientes gamma.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
from scipy.optimize import brentq

from .domain import ActivityModel, Component, SystemDefinition
from .validation import InputValidationError, validate_composition


R_KPA_M3_MOL_K = 0.008314462618


@dataclass(frozen=True)
class CubicPureParameters:
    a: float
    b: float
    alpha: float


@dataclass(frozen=True)
class CubicMixtureState:
    z: float
    phi: tuple[float, ...]


@dataclass(frozen=True)
class EosBubbleResult:
    pressure_kpa: float
    y: tuple[float, ...]
    phi_liquid: tuple[float, ...]
    phi_vapor: tuple[float, ...]
    k_values: tuple[float, ...]
    iterations: int
    residual: float


def pure_parameters(component: Component, temperature_k: float, model: ActivityModel) -> CubicPureParameters:
    if temperature_k <= 0:
        raise InputValidationError("Temperatura inválida para EOS cúbica.")
    if component.tc_k <= 0 or component.pc_kpa <= 0:
        raise InputValidationError(f"Faltan propiedades críticas de {component.name}.")
    tr = temperature_k / component.tc_k
    if model is ActivityModel.REDLICH_KWONG:
        alpha = tr**-0.5
        a = 0.42748 * (R_KPA_M3_MOL_K**2) * (component.tc_k**2) / component.pc_kpa * alpha
    elif model is ActivityModel.SOAVE_REDLICH_KWONG:
        m = 0.480 + 1.574 * component.omega - 0.176 * component.omega**2
        alpha = (1.0 + m * (1.0 - math.sqrt(tr))) ** 2
        a = 0.42748 * (R_KPA_M3_MOL_K**2) * (component.tc_k**2) / component.pc_kpa * alpha
    else:
        raise InputValidationError(f"Modelo EOS no soportado: {model.value}.")
    b = 0.08664 * R_KPA_M3_MOL_K * component.tc_k / component.pc_kpa
    return CubicPureParameters(a=float(a), b=float(b), alpha=float(alpha))


def _mixing(pures: tuple[CubicPureParameters, ...], composition: tuple[float, ...]) -> tuple[float, float, np.ndarray]:
    z = np.asarray(composition, dtype=float)
    a_i = np.asarray([pure.a for pure in pures], dtype=float)
    b_i = np.asarray([pure.b for pure in pures], dtype=float)
    a_ij = np.sqrt(np.outer(a_i, a_i))
    a_mix = float(z @ a_ij @ z)
    b_mix = float(np.dot(z, b_i))
    return a_mix, b_mix, a_ij


def z_roots(
    system: SystemDefinition,
    temperature_k: float,
    pressure_kpa: float,
    composition: tuple[float, ...],
    model: ActivityModel,
) -> tuple[float, ...]:
    pures = tuple(pure_parameters(component, temperature_k, model) for component in system.components)
    a_mix, b_mix, _ = _mixing(pures, composition)
    a_dimensionless = a_mix * pressure_kpa / (R_KPA_M3_MOL_K**2 * temperature_k**2)
    b_dimensionless = b_mix * pressure_kpa / (R_KPA_M3_MOL_K * temperature_k)
    # SRK/RK con u=1, w=0: Z^3 - Z^2 + (A-B-B^2)Z - AB = 0
    coeffs = [
        1.0,
        -1.0,
        a_dimensionless - b_dimensionless - b_dimensionless**2,
        -a_dimensionless * b_dimensionless,
    ]
    roots = np.roots(coeffs)
    real_roots = sorted(float(root.real) for root in roots if abs(root.imag) < 1e-8 and root.real > b_dimensionless)
    if not real_roots:
        raise InputValidationError("La EOS cúbica no produjo raíces Z reales físicas.")
    return tuple(real_roots)


def fugacity_coefficients(
    system: SystemDefinition,
    temperature_k: float,
    pressure_kpa: float,
    composition: tuple[float, ...],
    model: ActivityModel,
    phase: str = "vapor",
) -> CubicMixtureState:
    composition = validate_composition(composition, len(system.components))
    if pressure_kpa <= 0:
        raise InputValidationError("Presión inválida para EOS cúbica.")
    pures = tuple(pure_parameters(component, temperature_k, model) for component in system.components)
    a_mix, b_mix, a_ij = _mixing(pures, composition)
    z_values = z_roots(system, temperature_k, pressure_kpa, composition, model)
    z_factor = max(z_values) if phase == "vapor" else min(z_values)
    a_dimensionless = a_mix * pressure_kpa / (R_KPA_M3_MOL_K**2 * temperature_k**2)
    b_dimensionless = b_mix * pressure_kpa / (R_KPA_M3_MOL_K * temperature_k)
    if z_factor <= b_dimensionless:
        raise InputValidationError("Raíz Z no física para cálculo de fugacidad.")
    b_i = np.asarray([pure.b for pure in pures], dtype=float)
    composition_array = np.asarray(composition, dtype=float)
    a_i_mix = a_ij @ composition_array
    log_argument = 1.0 + b_dimensionless / z_factor
    phi: list[float] = []
    for index in range(len(system.components)):
        bi_over_b = b_i[index] / b_mix
        two_ai_over_a = 2.0 * a_i_mix[index] / a_mix if a_mix > 0 else 0.0
        ln_phi = (
            bi_over_b * (z_factor - 1.0)
            - math.log(z_factor - b_dimensionless)
            - (a_dimensionless / b_dimensionless) * (two_ai_over_a - bi_over_b) * math.log(log_argument)
        )
        phi.append(float(math.exp(ln_phi)))
    return CubicMixtureState(z=float(z_factor), phi=tuple(phi))


def bubble_pressure_phi_phi(
    system: SystemDefinition,
    temperature_k: float,
    liquid_composition: tuple[float, ...],
    model: ActivityModel = ActivityModel.SOAVE_REDLICH_KWONG,
    *,
    tolerance: float = 1e-6,
    max_iterations: int = 100,
) -> EosBubbleResult:
    if len(system.components) != 2:
        raise InputValidationError("BUBL P EOS está implementado para sistemas binarios.")
    x = np.asarray(validate_composition(liquid_composition, len(system.components)), dtype=float)
    pressure = _initial_pressure_guess(system, temperature_k, x)
    y = x.copy()
    residual = math.inf
    phi_l = np.ones(len(x))
    phi_v = np.ones(len(x))
    k_values = np.ones(len(x))
    for iteration in range(1, max_iterations + 1):
        liquid_state = fugacity_coefficients(system, temperature_k, pressure, tuple(x), model, phase="liquid")
        vapor_state = fugacity_coefficients(system, temperature_k, pressure, tuple(y), model, phase="vapor")
        phi_l = np.asarray(liquid_state.phi, dtype=float)
        phi_v = np.asarray(vapor_state.phi, dtype=float)
        k_values = phi_l / phi_v
        sum_kx = float(np.dot(k_values, x))
        residual = abs(sum_kx - 1.0)
        new_y = k_values * x / max(sum_kx, 1e-30)
        non_trivial_split = float(np.max(np.abs(k_values - 1.0))) > 1e-5
        if residual <= tolerance and non_trivial_split and float(np.max(np.abs(new_y - y))) <= max(tolerance, 1e-6):
            y = new_y
            break
        y = new_y
        pressure *= 1.25 if not non_trivial_split else max(0.25, min(4.0, sum_kx))
        pressure = max(1.0, min(20_000.0, pressure))
    else:
        # Refinamiento de seguridad con raíz externa de sum(Kx)-1.
        pressure = _bracketed_pressure(system, temperature_k, tuple(x), model, tolerance)
        liquid_state = fugacity_coefficients(system, temperature_k, pressure, tuple(x), model, phase="liquid")
        phi_l = np.asarray(liquid_state.phi, dtype=float)
        y = x.copy()
        for iteration in range(1, max_iterations + 1):
            vapor_state = fugacity_coefficients(system, temperature_k, pressure, tuple(y), model, phase="vapor")
            phi_v = np.asarray(vapor_state.phi, dtype=float)
            k_values = phi_l / phi_v
            sum_kx = float(np.dot(k_values, x))
            new_y = k_values * x / max(sum_kx, 1e-30)
            residual = abs(sum_kx - 1.0)
            y = new_y
            if residual <= tolerance:
                break
    return EosBubbleResult(
        pressure_kpa=float(pressure),
        y=tuple(float(value) for value in y),
        phi_liquid=tuple(float(value) for value in phi_l),
        phi_vapor=tuple(float(value) for value in phi_v),
        k_values=tuple(float(value) for value in k_values),
        iterations=int(iteration),
        residual=float(residual),
    )


def vapor_fugacity_result(
    system: SystemDefinition,
    temperature_k: float,
    pressure_kpa: float,
    vapor_composition: tuple[float, ...],
    model: ActivityModel = ActivityModel.REDLICH_KWONG,
) -> CubicMixtureState:
    return fugacity_coefficients(system, temperature_k, pressure_kpa, vapor_composition, model, phase="vapor")


def _initial_pressure_guess(system: SystemDefinition, temperature_k: float, x: np.ndarray) -> float:
    # Lee-Kesler/Pitzer simple para semilla: sirve aunque CH4 esté sobre Tc.
    guesses: list[float] = []
    for component in system.components:
        tr = temperature_k / component.tc_k
        if tr < 1.0:
            ln_pr = 5.373 * (1.0 + component.omega) * (1.0 - 1.0 / tr)
            guesses.append(component.pc_kpa * math.exp(ln_pr))
        else:
            guesses.append(component.pc_kpa)
    return float(max(10.0, min(15_000.0, np.dot(x, np.asarray(guesses)))))


def _sum_kx_minus_one(
    system: SystemDefinition,
    temperature_k: float,
    pressure_kpa: float,
    liquid_composition: tuple[float, ...],
    model: ActivityModel,
) -> float:
    if len(z_roots(system, temperature_k, pressure_kpa, liquid_composition, model)) < 2:
        return float("nan")
    x = np.asarray(liquid_composition, dtype=float)
    liquid_state = fugacity_coefficients(system, temperature_k, pressure_kpa, liquid_composition, model, phase="liquid")
    y = x.copy()
    phi_l = np.asarray(liquid_state.phi, dtype=float)
    for _ in range(40):
        vapor_state = fugacity_coefficients(system, temperature_k, pressure_kpa, tuple(y), model, phase="vapor")
        k = phi_l / np.asarray(vapor_state.phi, dtype=float)
        sum_kx = float(np.dot(k, x))
        y = k * x / max(sum_kx, 1e-30)
    return sum_kx - 1.0


def _bracketed_pressure(
    system: SystemDefinition,
    temperature_k: float,
    liquid_composition: tuple[float, ...],
    model: ActivityModel,
    tolerance: float,
) -> float:
    grid = np.geomspace(10.0, 20_000.0, 80)
    previous_p: float | None = None
    previous_f: float | None = None
    for pressure in grid[1:]:
        current_p = float(pressure)
        current_f = _sum_kx_minus_one(system, temperature_k, current_p, liquid_composition, model)
        if not math.isfinite(current_f):
            continue
        if previous_p is not None and previous_f is not None and (
            previous_f == 0 or current_f == 0 or previous_f * current_f < 0
        ):
            return float(
                brentq(
                    lambda p: _sum_kx_minus_one(system, temperature_k, p, liquid_composition, model),
                    previous_p,
                    current_p,
                    xtol=tolerance,
                )
            )
        previous_p, previous_f = current_p, current_f
    raise InputValidationError("No se encontró intervalo de presión para BUBL P EOS.")
