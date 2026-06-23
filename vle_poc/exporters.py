"""Exportadores de reportes legibles para usuario final."""

from __future__ import annotations

from datetime import datetime

from .domain import CalculationResult
from .service import SIMULATION_WARNING
from .units import kelvin_to_celsius


def format_result_txt(result: CalculationResult) -> str:
    """Construye el reporte TXT de un resultado VLE.

    El formato se mantiene deliberadamente simple para que pueda abrirse en
    Bloc de notas de Windows sin depender de Excel, Word u otra herramienta.
    """

    result.assert_shape()
    lines: list[str] = [
        "VLE Gamma-Phi - Reporte de resultados",
        "=" * 42,
        f"Fecha de exportacion: {datetime.now():%Y-%m-%d %H:%M:%S}",
        "",
        "ADVERTENCIA",
        SIMULATION_WARNING,
        "",
        "Resumen del calculo",
        "-" * 20,
        f"Tipo de calculo: {result.calculation_type}",
        f"Sistema: {result.system_name}",
        f"Modelo de actividad: {result.activity_model}",
        f"Modelo de vapor: {result.vapor_model}",
        f"Temperatura: {result.temperature_k:.6f} K",
        f"Temperatura: {kelvin_to_celsius(result.temperature_k):.6f} °C",
        f"Presion: {result.pressure_kpa:.6f} kPa",
        f"Convergencia: {'Convergio' if result.converged else 'No convergio'}",
        f"Iteraciones: {result.iterations}",
        f"Mensaje: {result.message}",
        "",
        "Tabla por componente",
        "-" * 20,
        (
            f"{'Componente':<28}"
            f"{'x':>12}"
            f"{'y':>12}"
            f"{'gamma':>12}"
            f"{'phi':>12}"
            f"{'phi_sat':>12}"
            f"{'Poynting':>12}"
        ),
    ]
    for index, name in enumerate(result.component_names):
        lines.append(
            f"{name:<28}"
            f"{result.x[index]:>12.6f}"
            f"{result.y[index]:>12.6f}"
            f"{result.gamma[index]:>12.6f}"
            f"{result.phi[index]:>12.6f}"
            f"{result.phi_sat[index]:>12.6f}"
            f"{result.poynting[index]:>12.6f}"
        )

    lines.extend(["", "Residuales finales", "-" * 20])
    if result.residuals:
        for key, value in result.residuals.items():
            lines.append(f"{key}: {value:.6e}")
    else:
        lines.append("Sin residuales reportados.")

    lines.extend(["", "Advertencias", "-" * 20])
    if result.warnings:
        lines.extend(f"- {warning}" for warning in result.warnings)
    else:
        lines.append("- Sin advertencias adicionales.")

    if result.comparison_value is not None and result.comparison_label is not None:
        target = result.pressure_kpa if "Presion" in result.comparison_label or "Presión" in result.comparison_label else result.temperature_k
        delta = 100 * (target - result.comparison_value) / target
        lines.extend(
            [
                "",
                "Comparacion gamma-phi vs phi = 1",
                "-" * 36,
                f"{result.comparison_label}: {result.comparison_value:.6f}",
                f"Diferencia relativa simulada: {delta:.6f} %",
            ]
        )

    lines.extend(
        [
            "",
            "Nota",
            "-" * 20,
            "Este archivo documenta una corrida de la POC. No contiene calculos termodinamicos reales.",
            "",
        ]
    )
    return "\n".join(lines)
