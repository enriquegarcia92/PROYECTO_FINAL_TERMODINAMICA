"""Validaciones reales de entrada reutilizables por cualquier interfaz."""

from __future__ import annotations

import math

from .domain import CalculationRequest, CalculationType, SystemDefinition


class InputValidationError(ValueError):
    """Error previsible que debe presentarse al usuario sin traceback."""


def validate_composition(values: tuple[float, ...], expected_size: int) -> tuple[float, ...]:
    if len(values) != expected_size:
        raise InputValidationError(
            f"Se esperaban {expected_size} fracciones molares y se recibieron {len(values)}."
        )
    if any(not math.isfinite(value) for value in values):
        raise InputValidationError("Las fracciones molares deben ser números finitos.")
    if any(value < 0 or value > 1 for value in values):
        raise InputValidationError("Cada fracción molar debe encontrarse entre 0 y 1.")
    total = sum(values)
    if total <= 0:
        raise InputValidationError("La composición no puede sumar cero.")
    deviation = abs(total - 1.0)
    if deviation > 1e-3:
        raise InputValidationError(f"Las fracciones molares deben sumar 1. Suma actual: {total:.6f}.")
    return tuple(value / total for value in values)


def validate_request(request: CalculationRequest, system: SystemDefinition) -> CalculationRequest:
    composition = validate_composition(request.composition, len(system.components))
    if request.fixed_value <= 0 or not math.isfinite(request.fixed_value):
        variable = request.calculation_type.fixed_variable.capitalize()
        raise InputValidationError(f"{variable} debe ser un número positivo y finito.")
    if request.calculation_type in {CalculationType.BUBL_P, CalculationType.DEW_P}:
        if request.fixed_value < 180 or request.fixed_value > 800:
            raise InputValidationError("La temperatura debe estar entre 180 K y 800 K para esta POC.")
    elif request.fixed_value > 10_000:
        raise InputValidationError("La presión excede el límite de 10 000 kPa de esta POC.")
    if request.activity_model.value not in system.available_models:
        raise InputValidationError(
            f"No hay parámetros {request.activity_model.value} para {system.name}."
        )
    if request.tolerance <= 0 or request.tolerance >= 0.1:
        raise InputValidationError("La tolerancia debe ser positiva y menor que 0.1.")
    if request.max_iterations < 5 or request.max_iterations > 10_000:
        raise InputValidationError("El máximo de iteraciones debe estar entre 5 y 10 000.")
    return CalculationRequest(
        calculation_type=request.calculation_type,
        system_id=request.system_id,
        activity_model=request.activity_model,
        vapor_model=request.vapor_model,
        fixed_value=request.fixed_value,
        composition=composition,
        tolerance=request.tolerance,
        max_iterations=request.max_iterations,
    )
