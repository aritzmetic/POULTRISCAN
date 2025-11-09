# Training/analytics.py

import sys
import os
import csv
import statistics
from datetime import datetime
import qtawesome as qta
from collections import defaultdict

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QStackedWidget, QListWidget, QListWidgetItem,
    QCheckBox, QScrollArea, QGridLayout, QSpacerItem, QSizePolicy,
    QHeaderView, QTreeWidget, QTreeWidgetItem
)
from PySide6.QtCore import Qt, QSize, Slot
from PySide6.QtGui import QFont, QColor, QBrush

# --- Matplotlib Imports ---
# Make sure matplotlib is installed: pip install matplotlib
import matplotlib
matplotlib.use('QtAgg') # Use the Qt backend
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
# --- End Matplotlib Imports ---

# --- 1. ADD PARENT DIR TO PATH ---
# This allows us to import from the parent directory
PARENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PARENT_DIR not in sys.path:
    sys.path.append(PARENT_DIR)
# -------------------------------

# --- 2. Custom Dialog Import ---
try:
    # Try to import the custom dialog for consistent error messages
    from custom_dialog import show_custom_message
except ImportError:
    # Fallback if the import fails
    from PySide6.QtWidgets import QMessageBox
    print("Warning: Could not import custom_dialog. Using QMessageBox fallback.")
    def show_custom_message(parent, title, message, icon, palette):
        # Create a basic mapping from icon type to QMessageBox.Icon
        icon_map = {
            "info": QMessageBox.Icon.Information,
            "warning": QMessageBox.Icon.Warning,
            "error": QMessageBox.Icon.Critical,
            "success": QMessageBox.Icon.Information,
        }
        msg_box = QMessageBox(parent)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(icon_map.get(icon, QMessageBox.Icon.NoIcon))
        msg_box.exec()
# --- END Custom Dialog Import ---


# --- 3. File Definitions ---
# These paths are relative to this file's location (in the 'Training' folder)
TRAINING_ROOT_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(TRAINING_ROOT_DIR, "data")
DATA_COLLECTION_FILE = os.path.join(DATA_DIR, "data_collection.csv")
BASELINE_COLLECTION_FILE = os.path.join(DATA_DIR, "baseline_collection.csv")
RAW_BLOCK_DATA_FILE = os.path.join(DATA_DIR, "raw_block_data.csv")

# Define which CSV headers fall into which data category
MQ_HEADERS = ["final_mq137", "final_mq135", "final_mq4", "final_mq7",
              "baseline_mq137", "baseline_mq135", "baseline_mq4", "baseline_mq7",
              "MQ-137 (Ammonia)", "MQ-135 (Air Quality)", "MQ-4 (Methane)", "MQ-3 (Alcohol)"]
SPEC_HEADERS = [f"AS7265X_ch{i}" for i in range(1, 19)]
SPEC_HEADERS.extend([f"as_ref_white_ch{i}" for i in range(1, 19)])
SPEC_HEADERS.extend([f"as_ref_dark_ch{i}" for i in range(1, 19)])
TEMP_HEADERS = ["temp_c", "hum_pct", "ambient_temp", "ambient_hum"]
# --- END File Definitions ---


def _create_styled_button(text, icon_name, palette, object_name="nav_button"):
    """Helper to create a consistent navigation button."""
    btn = QPushButton(f" {text}")
    btn.setIcon(qta.icon(icon_name, color=palette['UNSELECTED_TEXT']))
    btn.setObjectName(object_name)
    btn.setCheckable(True)
    btn.setMinimumHeight(35) # <-- REDUCED
    return btn

