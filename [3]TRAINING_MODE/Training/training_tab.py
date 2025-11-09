# Training/training_tab.py

import sys
import os
import csv
import json
import qtawesome as qta
import time
import lgpio  # <-- 1. ADDED LGPIO IMPORT
import statistics # For calculating standard deviation
from datetime import datetime
import re # For email validation
import smtplib # For sending email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders # For attaching file

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

# --- 2. REAL SENSOR IMPORTS (MODIFIED) ---
try:
    from custom_dialog import show_custom_message, CustomDialog
    from Sensors.aht20 import read_aht20, UninitializedAHT20Error
    from Sensors.enose import read_enose, UninitializedENoseError
    from Sensors.as7265x import (
        read_spectrometer, as_led_on, as_led_off,
        as_uv_led_on, as_uv_led_off, as_ir_led_on, as_ir_led_off, # <-- Keep all controls
        UninitializedAS7265XError
    )
except ImportError as e:
    print(f"FATAL ERROR in training_tab.py: Could not import modules.")
    print(f"Make sure training_tab.py is in a 'Training' folder, and 'Sensors' and 'custom_dialog.py' are in the parent folder.")
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

# --- 3. SMTP Configuration (Unchanged) ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "poultriscan4201@gmail.com"
SENDER_PASSWORD = "ikaggyzetigoajre"
# --- END SMTP Configuration ---


# --- 4. File & Directory Definitions (MODIFIED) ---
# --- ADDED FAN CONFIG ---
FAN_PIN = 27
PWM_FREQ = 100
# --- End Fan Config ---
TRAINING_ROOT_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(TRAINING_ROOT_DIR, "data")
RAW_DIR = os.path.join(DATA_DIR, "raw_json")
BASELINE_DIR = os.path.join(DATA_DIR, "baselines")
REFS_DIR = os.path.join(DATA_DIR, "references")

# --- MODIFIED: Changed to v3 files to prevent header mismatch with old data ---
DATA_COLLECTION_FILE = os.path.join(DATA_DIR, "data_collection_v3_mq3_no_uvir.csv")
BASELINE_COLLECTION_FILE = os.path.join(DATA_DIR, "baseline_collection_v3_mq3_no_uvir.csv")
RAW_BLOCK_DATA_FILE = os.path.join(DATA_DIR, "raw_block_data_v3_mq3_no_uvir.csv")
# --- END MODIFICATION ---

MQ_BASELINE_CURRENT_FILE = os.path.join(BASELINE_DIR, "mq_baseline_current.json")
AS_REFS_FILE = os.path.join(REFS_DIR, "as7265_refs.json")

# --- 5. CSV Headers (MODIFIED - REMOVED UV/IR) ---

CANONICAL_HEADER = [
    "sample_id", "meat_type", "storage_type", "hour", "timestamp_iso", 
    "temp_c", "hum_pct",
    "frozen_age_days", "thaw_method", "time_since_thaw_min",
    "final_mq137", "final_mq135", "final_mq4", "final_mq3", # <-- Corrected to MQ4/MQ3
    # White Light Channels (Visible Reflectance)
    "AS7265X_ch1", "AS7265X_ch2", "AS7265X_ch3", "AS7265X_ch4",
    "AS7265X_ch5", "AS7265X_ch6", "AS7265X_ch7", "AS7265X_ch8",
    "AS7265X_ch9", "AS7265X_ch10", "AS7265X_ch11", "AS7265X_ch12",
    "AS7265X_ch13", "AS7265X_ch14", "AS7265X_ch15", "AS7265X_ch16",
    "AS7265X_ch17", "AS7265X_ch18",
    # UV and IR channels are REMOVED
    "avg_valid", "cv_flag", "final_label", "ground_truth_value"
]

BASELINE_HEADER = [
    "timestamp_iso", "operator", "ambient_temp", "ambient_hum", 
    "baseline_mq137", "baseline_mq135", "baseline_mq4", "baseline_mq3" # <-- Corrected
] + [f"as_dark_ref_ch{i}" for i in range(1, 19)] \
  + [f"as_white_ref_ch{i}" for i in range(1, 19)]
  # UV and IR refs are REMOVED

RAW_BLOCK_HEADER = [
    "sample_id", "hour", "timestamp_iso", "led_source",
    "temp_c", "hum_pct",
    "MQ-137 (Ammonia)", "MQ-135 (Air Quality)", "MQ-4 (Methane)", "MQ-3 (Alcohol)", # <-- Corrected
    "AS7265X_ch1", "AS7265X_ch2", "AS7265X_ch3", "AS7265X_ch4",
    "AS7265X_ch5", "AS7265X_ch6", "AS7265X_ch7", "AS7265X_ch8",
    "AS7265X_ch9", "AS7265X_ch10", "AS7265X_ch11", "AS7265X_ch12",
    "AS7265X_ch13", "AS7265X_ch14", "AS7265X_ch15", "AS7265X_ch16",
    "AS7265X_ch17", "AS7265X_ch18", "final_label"
]


# --- 6. Helper Functions (MODIFIED) ---
# --- DELETED PLACEHOLDER _control_fan ---

def _control_5050_led(state):
    """
    Placeholder function to control the 5V 5050 LED strip.
    ACTION REQUIRED: Replace this with your actual GPIO/hardware code.
    """
    if state:
        # print("DEBUG: 5050 LED Strip ON")
        pass
    else:
        # print("DEBUG: 5050 LED Strip OFF")
        pass

def _create_card(parent, title, palette, icon_name=None):
    # (Unchanged)
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
        title_label = QLabel(f"Training Data: {os.path.basename(file_path)}")
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


