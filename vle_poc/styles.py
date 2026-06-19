"""Tema visual claro para la aplicación."""

APP_STYLE = """
QMainWindow, QWidget { background: #f4f7f8; color: #17343c; font-family: Arial; font-size: 13px; }
QLabel { background: transparent; }
QFrame#sidebar { background: #123b46; border: none; }
QLabel#brand { color: white; font-size: 20px; font-weight: 700; padding: 18px 14px; }
QLabel#subtitle { color: #a9c8ce; font-size: 11px; padding: 0 14px 16px 14px; }
QPushButton#navButton { background: transparent; color: #d7e8eb; text-align: left; border: none; border-radius: 7px; padding: 11px 14px; }
QPushButton#navButton:hover { background: #1b5260; }
QPushButton#navButton:checked { background: #1d6675; color: white; font-weight: 700; }
QLabel#pageTitle { font-size: 24px; font-weight: 700; color: #123b46; }
QLabel#pageDescription { color: #56747b; font-size: 13px; }
QLabel#warningBanner { background: #fff3cd; color: #765c00; border: 1px solid #ead38a; border-radius: 7px; padding: 9px; font-weight: 700; }
QFrame#card { background: white; border: 1px solid #d9e4e6; border-radius: 10px; }
QLabel#metricValue { font-size: 22px; font-weight: 700; color: #167467; }
QLabel#metricLabel { color: #607b81; }
QPushButton { background: #167467; color: white; border: none; border-radius: 7px; padding: 9px 14px; font-weight: 600; }
QPushButton:hover { background: #105f55; }
QPushButton:disabled { background: #9ab5b1; }
QPushButton#secondaryButton { background: white; color: #155965; border: 1px solid #9db7bc; }
QPushButton#secondaryButton:hover { background: #eaf2f3; }
QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox { background: white; border: 1px solid #b9cdd1; border-radius: 6px; padding: 7px; min-height: 20px; }
QTableWidget { background: white; alternate-background-color: #f1f6f7; border: 1px solid #d3e0e2; border-radius: 7px; gridline-color: #e4edef; }
QHeaderView::section { background: #e5eff1; color: #234b54; padding: 7px; border: none; border-bottom: 1px solid #cadbdd; font-weight: 700; }
QGroupBox { background: white; border: 1px solid #d6e2e4; border-radius: 9px; margin-top: 10px; padding: 16px 10px 10px 10px; font-weight: 700; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; }
QStatusBar { background: #e5eff1; color: #355b63; }
"""
