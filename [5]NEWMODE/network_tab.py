# network_tab.py

import sys
import os
import qtawesome as qta
import subprocess
import re
import time
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QComboBox, QScrollArea, QTreeWidget, QTreeWidgetItem,
    QLineEdit, QHeaderView
)
from PySide6.QtCore import Qt, QTimer, QSize, QThread, QObject, Signal, Slot
from PySide6.QtGui import QColor, QFont, QBrush

from custom_dialog import show_custom_message

# --- Helper function (Unchanged) ---
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
# --- End Helper ---


class NetworkScanWorker(QObject):
    """
    Worker thread to scan for WiFi networks.
    """
    finished = Signal(list)
    error = Signal(str)

    def _parse_iwlist_output(self, text):
        """Parses the complex output of 'iwlist scan'."""
        networks = []
        
        # --- FIX: Make whitespace flexible to handle output variations ---
        cells = re.split(r'Cell \d+\s*-\s*Address:\s*', text)
        
        for cell_data in cells[1:]: # Skip the header
            ssid_match = re.search(r'ESSID:"(.*?)"', cell_data, re.DOTALL)
            signal_match = re.search(r'Signal level[=:]\s*(.*?dBm)', cell_data, re.DOTALL)

            if ssid_match and signal_match:
                ssid = ssid_match.group(1).strip()
                
                if not ssid or ssid == "\\x00":
                    continue
                
                signal = signal_match.group(1).strip()
                
                security = "Open"
                if re.search(r'Encryption key:\s*on', cell_data, re.DOTALL):
                    if re.search(r'IE:.*\s+(WPA|WPA2)\s+', cell_data, re.DOTALL):
                        security = "WPA/WPA2"
                    else:
                        security = "WEP" 
                
                networks.append({"ssid": ssid, "signal": signal, "security": security})
        return networks

    @Slot()
    def run_scan(self):
        try:
            print("NetworkTab: Running 'iwlist wlan0 scan'...") 
            
            # --- FIX: Force C locale for consistent English output ---
            proc_env = os.environ.copy()
            proc_env['LC_ALL'] = 'C'
            
            proc = subprocess.run(
                ['iwlist', 'wlan0', 'scan'],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
                env=proc_env  # Use the modified environment
            )
            
            networks = self._parse_iwlist_output(proc.stdout)
            print(f"NetworkTab: Scan complete, found {len(networks)} networks.")
            self.finished.emit(networks)
            
        except FileNotFoundError:
            self.error.emit("'iwlist' not found. Is 'wireless-tools' installed?")
        except subprocess.CalledProcessError as e:
            if "Network is down" in e.stderr:
                self.error.emit("Scan failed: WiFi interface (wlan0) is down.")
            else:
                self.error.emit(f"Scan command failed: {e.stderr}")
        except subprocess.TimeoutExpired:
            self.error.emit("Scan timed out. 'iwlist' took too long to respond.")
        except Exception as e:
            self.error.emit(f"An unexpected error occurred during scan: {e}")


