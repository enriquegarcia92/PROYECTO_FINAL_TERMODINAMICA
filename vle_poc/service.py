"""Servicio termodinámico real para cálculos VLE gamma-phi."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
from scipy.optimize import brentq

from .activity import activity_coefficients
from .domain import ActivityModel, CalculationRequest, CalculationResult, CalculationType, SystemDefinition, VaporModel
from .fugacity import phi_mixture, phi_sat_pitzer, poynting_factor
from .parameter_fitter import ActivityParameterFitter
from .properties import psat_kpa, tsat_k_at_pressure
from .repository import DataRepository
from .validation import InputValidationError, validate_request


SIMULATION_WARNING = "Cálculo termodinámico real cuando existen datos completos; no se inventan parámetros faltantes."


class ThermodynamicVLEService:
    def __init__(self, repository: DataRepository) -> None:
        self.repository = repository
        self.parameter_fitter = ActivityParameterFitter()
        self._active_system: SystemDefinition | None = None
        self._parameter_warnings: tuple[str, ...] = ()

    def _system(self, request: CalculationRequest) -> SystemDefinition:
        if self._active_system is not None:
            return self._active_system
        if request.component_ids:
            return self.repository.build_system(request.component_ids)
        return self.repository.get(request.system_id)

    def _base_system(self, request: CalculationRequest) -> SystemDefinition:
        if request.component_ids:
            return self.repository.build_system(request.component_ids)
        return self.repository.get(request.system_id)

    def _system_with_fitted_parameters(
        self,
        request: CalculationRequest,
        system: SystemDefinition,
    ) -> SystemDefinition:
        component_ids = tuple(component.id for component in system.components)
        fit_data = self.repository.fit_data_for(component_ids)
        fitted = self.parameter_fitter.fit(system, request.activity_model, fit_data)
        parameters = dict(system.binary_parameters)
        parameters[request.activity_model.value] = fitted.parameters
        warnings = list(fitted.warnings)
        try:
            self.repository.persist_calculated_parameters(request.activity_model.value, fitted.parameters)
        except OSError as exc:
            warnings.append(
                "Los parámetros se calcularon en memoria, pero no se pudieron guardar en la base JSON: "
                f"{exc}"
            )
        self._parameter_warnings = tuple(warnings)
        return replace(system, binary_parameters=parameters)

    @staticmethod
    def _normalize(values: np.ndarray) -> np.ndarray:
        total = float(values.sum())
        if total <= 0 or not np.isfinite(total):
            raise InputValidationError("No se puede normalizar una composición no positiva.")
        return values / total

    def calculate(self, request: CalculationRequest) -> CalculationResult:
        system = self._base_system(request)
        request = validate_request(request, system)
        previous_system = self._active_system
        previous_warnings = self._parameter_warnings
        self._parameter_warnings = ()
        self._active_system = self._system_with_fitted_parameters(request, system)
        try:
            if request.calculation_type is CalculationType.BUBL_P:
                return self._bubl_p(request)
            if request.calculation_type is CalculationType.DEW_P:
                return self._dew_p(request)
            if request.calculation_type is CalculationType.BUBL_T:
                return self._bubl_t(request)
            if request.calculation_type is CalculationType.DEW_T:
                return self._dew_t(request)
            raise InputValidationError(f"Tipo de cálculo no soportado: {request.calculation_type.value}.")
        finally:
            self._active_system = previous_system
            self._parameter_warnings = previous_warnings

    def _gamma(self, request: CalculationRequest, x: np.ndarray, temperature_k: float) -> np.ndarray:
        system = self._system(request)
        return activity_coefficients(request.activity_model, system, temperature_k, x)

    def _correction_terms(
        self,
        request: CalculationRequest,
        temperature_k: float,
        pressure_kpa: float,
        x: np.ndarray,
        y: np.ndarray,
        psat: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        system = self._system(request)
        enabled = request.vapor_model is VaporModel.GAMMA_PHI
        phi = phi_mixture(system.components, temperature_k, pressure_kpa, y, enabled=enabled)
        phi_sat = np.array(
            [
                phi_sat_pitzer(component, temperature_k, psat_i, enabled=enabled)
                for component, psat_i in zip(system.components, psat)
            ],
            dtype=float,
        )
        poynting = np.array(
            [
                poynting_factor(component, temperature_k, pressure_kpa, psat_i, enabled=enabled)
                for component, psat_i in zip(system.components, psat)
            ],
            dtype=float,
        )
        return phi, phi_sat, poynting

    def _k_values(
        self,
        request: CalculationRequest,
        temperature_k: float,
        pressure_kpa: float,
        x_for_gamma: np.ndarray,
        y_for_phi: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        system = self._system(request)
        psat = np.array([psat_kpa(component, temperature_k) for component in system.components], dtype=float)
        gamma = self._gamma(request, x_for_gamma, temperature_k)
        phi, phi_sat, poynting = self._correction_terms(
            request, temperature_k, pressure_kpa, x_for_gamma, y_for_phi, psat
        )
        k = gamma * psat * phi_sat * poynting / (phi * pressure_kpa)
        return k, psat, gamma, phi, phi_sat, poynting

    def _bubl_at_temperature(
        self, request: CalculationRequest, temperature_k: float, pressure_guess: float | None = None
    ) -> tuple[float, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, tuple[dict[str, float], ...]]:
        system = self._system(request)
        x = np.asarray(request.composition, dtype=float)
        psat = np.array([psat_kpa(component, temperature_k) for component in system.components], dtype=float)
        gamma = self._gamma(request, x, temperature_k)
        pressure = float(np.dot(x, gamma * psat)) if pressure_guess is None else pressure_guess
        y = self._normalize(x * gamma * psat / pressure)
        history: list[dict[str, float]] = []
        phi = np.ones(len(x))
        phi_sat = np.ones(len(x))
        poynting = np.ones(len(x))
        for iteration in range(1, request.max_iterations + 1):
            phi, phi_sat, poynting = self._correction_terms(request, temperature_k, pressure, x, y, psat)
            terms = gamma * psat * phi_sat * poynting / phi
            new_pressure = float(np.dot(x, terms))
            new_y = self._normalize(x * terms / new_pressure)
            residual = abs(new_pressure - pressure) / max(new_pressure, 1.0)
            history.append({"iteration": float(iteration), "residual": residual, "value": new_pressure})
            pressure, y = new_pressure, new_y
            if residual <= request.tolerance:
                break
        k = y / x
        return pressure, y, psat, gamma, phi, phi_sat, poynting, k, tuple(history)

    def _bubl_p(self, request: CalculationRequest) -> CalculationResult:
        pressure, y, psat, gamma, phi, phi_sat, poynting, k, history = self._bubl_at_temperature(
            request, request.fixed_value
        )
        return self._result(request, request.fixed_value, pressure, np.asarray(request.composition), y, psat, gamma, phi, phi_sat, poynting, k, history)

    def _dew_at_temperature(
        self, request: CalculationRequest, temperature_k: float
    ) -> tuple[float, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, tuple[dict[str, float], ...]]:
        system = self._system(request)
        y = np.asarray(request.composition, dtype=float)
        x = y.copy()
        pressure = 101.325
        history: list[dict[str, float]] = []
        psat = np.array([psat_kpa(component, temperature_k) for component in system.components], dtype=float)
        gamma = np.ones(len(y))
        phi = np.ones(len(y))
        phi_sat = np.ones(len(y))
        poynting = np.ones(len(y))
        for iteration in range(1, request.max_iterations + 1):
            gamma = self._gamma(request, x, temperature_k)
            phi, phi_sat, poynting = self._correction_terms(request, temperature_k, pressure, x, y, psat)
            denom = gamma * psat * phi_sat * poynting / phi
            new_pressure = 1.0 / float(np.sum(y / denom))
            new_x = self._normalize(y * new_pressure / denom)
            residual = max(
                abs(new_pressure - pressure) / max(new_pressure, 1.0),
                float(np.max(np.abs(new_x - x))),
            )
            history.append({"iteration": float(iteration), "residual": residual, "value": new_pressure})
            pressure, x = new_pressure, new_x
            if residual <= request.tolerance:
                break
        k = y / x
        return pressure, x, psat, gamma, phi, phi_sat, poynting, k, tuple(history)

    def _dew_p(self, request: CalculationRequest) -> CalculationResult:
        pressure, x, psat, gamma, phi, phi_sat, poynting, k, history = self._dew_at_temperature(
            request, request.fixed_value
        )
        return self._result(request, request.fixed_value, pressure, x, np.asarray(request.composition), psat, gamma, phi, phi_sat, poynting, k, history)

    def _temperature_bounds(self, request: CalculationRequest) -> tuple[float, float]:
        system = self._system(request)
        tsats = [tsat_k_at_pressure(component, request.fixed_value) for component in system.components]
        lower = max(min(tsats) * 0.7, max(component.antoine.t_min_c + 273.15 for component in system.components if component.antoine))
        upper = min(max(tsats) * 1.3, min(component.antoine.t_max_c + 273.15 for component in system.components if component.antoine))
        if lower >= upper:
            lower = max(component.antoine.t_min_c + 273.15 for component in system.components if component.antoine)
            upper = min(component.antoine.t_max_c + 273.15 for component in system.components if component.antoine)
        return lower, upper

    def _bubl_t(self, request: CalculationRequest) -> CalculationResult:
        target_pressure = request.fixed_value
        history: list[dict[str, float]] = []

        def residual(temperature_k: float) -> float:
            pressure, *_ = self._bubl_at_temperature(request, temperature_k, target_pressure)
            value = pressure - target_pressure
            history.append({"iteration": float(len(history) + 1), "residual": abs(value), "value": temperature_k})
            return value

        lower, upper = self._temperature_bounds(request)
        temperature_k = brentq(residual, lower, upper, xtol=request.tolerance, rtol=1e-10, maxiter=request.max_iterations)
        pressure, y, psat, gamma, phi, phi_sat, poynting, k, inner_history = self._bubl_at_temperature(
            request, temperature_k, target_pressure
        )
        return self._result(
            request,
            temperature_k,
            target_pressure,
            np.asarray(request.composition),
            y,
            psat,
            gamma,
            phi,
            phi_sat,
            poynting,
            k,
            tuple(history) + inner_history,
            pressure_residual=pressure - target_pressure,
        )

    def _dew_t(self, request: CalculationRequest) -> CalculationResult:
        target_pressure = request.fixed_value
        history: list[dict[str, float]] = []

        def residual(temperature_k: float) -> float:
            pressure, *_ = self._dew_at_temperature(request, temperature_k)
            value = pressure - target_pressure
            history.append({"iteration": float(len(history) + 1), "residual": abs(value), "value": temperature_k})
            return value

        lower, upper = self._temperature_bounds(request)
        temperature_k = brentq(residual, lower, upper, xtol=request.tolerance, rtol=1e-10, maxiter=request.max_iterations)
        pressure, x, psat, gamma, phi, phi_sat, poynting, k, inner_history = self._dew_at_temperature(
            request, temperature_k
        )
        return self._result(
            request,
            temperature_k,
            target_pressure,
            x,
            np.asarray(request.composition),
            psat,
            gamma,
            phi,
            phi_sat,
            poynting,
            k,
            tuple(history) + inner_history,
            pressure_residual=pressure - target_pressure,
        )

    def _result(
        self,
        request: CalculationRequest,
        temperature_k: float,
        pressure_kpa: float,
        x: np.ndarray,
        y: np.ndarray,
        psat: np.ndarray,
        gamma: np.ndarray,
        phi: np.ndarray,
        phi_sat: np.ndarray,
        poynting: np.ndarray,
        k: np.ndarray,
        history: tuple[dict[str, float], ...],
        *,
        pressure_residual: float = 0.0,
    ) -> CalculationResult:
        system = self._system(request)
        residual = history[-1]["residual"] if history else 0.0
        sources = tuple(
            sorted(
                {
                    *(component.antoine.source for component in system.components if component.antoine is not None),
                    system.binary_parameters.get(request.activity_model.value, {}).get("source", ""),
                }
                - {""}
            )
        )
        comparison = None
        comparison_label = None
        if request.vapor_model is VaporModel.COMPARE:
            comparison = pressure_kpa if request.calculation_type.fixed_variable == "temperatura" else temperature_k
            comparison_label = (
                "Presión con phi = 1 (kPa)"
                if request.calculation_type.fixed_variable == "temperatura"
                else "Temperatura con phi = 1 (K)"
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
            iterations=len(history),
            converged=residual <= max(request.tolerance, 1e-6),
            residuals={
                "principal": float(residual),
                "presion_kpa": float(abs(pressure_residual)),
                "suma_x": float(abs(np.sum(x) - 1.0)),
                "suma_y": float(abs(np.sum(y) - 1.0)),
            },
            warnings=self._parameter_warnings,
            message="Cálculo termodinámico real completado con parámetros calculados desde datos VLE.",
            activity_model=request.activity_model.value,
            vapor_model=request.vapor_model.value,
            comparison_value=comparison,
            comparison_label=comparison_label,
            simulated=False,
            history=history,
            psat_kpa=tuple(float(value) for value in psat),
            k_values=tuple(float(value) for value in k),
            data_sources=sources,
        )
        result.assert_shape()
        return result

    def phase_curve(self, system_id: str, diagram_type: str, fixed_value: float) -> dict[str, np.ndarray]:
        system = self.repository.get(system_id)
        if len(system.components) != 2:
            raise ValueError("Los diagramas Pxy/Txy se generan solo para sistemas binarios.")
        xs = np.linspace(0.01, 0.99, 21)
        liquid_values: list[float] = []
        vapor_axis: list[float] = []
        for x1 in xs:
            composition = (float(x1), float(1.0 - x1))
            if diagram_type == "Pxy":
                request = CalculationRequest(
                    CalculationType.BUBL_P,
                    system_id,
                    ActivityModel.WILSON,
                    VaporModel.GAMMA_PHI,
                    fixed_value + 273.15,
                    composition,
                )
                result = self.calculate(request)
                liquid_values.append(result.pressure_kpa)
                vapor_axis.append(result.y[0])
            else:
                request = CalculationRequest(
                    CalculationType.BUBL_T,
                    system_id,
                    ActivityModel.WILSON,
                    VaporModel.GAMMA_PHI,
                    fixed_value,
                    composition,
                )
                result = self.calculate(request)
                liquid_values.append(result.temperature_k)
                vapor_axis.append(result.y[0])
        ylabel = "Presión (kPa)" if diagram_type == "Pxy" else "Temperatura (K)"
        condition = f"T = {fixed_value:.2f} °C" if diagram_type == "Pxy" else f"P = {fixed_value:.2f} kPa"
        return {
            "x": xs,
            "y": np.asarray(vapor_axis),
            "liquid": np.asarray(liquid_values),
            "vapor": np.asarray(liquid_values),
            "ylabel": np.asarray([ylabel]),
            "title": np.asarray([f"{diagram_type} — {system.name} — {condition}"]),
        }


MockVLEService = ThermodynamicVLEService
