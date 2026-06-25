"""Interfaz PySide6 completa de la POC."""

from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path

_MPL_CONFIG = Path(__file__).resolve().parents[1] / ".mplconfig"
_MPL_CONFIG.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_MPL_CONFIG))

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .domain import MAX_COMPONENTS, ActivityModel, CalculationRequest, CalculationResult, CalculationType, VaporModel
from .exporters import format_result_txt
from .repository import DataRepository
from .service import SIMULATION_WARNING, ThermodynamicVLEService
from .styles import APP_STYLE
from .units import celsius_to_kelvin, kelvin_to_celsius
from .validation import InputValidationError


def page_header(title: str, description: str) -> QVBoxLayout:
    layout = QVBoxLayout()
    title_label = QLabel(title)
    title_label.setObjectName("pageTitle")
    description_label = QLabel(description)
    description_label.setObjectName("pageDescription")
    description_label.setWordWrap(True)
    layout.addWidget(title_label)
    layout.addWidget(description_label)
    layout.addSpacing(8)
    return layout


def warning_banner() -> QLabel:
    label = QLabel(f"⚠  {SIMULATION_WARNING}")
    label.setObjectName("warningBanner")
    label.setWordWrap(True)
    return label


def card(title: str, value: str) -> QFrame:
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    label = QLabel(title)
    label.setObjectName("metricLabel")
    metric = QLabel(value)
    metric.setObjectName("metricValue")
    layout.addWidget(label)
    layout.addWidget(metric)
    frame.metric_label = metric  # type: ignore[attr-defined]
    return frame


def draw_phase_curve(figure: Figure, data: dict[str, object]) -> None:
    figure.clear()
    axes = figure.add_subplot(111)
    x_axis = data["x"]
    y_axis = data["y"]
    liquid_values = data["liquid"]
    vapor_values = data["vapor"]
    axes.plot(x_axis, liquid_values, color="#167467", linewidth=2.3, label="Líquido saturado")
    axes.plot(y_axis, vapor_values, color="#d58a35", linewidth=2.3, label="Vapor saturado")
    if "point_x" in data and "point_y" in data and "point_value" in data:
        point_x = float(data["point_x"][0])
        point_y = float(data["point_y"][0])
        point_value = float(data["point_value"][0])
        axes.scatter([point_x], [point_value], color="#0f4c5c", s=42, zorder=5, label="Punto líquido")
        axes.scatter([point_y], [point_value], color="#9a5b16", s=42, zorder=5, label="Punto vapor")
        axes.axhline(point_value, color="#6d858a", linestyle="--", linewidth=1.0, alpha=0.75)
        axes.axvline(point_x, color="#167467", linestyle=":", linewidth=1.0, alpha=0.75)
        axes.axvline(point_y, color="#d58a35", linestyle=":", linewidth=1.0, alpha=0.75)
    axes.set_xlabel(str(data.get("xlabel", ["Fracción molar del componente 1"])[0]))
    axes.set_ylabel(str(data["ylabel"][0]))
    axes.set_title(str(data["title"][0]))
    axes.set_xlim(0, 1)
    axes.grid(alpha=0.22)
    axes.legend()


