# dashboard_tab.py

import tkinter as tk
from tkinter import ttk
import os
import csv
from datetime import datetime
from custom_dialog import show_custom_message 
import threading 
import random 
import time

# Define the file path for the report log
report_file = "poultri_scan_report.csv"
current_sample_id = None

# --- Sensor Fusion Import (Robust Mocking) ---
try:
    from Sensors import sensor_fusion 
    SPECTROMETER_PLACEHOLDER = sensor_fusion.SPECTROMETER_PLACEHOLDER
except ImportError as e:
    # Full mock implementation if sensor_fusion fails to import
    def mock_read_all_sensors():
        return {
            "Temperature": round(random.uniform(25.0, 30.0), 1),
            "Humidity": round(random.uniform(50.0, 70.0), 1),
            "MQ-137 (Ammonia)": round(random.uniform(1.0, 6.0), 2), 
            "MQ-136 (H2S)": round(random.uniform(0.5, 3.0), 2), 
            "MQ-4 (Methane)": round(random.uniform(2.0, 9.0), 2), 
            "MQ-7 (CO)": round(random.uniform(1.0, 5.0), 2),
            "WHC Index": round(random.uniform(0.80, 0.95), 3),
            "Fatty Acid Profile": round(random.uniform(0.40, 0.65), 3),
        }
    def mock_calculate_group_scores(raw_r): 
        s1 = random.randint(50, 95); s2 = random.randint(50, 95); s3 = random.randint(50, 95)
        final_s = int(round((s1 * 0.4) + (s2 * 0.3) + (s3 * 0.3)))
        return s1, s2, s3, final_s
        
    def mock_calculate_overall_quality(score):
        if score >= 90: cat = "FRESH"; tag = "high"
        elif score >= 80: cat = "SLIGHTLY FRESH"; tag = "high"
        elif score >= 60: cat = "NORMAL"; tag = "normal"
        elif score >= 40: cat = "SLIGHTLY SPOILED"; tag = "low"
        else: cat = "SPOILED"; tag = "low"
        return cat, tag, score
        
    sensor_fusion = type('MockFusion', (object,), {
        'read_all_sensors': mock_read_all_sensors,
        'calculate_group_scores': mock_calculate_group_scores,
        'calculate_overall_quality': mock_calculate_overall_quality,
    })()
    SPECTROMETER_PLACEHOLDER = "N/A - Mock"
    print(f"Failed to import sensor_fusion: {e}. Using full mock functionality.")
# -----------------------------


