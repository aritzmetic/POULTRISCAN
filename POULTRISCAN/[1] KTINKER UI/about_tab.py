# about_tab.py

import tkinter as tk
from tkinter import ttk

def _create_card(parent, title, palette, style="Modern.TFrame"):
    """Creates a modern, themed card frame with a title label."""
    card_frame = ttk.Frame(parent, style=style, padding="15 15 15 15")
    ttk.Label(card_frame, text=title, style="Subtitle.TLabel", foreground=palette["PRIMARY"], background=palette["SECONDARY_BG"]).pack(padx=5, pady=(0, 10), anchor="w")
    content_frame = ttk.Frame(card_frame, style="TFrame")
    content_frame.pack(fill="both", expand=True)
    return card_frame, content_frame


def create_about_tab(tab_control, palette):
    """Creates the About tab with detailed, card-based information."""
    
    about_tab = ttk.Frame(tab_control, style="TFrame")
    tab_control.add(about_tab, text=" About")

    # --- Color/Palette Definitions ---
    PRIMARY_COLOR = palette["PRIMARY"]
    ACCENT_COLOR = palette["ACCENT"]
    TEXT_COLOR = palette["TEXT"]
    SECONDARY_BG = palette["SECONDARY_BG"]
    
    about_tab.grid_columnconfigure(0, weight=1)
    about_tab.grid_rowconfigure(4, weight=1) # Empty row to push content up
    
    # --- 1. PROJECT INFORMATION CARD ---
    info_card, info_frame = _create_card(about_tab, "🔬 PoultriScan: Project Overview", palette)
    info_card.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")

    ttk.Label(info_frame, 
              text="PoultriScan is a **non-invasive, multi-sensor platform** designed for rapid quality assessment of broiler chicken meat. It utilizes sensor fusion technology combining environmental, spectroscopic, and volatile organic compound (VOC) data for an objective quality score.", 
              wraplength=800, 
              justify=tk.LEFT,
              foreground=TEXT_COLOR, 
              background=SECONDARY_BG).pack(padx=10, pady=5, anchor="w")
    
    ttk.Label(info_frame, 
              text=f"Current Version: **1.0.0 (Alpha)**", 
              foreground=PRIMARY_COLOR, 
              background=SECONDARY_BG, 
              font=("Segoe UI", 11, "bold")).pack(padx=10, pady=5, anchor="w")
    
    ttk.Label(info_frame, 
              text=f"Target Release: Q4 2025 (Initial Production)", 
              foreground=ACCENT_COLOR, 
              background=SECONDARY_BG).pack(padx=10, pady=5, anchor="w")


    # --- 2. DEVELOPMENT TEAM CARD ---
    team_card, team_frame = _create_card(about_tab, "👥 Development Team", palette)
    team_card.grid(row=1, column=0, padx=20, pady=10, sticky="ew")

    team_members = [
        "**Project Lead:** Engr. A. Dela Cruz (Sensor Fusion & Algorithm Design)",
        "**Software Architect:** J. M. Sotto (Tkinter UI/UX & Backend Integration)",
        "**Hardware Specialist:** M. R. Ramos (Prototype Fabrication & Testing)",
        "**Data Analyst:** L. V. Santos (Model Training & Validation)",
    ]
    
    ttk.Label(team_frame, text="This project was developed as a Capstone/Thesis requirement.", foreground=TEXT_COLOR, background=SECONDARY_BG).pack(padx=10, pady=5, anchor="w")

    for member in team_members:
        ttk.Label(team_frame, text=f"• {member}", foreground=TEXT_COLOR, background=SECONDARY_BG).pack(padx=20, pady=2, anchor="w")


    # --- 3. TECHNOLOGY STACK CARD ---
    tech_card, tech_frame = _create_card(about_tab, "💻 Technology Stack", palette)
    tech_card.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
    
    tech_stack = [
        "**Frontend/UI:** Python Tkinter (Themed & Modern Styling)",
        "**Backend/Logic:** Python 3.x (Modularized Structure)",
        "**Sensor Communication (Mocked):** Pyserial & I2C/SPI Protocols",
        "**Data Storage:** CSV Flatfile (Local Archival)",
        "**Core Sensors:** AS7265X (Spectrometer), AHT20 (Environment), MQ-Series (eNose VOCs)",
    ]
    
    for item in tech_stack:
        ttk.Label(tech_frame, text=f"→ {item}", foreground=TEXT_COLOR, background=SECONDARY_BG).pack(padx=10, pady=2, anchor="w")


    # --- 4. LICENSING & DISCLAIMER CARD ---
    license_card, license_frame = _create_card(about_tab, "📜 Licensing & Usage Disclaimer", palette)
    license_card.grid(row=3, column=0, padx=20, pady=(10, 20), sticky="ew")

    ttk.Label(license_frame, 
              text="Licensing: PoultriScan is released under the **MIT License**.", 
              foreground=PRIMARY_COLOR, 
              background=SECONDARY_BG, 
              font=("Segoe UI", 10, "bold")).pack(padx=10, pady=5, anchor="w")
    
    ttk.Label(license_frame, 
              text="**DISCLAIMER:** This application is for non-commercial, research, and educational purposes only. It is not intended for use as a primary safety or quality control tool in commercial food production.", 
              wraplength=800,
              justify=tk.LEFT,
              foreground=palette["DANGER"], 
              background=SECONDARY_BG,
              font=("Segoe UI", 10, "bold")).pack(padx=10, pady=5, anchor="w")
              
    ttk.Label(license_frame, 
              text="© 2025 PoultriScan Development Team. All rights reserved.", 
              foreground=ACCENT_COLOR, 
              background=SECONDARY_BG).pack(padx=10, pady=5, anchor="w")

    return about_tab