class HomePage(QWidget):
    navigate = Signal(int)

    def __init__(self, repository: DataRepository) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addLayout(page_header("VLE Gamma-Phi", "Prueba de concepto para diseñar y validar la aplicación final."))
        layout.addWidget(warning_banner())
        metrics = QHBoxLayout()
        metrics.addWidget(card("Cálculos previstos", "4"))
        metrics.addWidget(card("Sistemas demo", str(len(repository.all_systems()))))
        metrics.addWidget(card("Modelos gamma", "3"))
        layout.addLayout(metrics)

        intro = QFrame()
        intro.setObjectName("card")
        intro_layout = QVBoxLayout(intro)
        heading = QLabel("Un flujo completo antes de construir el solver")
        heading.setStyleSheet("font-size: 18px; font-weight: 700;")
        body = QLabel(
            "Esta POC valida selección de sistema, composición, modelo, presentación de resultados, "
            "comparación con phi = 1 y diagramas Pxy/Txy. Los cálculos corren solo con datos documentados."
        )
        body.setWordWrap(True)
        actions = QHBoxLayout()
        calculate = QPushButton("Crear nuevo cálculo")
        calculate.clicked.connect(lambda: self.navigate.emit(1))
        diagram = QPushButton("Ver último diagrama")
        diagram.setObjectName("secondaryButton")
        diagram.clicked.connect(lambda: self.navigate.emit(3))
        actions.addWidget(calculate)
        actions.addWidget(diagram)
        actions.addStretch()
        intro_layout.addWidget(heading)
        intro_layout.addWidget(body)
        intro_layout.addLayout(actions)
        layout.addWidget(intro)
        layout.addStretch()


