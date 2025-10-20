# custom_dialog.py

import tkinter as tk
from tkinter import ttk

def show_custom_message(parent, title, message, type, palette):
    """
    Displays a custom, modern, theme-compliant modal message box.

    Args:
        parent (tk.Tk or tk.Toplevel): The parent window.
        title (str): Title of the dialog.
        message (str): Message content.
        type (str): 'info', 'warning', 'success', 'error', or 'confirm'.
        palette (dict): The current application theme palette.
    """
    
    # --- Color mapping ---
    BG = palette["SECONDARY_BG"]
    TEXT = palette["TEXT"]
    PRIMARY = palette["PRIMARY"]
    
    color_map = {
        "info": palette["PRIMARY"],
        "warning": palette["ACCENT"],
        "success": palette["SUCCESS"],
        "error": palette["DANGER"],
        "confirm": palette["PRIMARY"]
    }
    
    # Select main color based on type
    main_color = color_map.get(type, PRIMARY)

    # --- Setup Toplevel Window ---
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.config(bg=BG, padx=20, pady=20)
    try:
        # Attempt to remove minimize/maximize buttons
        dialog.attributes('-toolwindow', True) 
    except tk.TclError:
        pass # Not supported on all systems
        
    dialog.resizable(False, False)
    
    # --- Positioning (Center the dialog over the parent window) ---
    parent.update_idletasks()
    parent_x = parent.winfo_x()
    parent_y = parent.winfo_y()
    parent_width = parent.winfo_width()
    parent_height = parent.winfo_height()
    
    dialog_width = 400
    dialog_height = 200 # Initial estimate
    
    x = parent_x + (parent_width // 2) - (dialog_width // 2)
    y = parent_y + (parent_height // 2) - (dialog_height // 2)
    dialog.geometry(f'{dialog_width}x{dialog_height}+{x}+{y}')
    
    # Make the dialog modal
    dialog.transient(parent)
    dialog.grab_set()

    # --- Result Variable for Confirm Dialogs ---
    result_var = tk.BooleanVar(dialog, value=False)
    
    # --- Content Frame ---
    content_frame = tk.Frame(dialog, bg=BG)
    content_frame.pack(fill="both", expand=True)

    # Icon Label (Large)
    icon = {
        "info": "ⓘ", "warning": "⚠️", "success": "✅", "error": "❌", "confirm": "❓"
    }.get(type, "💬")
    
    icon_label = tk.Label(content_frame, text=icon, font=("Segoe UI", 30), fg=main_color, bg=BG)
    icon_label.pack(pady=10)

    # Message Label
    message_label = tk.Label(content_frame, text=message, font=("Segoe UI", 10), fg=TEXT, bg=BG, justify=tk.CENTER, wraplength=350)
    message_label.pack(pady=(0, 20))

    # --- Button Frame ---
    button_frame = tk.Frame(dialog, bg=BG)
    button_frame.pack(fill="x")

    def close_dialog(res=False):
        """Closes the dialog and sets the result for 'confirm'."""
        result_var.set(res)
        dialog.grab_release()
        dialog.destroy()
        
    # --- Button Styling ---
    # Define a style for custom buttons using Toplevel/tk widgets
    tk_button_style = {
        'font': ("Segoe UI", 10, "bold"),
        'relief': 'flat',
        'bd': 0,
        'fg': BG, # Text color is BG color
        'padx': 15,
        'pady': 7,
        'cursor': 'hand2'
    }

    if type == "confirm":
        # Yes button (Primary Color)
        yes_btn = tk.Button(
            button_frame, 
            text="Yes", 
            command=lambda: close_dialog(True),
            bg=main_color,
            activebackground=main_color,
            **tk_button_style
        )
        yes_btn.pack(side="right", padx=(10, 0))

        # No button (Accent/Secondary) - MODIFIED to use UNSELECTED_TEXT
        no_btn = tk.Button(
            button_frame, 
            text="No", 
            command=lambda: close_dialog(False),
            # Use UNSELECTED_TEXT for better visibility as a secondary action
            bg=palette["UNSELECTED_TEXT"], 
            activebackground=palette["UNSELECTED_TEXT"],
            **tk_button_style
        )
        no_btn.pack(side="right")
        
    else:
        # OK button (Primary Color)
        ok_btn = tk.Button(
            button_frame, 
            text="OK", 
            command=close_dialog,
            bg=main_color,
            activebackground=main_color,
            **tk_button_style
        )
        ok_btn.pack(side="right")
        
    # Bind Return key to the OK/Yes button
    if type in ["info", "warning", "success", "error"]:
        dialog.bind('<Return>', lambda e: close_dialog())
    elif type == "confirm":
        dialog.bind('<Return>', lambda e: close_dialog(True))
        
    # Wait for the window to be closed (modal behavior)
    parent.wait_window(dialog)
    
    # Return result for confirm dialogs
    if type == "confirm":
        return result_var.get()
    else:
        return None