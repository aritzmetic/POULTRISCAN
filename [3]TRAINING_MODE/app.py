# app.py

import sys
import os
import qtawesome as qta
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QLabel, QFrame, QPushButton, QScrollArea
)
from PySide6.QtGui import QPixmap, QImage, QIcon, QColor
from PySide6.QtCore import Qt, QSize, QPropertyAnimation, QEasingCurve, QAbstractAnimation

# Import the tab modules
from dashboard_tab import DashboardTab
from reports_tab import ReportsTab
from settings_tab import create_settings_tab
from about_tab import create_about_tab
from Training.training_tab import create_training_tab # <-- 1. IMPORT NEW TAB

# --- Configuration Data ---
sample_type_prefix = {
    "Chicken Breast": "BR",
    "Chicken Thigh": "TH",
    "Chicken Wing": "WG",
}

# --- Theme Palettes (Unchanged) ---
THEMES = {
    "PoultriScan Dark": {
        "BG": "#101218", "SECONDARY_BG": "#1C1E24", "PRIMARY": "#B8860B",
        "ACCENT": "#F0C419", "TEXT": "#E0E0E0", "UNSELECTED_TEXT": "#555760",
        "SUCCESS": "#4CAF50", "DANGER": "#D32F2F", "BORDER": "#2A2C33",
        "NORMAL_COLOR": "#F0C419", "PRIMARY_HOVER": "#F0C419", "DANGER_HOVER": "#FF4136",
        "SECONDARY_HOVER": "#3A3D46", "BUTTON_TEXT": "#E0E0E0", "DANGER_TEXT": "#E0E0E0",
        "SUCCESS_TEXT": "#E0E0E0"
    },
    "PoultriScan Light": {
        "BG": "#F0F2F5", "SECONDARY_BG": "#FFFFFF", "PRIMARY": "#F0C419",
        "ACCENT": "#E6B800", "TEXT": "#212121", "UNSELECTED_TEXT": "#607D8B",
        "SUCCESS": "#4CAF50",
        "DANGER": "#D32F2F",
        "BORDER": "#CFD8DC",
        "NORMAL_COLOR": "#E6B800", "PRIMARY_HOVER": "#E6B800", "DANGER_HOVER": "#EF9A9A",
        "SECONDARY_HOVER": "#E0E0E0", "BUTTON_TEXT": "#212121",
        "DANGER_TEXT": "#E0E0E0",
        "SUCCESS_TEXT": "#E0E0E0"
    }
}


GLOBAL_PALETTE = {}

