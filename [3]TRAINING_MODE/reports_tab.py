# reports_tab.py

import sys
import os
import csv
import qtawesome as qta
import re # For email validation
import smtplib # For sending email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders # For attaching file
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QTreeWidget, QTreeWidgetItem, QHeaderView,
    QFileDialog, QScrollArea, QLineEdit, QDialog
)
from PySide6.QtCore import Qt, QTimer, QSize, QThread, QObject, Signal, Slot
from PySide6.QtGui import QColor, QBrush, QFont

from custom_dialog import show_custom_message, CustomDialog

report_file = "poultri_scan_report.csv"
DATABASE_LOG_FILE = "raw_database_log.csv" # <-- 1. ADDED DATABASE FILE CONSTANT

# --- SMTP Configuration (Unchanged) ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "poultriscan4201@gmail.com"
SENDER_PASSWORD = "ikaggyzetigoajre"
# --- END SMTP Configuration ---


# --- 2. EmailWorker CLASS (UPDATED) ---
class EmailWorker(QObject):
    finished = Signal(str) 
    error = Signal(str, str)

    # Updated __init__ to accept subject, body, and file path
    def __init__(self, recipient, palette, smtp_server, smtp_port, 
                 sender_email, sender_password, report_file_path, 
                 email_subject, email_body):
        super().__init__()
        self.recipient_email = recipient
        self.palette = palette
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.sender_password = sender_password
        self.report_file = report_file_path
        self.email_subject = email_subject # New
        self.email_body = email_body     # New

    @Slot()
    def run(self):
        try:
            message = MIMEMultipart()
            message['From'] = self.sender_email
            message['To'] = self.recipient_email
            message['Subject'] = self.email_subject # Use parameter
            
            # Attach the HTML body
            message.attach(MIMEText(self.email_body, 'html'))
            
            # Attach the correct CSV file
            with open(self.report_file, "rb") as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f"attachment; filename= {os.path.basename(self.report_file)}",
            )
            message.attach(part)
            
            # Send the email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(message)
            
            self.finished.emit(f"Report successfully sent to:\n{self.recipient_email}")
        
        except smtplib.SMTPAuthenticationError:
            self.error.emit("Email Error", "Authentication failed. Please double-check SENDER_EMAIL and SENDER_PASSWORD (App Password).")
        except smtplib.SMTPConnectError:
            self.error.emit("Email Error", f"Could not connect to the email server ({self.smtp_server}). Check server/port and network connection.")
        except smtplib.SMTPServerDisconnected:
             self.error.emit("Email Error", "Server disconnected unexpectedly. Please try again.")
        except ConnectionRefusedError:
             self.error.emit("Email Error", f"Connection refused by the email server ({self.smtp_server}). Check server/port details.")
        except TimeoutError:
             self.error.emit("Email Error", f"Connection to the email server timed out. Check network connection.")
        except Exception as e:
            self.error.emit("Email Error", f"An unexpected error occurred:\n{type(e).__name__}: {e}")
# --- END EmailWorker CLASS ---


# --- 3. NEW RAW DATA VIEWER DIALOG ---
class RawDataViewer(QDialog):
    """
    A new dialog window to display the contents of the
    raw_database_log.csv file.
    """
    def __init__(self, palette, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Raw Database Log Viewer")
        self.setMinimumSize(750, 450) # <-- REDUCED Was 900, 600
        self.palette = palette
        self.setStyleSheet(f"QDialog {{ background-color: {palette['BG']}; }}")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Title
        title_label = QLabel("Raw Sensor Data (for Database)")
        title_label.setObjectName("subtitle")
        main_layout.addWidget(title_label)

        # Tree Widget
        self.tree = QTreeWidget()
        self.tree.setAlternatingRowColors(True)
        main_layout.addWidget(self.tree, 1)

        # Button Layout
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.close_btn = QPushButton(" Close")
        self.close_btn.setObjectName("secondary")
        self.close_btn.setIcon(qta.icon('fa5s.times', color=palette["UNSELECTED_TEXT"]))
        self.close_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.close_btn)
        
        main_layout.addLayout(button_layout)

    def load_raw_data(self):
        self.tree.clear()
        
        if not os.path.exists(DATABASE_LOG_FILE):
            item = QTreeWidgetItem(self.tree, ["Error: 'raw_database_log.csv' not found."])
            item.setForeground(0, QBrush(QColor(self.palette["DANGER"])))
            return

        try:
            with open(DATABASE_LOG_FILE, "r", newline="") as f:
                reader = csv.reader(f)
                
                # Read header dynamically
                try:
                    header = next(reader)
                    self.tree.setColumnCount(len(header))
                    self.tree.setHeaderLabels(header)
                except StopIteration:
                    self.tree.setHeaderLabels(["File is empty."])
                    return
                
                # Read data rows
                rows_to_insert = []
                for row in reader:
                    if row: # Skip empty rows
                        rows_to_insert.append(row)

            if not rows_to_insert:
                item = QTreeWidgetItem(self.tree, ["No raw data records found."])
                item.setForeground(0, QBrush(QColor(self.palette["UNSELECTED_TEXT"])))
            else:
                for data in rows_to_insert:
                    item = QTreeWidgetItem(self.tree, data)
            
            # Resize columns
            for i in range(self.tree.columnCount()):
                self.tree.header().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

        except Exception as e:
            self.tree.clear()
            item = QTreeWidgetItem(self.tree, [f"Error reading file: {e}"])
            item.setForeground(0, QBrush(QColor(self.palette["DANGER"])))


