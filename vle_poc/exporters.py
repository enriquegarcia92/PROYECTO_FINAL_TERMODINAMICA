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
                f"Diferencia relativa: {delta:.6f} %",
            ]
        )

    if result.psat_kpa:
        lines.extend(["", "Presiones de saturacion", "-" * 20])
        for name, value in zip(result.component_names, result.psat_kpa):
            lines.append(f"{name}: {value:.6f} kPa")

    if result.k_values:
        lines.extend(["", "Valores K", "-" * 20])
        for name, value in zip(result.component_names, result.k_values):
            lines.append(f"{name}: {value:.6f}")

    if result.data_sources:
        lines.extend(["", "Fuentes de datos", "-" * 20])
        lines.extend(f"- {source}" for source in result.data_sources)

    if result.vle_fit_data_used:
        lines.extend(["", "Datos VLE ingresados/usados para ajuste", "-" * 40])
        lines.append(f"{'Par':<32}{'T (°C/K)':>18}{'P kPa':>12}{'x':>18}{'y':>18}{'Fuente':>24}")
        for point in result.vle_fit_data_used:
            temperature = (
                f"{float(point['temperature_c']):.6f} °C"
                if "temperature_c" in point
                else f"{float(point['temperature_k']):.6f} K"
            )
            lines.append(
                f"{str(point.get('pair_key', '')):<32}"
                f"{temperature:>18}"
                f"{float(point['pressure_kpa']):>12.6f}"
                f"{str(point['x']):>18}"
                f"{str(point['y']):>18}"
                f"{str(point.get('source', 'Usuario')):>24}"
            )

    lines.extend(
        [
            "",
            "Nota",
            "-" * 20,
            "Este archivo documenta una corrida del motor termodinamico. Revise fuentes, rangos y advertencias.",
            "",
        ]
    )
    return "\n".join(lines)
