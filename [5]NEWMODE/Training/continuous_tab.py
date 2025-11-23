# continuous_tab.py

import sys
import os
import csv
import json
import qtawesome as qta
import time
import lgpio  # <-- Required for Fan and LED control
import statistics # For calculating standard deviation
from datetime import datetime
import re # For email validation
import smtplib # For sending email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders # For attaching file
from collections import deque # <-- ADDED: For graph data buffer
import math # <-- REMOVED: No longer needed for PPM

import pyqtgraph as pg # <-- ADDED: For graphing

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QTreeWidget, QTreeWidgetItem, QHeaderView,
    QFileDialog, QScrollArea, QLineEdit, QDialog,
    QGridLayout, QTextEdit, QProgressBar, QComboBox,
    QInputDialog, QFormLayout, QCheckBox, QApplication
)
from PySide6.QtCore import Qt, QTimer, QSize, QThread, QObject, Signal, Slot
from PySide6.QtGui import QColor, QBrush, QFont, QIcon

# --- 1. ADD PARENT DIR TO PATH ---
PARENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PARENT_DIR not in sys.path:
    sys.path.append(PARENT_DIR)
# -------------------------------

# --- 2. REAL SENSOR IMPORTS ---
try:
    from custom_dialog import show_custom_message, CustomDialog
    from Sensors.aht20 import read_aht20, UninitializedAHT20Error
    from Sensors.enose import read_enose, UninitializedENoseError
    from Sensors.as7265x import (
        read_spectrometer, as_led_on, as_led_off,
        as_uv_led_on, as_uv_led_off, as_ir_led_on, as_ir_led_off,
        UninitializedAS7265XError
    )
except ImportError as e:
    print(f"FATAL ERROR in continuous_tab.py: Could not import modules.")
    print(f"Make sure continuous_tab.py is in a folder, and 'Sensors' and 'custom_dialog.py' are in the parent folder.")
    print(f"Error: {e}")
    # Define dummy functions and exceptions if import fails, to prevent crash
    def as_led_on(): print("DUMMY: AS LED ON")
    def as_led_off(): print("DUMMY: AS LED OFF")
    def as_uv_led_on(): print("DUMMY: UV LED ON")
    def as_uv_led_off(): print("DUMMY: UV LED OFF")
    def as_ir_led_on(): print("DUMMY: IR LED ON")
    def as_ir_led_off(): print("DUMMY: IR LED OFF")
    if 'UninitializedAS7265XError' not in globals():
        class UninitializedAS7265XError(Exception): pass
    if 'UninitializedAHT20Error' not in globals():
        class UninitializedAHT20Error(Exception): pass
    if 'UninitializedENoseError' not in globals():
        class UninitializedENoseError(Exception): pass
# -------------------------------

# --- 3. SMTP Configuration ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "poultriscan4201@gmail.com"
SENDER_PASSWORD = "delzwnrbsyogigyt"
# --- END SMTP Configuration ---


# --- 4. File & Directory Definitions ---
# --- HARDWARE CONFIG ---
FAN_PIN = 27
LED_PIN = 17    # <-- 5050 White LED Strip
PWM_FREQ = 100
# --- End Hardware Config ---

TRAINING_ROOT_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(TRAINING_ROOT_DIR, "data")
BASELINE_DIR = os.path.join(DATA_DIR, "baselines")
REFS_DIR = os.path.join(DATA_DIR, "references")

# --- MODIFIED: Removed old file paths, added new raw file ---
BASELINE_COLLECTION_FILE = os.path.join(DATA_DIR, "baseline_collection.csv") # Kept for baseline history
CONTINUOUS_DATA_FILE = os.path.join(DATA_DIR, "continuous_averaged_data.csv") # Averaged 5-min data
CONTINUOUS_RAW_DATA_FILE = os.path.join(DATA_DIR, "continuous_raw_data.csv") # Raw 5-sec data
# --- END MODIFICATION ---

MQ_BASELINE_CURRENT_FILE = os.path.join(BASELINE_DIR, "mq_baseline_current.json")
AS_REFS_FILE = os.path.join(REFS_DIR, "as7265_refs.json")

# --- 5. CSV Headers ---

# --- MODIFIED: This header will be used for BOTH raw and averaged files for consistency ---
CANONICAL_HEADER = [
    "sample_id", "meat_type", "storage_type", "hour", "timestamp_iso", 
    "temp_c", "hum_pct",
    "frozen_age_days", "thaw_method", "time_since_thaw_min",
    # MODIFIED: MQ Raw Voltages (Rs)
    "mq137_v_rs", "mq135_v_rs", "mq4_v_rs", "mq3_v_rs",
    # MODIFIED: AS7265x Raw Channels
    "as_raw_ch1", "as_raw_ch2", "as_raw_ch3", "as_raw_ch4",
    "as_raw_ch5", "as_raw_ch6", "as_raw_ch7", "as_raw_ch8",
    "as_raw_ch9", "as_raw_ch10", "as_raw_ch11", "as_raw_ch12",
    "as_raw_ch13", "as_raw_ch14", "as_raw_ch15", "as_raw_ch16",
    "as_raw_ch17", "as_raw_ch18",
    "avg_valid", "cv_flag", "final_label", "ground_truth_value"
]

BASELINE_HEADER = [
    "timestamp_iso", "operator", "ambient_temp", "ambient_hum", 
    "baseline_mq137", "baseline_mq135", "baseline_mq4", "baseline_mq3"
] + [f"as_dark_ref_ch{i}" for i in range(1, 19)] \
  + [f"as_white_ref_ch{i}" for i in range(1, 19)]


# --- 6. Helper Functions ---

def _create_card(parent, title, palette, icon_name=None):
    card_frame = QWidget(parent)
    card_frame.setObjectName("card")
    card_layout = QVBoxLayout(card_frame)
    card_layout.setContentsMargins(15, 15, 15, 15)
    title_frame = QWidget()
    title_layout = QHBoxLayout(title_frame)
    title_layout.setContentsMargins(0, 0, 0, 0)
    title_layout.setSpacing(10)
    if icon_name:
        icon = qta.icon(icon_name, color=palette["ACCENT"])
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
    content_frame.setStyleSheet(f"background-color: {palette['SECONDARY_BG']};")
    card_layout.addWidget(content_frame, 1)
    return card_frame, content_frame

def _get_with_nan(data_dict, key):
    """Helper to get a value from a dict, returning 'NaN' instead of None."""
    val = data_dict.get(key)
    if val is None:
        return "NaN"
    return val

# --- REMOVED PPM CONVERSION FUNCTIONS ---
# -----------------------------------


# --- EmailWorker CLASS (Unchanged) ---
class EmailWorker(QObject):
    finished = Signal(str) 
    error = Signal(str, str)
    def __init__(self, recipient, palette, smtp_server, smtp_port, 
                 sender_email, sender_password, file_path_list, 
                 email_subject, email_body):
        super().__init__()
        self.recipient_email = recipient
        self.palette = palette
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.sender_password = sender_password
        self.file_paths = file_path_list
        self.email_subject = email_subject
        self.email_body = email_body

    @Slot()
    def run(self):
        try:
            message = MIMEMultipart()
            message['From'] = self.sender_email
            message['To'] = self.recipient_email
            message['Subject'] = self.email_subject
            message.attach(MIMEText(self.email_body, 'html'))
            
            for file_path in self.file_paths:
                if not os.path.exists(file_path):
                    print(f"Warning: File not found, skipping attachment: {file_path}")
                    continue
                
                with open(file_path, "rb") as attachment:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment.read())
                
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', f"attachment; filename= {os.path.basename(file_path)}")
                message.attach(part)

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(message)
            
            file_count = len(self.file_paths)
            self.finished.emit(f"{file_count} report(s) successfully sent to:\n{self.recipient_email}")
        except smtplib.SMTPAuthenticationError:
            self.error.emit("Email Error", "Authentication failed. Check SENDER_EMAIL/PASSWORD.")
        except Exception as e:
            self.error.emit("Email Error", f"An unexpected error occurred:\n{type(e).__name__}: {e}")
# --- END EmailWorker CLASS ---


