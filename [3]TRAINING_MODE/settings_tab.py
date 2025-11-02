# settings_tab.py

import sys
import os
import qtawesome as qta
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QComboBox, QScrollArea
)
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QColor

from custom_dialog import show_custom_message

REPORT_FILE = "poultri_scan_report.csv"
DATABASE_LOG_FILE = "raw_database_log.csv" # <-- 1. ADDED DATABASE FILE


def _create_card(parent, title, palette, icon_name=None):
    """Helper to create a themed card."""
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
        icon_label.setPixmap(icon.pixmap(QSize(35, 35))) # Was 30, 30
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
    light.setPixmap(icon.pixmap(QSize(12, 12))) # Was 10, 10
    layout.addWidget(light)
    layout.addWidget(QLabel(text))
    layout.addStretch()
    return frame

# --- Control Functions (Unchanged) ---
# --- 2. REMOVED clear_all_app_settings ---

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


def create_settings_tab(tab_control, main_window, theme_switch_callback, palette, themes_dict, root_window, reload_reports_callback=None):

    settings_tab_content = QWidget()
    main_layout = QVBoxLayout(settings_tab_content)
    main_layout.setContentsMargins(10, 10, 10, 10)
    main_layout.setSpacing(15)
    main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
    
    btn_text_color = palette.get("BUTTON_TEXT", palette["BG"])
    danger_text_color = palette.get("DANGER_TEXT", palette["TEXT"])
    unselected_text_color = palette.get("UNSELECTED_TEXT", "#555760")

    # --- 1. THEME SETTINGS CARD ---
    theme_card, theme_frame = _create_card(
        settings_tab_content, " Theme & Appearance Settings", palette, icon_name="fa5s.palette"
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

    # --- 2. APPLICATION MANAGEMENT CARD ---
    management_card, management_frame = _create_card(
        settings_tab_content, " Application & Device Management", palette, icon_name="fa5s.tools"
    )
    main_layout.addWidget(management_card)
    mgmt_layout = QHBoxLayout(management_frame)
    
    # --- 3. REPLACED "CLEAR SETTINGS" WITH "TRAINING MODE" ---
    btn_training_mode = QPushButton(" TRAINING MODE")
    btn_training_mode.setObjectName("secondary")
    btn_training_mode.setIcon(qta.icon('fa5s.clipboard-list', color=unselected_text_color))
    # Switch to tab index 4 (Dashboard=0, Reports=1, Settings=2, About=3, Training=4)
    btn_training_mode.clicked.connect(lambda: root_window.switch_page(4))
    mgmt_layout.addWidget(btn_training_mode)
    
    btn_restart_device = QPushButton(" RESTART DEVICE")
    btn_restart_device.setIcon(qta.icon('fa5s.redo', color=btn_text_color))
    btn_restart_device.clicked.connect(lambda: restart_device_mock(settings_tab_content, palette))
    mgmt_layout.addWidget(btn_restart_device)
    btn_erase_data = QPushButton(" ERASE TEST DATA")
    btn_erase_data.setObjectName("danger")
    btn_erase_data.setIcon(qta.icon('fa5s.trash', color=danger_text_color))
    # --- 4. UPDATED erase function to also reload reports ---
    btn_erase_data.clicked.connect(lambda: erase_all_report_data(settings_tab_content, palette, reload_reports_callback))
    mgmt_layout.addWidget(btn_erase_data)
    btn_exit = QPushButton(" EXIT APPLICATION")
    btn_exit.setObjectName("danger")
    btn_exit.setIcon(qta.icon('fa5s.times', color=danger_text_color))
    btn_exit.clicked.connect(lambda: exit_application(root_window))
    mgmt_layout.addWidget(btn_exit)

    # --- 3. SYSTEM INFO CARD ---
    info_card, info_frame = _create_card(
        settings_tab_content, " System Information", palette, icon_name="fa5s.info-circle"
    )
    main_layout.addWidget(info_card)
    info_layout = QHBoxLayout(info_frame)
    col1_frame = QWidget()
    col1_layout = QVBoxLayout(col1_frame)
    col1_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
    info_layout.addWidget(col1_frame, 1)
    
    l1 = QLabel(f"PoultriScan Version: 1.0.0")
    l1.setStyleSheet(f"color: {palette['ACCENT']}; font: bold 18pt 'Bahnschrift'; background-color: {palette['SECONDARY_BG']};") # Was 14pt
    col1_layout.addWidget(l1)
    
    time_label = QLabel("Current System Time: ...")
    time_label.setObjectName("dataLabel")
    col1_layout.addWidget(time_label)
    timer = QTimer(settings_tab_content)
    timer.timeout.connect(lambda tl=time_label: tl.setText(f"Current System Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"))
    timer.start(1000) 
    col1_layout.addStretch()
    l2 = QLabel("Review the 'About' tab for full details.")
    l2.setObjectName("dataLabel")
    col1_layout.addWidget(l2)
    
    col2_frame = QWidget()
    col2_layout = QVBoxLayout(col2_frame)
    col2_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
    info_layout.addWidget(col2_frame, 1)
    
    l3 = QLabel("System Status")
    l3.setStyleSheet(f"color: {palette['TEXT']}; font: bold 18pt 'Bahnschrift'; background-color: {palette['SECONDARY_BG']};") # Was 14pt
    col2_layout.addWidget(l3)
    col2_layout.addWidget(_create_status_indicator(col2_frame, "Sensor Hub", palette["SUCCESS"], palette))
    col2_layout.addWidget(_create_status_indicator(col2_frame, "Spectrometer", palette["SUCCESS"], palette))
    col2_layout.addWidget(_create_status_indicator(col2_frame, "eNose Array", palette["SUCCESS"], palette))
    col2_layout.addWidget(_create_status_indicator(col2_frame, "Database Link", palette["ACCENT"], palette)) 
    col2_layout.addWidget(_create_status_indicator(col2_frame, "Network", palette["DANGER"], palette)) 
    col2_layout.addStretch()
    main_layout.addStretch() 

    # --- Create the scroll area container ---
    container = QWidget()
    page_layout = QVBoxLayout(container)
    page_layout.setContentsMargins(0, 0, 0, 0)
    scroll_area = QScrollArea()
    scroll_area.setWidgetResizable(True)
    scroll_area.setWidget(settings_tab_content)
    page_layout.addWidget(scroll_area)
    
    return container