# dashboard_tab.py

import sys
import os
import csv
import time
import qtawesome as qta
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QFrame, QPushButton, QComboBox, QProgressBar, QScrollArea, QMainWindow, QApplication
)
from PySide6.QtCore import (
    Qt, QTimer, QThread, QObject, Signal, Slot,
    QPropertyAnimation, QEasingCurve, QAbstractAnimation, Property, QSize
)
from PySide6.QtGui import QFont, QColor

from custom_dialog import show_custom_message

report_file = "poultri_scan_report.csv"
DATABASE_LOG_FILE = "raw_database_log.csv" 
current_sample_id = None
# SPECTROMETER_PLACEHOLDER is imported from as7265x

# --- UPDATED IMPORTS ---
try:
    from Sensors.as7265x import read_all_sensors, SPECTROMETER_PLACEHOLDER
    from Sensors.data_model import calculate_group_scores, calculate_overall_quality
except ImportError as e:
    print("="*50)
    print(f"FATAL ERROR: Could not import sensor/data modules.")
    print(f"Error: {e}")
    print("The application cannot run without sensor files and 'data_model.py'.")
    print("Please ensure all sensor files (aht20.py, enose.py, as7265x.py, data_model.py) exist.")
    print("="*50)
    def show_exit_message():
        app = QApplication.instance()
        if app:
            main_window = next((w for w in app.topLevelWidgets() if isinstance(w, QMainWindow)), None)
            if main_window:
                show_custom_message(main_window, "Fatal Error", f"Failed to import sensor modules: {e}\n\nApplication will now exit.", "error", {"DANGER": "#D32F2F"})
            QTimer.singleShot(100, app.quit)
        else:
            sys.exit(1) # Fallback exit
    
    QTimer.singleShot(100, show_exit_message)
    raise SystemExit(f"Missing required sensor/data modules: {e}")
# -----------------------------


class SensorWorker(QObject):
    finished = Signal(dict)
    error = Signal(str)
    
    @Slot()
    def run_scan(self):
        try:
            raw_readings = read_all_sensors() 
            self.finished.emit(raw_readings)
        except Exception as e:
            self.error.emit(str(e))


