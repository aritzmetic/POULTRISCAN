# settings_tab.py

import sys
import os
import qtawesome as qta
import subprocess 
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QComboBox, QScrollArea
)
from PySide6.QtCore import (
    Qt, QTimer, QSize, QThread, QObject, Signal, Slot 
)
from PySide6.QtGui import QColor

from custom_dialog import show_custom_message

REPORT_FILE = "poultri_scan_report.csv"
DATABASE_LOG_FILE = "raw_database_log.csv" 


def _create_card(parent, title, palette, icon_name=None):
    """Helper to create a themed card."""
    card_frame = QWidget(parent)
    card_frame.setObjectName("card")
    card_layout = QVBoxLayout(card_frame)
    card_layout.setContentsMargins(10, 10, 10, 10) 
    title_frame = QWidget()
    title_layout = QHBoxLayout(title_frame)
    title_layout.setContentsMargins(0, 0, 0, 0)
    title_layout.setSpacing(5) 
    if icon_name:
        icon = qta.icon(icon_name, color=palette["ACCENT"])
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
    content_frame.setStyleSheet(f"background-color: {palette['SECONDARY_BG']};")
    card_layout.addWidget(content_frame)
    return card_frame, content_frame

def _create_status_indicator(parent, text, status_color, palette):
    """Creates a line item with a status icon and text."""
    frame = QWidget(parent)
    frame.setStyleSheet(f"background-color: {palette['SECONDARY_BG']};")
    layout = QHBoxLayout(frame)
    layout.setContentsMargins(0, 5, 0, 5)
    icon = qta.icon("fa5s.circle", color=status_color)
    light = QLabel()
    light.setPixmap(icon.pixmap(QSize(10, 10))) 
    layout.addWidget(light)
    layout.addWidget(QLabel(text))
    layout.addStretch()
    return frame

# --- 1. MODIFIED NetworkCheckWorker ---
class NetworkCheckWorker(QObject):
    """
    Worker thread to check for SSID and internet connectivity.
    """
    # Emits: (bool: has_internet, str: ssid_or_status)
    status_updated = Signal(bool, str)

    @Slot()
    def run_check(self):
        is_connected = False
        ssid = "Disconnected"
        
        # --- Step 1: Check for connected SSID ---
        try:
            # 'iwgetid -r' prints the SSID if connected, or errors if not.
            proc = subprocess.run(
                ['iwgetid', '-r'],
                capture_output=True, text=True, timeout=2
            )
            if proc.returncode == 0 and proc.stdout:
                ssid = proc.stdout.strip()
            else:
                ssid = "Disconnected"
        except FileNotFoundError:
            print("NetworkCheckWorker: 'iwgetid' not found. Cannot get SSID.")
            ssid = "Error: iwgetid missing"
        except Exception as e:
            print(f"NetworkCheckWorker (iwgetid) Error: {e}")
            ssid = "Disconnected"

        # --- Step 2: If connected to an AP, check for internet ---
        if ssid != "Disconnected":
            try:
                # -c 1 = 1 packet, -W 2 = 2-second timeout
                result = subprocess.run(
                    ["ping", "-c", "1", "-W", "2", "8.8.8.8"],
                    capture_output=True, text=True, check=False
                )
                if result.returncode == 0:
                    is_connected = True
            except Exception as e:
                print(f"NetworkCheckWorker (ping) Error: {e}")
                is_connected = False # Ping failed
            
        self.status_updated.emit(is_connected, ssid)
# --- END MODIFICATION ---


# --- Control Functions (Unchanged) ---
def restart_device_mock(parent, palette):
    is_confirmed = show_custom_message(parent, "Confirm Device Restart", "This will close the application and simulate a hardware reboot. Proceed?", "confirm", palette)
    if is_confirmed:
        show_custom_message(parent, "Restarting...", "Application closed. Device is now restarting (Simulation)...", "info", palette)
        QTimer.singleShot(1500, sys.exit) 

def exit_application(root_window):
    root_window.close()

def erase_all_report_data(parent, palette, reload_callback=None):
    is_confirmed = show_custom_message(parent, "Confirm Deletion", "Are you sure you want to permanently erase ALL PoultriScan test data (Main & Raw)?\nThis action cannot be undone.", "confirm", palette)
    if is_confirmed:
        files_to_delete = [REPORT_FILE, DATABASE_LOG_FILE]
        deleted_files = []
        errors = []
        
        for f in files_to_delete:
            try:
                if os.path.exists(f):
                    os.remove(f)
                    deleted_files.append(os.path.basename(f))
            except Exception as e:
                errors.append(f"Failed to erase {os.path.basename(f)}: {e}")

        if errors:
            show_custom_message(parent, "Deletion Error", "\n".join(errors), "error", palette)
        elif not deleted_files:
            show_custom_message(parent, "No Data Found", "No report files exist. Nothing to erase.", "info", palette)
        else:
            show_custom_message(parent, "Deletion Successful", f"All test data erased:\n{', '.join(deleted_files)}", "success", palette)

        if reload_callback:
            reload_callback()


