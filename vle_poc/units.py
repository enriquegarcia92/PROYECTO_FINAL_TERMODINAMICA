"""Conversiones de unidades compartidas por UI, CLI y reportes."""

from __future__ import annotations


KELVIN_OFFSET = 273.15


def celsius_to_kelvin(temperature_c: float) -> float:
    """Convierte grados Celsius a Kelvin."""
    return temperature_c + KELVIN_OFFSET


def kelvin_to_celsius(temperature_k: float) -> float:
    """Convierte Kelvin a grados Celsius."""
    return temperature_k - KELVIN_OFFSET
