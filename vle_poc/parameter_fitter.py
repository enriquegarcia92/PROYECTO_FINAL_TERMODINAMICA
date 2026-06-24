"""Ajuste automático de parámetros de actividad desde datos VLE."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from typing import Any

import numpy as np
from scipy.optimize import least_squares

from .activity import GAS_CONSTANT_J_MOL_K
from .domain import ActivityModel, SystemDefinition
from .properties import psat_kpa
from .units import celsius_to_kelvin
from .validation import InputValidationError, validate_composition


@dataclass(frozen=True)
class VLEFitPoint:
    pair_key: str
    source: str
    temperature_k: float
    pressure_kpa: float
    x: tuple[float, float]
    y: tuple[float, float]
    gamma: tuple[float, float]
    ln_gamma: tuple[float, float]


@dataclass(frozen=True)
class FittedActivityParameters:
    model: str
    parameters: dict[str, Any]
    warnings: tuple[str, ...] = ()


class ActivityParameterFitter:
    """Calcula parámetros Wilson, Margules y Van Laar desde puntos VLE."""

    def fit(
        self,
        system: SystemDefinition,
        model: ActivityModel,
        fit_data: dict[str, list[dict[str, Any]]],
    ) -> FittedActivityParameters:
        if model is ActivityModel.WILSON:
            return self._fit_wilson(system, fit_data)
        if model is ActivityModel.MARGULES:
            return self._fit_margules(system, fit_data)
        if model is ActivityModel.VAN_LAAR:
            return self._fit_van_laar(system, fit_data)
        raise InputValidationError(f"Modelo de actividad no soportado para ajuste automático: {model.value}.")

    def _fit_margules(
        self,
        system: SystemDefinition,
        fit_data: dict[str, list[dict[str, Any]]],
    ) -> FittedActivityParameters:
        self._require_binary(system, "Margules")
        first, second = system.components
        pair_key = f"{first.id}|{second.id}"
        points = self._points_for_pair(system, fit_data, first.id, second.id)
        matrix: list[list[float]] = []
        rhs: list[float] = []
        for point in points:
            x1, x2 = point.x
            ln_g1, ln_g2 = point.ln_gamma
            matrix.append([x2**2 * (1.0 - 2.0 * x2), x2**2 * (2.0 * x2)])
            rhs.append(ln_g1)
            matrix.append([x1**2 * (2.0 * x1), x1**2 * (1.0 - 2.0 * x1)])
            rhs.append(ln_g2)
        solution, residuals, *_ = np.linalg.lstsq(np.asarray(matrix), np.asarray(rhs), rcond=None)
        a12, a21 = (float(solution[0]), float(solution[1]))
        return self._dimensionless_result(
            "Margules",
            pair_key,
            f"{second.id}|{first.id}",
            a12,
            a21,
            points,
            residuals,
        )

    def _fit_van_laar(
        self,
        system: SystemDefinition,
        fit_data: dict[str, list[dict[str, Any]]],
    ) -> FittedActivityParameters:
        self._require_binary(system, "Van Laar")
        first, second = system.components
        pair_key = f"{first.id}|{second.id}"
        points = self._points_for_pair(system, fit_data, first.id, second.id)
        seed = self._van_laar_seed(points[0])

        def residual(values: np.ndarray) -> np.ndarray:
            a12, a21 = values
            if a12 <= 0 or a21 <= 0:
                return np.full(len(points) * 2, 1e6)
            errors: list[float] = []
            for point in points:
                x1, x2 = point.x
                denominator = a12 * x1 + a21 * x2
                if denominator <= 0:
                    return np.full(len(points) * 2, 1e6)
                errors.append(a12 * ((a21 * x2) / denominator) ** 2 - point.ln_gamma[0])
                errors.append(a21 * ((a12 * x1) / denominator) ** 2 - point.ln_gamma[1])
            return np.asarray(errors, dtype=float)

        result = least_squares(residual, np.asarray(seed, dtype=float), bounds=(1e-12, np.inf), max_nfev=1000)
        if not result.success:
            raise InputValidationError("No se pudieron ajustar parámetros Van Laar desde los datos VLE.")
        a12, a21 = (float(result.x[0]), float(result.x[1]))
        return self._dimensionless_result(
            "Van Laar",
            pair_key,
            f"{second.id}|{first.id}",
            a12,
            a21,
            points,
            float(np.dot(result.fun, result.fun)),
        )

    def _fit_wilson(
        self,
        system: SystemDefinition,
        fit_data: dict[str, list[dict[str, Any]]],
    ) -> FittedActivityParameters:
        pairs: dict[str, Any] = {}
        sources: set[str] = set()
        residual_total = 0.0
        points_total = 0
        for i, first in enumerate(system.components):
            for j, second in enumerate(system.components):
                if i >= j:
                    continue
                pair_points = self._points_for_pair(system, fit_data, first.id, second.id)
                self._require_liquid_volumes(system, first.id, second.id)
                seed = np.zeros(2, dtype=float)

                def residual(values: np.ndarray) -> np.ndarray:
                    delta_12, delta_21 = values
                    errors: list[float] = []
                    for point in pair_points:
                        x1, x2 = point.x
                        volume_1 = first.liquid_molar_volume_m3_mol
                        volume_2 = second.liquid_molar_volume_m3_mol
                        lambda_12 = (volume_2 / volume_1) * math.exp(
                            -delta_12 / (GAS_CONSTANT_J_MOL_K * point.temperature_k)
                        )
                        lambda_21 = (volume_1 / volume_2) * math.exp(
                            -delta_21 / (GAS_CONSTANT_J_MOL_K * point.temperature_k)
                        )
                        row_1 = x1 + lambda_12 * x2
                        row_2 = lambda_21 * x1 + x2
                        if row_1 <= 0 or row_2 <= 0:
                            return np.full(len(pair_points) * 2, 1e6)
                        ln_g1 = 1.0 - math.log(row_1) - (x1 / row_1 + x2 * lambda_21 / row_2)
                        ln_g2 = 1.0 - math.log(row_2) - (x1 * lambda_12 / row_1 + x2 / row_2)
                        errors.append(ln_g1 - point.ln_gamma[0])
                        errors.append(ln_g2 - point.ln_gamma[1])
                    return np.asarray(errors, dtype=float)

                result = least_squares(residual, seed, max_nfev=1000)
                if not result.success:
                    raise InputValidationError(f"No se pudieron ajustar parámetros Wilson para {first.name}/{second.name}.")
                delta_12, delta_21 = (float(result.x[0]), float(result.x[1]))
                common = self._record_common(pair_points, float(np.dot(result.fun, result.fun)))
                pairs[f"{first.id}|{second.id}"] = {
                    **common,
                    "type": "energy_difference",
                    "value": delta_12,
                    "lambda_ij_minus_lambda_ii": delta_12,
                    "units": "J/mol",
                }
                pairs[f"{second.id}|{first.id}"] = {
                    **common,
                    "type": "energy_difference",
                    "value": delta_21,
                    "lambda_ij_minus_lambda_ii": delta_21,
                    "units": "J/mol",
                }
                sources.update(point.source for point in pair_points)
                residual_total += float(np.dot(result.fun, result.fun))
                points_total += len(pair_points)
        if not pairs:
            raise InputValidationError("No hay pares binarios para ajustar Wilson.")
        return FittedActivityParameters(
            model="Wilson",
            parameters={
                "type": "energy_difference",
                "source": " | ".join(sorted(sources)),
                "pairs": pairs,
                "residual_sum_squares": residual_total,
                "points_used": points_total,
            },
        )

    def _points_for_pair(
        self,
        system: SystemDefinition,
        fit_data: dict[str, list[dict[str, Any]]],
        first_id: str,
        second_id: str,
    ) -> tuple[VLEFitPoint, ...]:
        forward_key = f"{first_id}|{second_id}"
        reverse_key = f"{second_id}|{first_id}"
        if forward_key in fit_data:
            raw_points = fit_data[forward_key]
            reverse = False
            pair_key = forward_key
        elif reverse_key in fit_data:
            raw_points = fit_data[reverse_key]
            reverse = True
            pair_key = reverse_key
        else:
            raise InputValidationError(f"Faltan datos VLE para ajustar el par {forward_key}.")
        if not raw_points:
            raise InputValidationError(f"La sección VLE para {pair_key} no contiene puntos.")
        component_map = {component.id: component for component in system.components}
        points = [
            self._parse_point(pair_key, raw_point, component_map, reverse=reverse)
            for raw_point in raw_points
        ]
        return tuple(points)

    def _parse_point(
        self,
        pair_key: str,
        raw_point: dict[str, Any],
        component_map: dict[str, Any],
        *,
        reverse: bool,
    ) -> VLEFitPoint:
        first_id, _, second_id = pair_key.partition("|")
        if first_id not in component_map or second_id not in component_map:
            raise InputValidationError(f"El punto VLE {pair_key} no coincide con el sistema seleccionado.")
        temperature_k = self._temperature_k(raw_point)
        pressure_kpa = float(raw_point["pressure_kpa"])
        if pressure_kpa <= 0 or not math.isfinite(pressure_kpa):
            raise InputValidationError(f"Presión VLE inválida para {pair_key}.")
        x = validate_composition(tuple(float(value) for value in raw_point["x"]), 2)
        y = validate_composition(tuple(float(value) for value in raw_point["y"]), 2)
        if reverse:
            x = (x[1], x[0])
            y = (y[1], y[0])
            first_id, second_id = second_id, first_id
        if any(value <= 0 for value in x):
            raise InputValidationError(f"El ajuste automático requiere x_i > 0 en {pair_key}.")
        if any(value <= 0 for value in y):
            raise InputValidationError(f"El ajuste automático requiere y_i > 0 en {pair_key}.")
        components = (component_map[first_id], component_map[second_id])
        psat = tuple(psat_kpa(component, temperature_k) for component in components)
        gamma = tuple(y_i * pressure_kpa / (x_i * psat_i) for x_i, y_i, psat_i in zip(x, y, psat))
        if any(value <= 0 or not math.isfinite(value) for value in gamma):
            raise InputValidationError(f"Gamma VLE inválida para {pair_key}.")
        ln_gamma = tuple(math.log(value) for value in gamma)
        return VLEFitPoint(
            pair_key=f"{first_id}|{second_id}",
            source=str(raw_point.get("source", f"Datos VLE {pair_key}")),
            temperature_k=temperature_k,
            pressure_kpa=pressure_kpa,
            x=(float(x[0]), float(x[1])),
            y=(float(y[0]), float(y[1])),
            gamma=(float(gamma[0]), float(gamma[1])),
            ln_gamma=(float(ln_gamma[0]), float(ln_gamma[1])),
        )

    @staticmethod
    def _temperature_k(raw_point: dict[str, Any]) -> float:
        if "temperature_k" in raw_point:
            value = float(raw_point["temperature_k"])
        elif "temperature_c" in raw_point:
            value = celsius_to_kelvin(float(raw_point["temperature_c"]))
        else:
            raise InputValidationError("Cada punto VLE debe incluir temperature_k o temperature_c.")
        if value <= 0 or not math.isfinite(value):
            raise InputValidationError("Temperatura VLE inválida.")
        return value

    @staticmethod
    def _van_laar_seed(point: VLEFitPoint) -> tuple[float, float]:
        ln_g1, ln_g2 = point.ln_gamma
        if ln_g1 <= 0 or ln_g2 <= 0:
            raise InputValidationError("Van Laar requiere ln(gamma1) y ln(gamma2) positivos en los datos VLE.")
        x1, x2 = point.x
        a12 = ln_g1 * (1.0 + (x2 * ln_g2) / (x1 * ln_g1)) ** 2
        a21 = ln_g2 * (1.0 + (x1 * ln_g1) / (x2 * ln_g2)) ** 2
        return a12, a21

    @staticmethod
    def _require_binary(system: SystemDefinition, model: str) -> None:
        if len(system.components) != 2:
            raise InputValidationError(f"{model} automático solo está habilitado para sistemas binarios.")

    @staticmethod
    def _require_liquid_volumes(system: SystemDefinition, first_id: str, second_id: str) -> None:
        components = {component.id: component for component in system.components}
        for component_id in (first_id, second_id):
            if components[component_id].liquid_molar_volume_m3_mol is None:
                raise InputValidationError(f"Wilson automático requiere volumen líquido de {components[component_id].name}.")

    @staticmethod
    def _record_common(points: tuple[VLEFitPoint, ...], residual_sum_squares: float) -> dict[str, Any]:
        return {
            "source": " | ".join(sorted({point.source for point in points})),
            "calculated_from_vle": True,
            "calculated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "points_used": len(points),
            "residual_sum_squares": residual_sum_squares,
        }

    def _dimensionless_result(
        self,
        model: str,
        forward_key: str,
        reverse_key: str,
        a12: float,
        a21: float,
        points: tuple[VLEFitPoint, ...],
        residuals: Any,
    ) -> FittedActivityParameters:
        residual_sum = float(np.sum(residuals)) if np.ndim(residuals) else float(residuals)
        common = self._record_common(points, residual_sum)
        return FittedActivityParameters(
            model=model,
            parameters={
                "type": "dimensionless_a",
                "source": common["source"],
                "pairs": {
                    forward_key: {**common, "type": "dimensionless_a", "value": float(a12)},
                    reverse_key: {**common, "type": "dimensionless_a", "value": float(a21)},
                },
                "residual_sum_squares": residual_sum,
                "points_used": len(points),
            },
        )