def _load_csv_data(file_path, parent, palette):
    """Utility to read a CSV file into a list of dictionaries."""
    if not os.path.exists(file_path):
        show_custom_message(parent, "File Not Found",
                            f"The data file could not be found:\n{os.path.basename(file_path)}",
                            "error", palette)
        return None, None
    try:
        data = []
        with open(file_path, 'r', newline='') as f:
            reader = csv.reader(f)
            header = next(reader)
            # Clean header names
            header = [h.strip() for h in header]
            
            # Find the 'sample_id' column, if it exists
            sample_id_col = -1
            if "sample_id" in header:
                sample_id_col = header.index("sample_id")
                
            unique_samples = set()
            
            for row in reader:
                if not row: continue # Skip empty rows
                row_data = {h: val for h, val in zip(header, row)}
                data.append(row_data)
                if sample_id_col != -1:
                    unique_samples.add(row[sample_id_col])
                    
        if not data:
            show_custom_message(parent, "Empty File",
                                f"The data file is empty:\n{os.path.basename(file_path)}",
                                "warning", palette)
            return None, None
            
        return data, sorted(list(unique_samples))
        
    except Exception as e:
        show_custom_message(parent, "Error Reading File",
                            f"An error occurred while reading:\n{os.path.basename(file_path)}\n\nError: {e}",
                            "error", palette)
        return None, None


class MplCanvas(QWidget):
    """A custom QWidget to embed a Matplotlib figure."""
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        super().__init__(parent)
        self.figure = Figure(figsize=(width, height), dpi=dpi)
        self.canvas = FigureCanvas(self.figure)
        
        # Apply styling from palette
        self.figure.patch.set_facecolor('#1C1E24') # SECONDARY_BG
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)
        
    def clear(self):
        """Clears the figure."""
        self.figure.clear()
        
    def draw(self):
        """Redraws the canvas."""
        self.canvas.draw()
        
    def _style_axes(self, ax, title):
        """Helper to apply consistent styling to plot axes."""
        ax.set_title(title, color='#E0E0E0', fontsize=10, weight='bold') # <-- REDUCED
        ax.set_facecolor('#101218') # BG
        ax.grid(True, which='both', linestyle='--', linewidth=0.5, color='#2A2C33')
        ax.spines['top'].set_color('none')
        ax.spines['right'].set_color('none')
        ax.spines['bottom'].set_color('#888')
        ax.spines['left'].set_color('#888')
        ax.tick_params(axis='x', colors='#E0E0E0')
        ax.tick_params(axis='y', colors='#E0E0E0')
        ax.yaxis.label.set_color('#E0E0E0')
        ax.xaxis.label.set_color('#E0E0E0')
        if ax.get_legend():
             ax.get_legend().get_frame().set_facecolor('#1C1E24')
             ax.get_legend().get_frame().set_edgecolor('#2A2C33')
             for text in ax.get_legend().get_texts():
                 text.set_color('#E0E0E0')