def get_style_sheet(theme_name):
    """
    Generates the Qt Style Sheet (QSS) for the chosen theme.
    Now includes styles for the new sidebar navigation and menu button.
    """

    global GLOBAL_PALETTE
    palette = THEMES[theme_name]
    GLOBAL_PALETTE = palette

    # --- Font Sizes (INCREASED) ---
    base_font = "18pt 'Bahnschrift', 'Segoe UI'"         # Was 14pt
    bold_font = "bold 22pt 'Bahnschrift', 'Segoe UI'"   # Was 18pt
    subtitle_font = "bold 24pt 'Bahnschrift', 'Segoe UI'" # Was 18pt
    large_header_font = "bold 36pt 'Bahnschrift', 'Segoe UI'" # Was 30pt

    qss = f"""
        /* --- General --- */
        QMainWindow, QDialog {{ background-color: {palette["BG"]}; }}
        QWidget {{
            background-color: {palette["BG"]};
            color: {palette["TEXT"]};
            font: {base_font};
            border: none;
        }}

        /* --- Header Bar (Unchanged) --- */
        #HeaderFrame {{
            background-color: {palette["SECONDARY_BG"]};
            border-bottom: 2px solid {palette["BORDER"]};
        }}
        #HeaderTitle {{
            font: {large_header_font};
            color: {palette["ACCENT"]};
            background-color: transparent;
        }}
        #HeaderSubtitle {{
            font: {base_font};
            color: {palette["UNSELECTED_TEXT"]};
            background-color: transparent;
        }}

        /* --- Menu Toggle Button (Padding Increased) --- */
        QPushButton[objectName="menuButton"] {{
            background: transparent;
            border: none;
            padding: 15px; /* Was 10px */
            color: {palette["UNSELECTED_TEXT"]};
        }}
        QPushButton[objectName="menuButton"]:hover {{
            background-color: {palette["BORDER"]};
            color: {palette["ACCENT"]};
        }}

        /* --- Sidebar Navigation (Padding Increased) --- */
        #NavFrame {{
            background-color: {palette["SECONDARY_BG"]};
            border-right: 2px solid {palette["BORDER"]};
        }}
        QPushButton[objectName="navButton"] {{
            font: {bold_font};
            color: {palette["UNSELECTED_TEXT"]};
            background-color: transparent;
            border: none;
            padding: 25px; /* Was 20px */
            text-align: left;
        }}
        QPushButton[objectName="navButton"][collapsed="true"] {{
            text-align: center;
            padding: 25px 0; /* Was 20px */
        }}
        QPushButton[objectName="navButton"]:hover {{
            background-color: {palette["BORDER"]};
            color: {palette["ACCENT"]};
        }}
        QPushButton[objectName="navButton"][selected="true"] {{
            background-color: {palette["BG"]};
            color: {palette["ACCENT"]};
            border-left: 5px solid {palette["ACCENT"]};
        }}
        
        /* --- Cards (Unchanged) --- */
        QWidget[objectName="card"] {{
            background-color: {palette["SECONDARY_BG"]};
            border-radius: 5px;
        }}

        /* --- Labels (Unchanged) --- */
        QLabel {{
            color: {palette["TEXT"]};
            background-color: transparent;
        }}
        QLabel[objectName="dataLabel"] {{ background-color: {palette["SECONDARY_BG"]}; }}
        QLabel[objectName="subtitle"] {{
            font: {subtitle_font};
            color: {palette["ACCENT"]};
            background-color: {palette["SECONDARY_BG"]};
            padding-bottom: 5px;
            border-bottom: 1px solid {palette["BORDER"]};
        }}

        /* --- Buttons (Padding Increased) --- */
        QPushButton {{
            font: {bold_font};
            padding: 25px 35px; /* Was 18px 30px */
            background-color: {palette["PRIMARY"]};
            color: {palette["BUTTON_TEXT"]};
            border-radius: 3px;
        }}
        QPushButton:hover {{ background-color: {palette["PRIMARY_HOVER"]}; }}
        QPushButton:disabled {{ background-color: {palette["BORDER"]}; }}
        QPushButton[objectName="danger"] {{
            background-color: {palette["DANGER"]};
            color: {palette["DANGER_TEXT"]};
        }}
        QPushButton[objectName="danger"]:hover {{ background-color: {palette["DANGER_HOVER"]}; }}
        QPushButton[objectName="success"] {{
            background-color: {palette["SUCCESS"]};
            color: {palette["SUCCESS_TEXT"]};
        }}
        QPushButton[objectName="success"]:hover {{ 
            background-color: {palette["ACCENT"]}; 
        }}
        QPushButton[objectName="secondary"] {{
            background-color: {palette["SECONDARY_BG"]};
            color: {palette["UNSELECTED_TEXT"]};
            border: 1px solid {palette["BORDER"]};
        }}
        QPushButton[objectName="secondary"]:hover {{
            background-color: {palette["SECONDARY_HOVER"]};
            color: {palette["TEXT"]};
            border-color: {palette["PRIMARY"]};
        }}

        /* --- QComboBox (Padding Increased) --- */
        QComboBox {{
            background-color: {palette["SECONDARY_BG"]};
            border: 1px solid {palette["BORDER"]};
            border-radius: 3px;
            padding: 18px 20px; /* Was 12px 14px */
            color: {palette["TEXT"]};
        }}
        QComboBox:hover {{ border-color: {palette["PRIMARY"]}; }}
        QComboBox::drop-down {{ border: none; width: 25px; }} /* Was 20px */
        QComboBox::down-arrow {{ image: url(logo.png); }}
        QComboBox QAbstractItemView {{
            background-color: {palette["SECONDARY_BG"]};
            color: {palette["TEXT"]};
            selection-background-color: {palette["PRIMARY"]};
            selection-color: {palette["BUTTON_TEXT"]};
            outline: none;
            border: 1px solid {palette["PRIMARY"]};
        }}
        
        /* --- NEW: QLineEdit --- */
        QLineEdit {{
            background-color: {palette["SECONDARY_BG"]};
            border: 1px solid {palette["BORDER"]};
            border-radius: 3px;
            padding: 18px 20px; /* Match QComboBox */
            color: {palette["TEXT"]};
        }}
        QLineEdit:hover {{ 
            border-color: {palette["PRIMARY"]}; 
        }}

        /* --- QTreeWidget (Font linked, Padding Increased) --- */
        QTreeWidget, QTextEdit {{
            background-color: {palette["SECONDARY_BG"]};
            color: {palette["TEXT"]};
            font: {base_font}; /* Was 15pt */
            border: none;
            alternate-background-color: {palette["BG"]};
        }}
        QHeaderView::section {{
            background-color: {palette["BORDER"]};
            color: {palette["TEXT"]};
            font: {bold_font};
            padding: 20px; /* Was 14px */
            border: none;
        }}
        QTreeWidget::item:selected {{
            background-color: {palette["PRIMARY"]};
            color: {palette["BUTTON_TEXT"]};
        }}
        
        /* --- QScrollArea (Unchanged) --- */
        QScrollArea {{
            border: none;
            background-color: transparent;
        }}
        QScrollArea > QWidget > QWidget {{
            background-color: transparent;
        }}

        /* --- QProgressBar (Height Increased) --- */
        QProgressBar {{
            border: none;
            background-color: {palette["BORDER"]};
            text-align: center;
            height: 15px; /* Was 10px */
            border-radius: 7px; /* Was 5px */
        }}
        QProgressBar::chunk {{
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 {palette["PRIMARY"]}, stop:1 {palette["ACCENT"]});
            border-radius: 7px; /* Was 5px */
        }}
        QProgressBar[styleIdentifier="green"]::chunk {{ background-color: {palette["SUCCESS"]}; }}
        QProgressBar[styleIdentifier="orange"]::chunk {{ background-color: {palette["NORMAL_COLOR"]}; }}
        QProgressBar[styleIdentifier="red"]::chunk {{ background-color: {palette["DANGER"]}; }}

        /* --- Scrollbars (Width Increased) --- */
        QScrollBar:vertical {{
            background: {palette["BG"]}; width: 12px; margin: 0; /* Was 8px */
        }}
        QScrollBar::handle:vertical {{
            background: {palette["BORDER"]}; min-height: 20px; border-radius: 6px; /* Was 4px */
        }}
        QScrollBar::handle:vertical:hover {{ background: {palette["PRIMARY"]}; }}
        QScrollBar:horizontal {{
            background: {palette["BG"]}; height: 12px; margin: 0; /* Was 8px */
        }}
        QScrollBar::handle:horizontal {{
            background: {palette["BORDER"]}; min-width: 20px; border-radius: 6px; /* Was 4px */
        }}
        QScrollBar::handle:horizontal:hover {{ background: {palette["PRIMARY"]}; }}
    """
    return qss


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.current_theme_name = "PoultriScan Dark"
        self.reload_reports_callback = lambda: None
        
        self.nav_buttons = []
        self.nav_button_map = {}
        self.is_sidebar_expanded = True
        self.expanded_width = 420  # Was 350
        self.collapsed_width = 110 # Was 90

        self.setWindowTitle("PoultriScan | Chicken Quality Analyzer")
        self.setGeometry(100, 100, 1400, 800) 

        # --- Main Layout ---
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- FIX: Call setup_style() FIRST ---
        self.setup_style()
        # --- END FIX ---

        # 1. Header
        self.header_frame = self.create_header()
        main_layout.addWidget(self.header_frame)

        # 2. Content Area
        self.content_frame = QWidget()
        main_layout.addWidget(self.content_frame, 1)

        # --- Initial Setup ---
        self.setup_ui() 
        self.showFullScreen()


    def create_header(self):
        """Creates the top header bar."""
        header_frame = QWidget()
        header_frame.setObjectName("HeaderFrame")
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(10, 10, 30, 10)

        # --- NEW: Menu Button ---
        self.menu_button = QPushButton()
        self.menu_button.setObjectName("menuButton")
        self.menu_button.setIcon(qta.icon('fa5s.bars', color=GLOBAL_PALETTE["UNSELECTED_TEXT"]))
        self.menu_button.setIconSize(QSize(40, 40)) # Was 30, 30
        self.menu_button.clicked.connect(self.toggle_sidebar)
        header_layout.addWidget(self.menu_button)

        try:
            logo_path = "/home/pi/poultriscan-env/[2]PoultriScan-pyside/logo.png"
            if os.path.exists(logo_path):
                img = QImage(logo_path)
                logo_pixmap = QPixmap.fromImage(img).scaledToHeight(
                    80, Qt.TransformationMode.SmoothTransformation # Was 60
                )
                logo_label = QLabel()
                logo_label.setPixmap(logo_pixmap)
                logo_label.setObjectName("HeaderTitle")
                header_layout.addWidget(logo_label)
        except Exception as e:
            print(f"Error loading logo: {e}")

        title_label = QLabel(" POULTRISCAN")
        title_label.setObjectName("HeaderTitle")
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        subtitle_label = QLabel("A Non-Invasive Quality Assessment System for Broiler Chicken (Gallus gallus domesticus) Meat")
        subtitle_label.setObjectName("HeaderSubtitle")
        header_layout.addWidget(subtitle_label)
        
        return header_frame

    def setup_ui(self, initial_page=0): # <-- ADD 'initial_page=0'
        """Builds the main UI with sidebar and stacked widget."""
        
        self.is_sidebar_expanded = True 
        
        # --- START FIX ---
        # (This layout clearing code remains the same)
        if self.content_frame.layout():
            while self.content_frame.layout().count():
                child = self.content_frame.layout().takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
            QWidget().setLayout(self.content_frame.layout())
        # --- END FIX ---

        content_layout = QHBoxLayout(self.content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # 1. Create Navigation Frame
        self.nav_frame = self.create_navigation_frame()
        content_layout.addWidget(self.nav_frame)

        # 2. Create Content Stack
        self.content_stack = QStackedWidget()
        self.create_content_pages()
        content_layout.addWidget(self.content_stack, 1)
        
        # 3. Connect signals
        self.connect_signals()
        
        # 4. Set initial page
        self.switch_page(initial_page)


    def create_navigation_frame(self):
        """Creates the left-side navigation bar with buttons."""
        nav_frame = QWidget()
        nav_frame.setObjectName("NavFrame")
        nav_frame.setFixedWidth(self.expanded_width) 
        
        nav_layout = QVBoxLayout(nav_frame)
        nav_layout.setContentsMargins(0, 15, 0, 15)
        nav_layout.setSpacing(5)

        icon_color_key = "ACCENT" if "Light" in self.current_theme_name else "PRIMARY"
        icon_color = GLOBAL_PALETTE[icon_color_key]

        # --- 2. ADDED "TRAINING" TO NAV ---
        button_data = [
            ('fa5s.bolt', " Dashboard"),
            ('fa5s.file-alt', " Reports"),
            ('fa5s.cog', " Settings"),
            ('fa5s.info-circle', " About"),
            ('fa5s.clipboard-list', " Training") # <-- New Button
        ]
        
        self.nav_buttons = [] 
        self.nav_button_map = {}

        for icon_name, text in button_data:
            button = QPushButton(text)
            button.setObjectName("navButton")
            button.setIcon(qta.icon(icon_name, color=icon_color))
            button.setIconSize(QSize(35, 35)) # Was 30, 30
            nav_layout.addWidget(button)
            
            self.nav_buttons.append(button)
            self.nav_button_map[button] = text 

        nav_layout.addStretch()
        return nav_frame

    def create_content_pages(self):
        """Creates and adds all tab widgets to the QStackedWidget."""
        
        # 1. Dashboard (Index 0)
        dashboard_tab = DashboardTab(GLOBAL_PALETTE, sample_type_prefix)
        self.content_stack.addWidget(dashboard_tab)

        # 2. Reports (Index 1)
        reports_tab_widget = ReportsTab(GLOBAL_PALETTE, self)
        self.reload_reports_callback = reports_tab_widget.load_report_data
        self.content_stack.addWidget(reports_tab_widget)

        # 3. Settings (Index 2)
        settings_tab = create_settings_tab(
            self.content_stack, self, self.switch_theme, GLOBAL_PALETTE,
            THEMES, self, self.reload_reports_callback
        )
        self.content_stack.addWidget(settings_tab)

        # 4. About (Index 3)
        about_tab = create_about_tab(self.content_stack, GLOBAL_PALETTE)
        self.content_stack.addWidget(about_tab)
        
        # 5. Training (Index 4) <-- 3. ADDED NEW TAB
        training_tab = create_training_tab(self.content_stack, GLOBAL_PALETTE, self)
        self.content_stack.addWidget(training_tab)


    def connect_signals(self):
        """Connects the nav buttons to the switch_page function."""
        # --- 4. UPDATED TO 5 BUTTONS ---
        if len(self.nav_buttons) >= 5:
            self.nav_buttons[0].clicked.connect(lambda: self.switch_page(0))
            self.nav_buttons[1].clicked.connect(lambda: self.switch_page(1))
            self.nav_buttons[2].clicked.connect(lambda: self.switch_page(2))
            self.nav_buttons[3].clicked.connect(lambda: self.switch_page(3))
            self.nav_buttons[4].clicked.connect(lambda: self.switch_page(4)) # <-- New Signal

    def switch_page(self, index):
        """Switches the QStackedWidget and updates button styles."""
        self.content_stack.setCurrentIndex(index)
        
        for i, button in enumerate(self.nav_buttons):
            is_selected = (i == index)
            button.setProperty("selected", is_selected)
            button.style().unpolish(button)
            button.style().polish(button)


    def toggle_sidebar(self):
        """Expand or collapse the sidebar."""
        if self.is_sidebar_expanded:
            self.collapse_sidebar()
        else:
            self.expand_sidebar()
        self.is_sidebar_expanded = not self.is_sidebar_expanded

    # (Rest of MainWindow class is unchanged)
    def collapse_sidebar(self):
        """Animates the sidebar to its collapsed state."""
        self.animation = QPropertyAnimation(self.nav_frame, b"maximumWidth")
        self.animation.setDuration(300)
        self.animation.setStartValue(self.expanded_width)
        self.animation.setEndValue(self.collapsed_width)
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)
        
        self.animation.finished.connect(self.on_sidebar_collapsed)
        self.animation.start()

        self.animation2 = QPropertyAnimation(self.nav_frame, b"minimumWidth")
        self.animation2.setDuration(300)
        self.animation2.setStartValue(self.expanded_width)
        self.animation2.setEndValue(self.collapsed_width)
        self.animation2.setEasingCurve(QEasingCurve.InOutQuad)
        self.animation2.start()

    def on_sidebar_collapsed(self):
        """Called when collapse animation finishes."""
        for button in self.nav_buttons:
            button.setText("")
            button.setProperty("collapsed", True)
            button.style().unpolish(button)
            button.style().polish(button)

    def expand_sidebar(self):
        """Animates the sidebar to its expanded state."""
        
        for button in self.nav_buttons:
            button.setText(self.nav_button_map[button])
            button.setProperty("collapsed", False)
            button.style().unpolish(button)
            button.style().polish(button)
            
        self.animation = QPropertyAnimation(self.nav_frame, b"maximumWidth")
        self.animation.setDuration(300)
        self.animation.setStartValue(self.collapsed_width)
        self.animation.setEndValue(self.expanded_width)
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.animation.start()
        
        self.animation2 = QPropertyAnimation(self.nav_frame, b"minimumWidth")
        self.animation2.setDuration(300)
        self.animation2.setStartValue(self.collapsed_width)
        self.animation2.setEndValue(self.expanded_width)
        self.animation2.setEasingCurve(QEasingCurve.InOutQuad)
        self.animation2.start()


    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
             if self.isFullScreen():
                 self.showMaximized() 
             elif self.isMaximized():
                 self.showFullScreen()
             else:
                 self.showMaximized()


    def setup_style(self):
        qss = get_style_sheet(self.current_theme_name)
        self.setStyleSheet(qss)

    def switch_theme(self):
        current_index = self.content_stack.currentIndex() 
        self.setup_style()
        self.setup_ui(initial_page=current_index)
        


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()