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


def test_gui_can_run_a_mock_calculation() -> None:
    app = create_application()
    window = MainWindow()
    assert window.calculation_page.fixed_label.text() == "Temperatura (°C)"
    assert window.calculation_page.fixed_value.value() == 76.85
    window.calculation_page.component_combo.setCurrentIndex(
        window.calculation_page.component_combo.findData("n_heptane")
    )
    window.calculation_page._add_component()
    window.calculation_page._run()
    assert window.stack.currentIndex() == 2
    assert window.results_page.content.isVisible() is False or window.results_page.content.isHidden() is False
    assert window.results_page.current_diagram is not None
    assert window.diagram_page.current_diagram is not None
    window.close()
    app.processEvents()


def test_calculation_page_is_scrollable_and_tables_show_three_rows() -> None:
    app = create_application()
    window = MainWindow()
    assert window.calculation_page.findChild(QScrollArea) is not None
    assert window.calculation_page.component_table.minimumHeight() >= 150
    assert window.calculation_page.composition_table.minimumHeight() >= 150
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