class NetworkConnectWorker(QObject):
    """
    (Unchanged from last fix) Worker thread to connect using 'wpa_cli'.
    """
    finished = Signal(str)
    error = Signal(str, str) # title, message

    def __init__(self, ssid, password):
        super().__init__()
        self.ssid = ssid
        self.password = password

    def run_wpa_cli(self, cmd_list):
        """Helper function to run wpa_cli commands."""
        base_cmd = ['wpa_cli', '-i', 'wlan0']
        proc = subprocess.run(base_cmd + cmd_list, capture_output=True, text=True, timeout=5)
        print(f"NetworkTab: CMD: {' '.join(base_cmd + cmd_list)} -> STDOUT: {proc.stdout.strip()} | STDERR: {proc.stderr.strip()}")
        
        if "save_config" not in cmd_list:
            if proc.returncode != 0 or "FAIL" in proc.stdout:
                error_msg = proc.stderr.strip() or proc.stdout.strip()
                raise Exception(f"Failed to run: {' '.join(cmd_list)}\n{error_msg}")
        return proc.stdout.strip()

    @Slot()
    def run_connect(self):
        try:
            if not self.ssid:
                self.error.emit("Connection Error", "No network selected.")
                return
            if not self.password or len(self.password) < 8:
                self.error.emit("Connection Error", "Password must be at least 8 characters.")
                return
            
            print(f"NetworkTab: Connecting to {self.ssid} using wpa_cli...")

            net_id = self.run_wpa_cli(['add_network'])
            if not net_id.isdigit():
                raise Exception(f"Failed to get new network ID. Got: {net_id}")
            print(f"NetworkTab: Got new network ID: {net_id}")
            
            self.run_wpa_cli(['set_network', net_id, 'ssid', f'"{self.ssid}"'])
            self.run_wpa_cli(['set_network', net_id, 'psk', f'"{self.password}"'])
            self.run_wpa_cli(['enable_network', net_id])
            
            print(f"NetworkTab: Forcing disconnect to switch networks...")
            self.run_wpa_cli(['disconnect'])
            self.run_wpa_cli(['reassociate'])
            print(f"NetworkTab: Sent 'reassociate' for {self.ssid}.")
            print("NetworkTab: Configuration enabled in-memory.")
            
            print(f"NetworkTab: Verifying connection to {self.ssid}...")
            
            max_wait_time_sec = 15
            for i in range(max_wait_time_sec):
                time.sleep(1) 
                try:
                    status_output = self.run_wpa_cli(['status'])
                    
                    ssid_match = re.search(r'^ssid=(.*)', status_output, re.MULTILINE)
                    state_match = re.search(r'^wpa_state=(.*)', status_output, re.MULTILINE)
                    
                    if ssid_match and state_match:
                        current_ssid = ssid_match.group(1)
                        current_state = state_match.group(1)
                        
                        print(f"NetworkTab: Verification... (State: {current_state}, SSID: {current_ssid})")
                        
                        if current_ssid == self.ssid and current_state == 'COMPLETED':
                            self.finished.emit(f"Successfully connected to {self.ssid}!")
                            return

                        if 'WRONG_KEY' in status_output:
                            self.error.emit("Connection Failed", "Connection failed: WRONG_KEY. Please check your password.")
                            return
                        
                except Exception as e:
                    print(f"NetworkTab: Poll error: {e}")

            self.error.emit("Connection Timed Out", "The connection attempt timed out. The network may be out of range or password may be incorrect.")
            
        except FileNotFoundError:
            self.error.emit("Command Error", "'wpa_cli' not found. Is 'wpa_supplicant' installed?")
        except subprocess.TimeoutExpired:
            self.error.emit("Timeout Error", "A wpa_cli command timed out. Network interface may be busy.")
        except Exception as e:
            self.error.emit("Connection Error", f"Failed to connect:\n{str(e)}")