def _create_card(parent, title, palette, icon_name=None):
    """Helper to create a themed card."""
    card_frame = QWidget(parent)
    card_frame.setObjectName("card")
    card_layout = QVBoxLayout(card_frame)
    card_layout.setContentsMargins(10, 10, 10, 10) # <-- REDUCED
    title_frame = QWidget()
    title_layout = QHBoxLayout(title_frame)
    title_layout.setContentsMargins(0, 0, 0, 0)
    title_layout.setSpacing(5) # <-- REDUCED
    if icon_name:
        icon = qta.icon(icon_name, color=palette["ACCENT"])
        icon_label = QLabel()
        icon_label.setPixmap(icon.pixmap(QSize(20, 20))) # <-- REDUCED Was 35, 35
        icon_label.setStyleSheet("background-color: transparent;")
        title_layout.addWidget(icon_label)
    title_label = QLabel(title)
    title_label.setObjectName("subtitle")
    title_layout.addWidget(title_label)
    title_layout.addStretch()
    card_layout.addWidget(title_frame)
    content_frame = QWidget()
    content_frame.setStyleSheet(f"background-color: {palette['SECONDARY_BG']};")
    card_layout.addWidget(content_frame)
    return card_frame, content_frame

class ReportsTab(QWidget):
    def __init__(self, palette, root_window, parent=None):
        super().__init__(parent)

        self.palette = palette
        self.root_window = root_window
        self.email_thread = None
        self.email_worker = None
        self.processing_dialog = None

        # --- Main Layout ---
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        main_layout = QVBoxLayout(scroll_content)
        main_layout.setContentsMargins(5, 5, 5, 5) # <-- REDUCED
        main_layout.setSpacing(10) # <-- REDUCED

        # --- 1. REPORT CONTROL CARD (UPDATED) ---
        control_card, control_frame = _create_card(
            scroll_content, " Report Control & Actions", palette, icon_name="fa5s.tasks"
        )
        main_layout.addWidget(control_card)
        control_layout = QHBoxLayout(control_frame)
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(10) # <-- REDUCED
        
        self.btn_reload = QPushButton(" RELOAD Data")
        self.btn_reload.setIcon(qta.icon('fa5s.sync-alt', color=palette.get("BUTTON_TEXT", palette["BG"])))
        control_layout.addWidget(self.btn_reload)
        
        # --- 4. ADDED "SHOW RAW DATA" BUTTON ---
        self.btn_show_raw = QPushButton(" SHOW RAW DATA")
        self.btn_show_raw.setIcon(qta.icon('fa5s.database', color=palette.get("UNSELECTED_TEXT", "#555760")))
        self.btn_show_raw.setObjectName("secondary")
        control_layout.addWidget(self.btn_show_raw)
        
        control_layout.addStretch(1)
        
        control_layout.addWidget(QLabel("Email to:"))
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("recipient@example.com")
        self.email_input.setMinimumWidth(200) # <-- REDUCED Was 300
        control_layout.addWidget(self.email_input)
        
        self.btn_email = QPushButton(" EMAIL REPORT")
        self.btn_email.setIcon(qta.icon('fa5s.paper-plane', color=palette.get("BUTTON_TEXT", palette["BG"])))
        control_layout.addWidget(self.btn_email)
        
        self.btn_export = QPushButton(" EXPORT CSV")
        self.btn_export.setIcon(qta.icon('fa5s.save', color=palette.get("UNSELECTED_TEXT", "#555760")))
        self.btn_export.setObjectName("secondary")
        control_layout.addWidget(self.btn_export)

        # --- 2. REPORT DATA CARD ---
        data_card, data_frame = _create_card(
            scroll_content, " PoultriScan Test History", palette, icon_name="fa5s.history"
        )
        main_layout.addWidget(data_card, 1)
        data_layout = QVBoxLayout(data_frame)
        data_layout.setContentsMargins(0, 0, 0, 0)
        
        # --- MODIFIED: Changed MQ-7 to MQ-3 ---
        self.columns = (
            "Timestamp", "Sample ID", "Type", "Temperature", "Humidity",
            "WHC Index", "Fatty Acid Profile", "Myoglobin", "MQ-137 (NH3)",
            "MQ-135 (Air Quality)", "MQ-3 (Alcohol)", "MQ-4 (CH4)", "Quality"
        )
        # --- END MODIFICATION ---
        
        self.tree = QTreeWidget()
        self.tree.setColumnCount(len(self.columns))
        self.tree.setHeaderLabels(self.columns)
        self.tree.setAlternatingRowColors(True)
        data_layout.addWidget(self.tree)
        
        # Column Sizing
        # --- MODIFIED: Changed MQ-7 to MQ-3 ---
        numerical_cols = ["Temperature", "Humidity", "WHC Index", "Fatty Acid Profile", "Myoglobin", "MQ-137 (NH3)", "MQ-135 (Air Quality)", "MQ-3 (Alcohol)", "MQ-4 (CH4)"]
        # --- END MODIFICATION ---
        
        for i, col in enumerate(self.columns):
            if col in numerical_cols:
                self.tree.header().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
                self.tree.setColumnWidth(i, 110)
            elif col in ["Sample ID", "Quality"]:
                self.tree.header().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
                self.tree.setColumnWidth(i, 100)
            elif col == "Timestamp":
                self.tree.setColumnWidth(i, 120) # <-- REDUCED
            else:
                self.tree.header().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

        scroll_area.setWidget(scroll_content)
        page_layout.addWidget(scroll_area)
        
        # --- Connect Signals ---
        self.btn_reload.clicked.connect(self.load_report_data)
        self.btn_export.clicked.connect(self.mock_export_report_data)
        self.btn_email.clicked.connect(self.email_report_data)
        self.btn_show_raw.clicked.connect(self.show_raw_data_viewer) # <-- 5. CONNECTED NEW BUTTON
        
        self.load_report_data()

    # --- 6. NEW METHOD TO SHOW DIALOG ---
    def show_raw_data_viewer(self):
        dialog = RawDataViewer(self.palette, self)
        dialog.load_raw_data()
        dialog.exec()

    def mock_export_report_data(self):
        # (Unchanged)
        if not os.path.exists(report_file):
            show_custom_message(self.root_window, "Export Failed", "No report file found to export.", "warning", self.palette)
            return
        export_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export PoultriScan Report",
            "PoultriScan_Export.csv",
            "CSV files (*.csv)"
        )
        if export_path:
            try:
                import shutil
                shutil.copyfile(report_file, export_path)
                show_custom_message(self.root_window, "Export Successful", f"Report exported successfully to:\n{export_path}", "success", self.palette)
            except Exception as e:
                 show_custom_message(self.root_window, "Export Error", f"Failed to copy file: {e}", "error", self.palette)

    # --- 7. MODIFIED EMAIL METHOD ---
    def email_report_data(self):
        # --- A. Ask user which report to send ---
        dialog = QDialog(self.root_window)
        dialog.setWindowTitle("Select Report Type")
        dialog.setStyleSheet(f"QDialog {{ background-color: {self.palette['SECONDARY_BG']}; padding: 20px; }}")
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)
        
        label = QLabel("Which report would you like to email?")
        label.setFont(QFont("Bahnschrift", 11)) # <-- REDUCED
        layout.addWidget(label)
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        btn_main = QPushButton(" Main Report")
        btn_main.setIcon(qta.icon('fa5s.file-alt', color=self.palette.get("BUTTON_TEXT", self.palette["BG"])))
        
        btn_raw = QPushButton(" Raw Data Log")
        btn_raw.setIcon(qta.icon('fa5s.database', color=self.palette.get("UNSELECTED_TEXT", "#555760")))
        btn_raw.setObjectName("secondary")

        btn_layout.addWidget(btn_raw)
        btn_layout.addWidget(btn_main)
        layout.addLayout(btn_layout)
        
        # Store choice in a dialog attribute
        btn_main.clicked.connect(lambda: (setattr(dialog, 'choice', 'main'), dialog.accept()))
        btn_raw.clicked.connect(lambda: (setattr(dialog, 'choice', 'raw'), dialog.accept()))
        
        if not dialog.exec():
            return # User cancelled
        
        chosen_report = getattr(dialog, 'choice', None)
        if not chosen_report:
            return

        # --- B. Set file paths, subject, and body based on choice ---
        recipient_email = self.email_input.text().strip()
        if not re.match(r"[^@]+@[^@]+\.[^@]+", recipient_email):
            show_custom_message(self.root_window, "Invalid Email", "Please enter a valid recipient email address.", "warning", self.palette)
            return
        
        file_to_send = ""
        email_subject = ""
        email_body = ""
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")
        
        accent_color = self.palette.get("ACCENT", "#E6B800")
        primary_color = self.palette.get("PRIMARY", "#B8860B")
        
        if chosen_report == 'main':
            file_to_send = report_file
            email_subject = f"PoultriScan Quality Report :: {date_str} {time_str}"
            email_body = f"""
            <html><body><div style="font-family: Arial; padding: 25px; background-color: #f7f7f7;">
                <div style="padding: 30px; border: 1px solid #dddddd; border-radius: 8px; background-color: #ffffff; max-width: 650px; margin: 20px auto;">
                    <div style="font-size: 20pt; font-weight: bold; color: {primary_color}; border-bottom: 3px solid {accent_color}; padding-bottom: 15px; margin-bottom: 20px;">
                        PoultriScan Quality Analysis Report
                    </div>
                    <p>Dear Recipient,</p>
                    <p>The attached CSV file contains the <b>Main Test History Report</b> generated by the PoultriScan system.</p>
                    <p>This report includes sample IDs, timestamps, sensor indexes, and the final quality assessment.</p>
                    <p style="font-style: italic; color: #777777; font-size: 10pt; margin-top: 20px;">
                        Report Generated: {date_str} at {time_str}
                    </p>
                </div></div></body></html>
            """
        else: # chosen_report == 'raw'
            file_to_send = DATABASE_LOG_FILE
            email_subject = f"PoultriScan RAW DATA LOG :: {date_str} {time_str}"
            email_body = f"""
            <html><body><div style="font-family: Arial; padding: 25px; background-color: #f7f7f7;">
                <div style="padding: 30px; border: 1px solid #dddddd; border-radius: 8px; background-color: #ffffff; max-width: 650px; margin: 20px auto;">
                    <div style="font-size: 20pt; font-weight: bold; color: {primary_color}; border-bottom: 3px solid {accent_color}; padding-bottom: 15px; margin-bottom: 20px;">
                        PoultriScan Raw Sensor Data Log
                    </div>
                    <p>Dear Recipient,</p>
                    <p>The attached CSV file contains the <b>Raw Sensor Data Log</b>, formatted for database import (matching tbl_reading).</p>
                    <p>This file includes sample IDs, timestamps, and all raw sensor values (temp, hum, MQ-volts, and 18-channel AS7265x readings).</p>
                    <p style="font-style: italic; color: #777777; font-size: 10pt; margin-top: 20px;">
                        Log Generated: {date_str} at {time_str}
                    </p>
                </div></div></body></html>
            """
            
        if not os.path.exists(file_to_send):
            show_custom_message(self.root_window, "Email Failed", f"The file '{os.path.basename(file_to_send)}' was not found. Please run a test to generate it.", "warning", self.palette)
            return

        # --- C. Start the email worker with new parameters ---
        self.processing_dialog = CustomDialog(
            self.root_window, 
            "Sending Email", 
            f"Sending '{os.path.basename(file_to_send)}' to {recipient_email}...", 
            "processing", 
            self.palette
        )
        
        self.email_thread = QThread()
        self.email_worker = EmailWorker(
            recipient=recipient_email,
            palette=self.palette,
            smtp_server=SMTP_SERVER,
            smtp_port=SMTP_PORT,
            sender_email=SENDER_EMAIL,
            sender_password=SENDER_PASSWORD,
            report_file_path=file_to_send,    # Pass correct file
            email_subject=email_subject,      # Pass correct subject
            email_body=email_body             # Pass correct body
        )
        self.email_worker.moveToThread(self.email_thread)
        self.email_thread.started.connect(self.email_worker.run)
        self.email_worker.finished.connect(self.on_email_success)
        self.email_worker.error.connect(self.on_email_error)
        self.email_worker.finished.connect(self.email_thread.quit)
        self.email_worker.finished.connect(self.email_worker.deleteLater)
        self.email_thread.finished.connect(self.email_thread.deleteLater)
        
        self.btn_email.setEnabled(False)
        self.btn_email.setText(" SENDING...")
        icon_color = self.palette.get("BUTTON_TEXT", self.palette["BG"])
        self.btn_email.setIcon(qta.icon('fa5s.spinner', color=icon_color, animation=qta.Spin(self.btn_email)))
        
        self.email_thread.start()
        self.processing_dialog.show()

    @Slot(str)
    def on_email_success(self, message):
        # (Unchanged)
        if self.processing_dialog:
            self.processing_dialog.accept()
            self.processing_dialog = None
        self.btn_email.setEnabled(True)
        self.btn_email.setText(" EMAIL REPORT")
        icon_color = self.palette.get("BUTTON_TEXT", self.palette["BG"])
        self.btn_email.setIcon(qta.icon('fa5s.paper-plane', color=icon_color))
        show_custom_message(self.root_window, "Email Sent", message, "success", self.palette)

    @Slot(str, str)
    def on_email_error(self, title, message):
        # (Unchanged)
        if self.processing_dialog:
            self.processing_dialog.accept()
            self.processing_dialog = None
        self.btn_email.setEnabled(True)
        self.btn_email.setText(" EMAIL REPORT")
        icon_color = self.palette.get("BUTTON_TEXT", self.palette["BG"])
        self.btn_email.setIcon(qta.icon('fa5s.paper-plane', color=icon_color))
        show_custom_message(self.root_window, title, message, "error", self.palette)


    def load_report_data(self):
        # (Unchanged)
        self.tree.clear()
        brush_nodata = QBrush(QColor(self.palette["UNSELECTED_TEXT"]))
        nodata_font = QFont("Bahnschrift", 9, italic=True) # <-- REDUCED
        loading_item = QTreeWidgetItem(self.tree, ["", "Loading report data..."] + [""] * (len(self.columns) - 2))
        loading_item.setForeground(0, brush_nodata)
        loading_item.setFont(0, nodata_font)
        QTimer.singleShot(50, self._perform_load)

    def _perform_load(self):
        # (Unchanged)
        self.tree.clear()
        brush_high = QBrush(QColor(self.palette["SUCCESS"]))
        brush_low = QBrush(QColor(self.palette["DANGER"]))
        brush_normal = QBrush(QColor(self.palette["NORMAL_COLOR"]))
        brush_nodata = QBrush(QColor(self.palette["UNSELECTED_TEXT"]))
        nodata_font = QFont("Bahnschrift", 9, italic=True) # <-- REDUCED
        
        num_cols = len(self.columns)
        
        if not os.path.exists(report_file):
            item = QTreeWidgetItem(self.tree, ["N/A", "No Data Found. Run Analysis or check Settings."] + ["N/A"] * (num_cols - 2))
            for i in range(self.tree.columnCount()):
                item.setForeground(i, brush_nodata)
                item.setFont(i, nodata_font)
            return
        try:
            rows_to_insert = []
            with open(report_file, "r", newline="") as f:
                reader = csv.reader(f)
                try:
                    next(reader)
                except StopIteration:
                     item = QTreeWidgetItem(self.tree, ["N/A", "Report file is empty."] + ["N/A"] * (num_cols - 2))
                     for i in range(self.tree.columnCount()):
                         item.setForeground(i, brush_nodata)
                         item.setFont(i, nodata_font)
                     return
                for row in reader:
                    if len(row) >= num_cols:
                        rows_to_insert.append(row[:num_cols])
                    else:
                        print(f"Skipping malformed row: {row}")
            if not rows_to_insert:
                 item = QTreeWidgetItem(self.tree, ["N/A", "No valid data found in report file."] + ["N/A"] * (num_cols - 2))
                 for i in range(self.tree.columnCount()):
                     item.setForeground(i, brush_nodata)
                     item.setFont(i, nodata_font)
            for data in rows_to_insert:
                item = QTreeWidgetItem(self.tree, data)
                quality = str(data[-1]).upper()
                if quality in ['FRESH', 'SLIGHTLY FRESH']:
                    item.setForeground(self.columns.index("Quality"), brush_high)
                elif quality == 'NORMAL':
                    item.setForeground(self.columns.index("Quality"), brush_normal)
                elif quality == 'SPOILT':
                    item.setForeground(self.columns.index("Quality"), brush_low)
        except Exception as e:
            self.tree.clear()
            error_msg = f"Error reading report file: {e}"
            print(error_msg)
            show_custom_message(self, "Report Error", error_msg, "error", self.palette)
            item = QTreeWidgetItem(self.tree, ["N/A", "Error loading data."] + ["N/A"] * (num_cols - 2))
            for i in range(self.tree.columnCount()):
                item.setForeground(i, brush_nodata)
                item.setFont(i, nodata_font)