# dashboard_tab.py

import sys
import os
import csv
import time
import qtawesome as qta
import lgpio  
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QFrame, QPushButton, QComboBox, QProgressBar, QScrollArea, 
    QMainWindow, QApplication, QDialog, QGraphicsBlurEffect
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

# --- HARDWARE CONSTANTS ---
FAN_PIN = 27
LED_PIN = 17 
PWM_FREQ = 100

# --- TIMING CONSTANTS ---
STARTUP_PURGE_MS = 15000      
CALIBRATION_TIME_MS = 30000   
SCAN_ITERATIONS = 5           
SCAN_DELAY_S = 0.5            
SMART_PURGE_TIMEOUT_S = 60    

# --- IMPORTS ---
try:
    from Sensors.as7265x import read_all_sensors, SPECTROMETER_PLACEHOLDER
    from Sensors.data_model import calculate_group_scores, calculate_overall_quality
except ImportError as e:
    print("="*50)
    print(f"FATAL ERROR: Could not import sensor/data modules.")
    print(f"Error: {e}")
    def show_exit_message():
        app = QApplication.instance()
        if app:
            main_window = next((w for w in app.topLevelWidgets() if isinstance(w, QMainWindow)), None)
            if main_window:
                show_custom_message(main_window, "Fatal Error", f"Failed to import sensor modules: {e}\n\nApplication will now exit.", "error", {"DANGER": "#D32F2F"})
            QTimer.singleShot(100, app.quit)
        else:
            sys.exit(1) 
    QTimer.singleShot(100, show_exit_message)
    raise SystemExit(f"Missing required sensor/data modules: {e}")


class SensorWorker(QObject):
    finished = Signal(dict) 
    progress = Signal(int) 
    error = Signal(str)
    
    @Slot()
    def run_scan(self):
        try:
            accumulated_readings = []
            for i in range(SCAN_ITERATIONS):
                current_progress = int((i / SCAN_ITERATIONS) * 100)
                self.progress.emit(current_progress)
                
                reading = read_all_sensors()
                reading['_iteration'] = i + 1 
                accumulated_readings.append(reading)
                
                if i < SCAN_ITERATIONS - 1:
                    time.sleep(SCAN_DELAY_S)

            self.progress.emit(100) 

            if not accumulated_readings:
                raise ValueError("No readings were collected.")

            final_result = {}
            first_reading = accumulated_readings[0]
            
            for key, value in first_reading.items():
                if key == '_iteration': continue 
                if isinstance(value, (int, float)):
                    max_val = max(d[key] for d in accumulated_readings)
                    final_result[key] = max_val
                else:
                    final_result[key] = value

            payload = {
                "average": final_result,
                "all_iterations": accumulated_readings
            }
            self.finished.emit(payload)

        except Exception as e:
            self.error.emit(str(e))


class SmartPurgeWorker(QObject):
    readings_update = Signal(dict)
    finished = Signal()
    
    def __init__(self):
        super().__init__()
        self._is_running = True

    @Slot()
    def start_monitoring(self):
        while self._is_running:
            try:
                current_data = read_all_sensors()
                self.readings_update.emit(current_data)
                time.sleep(1.0) 
            except Exception:
                pass 
        self.finished.emit()

    def stop(self):
        self._is_running = False


