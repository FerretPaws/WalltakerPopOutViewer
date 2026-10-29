THEMES = {
    "Dark": {
        "window": "#303030", "panel": "#3a3a3a", "viewport": "#1d1d1d",
        "field": "#1f1f1f", "button": "#4a4a4a", "button_hover": "#585858",
        "border": "#1a1a1a", "text": "#e6e6e6", "muted": "#9a9a9a",
        "accent": "#4772b3", "accent_hover": "#5a86c8", "link": "#8fb4ee",
        "ok": "#3d8f52", "error": "#a63a3a",
    },
    "Light": {
        "window": "#d9d9d9", "panel": "#e8e8e8", "viewport": "#bdbdbd",
        "field": "#ffffff", "button": "#cfcfcf", "button_hover": "#c0c0c0",
        "border": "#a8a8a8", "text": "#1a1a1a", "muted": "#5c5c5c",
        "accent": "#4772b3", "accent_hover": "#3a639f", "link": "#1f4f99",
        "ok": "#2f8a47", "error": "#b13a3a",
    },
    "Classic": {
        "window": "#152f56", "panel": "#1b3a68", "viewport": "#0e2140",
        "field": "#0e2140", "button": "#274a7c", "button_hover": "#31598f",
        "border": "#0b1a33", "text": "#ffffff", "muted": "#a9b9d3",
        "accent": "#fcb328", "accent_hover": "#fdc355", "link": "#fcb328",
        "ok": "#2f8a47", "error": "#a63a3a",
    },
}


def build_stylesheet(t):
    return f"""
    * {{ font-family: "Segoe UI", "Inter", "Helvetica Neue", sans-serif; font-size: 10pt; }}
    QMainWindow, QDockWidget, QStatusBar {{ background: {t['window']}; color: {t['text']}; }}
    QWidget {{ color: {t['text']}; }}
    QWidget#panelBody, QScrollArea, QScrollArea > QWidget > QWidget {{ background: {t['window']}; }}
    QLabel {{ background: transparent; }}
    QLabel#muted {{ color: {t['muted']}; }}
    QLabel#value {{ color: {t['muted']}; min-width: 52px; qproperty-alignment: AlignRight; }}
    QLabel#viewport {{ background: {t['viewport']}; border: 1px solid {t['border']}; border-radius: 4px; }}
    QLabel#toast {{ border-radius: 4px; padding: 8px 12px; color: #fff; }}

    QToolBar {{ background: {t['panel']}; border: none; border-bottom: 1px solid {t['border']}; spacing: 6px; padding: 4px 8px; }}
    QToolButton {{ background: transparent; border: 1px solid transparent; border-radius: 4px; padding: 5px 10px; }}
    QToolButton:hover {{ background: {t['button_hover']}; }}
    QToolButton:checked {{ background: {t['accent']}; color: #fff; }}
    QToolButton:disabled {{ color: {t['muted']}; }}
    QToolButton#sectionHeader {{ background: {t['panel']}; border: 1px solid {t['border']}; border-radius: 4px;
        padding: 6px 8px; text-align: left; font-weight: 600; }}
    QToolButton#sectionHeader:hover {{ background: {t['button_hover']}; }}
    QFrame#sectionBody {{ background: {t['panel']}; border: 1px solid {t['border']}; border-top: none;
        border-bottom-left-radius: 4px; border-bottom-right-radius: 4px; }}

    QLineEdit, QComboBox {{ background: {t['field']}; border: 1px solid {t['border']}; border-radius: 4px;
        padding: 5px 8px; selection-background-color: {t['accent']}; }}
    QLineEdit:focus, QComboBox:focus {{ border: 1px solid {t['accent']}; }}
    QComboBox::drop-down {{ border: none; width: 22px; }}
    QComboBox QAbstractItemView {{ background: {t['field']}; border: 1px solid {t['border']};
        selection-background-color: {t['accent']}; selection-color: #fff; outline: none; }}

    QPushButton {{ background: {t['button']}; border: 1px solid {t['border']}; border-radius: 4px; padding: 6px 14px; }}
    QPushButton:hover {{ background: {t['button_hover']}; }}
    QPushButton:checked, QPushButton#primary {{ background: {t['accent']}; border-color: {t['accent']}; color: #fff; }}
    QPushButton#primary:hover {{ background: {t['accent_hover']}; }}
    QPushButton:disabled {{ color: {t['muted']}; background: {t['panel']}; }}

    QCheckBox {{ spacing: 8px; }}
    QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 3px; border: 1px solid {t['border']}; background: {t['field']}; }}
    QCheckBox::indicator:checked {{ background: {t['accent']}; border-color: {t['accent']}; }}

    QSlider::groove:horizontal {{ height: 6px; background: {t['field']}; border-radius: 3px; }}
    QSlider::sub-page:horizontal {{ background: {t['accent']}; border-radius: 3px; }}
    QSlider::handle:horizontal {{ background: {t['text']}; width: 14px; margin: -5px 0; border-radius: 7px; }}

    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
    QScrollBar::handle:vertical {{ background: {t['button']}; border-radius: 5px; min-height: 24px; }}
    QScrollBar::handle:vertical:hover {{ background: {t['button_hover']}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}

    QDockWidget {{ titlebar-close-icon: none; font-weight: 600; }}
    QDockWidget::title {{ background: {t['panel']}; padding: 6px 10px; border-bottom: 1px solid {t['border']}; }}
    QStatusBar {{ background: {t['panel']}; border-top: 1px solid {t['border']}; color: {t['muted']}; }}
    QStatusBar::item {{ border: none; }}
    QMenu {{ background: {t['panel']}; border: 1px solid {t['border']}; }}
    QMenu::item:selected {{ background: {t['accent']}; color: #fff; }}
    QToolTip {{ background: {t['panel']}; color: {t['text']}; border: 1px solid {t['border']}; }}

    QDialog#themedDialog {{ background: {t['window']}; border: 1px solid {t['accent']}; }}
    QDialog#themedDialog QLabel {{ color: {t['text']}; }}
    QDialog#themedDialog QLabel#muted {{ color: {t['muted']}; }}
    QMessageBox, QInputDialog {{ background: {t['window']}; }}

    QWidget#titleBar {{ background: {t['panel']}; border-bottom: 1px solid {t['border']}; }}
    QLabel#titleText {{ font-weight: 600; padding-left: 4px; }}
    QToolButton#titleButton, QToolButton#titleClose {{
        font-family: "Segoe MDL2 Assets", "Segoe Fluent Icons"; font-size: 9pt;
        background: transparent; border: none; border-radius: 0; padding: 0; }}
    QToolButton#titleButton:hover {{ background: {t['button_hover']}; }}
    QToolButton#titleClose:hover {{ background: #c42b1c; color: #fff; }}
    """