class CalculationPage(QWidget):
    calculated = Signal(object)

    def __init__(self, repository: DataRepository, service: ThermodynamicVLEService) -> None:
        super().__init__()
        self.repository = repository
        self.service = service
        self.selected_component_ids: list[str] = ["cyclohexane"]
        outer_layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer_layout.addWidget(scroll)
        container = QWidget()
        scroll.setWidget(container)
        layout = QVBoxLayout(container)
        layout.addLayout(page_header("Nuevo cálculo", "Configure el flujo VLE que deberá resolver el núcleo termodinámico."))
        layout.addWidget(warning_banner())

        top = QHBoxLayout()
        setup = QGroupBox("Configuración")
        setup_form = QFormLayout(setup)
        self.calculation_combo = QComboBox()
        for item in CalculationType:
            self.calculation_combo.addItem(item.value, item.name)
        self.component_combo = QComboBox()
        for component in repository.all_components():
            self.component_combo.addItem(f"{component.name} ({component.formula})", component.id)
        self.add_component_button = QPushButton("Agregar componente")
        self.add_component_button.setObjectName("secondaryButton")
        self.add_component_button.clicked.connect(self._add_component)
        self.activity_combo = QComboBox()
        for item in ActivityModel:
            self.activity_combo.addItem(item.value, item.name)
        self.vapor_combo = QComboBox()
        for item in VaporModel:
            self.vapor_combo.addItem(item.value, item.name)
        self.fixed_value = QDoubleSpinBox()
        self.fixed_value.setRange(-273.149, 10000.0)
        self.fixed_value.setDecimals(3)
        self.fixed_value.setValue(76.850)
        self.fixed_label = QLabel("Temperatura (°C)")
        setup_form.addRow("Tipo de cálculo", self.calculation_combo)
        setup_form.addRow("Modelo de actividad", self.activity_combo)
        setup_form.addRow("Fase vapor", self.vapor_combo)
        setup_form.addRow(self.fixed_label, self.fixed_value)
        setup_form.addRow("Sustancia", self.component_combo)
        setup_form.addRow(self.add_component_button)
        top.addWidget(setup, 1)

        numerical = QGroupBox("Control numérico")
        numerical_form = QFormLayout(numerical)
        self.tolerance = QDoubleSpinBox()
        self.tolerance.setDecimals(7)
        self.tolerance.setRange(0.0000001, 0.01)
        self.tolerance.setValue(0.0001)
        self.iterations = QSpinBox()
        self.iterations.setRange(5, 10000)
        self.iterations.setValue(100)
        numerical_form.addRow("Tolerancia", self.tolerance)
        numerical_form.addRow("Máximo de iteraciones", self.iterations)
        note = QLabel("Estos controles se conectarán directamente a los solvers reales.")
        note.setWordWrap(True)
        numerical_form.addRow(note)
        top.addWidget(numerical, 1)
        layout.addLayout(top)

        selected_group = QGroupBox(f"Sistema construido (máximo {MAX_COMPONENTS} sustancias)")
        selected_layout = QVBoxLayout(selected_group)
        self.component_table = QTableWidget(0, 3)
        self.component_table.setHorizontalHeaderLabels(["Sustancia", "Fórmula", "Acción"])
        self.component_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.component_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.component_table.setMinimumHeight(150)
        selected_layout.addWidget(self.component_table)
        layout.addWidget(selected_group)

        composition_group = QGroupBox("Composición conocida")
        composition_layout = QVBoxLayout(composition_group)
        self.phase_hint = QLabel()
        self.composition_table = QTableWidget(0, 3)
        self.composition_table.setHorizontalHeaderLabels(["Componente", "Fórmula", "Fracción molar"])
        self.composition_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.composition_table.setAlternatingRowColors(True)
        self.composition_table.setMinimumHeight(150)
        composition_layout.addWidget(self.phase_hint)
        composition_layout.addWidget(self.composition_table)
        layout.addWidget(composition_group)

        action_row = QHBoxLayout()
        self.total_label = QLabel()
        action_row.addWidget(self.total_label)
        action_row.addStretch()
        reset = QPushButton("Restablecer composición")
        reset.setObjectName("secondaryButton")
        reset.clicked.connect(self._populate_composition)
        run = QPushButton("Ejecutar cálculo")
        run.clicked.connect(self._run)
        action_row.addWidget(reset)
        action_row.addWidget(run)
        layout.addLayout(action_row)

        self.calculation_combo.currentIndexChanged.connect(self._update_fixed_variable)
        self.composition_table.itemChanged.connect(self._update_total)
        self._populate_component_table()
        self._populate_composition()
        self._update_fixed_variable()

    def _add_component(self) -> None:
        component_id = self.component_combo.currentData()
        if component_id in self.selected_component_ids:
            QMessageBox.warning(self, "Componente repetido", "Esa sustancia ya forma parte del sistema.")
            return
        if len(self.selected_component_ids) >= MAX_COMPONENTS:
            QMessageBox.warning(self, "Límite alcanzado", f"El máximo permitido es {MAX_COMPONENTS} sustancias.")
            return
        self.selected_component_ids.append(component_id)
        self._populate_component_table()
        self._populate_composition()

    def _remove_component(self, component_id: str) -> None:
        if component_id in self.selected_component_ids:
            self.selected_component_ids.remove(component_id)
            self._populate_component_table()
            self._populate_composition()

    def _populate_component_table(self) -> None:
        self.component_table.setRowCount(len(self.selected_component_ids))
        for row, component_id in enumerate(self.selected_component_ids):
            component = self.repository.get_component(component_id)
            name = QTableWidgetItem(component.name)
            formula = QTableWidgetItem(component.formula)
            remove = QPushButton("Quitar")
            remove.setObjectName("secondaryButton")
            remove.clicked.connect(lambda checked=False, cid=component_id: self._remove_component(cid))
            self.component_table.setItem(row, 0, name)
            self.component_table.setItem(row, 1, formula)
            self.component_table.setCellWidget(row, 2, remove)

    def _populate_composition(self) -> None:
        components = tuple(self.repository.get_component(component_id) for component_id in self.selected_component_ids)
        self.composition_table.blockSignals(True)
        self.composition_table.setRowCount(len(components))
        equal = 1.0 / len(components) if components else 0.0
        for row, component in enumerate(components):
            name = QTableWidgetItem(component.name)
            name.setFlags(name.flags() & ~Qt.ItemFlag.ItemIsEditable)
            formula = QTableWidgetItem(component.formula)
            formula.setFlags(formula.flags() & ~Qt.ItemFlag.ItemIsEditable)
            fraction = QTableWidgetItem(f"{equal:.6f}")
            fraction.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.composition_table.setItem(row, 0, name)
            self.composition_table.setItem(row, 1, formula)
            self.composition_table.setItem(row, 2, fraction)
        self.composition_table.blockSignals(False)
        self._update_total()

    def _update_fixed_variable(self) -> None:
        calculation = CalculationType[self.calculation_combo.currentData()]
        if calculation.fixed_variable == "temperatura":
            self.fixed_label.setText("Temperatura (°C)")
            self.fixed_value.setRange(-273.149, 10000.0)
            self.fixed_value.setSuffix(" °C")
            self.fixed_value.setValue(76.850)
        else:
            self.fixed_label.setText("Presión (kPa)")
            self.fixed_value.setRange(0.001, 10000.0)
            self.fixed_value.setSuffix(" kPa")
            self.fixed_value.setValue(101.325)
        self.phase_hint.setText(f"Composición conocida de la fase {calculation.known_phase}: Σ zᵢ debe ser 1.")

    def _composition(self) -> tuple[float, ...]:
        values: list[float] = []
        for row in range(self.composition_table.rowCount()):
            item = self.composition_table.item(row, 2)
            try:
                values.append(float(item.text().replace(",", ".")))
            except (AttributeError, ValueError) as exc:
                raise InputValidationError(f"La fracción molar de la fila {row + 1} no es válida.") from exc
        return tuple(values)

    def _update_total(self) -> None:
        try:
            total = sum(self._composition())
        except InputValidationError:
            self.total_label.setText("Σ zᵢ = valor inválido")
            self.total_label.setStyleSheet("color: #a23b3b; font-weight: 700;")
            return
        valid = abs(total - 1.0) <= 1e-3
        self.total_label.setText(f"Σ zᵢ = {total:.6f}")
        self.total_label.setStyleSheet(
            f"color: {'#167467' if valid else '#a23b3b'}; font-weight: 700;"
        )

    def _run(self) -> None:
        try:
            calculation_type = CalculationType[self.calculation_combo.currentData()]
            request = CalculationRequest(
                calculation_type=calculation_type,
                system_id="dynamic",
                activity_model=ActivityModel[self.activity_combo.currentData()],
                vapor_model=VaporModel[self.vapor_combo.currentData()],
                fixed_value=(
                    celsius_to_kelvin(self.fixed_value.value())
                    if calculation_type.fixed_variable == "temperatura"
                    else self.fixed_value.value()
                ),
                composition=self._composition(),
                tolerance=self.tolerance.value(),
                max_iterations=self.iterations.value(),
                component_ids=tuple(self.selected_component_ids),
            )
            self.calculated.emit(self.service.calculate(request))
        except (InputValidationError, ValueError) as exc:
            QMessageBox.warning(self, "Entrada no válida", str(exc))