class NetworkTab(QWidget):
    def __init__(self, palette, root_window, parent=None):
        super().__init__(parent)
        self.palette = palette
        self.root_window = root_window 
        
        self.scan_thread = None
        self.scan_worker = None
        self.connect_thread = None
        self.connect_worker = None
        self.scan_animation = None
        
        self.unselected_text_color = palette.get("UNSELECTED_TEXT", "#555760")
        self.btn_text_color = palette.get("BUTTON_TEXT", palette["BG"])
        self.btn_scan_icon = qta.icon('fa5s.sync-alt', color=self.btn_text_color)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(10)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # --- Network Config Card (Unchanged) ---
        net_card, net_frame = _create_card(
            self, " Network Configuration (wlan0)", palette, icon_name="fa5s.wifi"
        )
        main_layout.addWidget(net_card)
        net_layout = QVBoxLayout(net_frame)
        
        scan_layout = QHBoxLayout()
        scan_layout.addWidget(QLabel("Available Wireless Networks:"))
        scan_layout.addStretch()
        self.btn_scan = QPushButton(" SCAN")
        self.btn_scan.setIcon(self.btn_scan_icon)
        
        # --- 1. MODIFIED: Connect to 'start_scan' directly ---
        self.btn_scan.clicked.connect(self.start_scan)
        scan_layout.addWidget(self.btn_scan)
        net_layout.addLayout(scan_layout)
        
        self.network_tree = QTreeWidget()
        self.network_tree.setColumnCount(3)
        self.network_tree.setHeaderLabels(["SSID (Network Name)", "Signal", "Security"])
        self.network_tree.setAlternatingRowColors(True)
        self.network_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.network_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.network_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        net_layout.addWidget(self.network_tree)
        
        connect_layout = QHBoxLayout()
        connect_layout.addWidget(QLabel("Password:"))
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Enter network password...")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        connect_layout.addWidget(self.password_input, 1)
        self.btn_connect = QPushButton(" CONNECT")
        self.btn_connect.setIcon(qta.icon('fa5s.plug', color=self.btn_text_color))
        self.btn_connect.clicked.connect(self.start_connection)
        connect_layout.addWidget(self.btn_connect)
        net_layout.addLayout(connect_layout)
        
        main_layout.addStretch()
        
        self.btn_back = QPushButton(" BACK TO SETTINGS")
        self.btn_back.setObjectName("secondary")
        self.btn_back.setIcon(qta.icon('fa5s.arrow-left', color=self.unselected_text_color))
        # --- 2. MODIFIED: Connect to simple 'go_back' slot ---
        self.btn_back.clicked.connect(self.go_back)
        main_layout.addWidget(self.btn_back, 0, Qt.AlignmentFlag.AlignBottom)

        # --- 3. MODIFIED: Removed all timers ---
        # No automatic scanning. Only manual scans.
        
    @Slot()
    def go_back(self):
        """Switches tabs back to settings."""
        self.root_window.switch_page(2) # Index 2 is Settings
        
    # --- 4. REMOVED: showEvent, hideEvent, start_scan_timer ---
    # These are no longer needed as we are not using a timer.
        
    @Slot()
    def start_scan(self):
        """
        Slot for the manual scan button.
        This is now the ONLY way a scan is triggered.
        """
        if self.scan_thread and self.scan_thread.isRunning():
            print("NetworkTab: Scan already in progress, skipping.")
            return
            
        # Start the animation
        self.scan_animation = qta.Spin(self.btn_scan)
        self.btn_scan.setIcon(qta.icon('fa5s.spinner', color=self.btn_text_color, animation=self.scan_animation))
        self.btn_scan.setText(" SCANNING...")
        self.btn_scan.setEnabled(False)

        # Show "Scanning..." in the list
        self.network_tree.clear()
        item = QTreeWidgetItem(self.network_tree, ["Scanning for networks..."])
        item.setForeground(0, QBrush(QColor(self.palette["UNSELECTED_TEXT"])))
        
        self.scan_thread = QThread()
        self.scan_worker = NetworkScanWorker()
        self.scan_worker.moveToThread(self.scan_thread)
        
        self.scan_thread.started.connect(self.scan_worker.run_scan)
        self.scan_worker.finished.connect(self.on_scan_finished)
        self.scan_worker.error.connect(self.on_scan_error)
        
        self.scan_worker.finished.connect(self.scan_thread.quit)
        self.scan_worker.error.connect(self.scan_thread.quit) 
        
        self.scan_thread.finished.connect(self.scan_worker.deleteLater)
        self.scan_thread.finished.connect(self.scan_thread.deleteLater)
        self.scan_thread.finished.connect(self.on_scan_thread_finished) 
        
        self.scan_thread.start()

    @Slot()
    def on_scan_thread_finished(self):
        """Resets the scan button and animation."""
        self.scan_thread = None
        self.scan_worker = None
        
        if self.scan_animation:
            self.scan_animation.stop()
            self.scan_animation = None
        self.btn_scan.setIcon(self.btn_scan_icon)
        self.btn_scan.setText(" SCAN")
        self.btn_scan.setEnabled(True)

    @Slot(list)
    def on_scan_finished(self, networks):
        current_selection = None
        if self.network_tree.currentItem():
            current_selection = self.network_tree.currentItem().text(0)
            
        self.network_tree.clear() 
        if not networks:
            item = QTreeWidgetItem(self.network_tree, ["No networks found."])
            item.setForeground(0, QBrush(QColor(self.palette["UNSELECTED_TEXT"])))
        else:
            try:
                networks.sort(key=lambda x: int(x['signal'].split(' ')[0]), reverse=True)
            except Exception:
                pass 
            
            for net in networks:
                item = QTreeWidgetItem(self.network_tree, [net["ssid"], net["signal"], net["security"]])
                if net["ssid"] == current_selection:
                    self.network_tree.setCurrentItem(item) 
        
    @Slot(str)
    def on_scan_error(self, error_msg):
        self.network_tree.clear() 
        item = QTreeWidgetItem(self.network_tree, [f"{error_msg}"])
        item.setForeground(0, QBrush(QColor(self.palette["DANGER"])))
        show_custom_message(self.root_window, "Scan Error", error_msg, "error", self.palette)

    # --- Connection logic (unchanged) ---
    def start_connection(self):
        if self.connect_thread and self.connect_thread.isRunning():
            return
            
        selected_item = self.network_tree.currentItem()
        if not selected_item:
            show_custom_message(self.root_window, "Connection Error", "Please select a network from the list.", "warning", self.palette)
            return
            
        ssid = selected_item.text(0)
        password = self.password_input.text()

        self.btn_connect.setEnabled(False)
        self.btn_connect.setText(" CONNECTING...")
        
        self.connect_thread = QThread()
        self.connect_worker = NetworkConnectWorker(ssid, password)
        self.connect_worker.moveToThread(self.connect_thread)

        self.connect_thread.started.connect(self.connect_worker.run_connect)
        self.connect_worker.finished.connect(self.on_connect_finished)
        self.connect_worker.error.connect(self.on_connect_error)

        self.connect_worker.finished.connect(self.connect_thread.quit)
        self.connect_worker.error.connect(self.connect_thread.quit)
        
        self.connect_thread.finished.connect(self.connect_worker.deleteLater)
        self.connect_thread.finished.connect(self.connect_thread.deleteLater)
        self.connect_thread.finished.connect(self.on_connect_thread_finished)

        self.connect_thread.start()

    @Slot()
    def on_connect_thread_finished(self):
        self.connect_thread = None
        self.connect_worker = None

    @Slot(str)
    def on_connect_finished(self, message):
        self.btn_connect.setEnabled(True)
        self.btn_connect.setText(" CONNECT")
        self.password_input.clear()
        show_custom_message(self.root_window, "Connection Success", message, "success", self.palette)
        
        QTimer.singleShot(1000, self.go_back)

    @Slot(str, str)
    def on_connect_error(self, title, error_msg):
        self.btn_connect.setEnabled(True)
        self.btn_connect.setText(" CONNECT")
        show_custom_message(self.root_window, title, error_msg, "error", self.palette)


def create_network_tab(tab_control, palette, root_window):
    """Factory function to create the Network tab."""
    
    container = QWidget()
    page_layout = QVBoxLayout(container)
    page_layout.setContentsMargins(0, 0, 0, 0)
    scroll_area = QScrollArea()
    scroll_area.setWidgetResizable(True)
    
    network_tab_content = NetworkTab(palette, root_window)
    
    scroll_area.setWidget(network_tab_content)
    page_layout.addWidget(scroll_area)
    
    return container