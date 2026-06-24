"""Modelos de coeficiente de actividad."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from .domain import ActivityModel, SystemDefinition
from .validation import InputValidationError

GAS_CONSTANT_J_MOL_K = 8.314462618
CAL_TO_J = 4.184


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
        return wilson_gamma(system, temperature_k, x, parameters)
    if model is ActivityModel.MARGULES:
        return margules_gamma(system, x, parameters)
    if model is ActivityModel.VAN_LAAR:
        return van_laar_gamma(system, x, parameters)
    raise InputValidationError(f"Modelo de actividad no soportado: {model.value}.")


def _pair_record(parameters: dict[str, Any], first: str, second: str) -> Any:
    key = f"{first}|{second}"
    try:
        return parameters["pairs"][key]
    except KeyError as exc:
        raise InputValidationError(f"Falta parámetro binario {key}.") from exc


def _pair_value(parameters: dict[str, Any], first: str, second: str) -> float:
    record = _pair_record(parameters, first, second)
    if isinstance(record, dict):
        try:
            return float(record["value"])
        except KeyError as exc:
            raise InputValidationError(f"Falta valor numérico para el parámetro binario {first}|{second}.") from exc
    return float(record)


def _energy_to_j_per_mol(value: float, units: str, key: str) -> float:
    normalized = units.strip().lower().replace(" ", "")
    if normalized in {"j/mol", "jmol^-1", "jmol-1"}:
        return value
    if normalized in {"cal/mol", "calmol^-1", "calmol-1"}:
        return value * CAL_TO_J
    raise InputValidationError(
        f"Unidad energética Wilson no soportada para {key}: {units}. "
        "Use J/mol o cal/mol."
    )


def _wilson_lambda_value(
    system: SystemDefinition,
    parameters: dict[str, Any],
    temperature_k: float,
    i: int,
    j: int,
) -> float:
    component_i = system.components[i]
    component_j = system.components[j]
    key = f"{component_i.id}|{component_j.id}"
    try:
        record = _pair_record(parameters, component_i.id, component_j.id)
    except InputValidationError as exc:
        raise InputValidationError(
            f"Falta parámetro binario Wilson {key}. "
            "Wilson requiere Λij directo o energía λij−λii documentada para cada par dirigido."
        ) from exc

    if not isinstance(record, dict):
        value = float(record)
    else:
        parameter_type = record.get("type", "dimensionless_lambda")
        if parameter_type == "dimensionless_lambda":
            try:
                value = float(record["value"])
            except KeyError as exc:
                raise InputValidationError(f"Falta valor Λij para el parámetro Wilson {key}.") from exc
        elif parameter_type == "energy_difference":
            volume_i = component_i.liquid_molar_volume_m3_mol
            volume_j = component_j.liquid_molar_volume_m3_mol
            if volume_i is None or volume_j is None:
                raise InputValidationError(
                    f"No se puede calcular Λij(T) para {key}: falta volumen líquido de una sustancia."
                )
            if temperature_k <= 0 or not math.isfinite(temperature_k):
                raise InputValidationError("Temperatura Kelvin inválida para calcular parámetros Wilson.")
            raw_energy = record.get("lambda_ij_minus_lambda_ii", record.get("value"))
            if raw_energy is None:
                raise InputValidationError(
                    f"Falta energía Wilson λij−λii para {key}; no basta con Antoine o propiedades críticas."
                )
            units = str(record.get("units", "J/mol"))
            delta_j_per_mol = _energy_to_j_per_mol(float(raw_energy), units, key)
            value = (volume_j / volume_i) * math.exp(-delta_j_per_mol / (GAS_CONSTANT_J_MOL_K * temperature_k))
        else:
            raise InputValidationError(
                f"Tipo de parámetro Wilson no soportado para {key}: {parameter_type}. "
                "Use dimensionless_lambda o energy_difference."
            )

    if value <= 0 or not math.isfinite(value):
        raise InputValidationError(f"El parámetro Wilson Λ para {key} debe ser positivo y finito.")
    return value


def wilson_gamma(
    system: SystemDefinition,
    temperature_k: float,
    x: np.ndarray,
    parameters: dict[str, Any],
) -> np.ndarray:
    size = len(system.components)
    lambdas = np.eye(size)
    for i, _component_i in enumerate(system.components):
        for j, _component_j in enumerate(system.components):
            if i != j:
                lambdas[i, j] = _wilson_lambda_value(system, parameters, temperature_k, i, j)
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
    ln_g1 = x2**2 * (a12 + 2.0 * (a21 - a12) * x2)
    ln_g2 = x1**2 * (a21 + 2.0 * (a12 - a21) * x1)
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