class ResultsPage(QWidget):
    diagram_ready = Signal(object)

    def __init__(self, service: ThermodynamicVLEService) -> None:
        super().__init__()
        self.service = service
        self.current_result: CalculationResult | None = None
        self.current_diagram: dict[str, object] | None = None
        self.figure = Figure(figsize=(7, 4), tight_layout=True)
        self.canvas = FigureCanvasQTAgg(self.figure)
        layout = QVBoxLayout(self)
        layout.addLayout(page_header("Resultados", "Resumen uniforme preparado para los cuatro solvers VLE."))
        layout.addWidget(warning_banner())
        self.empty = QLabel("Ejecute un cálculo para visualizar los resultados.")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setStyleSheet("padding: 42px; color: #6d858a;")
        layout.addWidget(self.empty)
        self.content = QWidget()
        content_layout = QVBoxLayout(self.content)
        metrics = QHBoxLayout()
        self.temperature_card = card("Temperatura", "—")
        self.pressure_card = card("Presión", "—")
        self.iteration_card = card("Iteraciones", "—")
        self.status_card = card("Convergencia", "—")
        for widget in (self.temperature_card, self.pressure_card, self.iteration_card, self.status_card):
            metrics.addWidget(widget)
        content_layout.addLayout(metrics)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        content_layout.addWidget(self.summary)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["Componente", "x", "y", "γ", "φ", "φ sat", "Poynting"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        content_layout.addWidget(self.table)
        self.residuals = QLabel()
        self.residuals.setWordWrap(True)
        content_layout.addWidget(self.residuals)
        self.comparison = QLabel()
        self.comparison.setObjectName("warningBanner")
        self.comparison.setWordWrap(True)
        content_layout.addWidget(self.comparison)
        self.diagram_message = QLabel()
        self.diagram_message.setObjectName("warningBanner")
        self.diagram_message.setWordWrap(True)
        content_layout.addWidget(self.diagram_message)
        content_layout.addWidget(self.canvas, 1)
        actions = QHBoxLayout()
        actions.addStretch()
        self.save_txt_button = QPushButton("Guardar resultados TXT")
        self.save_txt_button.setObjectName("secondaryButton")
        self.save_txt_button.clicked.connect(self.save_txt)
        self.save_png_button = QPushButton("Guardar PNG")
        self.save_png_button.setObjectName("secondaryButton")
        self.save_png_button.clicked.connect(lambda: self.save_diagram("png"))
        self.save_pdf_button = QPushButton("Guardar PDF")
        self.save_pdf_button.setObjectName("secondaryButton")
        self.save_pdf_button.clicked.connect(lambda: self.save_diagram("pdf"))
        actions.addWidget(self.save_txt_button)
        actions.addWidget(self.save_png_button)
        actions.addWidget(self.save_pdf_button)
        content_layout.addLayout(actions)
        layout.addWidget(self.content)
        self.content.hide()
        self._draw_empty_diagram()

    def set_result(self, result: CalculationResult) -> None:
        self.current_result = result
        self.empty.hide()
        self.content.show()
        self.temperature_card.metric_label.setText(
            f"{result.temperature_k:.3f} K ({kelvin_to_celsius(result.temperature_k):.3f} °C)"
        )  # type: ignore[attr-defined]
        self.pressure_card.metric_label.setText(f"{result.pressure_kpa:.3f} kPa")  # type: ignore[attr-defined]
        self.iteration_card.metric_label.setText(str(result.iterations))  # type: ignore[attr-defined]
        self.status_card.metric_label.setText("Convergió" if result.converged else "No convergió")  # type: ignore[attr-defined]
        self.summary.setText(
            f"<b>{result.calculation_type}</b> · {result.system_name} · "
            f"{result.activity_model} · {result.vapor_model}<br>{result.message}"
        )
        self.table.setRowCount(len(result.component_names))
        vectors = (result.x, result.y, result.gamma, result.phi, result.phi_sat, result.poynting)
        for row, name in enumerate(result.component_names):
            self.table.setItem(row, 0, QTableWidgetItem(name))
            for column, vector in enumerate(vectors, start=1):
                item = QTableWidgetItem(f"{vector[row]:.6f}")
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, column, item)
        residual_text = " · ".join(f"{key}: {value:.2e}" for key, value in result.residuals.items())
        self.residuals.setText(f"<b>Residuales finales:</b> {residual_text}")
        if result.comparison_value is not None:
            target = result.pressure_kpa if "Presión" in (result.comparison_label or "") else result.temperature_k
            delta = 100 * (target - result.comparison_value) / target
            self.comparison.setText(
                f"Comparación — {result.comparison_label}: {result.comparison_value:.3f}. "
                f"Diferencia relativa: {delta:.2f} %."
            )
            self.comparison.show()
        else:
            self.comparison.hide()
        self._generate_diagram(result)

    def _draw_empty_diagram(self) -> None:
        self.figure.clear()
        axes = self.figure.add_subplot(111)
        axes.set_title("Ejecute un cálculo para generar el diagrama")
        axes.set_xlabel("Fracción molar")
        axes.set_ylabel("Variable de equilibrio")
        axes.grid(alpha=0.22)
        self.canvas.draw()

    def _generate_diagram(self, result: CalculationResult) -> None:
        try:
            self.current_diagram = self.service.phase_curve_for_result(result)
        except (InputValidationError, ValueError) as exc:
            self.current_diagram = None
            self.diagram_message.setText(f"No se pudo generar el diagrama automático: {exc}")
            self.diagram_message.show()
            self._draw_empty_diagram()
            self.diagram_ready.emit(None)
            return
        self.diagram_message.hide()
        draw_phase_curve(self.figure, self.current_diagram)
        self.canvas.draw()
        self.diagram_ready.emit(self.current_diagram)

    def save_txt(self) -> None:
        if self.current_result is None:
            QMessageBox.information(
                self,
                "Sin resultados",
                "Primero ejecute un cálculo para poder guardar el reporte TXT.",
            )
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suggested = str(Path.home() / "Documents" / f"resultados_vle_{timestamp}.txt")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar resultados TXT",
            suggested,
            "Archivo de texto (*.txt)",
        )
        if not path:
            QMessageBox.information(self, "Guardado cancelado", "No se creó ningún archivo.")
            return
        target = Path(path)
        if target.suffix.lower() != ".txt":
            target = target.with_suffix(".txt")
        try:
            target.write_text(format_result_txt(self.current_result), encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(
                self,
                "No se pudo guardar",
                f"No fue posible crear el archivo seleccionado.\n\nDetalle: {exc}",
            )
            return
        QMessageBox.information(self, "Resultados guardados", f"Archivo creado en:\n{target}")

    def save_diagram(self, extension: str) -> None:
        if self.current_diagram is None:
            QMessageBox.information(
                self,
                "Sin diagrama",
                "Primero ejecute un cálculo para generar el diagrama.",
            )
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        diagram_type = str(self.current_diagram.get("diagram_type", ["diagrama"])[0]).lower()
        suggested = str(Path.home() / "Documents" / f"diagrama_{diagram_type}_{timestamp}.{extension}")
        title = "Guardar diagrama PNG" if extension == "png" else "Guardar diagrama PDF"
        file_filter = "Imagen PNG (*.png)" if extension == "png" else "Documento PDF (*.pdf)"
        path, _ = QFileDialog.getSaveFileName(self, title, suggested, file_filter)
        if not path:
            QMessageBox.information(self, "Guardado cancelado", "No se creó ningún archivo.")
            return
        target = Path(path)
        if target.suffix.lower() != f".{extension}":
            target = target.with_suffix(f".{extension}")
        try:
            self.figure.savefig(target, dpi=180)
        except OSError as exc:
            QMessageBox.critical(
                self,
                "No se pudo guardar",
                f"No fue posible crear el archivo seleccionado.\n\nDetalle: {exc}",
            )
            return
        QMessageBox.information(self, "Diagrama guardado", f"Archivo creado en:\n{target}")


class DiagramPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.current_diagram: dict[str, object] | None = None
        self.figure = Figure(figsize=(7, 4), tight_layout=True)
        self.canvas = FigureCanvasQTAgg(self.figure)
        layout = QVBoxLayout(self)
        layout.addLayout(page_header("Diagrama del último cálculo", "El gráfico se genera automáticamente al ejecutar un cálculo."))
        layout.addWidget(warning_banner())
        controls = QHBoxLayout()
        save_png = QPushButton("Guardar PNG")
        save_png.setObjectName("secondaryButton")
        save_png.clicked.connect(lambda: self.save("png"))
        save_pdf = QPushButton("Guardar PDF")
        save_pdf.setObjectName("secondaryButton")
        save_pdf.clicked.connect(lambda: self.save("pdf"))
        controls.addStretch()
        for widget in (save_png, save_pdf):
            controls.addWidget(widget)
        layout.addLayout(controls)
        layout.addWidget(self.canvas, 1)
        self.set_diagram(None)

    def set_diagram(self, data: dict[str, object] | None) -> None:
        self.current_diagram = data
        self.figure.clear()
        axes = self.figure.add_subplot(111)
        if data is None:
            axes.set_title("Ejecute un cálculo para generar el diagrama")
            axes.set_xlabel("Fracción molar")
            axes.set_ylabel("Variable de equilibrio")
            axes.grid(alpha=0.22)
        else:
            draw_phase_curve(self.figure, data)
        self.canvas.draw()

    def save(self, extension: str) -> None:
        if self.current_diagram is None:
            QMessageBox.information(self, "Sin diagrama", "Primero ejecute un cálculo para generar el diagrama.")
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        diagram_type = str(self.current_diagram.get("diagram_type", ["diagrama"])[0]).lower()
        suggested = str(Path.home() / "Documents" / f"diagrama_{diagram_type}_{timestamp}.{extension}")
        if extension == "png":
            title = "Guardar diagrama PNG"
            file_filter = "Imagen PNG (*.png)"
        else:
            title = "Guardar diagrama PDF"
            file_filter = "Documento PDF (*.pdf)"
        path, _ = QFileDialog.getSaveFileName(self, title, suggested, file_filter)
        if not path:
            QMessageBox.information(self, "Guardado cancelado", "No se creó ningún archivo.")
            return
        target = Path(path)
        if target.suffix.lower() != f".{extension}":
            target = target.with_suffix(f".{extension}")
        try:
            self.figure.savefig(target, dpi=180)
        except OSError as exc:
            QMessageBox.critical(
                self,
                "No se pudo guardar",
                f"No fue posible crear el archivo seleccionado.\n\nDetalle: {exc}",
            )
            return
        QMessageBox.information(self, "Diagrama guardado", f"Archivo creado en:\n{target}")


class ValidationsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addLayout(page_header("Validaciones", "Matriz prevista para evidencias científicas y numéricas."))
        layout.addWidget(warning_banner())
        table = QTableWidget(4, 5)
        table.setHorizontalHeaderLabels(["Caso", "Propósito", "Estado POC", "Criterio final", "Evidencia"])
        rows = [
            ("Ciclohexano / n-Heptano", "Límite casi ideal", "Flujo disponible", "Recuperar Raoult", "Pendiente solver"),
            ("Etanol / Tolueno", "Azeótropo", "Gráfico disponible", "Extremo Pxy/Txy", "Pendiente solver"),
            ("Sistema ternario", "Multicomponente", "Tabla disponible", "≥ 3 especies", "Pendiente solver"),
            ("Capítulo 14", "Referencia", "Diseño preparado", "Error < 2 %", "Pendiente solver"),
        ]
        for row, values in enumerate(rows):
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 2:
                    item.setForeground(QBrush(QColor("#167467")))
                table.setItem(row, column, item)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(table)


class DatabasePage(QWidget):
    def __init__(self, repository: DataRepository) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addLayout(page_header("Base de datos", "Catálogo demostrativo; propiedades reales se incorporarán con fuente y rango."))
        layout.addWidget(warning_banner())
        components = [(system, component) for system in repository.all_systems() for component in system.components]
        table = QTableWidget(len(components), 7)
        table.setHorizontalHeaderLabels(["Sistema", "Componente", "Fórmula", "Tc (K)", "Pc (kPa)", "ω", "Uso"])
        for row, (system, component) in enumerate(components):
            values = (
                system.name,
                component.name,
                component.formula,
                f"{component.tc_k:.2f}",
                f"{component.pc_kpa:.2f}",
                f"{component.omega:.3f}",
                system.kind,
            )
            for column, value in enumerate(values):
                table.setItem(row, column, QTableWidgetItem(value))
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        layout.addWidget(table)


class AboutPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addLayout(page_header("Acerca del proyecto", "Alcance, arquitectura y límites de esta prueba de concepto."))
        layout.addWidget(warning_banner())
        panel = QFrame()
        panel.setObjectName("card")
        panel_layout = QVBoxLayout(panel)
        text = QLabel(
            "<h2>VLE Gamma-Phi · POC 0.1</h2>"
            "<p>Interfaz desarrollada con PySide6 y Matplotlib. El núcleo actual es un servicio "
            "termodinámico real para sistemas con datos completos documentados.</p>"
            "<p><b>Política de datos:</b> si faltan parámetros Antoine, Pitzer o binarios, "
            "el cálculo se bloquea con un mensaje claro en vez de inventar valores.</p>"
            "<p><b>Uso de IA:</b> esta estructura fue desarrollada con asistencia de OpenAI Codex. "
            "Las ecuaciones reales deberán revisarse contra las fuentes del proyecto.</p>"
        )
        text.setWordWrap(True)
        panel_layout.addWidget(text)
        layout.addWidget(panel)
        layout.addStretch()


class MainWindow(QMainWindow):
    NAVIGATION = ("Inicio", "Nuevo cálculo", "Resultados", "Diagrama", "Validaciones", "Base de datos", "Acerca de")

    def __init__(self, repository: DataRepository | None = None) -> None:
        super().__init__()
        self.repository = repository or DataRepository()
        self.service = ThermodynamicVLEService(self.repository)
        self.setWindowTitle("VLE Gamma-Phi — POC")
        self.setMinimumSize(1120, 720)
        self.resize(1320, 820)
        self.setStyleSheet(APP_STYLE)

        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self.setCentralWidget(root)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        sidebar_layout = QVBoxLayout(sidebar)
        brand = QLabel("VLE · γ/φ")
        brand.setObjectName("brand")
        subtitle = QLabel("Termodinámica química\nPrueba de concepto")
        subtitle.setObjectName("subtitle")
        sidebar_layout.addWidget(brand)
        sidebar_layout.addWidget(subtitle)
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        for index, name in enumerate(self.NAVIGATION):
            button = QPushButton(name)
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, i=index: self.navigate(i))
            self.nav_group.addButton(button, index)
            sidebar_layout.addWidget(button)
        sidebar_layout.addStretch()
        version = QLabel("POC 0.2 · MOTOR REAL")
        version.setStyleSheet("color: #9bc0c7; padding: 14px;")
        sidebar_layout.addWidget(version)
        root_layout.addWidget(sidebar)

        content_frame = QFrame()
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(26, 22, 26, 18)
        self.stack = QStackedWidget()
        self.home_page = HomePage(self.repository)
        self.calculation_page = CalculationPage(self.repository, self.service)
        self.results_page = ResultsPage(self.service)
        self.diagram_page = DiagramPage()
        pages = (
            self.home_page,
            self.calculation_page,
            self.results_page,
            self.diagram_page,
            ValidationsPage(),
            DatabasePage(self.repository),
            AboutPage(),
        )
        for page in pages:
            self.stack.addWidget(page)
        content_layout.addWidget(self.stack)
        root_layout.addWidget(content_frame, 1)

        self.home_page.navigate.connect(self.navigate)
        self.calculation_page.calculated.connect(self._show_result)
        self.results_page.diagram_ready.connect(self.diagram_page.set_diagram)
        self.nav_group.button(0).setChecked(True)
        self.statusBar().showMessage("Motor real activo · Solo calcula sistemas con datos documentados")

    def navigate(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        button = self.nav_group.button(index)
        if button:
            button.setChecked(True)

    def _show_result(self, result: CalculationResult) -> None:
        self.results_page.set_result(result)
        self.navigate(2)
        self.statusBar().showMessage(
            f"{result.calculation_type} · {result.system_name} · {result.iterations} iteraciones"
        )


def create_application() -> QApplication:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("VLE Gamma-Phi")
    app.setOrganizationName("Proyecto Termodinámica IQ")
    return app