class AnalyticsCenter(QWidget):
    """
    Main widget for the Analytics Center tab.
    It manages the different report pages and global filters.
    """
    def __init__(self, palette, parent=None):
        super().__init__(parent)
        self.palette = palette
        self.current_report_page = None # To hold the active page
        
        # --- Main Layout ---
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # --- 1. Left Navigation Panel ---
        nav_frame = QFrame()
        nav_frame.setObjectName("analytics_nav_frame")
        nav_frame.setFixedWidth(200) # <-- REDUCED
        nav_layout = QVBoxLayout(nav_frame)
        nav_layout.setContentsMargins(8, 8, 8, 8) # <-- REDUCED
        nav_layout.setSpacing(5) # <-- REDUCED
        
        title_label = QLabel("Analytics Center")
        title_label.setObjectName("title")
        nav_layout.addWidget(title_label)
        
        # Report Type Selection
        report_label = QLabel("REPORT TYPE")
        report_label.setObjectName("header")
        nav_layout.addWidget(report_label)
        
        self.btn_group_reports = []
        self.btn_baseline = _create_styled_button("Baseline Trends", "fa5s.history", palette)
        self.btn_raw_data = _create_styled_button("Raw Block Data", "fa5s.database", palette)
        self.btn_main_report = _create_styled_button("Main Report", "fa5s.file-alt", palette)
        
        self.btn_group_reports = [self.btn_baseline, self.btn_raw_data, self.btn_main_report]
        nav_layout.addWidget(self.btn_baseline)
        nav_layout.addWidget(self.btn_raw_data)
        nav_layout.addWidget(self.btn_main_report)

        nav_layout.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)) # <-- REDUCED
        
        # Data Type Selection (Global Filter)
        data_label = QLabel("DATA TO VISUALIZE")
        data_label.setObjectName("header")
        nav_layout.addWidget(data_label)
        
        self.check_mq = QCheckBox("MQ Sensor Data (e-Nose)")
        self.check_spec = QCheckBox("Spectral Data (AS7265x)")
        self.check_temp = QCheckBox("Temperature & Humidity")
        self.check_mq.setChecked(True)
        self.check_spec.setChecked(True)
        self.check_temp.setChecked(True)
        
        nav_layout.addWidget(self.check_mq)
        nav_layout.addWidget(self.check_spec)
        nav_layout.addWidget(self.check_temp)
        
        nav_layout.addStretch()
        
        # Apply button
        self.btn_apply = QPushButton(" APPLY FILTERS")
        self.btn_apply.setIcon(qta.icon('fa5s.sync-alt', color=palette.get("BUTTON_TEXT", palette["BG"])))
        self.btn_apply.setObjectName("primary") # Use styling from main app
        self.btn_apply.setMinimumHeight(35) # <-- REDUCED
        self.btn_apply.setToolTip("Apply data type filters to the current report")
        nav_layout.addWidget(self.btn_apply)
        
        main_layout.addWidget(nav_frame)
        
        # --- 2. Main Content Stack ---
        content_frame = QFrame()
        content_frame.setObjectName("analytics_content_frame")
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack)
        
        # Create pages
        self.welcome_page = self._create_welcome_page()
        self.baseline_page = BaselineReportPage(self.palette, self)
        self.raw_data_page = SampleReportPage(self.palette, RAW_BLOCK_DATA_FILE, "Raw Block Data", self)
        self.main_report_page = SampleReportPage(self.palette, DATA_COLLECTION_FILE, "Main Report Data", self)
        
        self.stack.addWidget(self.welcome_page) # index 0
        self.stack.addWidget(self.baseline_page) # index 1
        self.stack.addWidget(self.raw_data_page) # index 2
        self.stack.addWidget(self.main_report_page) # index 3
        
        main_layout.addWidget(content_frame, 1) # Add frame with stretch factor

        # --- 3. Connections ---
        self.btn_baseline.clicked.connect(lambda: self._switch_page(1, self.btn_baseline))
        self.btn_raw_data.clicked.connect(lambda: self._switch_page(2, self.btn_raw_data))
        self.btn_main_report.clicked.connect(lambda: self._switch_page(3, self.btn_main_report))
        
        self.btn_apply.clicked.connect(self.on_apply_filters)
        
        # Connect checkboxes to auto-apply
        self.check_mq.stateChanged.connect(self.on_apply_filters)
        self.check_spec.stateChanged.connect(self.on_apply_filters)
        self.check_temp.stateChanged.connect(self.on_apply_filters)

        # --- 4. Styling ---
        self.setStyleSheet(self._get_stylesheet())
        
        # Start on welcome page
        self._switch_page(0, None)

    def _create_welcome_page(self):
        """Creates the initial landing page for the analytics tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(15)
        
        icon = qta.icon('fa5s.chart-bar', color=self.palette['ACCENT'], color_active=self.palette['ACCENT'])
        icon_label = QLabel()
        icon_label.setPixmap(icon.pixmap(QSize(40, 40))) # <-- REDUCED
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)
        
        label = QLabel("Welcome to the Analytics Center")
        label.setObjectName("subtitle")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        
        info = QLabel("Select a report type from the left panel to begin.")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setObjectName("info_text")
        layout.addWidget(info)
        
        return widget

    @Slot()
    def _switch_page(self, index, clicked_button):
        """Switches the content in the QStackedWidget."""
        self.stack.setCurrentIndex(index)
        
        # Update button styles
        for btn in self.btn_group_reports:
            is_active = (btn == clicked_button)
            btn.setChecked(is_active)
            icon_color = self.palette['ACCENT'] if is_active else self.palette['UNSELECTED_TEXT']
            if btn == self.btn_baseline:
                btn.setIcon(qta.icon('fa5s.history', color=icon_color))
            elif btn == self.btn_raw_data:
                btn.setIcon(qta.icon('fa5s.database', color=icon_color))
            elif btn == self.btn_main_report:
                btn.setIcon(qta.icon('fa5s.file-alt', color=icon_color))
        
        # Store active page and apply filters
        if index > 0:
            self.current_report_page = self.stack.widget(index)
            self.on_apply_filters()
        else:
            self.current_report_page = None

    @Slot()
    def on_apply_filters(self):
        """Gathers filter states and tells the current page to update."""
        if self.current_report_page is None:
            return
            
        data_types = {
            "mq": self.check_mq.isChecked(),
            "spec": self.check_spec.isChecked(),
            "temp": self.check_temp.isChecked()
        }
        
        # Call the update_plot method (if it exists) on the active page
        if hasattr(self.current_report_page, "update_plot"):
            self.current_report_page.update_plot(data_types)
        
    def _get_stylesheet(self):
        """Generates the stylesheet for this widget."""
        return f"""
            QFrame#analytics_nav_frame {{
                background-color: {self.palette['SECONDARY_BG']};
                border-right: 1px solid {self.palette['BORDER']};
            }}
            QFrame#analytics_content_frame {{
                background-color: {self.palette['BG']};
            }}
            QLabel#header {{
                color: {self.palette['UNSELECTED_TEXT']};
                font: bold 9pt 'Bahnschrift', 'Segoe UI';
                padding-top: 5px;
                padding-bottom: 5px;
                letter-spacing: 1px;
            }}
            QLabel#info_text {{
                color: {self.palette['UNSELECTED_TEXT']};
                font-size: 10pt;
            }}
            QCheckBox {{
                font-size: 10pt;
                color: {self.palette['TEXT']};
                spacing: 10px;
                padding: 5px 0;
            }}
            QCheckBox::indicator {{
                width: 14px;
                height: 14px;
            }}
            QPushButton#nav_button {{
                background-color: transparent;
                color: {self.palette['UNSELECTED_TEXT']};
                border: 1px solid transparent;
                font: bold 10pt 'Bahnschrift', 'Segoe UI';
                padding: 8px;
                text-align: left;
                border-radius: 5px;
            }}
            QPushButton#nav_button:hover {{
                background-color: {self.palette['BORDER']};
                color: {self.palette['TEXT']};
            }}
            QPushButton#nav_button:checked {{
                background-color: {self.palette['BG']};
                color: {self.palette['ACCENT']};
                border: 1px solid {self.palette['BORDER']};
            }}
            /* Primary button style copied from main app */
            QPushButton#primary {{
                background-color: {self.palette['ACCENT']};
                color: {self.palette.get('BUTTON_TEXT', self.palette['BG'])};
                border: none;
                padding: 8px;
                font: bold 10pt 'Bahnschrift', 'Segoe UI';
                border-radius: 5px;
            }}
            QPushButton#primary:hover {{
                background-color: {self.palette.get('ACCENT_HOVER', self.palette['ACCENT'])};
            }}
            QPushButton#primary:disabled {{
                background-color: {self.palette['BORDER']};
                color: {self.palette['UNSELECTED_TEXT']};
            }}
        """


class BaselineReportPage(QWidget):
    """
    Page for displaying baseline trends over time.
    """
    def __init__(self, palette, parent=None):
        super().__init__(parent)
        self.palette = palette
        self.all_data = [] # To store loaded CSV data
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10) # <-- REDUCED
        
        # Title
        title = QLabel("Baseline Trends")
        title.setObjectName("subtitle")
        layout.addWidget(title)
        
        # Plot Canvas
        self.plot_canvas = MplCanvas(self, width=8, height=6, dpi=100)
        layout.addWidget(self.plot_canvas, 1) # Add with stretch
        
        # Initial load
        self.all_data, _ = _load_csv_data(BASELINE_COLLECTION_FILE, self, palette)

    @Slot()
    def update_plot(self, data_types):
        """Reloads data and generates the plot based on filters."""
        if not self.all_data:
            return
            
        self.plot_canvas.clear()
        
        # Prepare data for plotting
        timestamps = []
        plot_data = defaultdict(list)
        
        for row in self.all_data:
            try:
                # Try parsing ISO timestamp
                dt = datetime.fromisoformat(row.get("timestamp_iso", ""))
                timestamps.append(dt)
            except ValueError:
                # Fallback for invalid/missing timestamp
                timestamps.append(datetime.now()) # Not ideal, but won't crash
                
            for h in MQ_HEADERS:
                if h in row: plot_data[h].append(float(row[h]) if row[h] != 'NaN' else 0)
            for h in SPEC_HEADERS:
                if h in row: plot_data[h].append(float(row[h]) if row[h] != 'NaN' else 0)
            for h in TEMP_HEADERS:
                if h in row: plot_data[h].append(float(row[h]) if row[h] != 'NaN' else 0)

        # Determine how many subplots we need
        num_plots = sum(data_types.values())
        if num_plots == 0:
            ax = self.plot_canvas.figure.add_subplot(111)
            ax.text(0.5, 0.5, "No data types selected.",
                    horizontalalignment='center', verticalalignment='center',
                    transform=ax.transAxes, color=self.palette['UNSELECTED_TEXT'], fontsize=14)
            self.plot_canvas._style_axes(ax, "Baseline Report")
            self.plot_canvas.draw()
            return

        fig = self.plot_canvas.figure
        plot_index = 1
        
        # Plot MQ Data
        if data_types["mq"]:
            ax_mq = fig.add_subplot(num_plots, 1, plot_index)
            plot_index += 1
            for key in ["baseline_mq137", "baseline_mq135", "baseline_mq4", "baseline_mq7"]:
                if key in plot_data:
                    ax_mq.plot(timestamps, plot_data[key], label=key, marker='o', markersize=4, linestyle='--')
            ax_mq.legend()
            self.plot_canvas._style_axes(ax_mq, "MQ Baseline Trends (Volts)")
        
        # Plot Spec Data
        if data_types["spec"]:
            ax_spec = fig.add_subplot(num_plots, 1, plot_index)
            plot_index += 1
            # Plot just a few key channels to avoid clutter
            for key in ["as_ref_white_ch6", "as_ref_white_ch10", "as_ref_dark_ch6", "as_ref_dark_ch10"]:
                 if key in plot_data:
                    ax_spec.plot(timestamps, plot_data[key], label=key, marker='o', markersize=4, linestyle='--')
            ax_spec.legend()
            self.plot_canvas._style_axes(ax_spec, "Spectral Reference Trends (Counts)")
        
        # Plot Temp/Hum Data
        if data_types["temp"]:
            ax_temp = fig.add_subplot(num_plots, 1, plot_index)
            plot_index += 1
            if "ambient_temp" in plot_data:
                ax_temp.plot(timestamps, plot_data["ambient_temp"], label="Ambient Temp (°C)", color="#D32F2F", marker='o', markersize=4) # Use hex for DANGER
            if "ambient_hum" in plot_data:
                # Use a secondary axis for humidity
                ax_hum = ax_temp.twinx()
                ax_hum.plot(timestamps, plot_data["ambient_hum"], label="Ambient Hum (%)", color="#1976D2", marker='s', markersize=4) # Use a blue for INFO
                ax_hum.set_ylabel("Humidity (%)", color="#1976D2")
                ax_hum.tick_params(axis='y', colors="#1976D2")
                ax_hum.spines['left'].set_color("#D32F2F")
                ax_hum.spines['right'].set_color("#1976D2")
            
            self.plot_canvas._style_axes(ax_temp, "Ambient Conditions")
            ax_temp.set_ylabel("Temperature (°C)", color="#D32F2F")
            ax_temp.tick_params(axis='y', colors="#D32F2F")
            fig.legend()

        fig.tight_layout()
        self.plot_canvas.draw()


class SampleReportPage(QWidget):
    """
    Page for displaying data based on selected samples.
    Used for both Raw Data and Main Report.
    """
    def __init__(self, palette, csv_file_path, title, parent=None):
        super().__init__(parent)
        self.palette = palette
        self.csv_file_path = csv_file_path
        self.page_title = title
        self.all_data = []
        self.unique_samples = []
        
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10) # <-- REDUCED
        main_layout.setSpacing(10) # <-- REDUCED
        
        # --- Left Panel: Sample Selection ---
        left_frame = QFrame()
        left_frame.setFixedWidth(220) # <-- REDUCED
        left_frame.setObjectName("analytics_nav_frame") # Reuse style
        left_layout = QVBoxLayout(left_frame)
        
        title = QLabel(self.page_title)
        title.setObjectName("subtitle")
        left_layout.addWidget(title)
        
        filter_label = QLabel("SELECT SAMPLES")
        filter_label.setObjectName("header")
        left_layout.addWidget(filter_label)
        
        # Scroll area for sample list
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setObjectName("transparent_scroll")
        
        self.sample_list_widget = QListWidget()
        self.sample_list_widget.setStyleSheet("background-color: transparent; border: none;")
        scroll_area.setWidget(self.sample_list_widget)
        left_layout.addWidget(scroll_area, 1) # Add with stretch
        
        # Selection buttons
        select_layout = QHBoxLayout()
        self.btn_select_all = QPushButton("All")
        self.btn_select_all.setObjectName("secondary") # Style from main app
        self.btn_select_none = QPushButton("None")
        self.btn_select_none.setObjectName("secondary") # Style from main app
        select_layout.addWidget(self.btn_select_all)
        select_layout.addWidget(self.btn_select_none)
        left_layout.addLayout(select_layout)
        
        # Info Tree
        info_label = QLabel("SAMPLE INFO")
        info_label.setObjectName("header")
        left_layout.addWidget(info_label)
        self.info_tree = QTreeWidget()
        self.info_tree.setHeaderHidden(True)
        self.info_tree.setObjectName("info_tree")
        self.info_tree.setMinimumHeight(100) # <-- REDUCED
        left_layout.addWidget(self.info_tree)

        main_layout.addWidget(left_frame)
        
        # --- Right Panel: Plot ---
        right_frame = QFrame()
        right_layout = QVBoxLayout(right_frame)
        self.plot_canvas = MplCanvas(self, width=8, height=6, dpi=100)
        right_layout.addWidget(self.plot_canvas, 1) # Add with stretch
        
        main_layout.addWidget(right_frame, 1) # Add with stretch
        
        # --- Connections ---
        self.sample_list_widget.itemChanged.connect(self.on_sample_selection_changed)
        self.btn_select_all.clicked.connect(self._select_all_samples)
        self.btn_select_none.clicked.connect(self._select_none_samples)
        
        # --- Load Data ---
        self.load_data()
        
        # --- Styling ---
        self.setStyleSheet(f"""
            QFrame#analytics_nav_frame {{
                background-color: {self.palette['SECONDARY_BG']};
                border-radius: 8px;
                padding: 10px;
            }}
            QScrollArea#transparent_scroll {{
                background-color: {self.palette['BG']};
                border: 1px solid {self.palette['BORDER']};
                border-radius: 5px;
            }}
            QListWidget::item {{
                padding: 4px;
                font-size: 10pt;
                color: {self.palette['TEXT']};
            }}
            QListWidget::item:hover {{
                background-color: {self.palette['BORDER']};
            }}
            QTreeWidget#info_tree {{
                background-color: {self.palette['BG']};
                border: 1px solid {self.palette['BORDER']};
                color: {self.palette['TEXT']};
                font-size: 9pt;
            }}
        """)
    
    def load_data(self):
        """Loads the CSV and populates the sample list."""
        self.all_data, self.unique_samples = _load_csv_data(self.csv_file_path, self, self.palette)
        
        if not self.unique_samples:
            return
            
        self.sample_list_widget.clear()
        for sample_id in self.unique_samples:
            item = QListWidgetItem(sample_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.sample_list_widget.addItem(item)
            
    def _get_selected_samples(self):
        """Returns a list of sample_id strings that are checked."""
        selected = []
        for i in range(self.sample_list_widget.count()):
            item = self.sample_list_widget.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected.append(item.text())
        return selected
        
    @Slot()
    def _select_all_samples(self):
        for i in range(self.sample_list_widget.count()):
            self.sample_list_widget.item(i).setCheckState(Qt.CheckState.Checked)

    @Slot()
    def _select_none_samples(self):
        for i in range(self.sample_list_widget.count()):
            self.sample_list_widget.item(i).setCheckState(Qt.CheckState.Unchecked)

    @Slot(QListWidgetItem)
    def on_sample_selection_changed(self, item):
        """Triggers a plot update and info panel update."""
        # Update info panel
        self.info_tree.clear()
        if item.checkState() == Qt.CheckState.Checked:
            # Find first row for this sample
            sample_id = item.text()
            sample_info = next((row for row in self.all_data if row.get("sample_id") == sample_id), None)
            
            if sample_info:
                # Populate info tree
                QTreeWidgetItem(self.info_tree, ["ID: " + sample_info.get("sample_id", "N/A")])
                QTreeWidgetItem(self.info_tree, ["Meat: " + sample_info.get("meat_type", "N/A")])
                QTreeWidgetItem(self.info_tree, ["Storage: " + sample_info.get("storage_type", "N/A")])
                
                # Find all hours for this sample
                hours = sorted(list(set(
                    int(row.get("hour", 0)) for row in self.all_data if row.get("sample_id") == sample_id and row.get("hour", '0').isdigit()
                )))
                QTreeWidgetItem(self.info_tree, ["Hours: " + ", ".join(map(str, hours))])

        # Trigger plot update
        # Get parent AnalyticsCenter and call its apply function
        parent_analytics_center = self.parent().parent().parent().parent()
        parent_analytics_center.on_apply_filters()
        
    @Slot()
    def update_plot(self, data_types):
        """Generates the plot based on selected samples and data types."""
        selected_samples = self._get_selected_samples()
        self.plot_canvas.clear()
        
        if not selected_samples:
            ax = self.plot_canvas.figure.add_subplot(111)
            ax.text(0.5, 0.5, "Select one or more samples to visualize data.",
                    horizontalalignment='center', verticalalignment='center',
                    transform=ax.transAxes, color=self.palette['UNSELECTED_TEXT'], fontsize=14)
            self.plot_canvas._style_axes(ax, self.page_title)
            self.plot_canvas.draw()
            return
            
        # Filter data
        plot_data_rows = [row for row in self.all_data if row.get("sample_id") in selected_samples]
        
        # --- Plotting logic ---
        # This logic needs to be different for Raw Data vs Main Report
        
        if self.page_title == "Main Report Data":
            self._plot_main_report(plot_data_rows, data_types, selected_samples)
        else:
            self._plot_raw_data_report(plot_data_rows, data_types, selected_samples)

        self.plot_canvas.figure.tight_layout()
        self.plot_canvas.draw()
        
    def _plot_main_report(self, data_rows, data_types, selected_samples):
        """Plotting logic for Main Report (trends over hours)."""
        
        # Group data by sample_id, then by hour
        grouped_data = defaultdict(lambda: defaultdict(list))
        for row in data_rows:
            sample_id = row.get("sample_id")
            try:
                hour = int(row.get("hour", 0))
            except ValueError:
                continue
            grouped_data[sample_id][hour].append(row)
            
        # Determine number of plots
        num_plots = sum(data_types.values())
        if num_plots == 0: return # Handled by caller, but good practice
        
        fig = self.plot_canvas.figure
        plot_index = 1
        
        # Plot MQ
        if data_types["mq"]:
            ax_mq = fig.add_subplot(num_plots, 1, plot_index)
            plot_index += 1
            for sample_id in selected_samples:
                hours = sorted(grouped_data[sample_id].keys())
                # Just plot one MQ value for clarity
                mq_key = "final_mq137"
                values = []
                for h in hours:
                    # Average if multiple entries for same hour
                    vals = [float(r[mq_key]) for r in grouped_data[sample_id][h] if r.get(mq_key, 'NaN') != 'NaN']
                    values.append(statistics.mean(vals) if vals else 0)
                
                if values:
                    ax_mq.plot(hours, values, label=f"{sample_id} (MQ-137)", marker='o')
            ax_mq.set_xlabel("Hour")
            ax_mq.set_ylabel("Volts")
            ax_mq.legend()
            self.plot_canvas._style_axes(ax_mq, "MQ Sensor Trends (Final Avg)")

        # Plot Spec
        if data_types["spec"]:
            ax_spec = fig.add_subplot(num_plots, 1, plot_index)
            plot_index += 1
            for sample_id in selected_samples:
                hours = sorted(grouped_data[sample_id].keys())
                # Plot a key spectral channel
                spec_key = "AS7265X_ch10" # Example: 610nm
                values = []
                for h in hours:
                    vals = [float(r[spec_key]) for r in grouped_data[sample_id][h] if r.get(spec_key, 'NaN') != 'NaN']
                    values.append(statistics.mean(vals) if vals else 0)
                
                if values:
                    ax_spec.plot(hours, values, label=f"{sample_id} (Ch 10)", marker='o')
            ax_spec.set_xlabel("Hour")
            ax_spec.set_ylabel("Counts")
            ax_spec.legend()
            self.plot_canvas._style_axes(ax_spec, "Spectral Trends (Final Avg, 610nm)")

        # Plot Temp
        if data_types["temp"]:
            ax_temp = fig.add_subplot(num_plots, 1, plot_index)
            plot_index += 1
            for sample_id in selected_samples:
                hours = sorted(grouped_data[sample_id].keys())
                temp_key = "temp_c"
                values = []
                for h in hours:
                    vals = [float(r[temp_key]) for r in grouped_data[sample_id][h] if r.get(temp_key, 'NaN') != 'NaN']
                    values.append(statistics.mean(vals) if vals else 0)
                
                if values:
                    ax_temp.plot(hours, values, label=f"{sample_id} (Temp)", marker='o')
            ax_temp.set_xlabel("Hour")
            ax_temp.set_ylabel("Temperature (°C)")
            ax_temp.legend()
            self.plot_canvas._style_axes(ax_temp, "Temperature Trends (Final Avg)")

    def _plot_raw_data_report(self, data_rows, data_types, selected_samples):
        """Plotting logic for Raw Data (box plot of variance)."""
        
        # Group data by sample_id
        grouped_data = defaultdict(list)
        for row in data_rows:
            grouped_data[row.get("sample_id")].append(row)
            
        num_plots = sum(data_types.values())
        if num_plots == 0: return
        
        fig = self.plot_canvas.figure
        plot_index = 1
        
        # Plot MQ
        if data_types["mq"]:
            ax_mq = fig.add_subplot(num_plots, 1, plot_index)
            plot_index += 1
            mq_key = "MQ-137 (Ammonia)"
            plot_values = []
            labels = []
            for sample_id in selected_samples:
                vals = [float(r[mq_key]) for r in grouped_data[sample_id] if r.get(mq_key, 'NaN') != 'NaN']
                if vals:
                    plot_values.append(vals)
                    labels.append(sample_id)
            if plot_values:
                ax_mq.boxplot(plot_values, labels=labels)
            self.plot_canvas._style_axes(ax_mq, "MQ-137 Raw Reading Distribution")
            
        # Plot Spec
        if data_types["spec"]:
            ax_spec = fig.add_subplot(num_plots, 1, plot_index)
            plot_index += 1
            spec_key = "AS7265X_ch10"
            plot_values = []
            labels = []
            for sample_id in selected_samples:
                vals = [float(r[spec_key]) for r in grouped_data[sample_id] if r.get(spec_key, 'NaN') != 'NaN']
                if vals:
                    plot_values.append(vals)
                    labels.append(sample_id)
            if plot_values:
                ax_spec.boxplot(plot_values, labels=labels)
            self.plot_canvas._style_axes(ax_spec, "AS7265x Ch10 Raw Reading Distribution")

        # Plot Temp
        if data_types["temp"]:
            ax_temp = fig.add_subplot(num_plots, 1, plot_index)
            plot_index += 1
            temp_key = "temp_c"
            plot_values = []
            labels = []
            for sample_id in selected_samples:
                # Temp is often recorded once per block, so 'distribution' is small
                vals = [float(r[temp_key]) for r in grouped_data[sample_id] if r.get(temp_key, 'NaN') != 'NaN']
                if vals:
                    plot_values.append(vals)
                    labels.append(sample_id)
            if plot_values:
                ax_temp.boxplot(plot_values, labels=labels)
            self.plot_canvas._style_axes(ax_temp, "Temperature Raw Reading Distribution")