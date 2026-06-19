"""Servicio determinista de la POC; será sustituido por los solvers reales."""

from __future__ import annotations

import math

import numpy as np

from .domain import CalculationRequest, CalculationResult, CalculationType, VaporModel
from .repository import DataRepository
from .validation import validate_request


SIMULATION_WARNING = "Datos simulados — no usar para cálculos ni decisiones de ingeniería."


class MockVLEService:
    def __init__(self, repository: DataRepository) -> None:
        self.repository = repository

    @staticmethod
    def _normalize(values: np.ndarray) -> np.ndarray:
        return values / values.sum()

    def calculate(self, request: CalculationRequest) -> CalculationResult:
        system = self.repository.get(request.system_id)
        request = validate_request(request, system)
        known = np.asarray(request.composition, dtype=float)
        count = len(known)
        volatility = np.linspace(1.75, 0.72, count)

        if request.calculation_type.known_phase == "líquido":
            x = known
            y = self._normalize(x * volatility)
        else:
            y = known
            x = self._normalize(y / volatility)

        model_factor = {"Wilson": 1.0, "Margules": 1.035, "Van Laar": 0.975}[
            request.activity_model.value
        ]
        weighted = float(np.dot(x, np.linspace(1.08, 0.91, count)))
        if request.calculation_type in {CalculationType.BUBL_P, CalculationType.DEW_P}:
            temperature_k = request.fixed_value
            pressure_kpa = (45.0 + 0.92 * (temperature_k - 273.15)) * weighted * model_factor
            pressure_kpa = max(8.0, pressure_kpa)
            output_value = pressure_kpa
            comparison_label = "Presión con phi = 1 (kPa)"
        else:
            pressure_kpa = request.fixed_value
            temperature_k = 292.0 + 0.42 * pressure_kpa / max(weighted, 0.5) / model_factor
            output_value = temperature_k
            comparison_label = "Temperatura con phi = 1 (K)"

        indices = np.arange(count, dtype=float)
        gamma = 1.0 + (0.10 + 0.025 * indices) * (1.0 - x)
        phi = 1.0 - (0.012 + 0.004 * indices) * min(pressure_kpa / 500.0, 1.0)
        phi_sat = 1.0 - 0.004 * (indices + 1)
        poynting = 1.0 + 0.0006 * (indices + 1) * min(pressure_kpa / 100.0, 5.0)
        iterations = 5 + count + list(CalculationType).index(request.calculation_type)
        comparison = output_value * 0.982 if request.vapor_model is VaporModel.COMPARE else None
        history = tuple(
            {
                "iteration": float(i),
                "residual": 10 ** (-(i + 1)),
                "value": output_value * (1 + 0.04 / (i + 1)),
            }
            for i in range(1, iterations + 1)
        )
        result = CalculationResult(
            calculation_type=request.calculation_type.value,
            system_name=system.name,
            component_names=tuple(component.name for component in system.components),
            temperature_k=float(temperature_k),
            pressure_kpa=float(pressure_kpa),
            x=tuple(float(value) for value in x),
            y=tuple(float(value) for value in y),
            gamma=tuple(float(value) for value in gamma),
            phi=tuple(float(value) for value in phi),
            phi_sat=tuple(float(value) for value in phi_sat),
            poynting=tuple(float(value) for value in poynting),
            iterations=iterations,
            converged=True,
            residuals={
                "variable_relativa": 4.2e-6,
                "composicion": 7.5e-7,
                "fugacidad": 8.1e-6,
            },
            warnings=(SIMULATION_WARNING,),
            message="La simulación POC completó el flujo de cálculo correctamente.",
            activity_model=request.activity_model.value,
            vapor_model=request.vapor_model.value,
            comparison_value=comparison,
            comparison_label=comparison_label if comparison is not None else None,
            history=history,
        )
        result.assert_shape()
        return result

    def phase_curve(self, system_id: str, diagram_type: str, fixed_value: float) -> dict[str, np.ndarray]:
        system = self.repository.get(system_id)
        if len(system.components) != 2:
            raise ValueError("La POC gráfica Pxy/Txy solo para sistemas binarios.")
        x = np.linspace(0.0, 1.0, 41)
        y = (1.65 * x) / (1.0 + 0.65 * x)
        if diagram_type == "Pxy":
            liquid = 55.0 + 55.0 * x + 7.0 * np.sin(np.pi * x)
            vapor = 55.0 + 55.0 * y - 5.0 * np.sin(np.pi * y)
            ylabel = "Presión (kPa)"
            condition = f"T = {fixed_value:.2f} K"
        else:
            liquid = 365.0 - 28.0 * x - 5.0 * np.sin(np.pi * x)
            vapor = 365.0 - 28.0 * y + 4.0 * np.sin(np.pi * y)
            ylabel = "Temperatura (K)"
            condition = f"P = {fixed_value:.2f} kPa"
        return {
            "x": x,
            "y": y,
            "liquid": liquid,
            "vapor": vapor,
            "ylabel": np.asarray([ylabel]),
            "title": np.asarray([f"{diagram_type} — {system.name} — {condition}"]),
        }
