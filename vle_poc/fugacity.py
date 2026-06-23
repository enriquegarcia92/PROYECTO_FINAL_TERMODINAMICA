"""Correcciones gamma-phi con Pitzer/virial."""

from __future__ import annotations

import math

import numpy as np

from .domain import Component

R_KPA_M3_MOL_K = 8.314462618e-3


def b0_pitzer(tr: float) -> float:
    return 0.083 - 0.422 / tr**1.6


def b1_pitzer(tr: float) -> float:
    return 0.139 - 0.172 / tr**4.2


def pure_second_virial_m3_mol(component: Component, temperature_k: float) -> float:
    tr = temperature_k / component.tc_k
    return R_KPA_M3_MOL_K * component.tc_k / component.pc_kpa * (
        b0_pitzer(tr) + component.omega * b1_pitzer(tr)
    )


def second_virial_matrix(components: tuple[Component, ...], temperature_k: float) -> np.ndarray:
    size = len(components)
    matrix = np.zeros((size, size), dtype=float)
    for i, ci in enumerate(components):
        for j, cj in enumerate(components):
            if i == j:
                matrix[i, j] = pure_second_virial_m3_mol(ci, temperature_k)
            else:
                tc_ij = math.sqrt(ci.tc_k * cj.tc_k)
                pc_ij = 2.0 / (1.0 / ci.pc_kpa + 1.0 / cj.pc_kpa)
                omega_ij = 0.5 * (ci.omega + cj.omega)
                tr_ij = temperature_k / tc_ij
                matrix[i, j] = R_KPA_M3_MOL_K * tc_ij / pc_ij * (
                    b0_pitzer(tr_ij) + omega_ij * b1_pitzer(tr_ij)
                )
    return matrix


def phi_mixture(
    components: tuple[Component, ...],
    temperature_k: float,
    pressure_kpa: float,
    y: np.ndarray,
    *,
    enabled: bool,
) -> np.ndarray:
    if not enabled or pressure_kpa <= 0:
        return np.ones(len(components), dtype=float)
    bij = second_virial_matrix(components, temperature_k)
    b_mix = float(y @ bij @ y)
    ln_phi = np.zeros(len(components), dtype=float)
    for i in range(len(components)):
        partial = 2.0 * float(np.dot(y, bij[i, :])) - b_mix
        ln_phi[i] = pressure_kpa * partial / (R_KPA_M3_MOL_K * temperature_k)
    return np.exp(ln_phi)


def phi_sat_pitzer(
    component: Component,
    temperature_k: float,
    psat_kpa: float,
    *,
    enabled: bool,
) -> float:
    if not enabled or psat_kpa <= 0:
        return 1.0
    b_ii = pure_second_virial_m3_mol(component, temperature_k)
    return math.exp(psat_kpa * b_ii / (R_KPA_M3_MOL_K * temperature_k))


def poynting_factor(
    component: Component,
    temperature_k: float,
    pressure_kpa: float,
    psat_kpa: float,
    *,
    enabled: bool,
) -> float:
    if not enabled or component.liquid_molar_volume_m3_mol is None:
        return 1.0
    exponent = component.liquid_molar_volume_m3_mol * (pressure_kpa - psat_kpa) / (
        R_KPA_M3_MOL_K * temperature_k
    )
    return math.exp(exponent)
