from __future__ import annotations

import pytest

from vle_poc.units import celsius_to_kelvin, kelvin_to_celsius


def test_celsius_to_kelvin_conversion() -> None:
    assert celsius_to_kelvin(0.0) == pytest.approx(273.15)
    assert celsius_to_kelvin(76.85) == pytest.approx(350.0)


def test_kelvin_to_celsius_conversion() -> None:
    assert kelvin_to_celsius(273.15) == pytest.approx(0.0)