# --- MultiCsvSelectDialog CLASS (Unchanged) ---
class MultiCsvSelectDialog(QDialog):
    def __init__(self, file_map, palette, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Files to Email")
        self.setMinimumWidth(400)
        
        self.file_map = file_map
        self.palette = palette
        self.checkboxes = {}
        self.selected_files = []

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {palette.get('BG', '#101218')};
                color: {palette.get('TEXT', '#E0E0E0')};
                font-family: 'Bahnschrift', 'Segoe UI', Arial, sans-serif;
            }}
            QLabel {{
                font-size: 16pt;
                color: {palette.get('TEXT', '#E0E0E0')};
                padding-bottom: 5px;
            }}
            QCheckBox {{
                font-size: 14pt;
                spacing: 10px;
                padding: 8px;
            }}
            QCheckBox::indicator {{
                width: 20px;
                height: 20px;
            }}
            QPushButton {{
                background-color: {palette.get('ACCENT', '#F0C419')};
                color: {palette.get('BUTTON_TEXT', palette.get('BG', '#101218'))};
                border: none;
                padding: 10px 20px;
                font-size: 14pt;
                font-weight: bold;
                border-radius: 5px;
            }}
            QPushButton:hover {{
                background-color: {palette.get('ACCENT_HOVER', '#FFD43A')};
            }}
            QPushButton#secondary {{
                background-color: {palette.get('SECONDARY_BG', '#1C1E24')};
                color: {palette.get('UNSELECTED_TEXT', '#888')};
            }}
            QPushButton#secondary:hover {{
                background-color: {palette.get('BORDER', '#2A2C33')};
            }}
        """)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        title_label = QLabel("Select Files to Email")
        main_layout.addWidget(title_label)
        checkbox_frame = QFrame()
        checkbox_layout = QVBoxLayout(checkbox_frame)
        for display_name, file_path in self.file_map.items():
            if os.path.exists(file_path):
                file_info = f"{display_name} ({os.path.basename(file_path)})"
            else:
                file_info = f"{display_name} (File not found)"
            cb = QCheckBox(file_info)
            cb.setChecked(True) # Default to checked
            if not os.path.exists(file_path):
                cb.setEnabled(False)
                cb.setToolTip("File does not exist and cannot be sent.")
            checkbox_layout.addWidget(cb)
            self.checkboxes[display_name] = cb
        main_layout.addWidget(checkbox_frame)
        select_layout = QHBoxLayout()
        select_layout.setSpacing(10)
        self.btn_select_all = QPushButton("Select All")
        self.btn_select_all.setObjectName("secondary")
        self.btn_select_all.clicked.connect(self.select_all)
        select_layout.addWidget(self.btn_select_all)
        self.btn_select_none = QPushButton("Select None")
        self.btn_select_none.setObjectName("secondary")
        self.btn_select_none.clicked.connect(self.select_none)
        select_layout.addWidget(self.btn_select_none)
        select_layout.addStretch()
        main_layout.addLayout(select_layout)
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.addStretch()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("secondary")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self.on_accept)
        button_layout.addWidget(self.send_btn)
        main_layout.addLayout(button_layout)
    @Slot()
    def select_all(self):
        for cb in self.checkboxes.values():
            if cb.isEnabled():
                cb.setChecked(True)
    @Slot()
    def select_none(self):
        for cb in self.checkboxes.values():
            cb.setChecked(False)
    @Slot()
    def on_accept(self):
        self.selected_files = []
        for display_name, cb in self.checkboxes.items():
            if cb.isChecked() and cb.isEnabled():
                self.selected_files.append(self.file_map[display_name])
        self.accept()
    def get_selected_files(self):
        return self.selected_files
# --- END MultiCsvSelectDialog CLASS ---


# --- CsvViewerDialog CLASS (Unchanged) ---
class CsvViewerDialog(QDialog):
    def __init__(self, palette, file_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"CSV Viewer: {os.path.basename(file_path)}")
        self.setMinimumSize(1000, 700)
        self.palette = palette
        self.file_path = file_path
        self.setStyleSheet(f"QDialog {{ background-color: {palette['BG']}; }}")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        title_label = QLabel(f"Data File: {os.path.basename(self.file_path)}")
        title_label.setObjectName("subtitle")
        main_layout.addWidget(title_label)
        self.tree = QTreeWidget()
        self.tree.setAlternatingRowColors(True)
        self.tree.setSortingEnabled(True)
        main_layout.addWidget(self.tree, 1)
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.close_btn = QPushButton(" Close")
        self.close_btn.setObjectName("secondary")
        self.close_btn.setIcon(qta.icon('fa5s.times', color=palette["UNSELECTED_TEXT"]))
        self.close_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.close_btn)
        main_layout.addLayout(button_layout)
    def load_csv_data(self):
        self.tree.clear()
        if not os.path.exists(self.file_path):
            item = QTreeWidgetItem(self.tree, [f"Error: '{os.path.basename(self.file_path)}' not found."])
            item.setForeground(0, QBrush(QColor(self.palette["DANGER"])))
            return
        try:
            with open(self.file_path, "r", newline="", encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                try:
                    header = next(reader)
                    self.tree.setColumnCount(len(header))
                    self.tree.setHeaderLabels(header)
                except StopIteration:
                    self.tree.setHeaderLabels(["File is empty."])
                    return
                rows_to_insert = []
                for row in reader:
                    if row:
                        rows_to_insert.append(row)
            if not rows_to_insert:
                item = QTreeWidgetItem(self.tree, ["No data records found."])
                item.setForeground(0, QBrush(QColor(self.palette["UNSELECTED_TEXT"])))
            else:
                for data in rows_to_insert:
                    item = QTreeWidgetItem(self.tree, data)
            for i in range(self.tree.columnCount()):
                self.tree.header().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        except Exception as e:
            self.tree.clear()
            item = QTreeWidgetItem(self.tree, [f"Error reading file: {e}"])
            item.setForeground(0, QBrush(QColor(self.palette["DANGER"])))
# --- END CsvViewerDialog CLASS ---


# --- REAL MQ BASELINE WORKER (Unchanged) ---
class MQBaselineWorker(QObject):
    finished = Signal(dict)
    progress = Signal(int)
    error = Signal(str)
    def __init__(self, duration_sec=30, interval_sec=1):
        super().__init__()
        self.duration = duration_sec
        self.interval = interval_sec
        self._is_running = True
    @Slot()
    def run(self):
        try:
            # Using MQ4 and MQ3
            readings = {"mq137": [], "mq135": [], "mq4": [], "mq3": [], "temp": [], "hum": []}
            num_steps = int(self.duration / self.interval)
            for i in range(num_steps):
                if not self._is_running:
                    self.error.emit("Baseline cancelled")
                    return
                mq_data = read_enose()
                aht_data = read_aht20()
                readings["mq137"].append(mq_data["MQ-137 (Ammonia)"])
                readings["mq135"].append(mq_data["MQ-135 (Air Quality)"])
                readings["mq4"].append(mq_data["MQ-4 (Methane)"])
                readings["mq3"].append(mq_data["MQ-3 (Alcohol)"])
                readings["temp"].append(aht_data["Temperature"])
                readings["hum"].append(aht_data["Humidity"])
                time.sleep(self.interval)
                self.progress.emit(i + 1)
            final_baseline = {
                "baseline_mq137": statistics.mean(readings["mq137"]),
                "baseline_mq135": statistics.mean(readings["mq135"]),
                "baseline_mq4": statistics.mean(readings["mq4"]),
                "baseline_mq3": statistics.mean(readings["mq3"]),
                "baseline_timestamp": datetime.now().isoformat(),
                "operator": "system",
                "ambient_temp": statistics.mean(readings["temp"]),
                "ambient_hum": statistics.mean(readings["hum"])
            }
            self.finished.emit(final_baseline)
        except (UninitializedAHT20Error, UninitializedENoseError) as e:
            self.error.emit(f"Hardware Error: {e}")
        except Exception as e:
            self.error.emit(f"MQ Baseline failed: {e}")
    def stop(self):
        self._is_running = False
# --- END MQBaselineWorker ---


# --- 7. REVISED: CONTINUOUS MEASUREMENT WORKER ---
class ContinuousMeasurementWorker(QObject):
    """
    Worker to continuously measure sensors every 5 seconds (raw file) and
    average in 60-sample (5-minute) chunks (averaged file).
    """
    update_status = Signal(str)
    averaged_update = Signal(dict) # <-- RENAMED: Emits the 5-min averaged data row
    raw_data_update = Signal(dict) # <-- ADDED: Emits the raw 5-sec data
    error = Signal(str)
    request_led_control = Signal(bool)
    finished = Signal() # <-- **** FIX 1.1: ADDED THIS SIGNAL ****
    
    def __init__(self, sample_info, mq_baseline, as_refs, window_size=60, interval_sec=5):
        super().__init__()
        self.sample_info = sample_info
        self.mq_baseline = mq_baseline
        # self.as_refs = as_refs # No longer used
        self.window_size = window_size
        self.interval_sec = interval_sec
        self._is_running = True
        
        # --- MODIFIED: Initialize lists for chunk averaging ---
        self.temp_buffer = []
        self.hum_buffer = []
        
        self.mq_buffers = {
            "mq137_v_rs": [],
            "mq135_v_rs": [],
            "mq4_v_rs": [],
            "mq3_v_rs": []
        }
        
        self.as_buffers = {
            f"as_raw_ch{i}": [] for i in range(1, 19)
        }
        # --- End buffer initialization ---

    def _write_csv_row(self, file_path, header, data_row):
        """Helper to append a row to a CSV file."""
        try:
            file_exists = os.path.exists(file_path)
            with open(file_path, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=header)
                if not file_exists:
                    writer.writeheader()
                # Filter row to only include keys present in the header
                filtered_row = {h: _get_with_nan(data_row, h) for h in header}
                writer.writerow(filtered_row)
        except Exception as e:
            # Emit error but don't crash the worker
            self.error.emit(f"CSV Write Error ({os.path.basename(file_path)}): {e}")

    @Slot()
    def run(self):
        """Runs the continuous measurement loop."""
        
        # --- 1. Get Baseline (Ro) Values ---
        # Note: These are still loaded but no longer used for PPM calculation.
        # Kept in case user wants to calculate Rs/Ro in post-processing.
        r_o_mq137 = self.mq_baseline.get("baseline_mq137", 1.0)
        r_o_mq135 = self.mq_baseline.get("baseline_mq135", 1.0)
        r_o_mq4 = self.mq_baseline.get("baseline_mq4", 1.0)
        r_o_mq3 = self.mq_baseline.get("baseline_mq3", 1.0)
        
        # --- REMOVED AS_REFS ---
        
        self.update_status.emit(f"Starting continuous monitoring. (Interval: {self.interval_sec}s, Chunk Size: {self.window_size} samples)")

        try:
            while self._is_running:
                loop_start_time = time.time()
                current_timestamp = datetime.now().isoformat()
                
                # --- 2. Take a single 5-second reading ---
                self.update_status.emit("Reading sensors (5s interval)...")
                self.request_led_control.emit(True)
                as_led_on()
                
                # --- **** EDITED: Reduced sleep from 1.5s to 0.5s **** ---
                time.sleep(0.5) # Stabilize
                
                mq_data = read_enose()
                aht_data = read_aht20()
                spec_data_white = read_spectrometer()
                
                as_led_off()
                self.request_led_control.emit(False)
                
                # --- 3. Process the single reading ---
                
                # AHT20
                current_temp = aht_data["Temperature"]
                current_hum = aht_data["Humidity"]
                
                # MODIFIED: eNose (Get raw Rs voltage)
                current_mq_voltages = {
                    "mq137_v_rs": mq_data.get("MQ-137 (Ammonia)", 0),
                    "mq135_v_rs": mq_data.get("MQ-135 (Air Quality)", 0),
                    "mq4_v_rs": mq_data.get("MQ-4 (Methane)", 0),
                    "mq3_v_rs": mq_data.get("MQ-3 (Alcohol)", 0)
                }
                
                # --- REMOVED PPM CALCULATION ---
                
                # MODIFIED: AS7265x (Get Raw Counts)
                current_as_raw = {}
                for i in range(1, 19):
                    ch_key_raw = f"AS7265X_ch{i}"
                    ch_key_final = f"as_raw_ch{i}"
                    current_as_raw[ch_key_final] = spec_data_white.get(ch_key_raw, 0.0)
                
                # --- REMOVED REFLECTANCE CALCULATION ---

                # --- 4A. Store raw 5-second data ---
                self.update_status.emit("Saving raw 5-sec data...")
                raw_data_row = {}
                raw_data_row.update(self.sample_info) # Add ID, meat_type, etc.
                raw_data_row.update({
                    "timestamp_iso": current_timestamp,
                    "temp_c": current_temp,
                    "hum_pct": current_hum,
                    "final_label": "RAW_5_SEC",
                    "avg_valid": False,
                    "cv_flag": "N/A",
                    "ground_truth_value": "N/A"
                })
                raw_data_row.update(current_mq_voltages) # Add mq137_v_rs, ...
                raw_data_row.update(current_as_raw) # Add as_raw_ch1, ...
                
                # Write to the raw CSV file
                self._write_csv_row(CONTINUOUS_RAW_DATA_FILE, CANONICAL_HEADER, raw_data_row)
                
                # --- ADDED: Emit raw data for graph/labels ---
                self.raw_data_update.emit(raw_data_row)
                
                # --- 4B. Add single reading to averaging buffers ---
                self.temp_buffer.append(current_temp)
                self.hum_buffer.append(current_hum)
                for key, val in current_mq_voltages.items():
                    if key in self.mq_buffers:
                        self.mq_buffers[key].append(val)
                for key, val in current_as_raw.items():
                    if key in self.as_buffers:
                        self.as_buffers[key].append(val)

                # --- 5. MODIFIED: Check if buffer is full, average, and CLEAR (Tumbling Window) ---
                if len(self.temp_buffer) == self.window_size:
                    self.update_status.emit(f"Buffer full. Averaging {self.window_size}-sample (5-min) chunk...")
                    
                    avg_data_row = {}
                    avg_data_row.update(self.sample_info)
                    avg_data_row.update({
                        "timestamp_iso": current_timestamp, # Use timestamp of the *last* reading
                        "frozen_age_days": self.sample_info.get("frozen_age_days", "N/A"),
                        "thaw_method": self.sample_info.get("thaw_method", "N/A"),
                        "time_since_thaw_min": self.sample_info.get("time_since_thaw_min", "N/A"),
                        "final_label": "AVG_5_MIN",
                        "avg_valid": True,
                        "cv_flag": "N/A",
                        "ground_truth_value": "N/A"
                    })
                    
                    # Add averaged sensor data
                    avg_data_row["temp_c"] = statistics.mean(self.temp_buffer)
                    avg_data_row["hum_pct"] = statistics.mean(self.hum_buffer)
                    for key, buf in self.mq_buffers.items():
                        avg_data_row[key] = statistics.mean(buf)
                    for key, buf in self.as_buffers.items():
                        avg_data_row[key] = statistics.mean(buf)
                        
                    # Write to the averaged CSV file
                    self._write_csv_row(CONTINUOUS_DATA_FILE, CANONICAL_HEADER, avg_data_row)

                    # Emit the averaged data for the UI
                    self.averaged_update.emit(avg_data_row) # <-- RENAMED signal
                    
                    # --- NEW: Clear buffers for next chunk ---
                    self.update_status.emit("Buffers cleared. Starting new 5-min chunk.")
                    self.temp_buffer.clear()
                    self.hum_buffer.clear()
                    for buf in self.mq_buffers.values():
                        buf.clear()
                    for buf in self.as_buffers.values():
                        buf.clear()
                    # --- END NEW ---
                
                else:
                    samples_needed = self.window_size - len(self.temp_buffer)
                    self.update_status.emit(f"Collecting 5-min chunk... {samples_needed} samples remaining.")

                
                # --- 6. Wait for next interval (MODIFIED FOR RESPONSIVE STOP) ---
                elapsed = time.time() - loop_start_time
                sleep_time = self.interval_sec - elapsed

                if sleep_time > 0:
                    # Sleep in small 100ms chunks to check the stop flag
                    chunk_sleep = 0.1 
                    num_chunks = int(sleep_time / chunk_sleep)
                    
                    for _ in range(num_chunks):
                        if not self._is_running:
                            # Stop signal received, exit the sleep loop
                            break 
                        time.sleep(chunk_sleep)
                    
                    # Sleep for any remaining fractional time
                    if self._is_running:
                        remaining_sleep = sleep_time - (num_chunks * chunk_sleep)
                        if remaining_sleep > 0:
                            time.sleep(remaining_sleep)
                
                # After sleeping (or breaking early), the 'while self._is_running:'
                # loop will check the flag again and exit properly.
                

        except (UninitializedAHT20Error, UninitializedENoseError, UninitializedAS7265XError) as e:
            self.error.emit(f"Hardware Error: {e}")
        except Exception as e:
            self.error.emit(f"Measurement failed: {e}")
        finally:
            # --- FIX: Turn off ALL LEDs on exit/error ---
            as_led_off()
            as_uv_led_off()
            as_ir_led_off()
            self.request_led_control.emit(False)
            
            self.finished.emit() # <-- **** FIX 1.2: EMIT THE SIGNAL ****
            
    def stop(self):
        self.update_status.emit("Stop signal received. Finishing last loop...")
        self._is_running = False
# --- END ContinuousMeasurementWorker ---


# --- NEW: DYNAMIC PURGE WORKER ---
class PurgeWorker(QObject):
    finished = Signal()
    update_status = Signal(str)
    error = Signal(str)

    def __init__(self, baseline_data, tolerance_pct=5.0, interval_sec=3):
        """
        Worker to purge the chamber until MQ sensors return to baseline.

        :param baseline_data: The dictionary from the initial MQ baseline run.
        :param tolerance_pct: The allowed percentage (e.g., 5.0) from baseline.
        :param interval_sec: How often to check the sensors (in seconds).
        """
        super().__init__()
        self.baseline = baseline_data
        self.tolerance_val = tolerance_pct / 100.0
        self.interval_sec = interval_sec
        self._is_running = True

        # Get baseline target values, with a default fallback
        self.baseline_targets = {
            "MQ-137 (Ammonia)": self.baseline.get("baseline_mq137", 1.0),
            "MQ-135 (Air Quality)": self.baseline.get("baseline_mq135", 1.0),
            "MQ-4 (Methane)": self.baseline.get("baseline_mq4", 1.0),
            "MQ-3 (Alcohol)": self.baseline.get("baseline_mq3", 1.0),
        }
        
        self.update_status.emit(f"Dynamic Purge: Target tolerance +/- {tolerance_pct:.1f}%")

    def _is_at_baseline(self, current_val, target_val):
        """Checks if current value is within the tolerance range of the target."""
        if target_val == 0: # Avoid division by zero
            return current_val == 0
            
        low_bound = target_val * (1.0 - self.tolerance_val)
        high_bound = target_val * (1.0 + self.tolerance_val)
        return low_bound <= current_val <= high_bound

    @Slot()
    def run(self):
        try:
            self.update_status.emit("Starting dynamic purge. Fan ON.")
            
            while self._is_running:
                # 1. Read the sensors
                mq_data = read_enose()
                
                at_baseline_flags = {}
                status_msgs = []
                all_at_baseline = True
                
                # 2. Compare each sensor to its baseline target
                for key, target_val in self.baseline_targets.items():
                    current_val = mq_data.get(key, 0.0)
                    is_met = self._is_at_baseline(current_val, target_val)
                    
                    at_baseline_flags[key] = is_met
                    if not is_met:
                        all_at_baseline = False
                        
                    # Create a status message for logging
                    key_short = key.split(' ')[0] # "MQ-137"
                    status_msgs.append(f"{key_short}: {current_val:.3f}V (Tgt: {target_val:.3f}V) [{'+' if is_met else '-'}]")
                
                # 3. Log the current status
                log_msg = " | ".join(status_msgs)
                self.update_status.emit(f"Purging... {log_msg}")
                
                # 4. Check if all sensors have met the target
                if all_at_baseline:
                    self.update_status.emit("All sensors have returned to baseline. Purge complete.")
                    break # Exit the while loop
                    
                # 5. Wait for the next interval
                time.sleep(self.interval_sec)
                
            # After loop (either 'break' or 'stop' was called)
            if self._is_running:
                self.finished.emit() # Signal normal completion
            else:
                self.update_status.emit("Purge cancelled by user.")
                
        except UninitializedENoseError as e:
            self.error.emit(f"Hardware Error during purge: {e}")
        except Exception as e:
            self.error.emit(f"Purge worker failed: {e}")
    
    def stop(self):
        self._is_running = False
# --- END DYNAMIC PURGE WORKER ---


# --- 10. REVISED: Simplified SampleDialog ---
class SampleDialog(QDialog):
    def __init__(self, palette, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Enter New Sample Details")
        self.palette = palette
        self.setStyleSheet(f"QDialog {{ background-color: {palette['BG']}; }}")
        self.setMinimumWidth(500)

        self.existing_samples = {} # Still needed to find next replica
        self.sample_info = {}
        
        main_layout = QVBoxLayout(self)
        
        form_layout = QFormLayout()
        form_layout.setSpacing(15)
        
        self.new_sample_frame = QFrame()
        self.new_sample_layout = QFormLayout(self.new_sample_frame)
        self.new_sample_layout.setContentsMargins(0, 10, 0, 0)
        
        self.meat_type_combo = QComboBox()
        self.meat_type_combo.addItems(["Breast", "Thigh", "Wing"])
        self.new_sample_layout.addRow("Meat Type:", self.meat_type_combo)
        
        self.storage_combo = QComboBox()
        self.storage_combo.addItems(["Room", "Chilled", "Frozen"])
        self.new_sample_layout.addRow("Storage Type:", self.storage_combo)
        
        form_layout.addRow(self.new_sample_frame)
        
        self.hour_label = QLabel("Starting new continuous run.") # Simplified
        self.hour_label.setStyleSheet(f"font: bold 14pt 'Bahnschrift'; color: {palette['ACCENT']};")
        form_layout.addRow(self.hour_label)
        
        main_layout.addLayout(form_layout)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("secondary")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)
        self.proceed_btn = QPushButton("Proceed")
        self.proceed_btn.clicked.connect(self.on_proceed)
        btn_layout.addWidget(self.proceed_btn)
        main_layout.addLayout(btn_layout)
        
        self.load_existing_samples() # Load samples to find next ID

    def load_existing_samples(self):
        """Loads existing samples to determine the next available replica number."""
        self.existing_samples = {}
        
        # Check both new files for existing IDs
        files_to_check = [CONTINUOUS_RAW_DATA_FILE, CONTINUOUS_DATA_FILE] 
        
        for file_path in files_to_check:
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8-sig') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            sample_id = row.get("sample_id")
                            if sample_id:
                                # Just need to know the ID exists
                                self.existing_samples[sample_id] = True 
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")

    def _create_new_sample_info(self, m_type, s_type):
        type_map = {"Breast": "BRE", "Thigh": "THI", "Wing": "WNG"}
        storage_map = {"Room": "RT", "Chilled": "CH", "Frozen": "FR"}
        id_prefix = f"{type_map[m_type]}_{storage_map[s_type]}_"
        
        max_replica = 0
        for sample_id in self.existing_samples:
            if sample_id.startswith(id_prefix):
                try:
                    replica_num_str = sample_id.split('_')[-1]
                    replica_num = int(replica_num_str)
                    if replica_num > max_replica:
                        max_replica = replica_num
                except (ValueError, IndexError):
                    continue
                    
        new_replica_num = max_replica + 1
        new_replica_str = f"{new_replica_num:02d}"
        sample_id = f"{id_prefix}{new_replica_str}"
        
        # 'hour' is 0 by default, but may be updated by user for frozen samples
        return {
            "id": sample_id, "meat_type": m_type, "storage": s_type,
            "replica": new_replica_str, "hour": 0, "is_new": True
        }

    @Slot()
    def on_proceed(self):
        """Always creates a new sample."""
        m_type = self.meat_type_combo.currentText()
        s_type = self.storage_combo.currentText()
        self.sample_info = self._create_new_sample_info(m_type, s_type)
        self.accept()

    def get_sample_info(self):
        return self.sample_info
# --- END SampleDialog ---


# --- Main Continuous Tab ---
class ContinuousTab(QWidget):
    # MODIFIED: Removed Ref states
    # States
    STATE_LOCKED = 0
    STATE_NEEDS_INIT = 1
    STATE_PRE_PURGE = 2
    STATE_INITIALIZING_MQ = 3
    # STATE_NEEDS_DARK_REF = 4  <-- REMOVED
    # STATE_NEEDS_WHITE_REF = 5 <-- REMOVED
    STATE_READY_TO_MEASURE = 6
    STATE_MEASURING = 8
    STATE_PURGING = 9  # <-- ADDED
    
    # --- ADDED: Graph buffer length ---
    BUFFER_LEN = 100 # Store 100 data points for graphs
    
    def __init__(self, palette, main_window, gpio_handle, parent=None):
        super().__init__(parent)
        self.palette = palette
        self.main_window = main_window
        self.gpio_handle = gpio_handle  # Shared handle for Fan & LED
        self.current_state = self.STATE_LOCKED
        self.mq_baseline = {}
        self.as_refs = {}
        self.current_sample = {}
        self.baseline_worker = None
        self.baseline_thread = None
        self.continuous_worker = None
        self.continuous_thread = None
        self.purge_worker = None     # <-- ADDED
        self.purge_thread = None     # <-- ADDED
        self.email_thread = None
        self.email_worker = None
        self.processing_dialog = None
        
        # --- ADDED: Graph data buffers ---
        self.plot_time_counter = 0
        self.time_data = deque(maxlen=self.BUFFER_LEN)
        self.mq_data = {
            "mq137_v_rs": deque(maxlen=self.BUFFER_LEN),
            "mq135_v_rs": deque(maxlen=self.BUFFER_LEN),
            "mq4_v_rs": deque(maxlen=self.BUFFER_LEN),
            "mq3_v_rs": deque(maxlen=self.BUFFER_LEN)
        }
        self.as_data = {f"as_raw_ch{i}": deque(maxlen=self.BUFFER_LEN) for i in range(1, 19)}
        
        # --- REMOVED: pg.setConfigOption (moved to app.py) ---
        
        for d in [DATA_DIR, BASELINE_DIR, REFS_DIR]:
            os.makedirs(d, exist_ok=True)
            
        # --- 1. Create the main layout for the Tab itself ---
        tab_layout = QVBoxLayout(self)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        
        # --- 2. Create the Scroll Area ---
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        # Add border: none; to avoid a double-border look
        scroll_area.setStyleSheet("QScrollArea { border: none; }") 
        
        # --- 3. Create the widget that will be scrolled ---
        scroll_content_widget = QWidget()
        
        # --- 4. This is the layout that was previously the main layout ---
        #    (Note: It's now applied to scroll_content_widget, NOT self)
        main_layout = QVBoxLayout(scroll_content_widget) 
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # --- Lock Frame (Unchanged) ---
        self.lock_frame = QFrame()
        self.lock_frame.setStyleSheet(f"background-color: {palette['BG']};")
        lock_layout = QVBoxLayout(self.lock_frame)
        lock_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lock_layout.setSpacing(20)
        lock_label = QLabel("Continuous Mode Locked")
        lock_label.setObjectName("subtitle")
        lock_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lock_layout.addWidget(lock_label)
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Enter password...")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setMinimumWidth(400)
        self.password_input.returnPressed.connect(self.check_password)
        lock_layout.addWidget(self.password_input, 0, Qt.AlignmentFlag.AlignCenter)
        self.unlock_button = QPushButton(" UNLOCK")
        self.unlock_button.setIcon(qta.icon('fa5s.lock-open', color=palette.get("BUTTON_TEXT", palette["BG"])))
        self.unlock_button.clicked.connect(self.check_password)
        lock_layout.addWidget(self.unlock_button, 0, Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.lock_frame)
        
        # --- Main Frame ---
        self.main_frame = QWidget()
        main_frame_layout = QGridLayout(self.main_frame)
        main_frame_layout.setContentsMargins(10, 10, 10, 10)
        main_frame_layout.setSpacing(15)
        
        # --- **** MODIFIED: LOG CARD (TOP-LEFT) **** ---
        log_card, log_frame = _create_card(self.main_frame, " Continuous Log", palette, "fa5s.stream")
        log_layout = QVBoxLayout(log_frame)
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setFont(QFont("Consolas", 14))
        log_layout.addWidget(self.log_display)
        main_frame_layout.addWidget(log_card, 0, 0, 1, 1) # Row 0, Col 0
        
        # --- **** MODIFIED: STATUS CARD (TOP-RIGHT) **** ---
        status_card, status_frame = _create_card(self.main_frame, " Status & Controls", palette, "fa5s.tasks")
        status_layout = QVBoxLayout(status_frame)
        status_layout.setSpacing(15)
        self.status_label = QLabel("Enter password to unlock.")
        self.status_label.setFont(QFont("Bahnschrift", 18, QFont.Weight.Bold))
        self.status_label.setWordWrap(True)
        status_layout.addWidget(self.status_label)
        
        # --- REVISED: Live Data Display Area for Volts ---
        self.live_data_scroll = QScrollArea()
        self.live_data_scroll.setWidgetResizable(True)
        self.live_data_scroll.setObjectName("liveDataScroll")
        live_data_container = QWidget()
        self.live_data_layout = QFormLayout(live_data_container)
        self.live_data_layout.setContentsMargins(10, 10, 10, 10)
        self.live_data_layout.setSpacing(8)
        self.live_data_scroll.setWidget(live_data_container)
        status_layout.addWidget(self.live_data_scroll, 1) # Add with stretch factor
        
        self.live_data_widgets = {}
        live_data_font = QFont("Consolas", 16, QFont.Weight.Bold)
        
        # MODIFIED: Updated keys and display names
        live_data_keys = [
            ("temp_c", "Temp (°C)"), 
            ("hum_pct", "Humidity (%)"),
            ("mq137_v_rs", "MQ-137 (Volts)"),
            ("mq135_v_rs", "MQ-135 (Volts)"),
            ("mq4_v_rs", "MQ-4 (Volts)"),
            ("mq3_v_rs", "MQ-3 (Volts)")
        ]
        
        for key, display_name in live_data_keys:
            label = QLabel("---")
            label.setFont(live_data_font)
            label.setStyleSheet(f"color: {self.palette['ACCENT_HOVER']};")
            self.live_data_layout.addRow(f"{display_name}:", label)
            self.live_data_widgets[key] = label
        
        self.live_data_scroll.setVisible(False) # Hide by default
        # --- END: Live Data Display Area ---
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        status_layout.addWidget(self.progress_bar)
        
        self.action_button = QPushButton("Unlock")
        self.action_button.clicked.connect(self.on_action_button_click)
        status_layout.addWidget(self.action_button)
        
        status_layout.addStretch(0) # Remove stretch from here
        
        data_control_layout = QGridLayout()
        data_control_layout.setSpacing(10)
        self.btn_view_csv = QPushButton(" VIEW DATA")
        self.btn_view_csv.setObjectName("secondary")
        self.btn_view_csv.setIcon(qta.icon('fa5s.table', color=palette["UNSELECTED_TEXT"]))
        self.btn_view_csv.clicked.connect(self.show_csv_viewer)
        data_control_layout.addWidget(self.btn_view_csv, 0, 0, 1, 2)
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("recipient@example.com")
        data_control_layout.addWidget(self.email_input, 1, 0, 1, 1)
        self.btn_email_csv = QPushButton(" EMAIL DATA")
        self.btn_email_csv.setIcon(qta.icon('fa5s.paper-plane', color=palette.get("BUTTON_TEXT", palette["BG"])))
        self.btn_email_csv.clicked.connect(self.email_csv_file)
        data_control_layout.addWidget(self.btn_email_csv, 1, 1, 1, 1)
        status_layout.addLayout(data_control_layout)
        
        self.btn_exit_training = QPushButton(" EXIT MODE")
        self.btn_exit_training.setObjectName("danger")
        self.btn_exit_training.setIcon(qta.icon('fa5s.times-circle', color=palette.get("DANGER_TEXT", palette["TEXT"])))
        self.btn_exit_training.clicked.connect(self.exit_training_mode)
        status_layout.addWidget(self.btn_exit_training)
        
        main_frame_layout.addWidget(status_card, 0, 1, 1, 1) # Row 0, Col 1
        
        # --- **** MODIFIED: GRAPH CARD (BOTTOM) **** ---
        graph_card, graph_frame = _create_card(self.main_frame, " Real-Time Sensor Data", palette, "fa5s.chart-line")
        graph_layout = QVBoxLayout(graph_frame)
        graph_layout.setContentsMargins(0, 0, 0, 0)
        self.graph_widget = pg.GraphicsLayoutWidget()
        graph_layout.addWidget(self.graph_widget)
        main_frame_layout.addWidget(graph_card, 1, 0, 1, 2) # Row 1, Col 0, Span 2
        
        # --- Setup MQ Plot ---
        self.mq_plot = self.graph_widget.addPlot(row=0, col=0, title="MQ Sensor Voltages (V)")
        self.mq_plot.addLegend(offset=(1, 1), brush=pg.mkBrush(self.palette.get('BG', '#101218')), labelTextColor=self.palette.get('TEXT', '#E0E0E0'))
        self.mq_plot.showGrid(x=True, y=True, alpha=0.3)
        self.mq_plot_lines = {}
        mq_colors = ['#FF0000', '#00FF00', '#0000FF', '#FFFF00'] # R, G, B, Y
        mq_keys = ["mq137_v_rs", "mq135_v_rs", "mq3_v_rs", "mq4_v_rs"]
        for i, key in enumerate(mq_keys):
            self.mq_plot_lines[key] = self.mq_plot.plot(pen=pg.mkPen(color=mq_colors[i], width=2), name=key.split('_')[0].upper())
        
        # --- Setup AS Plot ---
        self.as_plot = self.graph_widget.addPlot(row=0, col=1, title="AS7265x Key Channels (Raw Counts)") # <-- MODIFIED: col=1
        self.as_plot.addLegend(offset=(1, 1), brush=pg.mkBrush(self.palette.get('BG', '#101218')), labelTextColor=self.palette.get('TEXT', '#E0E0E0'))
        self.as_plot.showGrid(x=True, y=True, alpha=0.3)
        self.as_plot_lines = {}
        # Plot 4 key channels: UV, Green, Red, IR
        as_keys_to_plot = {"as_raw_ch1": "410nm (UV)", "as_raw_ch6": "535nm (Green)", "as_raw_ch9": "610nm (Red)", "as_raw_ch15": "810nm (IR)"}
        as_colors = ['#9900FF', '#00FF00', '#FF0000', '#AAAAAA'] # Violet, Green, Red, Gray
        i = 0
        for key, name in as_keys_to_plot.items():
            self.as_plot_lines[key] = self.as_plot.plot(pen=pg.mkPen(color=as_colors[i], width=2), name=name)
            i += 1
        # ---------------------------
        
        # --- MODIFIED: Updated layout stretch factors ---
        main_frame_layout.setColumnStretch(0, 2) # Log area gets 2x stretch
        main_frame_layout.setColumnStretch(1, 1) # Control area gets 1x stretch
        main_frame_layout.setRowStretch(0, 1) # Top row (log/controls) gets 1x stretch
        main_frame_layout.setRowStretch(1, 2) # Bottom row (graph) gets 2x stretch
        
        self.main_frame.setVisible(False)
        main_layout.addWidget(self.main_frame, 1)
        
        # --- 5. Set the content widget for the scroll area ---
        scroll_area.setWidget(scroll_content_widget)
        
        # --- 6. Add the scroll area to the tab's main layout ---
        tab_layout.addWidget(scroll_area)
        
        self.set_state(self.STATE_LOCKED)

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_display.append(f"[{timestamp}] {message}")

    def set_state(self, state):
        self.current_state = state
        self.progress_bar.setVisible(False)
        self.action_button.setEnabled(True)
        self.action_button.setIcon(QIcon())
        
        data_buttons_enabled = (state != self.STATE_LOCKED and state != self.STATE_MEASURING and state != self.STATE_PURGING)
        self.btn_view_csv.setEnabled(data_buttons_enabled)
        self.email_input.setEnabled(data_buttons_enabled)
        self.btn_email_csv.setEnabled(data_buttons_enabled)
        self.btn_exit_training.setEnabled(data_buttons_enabled)
        self.live_data_scroll.setVisible(False)
        
        if state == self.STATE_LOCKED:
            self.status_label.setText("Enter password to unlock.")
            self.action_button.setText("Unlock")
            self.password_input.clear()
            self.password_input.setFocus()
            self.main_frame.setVisible(False)
            self.lock_frame.setVisible(True)
        elif state == self.STATE_NEEDS_INIT:
            self.status_label.setText("System unlocked. Ready to initialize sensors.")
            self.action_button.setText(" START INITIALIZATION")
            self.action_button.setIcon(qta.icon('fa5s.power-off', color=self.palette.get("BUTTON_TEXT", self.palette["BG"])))
            self.main_frame.setVisible(True)
            self.lock_frame.setVisible(False)
            self.log("System Unlocked. Ready for Initialization.")
        elif state == self.STATE_PRE_PURGE:
            self.status_label.setText("Pre-baseline purge (10s)... Fan ON.")
            self.action_button.setEnabled(False)
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)
            self.log("Starting Pre-baseline purge (10s)...")
        elif state == self.STATE_INITIALIZING_MQ:
            self.status_label.setText("Recording 30s MQ baseline... Please wait.")
            self.action_button.setEnabled(False)
            self.action_button.setText(" RECORDING...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 30)
            self.progress_bar.setValue(0)
            self.log("Starting 30s MQ Baseline...")
        # --- REMOVED DARK/WHITE REF STATES ---
        elif state == self.STATE_READY_TO_MEASURE:
            self.status_label.setText("Initialization Complete. Ready to measure sample.")
            self.action_button.setText(" START CONTINUOUS MONITORING")
            self.action_button.setIcon(qta.icon('fa5s.play', color=self.palette.get("BUTTON_TEXT", self.palette["BG"])))
            # Reset live data labels
            for label_widget in self.live_data_widgets.values():
                label_widget.setText("---")
            # --- ADDED: Clear plots ---
            self.clear_plots()
        elif state == self.STATE_MEASURING:
            self.status_label.setText(f"Continuously monitoring {self.current_sample.get('id', 'sample')}...")
            self.action_button.setText(" STOP MONITORING")
            self.action_button.setIcon(qta.icon('fa5s.stop', color=self.palette.get("BUTTON_TEXT", self.palette["BG"])))
            self.action_button.setEnabled(True) # Stop button must be enabled
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0) # Indeterminate
            self.live_data_scroll.setVisible(True)
            self.btn_exit_training.setEnabled(False) # Don't allow exit while measuring
        elif state == self.STATE_PURGING: # <-- ADDED THIS BLOCK
            self.status_label.setText("Purging chamber... Waiting for sensors to reach baseline.")
            self.action_button.setText(" PURGING...")
            self.action_button.setEnabled(False)
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0) # Indeterminate
            self.live_data_scroll.setVisible(False)
            self.btn_exit_training.setEnabled(False) # Don't allow exit while purging

    # --- ADDED: clear_plots method ---
    def clear_plots(self):
        self.time_data.clear()
        self.plot_time_counter = 0
        for key in self.mq_data:
            self.mq_data[key].clear()
            if key in self.mq_plot_lines:
                self.mq_plot_lines[key].setData([], [])
        
        for key in self.as_data:
            self.as_data[key].clear()
            
        for key in self.as_plot_lines:
            if key in self.as_plot_lines:
                self.as_plot_lines[key].setData([], [])
    # ---------------------------------

    def check_password(self):
        if self.password_input.text() == "poultriscan":
            self.set_state(self.STATE_NEEDS_INIT)
        else:
            show_custom_message(self, "Access Denied", "Incorrect password.", "error", self.palette)
            self.password_input.clear()
            self.password_input.setFocus()

    # --- HARDWARE CONTROL METHODS (Unchanged) ---
    def _control_fan(self, state):
        """Controls the purge fan using the SHARED lgpio handle."""
        if self.gpio_handle is None:
            self.log("Fan control skipped: Global gpio_handle is None.")
            return
        try:
            if state:
                lgpio.tx_pwm(self.gpio_handle, FAN_PIN, PWM_FREQ, 100) 
            else:
                lgpio.tx_pwm(self.gpio_handle, FAN_PIN, PWM_FREQ, 0)
        except Exception as e:
            self.log(f"Fan control error (lgpio): {e}")

    def _control_led(self, state):
        """Controls the 5050 LED strip using the SHARED lgpio handle."""
        if self.gpio_handle is None:
            return
        try:
            lgpio.gpio_write(self.gpio_handle, LED_PIN, 1 if state else 0)
        except Exception as e:
            self.log(f"LED control error: {e}")
    
    @Slot(bool)
    def on_led_control_request(self, state):
        self._control_led(state)
    # --------------------------------

    # --- **** MODIFIED: on_action_button_click **** ---
    # This now handles the state logic and calls the
    # new ask_to_stop_measurement method.
    def on_action_button_click(self):
        if self.current_state == self.STATE_NEEDS_INIT:
            self.run_mq_baseline()
        elif self.current_state == self.STATE_READY_TO_MEASURE:
            self.run_show_sample_dialog()
        elif self.current_state == self.STATE_MEASURING:
            self.ask_to_stop_measurement() # <-- CHANGED
    # --- **** END MODIFICATION **** ---

    # --- **** NEW METHOD **** ---
    def ask_to_stop_measurement(self):
        """
        Shows a confirmation dialog before stopping the measurement.
        """
        self.log("Stop button clicked. Asking for confirmation...")
        is_confirmed = show_custom_message(
            self, 
            "Confirm Stop", 
            "Are you sure you want to stop monitoring?\n\nThis will stop data collection and start the chamber purge.", 
            "confirm", 
            self.palette
        )
        
        if is_confirmed:
            self.log("User confirmed stop. Initiating stop sequence.")
            self.stop_continuous_measurement() # Call the original stop function
        else:
            self.log("User cancelled stop. Measurement will continue.")
            # Do nothing, measurement continues
    # --- **** END NEW METHOD **** ---

    # --- Initialization Methods (Mostly Unchanged) ---
    def run_mq_baseline(self):
        self.set_state(self.STATE_PRE_PURGE)
        self._control_fan(True)
        QTimer.singleShot(10000, self.start_mq_baseline_worker)

    def start_mq_baseline_worker(self):
        self.log("Pre-purge complete. Stabilizing for 5s...")
        self._control_fan(False)
        QTimer.singleShot(5000, self.start_mq_capture)
        
    def start_mq_capture(self):
        self.log("Stabilization complete. Starting MQ baseline capture.")
        self.set_state(self.STATE_INITIALIZING_MQ)
        
        self.baseline_thread = QThread()
        self.baseline_worker = MQBaselineWorker(duration_sec=30, interval_sec=1)
        self.baseline_worker.moveToThread(self.baseline_thread)
        self.baseline_worker.progress.connect(self.progress_bar.setValue)
        self.baseline_worker.finished.connect(self.on_mq_baseline_complete)
        self.baseline_worker.error.connect(self.on_initialization_error)
        self.baseline_thread.started.connect(self.baseline_worker.run)
        self.baseline_thread.start()

    def on_mq_baseline_complete(self, baseline_data):
        self.baseline_thread.quit()
        self.baseline_thread.wait()
        self.baseline_thread = None
        self.mq_baseline = baseline_data
        
        self.log(f"MQ Baseline Saved. (MQ-137 Avg: {baseline_data['baseline_mq137']:.3f} V, MQ-3 Avg: {baseline_data['baseline_mq3']:.3f} V)")
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_file = os.path.join(BASELINE_DIR, f"mq_baseline_{ts}.json")
            with open(archive_file, 'w') as f:
                json.dump(self.mq_baseline, f, indent=2)
            with open(MQ_BASELINE_CURRENT_FILE, 'w') as f:
                json.dump(self.mq_baseline, f, indent=2)
            self.log(f"Baseline JSON saved.")
        except Exception as e:
            self.on_initialization_error(f"Failed to save baseline JSON: {e}")
            return
        
        self.as_refs = {} # Worker expects this, even if empty
        
        # --- MODIFIED: Skip AS refs and go straight to ready ---
        self.log("Skipping AS7265x references as requested.")
        # We still need to log the baseline data to the CSV
        self.archive_baseline_data()
        self.set_state(self.STATE_READY_TO_MEASURE)
        # --- END MODIFICATION ---

    def on_initialization_error(self, error_message):
        self.log(f"ERROR: {error_message}")
        show_custom_message(self, "Initialization Error", error_message, "error", self.palette)
        if self.baseline_thread and self.baseline_thread.isRunning():
            self.baseline_worker.stop()
            self.baseline_thread.quit()
            self.baseline_thread.wait()
        self.baseline_thread = None
        self._control_fan(False)
        # Turn off ALL LEDs on error
        as_led_off()
        as_uv_led_off()
        as_ir_led_off()
        self._control_led(False)
        self.set_state(self.STATE_NEEDS_INIT)

    # --- NEW METHOD: To archive baseline data ---
    def archive_baseline_data(self):
        """
        Saves the MQ baseline data (and blank AS refs) to the
        baseline collection CSV file.
        """
        try:
            row_to_write = {}
            row_to_write["timestamp_iso"] = _get_with_nan(self.mq_baseline, "baseline_timestamp")
            row_to_write["operator"] = _get_with_nan(self.mq_baseline, "operator")
            row_to_write["ambient_temp"] = _get_with_nan(self.mq_baseline, "ambient_temp")
            row_to_write["ambient_hum"] = _get_with_nan(self.mq_baseline, "ambient_hum")
            row_to_write["baseline_mq137"] = _get_with_nan(self.mq_baseline, "baseline_mq137")
            row_to_write["baseline_mq135"] = _get_with_nan(self.mq_baseline, "baseline_mq135")
            row_to_write["baseline_mq4"] = _get_with_nan(self.mq_baseline, "baseline_mq4")
            row_to_write["baseline_mq3"] = _get_with_nan(self.mq_baseline, "baseline_mq3")
            
            # Add NaNs for AS refs since we skipped them
            for i in range(1, 19):
                row_to_write[f"as_dark_ref_ch{i}"] = "NaN"
                row_to_write[f"as_white_ref_ch{i}"] = "NaN"

            file_exists = os.path.exists(BASELINE_COLLECTION_FILE)
            with open(BASELINE_COLLECTION_FILE, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=BASELINE_HEADER)
                if not file_exists:
                    writer.writeheader()
                # Filter row to only include keys present in the header
                filtered_row = {h: _get_with_nan(row_to_write, h) for h in BASELINE_HEADER}
                writer.writerow(filtered_row)
            
            self.log(f"MQ Baseline (only) appended to {os.path.basename(BASELINE_COLLECTION_FILE)}")
        except Exception as e:
            self.on_initialization_error(f"Failed to save baseline CSV: {e}")

    # --- REMOVED run_dark_ref and run_white_ref ---
    # --- End Initialization Methods ---
        
    def run_show_sample_dialog(self):
        # --- MODIFIED: Use simplified dialog ---
        dialog = SampleDialog(self.palette, self)
        if dialog.exec():
            self.current_sample = dialog.get_sample_info()
            self.log(f"Sample created: {self.current_sample['id']}.")
            self.show_handling_instructions()
        else:
            self.log("Sample creation cancelled.")
        # --- END MODIFICATION ---

    def show_handling_instructions(self):
        storage = self.current_sample.get("storage", "Room")
        title = "Sample Preparation"
        message = ""
        is_confirmed = False
        
        if storage == "Room":
            message = "For **Room Temperature** samples:\n\n1. Leave sample in its RT container.\n2. Bring to the measurement chamber.\n\nClick **Yes** when ready to measure."
            is_confirmed = show_custom_message(self, title, message, "confirm", self.palette)
        elif storage == "Chilled":
            message = "For **Chilled** samples:\n\n1. Remove sample from the chiller.\n2. Allow it to stabilize for 3-5 minutes at room air.\n\nClick **Yes** when ready to measure."
            is_confirmed = show_custom_message(self, title, message, "confirm", self.palette)
        elif storage == "Frozen":
            thaw_method, ok1 = QInputDialog.getText(self, "Frozen Sample Info", "Enter Thaw Method (e.g., 'Chiller', 'Room Air'):")
            if not ok1 or not thaw_method:
                self.log("Frozen sample prep cancelled.")
                self.set_state(self.STATE_READY_TO_MEASURE)
                return
            time_since_thaw, ok2 = QInputDialog.getText(self, "Frozen Sample Info", "Enter Time Since Thaw (in minutes):")
            if not ok2 or not time_since_thaw:
                self.log("Frozen sample prep cancelled.")
                self.set_state(self.STATE_READY_TO_MEASURE)
                return
                
            hour_val, ok3 = QInputDialog.getText(self, "Frozen Sample Info", "Optional: Enter sample age in hours (e.g., '48'):")
            if ok3 and hour_val.isdigit():
                 self.current_sample["hour"] = int(hour_val)

            self.current_sample["thaw_method"] = thaw_method
            self.current_sample["time_since_thaw_min"] = time_since_thaw
            message = f"For **Frozen** samples:\n\n1. Thaw Method: {thaw_method}\n2. Time Since Thaw: {time_since_thaw} min\n\nClick **Yes** when ready to measure."
            is_confirmed = show_custom_message(self, title, message, "confirm", self.palette)
        
        if is_confirmed:
            self.log(f"Handling confirmed for {storage} sample. Starting measurement.")
            self.start_continuous_measurement()
        else:
            self.log("Measurement cancelled by user at handling step.")
            self.set_state(self.STATE_READY_TO_MEASURE)

    # --- REVISED Measurement Methods ---
    def start_continuous_measurement(self):
        self.set_state(self.STATE_MEASURING)
        self.log("Starting continuous measurement...")
        
        self.continuous_thread = QThread()
        self.continuous_worker = ContinuousMeasurementWorker(
            self.current_sample, self.mq_baseline, self.as_refs,
            window_size=60, interval_sec=5
        )
        
        self.continuous_worker.moveToThread(self.continuous_thread)
        
        self.continuous_worker.update_status.connect(self.log)
        # --- MODIFIED: Connect to new signals ---
        self.continuous_worker.averaged_update.connect(self.on_averaged_data_update)
        self.continuous_worker.raw_data_update.connect(self.on_raw_data_update)
        # ---
        self.continuous_worker.error.connect(self.on_measurement_error)
        self.continuous_worker.request_led_control.connect(self.on_led_control_request)
        
        self.continuous_thread.started.connect(self.continuous_worker.run)
        
        # --- **** FIX 2.1: Connect to the WORKER's finished signal **** ---
        self.continuous_worker.finished.connect(self.on_continuous_worker_finished)
        
        self.continuous_thread.start()

    @Slot(dict)
    def on_averaged_data_update(self, data_dict):
        """
        Slot to receive new 5-min averaged data.
        This is now ONLY for logging.
        """
        self.log(f"5-min average chunk saved. Temp: {data_dict.get('temp_c', 0):.2f}°C")
            
    # --- ADDED: Slot for raw data to update UI and graphs ---
    @Slot(dict)
    def on_raw_data_update(self, data_dict):
        """
        Slot to receive raw 5-second data.
        Updates labels and graphs.
        """
        # 1. Update UI Labels
        for key, label_widget in self.live_data_widgets.items():
            val = data_dict.get(key)
            if val is not None and isinstance(val, (int, float)):
                label_widget.setText(f"{val:.3f}") # 3 decimal places
            elif val is not None:
                 label_widget.setText(f"{val}")
            else:
                label_widget.setText("N/A")
                
        # 2. Update Graph Data
        self.plot_time_counter += 1
        self.time_data.append(self.plot_time_counter)
        
        # Update MQ Data
        for key in self.mq_data.keys():
            self.mq_data[key].append(data_dict.get(key, 0))
            if key in self.mq_plot_lines:
                self.mq_plot_lines[key].setData(list(self.time_data), list(self.mq_data[key]))
        
        # Update AS Data (all 18 channels)
        for key in self.as_data.keys():
            self.as_data[key].append(data_dict.get(key, 0))
            
        # Update AS Plot Lines (only the 4 we are plotting)
        for key in self.as_plot_lines.keys():
            self.as_plot_lines[key].setData(list(self.time_data), list(self.as_data[key]))

    # --- **** REWRITTEN: stop_continuous_measurement (non-blocking) **** ---
    # --- THIS FUNCTION IS NOW CALLED *AFTER* CONFIRMATION ---
    def stop_continuous_measurement(self):
        """
        Stops the continuous measurement worker by sending a signal.
        The actual cleanup is handled by on_continuous_worker_finished.
        """
        self.log("Stopping continuous measurement...")
        self.action_button.setEnabled(False)
        self.action_button.setText(" STOPPING...")
        self.status_label.setText("Waiting for worker to stop...")
        
        if self.continuous_thread and self.continuous_thread.isRunning():
            if self.continuous_worker:
                self.continuous_worker.stop() # This tells the worker's loop to exit
            # The worker's finished signal will handle the rest
        else:
            # Fallback in case thread is dead but state is wrong
            self.log("Worker already stopped. Proceeding to purge.")
            self.on_continuous_worker_finished()

    # --- **** ADDED: New slot for non-blocking stop **** ---
    @Slot()
    def on_continuous_worker_finished(self):
        """
        Slot connected to the worker's 'finished' signal.
        Ensures cleanup and purge happens AFTER the thread exits.
        """
        self.log("Measurement worker has finished.")
        
        if self.continuous_thread:
            self.continuous_thread.quit()
            self.continuous_thread.wait(200) # Short wait for safety
            self.continuous_thread = None
        self.continuous_worker = None
        
        self.log("Measurement stopped.")
        # show_custom_message(self, "Monitoring Stopped", "Continuous monitoring has been stopped.", "info", self.palette)
        
        # --- MODIFIED: Start the DYNAMIC purge worker ---
        self.start_dynamic_purge()

    
    @Slot(str)
    def on_measurement_error(self, error_message):
        self.log(f"ERROR: {error_message}")
        
        # Only show a popup if it's not a CSV error (which repeats)
        if "CSV Write Error" not in error_message:
            show_custom_message(self, "Measurement Error", error_message, "error", self.palette)
        
        # NOTE: We no longer manually stop the thread here.
        # The worker's 'try...except' block will catch the Hardware Error,
        # emit this signal, and then terminate its 'run()' method.
        # This will *correctly* trigger the worker's 'finished' signal,
        # which runs 'on_continuous_worker_finished()' and starts the purge.
    

    
    # --- ADD THESE NEW METHODS ---
    
    @Slot()
    def start_dynamic_purge(self):
        """Starts the dynamic purge worker thread."""
        self.log("Starting dynamic post-measurement purge... Fan ON.")
        self._control_fan(True)
        self.set_state(self.STATE_PURGING)

        self.purge_thread = QThread()
        # Use a 5% tolerance and check every 3 seconds
        self.purge_worker = PurgeWorker(self.mq_baseline, tolerance_pct=5.0, interval_sec=3) 
        self.purge_worker.moveToThread(self.purge_thread)
        
        self.purge_worker.update_status.connect(self.log)
        self.purge_worker.finished.connect(self.on_post_purge_complete) # Reuse the existing complete handler
        self.purge_worker.error.connect(self.on_purge_error)
        
        self.purge_thread.started.connect(self.purge_worker.run)
        self.purge_thread.start()

    @Slot(str)
    def on_purge_error(self, error_message):
        self.log(f"PURGE ERROR: {error_message}")
        show_custom_message(self, "Purge Error", error_message, "error", self.palette)
        # Even on error, stop the fan and reset.
        self.on_post_purge_complete()

    # --- END NEW METHODS ---


    @Slot()
    def on_post_purge_complete(self):
        self.log("Post-purge complete. Fan OFF.")
        self._control_fan(False)
        
        # --- ADDED: Clean up the purge worker thread ---
        if self.purge_thread:
            self.purge_thread.quit()
            self.purge_thread.wait(500) # Wait up to 500ms
            self.purge_thread = None
        self.purge_worker = None
        # --- END ADDITION ---
        
        self.set_state(self.STATE_READY_TO_MEASURE)
    # --- END Measurement Methods ---

    # --- MODIFIED: Simplified _ask_for_csv_file ---
    def _ask_for_csv_file(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Data File")
        dialog.setStyleSheet(f"QDialog {{ background-color: {self.palette['SECONDARY_BG']}; padding: 20px; }}")
        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)
        label = QLabel("Which data file would you like to use?")
        label.setFont(QFont("Bahnschrift", 16))
        layout.addWidget(label)
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        btn_avg_continuous = QPushButton(" Averaged 5-Min Data")
        btn_avg_continuous.setIcon(qta.icon('fa5s.chart-line', color=self.palette.get("BUTTON_TEXT", self.palette["BG"])))
        
        btn_raw_continuous = QPushButton(" Raw 5-Sec Data")
        btn_raw_continuous.setIcon(qta.icon('fa5s.database', color=self.palette.get("UNSELECTED_TEXT", "#555760")))
        btn_raw_continuous.setObjectName("secondary")
        
        btn_baseline = QPushButton(" Baseline Data")
        btn_baseline.setIcon(qta.icon('fa5s.history', color=self.palette.get("UNSELECTED_TEXT", "#555760")))
        btn_baseline.setObjectName("secondary")
        
        btn_layout.addWidget(btn_baseline)
        btn_layout.addWidget(btn_raw_continuous)
        btn_layout.addWidget(btn_avg_continuous)
        layout.addLayout(btn_layout)
        
        btn_avg_continuous.clicked.connect(lambda: (setattr(dialog, 'choice', (CONTINUOUS_DATA_FILE, "Averaged 5-Min Data")), dialog.accept()))
        btn_raw_continuous.clicked.connect(lambda: (setattr(dialog, 'choice', (CONTINUOUS_RAW_DATA_FILE, "Raw 5-Sec Data")), dialog.accept()))
        btn_baseline.clicked.connect(lambda: (setattr(dialog, 'choice', (BASELINE_COLLECTION_FILE, "Baseline Data")), dialog.accept()))
        
        if not dialog.exec():
            return None, None
        return getattr(dialog, 'choice', (None, None))
    # --- END MODIFICATION ---

    def show_csv_viewer(self):
        file_path, file_name = self._ask_for_csv_file()
        if not file_path:
            return
        try:
            dialog = CsvViewerDialog(self.palette, file_path, self)
            dialog.load_csv_data()
            dialog.exec()
        except Exception as e:
            self.log(f"Error opening CSV viewer: {e}")
            show_custom_message(self, "Error", f"Could not open CSV viewer: {e}", "error", self.palette)

    def stop_all_workers(self):
        if self.baseline_thread and self.baseline_thread.isRunning():
            self.log("Stopping MQ Baseline worker...")
            self.baseline_worker.stop()
            self.baseline_thread.quit()
            self.baseline_thread.wait(1000)
            self.log("Worker stopped.")
        self.baseline_thread = None
        self.baseline_worker = None
        
        if self.continuous_thread and self.continuous_thread.isRunning():
            self.log("Stopping Continuous Measurement worker...")
            if self.continuous_worker:
                self.continuous_worker.stop()
            self.continuous_thread.quit()
            self.continuous_thread.wait(1000)
            self.log("Worker stopped.")
        self.continuous_thread = None
        self.continuous_worker = None

        # --- ADD THIS BLOCK ---
        if self.purge_thread and self.purge_thread.isRunning():
            self.log("Stopping Purge worker...")
            if self.purge_worker:
                self.purge_worker.stop()
            self.purge_thread.quit()
            self.purge_thread.wait(1000)
            self.log("Worker stopped.")
        self.purge_thread = None
        self.purge_worker = None
        # --- END ADDITION ---

    def exit_training_mode(self):
        self.log("Exiting Continuous Mode...")
        self.stop_all_workers()
        self._control_fan(False)
        self._control_led(False)
        self.log_display.clear()
        self.password_input.clear()
        self.set_state(self.STATE_LOCKED) 
        self.main_window.switch_page(2) # Switch to Settings
        print("Switched to Settings tab.")

    # --- MODIFIED: Simplified email_csv_file ---
    def email_csv_file(self):
        recipient_email = self.email_input.text().strip()
        if not re.match(r"[^@]+@[^@]+\.[^@]+", recipient_email):
            show_custom_message(self, "Invalid Email", "Please enter a valid recipient email address.", "warning", self.palette)
            return
        
        # Only show the two new files
        file_map = {
            "Averaged 5-Min Data": CONTINUOUS_DATA_FILE,
            "Raw 5-Sec Data": CONTINUOUS_RAW_DATA_FILE,
            "Baseline Data": BASELINE_COLLECTION_FILE # Keep baseline as it's useful
        }
        
        dialog = MultiCsvSelectDialog(file_map, self.palette, self)
        if not dialog.exec():
            self.log("Email cancelled.")
            return
        selected_files_to_send = dialog.get_selected_files()
        if not selected_files_to_send:
            show_custom_message(self, "No Files Selected", "You did not select any files to send.", "info", self.palette)
            return
        for file_path in selected_files_to_send:
            if not os.path.exists(file_path):
                show_custom_message(self, "Email Failed", f"The file '{os.path.basename(file_path)}' was not found.", "warning", self.palette)
                return

        accent = self.palette.get("ACCENT", "#F0C419")
        bg = self.palette.get("BG", "#101218")
        secondary_bg = self.palette.get("SECONDARY_BG", "#1C1E24")
        text_color = self.palette.get("TEXT", "#E0E0E0")
        border = self.palette.get("BORDER", "#2A2C33")
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")
        file_count = len(selected_files_to_send)
        email_subject = f"PoultriScan Continuous Data :: {file_count} File(s) :: {date_str} {time_str}"
        file_name_list_html = "<ul>"
        for f in selected_files_to_send:
            file_name_list_html += f"<li>{os.path.basename(f)}</li>"
        file_name_list_html += "</ul>"
        email_body = f"""
        <html>
        <head>
            <style> body {{ font-family: 'Bahnschrift', 'Segoe UI', Arial, sans-serif; }} </style>
        </head>
        <body style="margin: 0; padding: 0; background-color: {bg}; color: {text_color};">
            <table width="100%" border="0" cellspacing="0" cellpadding="0">
                <tr>
                    <td align="center" style="padding: 20px 0;">
                        <table width="600" border="0" cellspacing="0" cellpadding="0" style="background-color: {secondary_bg}; border: 1px solid {border}; border-radius: 8px; overflow: hidden;">
                            <tr>
                                <td style="padding: 30px; border-bottom: 4px solid {accent};">
                                    <h1 style="font-size: 28px; color: {accent}; margin: 0;">PoultriScan</h1>
                                    <h2 style="font-size: 20px; color: {text_color}; margin: 5px 0 0 0;">Continuous Data Report</h2>
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 30px; font-size: 16px; line-height: 1.6;">
                                    <p>Dear Recipient,</p>
                                    <p>Attached, please find the PoultriScan data file(s) you requested:</p>
                                    <div style="border-left: 3px solid {accent}; padding-left: 15px; background-color: {bg}; padding: 10px 15px;">
                                        {file_name_list_html}
                                    </div>
                                    <p>These files contain data generated by the Continuous Mode module.</p>
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 20px 30px; background-color: {border}; color: #888; font-size: 12px; text-align: center;">
                                    <p style="margin: 0;">© 2025 PoultriScan Development Team</p>
                                    <p style="margin: 5px 0 0 0;">Report Generated: {date_str} at {time_str}</p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """
        self.processing_dialog = CustomDialog(
            self, "Sending Email", f"Sending {file_count} file(s)...", "processing", self.palette
        )
        self.email_thread = QThread()
        self.email_worker = EmailWorker(
            recipient=recipient_email, palette=self.palette,
            smtp_server=SMTP_SERVER, smtp_port=SMTP_PORT,
            sender_email=SENDER_EMAIL, sender_password=SENDER_PASSWORD,
            file_path_list=selected_files_to_send,
            email_subject=email_subject, email_body=email_body
        )
        self.email_worker.moveToThread(self.email_thread)
        self.email_thread.started.connect(self.email_worker.run)
        self.email_worker.finished.connect(self.on_email_success)
        self.email_worker.error.connect(self.on_email_error)
        self.email_worker.finished.connect(self.email_thread.quit)
        self.email_worker.finished.connect(self.email_worker.deleteLater)
        self.email_thread.finished.connect(self.email_thread.deleteLater)
        self.btn_email_csv.setEnabled(False)
        self.btn_email_csv.setText(" SENDING...")
        self.email_thread.start()
        self.processing_dialog.show()
    # --- END MODIFICATION ---

    @Slot(str)
    def on_email_success(self, message):
        if self.processing_dialog:
            self.processing_dialog.accept()
        self.processing_dialog = None
        self.btn_email_csv.setEnabled(True)
        self.btn_email_csv.setText(" EMAIL DATA")
        show_custom_message(self, "Email Sent", message, "success", self.palette)
        self.log("Email sent successfully.")

    @Slot(str, str)
    def on_email_error(self, title, message):
        if self.processing_dialog:
            self.processing_dialog.accept()
        self.processing_dialog = None
        self.btn_email_csv.setEnabled(True)
        self.btn_email_csv.setText(" EMAIL DATA")
        show_custom_message(self, title, message, "error", self.palette)
        self.log(f"Email Error: {message}")


# --- MODIFIED create_..._tab function ---
def create_continuous_tab(tab_control, palette, main_window, gpio_handle):
    """Creates the Continuous Monitoring tab."""
    container = ContinuousTab(palette, main_window, gpio_handle)
    return container