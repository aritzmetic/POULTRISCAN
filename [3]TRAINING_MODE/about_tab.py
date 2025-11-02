# about_tab.py

import qtawesome as qta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QScrollArea
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QFont 

def _create_card(parent, title, palette, icon_name=None):
    """Creates a modern, themed card frame with an icon and title."""
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


def create_about_tab(tab_control, palette):
    """Creates the About tab with detailed, card-based information."""

    about_tab_content = QWidget()
    main_layout = QVBoxLayout(about_tab_content)
    main_layout.setContentsMargins(10, 10, 10, 10)
    main_layout.setSpacing(15)
    main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
    
    detail_font = QFont("Bahnschrift", 18) # Was 14
    bold_font = QFont("Bahnschrift", 18)   # Was 14
    bold_font.setBold(True)

    # --- 1. PROJECT INFORMATION CARD ---
    info_card, info_frame = _create_card(
        about_tab_content, " PoultriScan: Project Overview", palette, icon_name="fa5s.microscope"
    )
    main_layout.addWidget(info_card)
    info_layout = QVBoxLayout(info_frame)
    info_layout.setSpacing(10) 
    l1 = QLabel(
        "PoultriScan is a non-invasive, multi-sensor platform designed for rapid quality "
        "assessment of broiler chicken meat. It utilizes sensor fusion technology combining "
        "environmental, spectroscopic, and volatile organic compound (VOC) data for an "
        "objective quality score."
    )
    l1.setWordWrap(True)
    l1.setObjectName("dataLabel")
    l1.setFont(detail_font)
    info_layout.addWidget(l1)
    
    l2 = QLabel(f"Current Version: 1.0.0 (Alpha)")
    l2.setStyleSheet(f"color: {palette['ACCENT']}; font: bold 18pt 'Bahnschrift'; background-color: {palette['SECONDARY_BG']};") # Was 14pt
    info_layout.addWidget(l2)
    
    l3 = QLabel(f"Target Release: Q4 2025 (Initial Production)")
    l3.setStyleSheet(f"color: {palette['ACCENT']}; font: 18pt 'Bahnschrift'; background-color: {palette['SECONDARY_BG']};") # Was 14pt
    info_layout.addWidget(l3)

    # --- 2. DEVELOPMENT TEAM CARD ---
    team_card, team_frame = _create_card(
        about_tab_content, " Development Team", palette, icon_name="fa5s.users"
    )
    main_layout.addWidget(team_card)
    team_layout = QVBoxLayout(team_frame)
    team_layout.setSpacing(15) 
    team_data = [
        {
            "role": "Project Lead: Ralph Lorenz Codilan",
            "tasks": [
                "Oversees overall project development and timeline execution",
                "Leads AI model training, calibration, and validation for poultry quality detection",
                "Performs data preprocessing, feature extraction, and dataset management",
                "Conducts analytical evaluations and performance benchmarking of trained models",
                "Ensures effective coordination among hardware, firmware, and software teams",
                "Prepares technical reports, documentation, and research integration"
            ]
        },
        {
            "role": "Firmware & Software Architect: Aritz Delera",
            "tasks": [
                "Designs and implements the firmware architecture for all sensors and actuators",
                "Develops sensor fusion algorithms for multi-sensor data interpretation",
                "Handles UI/UX design, system workflow, and backend integration",
                "Manages communication protocols (I2C, UART, SPI) and data handling pipelines",
                "Responsible for schematic design, power management, and embedded system optimization",
                "Oversees software testing, debugging, and deployment on Raspberry Pi"
            ]
        },
        {
            "role": "Hardware Specialist 1: Joshua Basilan",
            "tasks": [
                "Leads PCB fabrication, component assembly, and system wiring",
                "Integrates sensors and ensures proper calibration and interfacing with the controller",
                "Conducts prototype development, troubleshooting, and reliability testing",
                "Assists in thermal, mechanical, and electrical stability validation",
                "Documents hardware setup procedures and maintenance protocols"
            ]
        },
        {
            "role": "Hardware Specialist 2: Chean Bernard Vergel",
            "tasks": [
                "Focuses on prototype mechanical design and structural layout",
                "Assists in PCB design, assembly, and soldering processes",
                "Conducts sensor housing fabrication and environmental testing",
                "Performs performance validation and field testing of the final prototype",
                "Supports hardware optimization for durability and usability"
            ]
        }
    ]
    for member in team_data:
        role_label = QLabel(member["role"])
        role_label.setFont(bold_font)
        role_label.setStyleSheet(f"color: {palette['ACCENT']}; background-color: {palette['SECONDARY_BG']};")
        role_label.setWordWrap(True)
        team_layout.addWidget(role_label)
        task_layout = QVBoxLayout() 
        task_layout.setContentsMargins(20, 5, 0, 5) 
        task_layout.setSpacing(5)
        for task in member["tasks"]:
            task_label = QLabel(f"• {task}")
            task_label.setFont(detail_font)
            task_label.setObjectName("dataLabel")
            task_label.setWordWrap(True)
            task_layout.addWidget(task_label)
        team_layout.addLayout(task_layout)

    # --- 3. TECHNOLOGY STACK CARD ---
    tech_card, tech_frame = _create_card(
        about_tab_content, " Technology Stack", palette, icon_name="fa5s.laptop-code"
    )
    main_layout.addWidget(tech_card)
    tech_layout = QVBoxLayout(tech_frame)
    tech_layout.setSpacing(5) 
    tech_stack = [
        "Frontend/UI: Python Pyside6 (Qt6 Framework)",
        "Backend/Logic: Python 3.x (Modularized Structure)",
        "Sensor Communication (Mocked): Pyserial & I2C/SPI Protocols",
        "Data Storage: CSV Flatfile (Local Archival)",
        "Core Sensors: AS7265X (Spectrometer), AHT20 (Environment), MQ-Series (eNose VOCs)",
    ]
    for item in tech_stack:
        l = QLabel(f"<span style='color: {palette['ACCENT']};'>>_</span> {item}")
        l.setObjectName("dataLabel")
        l.setFont(detail_font)
        tech_layout.addWidget(l)

    # --- 4. LICENSING & DISCLAIMER CARD ---
    license_card, license_frame = _create_card(
        about_tab_content, " Licensing & Usage Disclaimer", palette, icon_name="fa5s.scroll"
    )
    main_layout.addWidget(license_card)
    license_layout = QVBoxLayout(license_frame)
    license_layout.setSpacing(10) 
    
    l5 = QLabel("Licensing: PoultriScan is released under the MIT License.")
    l5.setStyleSheet(f"color: {palette['ACCENT']}; font: bold 18pt 'Bahnschrift'; background-color: {palette['SECONDARY_BG']};") # Was 14pt
    license_layout.addWidget(l5)
    
    l6 = QLabel(
        "DISCLAIMER: This application is for non-commercial, research, and educational "
        "purposes only. It is not intended for use as a primary safety or quality "
        "control tool in commercial food production."
    )
    l6.setWordWrap(True)
    l6.setStyleSheet(f"color: {palette['DANGER']}; font: bold 18pt 'Bahnschrift'; background-color: {palette['SECONDARY_BG']};") # Was 14pt
    license_layout.addWidget(l6)
    
    l7 = QLabel("© 2025 PoultriScan Development Team. All rights reserved.")
    l7.setStyleSheet(f"color: {palette['UNSELECTED_TEXT']}; font: 18pt 'Bahnschrift'; background-color: {palette['SECONDARY_BG']};") # Was 14pt
    license_layout.addWidget(l7)

    main_layout.addStretch() 

    # --- Create the scroll area container ---
    container = QWidget()
    page_layout = QVBoxLayout(container)
    page_layout.setContentsMargins(0, 0, 0, 0)
    scroll_area = QScrollArea()
    scroll_area.setWidgetResizable(True)
    scroll_area.setWidget(about_tab_content)
    page_layout.addWidget(scroll_area)
    
    return container