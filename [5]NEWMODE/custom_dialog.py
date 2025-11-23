# custom_dialog.py

import qtawesome as qta
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QProgressBar
)
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSize
from PySide6.QtGui import QFont, QColor

class CustomDialog(QDialog):
    def __init__(self, parent, title, message, type, palette):
        super().__init__(parent)

        self.result = False

        # Color mapping (Unchanged)
        BG = palette["SECONDARY_BG"]
        TEXT = palette["TEXT"]
        PRIMARY = palette["PRIMARY"]
        color_map = {
            "info": palette["PRIMARY"],
            "warning": palette["ACCENT"],
            "success": palette["SUCCESS"],
            "error": palette["DANGER"],
            "confirm": palette["PRIMARY"],
            "processing": palette["PRIMARY"]
        }
        main_color = color_map.get(type, PRIMARY)
        main_color_hover = palette["ACCENT"]
        secondary_bg_hover = palette["SECONDARY_HOVER"]
        secondary_text_hover = palette["TEXT"]
        if type == "error":
            main_text_color = palette.get("DANGER_TEXT", palette.get("TEXT", "#FFFFFF"))
        elif type == "success":
            main_text_color = palette.get("SUCCESS_TEXT", palette.get("BUTTON_TEXT", "#101218"))
        else:
            main_text_color = palette.get("BUTTON_TEXT", palette.get("BG", "#101218"))


        # Setup Toplevel Window
        self.setWindowTitle(title)
        self.setModal(True)
        if type == "processing":
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint | Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint | Qt.WindowType.Tool)
            
        self.setMinimumWidth(350) # <-- REDUCED Was 500
        self.setStyleSheet(f"QDialog {{ background-color: {BG}; padding: 10px; }}") # <-- REDUCED Was 25px

        # Main Layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10) # <-- REDUCED Was 20

        # Content Frame
        content_frame = QWidget()
        content_layout = QVBoxLayout(content_frame)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(content_frame, 1)

        # Icon Label
        icon_map = {
            "info": "fa5s.info-circle",
            "warning": "fa5s.exclamation-triangle",
            "success": "fa5s.check-circle",
            "error": "fa5s.times-circle",
            "confirm": "fa5s.question-circle",
            "processing": "fa5s.paper-plane"
        }
        icon_name = icon_map.get(type, "fa5s.comment-dots")
        icon = qta.icon(icon_name, color=main_color)

        icon_label = QLabel()
        icon_label.setPixmap(icon.pixmap(QSize(32, 32))) # <-- REDUCED Was 55, 55
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(icon_label)

        # Message Label
        message_label = QLabel(message)
        message_label.setFont(QFont("Bahnschrift", 10)) # <-- REDUCED Was 16
        message_label.setStyleSheet(f"color: {TEXT}; background-color: transparent;")
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message_label.setWordWrap(True)
        content_layout.addWidget(message_label)

        if type == "processing":
            main_layout.addSpacing(5) # <-- REDUCED
            self.progress_bar = QProgressBar()
            self.progress_bar.setRange(0, 0) # Indeterminate
            self.progress_bar.setTextVisible(False)
            self.progress_bar.setStyleSheet(f"""
                QProgressBar {{
                    border: none;
                    background-color: {palette["BORDER"]};
                    height: 6px; /* <-- REDUCED Was 10px */
                    border-radius: 3px; /* <-- REDUCED Was 5px */
                }}
                QProgressBar::chunk {{
                    background-color: {main_color};
                    border-radius: 3px;
                }}
            """)
            content_layout.addWidget(self.progress_bar)


        main_layout.addSpacing(10) # <-- REDUCED

        # Button Frame
        button_frame = QWidget()
        button_layout = QHBoxLayout(button_frame)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.addStretch()
        main_layout.addWidget(button_frame)

        # Button Styling (REDUCED)
        button_style = f"""
            QPushButton {{
                font: bold 10pt 'Bahnschrift'; /* <-- REDUCED Was 16pt */
                background-color: {main_color};
                color: {main_text_color};
                border: none;
                border-radius: 3px;
                padding: 6px 12px; /* <-- REDUCED Was 12px 22px */
            }}
            QPushButton:hover {{
                background-color: {main_color_hover};
            }}
        """
        secondary_button_style = f"""
            QPushButton {{
                font: bold 10pt 'Bahnschrift'; /* <-- REDUCED Was 16pt */
                background-color: {palette["SECONDARY_BG"]};
                color: {palette["UNSELECTED_TEXT"]};
                border: 1px solid {palette["BORDER"]};
                border-radius: 3px;
                padding: 6px 12px; /* <-- REDUCED Was 12px 22px */
            }}
            QPushButton:hover {{
                background-color: {secondary_bg_hover};
                color: {secondary_text_hover};
                border-color: {main_color_hover};
            }}
        """

        if type == "confirm":
            self.yes_btn = QPushButton("Yes")
            self.yes_btn.setStyleSheet(button_style)
            self.yes_btn.clicked.connect(self.accept)

            self.no_btn = QPushButton("No")
            self.no_btn.setStyleSheet(secondary_button_style)
            self.no_btn.clicked.connect(self.reject)

            button_layout.addWidget(self.no_btn)
            button_layout.addWidget(self.yes_btn)

            self.yes_btn.setFocus()
            
        elif type == "processing":
            button_frame.setVisible(False)

        else:
            self.ok_btn = QPushButton("OK")
            self.ok_btn.setStyleSheet(button_style)
            self.ok_btn.clicked.connect(self.accept)
            button_layout.addWidget(self.ok_btn)
            self.ok_btn.setFocus()

    def accept(self):
        self.result = True
        super().accept()

    def reject(self):
        self.result = False
        super().reject()

    def get_result(self):
        return self.result

def show_custom_message(parent, title, message, type, palette):
    dialog = CustomDialog(parent, title, message, type, palette)
    dialog.exec()

    if type == "confirm":
        return dialog.get_result()
    else:
        return None