class StartupOverlay(QDialog):
    """
    A strictly modal overlay that blocks the entire application window
    during the initialization phase.
    """
    def __init__(self, palette, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Dialog)
        
        # STRICT MODALITY: Blocks input to all other windows (Sidebars, Tabs, etc.)
        self.setWindowModality(Qt.ApplicationModal)
        self.setModal(True)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        container = QFrame()
        container.setStyleSheet(f"""
            QFrame {{
                background-color: {palette['SECONDARY_BG']};
                border: 2px solid {palette['PRIMARY']};
                border-radius: 10px;
            }}
        """)
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(15)
        
        title = QLabel("SYSTEM INITIALIZATION")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"font: bold 16pt 'Bahnschrift'; color: {palette['PRIMARY']}; border: none;")
        container_layout.addWidget(title)
        
        self.status_label = QLabel("Preparing system...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(f"font: 12pt 'Bahnschrift'; color: {palette['TEXT']}; border: none;")
        container_layout.addWidget(self.status_label)
        
        self.pbar = QProgressBar()
        self.pbar.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                background-color: {palette['BG']};
                height: 10px;
                border-radius: 5px;
            }}
            QProgressBar::chunk {{
                background-color: {palette['ACCENT']};
                border-radius: 5px;
            }}
        """)
        self.pbar.setTextVisible(False)
        container_layout.addWidget(self.pbar)
        
        warning = QLabel("Please wait. Do not interrupt.")
        warning.setAlignment(Qt.AlignCenter)
        warning.setStyleSheet(f"font: italic 10pt 'Bahnschrift'; color: {palette['UNSELECTED_TEXT']}; border: none;")
        container_layout.addWidget(warning)
        
        layout.addWidget(container)
        self.setFixedSize(400, 250)

    def showEvent(self, event):
        """
        Force the dialog to center itself on the MAIN WINDOW (Root Parent),
        ignoring the specific tab geometry. This ensures it's in the visual middle.
        """
        if self.parent() and self.parent().window():
            parent_window = self.parent().window()
            geo = parent_window.geometry()
            x = geo.x() + (geo.width() - self.width()) // 2
            y = geo.y() + (geo.height() - self.height()) // 2
            self.move(x, y)
        super().showEvent(event)

    def keyPressEvent(self, event):
        """Block Escape key to prevent closing."""
        if event.key() == Qt.Key.Key_Escape:
            event.ignore()
        else:
            super().keyPressEvent(event)

    def update_status(self, text, progress_value=0, indeterminate=True):
        self.status_label.setText(text)
        if indeterminate:
            self.pbar.setRange(0, 0) 
        else:
            self.pbar.setRange(0, 100)
            self.pbar.setValue(progress_value)


class DashboardTab(QWidget):

    def __init__(self, palette, sample_type_prefix, gpio_handle=None, parent=None):
        super().__init__(parent)

        self._score_kpi_value = 0 
        self.palette = palette
        self.sample_type_prefix = sample_type_prefix
        self.gpio_handle = gpio_handle
        
        self.baseline_data = {} 
        self.raw_label_refs = {}
        self.index_refs = {}
        
        self.scan_thread = None
        self.scan_worker = None
        
        self.purge_thread = None
        self.purge_worker = None
        self.purge_start_time = 0

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
        
        self.setup_ui()
        
        # Initialize Overlay with self as parent, logic in Overlay will find Main Window
        self.startup_overlay = StartupOverlay(palette, self)
        
        # Trigger startup immediately upon activation
        QTimer.singleShot(100, self.start_startup_sequence)

    def setup_ui(self):
        page_layout = QVBoxLayout(self) 
        page_layout.setContentsMargins(0, 0, 0, 0)
        
        self.scroll_area = QScrollArea() 
        self.scroll_area.setWidgetResizable(True)
        
        scroll_content = QWidget()
        main_layout = QGridLayout(scroll_content)
        main_layout.setContentsMargins(5, 5, 5, 5) 
        main_layout.setSpacing(10) 

        control_card, control_frame = self._create_card(scroll_content, " Test Control & Status", icon_name="fa5s.gamepad")
        main_layout.addWidget(control_card, 0, 0, 1, 2)
        control_layout = QGridLayout(control_frame)
        control_layout.addWidget(QLabel("Sample Type:"), 0, 0, Qt.AlignmentFlag.AlignLeft)
        self.sample_type_combobox = QComboBox()
        self.sample_type_combobox.addItems(list(self.sample_type_prefix.keys()))
        self.sample_type_combobox.setFixedWidth(200) 
        control_layout.addWidget(self.sample_type_combobox, 0, 1)
        control_layout.addWidget(QLabel("Sample ID:"), 0, 2, Qt.AlignmentFlag.AlignRight)
        self.sample_id_label = QLabel("PS-INIT-0000")
        self.sample_id_label.setStyleSheet(f"font: bold 12pt 'Bahnschrift'; color: {self.ACCENT_COLOR};") 
        control_layout.addWidget(self.sample_id_label, 0, 3, Qt.AlignmentFlag.AlignLeft)
        self.status_light = QLabel()
        self.status_light.setFixedSize(15, 12) 
        self.status_light.setStyleSheet(f"background-color: {self.UNSELECTED_TEXT}; border-radius: 6px;") 
        control_layout.addWidget(self.status_light, 0, 4, Qt.AlignmentFlag.AlignLeft)
        control_layout.setColumnStretch(5, 1)
        
        self.btn_purge = QPushButton(" PURGE")
        self.btn_purge.setIcon(qta.icon('fa5s.fan', color=self.palette['TEXT']))
        self.btn_purge.setObjectName("secondary")
        self.btn_purge.clicked.connect(self.start_smart_purge)
        control_layout.addWidget(self.btn_purge, 0, 6)

        self.btn_run = QPushButton(" RUN TEST")
        self.btn_run.setIcon(qta.icon('fa5s.play', color=self.btn_run_icon_color))
        control_layout.addWidget(self.btn_run, 0, 7)
        
        self.btn_clear = QPushButton(" CLEAR")
        self.btn_clear.setIcon(qta.icon('fa5s.broom', color=self.btn_clear_icon_color))
        self.btn_clear.setObjectName("secondary")
        self.btn_clear.clicked.connect(self.clear_dashboard)
        control_layout.addWidget(self.btn_clear, 0, 8)
        
        main_content_frame = QWidget()
        main_content_layout = QGridLayout(main_content_frame)
        main_content_layout.setSpacing(10) 
        main_layout.addWidget(main_content_frame, 1, 0, 1, 2)
        
        score_category_frame = QWidget()
        score_category_layout = QGridLayout(score_category_frame)
        score_category_layout.setSpacing(10) 
        main_content_layout.addWidget(score_category_frame, 0, 0, 1, 2)
        
        self.score_border_frame, overall_frame_g = self._create_card(score_category_frame, " PoultriScan Quality Score", icon_name="fa5s.tachometer-alt")
        self.score_border_frame.setStyleSheet(f"QWidget[objectName=\"card\"] {{ border: 2px solid {self.UNSELECTED_TEXT}; }}")
        score_category_layout.addWidget(self.score_border_frame, 0, 0, 2, 1)
        overall_layout = QVBoxLayout(overall_frame_g)
        score_kpi_frame = QWidget()
        score_kpi_frame.setStyleSheet(f"background-color: {self.BORDER_COLOR}; border-radius: 5px;")
        score_kpi_layout = QVBoxLayout(score_kpi_frame)
        self.score_display = QLabel("--")
        self.score_display.setFont(QFont("Bahnschrift", 32, QFont.Weight.Bold)) 
        self.score_display.setStyleSheet(f"color: {self.UNSELECTED_TEXT}; background-color: transparent;")
        self.score_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        score_kpi_layout.addWidget(self.score_display)
        overall_layout.addWidget(score_kpi_frame)
        self.quality_label = QLabel("AWAITING SCAN")
        self.quality_label.setFont(QFont("Bahnschrift", 12, QFont.Weight.Bold)) 
        self.quality_label.setStyleSheet(f"color: {self.UNSELECTED_TEXT};")
        self.quality_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        overall_layout.addWidget(self.quality_label)
        self.progress_bar = QProgressBar()
        self.progress_bar.setProperty("styleIdentifier", "blue")
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setValue(0)
        overall_layout.addWidget(self.progress_bar)
        
        self.index_refs['enose'] = self._create_index_card(score_category_frame, " eNose VOC Index", 0, 1, "fa5s.wind")
        self.index_refs['whc'] = self._create_index_card(score_category_frame, " WHC Index", 0, 2, "fa5s.water")     
        self.index_refs['fac'] = self._create_index_card(score_category_frame, " FAC Index", 1, 1, "fa5s.flask")     
        self.index_refs['myo'] = self._create_index_card(score_category_frame, " Myoglobin Index", 1, 2, "fa5s.tint") 
        score_category_layout.setColumnStretch(0, 2) 
        score_category_layout.setColumnStretch(1, 1) 
        score_category_layout.setColumnStretch(2, 1) 
        score_category_layout.setColumnStretch(3, 0) 
        
        raw_data_card, raw_data_container = self._create_card(main_content_frame, " Raw Sensor Readings", icon_name="fa5s.wave-square")
        main_content_layout.addWidget(raw_data_card, 1, 0, 1, 2)
        raw_data_layout = QGridLayout(raw_data_container)
        raw_data_layout.setSpacing(10) 
        data_font = QFont("Bahnschrift", 9) 
        
        env_card, env_frame = self._create_card(raw_data_container, " AHT20 (Environment)", icon_name="fa5s.thermometer-half")
        raw_data_layout.addWidget(env_card, 0, 0)
        env_layout = QVBoxLayout(env_frame)
        self.raw_label_refs["Temperature"] = QLabel("Temperature: -- °C")
        self.raw_label_refs["Humidity"] = QLabel("Humidity: -- % RH")
        self.raw_label_refs["Temperature"].setFont(data_font)
        self.raw_label_refs["Humidity"].setFont(data_font)
        env_layout.addWidget(self.raw_label_refs["Temperature"])
        env_layout.addWidget(self.raw_label_refs["Humidity"])
        
        spec_card, spec_frame = self._create_card(raw_data_container, " AS7265X (Spectrometry)", icon_name="fa5s.palette")
        raw_data_layout.addWidget(spec_card, 0, 1)
        spec_layout = QVBoxLayout(spec_frame)
        self.raw_label_refs["WHC Index"] = QLabel("WHC Index: N/A")
        self.raw_label_refs["Fatty Acid Profile"] = QLabel("FAC Index: N/A")
        self.raw_label_refs["Myoglobin"] = QLabel("Myoglobin Index: N/A") 
        for key in ["WHC Index", "Fatty Acid Profile", "Myoglobin"]:
            self.raw_label_refs[key].setFont(data_font)
            spec_layout.addWidget(self.raw_label_refs[key])
        
        enose_raw_card, enose_raw_frame = self._create_card(raw_data_container, " eNose (VOCs)", icon_name="fa5s.cloud")
        raw_data_layout.addWidget(enose_raw_card, 0, 2)
        enose_layout = QGridLayout(enose_raw_frame)
        mq_sensors_data = [
            ("MQ-137 (Ammonia)", "NH₃ (Ammonia): N/A V"),
            ("MQ-135 (Air Quality)", "Air Quality: N/A V"),
            ("MQ-3 (Alcohol)", "Alcohol: N/A V"),
            ("MQ-4 (Methane)", "CH₄: N/A V"),
        ]
        for i, (key, initial_text) in enumerate(mq_sensors_data):
            label = QLabel(initial_text)
            label.setFont(data_font) 
            enose_layout.addWidget(label, i // 2, i % 2)
            self.raw_label_refs[key] = label
        
        main_layout.setRowStretch(1, 1)
        self.scroll_area.setWidget(scroll_content)
        page_layout.addWidget(self.scroll_area)
        
        self.btn_run.clicked.connect(self.run_test)

    def start_startup_sequence(self):
        # 1. Blur the entire Main Window content if possible, else blur dashboard
        target_widget = self.window() if self.window() else self.scroll_area
        self.blur_effect = QGraphicsBlurEffect(target_widget)
        self.blur_effect.setBlurRadius(15) 
        target_widget.setGraphicsEffect(self.blur_effect)

        self.startup_overlay.show()
        
        self.btn_run.setEnabled(False)
        self.btn_purge.setEnabled(False) 
        self.btn_run.setText(" STARTING...")
        
        sec = STARTUP_PURGE_MS // 1000
        self.startup_overlay.update_status(f"PURGING CHAMBER... ({sec}s)")
        
        self.quality_label.setText(f"STARTUP PURGE ({sec}s)")
        self.quality_label.setStyleSheet(f"color: {self.PRIMARY_COLOR};")
        self.status_light.setStyleSheet(f"background-color: {self.PRIMARY_COLOR}; border-radius: 6px;") 
        
        self._control_fan(True)
        QTimer.singleShot(STARTUP_PURGE_MS, self.start_startup_calibration)

    def start_startup_calibration(self):
        self._control_fan(False)
        
        sec = CALIBRATION_TIME_MS // 1000
        self.startup_overlay.update_status(f"CALIBRATING SENSORS... ({sec}s)", 0, indeterminate=False)
        
        self.quality_label.setText(f"CALIBRATING SENSORS ({sec}s)...")
        self.quality_label.setStyleSheet(f"color: {self.ACCENT_COLOR};")
        
        self.overlay_anim = QPropertyAnimation(self.startup_overlay.pbar, b"value", self)
        self.overlay_anim.setDuration(CALIBRATION_TIME_MS)
        self.overlay_anim.setStartValue(0)
        self.overlay_anim.setEndValue(100)
        self.overlay_anim.start()

        QTimer.singleShot(CALIBRATION_TIME_MS, self.capture_baseline_and_ready)

    def capture_baseline_and_ready(self):
        # Remove blur from Main Window
        target_widget = self.window() if self.window() else self.scroll_area
        target_widget.setGraphicsEffect(None)
        
        self.startup_overlay.update_status("FINALIZING INITIALIZATION...")
        
        try:
            baseline = read_all_sensors()
            self.baseline_data = baseline
        except Exception as e:
            print(f"Error capturing baseline: {e}")
            self.baseline_data = {} 

        self.quality_label.setText("READY TO SCAN")
        self.quality_label.setStyleSheet(f"color: {self.SUCCESS_COLOR};")
        self.status_light.setStyleSheet(f"background-color: {self.SUCCESS_COLOR}; border-radius: 6px;")
        self.progress_bar.setValue(0)
        
        self.btn_run.setEnabled(True)
        self.btn_purge.setEnabled(True) 
        self.btn_run.setText(" RUN TEST")
        
        self.startup_overlay.accept()
        
        QTimer.singleShot(2000, lambda: self.quality_label.setText("AWAITING SCAN"))
        QTimer.singleShot(2000, lambda: self.quality_label.setStyleSheet(f"color: {self.UNSELECTED_TEXT};"))
        QTimer.singleShot(2000, lambda: self.status_light.setStyleSheet(f"background-color: {self.UNSELECTED_TEXT}; border-radius: 6px;"))

    def run_test(self):
        sample_type = self.sample_type_combobox.currentText()
        if not sample_type:
            show_custom_message(self, "Missing Selection", "Please select a sample type.", "warning", self.palette)
            return
        if self.gpio_handle is None:
             show_custom_message(self, "Hardware Error", "GPIO is not initialized.", "error", self.palette)
             return

        self.btn_run.setEnabled(False)
        self.btn_purge.setEnabled(False) 
        self.btn_clear.setEnabled(False)
        self.btn_clear.setIcon(qta.icon('fa5s.broom', color=self.palette["BORDER"]))
        
        self.score_display.setText("...")
        self.score_display.setStyleSheet(f"color: {self.ACCENT_COLOR}; background-color: transparent;")
        self.quality_label.setText(f"SCANNING {sample_type}...")
        self.quality_label.setStyleSheet(f"color: {self.ACCENT_COLOR};")
        self.score_border_frame.setStyleSheet(f"QWidget[objectName=\"card\"] {{ border: 2px solid {self.ACCENT_COLOR}; }}")
        
        for group in self.index_refs.values():
            group['label'].setText("...")
            group['label'].setStyleSheet(f"color: {self.ACCENT_COLOR};")
            group['bar'].setValue(0)
            
        self.status_light.setStyleSheet(f"background-color: {self.ACCENT_COLOR}; border-radius: 6px;") 
        
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        
        self.stream_dot_count = 0
        self.streaming_timer.start(250) 
        
        self._control_led(True)
        
        self.scan_thread = QThread()
        self.scan_worker = SensorWorker()
        self.scan_worker.moveToThread(self.scan_thread)
        
        self.scan_thread.started.connect(self.scan_worker.run_scan)
        self.scan_worker.progress.connect(self.update_scan_progress) 
        self.scan_worker.finished.connect(self.update_gui_and_archive)
        self.scan_worker.error.connect(self.handle_scan_error)
        
        self.scan_worker.finished.connect(self.scan_thread.quit)
        self.scan_worker.finished.connect(self.scan_worker.deleteLater)
        self.scan_thread.finished.connect(self.scan_thread.deleteLater)
        
        self.scan_thread.start()

    @Slot(int)
    def update_scan_progress(self, val):
        anim = QPropertyAnimation(self.progress_bar, b"value", self)
        anim.setDuration(400)
        anim.setStartValue(self.progress_bar.value())
        anim.setEndValue(val)
        anim.start()

    @Slot(dict)
    def update_gui_and_archive(self, data_payload):
        avg_readings = data_payload.get("average", {})
        all_raw = data_payload.get("all_iterations", [])
        
        self._control_led(False)
        self.streaming_timer.stop()
        self.progress_bar.setValue(100)    

        try:
            enose_index, whc_index, fac_index, myoglobin_index, final_score = calculate_group_scores(avg_readings)
            # --- CHANGED: Receive 'grade' string instead of numeric score ---
            quality_category, color_tag, grade = calculate_overall_quality(final_score)
        except Exception as e:
            self.handle_scan_error(f"Failed during score calculation: {e}")
            return

        # Update UI
        final_color = self.DANGER_COLOR
        if color_tag == 'high': final_color = self.SUCCESS_COLOR
        elif color_tag == 'normal': final_color = self.NORMAL_COLOR

        # --- CHANGED: Set Text directly, no number animation ---
        self.score_display.setText(grade)
        self.score_display.setStyleSheet(f"color: {final_color}; background-color: transparent;")
        
        self.pulse_border_color(self.score_border_frame, final_color, 7)
        
        self.quality_label.setText(f"[ {quality_category} ]")
        self.quality_label.setStyleSheet(f"color: {final_color};")
        self.pulse_feedback(self.quality_label, final_color, 8)

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
        
        self._update_raw_labels_ui(avg_readings, whc_index, fac_index, myoglobin_index)

        QTimer.singleShot(500, lambda: self.initiate_archive_sequence(avg_readings, all_raw, quality_category, grade))

    def initiate_archive_sequence(self, avg_readings, all_raw, quality_category, grade):
        """Handles Save Confirmation + ID Logic + Purge"""
        
        is_confirmed_to_save = show_custom_message(
            self, 
            "Save Test Result", 
            f"Analysis Complete.\nCategory: {quality_category}\nResult: {grade}\n\nProceed with archival?", 
            "confirm", 
            self.palette
        )
        
        is_data_saved = False

        if is_confirmed_to_save:
            global current_sample_id
            sid = None 
            sample_type = self.sample_type_combobox.currentText()

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
                avg_readings.get("Temperature", 'N/A'),
                avg_readings.get("Humidity", 'N/A'),
                0, 0, 0, 
                avg_readings.get("MQ-137 (Ammonia)", 'N/A'),
                avg_readings.get("MQ-135 (Air Quality)", 'N/A'),
                avg_readings.get("MQ-3 (Alcohol)", 'N/A'),
                avg_readings.get("MQ-4 (Methane)", 'N/A')
            ]
            
            try:
                from Sensors.data_model import calculate_group_scores
                e_idx, w_idx, f_idx, m_idx, _ = calculate_group_scores(avg_readings)
                readings_list[2] = w_idx
                readings_list[3] = f_idx
                readings_list[4] = m_idx
            except:
                pass

            self.save_to_report(sid, sample_type, readings_list, quality_category)
            self.save_to_database_log(sid, all_raw) 
            
            is_data_saved = True
            show_custom_message(self, "Archival Success", f"Test data archived as {sid}", "success", self.palette)
        else:
            show_custom_message(self, "Cancelled", "Result was NOT saved.", "warning", self.palette)

        status_msg = "Data Saved." if is_data_saved else "Data NOT Saved."
        is_ready_to_purge = show_custom_message(
            self, 
            "Sample Removal", 
            f"{status_msg}\n\nPlease REMOVE the meat sample from the chamber now.\n\nAre you ready to start the Smart Purge?", 
            "confirm", 
            self.palette
        )

        if is_ready_to_purge:
            self.start_smart_purge()
        else:
            self.stop_smart_purge(reason="SKIPPED")

    def start_smart_purge(self):
        self._control_fan(True)
        
        self.btn_run.setEnabled(False)
        self.btn_purge.setEnabled(False) 
        self.btn_clear.setEnabled(False)
        
        self.quality_label.setText("CLEANING CHAMBER...")
        self.quality_label.setStyleSheet(f"color: {self.PRIMARY_COLOR};")
        self.progress_bar.setProperty("styleIdentifier", "orange")
        self.progress_bar.setValue(0) 

        self.purge_start_time = time.time()
        
        self.purge_thread = QThread()
        self.purge_worker = SmartPurgeWorker()
        self.purge_worker.moveToThread(self.purge_thread)
        
        self.purge_thread.started.connect(self.purge_worker.start_monitoring)
        self.purge_worker.readings_update.connect(self.on_purge_update)
        self.purge_worker.finished.connect(self.purge_thread.quit)
        self.purge_worker.finished.connect(self.purge_worker.deleteLater)
        self.purge_thread.finished.connect(self.purge_thread.deleteLater)
        
        self.purge_thread.start()

    @Slot(dict)
    def on_purge_update(self, current_readings):
        elapsed = time.time() - self.purge_start_time
        if elapsed > SMART_PURGE_TIMEOUT_S:
            self.stop_smart_purge(reason="TIMEOUT")
            return

        mq_keys = ["MQ-137 (Ammonia)", "MQ-135 (Air Quality)", "MQ-3 (Alcohol)", "MQ-4 (Methane)"]
        all_clear = True
        
        for key in mq_keys:
            curr_val = current_readings.get(key, 0)
            base_val = self.baseline_data.get(key, 0.1) 
            if base_val == 0: base_val = 0.1
            
            threshold = base_val 
            
            if curr_val > threshold:
                all_clear = False
                self.raw_label_refs[key].setText(f"{key.split(' ')[0]}: {curr_val:.2f}V -> {base_val:.2f}V")
                self.raw_label_refs[key].setStyleSheet(f"color: {self.DANGER_COLOR};")
            else:
                self.raw_label_refs[key].setText(f"{key.split(' ')[0]}: CLEARED ({curr_val:.2f}V)")
                self.raw_label_refs[key].setStyleSheet(f"color: {self.SUCCESS_COLOR};")

        if all_clear:
            self.stop_smart_purge(reason="CLEAN")

    def stop_smart_purge(self, reason):
        if self.purge_worker:
            self.purge_worker.stop()
        
        self._control_fan(False)
        
        self.btn_run.setEnabled(True)
        self.btn_purge.setEnabled(True) 
        self.btn_clear.setEnabled(True)
        self.btn_clear.setIcon(qta.icon('fa5s.broom', color=self.btn_clear_icon_color))
        
        if reason == "CLEAN":
            self.quality_label.setText("READY")
            self.quality_label.setStyleSheet(f"color: {self.SUCCESS_COLOR};")
        elif reason == "SKIPPED":
            self.quality_label.setText("PURGE SKIPPED")
            self.quality_label.setStyleSheet(f"color: {self.UNSELECTED_TEXT};")
        else:
            self.quality_label.setText("PURGE TIMEOUT")
            self.quality_label.setStyleSheet(f"color: {self.UNSELECTED_TEXT};")

    def _update_raw_labels_ui(self, readings, whc, fac, myo):
        self.raw_label_refs["Temperature"].setText(f"Temperature: {readings.get('Temperature', 0):.1f} °C")
        self.raw_label_refs["Humidity"].setText(f"Humidity: {readings.get('Humidity', 0):.1f} % RH")
        self.raw_label_refs["MQ-137 (Ammonia)"].setText(f"NH₃ (Ammonia): {readings.get('MQ-137 (Ammonia)', 0):.3f} V")
        self.raw_label_refs["MQ-135 (Air Quality)"].setText(f"Air Quality: {readings.get('MQ-135 (Air Quality)', 0):.3f} V")
        self.raw_label_refs["MQ-3 (Alcohol)"].setText(f"Alcohol: {readings.get('MQ-3 (Alcohol)', 0):.3f} V")
        self.raw_label_refs["MQ-4 (Methane)"].setText(f"CH₄ (Methane): {readings.get('MQ-4 (Methane)', 0):.3f} V")
        self.raw_label_refs["WHC Index"].setText(f"WHC Index: {whc}")
        self.raw_label_refs["Fatty Acid Profile"].setText(f"FAC Index: {fac}")
        self.raw_label_refs["Myoglobin"].setText(f"Myoglobin Index: {myo}")
        for label in self.raw_label_refs.values():
            label.setStyleSheet(f"color: {self.TEXT_COLOR};")

    def get_score_kpi_value(self):
        return self._score_kpi_value
    def set_score_kpi_value(self, value):
        # Kept for compatibility if anything else touches it, but unused for main score display now
        self._score_kpi_value = value
    score_kpi_value = Property(float, get_score_kpi_value, set_score_kpi_value)

    def _create_card(self, parent, title, icon_name=None):
        card_frame = QWidget(parent)
        card_frame.setObjectName("card")
        card_layout = QVBoxLayout(card_frame)
        card_layout.setContentsMargins(10, 10, 10, 10) 
        title_frame = QWidget()
        title_layout = QHBoxLayout(title_frame)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(5) 
        if icon_name:
            icon = qta.icon(icon_name, color=self.palette["ACCENT"])
            icon_label = QLabel()
            icon_label.setPixmap(icon.pixmap(QSize(20, 20))) 
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
        ref['label'].setFont(QFont("Bahnschrift", 16, QFont.Weight.Bold)) 
        ref['label'].setStyleSheet(f"color: {self.UNSELECTED_TEXT};")
        ref['label'].setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(ref['label'])
        ref['bar'] = QProgressBar()
        ref['bar'].setProperty("styleIdentifier", "blue")
        ref['bar'].setTextVisible(False)
        ref['bar'].setValue(0)
        content_layout.addWidget(ref['bar'])
        return ref
            
    def _control_fan(self, state):
        if self.gpio_handle is None: return
        try:
            if state: lgpio.tx_pwm(self.gpio_handle, FAN_PIN, PWM_FREQ, 100) 
            else: lgpio.tx_pwm(self.gpio_handle, FAN_PIN, PWM_FREQ, 0)
        except Exception as e: print(f"Fan Error: {e}")

    def _control_led(self, state):
        if self.gpio_handle is None: return
        try: lgpio.gpio_write(self.gpio_handle, LED_PIN, 1 if state else 0)
        except Exception as e: print(f"LED Error: {e}")

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
            except Exception: pass
        num = len(unique_ids)
        return f"{id_prefix_str}{num+1:04d}"

    def save_to_report(self, sample_id, sample, readings, quality):
        new_entry = [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), sample_id, sample] + readings + [quality]
        file_exists = os.path.exists(report_file)
        column_names = ["Timestamp", "Sample ID", "Type", "Temperature", "Humidity", "WHC Index", "Fatty Acid Profile", "Myoglobin", "MQ-137 (Ammonia)", "MQ-135 (Air Quality)", "MQ-3 (Alcohol)", "MQ-4 (Methane)", "Quality"]
        try:
            with open(report_file, "a", newline="") as f:
                writer = csv.writer(f)
                if not file_exists: writer.writerow(column_names)
                writer.writerow(new_entry)
        except Exception: pass

    def save_to_database_log(self, sample_id, all_raw_readings):
        header = ['sample_id', 'scan_iter', 'temp', 'hum', 'mq_137', 'mq_135', 'mq_4', 'mq_3'] + [f'as7265x_ch{i+1}' for i in range(18)] 
        try:
            file_exists = os.path.exists(DATABASE_LOG_FILE)
            with open(DATABASE_LOG_FILE, "a", newline="") as f:
                writer = csv.writer(f)
                if not file_exists: writer.writerow(header) 
                for idx, raw_readings in enumerate(all_raw_readings):
                    data_row = [sample_id, idx + 1, raw_readings.get('Temperature', 'N/A'), raw_readings.get('Humidity', 'N/A'), raw_readings.get('MQ-137 (Ammonia)', 'N/A'), raw_readings.get('MQ-135 (Air Quality)', 'N/A'), raw_readings.get('MQ-4 (Methane)', 'N/A'), raw_readings.get('MQ-3 (Alcohol)', 'N/A')]
                    for i in range(18): data_row.append(raw_readings.get(f'AS7265X_ch{i+1}', 'N/A'))
                    writer.writerow(data_row)
        except Exception: pass

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
        text = f"SCANNING (5x){dots:<4}"
        for key in self.raw_label_refs:
            if key not in ["Temperature", "Humidity", "WHC Index", "Fatty Acid Profile", "Myoglobin"]:
                current_text = self.raw_label_refs[key].text().split(':')[0]
                self.raw_label_refs[key].setText(f"{current_text}: {text}")
                self.raw_label_refs[key].setStyleSheet(f"color: {self.PRIMARY_COLOR};")
        if self.stream_dot_count % 2 == 0: self.status_light.setStyleSheet(f"background-color: {self.ACCENT_COLOR}; border-radius: 6px;") 
        else: self.status_light.setStyleSheet(f"background-color: {self.PRIMARY_COLOR}; border-radius: 6px;") 

    def animate_progress_bar(self, bar_widget, value):
        style_id = "red" if value < 40 else "orange" if value < 75 else "green"
        bar_widget.setProperty("styleIdentifier", style_id)
        bar_widget.style().unpolish(bar_widget)
        bar_widget.style().polish(bar_widget)
        anim = QPropertyAnimation(bar_widget, b"value", self)
        anim.setDuration(800)
        anim.setStartValue(0)
        anim.setEndValue(value)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start(QAbstractAnimation.DeleteWhenStopped)

    def clear_dashboard(self):
        global current_sample_id
        if hasattr(self, 'anim_score') and self.anim_score: self.anim_score.stop()
        self.streaming_timer.stop()
        self._control_fan(False) 
        self._control_led(False)
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
            group['bar'].setValue(0)
        self.status_light.setStyleSheet(f"background-color: {self.UNSELECTED_TEXT}; border-radius: 6px;") 
        self.raw_label_refs["Temperature"].setText("Temperature: -- °C")
        self.raw_label_refs["Humidity"].setText("Humidity: -- % RH")
        self.raw_label_refs["MQ-137 (Ammonia)"].setText("NH₃ (Ammonia): N/A V")
        self.raw_label_refs["MQ-135 (Air Quality)"].setText("Air Quality: N/A V")
        self.raw_label_refs["MQ-3 (Alcohol)"].setText("Alcohol: N/A V")
        self.raw_label_refs["MQ-4 (Methane)"].setText("CH₄ (Methane): N/A V")
        self.raw_label_refs["WHC Index"].setText("WHC Index: N/A")
        self.raw_label_refs["Fatty Acid Profile"].setText("FAC Index: N/A")
        self.raw_label_refs["Myoglobin"].setText("Myoglobin Index: N/A") 
        for label in self.raw_label_refs.values(): label.setStyleSheet(f"color: {self.TEXT_COLOR};")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        current_sample_id = None
        self.btn_run.setIcon(qta.icon('fa5s.play', color=self.btn_run_icon_color))
        self.btn_clear.setIcon(qta.icon('fa5s.broom', color=self.btn_clear_icon_color))
        self.btn_run.setEnabled(True)
        self.btn_purge.setEnabled(True) 
        self.btn_clear.setEnabled(True)

    @Slot(str)
    def handle_scan_error(self, error_message):
        self.streaming_timer.stop()
        self.btn_run.setIcon(qta.icon('fa5s.play', color=self.btn_run_icon_color))
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.score_display.setText("FAIL")
        self.score_display.setStyleSheet(f"color: {self.DANGER_COLOR}; background-color: transparent;")
        self.quality_label.setText("SENSOR ERROR")
        self.quality_label.setStyleSheet(f"color: {self.DANGER_COLOR};")
        self.status_light.setStyleSheet(f"background-color: {self.DANGER_COLOR}; border-radius: 6px;") 
        self._control_fan(False) 
        self._control_led(False)
        self.btn_run.setEnabled(True)
        self.btn_purge.setEnabled(True) 
        self.btn_clear.setEnabled(True)
        show_custom_message(self, "Sensor Error", f"Failed to read hardware sensors:\n{error_message}", "error", self.palette)