# --- REAL MQ BASELINE WORKER (MODIFIED) ---
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
            # <-- MODIFIED: Using MQ4 and MQ3
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
                readings["mq3"].append(mq_data["MQ-3 (Alcohol)"]) # <-- Corrected
                readings["temp"].append(aht_data["Temperature"])
                readings["hum"].append(aht_data["Humidity"])
                time.sleep(self.interval)
                self.progress.emit(i + 1)
            # <-- MODIFIED: Using MQ4 and MQ3
            final_baseline = {
                "baseline_mq137": statistics.mean(readings["mq137"]),
                "baseline_mq135": statistics.mean(readings["mq135"]),
                "baseline_mq4": statistics.mean(readings["mq4"]),
                "baseline_mq3": statistics.mean(readings["mq3"]), # <-- Corrected
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
# --- END MODIFIED MQBaselineWorker ---


# --- 7. REAL MEASUREMENT WORKER (MODIFIED - REMOVED UV/IR) ---
class MeasurementWorker(QObject):
    update_status = Signal(str)
    measurement_complete = Signal(dict)
    error = Signal(str)
    
    def __init__(self, sample_info, mq_baseline):
        super().__init__()
        self.sample_info = sample_info
        self.mq_baseline = mq_baseline
        self._is_running = True

    @Slot()
    def run(self):
        """Runs the main 3-block measurement loop, capturing 1 spectrum (White) per read."""
        try:
            all_block_avg_data = []
            raw_data_rows_to_write = []
            
            for block_num in range(1, 4):
                if not self._is_running:
                    self.error.emit("Measurement cancelled")
                    return
                self.update_status.emit(f"--- Starting Block {block_num}/3 ---")
                
                # <-- MODIFIED: Using MQ4 and MQ3
                block_reads_mq137, block_reads_mq135, block_reads_mq4, block_reads_mq3 = [], [], [], []
                block_reads_as_white = [] 
                block_reads_temp = []
                block_reads_hum = []
                
                for i in range(5):
                    if not self._is_running:
                        self.error.emit("Measurement cancelled")
                        return
                    
                    self.update_status.emit(f"Block {block_num}: Reading (White, MQ, AHT) ({i+1}/5)...")
                    
                    # --- Read 1: WHITE + MQ + AHT ---
                    _control_5050_led(True)
                    as_led_on()
                    time.sleep(2.0)
                    
                    mq_data = read_enose()
                    aht_data = read_aht20()
                    # --- MODIFIED: Uses new read_spectrometer() ---
                    spec_data_white = read_spectrometer()
                    
                    as_led_off()
                    _control_5050_led(False)
                    # --- UV and IR reads are REMOVED ---
                    
                    read_timestamp = datetime.now().isoformat()
                    
                    # --- Store data for block-level averaging ---
                    block_reads_mq137.append(mq_data["MQ-137 (Ammonia)"])
                    block_reads_mq135.append(mq_data["MQ-135 (Air Quality)"])
                    block_reads_mq4.append(mq_data["MQ-4 (Methane)"])
                    block_reads_mq3.append(mq_data["MQ-3 (Alcohol)"]) # <-- Corrected
                    block_reads_temp.append(aht_data["Temperature"])
                    block_reads_hum.append(aht_data["Humidity"])
                    block_reads_as_white.append(spec_data_white)
                    # --- UV and IR storage is REMOVED ---

                    # --- Store raw row data (1 row per read) ---
                    common_data = {
                        "sample_id": self.sample_info["id"], "hour": self.sample_info["hour"],
                        "timestamp_iso": read_timestamp,
                        "temp_c": aht_data["Temperature"],
                        "hum_pct": aht_data["Humidity"],
                        "final_label": "N/A"
                    }
                    
                    raw_row_white = {**common_data, **mq_data, "led_source": "WHITE"}
                    raw_row_white.update(spec_data_white)
                    raw_data_rows_to_write.append(raw_row_white)
                    # --- UV and IR raw rows are REMOVED ---
                    
                    if i < 4:
                        time.sleep(3) # 3-second interval
                
                # --- Block complete, calculate block averages ---
                block_avg_dict = {}
                block_avg_dict["block_mq137"] = statistics.mean(block_reads_mq137)
                block_avg_dict["block_mq135"] = statistics.mean(block_reads_mq135)
                block_avg_dict["block_mq4"] = statistics.mean(block_reads_mq4)
                block_avg_dict["block_mq3"] = statistics.mean(block_reads_mq3) # <-- Corrected
                block_avg_dict["temp"] = statistics.mean(block_reads_temp)
                block_avg_dict["hum"] = statistics.mean(block_reads_hum)
                
                for i in range(1, 19):
                    key = f"AS7265X_ch{i}"
                    block_avg_dict[key] = statistics.mean(
                        [read[key] for read in block_reads_as_white]
                    )
                    # --- UV and IR averaging is REMOVED ---
                
                all_block_avg_data.append(block_avg_dict)
                
                self.update_status.emit(f"Block {block_num} complete.")
                if block_num < 3:
                    self.update_status.emit("Waiting 5s before next block...")
                    time.sleep(5)

            # --- All 3 blocks complete, save all raw data ---
            try:
                # --- MODIFIED: Writes to new, versioned file ---
                file_exists = os.path.exists(RAW_BLOCK_DATA_FILE)
                with open(RAW_BLOCK_DATA_FILE, 'a', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=RAW_BLOCK_HEADER)
                    if not file_exists:
                        writer.writeheader()
                    for row_dict in raw_data_rows_to_write:
                        row_to_write = {h: _get_with_nan(row_dict, h) for h in RAW_BLOCK_HEADER}
                        writer.writerow(row_to_write)
                # Saved 15 reads (5 reads * 3 blocks * 1 row/read)
                self.update_status.emit(f"Saved 15 raw reads to {os.path.basename(RAW_BLOCK_DATA_FILE)}")
            except Exception as e:
                self.error.emit(f"Failed to save raw block data: {e}")
                return

            # --- Calculate final average across all 3 blocks ---
            self.update_status.emit("All blocks complete. Calculating final average...")
            final_data_row_dict = {} 
            final_data_row_dict.update({
                "sample_id": self.sample_info["id"],
                "meat_type": self.sample_info["meat_type"],
                "storage_type": self.sample_info["storage"],
                "replica": self.sample_info["replica"],
                "hour": self.sample_info["hour"],
                "timestamp_iso": datetime.now().isoformat(),
                "operator": "Operator",
                "frozen_age_days": self.sample_info.get("frozen_age_days"),
                "thaw_method": self.sample_info.get("thaw_method"),
                "time_since_thaw_min": self.sample_info.get("time_since_thaw_min"),
            })
            
            final_data_row_dict["final_mq137"] = statistics.mean(b["block_mq137"] for b in all_block_avg_data)
            final_data_row_dict["final_mq135"] = statistics.mean(b["block_mq135"] for b in all_block_avg_data)
            final_data_row_dict["final_mq4"] = statistics.mean(b["block_mq4"] for b in all_block_avg_data)
            final_data_row_dict["final_mq3"] = statistics.mean(b["block_mq3"] for b in all_block_avg_data) # <-- Corrected
            final_data_row_dict["temp_c"] = statistics.mean(b["temp"] for b in all_block_avg_data)
            final_data_row_dict["hum_pct"] = statistics.mean(b["hum"] for b in all_block_avg_data)
            
            for i in range(1, 19):
                key_white = f"AS7265X_ch{i}"
                final_data_row_dict[key_white] = statistics.mean(b[key_white] for b in all_block_avg_data)
                # --- UV and IR final averaging is REMOVED ---
                
            final_data_row_dict["cv_flag"] = "OK" # Placeholder
            final_data_row_dict["avg_valid"] = True # Placeholder
            self.measurement_complete.emit(final_data_row_dict)
            
        except (UninitializedAHT20Error, UninitializedENoseError, UninitializedAS7265XError) as e:
            self.error.emit(f"Hardware Error: {e}")
            # --- FIX: Turn off ALL LEDs on error ---
            as_led_off()
            as_uv_led_off()
            as_ir_led_off()
            _control_5050_led(False)
        except Exception as e:
            self.error.emit(f"Measurement failed: {e}")
            # --- FIX: Turn off ALL LEDs on error ---
            as_led_off()
            as_uv_led_off()
            as_ir_led_off()
            _control_5050_led(False)
            
    def stop(self):
        self._is_running = False
# --- END MODIFIED MeasurementWorker ---


# --- 10. Sample Selection Dialog (MODIFIED) ---
class SampleDialog(QDialog):
    def __init__(self, palette, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select or Create Sample")
        self.palette = palette
        self.setStyleSheet(f"QDialog {{ background-color: {palette['BG']}; }}")
        self.setMinimumWidth(600)
        self.existing_samples = {}
        self.sample_info = {}
        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        form_layout.setSpacing(15)
        self.sample_combo = QComboBox()
        form_layout.addRow("Select Sample:", self.sample_combo)
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
        self.hour_label = QLabel("Hour 0 (New Sample)")
        self.hour_label.setStyleSheet(f"font: bold 18pt 'Bahnschrift'; color: {palette['ACCENT']};")
        form_layout.addRow("Measurement Time:", self.hour_label)
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
        self.sample_combo.currentTextChanged.connect(self.on_sample_change)
        self.load_existing_samples()

    def load_existing_samples(self):
        self.sample_combo.clear()
        self.existing_samples = {}
        # --- MODIFIED: Reads from the new, versioned file ---
        if os.path.exists(DATA_COLLECTION_FILE):
            try:
                # Use utf-8-sig to handle potential BOM (Byte Order Mark)
                with open(DATA_COLLECTION_FILE, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        sample_id = row.get("sample_id")
                        hour_str = row.get("hour")
                        if sample_id and hour_str is not None:
                            try:
                                hour = int(hour_str)
                                if sample_id not in self.existing_samples or hour > self.existing_samples[sample_id]:
                                    self.existing_samples[sample_id] = hour
                            except (ValueError, TypeError):
                                print(f"Skipping row with invalid hour: {row}")
            except Exception as e:
                print(f"Error reading {DATA_COLLECTION_FILE}: {e}")
        self.sample_combo.addItem("--- Create New Sample ---")
        self.sample_combo.addItems(sorted(self.existing_samples.keys()))
        self.on_sample_change("--- Create New Sample ---")

    def on_sample_change(self, text):
        if text == "--- Create New Sample ---":
            self.new_sample_frame.setVisible(True)
            self.hour_label.setText("Hour 0 (New Sample)")
            self.proceed_btn.setEnabled(True)
        else:
            self.new_sample_frame.setVisible(False)
            last_hour = self.existing_samples.get(text, 0)
            next_hour_map = {0: 6, 6: 12, 12: 24, 24: 36, 36: 48, 48: "COMPLETED"}
            next_hour = next_hour_map.get(last_hour, "COMPLETED")
            self.hour_label.setText(f"Last: {last_hour}hr  |  Next: {next_hour}hr")
            self.proceed_btn.setEnabled(True) 
            
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
        return {
            "id": sample_id, "meat_type": m_type, "storage": s_type,
            "replica": new_replica_str, "hour": 0, "is_new": True
        }

    def on_proceed(self):
        selected_sample = self.sample_combo.currentText()
        if selected_sample == "--- Create New Sample ---":
            m_type = self.meat_type_combo.currentText()
            s_type = self.storage_combo.currentText()
            self.sample_info = self._create_new_sample_info(m_type, s_type)
            self.accept()
        else:
            last_hour = self.existing_samples.get(selected_sample, 0)
            next_hour_map = {0: 6, 6: 12, 12: 24, 24: 36, 36: 48, 48: "COMPLETED"}
            next_hour = next_hour_map.get(last_hour, "COMPLETED")

            dialog = CustomDialog(
                self, "Select Action",
                f"You selected **{selected_sample}** (Last: {last_hour}hr).\n\nWhat do you want to do?",
                "confirm", self.palette
            )
            
            dialog.yes_btn.setText(f"Continue (Measure {next_hour}hr)")
            dialog.no_btn.setText(f"Replicate (Re-measure {last_hour}hr)")
            
            if next_hour == "COMPLETED":
                dialog.yes_btn.setText("Completed")
                dialog.yes_btn.setEnabled(False)

            result = dialog.exec()
            
            parts = selected_sample.split('_')
            type_map_rev = {"BRE": "Breast", "THI": "Thigh", "WNG": "Wing"}
            storage_map_rev = {"RT": "Room", "CH": "Chilled", "FR": "Frozen"}
            m_type = type_map_rev.get(parts[0], "Unknown")
            s_type = storage_map_rev.get(parts[1], "Unknown")
            replica_str = parts[2] if len(parts) > 2 else "N/A"

            if result: # User clicked "Continue"
                if next_hour == "COMPLETED":
                    show_custom_message(self, "Sample Complete", "This sample has already completed all time points.", "info", self.palette)
                    return
                
                self.sample_info = {
                    "id": selected_sample, "meat_type": m_type, "storage": s_type,
                    "replica": replica_str, "hour": next_hour, "is_new": False
                }
                self.accept()
                
            elif not result and dialog.result is False: # User clicked "Replicate"
                self.sample_info = {
                    "id": selected_sample, "meat_type": m_type, "storage": s_type,
                    "replica": replica_str, "hour": last_hour, "is_new": False
                }
                self.accept()
            
            else:
                return # User closed the dialog

    def get_sample_info(self):
        return self.sample_info
# --- END SampleDialog ---


# --- Main Training Tab (MODIFIED) ---
class TrainingTab(QWidget):
    # Modified States
    STATE_LOCKED = 0
    STATE_NEEDS_INIT = 1
    STATE_PRE_PURGE = 2
    STATE_INITIALIZING_MQ = 3
    STATE_NEEDS_DARK_REF = 4
    STATE_NEEDS_WHITE_REF = 5
    STATE_READY_TO_MEASURE = 6 # (Was 8)
    STATE_AWAITING_SAMPLE = 7  # (Was 9)
    STATE_MEASURING = 8        # (Was 10)
    STATE_SAVING = 9           # (Was 11)
    STATE_POST_PURGE = 10      # (Was 12)
    
    # --- MODIFIED: Added fan_chip_handle ---
    def __init__(self, palette, main_window, fan_chip_handle, parent=None):
        super().__init__(parent)
        self.palette = palette
        self.main_window = main_window
        self.fan_chip = fan_chip_handle  # <-- STORE THE FAN HANDLE
        self.current_state = self.STATE_LOCKED
        self.mq_baseline = {}
        self.as_refs = {}
        self.current_sample = {}
        self.baseline_worker = None
        self.baseline_thread = None
        self.measurement_worker = None
        self.measurement_thread = None
        self.email_thread = None
        self.email_worker = None
        self.processing_dialog = None
        
        for d in [DATA_DIR, RAW_DIR, BASELINE_DIR, REFS_DIR]:
            os.makedirs(d, exist_ok=True)
            
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # --- Lock Frame (Unchanged) ---
        self.lock_frame = QFrame()
        self.lock_frame.setStyleSheet(f"background-color: {palette['BG']};")
        lock_layout = QVBoxLayout(self.lock_frame)
        lock_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lock_layout.setSpacing(20)
        lock_label = QLabel("Training Mode Locked")
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
        
        # --- Main Frame (Unchanged layout) ---
        self.main_frame = QWidget()
        main_frame_layout = QGridLayout(self.main_frame)
        main_frame_layout.setContentsMargins(10, 10, 10, 10)
        main_frame_layout.setSpacing(15)
        
        log_card, log_frame = _create_card(self.main_frame, " Training Log", palette, "fa5s.stream")
        log_layout = QVBoxLayout(log_frame)
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setFont(QFont("Consolas", 14))
        log_layout.addWidget(self.log_display)
        main_frame_layout.addWidget(log_card, 0, 0, 1, 1)
        
        status_card, status_frame = _create_card(self.main_frame, " Status & Controls", palette, "fa5s.tasks")
        status_layout = QVBoxLayout(status_frame)
        status_layout.setSpacing(15)
        self.status_label = QLabel("Enter password to unlock.")
        self.status_label.setFont(QFont("Bahnschrift", 18, QFont.Weight.Bold))
        self.status_label.setWordWrap(True)
        status_layout.addWidget(self.status_label)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        status_layout.addWidget(self.progress_bar)
        self.action_button = QPushButton("Unlock")
        self.action_button.clicked.connect(self.on_action_button_click)
        status_layout.addWidget(self.action_button)
        status_layout.addStretch()
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
        self.btn_exit_training = QPushButton(" EXIT TRAINING")
        self.btn_exit_training.setObjectName("danger")
        self.btn_exit_training.setIcon(qta.icon('fa5s.times-circle', color=palette.get("DANGER_TEXT", palette["TEXT"])))
        self.btn_exit_training.clicked.connect(self.exit_training_mode)
        status_layout.addWidget(self.btn_exit_training)
        main_frame_layout.addWidget(status_card, 0, 1, 1, 1)
        
        main_frame_layout.setColumnStretch(0, 2)
        main_frame_layout.setColumnStretch(1, 1)
        self.main_frame.setVisible(False)
        main_layout.addWidget(self.main_frame, 1)
        
        self.set_state(self.STATE_LOCKED)

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_display.append(f"[{timestamp}] {message}")

    def set_state(self, state):
        self.current_state = state
        self.progress_bar.setVisible(False)
        self.action_button.setEnabled(True)
        self.action_button.setIcon(QIcon())
        data_buttons_enabled = (state != self.STATE_LOCKED)
        self.btn_view_csv.setEnabled(data_buttons_enabled)
        self.email_input.setEnabled(data_buttons_enabled)
        self.btn_email_csv.setEnabled(data_buttons_enabled)
        
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
        elif state == self.STATE_NEEDS_DARK_REF:
            self.status_label.setText("MQ Baseline OK. Ready to capture AS7265x Dark Reference.")
            self.action_button.setText(" CAPTURE DARK REF")
            self.action_button.setIcon(qta.icon('fa5s.eye-slash', color=self.palette.get("BUTTON_TEXT", self.palette["BG"])))
        elif state == self.STATE_NEEDS_WHITE_REF:
            self.status_label.setText("Dark Ref OK. Ready to capture AS7265x White Reference.")
            self.action_button.setText(" CAPTURE WHITE REF")
            self.action_button.setIcon(qta.icon('fa5s.camera', color=self.palette.get("BUTTON_TEXT", self.palette["BG"])))
        # --- REMOVED UV_REF and IR_REF states ---
        elif state == self.STATE_READY_TO_MEASURE:
            self.status_label.setText("Initialization Complete. Ready to measure sample.")
            self.action_button.setText(" START MEASUREMENT")
            self.action_button.setIcon(qta.icon('fa5s.play', color=self.palette.get("BUTTON_TEXT", self.palette["BG"])))
        elif state == self.STATE_AWAITING_SAMPLE:
            self.status_label.setText("Purge complete. Awaiting sample placement...")
            self.action_button.setEnabled(False)
            self.action_button.setText("AWAITING...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
        elif state == self.STATE_MEASURING:
            self.status_label.setText(f"Measuring {self.current_sample.get('id', 'sample')}... Please wait.")
            self.action_button.setText(" MEASURING...")
            self.action_button.setEnabled(False)
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)
        elif state == self.STATE_SAVING:
            self.status_label.setText("Saving data...")
            self.action_button.setText(" SAVING...")
            self.action_button.setEnabled(False)
        elif state == self.STATE_POST_PURGE:
            self.status_label.setText("Post-measurement purge (15s)... Fan ON.")
            self.action_button.setText(" PURGING...")
            self.action_button.setEnabled(False)
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)

    def check_password(self):
        if self.password_input.text() == "poultriscan":
            self.set_state(self.STATE_NEEDS_INIT)
        else:
            show_custom_message(self, "Access Denied", "Incorrect password.", "error", self.palette)
            self.password_input.clear()
            self.password_input.setFocus()

    # --- ADDED REAL _control_fan METHOD ---
    def _control_fan(self, state):
        """
        Controls the purge fan using the SHARED lgpio handle.
        """
        if self.fan_chip is None:
            self.log("Fan control skipped: Global fan_chip is None.")
            return
        
        try:
            if state:
                # Set 100% duty cycle
                lgpio.tx_pwm(self.fan_chip, FAN_PIN, PWM_FREQ, 100) 
            else:
                # Set 0% duty cycle
                lgpio.tx_pwm(self.fan_chip, FAN_PIN, PWM_FREQ, 0)
        except Exception as e:
            self.log(f"Fan control error (lgpio): {e}")
    # --- END OF ADDED METHOD ---

    def on_action_button_click(self):
        # Modified States
        state_actions = {
            self.STATE_NEEDS_INIT: self.run_mq_baseline, 
            self.STATE_NEEDS_DARK_REF: self.run_dark_ref,
            self.STATE_NEEDS_WHITE_REF: self.run_white_ref,
            # Removed UV/IR clicks
            self.STATE_READY_TO_MEASURE: self.run_show_sample_dialog,
        }
        action = state_actions.get(self.current_state)
        if action:
            action()

    def run_mq_baseline(self):
        self.set_state(self.STATE_PRE_PURGE)
        self._control_fan(True)  # <-- MODIFIED: Use real fan control
        QTimer.singleShot(10000, self.start_mq_baseline_worker)

    def start_mq_baseline_worker(self):
        self.log("Pre-purge complete. Stabilizing for 5s...")
        self._control_fan(False) # <-- MODIFIED: Use real fan control
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
        
        # <-- MODIFIED: Log MQ-3
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
        
        self.as_refs = {} 
        self.set_state(self.STATE_NEEDS_DARK_REF) 

    def on_initialization_error(self, error_message):
        self.log(f"ERROR: {error_message}")
        show_custom_message(self, "Initialization Error", error_message, "error", self.palette)
        if self.baseline_thread and self.baseline_thread.isRunning():
            self.baseline_worker.stop()
            self.baseline_thread.quit()
            self.baseline_thread.wait()
        self.baseline_thread = None
        self._control_fan(False) # <-- MODIFIED: Use real fan control
        # --- FIX: Turn off ALL LEDs on error ---
        as_led_off()
        as_uv_led_off()
        as_ir_led_off()
        _control_5050_led(False)
        self.set_state(self.STATE_NEEDS_INIT)

    # --- MODIFIED: run_dark_ref (Added animation + explicit LED OFF) ---
    def run_dark_ref(self):
        show_custom_message(self, "Action Required",
            "Place the **Dark Reference Cap** (or completely cover the sensor) to ensure **NO light** is reaching it.\n\nClick OK when ready.",
            "info", self.palette)
        
        processing_dialog = CustomDialog(
            self, "Capturing...", "Acquiring dark reference...", "processing", self.palette
        )
        processing_dialog.show()
        QApplication.processEvents() # Force UI update
            
        try:
            self.log("Capturing dark reference... ALL LEDs OFF.")
            # Explicitly turn off ALL LEDs before starting
            as_led_off()
            as_uv_led_off() 
            as_ir_led_off() 
            _control_5050_led(False) 
            
            time.sleep(2.0) # Allow any residual light/phosphor glow to fade
            
            # --- CRITICAL FIX: pass leds_on=False ---
            self.as_refs["dark_ref"] = read_spectrometer(leds_on=False)
            # ----------------------------------------
            
            processing_dialog.accept() # Close dialog on success
            self.log("Dark Reference captured (LEDs remained OFF).")
            self.set_state(self.STATE_NEEDS_WHITE_REF) 
        
        except (UninitializedAS7265XError, Exception) as e:
            processing_dialog.accept() # Close dialog on failure
            self.on_initialization_error(f"Failed to capture dark ref: {e}")

    # --- MODIFIED: run_white_ref (Added animation, merged IR logic) ---
    def run_white_ref(self):
        show_custom_message(self, "Action Required",
            "Place the **White Reference Tile** directly over the sensor lens.\n\nEnsure it is flat and covering the entire sensor. Click OK when ready.",
            "info", self.palette)
            
        processing_dialog = CustomDialog(
            self, "Capturing...", "Acquiring white reference...", "processing", self.palette
        )
        processing_dialog.show()
        QApplication.processEvents() # Force UI update
            
        try:
            self.log("Capturing white reference...")
            # --- Turn off other LEDs just in case ---
            as_uv_led_off()
            as_ir_led_off()
            # --- Turn on white LEDs ---
            _control_5050_led(True) 
            as_led_on()
            time.sleep(2.0)
            
            # --- MODIFIED: Calls the new, safe read_spectrometer() ---
            self.as_refs["white_ref"] = read_spectrometer()
            
            as_led_off()
            _control_5050_led(False)
            self.log("White Reference captured.")

            # --- Start of logic moved from old run_ir_ref ---
            self.as_refs["timestamp"] = datetime.now().isoformat()
            
            with open(AS_REFS_FILE, 'w') as f:
                json.dump(self.as_refs, f, indent=2)
            self.log(f"White Reference captured. All Refs JSON saved.")

            row_to_write = {}
            row_to_write["timestamp_iso"] = _get_with_nan(self.mq_baseline, "baseline_timestamp")
            row_to_write["operator"] = _get_with_nan(self.mq_baseline, "operator")
            row_to_write["ambient_temp"] = _get_with_nan(self.mq_baseline, "ambient_temp")
            row_to_write["ambient_hum"] = _get_with_nan(self.mq_baseline, "ambient_hum")
            row_to_write["baseline_mq137"] = _get_with_nan(self.mq_baseline, "baseline_mq137")
            row_to_write["baseline_mq135"] = _get_with_nan(self.mq_baseline, "baseline_mq135")
            row_to_write["baseline_mq4"] = _get_with_nan(self.mq_baseline, "baseline_mq4")
            row_to_write["baseline_mq3"] = _get_with_nan(self.mq_baseline, "baseline_mq3") # <-- Corrected
            
            dark_ref_data = self.as_refs.get("dark_ref", {})
            white_ref_data = self.as_refs.get("white_ref", {})
            # --- UV and IR data removed ---

            for i in range(1, 19):
                key_from = f"AS7265X_ch{i}"
                row_to_write[f"as_dark_ref_ch{i}"] = _get_with_nan(dark_ref_data, key_from)
                row_to_write[f"as_white_ref_ch{i}"] = _get_with_nan(white_ref_data, key_from)
                # --- UV and IR ref writing removed ---

            # --- MODIFIED: Writes to new, versioned file ---
            file_exists = os.path.exists(BASELINE_COLLECTION_FILE)
            with open(BASELINE_COLLECTION_FILE, 'a', newline='') as f:
                # Use the new, simplified header
                writer = csv.DictWriter(f, fieldnames=BASELINE_HEADER)
                if not file_exists:
                    writer.writeheader()
                # Filter row_to_write to only include keys in BASELINE_HEADER
                filtered_row = {h: _get_with_nan(row_to_write, h) for h in BASELINE_HEADER}
                writer.writerow(filtered_row)
            
            self.log(f"Full Baseline (MQ+AS) appended to {os.path.basename(BASELINE_COLLECTION_FILE)}")
            
            processing_dialog.accept() # Close dialog on success
            self.set_state(self.STATE_READY_TO_MEASURE)
            # --- End of moved logic ---

        except (UninitializedAS7265XError, Exception) as e:
            processing_dialog.accept() # Close dialog on failure
            as_led_off()
            _control_5050_led(False)
            self.on_initialization_error(f"Failed to capture/save white ref: {e}")
    # --- END MODIFICATION ---

    # --- DELETED run_uv_ref and run_ir_ref ---
        
    def run_show_sample_dialog(self):
        # (Unchanged)
        dialog = SampleDialog(self.palette, self)
        if dialog.exec():
            self.current_sample = dialog.get_sample_info()
            self.log(f"Sample selected: {self.current_sample['id']} at Hour {self.current_sample['hour']}.")
            self.show_handling_instructions()
        else:
            self.log("Sample selection cancelled.")

    def show_handling_instructions(self):
        # (Unchanged)
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
            self.current_sample["thaw_method"] = thaw_method
            self.current_sample["time_since_thaw_min"] = time_since_thaw
            message = f"For **Frozen** samples:\n\n1. Thaw Method: {thaw_method}\n2. Time Since Thaw: {time_since_thaw} min\n\nClick **Yes** when ready to measure."
            is_confirmed = show_custom_message(self, title, message, "confirm", self.palette)
        
        if is_confirmed:
            self.log(f"Handling confirmed for {storage} sample. Starting measurement.")
            self.run_measurement()
        else:
            self.log("Measurement cancelled by user at handling step.")
            self.set_state(self.STATE_READY_TO_MEASURE)

    def run_measurement(self):
        # (Unchanged)
        self.set_state(self.STATE_MEASURING)
        self.log("Starting measurement...")
        
        self.measurement_thread = QThread()
        self.measurement_worker = MeasurementWorker(self.current_sample, self.mq_baseline)
        self.measurement_worker.moveToThread(self.measurement_thread)
        
        self.measurement_worker.update_status.connect(self.log)
        self.measurement_worker.measurement_complete.connect(self.on_measurement_complete)
        self.measurement_worker.error.connect(self.on_measurement_error)
        
        self.measurement_thread.started.connect(self.measurement_worker.run)
        self.measurement_thread.start()

    def on_measurement_error(self, error_message):
        # (Unchanged)
        self.log(f"ERROR: {error_message}")
        show_custom_message(self, "Measurement Error", error_message, "error", self.palette)
        if self.measurement_thread and self.measurement_thread.isRunning():
            self.measurement_worker.stop()
            self.measurement_thread.quit()
            self.measurement_thread.wait()
        self.measurement_thread = None
        self.set_state(self.STATE_READY_TO_MEASURE)

    def on_measurement_complete(self, final_data_row_dict):
        # (Unchanged)
        if self.measurement_thread and self.measurement_thread.isRunning():
            self.measurement_thread.quit()
            self.measurement_thread.wait()
        self.measurement_thread = None
        self.log("Measurement complete. Awaiting classification.")
        self.set_state(self.STATE_SAVING)
        hour = final_data_row_dict.get("hour", 0)
        labels = ["Fresh", "Semi-Fresh", "Semi-Degraded", "Spoiled"]
        suggested_label = "Fresh"
        if hour >= 24: suggested_label = "Spoiled"
        elif hour >= 12: suggested_label = "Semi-Degraded"
        elif hour >= 6: suggested_label = "Semi-Fresh"
        
        label_index = 0
        try:
            label_index = labels.index(suggested_label)
        except ValueError:
            pass 

        label, ok = QInputDialog.getItem(
            self, "Confirm Classification", "Select the final label for this sample:",
            labels, label_index, False
        )
        if ok:
            final_data_row_dict["final_label"] = label
            self.log(f"Label '{label}' confirmed.")
            final_data_row_dict["ground_truth_value"] = label 
            self.save_final_row(final_data_row_dict)
        else:
            self.log("Saving cancelled by user.")
            self.set_state(self.STATE_READY_TO_MEASURE)

    def save_final_row(self, final_data_row_dict):
        # (Unchanged)
        self.log(f"Saving final row for {final_data_row_dict['sample_id']}...")
        try:
            row_to_write = {}
            for header in CANONICAL_HEADER:
                row_to_write[header] = _get_with_nan(final_data_row_dict, header)

            # --- MODIFIED: Writes to new, versioned file ---
            file_exists = os.path.exists(DATA_COLLECTION_FILE)
            with open(DATA_COLLECTION_FILE, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=CANONICAL_HEADER)
                if not file_exists:
                    writer.writeheader()
                writer.writerow(row_to_write)
                
            self.log(f"✅ Final data saved to {os.path.basename(DATA_COLLECTION_FILE)}.")
            show_custom_message(self, "Save Successful", f"Final avg data saved for {final_data_row_dict['sample_id']}.", "success", self.palette)
            
            hour = final_data_row_dict.get("hour", 0)
            storage = final_data_row_dict.get("storage_type", "Room")
            next_hour_map = {0: 6, 6: 12, 12: 24, 24: 36, 36: 48, 48: "COMPLETED"}
            next_hour = next_hour_map.get(hour, "COMPLETED")
            post_message = ""
            if next_hour == "COMPLETED":
                post_message = f"Measurement for **Hour {hour}** is complete.\n\nAll measurements for this sample are finished. You may discard the sample."
            else:
                post_message = f"Measurement for **Hour {hour}** is complete.\n\nPlease return the sample to **{storage}** storage.\n\nThe next measurement is at **Hour {next_hour}**."
            show_custom_message(self, "Measurement Complete", post_message, "info", self.palette)
            
            self.log("Starting 15s post-measurement purge... Fan ON.")
            self._control_fan(True) # <-- MODIFIED: Use real fan control
            self.set_state(self.STATE_POST_PURGE)
            QTimer.singleShot(15000, self.on_post_purge_complete)
            
        except Exception as e:
            self.log(f"CRITICAL ERROR saving row: {e}")
            show_custom_message(self, "Save Error", f"Failed to save final data row: {e}", "error", self.palette)
            self.set_state(self.STATE_READY_TO_MEASURE)

    @Slot()
    def on_post_purge_complete(self):
        # (Unchanged)
        self.log("Post-purge complete. Fan OFF.")
        self._control_fan(False) # <-- MODIFIED: Use real fan control
        self.set_state(self.STATE_READY_TO_MEASURE)

    def _ask_for_csv_file(self):
        # (Unchanged)
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
        btn_main = QPushButton(" Main Data")
        btn_main.setIcon(qta.icon('fa5s.file-alt', color=self.palette.get("BUTTON_TEXT", self.palette["BG"])))
        btn_raw = QPushButton(" Raw Block Data")
        btn_raw.setIcon(qta.icon('fa5s.database', color=self.palette.get("UNSELECTED_TEXT", "#555760")))
        btn_raw.setObjectName("secondary")
        btn_baseline = QPushButton(" Baseline Data")
        btn_baseline.setIcon(qta.icon('fa5s.history', color=self.palette.get("UNSELECTED_TEXT", "#555760")))
        btn_baseline.setObjectName("secondary")
        btn_layout.addWidget(btn_baseline)
        btn_layout.addWidget(btn_raw)
        btn_layout.addWidget(btn_main)
        layout.addLayout(btn_layout)
        
        # --- MODIFIED: Point buttons to the new, versioned files ---
        btn_main.clicked.connect(lambda: (setattr(dialog, 'choice', (DATA_COLLECTION_FILE, "Main Data")), dialog.accept()))
        btn_raw.clicked.connect(lambda: (setattr(dialog, 'choice', (RAW_BLOCK_DATA_FILE, "Raw Block Data")), dialog.accept()))
        btn_baseline.clicked.connect(lambda: (setattr(dialog, 'choice', (BASELINE_COLLECTION_FILE, "Baseline Data")), dialog.accept()))
        
        if not dialog.exec():
            return None, None
        return getattr(dialog, 'choice', (None, None))

    def show_csv_viewer(self):
        # (Unchanged)
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
        # (Unchanged)
        if self.baseline_thread and self.baseline_thread.isRunning():
            self.log("Stopping MQ Baseline worker...")
            self.baseline_worker.stop()
            self.baseline_thread.quit()
            self.baseline_thread.wait(1000)
            self.log("Worker stopped.")
        self.baseline_thread = None
        self.baseline_worker = None
        
        if self.measurement_thread and self.measurement_thread.isRunning():
            self.log("Stopping Measurement worker...")
            self.measurement_worker.stop()
            self.measurement_thread.quit()
            self.measurement_thread.wait(1000)
            self.log("Worker stopped.")
        self.measurement_thread = None
        self.measurement_worker = None

    def exit_training_mode(self):
        # (Unchanged)
        self.log("Exiting Training Mode...")
        self.stop_all_workers()
        self.log_display.clear()
        self.password_input.clear()
        self.set_state(self.STATE_LOCKED) 
        self.main_window.switch_page(2) # Switch to Settings
        print("Switched to Settings tab.")

    def email_csv_file(self):
        # (Unchanged)
        recipient_email = self.email_input.text().strip()
        if not re.match(r"[^@]+@[^@]+\.[^@]+", recipient_email):
            show_custom_message(self, "Invalid Email", "Please enter a valid recipient email address.", "warning", self.palette)
            return
        
        # --- MODIFIED: Point map to the new, versioned files ---
        file_map = {
            "Main Data": DATA_COLLECTION_FILE,
            "Raw Block Data": RAW_BLOCK_DATA_FILE,
            "Baseline Data": BASELINE_COLLECTION_FILE
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
        email_subject = f"PoultriScan Training Data :: {file_count} File(s) :: {date_str} {time_str}"
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
                                    <h2 style="font-size: 20px; color: {text_color}; margin: 5px 0 0 0;">Training Data Report</h2>
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 30px; font-size: 16px; line-height: 1.6;">
                                    <p>Dear Recipient,</p>
                                    <p>Attached, please find the PoultriScan data file(s) you requested:</p>
                                    <div style="border-left: 3px solid {accent}; padding-left: 15px; background-color: {bg}; padding: 10px 15px;">
                                        {file_name_list_html}
                                    </div>
                                    <p>These files contain data generated by the Training Mode module.</p>
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

    @Slot(str)
    def on_email_success(self, message):
        # (Unchanged)
        if self.processing_dialog:
            self.processing_dialog.accept()
        self.processing_dialog = None
        self.btn_email_csv.setEnabled(True)
        self.btn_email_csv.setText(" EMAIL DATA")
        show_custom_message(self, "Email Sent", message, "success", self.palette)
        self.log("Email sent successfully.")

    @Slot(str, str)
    def on_email_error(self, title, message):
        # (Unchanged)
        if self.processing_dialog:
            self.processing_dialog.accept()
        self.processing_dialog = None
        self.btn_email_csv.setEnabled(True)
        self.btn_email_csv.setText(" EMAIL DATA")
        show_custom_message(self, title, message, "error", self.palette)
        self.log(f"Email Error: {message}")


# --- 7. MODIFIED create_training_tab TO ACCEPT 4 ARGUMENTS ---
def create_training_tab(tab_control, palette, main_window, fan_chip_handle):
    """Creates the Training tab."""
    container = TrainingTab(palette, main_window, fan_chip_handle)
    return container