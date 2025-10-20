# reports_tab.py

import tkinter as tk
from tkinter import ttk
import os
import csv
from custom_dialog import show_custom_message 
from tkinter import filedialog # Needed for export function

# Define the file path for the report log (Must match app.py/dashboard_tab.py)
report_file = "poultri_scan_report.csv"

# --- Placeholder/Mock Functions for Report Actions ---
# NOTE: In the final application, these functions are defined in settings_tab.py.
# They are mocked here to ensure the buttons in the reports_tab are functional
# and have correct command assignments for the UI demonstration.

def mock_export_report_data(parent_root, palette):
    """Mocks the export function to show a success message."""
    if not os.path.exists(report_file):
        show_custom_message(parent_root, "Export Failed", "No report file found to export.", "warning", palette)
        return
        
    export_path = filedialog.asksaveasfilename(
        defaultextension=".csv",
        filetypes=[("CSV files", "*.csv")],
        initialfile="PoultriScan_Export.csv",
        title="Export PoultriScan Report"
    )
    if export_path:
        show_custom_message(parent_root, "Export Successful", f"Report data successfully exported to:\n{export_path}", "success", palette)

def mock_erase_report_data(parent_root, palette, reload_callback):
    """Mocks the erase function to show confirmation and then trigger reload."""
    is_confirmed = show_custom_message(
        parent_root, 
        "Confirm Deletion", 
        "Are you sure you want to permanently erase ALL PoultriScan test data?", 
        "confirm", 
        palette
    )
    
    if is_confirmed:
        try:
            if os.path.exists(report_file):
                os.remove(report_file)
            show_custom_message(parent_root, "Deletion Successful", "All test data has been erased.", "success", palette)
            reload_callback() # Reload data after deletion
        except Exception as e:
            show_custom_message(parent_root, "Deletion Error", f"Failed to erase file: {e}", "error", palette)
# ---------------------------------------------------


