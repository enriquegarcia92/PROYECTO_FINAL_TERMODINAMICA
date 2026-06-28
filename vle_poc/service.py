"""Servicio termodinámico real para cálculos VLE gamma-phi."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
from scipy.optimize import brentq

from .activity import activity_coefficients
from .azeotrope import analyze_result_point, detect_binary_curve_azeotrope
from .cubic_eos import bubble_pressure_phi_phi, vapor_fugacity_result
from .domain import ActivityModel, CalculationRequest, CalculationResult, CalculationType, SystemDefinition, VaporModel
from .fugacity import phi_mixture, phi_sat_pitzer, poynting_factor
from .parameter_fitter import ActivityParameterFitter
from .properties import psat_kpa, tsat_k_at_pressure
from .repository import DataRepository
from .validation import InputValidationError, validate_request


SIMULATION_WARNING = "Cálculo termodinámico real cuando existen datos completos; no se inventan parámetros faltantes."
VLLE_1427_SYSTEM_ID = "water_n_pentane_n_heptane_1427"
VLLE_1427_WARNING = (
    "El problema 14.27 describe dos fases líquidas inmiscibles. "
    "El método físicamente recomendado es Raoult ideal para la fase hidrocarburo "
    "+ agua como fase líquida separada. Wilson se habilita solo por requerimiento "
    "del proyecto y no representa correctamente LLE/VLLE."
)
EOS_WARNING = (
    "Este sistema se resuelve con EOS cúbica phi-phi. "
    "No usa Wilson/Margules/Van Laar porque contiene gases ligeros/criogénicos."
)
EOS_MODELS = {ActivityModel.REDLICH_KWONG, ActivityModel.SOAVE_REDLICH_KWONG}
METHANE_N_BUTANE_SYSTEM_ID = "methane_n_butane_1402"
NITROGEN_METHANE_SYSTEM_ID = "nitrogen_methane_1401"


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
        if request.activity_model in EOS_MODELS:
            self._parameter_warnings = ()
            return system
        user_supplied_fit_data = bool(request.user_vle_fit_data)
        if (
            not user_supplied_fit_data
            and self._has_required_parameters(
                system, request.activity_model
            )
        ):
            self._parameter_warnings = ()
            return system
        component_ids = tuple(component.id for component in system.components)
        fit_data = request.user_vle_fit_data or self.repository.fit_data_for(component_ids)
        if not fit_data:
            raise InputValidationError(
                "Ingrese datos VLE x/y/P/T para ajustar el modelo seleccionado antes de ejecutar."
            )
        fitted = self.parameter_fitter.fit(system, request.activity_model, fit_data)
        parameters = dict(system.binary_parameters)
        parameters[request.activity_model.value] = fitted.parameters
        warnings = list(fitted.warnings)
        if user_supplied_fit_data:
            warnings.append("Parámetros ajustados desde datos VLE ingresados por usuario; no se guardaron en JSON.")
        else:
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
    def _has_required_parameters(system: SystemDefinition, model: ActivityModel) -> bool:
        parameters = system.binary_parameters.get(model.value, {})
        pairs = parameters.get("pairs", {}) if isinstance(parameters, dict) else {}
        if not isinstance(pairs, dict):
            return False
        component_ids = tuple(component.id for component in system.components)
        if model in {ActivityModel.MARGULES, ActivityModel.VAN_LAAR} and len(component_ids) != 2:
            return False
        return all(
            f"{first}|{second}" in pairs
            for first in component_ids
            for second in component_ids
            if first != second
        )

    @staticmethod
    def _normalize(values: np.ndarray) -> np.ndarray:
        total = float(values.sum())
        if total <= 0 or not np.isfinite(total):
            raise InputValidationError("No se puede normalizar una composición no positiva.")
        return values / total

    def calculate(self, request: CalculationRequest) -> CalculationResult:
        system = self._base_system(request)
        request = validate_request(request, system)
        if request.activity_model in EOS_MODELS:
            return self._eos_calculate(request, system)
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

    def _eos_calculate(self, request: CalculationRequest, system: SystemDefinition) -> CalculationResult:
        if request.activity_model is ActivityModel.SOAVE_REDLICH_KWONG:
            if request.calculation_type is not CalculationType.BUBL_P:
                raise InputValidationError("Metano/n-Butano con SRK está implementado como BUBL P a temperatura fija.")
            eos_result = bubble_pressure_phi_phi(
                system,
                request.fixed_value,
                request.composition,
                ActivityModel.SOAVE_REDLICH_KWONG,
                tolerance=request.tolerance,
                max_iterations=request.max_iterations,
            )
            x = tuple(float(value) for value in request.composition)
            residual = eos_result.residual
            sources = tuple(
                sorted(
                    {
                        "Smith, Van Ness & Abbott, Ejemplo 14.2; SRK phi-phi para metano/n-butano a 100 °F.",
                        *(system.description, system.kind),
                    }
                )
            )
            result = CalculationResult(
                calculation_type=request.calculation_type.value,
                system_name=system.name,
                component_names=tuple(component.name for component in system.components),
                temperature_k=float(request.fixed_value),
                pressure_kpa=float(eos_result.pressure_kpa),
                x=x,
                y=eos_result.y,
                gamma=tuple(1.0 for _ in system.components),
                phi=eos_result.phi_vapor,
                phi_sat=eos_result.phi_liquid,
                poynting=tuple(1.0 for _ in system.components),
                iterations=eos_result.iterations,
                converged=residual <= max(request.tolerance, 1e-6),
                residuals={
                    "sum_Kx_minus_1": float(residual),
                    "suma_x": float(abs(sum(x) - 1.0)),
                    "suma_y": float(abs(sum(eos_result.y) - 1.0)),
                    "validacion_capitulo_14_error_referencia": float("nan"),
                },
                warnings=(
                    EOS_WARNING,
                    "Validación capítulo 14: Ejemplo 14.2. Sin tabla experimental digitalizada; se reproduce el método SRK phi-phi y el diagrama P-x-y.",
                ),
                message="Cálculo EOS cúbica phi-phi completado para BUBL P.",
                activity_model=request.activity_model.value,
                vapor_model="EOS cúbica phi-phi",
                simulated=False,
                history=({"iteration": float(eos_result.iterations), "residual": float(residual), "value": float(eos_result.pressure_kpa)},),
                psat_kpa=(),
                k_values=eos_result.k_values,
                data_sources=sources,
                azeotrope_analysis={
                    "applicable": False,
                    "status": "No aplicable",
                    "message": "No aplicable: este cálculo EOS phi-phi no corresponde a un diagrama Pxy/Txy gamma-phi.",
                },
            )
            result.assert_shape()
            return result
        if request.activity_model is ActivityModel.REDLICH_KWONG:
            if request.system_id != NITROGEN_METHANE_SYSTEM_ID:
                raise InputValidationError("Redlich-Kwong está habilitado solo para Nitrógeno/Metano en esta BETA.")
            state = vapor_fugacity_result(
                system,
                request.fixed_value if request.calculation_type.fixed_variable == "temperatura" else 200.0,
                request.fixed_value if request.calculation_type.fixed_variable == "presión" else 3000.0,
                request.composition,
                ActivityModel.REDLICH_KWONG,
            )
            temperature_k = request.fixed_value if request.calculation_type.fixed_variable == "temperatura" else 200.0
            pressure_kpa = request.fixed_value if request.calculation_type.fixed_variable == "presión" else 3000.0
            z = tuple(float(value) for value in request.composition)
            result = CalculationResult(
                calculation_type="Fugacidad vapor RK",
                system_name=system.name,
                component_names=tuple(component.name for component in system.components),
                temperature_k=float(temperature_k),
                pressure_kpa=float(pressure_kpa),
                x=z,
                y=z,
                gamma=tuple(1.0 for _ in system.components),
                phi=state.phi,
                phi_sat=tuple(1.0 for _ in system.components),
                poynting=tuple(1.0 for _ in system.components),
                iterations=1,
                converged=True,
                residuals={"Z_vapor": float(state.z), "suma_y": float(abs(sum(z) - 1.0))},
                warnings=(EOS_WARNING, "Ejemplo 14.1: validación secundaria de coeficientes de fugacidad vapor, no diagrama VLE."),
                message="Cálculo Redlich-Kwong de coeficientes de fugacidad de vapor completado.",
                activity_model=request.activity_model.value,
                vapor_model="EOS cúbica phi-phi",
                simulated=False,
                history=({"iteration": 1.0, "residual": 0.0, "value": float(state.z)},),
                psat_kpa=(),
                k_values=(),
                data_sources=("Smith, Van Ness & Abbott, Ejemplo 14.1; Redlich-Kwong para N2/CH4.", system.description),
                azeotrope_analysis={
                    "applicable": False,
                    "status": "No aplicable",
                    "message": "No aplicable: este cálculo RK reporta fugacidad vapor y factor Z, no equilibrio azeotrópico Pxy/Txy.",
                },
            )
            result.assert_shape()
            return result
        raise InputValidationError(f"Modelo EOS no soportado: {request.activity_model.value}.")

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
                    *(
                        ["Parámetros ajustados desde datos VLE ingresados por usuario"]
                        if request.user_vle_fit_data
                        else []
                    ),
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
            warnings=(*self._parameter_warnings, *self._system_specific_warnings(system)),
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
            vle_fit_data_used=self._flatten_fit_data(request.user_vle_fit_data),
            azeotrope_analysis=analyze_result_point(
                CalculationResult(
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
                    residuals={},
                    warnings=(),
                    message="",
                    activity_model=request.activity_model.value,
                    vapor_model=request.vapor_model.value,
                )
            ),
        )
        result.assert_shape()
        return result

    @staticmethod
    def _flatten_fit_data(fit_data: dict[str, list[dict[str, object]]]) -> tuple[dict[str, object], ...]:
        rows: list[dict[str, object]] = []
        for pair_key, points in fit_data.items():
            for point in points:
                rows.append({"pair_key": pair_key, **dict(point)})
        return tuple(rows)

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
        data = {
            "x": xs,
            "y": np.asarray(vapor_axis),
            "liquid": np.asarray(liquid_values),
            "vapor": np.asarray(liquid_values),
            "ylabel": np.asarray([ylabel]),
            "title": np.asarray([f"{diagram_type} — {system.name} — {condition}"]),
            "diagram_type": np.asarray([diagram_type]),
            "is_cut": np.asarray([0]),
        }
        data["azeotrope_curve"] = detect_binary_curve_azeotrope(data)
        return data

    def phase_curve_for_result(self, result: CalculationResult) -> dict[str, np.ndarray]:
        component_ids = self._component_ids_from_result(result)
        if len(component_ids) < 2:
            raise InputValidationError("El diagrama requiere al menos dos componentes.")
        activity_model = ActivityModel(result.activity_model)
        if activity_model is ActivityModel.REDLICH_KWONG:
            return self._rk_fugacity_curve_for_result(result, component_ids)
        diagram_type = "Pxy" if result.calculation_type in {CalculationType.BUBL_P.value, CalculationType.DEW_P.value} else "Txy"
        fixed_value = result.temperature_k if diagram_type == "Pxy" else result.pressure_kpa
        vapor_model = VaporModel.COMPARE if activity_model in EOS_MODELS else VaporModel(result.vapor_model)
        known_composition = result.x if result.calculation_type in {CalculationType.BUBL_P.value, CalculationType.BUBL_T.value} else result.y
        main_name = result.component_names[0]
        xs = np.linspace(0.01, 0.99, 21)
        liquid_values: list[float] = []
        vapor_axis: list[float] = []
        point_x = result.x[0]
        point_y = result.y[0]
        for x1 in xs:
            composition = self._composition_for_cut(float(x1), known_composition)
            request = CalculationRequest(
                CalculationType.BUBL_P if diagram_type == "Pxy" else CalculationType.BUBL_T,
                "dynamic",
                activity_model,
                vapor_model,
                fixed_value,
                composition,
                component_ids=component_ids,
                user_vle_fit_data=self._fit_data_from_result(result),
            )
            try:
                curve_result = self.calculate(request)
            except InputValidationError:
                liquid_values.append(float("nan"))
                vapor_axis.append(float("nan"))
                continue
            liquid_values.append(curve_result.pressure_kpa if diagram_type == "Pxy" else curve_result.temperature_k)
            vapor_axis.append(curve_result.y[0])
        if diagram_type == "Pxy":
            ylabel = "Presión (kPa)"
            condition = f"T = {fixed_value - 273.15:.3f} °C"
            point_value = result.pressure_kpa
        else:
            ylabel = "Temperatura (K)"
            condition = f"P = {fixed_value:.3f} kPa"
            point_value = result.temperature_k
        cut_note = (
            ""
            if len(component_ids) == 2
            else " — Corte composicional: se mantienen proporciones relativas de los demás componentes"
        )
        data = {
            "x": xs,
            "y": np.asarray(vapor_axis),
            "liquid": np.asarray(liquid_values),
            "vapor": np.asarray(liquid_values),
            "ylabel": np.asarray([ylabel]),
            "title": np.asarray([f"{diagram_type} — {result.system_name} — {condition}{cut_note}"]),
            "xlabel": np.asarray([f"Fracción molar de {main_name}"]),
            "point_x": np.asarray([point_x]),
            "point_y": np.asarray([point_y]),
            "point_value": np.asarray([point_value]),
            "diagram_type": np.asarray([diagram_type]),
            "is_cut": np.asarray([1 if len(component_ids) > 2 else 0]),
        }
        data["azeotrope_curve"] = detect_binary_curve_azeotrope(data)
        return data

    def _rk_fugacity_curve_for_result(
        self,
        result: CalculationResult,
        component_ids: tuple[str, ...],
    ) -> dict[str, np.ndarray]:
        system = self.repository.build_system(component_ids, available_models=(ActivityModel.REDLICH_KWONG.value,))
        if len(system.components) != 2:
            raise InputValidationError("El gráfico de fugacidad RK está implementado para Nitrógeno/Metano binario.")
        y1_values = np.linspace(0.01, 0.99, 21)
        phi_first: list[float] = []
        phi_second: list[float] = []
        z_values: list[float] = []
        for y1 in y1_values:
            state = vapor_fugacity_result(
                system,
                result.temperature_k,
                result.pressure_kpa,
                (float(y1), float(1.0 - y1)),
                ActivityModel.REDLICH_KWONG,
            )
            phi_first.append(float(state.phi[0]))
            phi_second.append(float(state.phi[1]))
            z_values.append(float(state.z))
        point_y = float(result.y[0])
        data = {
            "x": y1_values,
            "phi_first": np.asarray(phi_first),
            "phi_second": np.asarray(phi_second),
            "z": np.asarray(z_values),
            "ylabel": np.asarray(["Coeficiente de fugacidad φ"]),
            "zlabel": np.asarray(["Factor de compresibilidad Z"]),
            "title": np.asarray(
                [
                    "Fugacidad RK — "
                    f"{result.system_name} — T = {result.temperature_k:.3f} K, "
                    f"P = {result.pressure_kpa:.3f} kPa"
                ]
            ),
            "xlabel": np.asarray([f"Fracción molar de {result.component_names[0]} en vapor"]),
            "point_x": np.asarray([point_y]),
            "point_phi_first": np.asarray([float(result.phi[0])]),
            "point_phi_second": np.asarray([float(result.phi[1])]),
            "point_z": np.asarray([float(result.residuals.get("Z_vapor", float("nan")))]),
            "component_first": np.asarray([result.component_names[0]]),
            "component_second": np.asarray([result.component_names[1]]),
            "diagram_type": np.asarray(["Fugacidad RK"]),
            "is_cut": np.asarray([0]),
        }
        data["azeotrope_curve"] = detect_binary_curve_azeotrope(data)
        return data

    @staticmethod
    def _composition_for_cut(x1: float, base_composition: tuple[float, ...]) -> tuple[float, ...]:
        if len(base_composition) == 2:
            return (x1, 1.0 - x1)
        remaining = 1.0 - x1
        tail = np.asarray(base_composition[1:], dtype=float)
        tail_sum = float(tail.sum())
        if tail_sum <= 0:
            weights = np.full(len(tail), 1.0 / len(tail))
        else:
            weights = tail / tail_sum
        return tuple([x1, *list((weights * remaining).astype(float))])

    @staticmethod
    def _fit_data_from_result(result: CalculationResult) -> dict[str, list[dict[str, object]]]:
        fit_data: dict[str, list[dict[str, object]]] = {}
        for row in result.vle_fit_data_used:
            pair_key = str(row.get("pair_key", "")).strip()
            if not pair_key:
                continue
            point = {key: value for key, value in row.items() if key != "pair_key"}
            fit_data.setdefault(pair_key, []).append(point)
        return fit_data

    @staticmethod
    def _system_specific_warnings(system: SystemDefinition) -> tuple[str, ...]:
        if system.id == VLLE_1427_SYSTEM_ID:
            return (VLLE_1427_WARNING,)
        return ()

    def _component_ids_from_result(self, result: CalculationResult) -> tuple[str, ...]:
        catalog = {component.name: component.id for component in self.repository.all_components()}
        ids: list[str] = []
        for name in result.component_names:
            try:
                ids.append(catalog[name])
            except KeyError as exc:
                raise InputValidationError(f"No se pudo reconstruir el sistema para graficar: {name}.") from exc
        return tuple(ids)


MockVLEService = ThermodynamicVLEService