class DashboardTab(QWidget):

    def __init__(self, palette, sample_type_prefix, parent=None):
        super().__init__(parent)

        self._score_kpi_value = 0 
        self.palette = palette
        self.sample_type_prefix = sample_type_prefix
        self.raw_label_refs = {}
        self.index_refs = {}
        self.scan_thread = None
        self.scan_worker = None
        self.scan_animation = None 
        self.streaming_timer = QTimer(self)
        self.streaming_timer.timeout.connect(self.animate_streaming_text)
        self.stream_dot_count = 0
        self.SUCCESS_COLOR = palette["SUCCESS"]
        self.DANGER_COLOR = palette["DANGER"]
        self.ACCENT_COLOR = palette["ACCENT"]
        self.PRIMARY_COLOR = palette["PRIMARY"]
        self.UNSELECTED_TEXT = palette["UNSELECTED_TEXT"]
        self.SECONDARY_BG = palette["SECONDARY_BG"]
        self.BORDER_COLOR = palette["BORDER"]
        self.TEXT_COLOR = palette["TEXT"]
        self.NORMAL_COLOR = palette["NORMAL_COLOR"] 
        self.btn_run_icon_color = self.palette.get("BUTTON_TEXT", self.palette["BG"])
        self.btn_clear_icon_color = self.palette.get("UNSELECTED_TEXT", "#555760")

        # --- Main Layout ---
        page_layout = QVBoxLayout(self) 
        page_layout.setContentsMargins(0, 0, 0, 0)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        main_layout = QGridLayout(scroll_content)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)

        # --- A. CONTROL CARD (Row 0, Span 2) ---
        control_card, control_frame = self._create_card(scroll_content, " Test Control & Status", icon_name="fa5s.gamepad")
        main_layout.addWidget(control_card, 0, 0, 1, 2)
        control_layout = QGridLayout(control_frame)
        control_layout.addWidget(QLabel("Sample Type:"), 0, 0, Qt.AlignmentFlag.AlignLeft)
        self.sample_type_combobox = QComboBox()
        self.sample_type_combobox.addItems(list(sample_type_prefix.keys()))
        self.sample_type_combobox.setFixedWidth(300) 
        control_layout.addWidget(self.sample_type_combobox, 0, 1)
        control_layout.addWidget(QLabel("Sample ID:"), 0, 2, Qt.AlignmentFlag.AlignRight)
        self.sample_id_label = QLabel("PS-INIT-0000")
        self.sample_id_label.setStyleSheet(f"font: bold 20pt 'Bahnschrift'; color: {self.ACCENT_COLOR};") 
        control_layout.addWidget(self.sample_id_label, 0, 3, Qt.AlignmentFlag.AlignLeft)
        self.status_light = QLabel()
        self.status_light.setFixedSize(25, 18) 
        self.status_light.setStyleSheet(f"background-color: {self.UNSELECTED_TEXT}; border-radius: 9px;") 
        control_layout.addWidget(self.status_light, 0, 4, Qt.AlignmentFlag.AlignLeft)
        control_layout.setColumnStretch(5, 1)
        self.btn_run = QPushButton(" RUN TEST")
        self.btn_run.setIcon(qta.icon('fa5s.play', color=self.btn_run_icon_color))
        control_layout.addWidget(self.btn_run, 0, 6)
        self.btn_clear = QPushButton(" CLEAR")
        self.btn_clear.setIcon(qta.icon('fa5s.broom', color=self.btn_clear_icon_color))
        self.btn_clear.setObjectName("secondary")
        self.btn_clear.clicked.connect(self.clear_dashboard)
        control_layout.addWidget(self.btn_clear, 0, 7)

        # --- B. MAIN CONTENT FRAME (Row 1, Span 2) ---
        main_content_frame = QWidget()
        main_content_layout = QGridLayout(main_content_frame)
        main_content_layout.setSpacing(15)
        main_layout.addWidget(main_content_frame, 1, 0, 1, 2)

        # --- B.1. SCORE AND CATEGORY FRAME ---
        score_category_frame = QWidget()
        score_category_layout = QGridLayout(score_category_frame)
        score_category_layout.setSpacing(15)
        main_content_layout.addWidget(score_category_frame, 0, 0, 1, 2)

        # 1. Overall Score Card
        self.score_border_frame, overall_frame_g = self._create_card(score_category_frame, " PoultriScan Quality Score", icon_name="fa5s.tachometer-alt")
        self.score_border_frame.setStyleSheet(f"QWidget[objectName=\"card\"] {{ border: 2px solid {self.UNSELECTED_TEXT}; }}")
        score_category_layout.addWidget(self.score_border_frame, 0, 0, 2, 1)
        overall_layout = QVBoxLayout(overall_frame_g)
        score_kpi_frame = QWidget()
        score_kpi_frame.setStyleSheet(f"background-color: {self.BORDER_COLOR}; border-radius: 5px;")
        score_kpi_layout = QVBoxLayout(score_kpi_frame)
        self.score_display = QLabel("--")
        self.score_display.setFont(QFont("Bahnschrift", 64, QFont.Weight.Bold)) 
        self.score_display.setStyleSheet(f"color: {self.UNSELECTED_TEXT}; background-color: transparent;")
        self.score_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        score_kpi_layout.addWidget(self.score_display)
        overall_layout.addWidget(score_kpi_frame)
        self.quality_label = QLabel("AWAITING SCAN")
        self.quality_label.setFont(QFont("Bahnschrift", 20, QFont.Weight.Bold)) 
        self.quality_label.setStyleSheet(f"color: {self.UNSELECTED_TEXT};")
        self.quality_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        overall_layout.addWidget(self.quality_label)
        self.progress_bar = QProgressBar()
        self.progress_bar.setProperty("styleIdentifier", "blue")
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setValue(0)
        overall_layout.addWidget(self.progress_bar)

        # 2. Group Index Cards (Rearranged into a 2x2 grid)
        self.index_refs['enose'] = self._create_index_card(score_category_frame, " eNose VOC Index", 0, 1, "fa5s.wind")
        self.index_refs['whc'] = self._create_index_card(score_category_frame, " WHC Index", 0, 2, "fa5s.water")     
        self.index_refs['fac'] = self._create_index_card(score_category_frame, " FAC Index", 1, 1, "fa5s.flask")     
        self.index_refs['myo'] = self._create_index_card(score_category_frame, " Myoglobin Index", 1, 2, "fa5s.tint") 
        
        score_category_layout.setColumnStretch(0, 2) 
        score_category_layout.setColumnStretch(1, 1) 
        score_category_layout.setColumnStretch(2, 1) 
        score_category_layout.setColumnStretch(3, 0) 


        # --- C. RAW SENSOR DATA CONTAINER ---
        raw_data_card, raw_data_container = self._create_card(main_content_frame, " Raw Sensor Readings", icon_name="fa5s.wave-square")
        main_content_layout.addWidget(raw_data_card, 1, 0, 1, 2)
        raw_data_layout = QGridLayout(raw_data_container)
        raw_data_layout.setSpacing(15)

        data_font = QFont("Bahnschrift", 16) 

        # C.1. Environmental Card
        env_card, env_frame = self._create_card(raw_data_container, " AHT20 (Environment)", icon_name="fa5s.thermometer-half")
        raw_data_layout.addWidget(env_card, 0, 0)
        env_layout = QVBoxLayout(env_frame)
        temp_label = QLabel("Temperature: -- °C")
        temp_label.setFont(data_font)
        humidity_label = QLabel("Humidity: -- % RH")
        humidity_label.setFont(data_font)
        env_layout.addWidget(temp_label)
        env_layout.addWidget(humidity_label)
        self.raw_label_refs["Temperature"] = temp_label
        self.raw_label_refs["Humidity"] = humidity_label

        # C.2. Spectrometer Card
        spec_card, spec_frame = self._create_card(raw_data_container, " AS7265X (Spectrometry)", icon_name="fa5s.palette")
        raw_data_layout.addWidget(spec_card, 0, 1)
        spec_layout = QVBoxLayout(spec_frame)
        whc_raw_label = QLabel("WHC Index: N/A")
        whc_raw_label.setFont(data_font)
        fac_raw_label = QLabel("FAC Index: N/A")
        fac_raw_label.setFont(data_font)
        myo_raw_label = QLabel("Myoglobin Index: N/A") 
        myo_raw_label.setFont(data_font) 
        spec_layout.addWidget(whc_raw_label)
        spec_layout.addWidget(fac_raw_label)
        spec_layout.addWidget(myo_raw_label) 
        self.raw_label_refs["WHC Index"] = whc_raw_label
        self.raw_label_refs["Fatty Acid Profile"] = fac_raw_label
        self.raw_label_refs["Myoglobin"] = myo_raw_label 

        # C.3. eNose Card
        enose_raw_card, enose_raw_frame = self._create_card(raw_data_container, " eNose (VOCs)", icon_name="fa5s.cloud")
        raw_data_layout.addWidget(enose_raw_card, 0, 2)
        enose_layout = QGridLayout(enose_raw_frame)
        mq_sensors_data = [
            ("MQ-137 (Ammonia)", "NH₃ (Ammonia): N/A V"),
            ("MQ-135 (Air Quality)", "Air Quality: N/A V"),
            ("MQ-7 (CO)", "CO: N/A V"),
            ("MQ-4 (Methane)", "CH₄: N/A V"),
        ]
        for i, (key, initial_text) in enumerate(mq_sensors_data):
            label = QLabel(initial_text)
            label.setFont(data_font) 
            enose_layout.addWidget(label, i // 2, i % 2)
            self.raw_label_refs[key] = label

        main_layout.setRowStretch(1, 1)
        scroll_area.setWidget(scroll_content)
        page_layout.addWidget(scroll_area)
        self.btn_run.clicked.connect(self.run_test)
        self.clear_dashboard()

    def get_score_kpi_value(self):
        return self._score_kpi_value
    def set_score_kpi_value(self, value):
        self._score_kpi_value = value
        self.score_display.setText(str(int(value)))
    score_kpi_value = Property(float, get_score_kpi_value, set_score_kpi_value)

    def _create_card(self, parent, title, icon_name=None):
        card_frame = QWidget(parent)
        card_frame.setObjectName("card")
        card_layout = QVBoxLayout(card_frame)
        card_layout.setContentsMargins(15, 15, 15, 15)
        title_frame = QWidget()
        title_layout = QHBoxLayout(title_frame)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(10)
        if icon_name:
            icon = qta.icon(icon_name, color=self.palette["ACCENT"])
            icon_label = QLabel()
            icon_label.setPixmap(icon.pixmap(QSize(35, 35))) 
            icon_label.setStyleSheet("background-color: transparent;")
            title_layout.addWidget(icon_label)
        title_label = QLabel(title)
        title_label.setObjectName("subtitle")
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        card_layout.addWidget(title_frame)
        content_frame = QWidget()
        content_frame.setStyleSheet(f"background-color: {self.palette['SECONDARY_BG']};")
        card_layout.addWidget(content_frame)
        return card_frame, content_frame


    def _create_index_card(self, parent, title, row, col, icon_name=None):
        card, content = self._create_card(parent, title, icon_name=icon_name)
        parent.layout().addWidget(card, row, col)
        content_layout = QVBoxLayout(content)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ref = {}
        ref['label'] = QLabel("--")
        ref['label'].setFont(QFont("Bahnschrift", 30, QFont.Weight.Bold)) 
        ref['label'].setStyleSheet(f"color: {self.UNSELECTED_TEXT};")
        ref['label'].setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(ref['label'])
        ref['bar'] = QProgressBar()
        ref['bar'].setProperty("styleIdentifier", "blue")
        ref['bar'].setTextVisible(False)
        ref['bar'].setValue(0)
        content_layout.addWidget(ref['bar'])
        return ref

    def _get_new_sample_id(self, sample_type):
        prefix = self.sample_type_prefix[sample_type] 
        id_prefix_str = f"PS-{prefix}_" 
        unique_ids = set()
        
        if os.path.exists(report_file):
            try:
                with open(report_file, "r", newline="") as f:
                    reader = csv.reader(f)
                    next(reader, None) 
                    for row in reader:
                        if len(row) > 2 and row[2] == sample_type:
                            unique_ids.add(row[1])
            except Exception as e:
                print(f"Error reading report file for ID calc: {e}")
        
        num = len(unique_ids)
        return f"{id_prefix_str}{num+1:04d}"

    def save_to_report(self, sample_id, sample, readings, quality):
        new_entry = [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), sample_id, sample] + readings + [quality]
        file_exists = os.path.exists(report_file)
        column_names = [
            "Timestamp", "Sample ID", "Type",
            "Temperature", "Humidity", "WHC Index", "Fatty Acid Profile", "Myoglobin", 
            "MQ-137 (Ammonia)", "MQ-135 (Air Quality)", "MQ-7 (CO)", "MQ-4 (Methane)", "Quality"
        ]
        try:
            with open(report_file, "a", newline="") as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(column_names)
                if len(new_entry) == len(column_names):
                    writer.writerow(new_entry)
                else:
                    show_custom_message(self, "Data Save Error", f"Report save failed: Expected {len(column_names)} columns, got {len(new_entry)}. Data not logged.", "error", self.palette)
        except Exception as e:
            show_custom_message(self, "Data Save Error", f"Report save failed: {e}", "error", self.palette)

    # --- MODIFIED: Function to save all 54 channels to database log ---
    def save_to_database_log(self, sample_id, raw_readings):
        """
        Saves a clean, raw sensor data row to a separate CSV
        file designed to match the database's tbl_reading.
        This now saves all 54 spectral channels.
        """
        
        # --- MODIFIED: Expanded header for all 54 spectral channels ---
        header = (
            ['sample_id', 'temp', 'hum', 'mq_137', 'mq_135', 'mq_4', 'mq_7'] +
            [f'as7265x_ch{i+1}' for i in range(18)] + # White
            [f'as_uv_ch{i+1}' for i in range(18)] +   # UV
            [f'as_ir_ch{i+1}' for i in range(18)]    # IR
        )
        # --- END MODIFICATION ---
        
        try:
            # --- MODIFIED: Map all data to the new header ---
            data_row = [
                sample_id,
                raw_readings.get('Temperature', 'N/A'),
                raw_readings.get('Humidity', 'N/A'),
                raw_readings.get('MQ-137 (Ammonia)', 'N/A'),
                raw_readings.get('MQ-135 (Air Quality)', 'N/A'),
                raw_readings.get('MQ-4 (Methane)', 'N/A'),
                raw_readings.get('MQ-7 (CO)', 'N/A'),
            ]
            
            # Add all 18 WHITE channels
            for i in range(18):
                key = f'AS7265X_ch{i+1}' # Key from sensor file is uppercase 'AS7265X'
                data_row.append(raw_readings.get(key, 'N/A'))
            
            # Add all 18 UV channels
            for i in range(18):
                key = f'AS_UV_ch{i+1}'
                data_row.append(raw_readings.get(key, 'N/A'))

            # Add all 18 IR channels
            for i in range(18):
                key = f'AS_IR_ch{i+1}'
                data_row.append(raw_readings.get(key, 'N/A'))
            # --- END MODIFICATION ---
            
            file_exists = os.path.exists(DATABASE_LOG_FILE)
            
            with open(DATABASE_LOG_FILE, "a", newline="") as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(header) # Write header only if file is new
                writer.writerow(data_row)
        
        except Exception as e:
            # Show an error but don't crash the main app
            print(f"CRITICAL: Failed to write to database log: {e}")
            show_custom_message(self, "DB Log Error", f"Failed to save raw database log:\n{e}", "error", self.palette)
    # --- END MODIFICATION ---
    
    
    def pulse_feedback(self, widget, original_color, count):
        if count > 0:
            current_color = self.ACCENT_COLOR if count % 2 == 0 else original_color
            widget.setStyleSheet(f"color: {current_color}; background-color: transparent;")
            QTimer.singleShot(100, lambda: self.pulse_feedback(widget, original_color, count - 1))
        else:
            widget.setStyleSheet(f"color: {original_color}; background-color: transparent;")

    def pulse_border_color(self, widget, color, count):
        if count > 0:
            current_color = color if count % 2 == 0 else self.BORDER_COLOR
            widget.setStyleSheet(f"QWidget[objectName=\"card\"] {{ border: 2px solid {current_color}; }}")
            QTimer.singleShot(150, lambda: self.pulse_border_color(widget, color, count - 1))
        else:
            widget.setStyleSheet(f"QWidget[objectName=\"card\"] {{ border: 2px solid {color}; }}")

    def animate_streaming_text(self):
        self.stream_dot_count += 1
        dots = " ." * (self.stream_dot_count % 3 + 1)
        text = f"SCANNING{dots:<4}" # <-- MODIFIED TEXT
        for key in self.raw_label_refs:
            current_text = self.raw_label_refs[key].text().split(':')[0]
            self.raw_label_refs[key].setText(f"{current_text}: {text}")
            self.raw_label_refs[key].setStyleSheet(f"color: {self.PRIMARY_COLOR};")
        if self.stream_dot_count % 2 == 0:
            self.status_light.setStyleSheet(f"background-color: {self.ACCENT_COLOR}; border-radius: 9px;")
        else:
            self.status_light.setStyleSheet(f"background-color: {self.PRIMARY_COLOR}; border-radius: 9px;")

    def animate_progress_bar(self, bar_widget, value):
        style_id = "red"
        if value >= 75: style_id = "green"
        elif value >= 40: style_id = "orange"
        bar_widget.setProperty("styleIdentifier", style_id)
        bar_widget.style().unpolish(bar_widget)
        bar_widget.style().polish(bar_widget)
        anim = QPropertyAnimation(bar_widget, b"value", self)
        anim.setDuration(800)
        anim.setStartValue(0)
        anim.setEndValue(value)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start(QAbstractAnimation.DeleteWhenStopped)

    
    @Slot(dict)
    def update_gui_and_archive(self, raw_readings):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.streaming_timer.stop()
        if self.scan_animation:
            self.scan_animation.stop()
        self.btn_run.setIcon(qta.icon('fa5s.play', color=self.btn_run_icon_color))

        try:
            enose_index, whc_index, fac_index, myoglobin_index, final_score = calculate_group_scores(raw_readings)
            quality_category, color_tag, score = calculate_overall_quality(final_score)
        except Exception as e:
            self.handle_scan_error(f"Failed during score calculation: {e}\nCheck data_model.py and raw sensor keys.")
            return

        final_color = self.DANGER_COLOR
        if color_tag == 'high': final_color = self.SUCCESS_COLOR
        elif color_tag == 'normal': final_color = self.NORMAL_COLOR

        self.score_display.setStyleSheet(f"color: {final_color}; background-color: transparent;")
        self.anim_score = QPropertyAnimation(self, b"score_kpi_value", self)
        self.anim_score.setDuration(1000)
        self.anim_score.setStartValue(0)
        self.anim_score.setEndValue(score)
        self.anim_score.setEasingCurve(QEasingCurve.OutCubic)
        self.anim_score.start(QAbstractAnimation.DeleteWhenStopped)
        self.pulse_border_color(self.score_border_frame, final_color, 7)
        def _update_quality_label():
            self.quality_label.setText(f"[ {quality_category} ]")
            self.quality_label.setStyleSheet(f"color: {final_color};")
            self.pulse_feedback(self.quality_label, final_color, 8)
        QTimer.singleShot(300, _update_quality_label)
        def _update_index_cards():
            self.index_refs['enose']['label'].setText(f"{enose_index}")
            self.index_refs['enose']['label'].setStyleSheet(f"color: {final_color};")
            self.animate_progress_bar(self.index_refs['enose']['bar'], enose_index)
            self.index_refs['whc']['label'].setText(f"{whc_index}")
            self.index_refs['whc']['label'].setStyleSheet(f"color: {final_color};")
            self.animate_progress_bar(self.index_refs['whc']['bar'], whc_index)
            self.index_refs['fac']['label'].setText(f"{fac_index}")
            self.index_refs['fac']['label'].setStyleSheet(f"color: {final_color};")
            self.animate_progress_bar(self.index_refs['fac']['bar'], fac_index)
            self.index_refs['myo']['label'].setText(f"{myoglobin_index}")
            self.index_refs['myo']['label'].setStyleSheet(f"color: {final_color};")
            self.animate_progress_bar(self.index_refs['myo']['bar'], myoglobin_index)
        QTimer.singleShot(500, _update_index_cards)
        
        def _update_raw_labels(whc_val, fac_val, myo_val):
            for label in self.raw_label_refs.values():
                label.setStyleSheet(f"color: {self.TEXT_COLOR};") 
            self.raw_label_refs["Temperature"].setText(f"Temperature: {raw_readings.get('Temperature', 0):.1f} °C")
            self.raw_label_refs["Humidity"].setText(f"Humidity: {raw_readings.get('Humidity', 0):.1f} % RH")
            
            self.raw_label_refs["MQ-137 (Ammonia)"].setText(f"NH₃ (Ammonia): {raw_readings.get('MQ-137 (Ammonia)', 0):.3f} V")
            self.raw_label_refs["MQ-135 (Air Quality)"].setText(f"Air Quality: {raw_readings.get('MQ-135 (Air Quality)', 0):.3f} V")
            self.raw_label_refs["MQ-7 (CO)"].setText(f"CO: {raw_readings.get('MQ-7 (CO)', 0):.3f} V")
            self.raw_label_refs["MQ-4 (Methane)"].setText(f"CH₄ (Methane): {raw_readings.get('MQ-4 (Methane)', 0):.3f} V")
            
            whc_text = f"WHC Index: {whc_val}"
            fac_text = f"FAC Index: {fac_val}"
            myo_text = f"Myoglobin Index: {myo_val}"
            self.raw_label_refs["WHC Index"].setText(whc_text)
            self.raw_label_refs["Fatty Acid Profile"].setText(fac_text)
            self.raw_label_refs["Myoglobin"].setText(myo_text)
        
        QTimer.singleShot(700, lambda: _update_raw_labels(whc_index, fac_index, myoglobin_index))

        def _show_archive_dialog():
            sample_type = self.sample_type_combobox.currentText()
            is_confirmed_to_save = show_custom_message(
                self, "Save Test Result",
                f"Analysis Complete. Category: {quality_category} ({score}).\nProceed with archival?",
                "confirm", self.palette
            )
            if is_confirmed_to_save:
                global current_sample_id
                sid = None 
                if current_sample_id:
                    title = "Confirm Sample ID"
                    message = (
                        f"Is this test for the *same* sample as the last one ({current_sample_id})?\n\n"
                        f"• Click YES to save this test under ID: {current_sample_id}\n"
                        f"• Click NO to assign a new ID for this different sample."
                    )
                    is_same_sample = show_custom_message(
                        self, title, message, "confirm", self.palette
                    )
                    if is_same_sample:
                        sid = current_sample_id
                    else:
                        sid = self._get_new_sample_id(sample_type)
                        current_sample_id = sid
                else:
                    sid = self._get_new_sample_id(sample_type)
                    current_sample_id = sid
                
                self.sample_id_label.setText(sid)
                
                readings_list = [
                    raw_readings.get("Temperature", 'N/A'),
                    raw_readings.get("Humidity", 'N/A'),
                    whc_index, 
                    fac_index, 
                    myoglobin_index,
                    raw_readings.get("MQ-137 (Ammonia)", 'N/A'),
                    raw_readings.get("MQ-135 (Air Quality)", 'N/A'),
                    raw_readings.get("MQ-7 (CO)", 'N/A'),
                    raw_readings.get("MQ-4 (Methane)", 'N/A')
                ]
                
                self.save_to_report(sid, sample_type, readings_list, quality_category)
                self.save_to_database_log(sid, raw_readings) 

                show_custom_message(self, "Archival Success", f"Test data archived as {sid}", "success", self.palette)

            self.btn_run.setEnabled(True)
            self.btn_clear.setEnabled(True)
            self.btn_clear.setIcon(qta.icon('fa5s.broom', color=self.btn_clear_icon_color))
        QTimer.singleShot(1200, _show_archive_dialog)


    @Slot(str)
    def handle_scan_error(self, error_message):
        self.streaming_timer.stop()
        if self.scan_animation:
            self.scan_animation.stop()
        self.btn_run.setIcon(qta.icon('fa5s.play', color=self.btn_run_icon_color))
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.score_display.setText("FAIL")
        self.score_display.setStyleSheet(f"color: {self.DANGER_COLOR}; background-color: transparent;")
        self.quality_label.setText("SENSOR ERROR")
        self.quality_label.setStyleSheet(f"color: {self.DANGER_COLOR};")
        self.status_light.setStyleSheet(f"background-color: {self.DANGER_COLOR}; border-radius: 9px;")
        self.btn_run.setEnabled(True)
        self.btn_clear.setEnabled(True)
        self.btn_clear.setIcon(qta.icon('fa5s.broom', color=self.btn_clear_icon_color))
        
        show_custom_message(self, "Sensor Error", f"Failed to read hardware sensors:\n{error_message}", "error", self.palette)

    def run_test(self):
        sample_type = self.sample_type_combobox.currentText()
        if not sample_type:
            show_custom_message(self, "Missing Selection", "Please select a sample type before running the test.", "warning", self.palette)
            return

        self.btn_run.setEnabled(False)
        self.btn_clear.setEnabled(False)
        self.btn_clear.setIcon(qta.icon('fa5s.broom', color=self.palette["BORDER"]))
        self.scan_animation = qta.Spin(self.btn_run)
        self.btn_run.setIcon(qta.icon('fa5s.spinner', color=self.btn_run_icon_color, animation=self.scan_animation))
        self.score_display.setText("...")
        self.score_display.setStyleSheet(f"color: {self.ACCENT_COLOR}; background-color: transparent;")
        self.quality_label.setText(f"SCANNING {sample_type}...")
        self.quality_label.setStyleSheet(f"color: {self.ACCENT_COLOR};")
        self.score_border_frame.setStyleSheet(f"QWidget[objectName=\"card\"] {{ border: 2px solid {self.ACCENT_COLOR}; }}")
        for group in self.index_refs.values():
            group['label'].setText("...")
            group['label'].setStyleSheet(f"color: {self.ACCENT_COLOR};")
            group['bar'].setProperty("styleIdentifier", "blue")
            group['bar'].setValue(0)
            group['bar'].style().unpolish(group['bar'])
            group['bar'].style().polish(group['bar'])
        self.status_light.setStyleSheet(f"background-color: {self.ACCENT_COLOR}; border-radius: 9px;")
        self.progress_bar.setRange(0, 0)
        self.stream_dot_count = 0
        self.streaming_timer.start(250) 
        self.scan_thread = QThread()
        self.scan_worker = SensorWorker()
        self.scan_worker.moveToThread(self.scan_thread)
        self.scan_thread.started.connect(self.scan_worker.run_scan)
        self.scan_worker.finished.connect(self.update_gui_and_archive)
        self.scan_worker.error.connect(self.handle_scan_error)
        self.scan_worker.finished.connect(self.scan_thread.quit)
        self.scan_worker.finished.connect(self.scan_worker.deleteLater)
        self.scan_thread.finished.connect(self.scan_thread.deleteLater)
        self.scan_thread.start()


    def clear_dashboard(self):
        global current_sample_id
        if hasattr(self, 'anim_score') and self.anim_score:
            self.anim_score.stop()
        if self.scan_animation:
            self.scan_animation.stop()
        self.streaming_timer.stop()
        self.sample_type_combobox.setCurrentText("Chicken Breast")
        self.sample_id_label.setText("PS-INIT-0000")
        self.score_display.setText("--")
        self.score_display.setStyleSheet(f"color: {self.UNSELECTED_TEXT}; background-color: transparent;")
        self.quality_label.setText("AWAITING SCAN")
        self.quality_label.setStyleSheet(f"color: {self.UNSELECTED_TEXT};")
        self.score_border_frame.setStyleSheet(f"QWidget[objectName=\"card\"] {{ border: 2px solid {self.UNSELECTED_TEXT}; }}")
        for group in self.index_refs.values():
            group['label'].setText("--")
            group['label'].setStyleSheet(f"color: {self.UNSELECTED_TEXT};")
            group['bar'].setProperty("styleIdentifier", "blue")
            group['bar'].setValue(0)
            group['bar'].style().unpolish(group['bar'])
            group['bar'].style().polish(group['bar'])
        self.status_light.setStyleSheet(f"background-color: {self.UNSELECTED_TEXT}; border-radius: 9px;")
        self.raw_label_refs["Temperature"].setText("Temperature: -- °C")
        self.raw_label_refs["Humidity"].setText("Humidity: -- % RH")
        
        self.raw_label_refs["MQ-137 (Ammonia)"].setText("NH₃ (Ammonia): N/A V")
        self.raw_label_refs["MQ-135 (Air Quality)"].setText("Air Quality: N/A V")
        self.raw_label_refs["MQ-7 (CO)"].setText("CO: N/A V")
        self.raw_label_refs["MQ-4 (Methane)"].setText("CH₄ (Methane): N/A V")
        
        self.raw_label_refs["WHC Index"].setText("WHC Index: N/A")
        self.raw_label_refs["Fatty Acid Profile"].setText("FAC Index: N/A")
        self.raw_label_refs["Myoglobin"].setText("Myoglobin Index: N/A") 
        for label in self.raw_label_refs.values():
            label.setStyleSheet(f"color: {self.TEXT_COLOR};")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        current_sample_id = None
        self.btn_run.setIcon(qta.icon('fa5s.play', color=self.btn_run_icon_color))
        self.btn_clear.setIcon(qta.icon('fa5s.broom', color=self.btn_clear_icon_color))
        self.btn_run.setEnabled(True)
        self.btn_clear.setEnabled(True)