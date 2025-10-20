# settings_tab.py

import tkinter as tk
from tkinter import ttk
import sys # For application exit
from custom_dialog import show_custom_message
from datetime import datetime 

# Define the file path for the report log (Used for erase mock)
REPORT_FILE = "poultri_scan_report.csv"

def _create_card(parent, title, palette, style="Modern.TFrame"):
    """Creates a modern, themed card frame with a title label."""
    card_frame = ttk.Frame(parent, style=style, padding="15 15 15 15")
    ttk.Label(card_frame, text=title, style="Subtitle.TLabel", foreground=palette["PRIMARY"], background=palette["SECONDARY_BG"]).pack(padx=5, pady=(0, 10), anchor="w")
    content_frame = ttk.Frame(card_frame, style="TFrame")
    content_frame.pack(fill="both", expand=True)
    return card_frame, content_frame

def clear_all_app_settings(parent, palette):
    """Mocks clearing application settings (excluding report data)."""
    is_confirmed = show_custom_message(
        parent,
        "Confirm Settings Reset",
        "Are you sure you want to reset all application settings to default?\n(This does NOT erase test data).",
        "confirm",
        palette
    )
    if is_confirmed:
        # In a real app, this would reset config files, preferences, etc.
        show_custom_message(parent, "Settings Cleared", "All application settings have been reset to default.", "success", palette)

def restart_device_mock(parent, palette):
    """Mocks the device restart functionality."""
    is_confirmed = show_custom_message(
        parent,
        "Confirm Device Restart",
        "This will close the application and simulate a hardware reboot. Proceed?",
        "confirm",
        palette
    )
    if is_confirmed:
        show_custom_message(parent, "Restarting...", "Application closed. Device is now restarting...", "info", palette)
        sys.exit()

def exit_application(root):
    """Safely closes the main application window."""
    root.destroy()
    sys.exit()


def create_settings_tab(tab_control, current_theme_var, theme_switch_callback, palette, themes_dict, root_window):
    """Creates the Settings tab with enhanced layout and interactivity."""
    
    settings_tab = ttk.Frame(tab_control, style="TFrame")
    tab_control.add(settings_tab, text=" Settings")

    # --- Color/Palette Definitions ---
    ACCENT_COLOR = palette["ACCENT"]
    TEXT_COLOR = palette["TEXT"]
    SECONDARY_BG = palette["SECONDARY_BG"]
    
    settings_tab.grid_columnconfigure(0, weight=1)
    settings_tab.grid_rowconfigure(2, weight=1) 
    
    # --- 1. THEME SETTINGS CARD ---
    theme_card, theme_frame = _create_card(settings_tab, "🎨 Theme & Appearance Settings", palette)
    theme_card.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
    
    theme_frame.grid_columnconfigure((0, 1), weight=1)
    
    ttk.Label(theme_frame, text="Current Theme:", style="Data.TLabel").grid(row=0, column=0, padx=10, pady=10, sticky="w")
    
    theme_combobox = ttk.Combobox(
        theme_frame, 
        textvariable=current_theme_var, 
        values=list(themes_dict.keys()), 
        state="readonly", 
        width=20
    )
    theme_combobox.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
    
    # Bind the theme switch to the selection change
    theme_combobox.bind("<<ComboboxSelected>>", lambda event: theme_switch_callback())
    
    
    # --- 2. APPLICATION MANAGEMENT CARD ---
    management_card, management_frame = _create_card(settings_tab, "🛠️ Application & Device Management", palette)
    management_card.grid(row=1, column=0, padx=20, pady=10, sticky="ew")

    # Use a sub-frame for the buttons to control spacing and alignment
    button_controls_frame = ttk.Frame(management_frame, style="TFrame")
    button_controls_frame.pack(fill="x", padx=10, pady=10)
    button_controls_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

    # Settings Reset Button
    btn_reset_settings = ttk.Button(
        button_controls_frame, 
        text="⚙️ CLEAR ALL SETTINGS", 
        style="Secondary.TButton",
        command=lambda: clear_all_app_settings(settings_tab, palette)
    )
    btn_reset_settings.grid(row=0, column=0, padx=5, sticky="ew")
    
    # NEW: Restart Device Button
    btn_restart_device = ttk.Button(
        button_controls_frame, 
        text="🔁 RESTART DEVICE", 
        style="Primary.TButton",
        command=lambda: restart_device_mock(settings_tab, palette)
    )
    btn_restart_device.grid(row=0, column=1, padx=5, sticky="ew")
    
    # Application Exit Button
    btn_exit = ttk.Button(
        button_controls_frame, 
        text="❌ EXIT APPLICATION", 
        style="Danger.TButton",
        command=lambda: exit_application(root_window)
    )
    btn_exit.grid(row=0, column=3, padx=5, sticky="ew")
    
    
    # --- 3. SYSTEM INFO CARD ---
    info_card, info_frame = _create_card(settings_tab, "ⓘ System Information", palette)
    info_card.grid(row=2, column=0, padx=20, pady=(10, 20), sticky="new")
    
    ttk.Label(info_frame, text=f"PoultriScan Version: 1.0.0", foreground=ACCENT_COLOR, background=SECONDARY_BG, font=("Segoe UI", 10, "bold")).pack(padx=10, pady=5, anchor="w")
    ttk.Label(info_frame, text=f"Last UI Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", foreground=TEXT_COLOR, background=SECONDARY_BG).pack(padx=10, pady=5, anchor="w")
    ttk.Label(info_frame, text="Review the 'About' tab for full details, team information, and licensing.", foreground=TEXT_COLOR, background=SECONDARY_BG).pack(padx=10, pady=5, anchor="w")
    
    return settings_tab