def load_report_data(tree, palette, parent):
    """Loads data from the CSV file into the Treeview."""
    # Define colors
    SUCCESS_COLOR = palette["SUCCESS"]
    DANGER_COLOR = palette["DANGER"]
    UNSELECTED_TEXT = palette["UNSELECTED_TEXT"]
    
    for item in tree.get_children():
        tree.delete(item)

    if not os.path.exists(report_file):
        tree.insert("", tk.END, values=("N/A", "No Data Found. Run Analysis.", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A"), tags=('nodata',))
        # Ensure tags are configured even if no data exists
        tree.tag_configure("nodata", foreground=UNSELECTED_TEXT, font=("Segoe UI", 10, "italic"))
        return

    try:
        with open(report_file, "r", newline="") as f:
            reader = csv.reader(f)
            next(reader) # Skip header row
            
            # --- Treeview Tag Configuration (needs to be inside load for color context) ---
            tree.tag_configure("high", foreground=SUCCESS_COLOR)
            tree.tag_configure("low", foreground=DANGER_COLOR)
            tree.tag_configure("normal", foreground=palette["PRIMARY"]) # Use primary for normal/medium
            tree.tag_configure("nodata", foreground=UNSELECTED_TEXT, font=("Segoe UI", 10, "italic"))
            
            for row in reader:
                if len(row) > 1:
                    row_data = row[:]
                    # Pad with 'N/A' if row is incomplete (12 columns expected)
                    if len(row_data) < 12:
                         row_data += ['N/A'] * (12 - len(row_data))
                         
                    quality = str(row_data[-1]).upper()
                    
                    # Map quality string to tag
                    if quality in ['FRESH', 'SLIGHTLY FRESH']: 
                        tag = 'high'
                    elif quality == 'NORMAL':
                        tag = 'normal'
                    else: # SPOILED or SLIGHTLY SPOILED, or N/A
                        tag = 'low'
                        
                    tree.insert("", tk.END, values=row_data, tags=(tag,))
                

    except Exception as e:
        error_msg = f"Error reading report file: {e}"
        show_custom_message(parent, "Report Error", error_msg, "error", palette)
        tree.insert("", tk.END, values=("N/A", error_msg, "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A"), tags=('nodata',))


def create_reports_tab(tab_control, palette, root_window):
    """Creates the Reports tab with a modern, data-centric design."""
    
    # --- Color/Palette Definitions ---
    PRIMARY_COLOR = palette["PRIMARY"]
    SECONDARY_BG = palette["SECONDARY_BG"]
    BORDER_COLOR = palette["BORDER"]
    
    # 1. Initialize Main Tab
    reports_tab = ttk.Frame(tab_control, style="TFrame")
    tab_control.add(reports_tab, text=" Reports")
    
    reports_tab.grid_columnconfigure(0, weight=1)
    reports_tab.grid_rowconfigure(1, weight=1) 
    
    # --- Helper Function for Creating Themed Cards ---
    def _create_card(parent, title, style="Modern.TFrame"):
        """Creates a modern, themed card frame with a title label."""
        card_frame = ttk.Frame(parent, style=style, padding="15 15 15 15")
        ttk.Label(card_frame, text=title, style="Subtitle.TLabel", foreground=PRIMARY_COLOR, background=SECONDARY_BG).pack(padx=5, pady=(0, 10), anchor="w")
        content_frame = ttk.Frame(card_frame, style="TFrame")
        content_frame.pack(fill="both", expand=True)
        return card_frame, content_frame

    # --- 2. REPORT CONTROL CARD (Action Area) ---
    control_card, control_frame = _create_card(reports_tab, "Report Control & Actions")
    control_card.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
    
    control_frame.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)

    # 1. Reload Button
    btn_reload = ttk.Button(control_frame, text="🔄 RELOAD Data", style="Primary.TButton")
    btn_reload.grid(row=0, column=0, padx=10, sticky="w")
    
    # 2. Export Button
    btn_export = ttk.Button(control_frame, text="💾 EXPORT CSV", style="Secondary.TButton")
    btn_export.grid(row=0, column=3, padx=10, sticky="e")
    
    # 3. Erase Button
    btn_erase = ttk.Button(control_frame, text="🗑️ ERASE ALL Data", style="Danger.TButton")
    btn_erase.grid(row=0, column=4, padx=(10, 0), sticky="e")

    # --- 3. REPORT DATA CARD (Treeview Area) ---
    data_card, data_frame = _create_card(reports_tab, "PoultriScan Test History")
    data_card.grid(row=1, column=0, padx=20, pady=(10, 20), sticky="nsew")
    
    # Configure grid weights for Treeview
    data_frame.grid_columnconfigure(0, weight=1)
    data_frame.grid_rowconfigure(0, weight=1)
    
    # --- Treeview and Scrollbars Setup ---
    columns = ("Timestamp", "Sample ID", "Type", "Temperature", "Humidity", "WHC Index", "Fatty Acid Profile", "MQ-137 (NH3)", "MQ-136 (H2S)", "MQ-4 (CH4)", "MQ-7 (CO)", "Quality")
    
    tree = ttk.Treeview(data_frame, columns=columns, show="headings", style="Data.Treeview")
    tree.grid(row=0, column=0, sticky="nsew")
    
    # Scrollbars
    vsb = ttk.Scrollbar(data_frame, orient="vertical", command=tree.yview)
    vsb.grid(row=0, column=1, sticky="ns")
    tree.configure(yscrollcommand=vsb.set)
    
    hsb = ttk.Scrollbar(data_frame, orient="horizontal", command=tree.xview)
    hsb.grid(row=1, column=0, sticky="ew")
    tree.configure(xscrollcommand=hsb.set)
    
    # Column definitions
    numerical_cols = ["Temperature", "Humidity", "WHC Index", "Fatty Acid Profile", "MQ-137 (NH3)", "MQ-136 (H2S)", "MQ-4 (CH4)", "MQ-7 (CO)"]
    
    for col in columns:
        tree.heading(col, text=col, anchor=tk.CENTER if col in ["Sample ID", "Quality"] else tk.W)
        
        if col in numerical_cols:
             tree.column(col, width=110, anchor=tk.E) 
        elif col in ["Sample ID", "Quality"]:
             tree.column(col, width=100, anchor=tk.CENTER)
        elif col == "Timestamp":
             tree.column(col, width=160, anchor=tk.W)
        elif col == "Type":
             tree.column(col, width=110, anchor=tk.W)
        else:
             tree.column(col, width=80, anchor=tk.W)

    
    # --- 4. Function Commands ---
    
    # Define the reload command using a lambda for argument passing
    reload_command = lambda: load_report_data(tree, palette, reports_tab)
    
    btn_reload.config(command=reload_command)
    btn_export.config(command=lambda: mock_export_report_data(root_window, palette))
    btn_erase.config(command=lambda: mock_erase_report_data(root_window, palette, reload_command))
    
    # Load initial data when the tab is created
    reload_command()
    
    return reports_tab