def create_dashboard_tab(tab_control, palette, sample_type_prefix):
    """Creates the main Dashboard tab with highly enhanced UI."""
    
    # 1. Initialize Main Tab
    dashboard_tab = ttk.Frame(tab_control, style="TFrame")
    tab_control.add(dashboard_tab, text=" Dashboard")

    # --- Color/Palette Definitions ---
    THEME_PALETTE = palette
    SUCCESS_COLOR = palette["SUCCESS"]
    DANGER_COLOR = palette["DANGER"]
    ACCENT_COLOR = palette["ACCENT"]
    PRIMARY_COLOR = palette["PRIMARY"]
    UNSELECTED_TEXT = palette["UNSELECTED_TEXT"]
    SECONDARY_BG = palette["SECONDARY_BG"]
    BORDER_COLOR = palette["BORDER"]
    TEXT_COLOR = palette["TEXT"]
    NORMAL_COLOR = palette["ACCENT"] 
    
    # Configure main grid weights for responsiveness
    dashboard_tab.grid_columnconfigure((0, 1), weight=1)
    dashboard_tab.grid_rowconfigure(1, weight=1) 
    
    # Dictionary to hold all raw data labels for easy update/animation
    raw_label_refs = {}
    
    # --- Helper Function for Creating Themed Cards ---
    def _create_card(parent, title, style="Modern.TFrame"):
        """Creates a modern, themed card frame with a title label."""
        card_frame = ttk.Frame(parent, style=style, padding="15 15 15 15")
        ttk.Label(card_frame, text=title, style="Subtitle.TLabel", foreground=PRIMARY_COLOR, background=SECONDARY_BG).pack(padx=5, pady=(0, 10), anchor="w")
        content_frame = ttk.Frame(card_frame, style="TFrame")
        content_frame.pack(fill="both", expand=True)
        return card_frame, content_frame

    # --- 2. WIDGET DEFINITIONS ---
    
    # --- A. CONTROL CARD (Row 0, Span 2) ---
    # Custom frame with border for the Active Monitoring pulse
    control_border_frame = tk.Frame(dashboard_tab, bg=BORDER_COLOR, highlightthickness=2, highlightbackground=BORDER_COLOR)
    control_border_frame.grid(row=0, column=0, columnspan=2, padx=20, pady=(20, 10), sticky="new")
    
    control_card, control_frame = _create_card(control_border_frame, "Test Control & Status")
    control_card.pack(fill="both", expand=True) # Use pack here as the parent is the bordered frame
    
    control_frame.grid_columnconfigure((0, 1, 2, 3, 4, 5, 6, 7), weight=1)

    # 1. Sample Type Selection
    ttk.Label(control_frame, text="Sample Type:", style="Data.TLabel").grid(row=0, column=0, padx=(0, 10), sticky="w")
    sample_type_combobox = ttk.Combobox(
        control_frame, 
        values=list(sample_type_prefix.keys()), 
        state="readonly", 
        width=18
    )
    sample_type_combobox.set("Chicken Breast") 
    sample_type_combobox.grid(row=0, column=1, padx=10, sticky="w")
    
    # 2. Sample ID Display
    ttk.Label(control_frame, text="Sample ID:", style="Data.TLabel").grid(row=0, column=2, padx=(30, 10), sticky="w")
    sample_id_label = ttk.Label(control_frame, text="PS-INIT-0000", style="Header.TLabel", foreground=ACCENT_COLOR)
    sample_id_label.grid(row=0, column=3, padx=(10, 0), sticky="w")
    
    # 3. Status Indicator Light
    status_canvas = tk.Canvas(control_frame, width=15, height=15, bg=SECONDARY_BG, highlightthickness=0)
    status_light = status_canvas.create_oval(3, 3, 13, 13, fill=UNSELECTED_TEXT)
    status_canvas.grid(row=0, column=4, padx=(0, 40), sticky="w")

    # 4. Control Buttons
    btn_run = ttk.Button(control_frame, text="▶️ RUN TEST", style="Primary.TButton")
    btn_run.grid(row=0, column=6, padx=10, sticky="e")
    
    btn_clear = ttk.Button(control_frame, text="🧹 CLEAR", style="Secondary.TButton")
    btn_clear.grid(row=0, column=7, padx=(10, 0), sticky="e")


    # --- B. MAIN CONTENT FRAME (Row 1, Span 2) ---
    main_content_frame = ttk.Frame(dashboard_tab, style="TFrame")
    main_content_frame.grid(row=1, column=0, columnspan=2, padx=20, pady=10, sticky="nsew")
    main_content_frame.grid_columnconfigure((0, 1), weight=1)
    main_content_frame.grid_rowconfigure(1, weight=1) 

    # --- B.1. SCORE AND CATEGORY FRAME (Row 0) ---
    score_category_frame = ttk.Frame(main_content_frame, style="TFrame")
    score_category_frame.grid(row=0, column=0, columnspan=2, pady=(0, 10), sticky="ew")
    score_category_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

    # 1. Overall Score Card (Larger, Gauge Style with Border Frame)
    score_border_frame = tk.Frame(score_category_frame, bg=SECONDARY_BG, highlightthickness=2, highlightbackground=UNSELECTED_TEXT)
    score_border_frame.grid(row=0, column=0, rowspan=2, padx=(0, 10), sticky="nsew")
    
    overall_card_g, overall_frame_g = _create_card(score_border_frame, "PoultriScan Quality Score", style="NoPadding.TFrame")
    overall_card_g.pack(fill="both", expand=True)
    
    # Inner Frame for Score to simulate a contrasting background/depth
    score_kpi_frame = tk.Frame(overall_frame_g, bg=BORDER_COLOR) # Use BORDER_COLOR for subtle dark background
    score_kpi_frame.pack(fill="x", padx=10, pady=(10, 5))
    
    score_display = ttk.Label(score_kpi_frame, text="--", foreground=UNSELECTED_TEXT, style="Header.TLabel", font=("Segoe UI", 48, "bold"), background=BORDER_COLOR)
    score_display.pack(pady=(5, 5), padx=10) 
    
    quality_label = ttk.Label(overall_frame_g, 
                              text="AWAITING SCAN", 
                              foreground=UNSELECTED_TEXT, 
                              style="Header.TLabel", 
                              font=("Segoe UI", 16, "bold"),
                              justify=tk.CENTER)
    quality_label.pack(pady=(0, 10), padx=10) 
    
    progress_bar = ttk.Progressbar(overall_frame_g, orient="horizontal", mode="determinate")
    progress_bar.pack(fill="x", padx=10, pady=(0, 5))

    # 2. Group Index Cards (With Individual Progress Bars)
    def create_index_card(parent, title, row, col, ref):
        card, content = _create_card(parent, title)
        card.grid(row=row, column=col, padx=5, sticky="nsew")
        
        ref['label'] = ttk.Label(content, text="--", style="Score.TLabel", font=("Segoe UI", 24, "bold"))
        ref['label'].pack(pady=(10, 5), padx=10)
        
        ref['bar'] = ttk.Progressbar(content, orient="horizontal", length=150, mode="determinate")
        ref['bar'].pack(fill="x", padx=10, pady=(5, 10))
        return card
        
    enose_ref = {}; whc_ref = {}; fac_ref = {}
    
    create_index_card(score_category_frame, "eNose VOC Index (0-100)", 0, 1, enose_ref)
    create_index_card(score_category_frame, "WHC Index (0-100)", 0, 2, whc_ref)
    create_index_card(score_category_frame, "FAC Index (0-100)", 0, 3, fac_ref)


    # --- C. RAW SENSOR DATA CONTAINER (Row 1, Span 2) ---
    raw_data_card, raw_data_container = _create_card(main_content_frame, "Raw Sensor Readings - Live Data Stream")
    raw_data_card.grid(row=1, column=0, columnspan=2, pady=(10, 20), sticky="nsew")
    
    raw_data_container.grid_columnconfigure((0, 1, 2), weight=1) 
    
    # --- C.1. Environmental Card (AHT20) ---
    env_card, env_frame = _create_card(raw_data_container, "🌡️ AHT20 (Environment)")
    env_card.grid(row=0, column=0, padx=(0, 10), sticky="nsew")
    
    temp_label = ttk.Label(env_frame, text="Temperature: -- °C", style="Data.TLabel", foreground=TEXT_COLOR)
    temp_label.pack(padx=10, pady=8, anchor="w")
    humidity_label = ttk.Label(env_frame, text="Humidity: -- % RH", style="Data.TLabel", foreground=TEXT_COLOR)
    humidity_label.pack(padx=10, pady=8, anchor="w")
    raw_label_refs["Temperature"] = temp_label
    raw_label_refs["Humidity"] = humidity_label

    # --- C.2. Spectrometer Card (WHC/FAC Raw) ---
    spec_card, spec_frame = _create_card(raw_data_container, "🌈 AS7265X (Spectrometry)")
    spec_card.grid(row=0, column=1, padx=10, sticky="nsew")
    
    whc_raw_label = ttk.Label(spec_frame, text="WHC Raw: N/A", style="Data.TLabel", foreground=TEXT_COLOR)
    whc_raw_label.pack(padx=10, pady=8, anchor="w")
    fac_raw_label = ttk.Label(spec_frame, text="FAC Raw: N/A", style="Data.TLabel", foreground=TEXT_COLOR)
    fac_raw_label.pack(padx=10, pady=8, anchor="w")
    raw_label_refs["WHC Index"] = whc_raw_label
    raw_label_refs["Fatty Acid Profile"] = fac_raw_label


    # --- C.3. eNose Card (Gas Sensors) ---
    enose_raw_card, enose_raw_frame = _create_card(raw_data_container, "💨 eNose (VOCs)")
    enose_raw_card.grid(row=0, column=2, padx=(10, 0), sticky="nsew")

    # Arrange eNose labels in two columns for better balance
    enose_raw_frame.grid_columnconfigure((0, 1), weight=1)
    
    mq_sensors_data = [
        ("MQ-137 (Ammonia)", "NH₃ (Ammonia): N/A"), 
        ("MQ-136 (H2S)", "H₂S: N/A"), 
        ("MQ-4 (Methane)", "CH₄: N/A"), 
        ("MQ-7 (CO)", "CO: N/A"), 
    ]
    
    for i, (key, initial_text) in enumerate(mq_sensors_data):
        col = i % 2
        row = i // 2
        label = ttk.Label(enose_raw_frame, text=initial_text, style="Data.TLabel", foreground=TEXT_COLOR)
        label.grid(row=row, column=col, padx=10, pady=8, sticky="w")
        raw_label_refs[key] = label


    # --- 3. NESTED FUNCTIONS (Logic and Animations) ---

    def save_to_report(sample_id, sample, readings, quality):
        """Saves a single test entry to the report CSV."""
        new_entry = [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), sample_id, sample] + readings + [quality]
        file_exists = os.path.exists(report_file)
        
        column_names = [
            "Timestamp", "Sample ID", "Type", 
            "Temperature", "Humidity", "WHC Index", "Fatty Acid Profile", 
            "MQ-137 (Ammonia)", "MQ-136 (H2S)", "MQ-4 (Methane)", "MQ-7 (CO)", "Quality"
        ]
        
        with open(report_file, "a", newline="") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(column_names)
            
            if len(new_entry) == 12:
                writer.writerow(new_entry)
            else:
                 show_custom_message(dashboard_tab, "Data Save Error", f"Report save failed: Expected 12 columns, got {len(new_entry)}. Data not logged.", "error", THEME_PALETTE)


    def idle_pulse(target_frame, count=10):
        """Creates a subtle, constant pulse on the border for 'Active Monitoring' state."""
        # Stop pulsing during a test run
        if btn_run.cget("state") == "disabled":
            return
            
        # 1. Subtle color shift (PRIMARY to BORDER color)
        current_color = target_frame.cget("highlightbackground")
        next_color = PRIMARY_COLOR if current_color == BORDER_COLOR else BORDER_COLOR

        target_frame.config(highlightbackground=next_color)
        
        # 2. Schedule the next pulse (slower heartbeat, ~800ms cycle)
        dashboard_tab.after(400, lambda: idle_pulse(target_frame))


    def pulse_feedback(widget, original_fg, count):
        """Animation function for score label pulse."""
        if count > 0:
            current_fg = widget.cget("foreground")
            next_fg = ACCENT_COLOR if current_fg != ACCENT_COLOR else original_fg
            widget.config(foreground=next_fg)
            dashboard_tab.after(100, lambda: pulse_feedback(widget, original_fg, count - 1))
        else:
            widget.config(foreground=original_fg)

    def pulse_status_light(fill_color, count):
        """Animation function for status light pulse during scanning."""
        if count > 0:
            current_fill = status_canvas.itemcget(status_light, 'fill')
            next_fill = ACCENT_COLOR if current_fill != ACCENT_COLOR else SECONDARY_BG
            status_canvas.itemconfig(status_light, fill=next_fill)
            dashboard_tab.after(200, lambda: pulse_status_light(fill_color, count - 1)) 
        else:
            status_canvas.itemconfig(status_light, fill=fill_color)
            
            # Restart idle pulse after the test finishes and the final status is set
            dashboard_tab.after(500, lambda: idle_pulse(control_border_frame))


    def data_stream_pulse(labels_dict, count):
        """Enhanced animation for raw data labels to simulate intense, live data stream."""
        labels_list = list(labels_dict.values()) 
        
        if count > 0:
            for label in labels_list:
                current_fg = label.cget("foreground")
                # Alternate between PRIMARY (cyan) and TEXT (white/light gray) for high contrast stream
                next_fg = PRIMARY_COLOR if current_fg == TEXT_COLOR else TEXT_COLOR
                label.config(foreground=next_fg)
            # Faster pulse speed (150ms per cycle)
            dashboard_tab.after(150, lambda: data_stream_pulse(labels_dict, count - 1)) 
        else:
            # When done, reset all label colors to default TEXT color
            for label in labels_list:
                label.config(foreground=TEXT_COLOR)


    def update_gui_and_archive(raw_readings, sample_type):
        """Processes data, updates GUI elements, and archives data (runs safely on main thread)."""
        global current_sample_id 
        
        # 1. Stop progress
        progress_bar.stop()
        progress_bar.config(mode="determinate", value=100) 

        # --- CALCULATE SCORES ---
        enose_index, whc_index, fac_index, final_score = sensor_fusion.calculate_group_scores(
            raw_readings
        )
        quality_category, color_tag, score = sensor_fusion.calculate_overall_quality(final_score)

        # Determine final status color
        final_color = DANGER_COLOR
        if color_tag == 'high': final_color = SUCCESS_COLOR
        elif color_tag == 'normal': final_color = NORMAL_COLOR 
        
        # 2. Update Group Score Cards
        enose_ref['label'].config(text=f"{enose_index}", foreground=final_color)
        whc_ref['label'].config(text=f"{whc_index}", foreground=final_color)
        fac_ref['label'].config(text=f"{fac_index}", foreground=final_color)
        
        enose_ref['bar'].config(value=enose_index)
        whc_ref['bar'].config(value=whc_index)
        fac_ref['bar'].config(value=fac_index)
        
        # 3. Update Raw Sensor Labels (Static text update after scan)
        raw_label_refs["Temperature"].config(text=f"Temperature: {raw_readings['Temperature']:.1f} °C")
        raw_label_refs["Humidity"].config(text=f"Humidity: {raw_readings['Humidity']:.1f} % RH")
        
        raw_label_refs["MQ-137 (Ammonia)"].config(text=f"NH₃ (Ammonia): {raw_readings['MQ-137 (Ammonia)']}")
        raw_label_refs["MQ-136 (H2S)"].config(text=f"H₂S: {raw_readings['MQ-136 (H2S)']}")
        raw_label_refs["MQ-4 (Methane)"].config(text=f"CH₄: {raw_readings['MQ-4 (Methane)']}")
        raw_label_refs["MQ-7 (CO)"].config(text=f"CO: {raw_readings['MQ-7 (CO)']}")

        whc_raw_display = raw_readings['WHC Index'] if raw_readings['WHC Index'] != SPECTROMETER_PLACEHOLDER else "N/A"
        fac_raw_display = raw_readings['Fatty Acid Profile'] if raw_readings['Fatty Acid Profile'] != SPECTROMETER_PLACEHOLDER else "N/A"
        
        raw_label_refs["WHC Index"].config(text=f"WHC Raw: {whc_raw_display}")
        raw_label_refs["Fatty Acid Profile"].config(text=f"FAC Raw: {fac_raw_display}")
        
        # Reset raw data label colors
        data_stream_pulse(raw_label_refs, 0) # Force stop/reset color

        # 4. Update Overall Quality Label
        score_display.config(text=str(score), foreground=final_color)
        quality_label.config(text=f"[ {quality_category} ]", foreground=final_color)
        score_border_frame.config(highlightbackground=final_color)

        # 5. Apply pulse animation for final score
        pulse_feedback(score_display, final_color, 8) 
        pulse_feedback(quality_label, final_color, 8) 
        # pulse_status_light is called at the end of its sequence to re-enable idle_pulse

        # 6. Archival logic
        is_confirmed = show_custom_message(
            dashboard_tab, 
            "Save Test Result", 
            f"Analysis Complete. Category: {quality_category} ({score}).\nProceed with archival?", 
            "confirm", 
            THEME_PALETTE
        )
        
        if is_confirmed:
            # Sample ID generation logic
            prefix = sample_type_prefix[sample_type]
            num = 0
            if os.path.exists(report_file):
                try:
                    with open(report_file, "r", newline="") as f:
                        reader = csv.reader(f)
                        next(reader, None) 
                        same_type = [r for r in reader if len(r) > 2 and r[2] == sample_type]
                        num = len(same_type)
                except Exception as e:
                    print(f"Error reading report file: {e}")
                    
            sid = f"PS-{prefix}_{num+1:04d}" 
            current_sample_id = sid
            sample_id_label.config(text=sid)
            
            readings_list = [raw_readings[k] for k in [
                "Temperature", "Humidity", "WHC Index", "Fatty Acid Profile", 
                "MQ-137 (Ammonia)", "MQ-136 (H2S)", "MQ-4 (Methane)", "MQ-7 (CO)"
            ]]
            
            save_to_report(sid, sample_type, readings_list, quality_category)
            show_custom_message(dashboard_tab, "Archival Success", f"Test data archived as {sid}", "success", THEME_PALETTE)

        # 7. Re-enable buttons
        btn_run.config(state="normal")
        btn_clear.config(state="normal")


    def perform_scan_threaded(sample_type):
        """Performs the blocking sensor read in a background thread (3 second simulation)."""
        
        # Status update (Main Thread)
        dashboard_tab.after(0, lambda: progress_bar.config(mode="indeterminate"))
        dashboard_tab.after(0, lambda: progress_bar.start(15)) 
        
        # Start animations (15 cycles * 200ms = 3 seconds)
        dashboard_tab.after(0, lambda: pulse_status_light(ACCENT_COLOR, 15)) 
        dashboard_tab.after(0, lambda: data_stream_pulse(raw_label_refs, 20)) # 20 cycles * 150ms = 3 seconds

        try:
            # Blocking sensor read simulation
            time.sleep(3) 
            raw_readings = sensor_fusion.read_all_sensors() 
            dashboard_tab.after(0, lambda: update_gui_and_archive(raw_readings, sample_type))

        except Exception as e:
            # Error handling (Main Thread)
            dashboard_tab.after(0, lambda: progress_bar.stop())
            dashboard_tab.after(0, lambda: score_display.config(text="FAIL", foreground=DANGER_COLOR))
            dashboard_tab.after(0, lambda: quality_label.config(text="SENSOR ERROR", foreground=DANGER_COLOR))
            dashboard_tab.after(0, lambda: status_canvas.itemconfig(status_light, fill=DANGER_COLOR))
            dashboard_tab.after(0, lambda: btn_run.config(state="normal"))
            dashboard_tab.after(0, lambda: btn_clear.config(state="normal"))
            dashboard_tab.after(0, lambda: idle_pulse(control_border_frame)) # Resume idle pulse
            dashboard_tab.after(0, lambda: show_custom_message(dashboard_tab, "Sensor Error", f"Failed to read hardware sensors:\n{e}", "error", THEME_PALETTE))
            return
            
            
    # --- Test/Clear Logic ---
    def run_test():
        sample_type = sample_type_combobox.get()
        if not sample_type:
            show_custom_message(dashboard_tab, "Missing Selection", "Please select a sample type before running the test.", "warning", THEME_PALETTE)
            return

        # 1. Disable buttons and stop idle pulse
        btn_run.config(state="disabled")
        btn_clear.config(state="disabled")
        control_border_frame.config(highlightbackground=ACCENT_COLOR) # Lock border to ACCENT color during scan
        
        # 2. Update status labels and set initial scanning colors
        score_display.config(text="...", foreground=ACCENT_COLOR)
        quality_label.config(text=f"SCANNING {sample_type}...", foreground=ACCENT_COLOR)
        score_border_frame.config(highlightbackground=ACCENT_COLOR)
        
        # Update index labels to show 'scanning' status
        enose_ref['label'].config(text="...", foreground=ACCENT_COLOR)
        whc_ref['label'].config(text="...", foreground=ACCENT_COLOR)
        fac_ref['label'].config(text="...", foreground=ACCENT_COLOR)
        enose_ref['bar'].config(value=0)
        whc_ref['bar'].config(value=0)
        fac_ref['bar'].config(value=0)
        
        # Update raw data text to scanning status (will be animated by data_stream_pulse)
        for key in raw_label_refs:
             current_text = raw_label_refs[key].cget('text').split(':')[0]
             raw_label_refs[key].config(text=f"{current_text}: *** STREAMING ***", foreground=PRIMARY_COLOR)
        
        dashboard_tab.update_idletasks()
        
        # 3. Start the background thread for the scan
        scan_thread = threading.Thread(target=perform_scan_threaded, args=(sample_type,), daemon=True)
        scan_thread.start()


    def clear_dashboard():
        global current_sample_id
        
        sample_type_combobox.set("Chicken Breast")
        sample_id_label.config(text="PS-INIT-0000")
        
        # Reset score and environmental labels
        score_display.config(text="--", foreground=UNSELECTED_TEXT)
        quality_label.config(text="AWAITING SCAN", foreground=UNSELECTED_TEXT)
        score_border_frame.config(highlightbackground=UNSELECTED_TEXT)
        
        # Reset Index labels and bars
        enose_ref['label'].config(text="--", foreground=UNSELECTED_TEXT)
        whc_ref['label'].config(text="--", foreground=UNSELECTED_TEXT)
        fac_ref['label'].config(text="--", foreground=UNSELECTED_TEXT)
        enose_ref['bar'].config(value=0)
        whc_ref['bar'].config(value=0)
        fac_ref['bar'].config(value=0)
        
        status_canvas.itemconfig(status_light, fill=UNSELECTED_TEXT)
        
        # Reset raw data labels and color
        raw_label_refs["Temperature"].config(text="Temperature: -- °C", foreground=TEXT_COLOR)
        raw_label_refs["Humidity"].config(text="Humidity: -- % RH", foreground=TEXT_COLOR)
        raw_label_refs["MQ-137 (Ammonia)"].config(text="NH₃ (Ammonia): N/A", foreground=TEXT_COLOR)
        raw_label_refs["MQ-136 (H2S)"].config(text="H₂S: N/A", foreground=TEXT_COLOR)
        raw_label_refs["MQ-4 (Methane)"].config(text="CH₄: N/A", foreground=TEXT_COLOR)
        raw_label_refs["MQ-7 (CO)"].config(text="CO: N/A", foreground=TEXT_COLOR)
        raw_label_refs["WHC Index"].config(text="WHC Raw: N/A", foreground=TEXT_COLOR)
        raw_label_refs["Fatty Acid Profile"].config(text="FAC Raw: N/A", foreground=TEXT_COLOR)
             
        # Ensure progress bar is reset
        progress_bar.stop()
        progress_bar.config(mode="indeterminate")
        progress_bar["value"] = 0
        current_sample_id = None
        
        # Restart idle pulse
        idle_pulse(control_border_frame, 1)

    # 4. Attach Commands to Buttons
    btn_run.config(command=run_test)
    btn_clear.config(command=clear_dashboard)
    
    # 5. Start the initial "Active Monitoring" idle pulse
    dashboard_tab.after(100, lambda: idle_pulse(control_border_frame))
    
    return dashboard_tab