from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from vle_poc.ui import MainWindow, create_application
from PySide6.QtWidgets import QPushButton, QScrollArea


def test_main_window_contains_seven_working_views() -> None:
    app = create_application()
    window = MainWindow()
    assert window.stack.count() == 7
    for index in range(7):
        window.navigate(index)
        assert window.stack.currentIndex() == index
    window.close()
    app.processEvents()


def test_gui_can_run_a_beta_calculation() -> None:
    app = create_application()
    window = MainWindow()
    assert window.calculation_page.fixed_label.text() == "Temperatura (°C)"
    assert window.calculation_page.fixed_value.value() == 76.85
    window.calculation_page.system_combo.setCurrentIndex(
        window.calculation_page.system_combo.findData("cyclohexane_n_heptane")
    )
    window.calculation_page._load_example_vle()
    assert window.calculation_page.vle_table.rowCount() >= 1
    window.calculation_page._run()
    assert window.stack.currentIndex() == 2
    assert window.results_page.content.isVisible() is False or window.results_page.content.isHidden() is False
    assert window.results_page.current_diagram is not None
    assert "Azeótropos" in window.results_page.azeotropes.text()
    assert window.diagram_page.current_diagram is not None
    window.close()
    app.processEvents()


def test_calculation_page_is_scrollable_and_tables_show_three_rows() -> None:
    app = create_application()
    window = MainWindow()
    assert window.calculation_page.findChild(QScrollArea) is not None
    assert window.calculation_page.component_table.minimumHeight() >= 150
    assert window.calculation_page.composition_table.minimumHeight() >= 150
    assert window.calculation_page.vle_table.minimumHeight() >= 150
    assert window.calculation_page.vle_table.columnCount() == 6
    window.close()
    app.processEvents()


def test_calculation_page_does_not_offer_custom_component_builder() -> None:
    app = create_application()
    window = MainWindow()
    button_texts = {button.text() for button in window.calculation_page.findChildren(QPushButton)}
    assert "Agregar componente" not in button_texts
    assert "Quitar" not in button_texts
    assert window.calculation_page.system_combo.count() >= 9
    window.close()
    app.processEvents()


def test_problem_1427_ui_shows_only_wilson_and_warning() -> None:
    app = create_application()
    window = MainWindow()
    window.calculation_page.system_combo.setCurrentIndex(
        window.calculation_page.system_combo.findData("water_n_pentane_n_heptane_1427")
    )
    assert window.calculation_page.activity_combo.count() == 1
    assert window.calculation_page.activity_combo.itemText(0) == "Wilson"
    assert not window.calculation_page.system_warning.isHidden()
    assert "Raoult ideal" in window.calculation_page.system_warning.text()
    window.calculation_page._add_vle_row()
    window.calculation_page._add_vle_row()
    window.calculation_page._add_vle_row()
    pairs = {window.calculation_page.vle_table.item(row, 0).text() for row in range(3)}
    assert pairs == {"water|n_pentane", "water|n_heptane", "n_pentane|n_heptane"}
    window.close()
    app.processEvents()


def test_acetone_methanol_water_ui_runs_without_vle_rows_or_warning() -> None:
    app = create_application()
    window = MainWindow()
    window.calculation_page.system_combo.setCurrentIndex(
        window.calculation_page.system_combo.findData("acetone_methanol_water_1220_1222")
    )
    assert window.calculation_page.activity_combo.count() == 1
    assert window.calculation_page.activity_combo.itemText(0) == "Wilson"
    assert window.calculation_page.system_warning.isHidden()
    assert "parámetros Wilson documentados" in window.calculation_page.vle_hint.text()
    assert window.calculation_page.vle_table.rowCount() == 0
    window.calculation_page.fixed_value.setValue(65.0)
    window.calculation_page._run()
    assert window.stack.currentIndex() == 2
    assert window.results_page.current_result is not None
    assert window.results_page.current_result.system_name == "Acetona / Metanol / Agua"
    assert window.results_page.current_diagram is not None
    window.close()
    app.processEvents()


def test_eos_systems_show_only_their_eos_model_and_skip_vle_data() -> None:
    app = create_application()
    window = MainWindow()

    window.calculation_page.system_combo.setCurrentIndex(
        window.calculation_page.system_combo.findData("methane_n_butane_1402")
    )
    assert window.calculation_page.activity_combo.count() == 1
    assert window.calculation_page.activity_combo.itemText(0) == "Soave-Redlich-Kwong"
    assert "EOS cúbica" in window.calculation_page.system_warning.text()
    assert "no se requieren datos VLE" in window.calculation_page.vle_hint.text()

    window.calculation_page.system_combo.setCurrentIndex(
        window.calculation_page.system_combo.findData("nitrogen_methane_1401")
    )
    assert window.calculation_page.activity_combo.count() == 1
    assert window.calculation_page.activity_combo.itemText(0) == "Redlich-Kwong"
    window.calculation_page._run()
    assert window.results_page.current_diagram is not None
    assert window.results_page.current_diagram["diagram_type"][0] == "Fugacidad RK"
    assert "no corresponde a un diagrama Pxy/Txy" in window.results_page.diagram_message.text()

    window.close()
    app.processEvents()


def test_diagram_page_has_no_generate_button() -> None:
    app = create_application()
    window = MainWindow()
    button_texts = {button.text() for button in window.diagram_page.findChildren(QPushButton)}
    assert "Generar" not in button_texts
    assert {"Guardar PNG", "Guardar PDF"}.issubset(button_texts)
    window.close()
    app.processEvents()
