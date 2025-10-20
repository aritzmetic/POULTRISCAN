# app.py

import tkinter as tk
from tkinter import ttk
import os
import csv
import time
from datetime import datetime
from dashboard_tab import create_dashboard_tab
from reports_tab import create_reports_tab
from settings_tab import create_settings_tab 
from about_tab import create_about_tab 
from custom_dialog import show_custom_message 

# --- Configuration Data ---
sample_type_prefix = {
    "Chicken Breast": "BR",
    "Chicken Thigh": "TH",
    "Chicken Wing": "WG",
}


# --- Theme Palettes ---
THEMES = {
    "Dark Mode": {
        "BG": "#1A1A2E",
        "SECONDARY_BG": "#2E3A53",
        "PRIMARY": "#00BCD4",
        "ACCENT": "#FF4081",
        "TEXT": "#E0E0E0",
        "UNSELECTED_TEXT": "#8899AA",
        "SUCCESS": "#00E676",
        "DANGER": "#FF1744",
        "BORDER": "#3A475F",
    },
    "Light Mode": {
        "BG": "#F0F2F5",
        "SECONDARY_BG": "#FFFFFF",
        "PRIMARY": "#1E88E5",
        "ACCENT": "#FF9800",
        "TEXT": "#212121",
        "UNSELECTED_TEXT": "#607D8B",
        "SUCCESS": "#4CAF50",
        "DANGER": "#F44336",
        "BORDER": "#CFD8DC",
    }
}

CURRENT_THEME = None 
GLOBAL_PALETTE = {} 

def setup_style(root, theme_name):
    """Configures the entire application style based on the chosen theme."""
    
    global GLOBAL_PALETTE
    palette = THEMES[theme_name]
    GLOBAL_PALETTE = palette 
    
    root.configure(bg=palette["BG"])
    
    style = ttk.Style()
    style.theme_use("clam")
    
    # --- General Frame and Label Configuration ---
    style.configure("TFrame", background=palette["BG"])
    style.configure("TLabel", background=palette["BG"], foreground=palette["TEXT"], font=("Segoe UI", 10))
    style.configure("Subtitle.TLabel", font=("Segoe UI", 12, "bold"), foreground=palette["PRIMARY"], background=palette["BG"])
    style.configure("Header.TLabel", font=("Segoe UI", 16, "bold"), foreground=palette["PRIMARY"], background=palette["BG"])
    
    # --- Card/Panel Style ---
    style.configure("Modern.TFrame", 
                    background=palette["SECONDARY_BG"], 
                    relief="flat", 
                    borderwidth=0)
    
    # --- Header Frame Configuration ---
    header_bg_color = palette["SECONDARY_BG"] 
    if root.winfo_children():
        header = root.winfo_children()[0]
        header.config(bg=header_bg_color)
        for widget in header.winfo_children():
            widget.config(bg=header_bg_color, fg=palette["PRIMARY"] if "POULTRISCAN" in widget.cget("text") else palette["TEXT"])

    # --- Notebook (Tab) Configuration ---
    style.configure("TNotebook", background=palette["BG"], borderwidth=0)
    style.configure(
        "TNotebook.Tab", 
        font=("Segoe UI", 11, "bold"), 
        padding=[25, 12], 
        background=palette["BG"],
        foreground=palette["UNSELECTED_TEXT"],
        relief="flat",
        borderwidth=0,
    )
    style.map(
        "TNotebook.Tab", 
        background=[("selected", palette["BG"])], 
        foreground=[("selected", palette["PRIMARY"])],
        expand=[("selected", [0, 0, 0, 4])] 
    )
    
    # --- Button Configuration ---
    active_color_map = {
        "Dark Mode": "#0097a7",  
        "Light Mode": "#1565c0"  
    }
    style.configure(
        "TButton", 
        font=("Segoe UI", 10, "bold"), 
        padding=[15, 10], 
        background=palette["PRIMARY"], 
        foreground=palette["BG"], 
        relief="flat",
        borderwidth=0,
        focusthickness=0,
    )
    style.map("TButton", 
              background=[("active", active_color_map[theme_name])],
              foreground=[("active", palette["BG"])]
             )
    
    # NEW: Dangerous Button Style (for Exit)
    danger_active_color_map = {
        "Dark Mode": "#C41038",  
        "Light Mode": "#D32F2F"  
    }
    style.configure(
        "Danger.TButton", 
        font=("Segoe UI", 10, "bold"), 
        padding=[15, 10], 
        background=palette["DANGER"], 
        foreground=palette["BG"], 
        relief="flat",
        borderwidth=0,
        focusthickness=0,
    )
    style.map("Danger.TButton", 
              background=[("active", danger_active_color_map[theme_name])],
              foreground=[("active", palette["BG"])]
             )


    # TCombobox Configuration 
    style.configure("TEntry", fieldbackground=palette["SECONDARY_BG"], foreground=palette["TEXT"], borderwidth=1, relief="flat", bordercolor=palette["BORDER"], padding=5)
    style.configure(
        "TCombobox", 
        fieldbackground=palette["SECONDARY_BG"], 
        foreground=palette["TEXT"], 
        selectforeground=palette["TEXT"],       
        selectbackground=palette["ACCENT"],     
        insertcolor=palette["PRIMARY"],         
        borderwidth=1, 
        relief="flat", 
        bordercolor=palette["BORDER"], 
        padding=5
    )
    style.map(
        "TCombobox", 
        fieldbackground=[('readonly', palette["SECONDARY_BG"])],
        foreground=[('readonly', palette["TEXT"])] 
    ) 

    # Tweak Treeview base style
    style.configure("Treeview", 
                    background=palette["SECONDARY_BG"], 
                    foreground=palette["TEXT"], 
                    fieldbackground=palette["SECONDARY_BG"],
                    rowheight=25)
    style.configure("Treeview.Heading", 
                    background=palette["BORDER"], 
                    foreground=palette["TEXT"], 
                    font=("Segoe UI", 10, "bold"))
    style.map(
        "Treeview",
        foreground=[('selected', palette["BG"])], 
        background=[('selected', palette["PRIMARY"])]
    )
    