class SettingsTabContent(QWidget):
    def __init__(self, tab_control, main_window, theme_switch_callback, palette, themes_dict, root_window, reload_reports_callback=None, parent=None):
        super().__init__(parent)
        
        self.palette = palette
        self.root_window = root_window
        self.network_check_thread = None
        self.network_check_worker = None
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5) 
        main_layout.setSpacing(10) 
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        btn_text_color = palette.get("BUTTON_TEXT", palette["BG"])
        danger_text_color = palette.get("DANGER_TEXT", palette["TEXT"])
        unselected_text_color = palette.get("UNSELECTED_TEXT", "#555760")

        # --- 1. THEME SETTINGS CARD (Unchanged) ---
        theme_card, theme_frame = _create_card(
            self, " Theme & Appearance Settings", palette, icon_name="fa5s.palette"
        )
        main_layout.addWidget(theme_card)
        theme_layout = QHBoxLayout(theme_frame)
        theme_layout.addWidget(QLabel("Current Theme:"))
        theme_combobox = QComboBox()
        theme_combobox.addItems(list(themes_dict.keys())) 
        theme_combobox.setCurrentText(main_window.current_theme_name)
        theme_layout.addWidget(theme_combobox, 1) 
        theme_combobox.currentTextChanged.connect(
            lambda theme_name: (
                setattr(main_window, 'current_theme_name', theme_name),
                theme_switch_callback()
            )
        )

        # --- 2. APPLICATION MANAGEMENT CARD (Unchanged) ---
        management_card, management_frame = _create_card(
            self, " Application & Device Management", palette, icon_name="fa5s.tools"
        )
        main_layout.addWidget(management_card)
        mgmt_layout = QHBoxLayout(management_frame)
        
        btn_training_mode = QPushButton(" TRAINING MODE")
        btn_training_mode.setObjectName("secondary")
        btn_training_mode.setIcon(qta.icon('fa5s.clipboard-list', color=unselected_text_color))
        btn_training_mode.clicked.connect(lambda: root_window.switch_page(4))
        mgmt_layout.addWidget(btn_training_mode)
        
        btn_restart_device = QPushButton(" RESTART DEVICE")
        btn_restart_device.setIcon(qta.icon('fa5s.redo', color=btn_text_color))
        btn_restart_device.clicked.connect(lambda: restart_device_mock(self, palette))
        mgmt_layout.addWidget(btn_restart_device)
        btn_erase_data = QPushButton(" ERASE TEST DATA")
        btn_erase_data.setObjectName("danger")
        btn_erase_data.setIcon(qta.icon('fa5s.trash', color=danger_text_color))
        btn_erase_data.clicked.connect(lambda: erase_all_report_data(self, palette, reload_reports_callback))
        mgmt_layout.addWidget(btn_erase_data)
        btn_exit = QPushButton(" EXIT APPLICATION")
        btn_exit.setObjectName("danger")
        btn_exit.setIcon(qta.icon('fa5s.times', color=danger_text_color))
        btn_exit.clicked.connect(lambda: exit_application(root_window))
        mgmt_layout.addWidget(btn_exit)

        # --- 3. SYSTEM INFO CARD (Unchanged) ---
        info_card, info_frame = _create_card(
            self, " System Information", palette, icon_name="fa5s.info-circle"
        )
        main_layout.addWidget(info_card)
        info_layout = QHBoxLayout(info_frame)
        col1_frame = QWidget()
        col1_layout = QVBoxLayout(col1_frame)
        col1_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        info_layout.addWidget(col1_frame, 1)
        
        l1 = QLabel(f"PoultriScan Version: 1.0.0")
        l1.setStyleSheet(f"color: {palette['ACCENT']}; font: bold 11pt 'Bahnschrift'; background-color: {palette['SECONDARY_BG']};") 
        col1_layout.addWidget(l1)
        
        time_label = QLabel("Current System Time: ...")
        time_label.setObjectName("dataLabel")
        col1_layout.addWidget(time_label)
        self.clock_timer = QTimer(self) 
        self.clock_timer.timeout.connect(lambda tl=time_label: tl.setText(f"Current System Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"))
        self.clock_timer.start(1000) 
        col1_layout.addStretch()
        l2 = QLabel("Review the 'About' tab for full details.")
        l2.setObjectName("dataLabel")
        col1_layout.addWidget(l2)
        
        # --- 2. MODIFIED: SECOND COLUMN (NETWORK STATUS) ---
        col2_frame = QWidget()
        col2_layout = QVBoxLayout(col2_frame)
        col2_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        info_layout.addWidget(col2_frame, 1)
        
        l3 = QLabel("Network Status")
        l3.setStyleSheet(f"color: {palette['TEXT']}; font: bold 11pt 'Bahnschrift'; background-color: {palette['SECONDARY_BG']};") 
        col2_layout.addWidget(l3)
        
        # Status Indicator
        status_frame = QWidget()
        status_frame_layout = QHBoxLayout(status_frame)
        status_frame_layout.setContentsMargins(0, 5, 0, 5)
        self.network_status_icon = qta.icon("fa5s.question-circle", color=palette["UNSELECTED_TEXT"])
        self.network_status_light = QLabel()
        self.network_status_light.setPixmap(self.network_status_icon.pixmap(QSize(10, 10)))
        status_frame_layout.addWidget(self.network_status_light)
        
        self.network_status_label = QLabel("Checking...")
        self.network_status_label.setWordWrap(True) # Allow text to wrap
        status_frame_layout.addWidget(self.network_status_label)
        status_frame_layout.addStretch()
        col2_layout.addWidget(status_frame)
        
        # Configure Button
        self.btn_configure_network = QPushButton(" CONFIGURE")
        self.btn_configure_network.setObjectName("secondary")
        self.btn_configure_network.setIcon(qta.icon('fa5s.wifi', color=unselected_text_color))
        self.btn_configure_network.clicked.connect(lambda: self.root_window.switch_page(5))
        self.btn_configure_network.setVisible(False) 
        col2_layout.addWidget(self.btn_configure_network)
        
        col2_layout.addStretch()
        # --- END MODIFICATION ---
        
        main_layout.addStretch() 

        self.setup_network_checker()

    def setup_network_checker(self):
        # (Unchanged from previous fix)
        self.network_check_thread = QThread()
        self.network_check_worker = NetworkCheckWorker()
        self.network_check_worker.moveToThread(self.network_check_thread)
        
        self.network_check_worker.status_updated.connect(self.on_network_status_updated)
        self.network_check_thread.started.connect(self.network_check_worker.run_check)
        self.network_check_worker.status_updated.connect(self.network_check_thread.quit)
        
        self.network_check_thread.finished.connect(self.network_check_worker.deleteLater)
        self.network_check_thread.finished.connect(self.network_check_thread.deleteLater)
        self.network_check_thread.finished.connect(self.on_network_check_finished)
        
        if not hasattr(self, 'network_timer'):
            self.network_timer = QTimer(self)
            self.network_timer.timeout.connect(self.run_network_check)
            self.network_timer.start(15000) # Check every 15 seconds
            self.run_network_check() # Initial check

    def run_network_check(self):
        # (Unchanged from previous fix)
        if self.network_check_thread and self.network_check_thread.isRunning():
            return
            
        self.network_status_label.setText("Checking...")
        self.network_status_label.setStyleSheet(f"color: {self.palette['TEXT']};")
        self.network_status_icon = qta.icon("fa5s.spinner", color=self.palette["ACCENT"], animation=qta.Spin(self.network_status_light))
        self.network_status_light.setPixmap(self.network_status_icon.pixmap(QSize(10, 10)))
        
        self.setup_network_checker() # Re-init thread/worker
        self.network_check_thread.start()

    @Slot()
    def on_network_check_finished(self):
        # (Unchanged from previous fix)
        self.network_check_thread = None
        self.network_check_worker = None

    # --- 3. MODIFIED on_network_status_updated ---
    @Slot(bool, str)
    def on_network_status_updated(self, is_connected, ssid):
        
        if ssid != "Disconnected" and "Error" not in ssid:
            # We are connected to a WiFi network
            if is_connected:
                # We have full internet access
                self.network_status_label.setText(f"Connected to: {ssid}")
                self.network_status_label.setStyleSheet(f"color: {self.palette['SUCCESS']};")
                self.network_status_icon = qta.icon("fa5s.check-circle", color=self.palette["SUCCESS"])
            else:
                # We are connected to WiFi, but no internet (e.g., local network only)
                self.network_status_label.setText(f"{ssid} (No Internet)")
                self.network_status_label.setStyleSheet(f"color: {self.palette['ACCENT']};")
                self.network_status_icon = qta.icon("fa5s.exclamation-triangle", color=self.palette["ACCENT"])
        else:
            # We are not connected to any network
            self.network_status_label.setText("Disconnected")
            self.network_status_label.setStyleSheet(f"color: {self.palette['DANGER']};")
            self.network_status_icon = qta.icon("fa5s.times-circle", color=self.palette["DANGER"])
            
        self.network_status_light.setPixmap(self.network_status_icon.pixmap(QSize(10, 10)))
        self.btn_configure_network.setVisible(True) # Always show config button
    # --- END MODIFICATION ---


    def closeEvent(self, event):
        # (Unchanged from previous fix)
        self.clock_timer.stop()
        if hasattr(self, 'network_timer'):
            self.network_timer.stop()
        if self.network_check_thread and self.network_check_thread.isRunning():
            self.network_check_thread.quit()
            self.network_check_thread.wait()
        super().closeEvent(event)


def create_settings_tab(tab_control, main_window, theme_switch_callback, palette, themes_dict, root_window, reload_reports_callback=None):
    # (Unchanged)
    settings_tab_content = SettingsTabContent(
        tab_control, main_window, theme_switch_callback, 
        palette, themes_dict, root_window, reload_reports_callback
    )

    container = QWidget()
    page_layout = QVBoxLayout(container)
    page_layout.setContentsMargins(0, 0, 0, 0)
    scroll_area = QScrollArea()
    scroll_area.setWidgetResizable(True)
    scroll_area.setWidget(settings_tab_content)
    page_layout.addWidget(scroll_area)
    
    return container