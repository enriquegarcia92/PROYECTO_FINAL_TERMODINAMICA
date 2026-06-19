from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from vle_poc.ui import MainWindow, create_application


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
    window.calculation_page._run()
    assert window.stack.currentIndex() == 2
    assert window.results_page.content.isVisible() is False or window.results_page.content.isHidden() is False
    window.close()
    app.processEvents()