def switch_theme(root, notebook):
    """Handles the full theme switching process and rebuilds tabs."""
    new_theme = CURRENT_THEME.get()
    
    setup_style(root, new_theme)
    
    # Temporarily remove all tabs
    for tab in notebook.tabs():
        notebook.forget(tab)

    # Recreate tabs with new style/palette
    create_dashboard_tab(notebook, GLOBAL_PALETTE, sample_type_prefix)
    create_reports_tab(notebook, GLOBAL_PALETTE, root) # FIX: Pass root
    # PASS root here
    create_settings_tab(notebook, CURRENT_THEME, lambda: switch_theme(root, notebook), GLOBAL_PALETTE, THEMES, root) 
    create_about_tab(notebook, GLOBAL_PALETTE)


def main():
    root = tk.Tk()
    
    global CURRENT_THEME
    CURRENT_THEME = tk.StringVar(root, value="Dark Mode") 
    
    root.title("PoultriScan | Chicken Quality Analyzer")
    
    # --- FULLSCREEN IMPLEMENTATION ---
    root.attributes('-fullscreen', True) 
    
    def exit_fullscreen(event):
        root.attributes('-fullscreen', False)
        try:
             root.state("zoomed")
        except tk.TclError:
             pass

    root.bind('<Escape>', exit_fullscreen)
    root.geometry("1400x800")
    # ---------------------------------

    setup_style(root, CURRENT_THEME.get())

    # --- Top Header Bar ---
    header = tk.Frame(root, height=70) 
    header.pack(fill="x")

    tk.Label(
        header, 
        text="🧬 POULTRISCAN", 
        font=("Segoe UI", 24, "bold"), 
    ).pack(side="left", padx=30, pady=10)
    
    tk.Label(
        header, 
        text="A Non-Invasive Quality Assessment System for Broiler Chicken (Gallus gallus domesticus) Meat", 
        font=("Segoe UI", 12), 
    ).pack(side="left", pady=10)

    # --- Main Content Area (Notebook) ---
    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True, padx=20, pady=20)

    # --- Initial Tab Creation ---
    create_dashboard_tab(notebook, GLOBAL_PALETTE, sample_type_prefix)
    create_reports_tab(notebook, GLOBAL_PALETTE, root) # FIX: Pass root
    # PASS root here
    create_settings_tab(notebook, CURRENT_THEME, lambda: switch_theme(root, notebook), GLOBAL_PALETTE, THEMES, root)
    create_about_tab(notebook, GLOBAL_PALETTE)

    root.mainloop()

if __name__ == "__main__":
    main()