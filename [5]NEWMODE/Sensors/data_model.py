# Sensors/data_model.py

import math
import csv
import os
import sys

"""
This file contains the "Classifier + Biochemical Approximator" logic.
It uses thresholds and spectral algorithms to determine meat quality.

STRICT MODE:
This script REQUIRES '[COMPILED POULTRISCAN DATA.csv' in the Sensors/ folder.
It will RAISE AN ERROR and STOP if the file is missing or invalid.

UPDATED LOGIC:
- Uses ALL 18 Spectral Channels for "Fresh vs Semi-Fresh" classification.
- Returns QUALITY GRADE (A, B, C) instead of raw score.
"""

# ==============================================================================
# 🎚️ GLOBAL VARIABLES (Uninitialized)
# ==============================================================================

# Safety Limits
FRESH_CH2_MIN = None
FRESH_MQ137_MAX = None
FRESH_MQ3_MAX = None

# Spectral Fingerprints
MEAN_SPECTRAL_FRESH = []
MEAN_SPECTRAL_SEMI = []

# Biochem Standards
MAX_REDNESS = None
MAX_LUMA = None
WHC_BASE = 88.0 

TRAINING_FILE_NAME = "[COMPILED POULTRISCAN DATA.csv"

# ==============================================================================
# 📂 STRICT DYNAMIC CALIBRATION LOADING
# ==============================================================================

def load_calibration():
    """
    Reads the CSV file to calculate 18-channel Spectral Fingerprints.
    Raises CRITICAL ERRORS if file is missing or data is insufficient.
    """
    global FRESH_CH2_MIN, FRESH_MQ137_MAX, FRESH_MQ3_MAX
    global MEAN_SPECTRAL_FRESH, MEAN_SPECTRAL_SEMI
    global MAX_REDNESS, MAX_LUMA

    base_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(base_dir, TRAINING_FILE_NAME)
            
    if not os.path.exists(csv_path):
        error_msg = (
            f"\n\n[CRITICAL ERROR] Calibration File Missing!\n"
            f"Expected file: {csv_path}\n"
            f"Please upload '{TRAINING_FILE_NAME}' to the Sensors folder.\n"
        )
        raise FileNotFoundError(error_msg)

    print(f"✅ LOADING CALIBRATION from: {csv_path}")

    try:
        fresh_mq137 = []
        fresh_mq3 = []
        fresh_ch2_vals = []
        
        fresh_spectral_data = {i: [] for i in range(1, 19)}
        semi_spectral_data = {i: [] for i in range(1, 19)}
        
        fresh_reds = [] 
        all_lumas = [] 

        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            reader.fieldnames = [name.strip() for name in reader.fieldnames]
            
            for row in reader:
                try:
                    label = row.get('spoilage_label', '').strip()
                    mq137 = float(row.get('mq137_v_rs', 0))
                    mq3 = float(row.get('mq3_v_rs', 0))
                    
                    current_spectrum = {}
                    for i in range(1, 19):
                        current_spectrum[i] = float(row.get(f'as_raw_ch{i}', 0))

                    luma = (current_spectrum[2] + current_spectrum[5] + current_spectrum[7]) / 3.0
                    all_lumas.append(luma)

                    if label == 'Fresh':
                        fresh_mq137.append(mq137)
                        fresh_mq3.append(mq3)
                        fresh_ch2_vals.append(current_spectrum[2])
                        for i in range(1, 19):
                            fresh_spectral_data[i].append(current_spectrum[i])
                        red = (current_spectrum[9] + current_spectrum[10] + current_spectrum[11]) / 3.0
                        fresh_reds.append(red)

                    elif label == 'Semi-Fresh':
                        for i in range(1, 19):
                            semi_spectral_data[i].append(current_spectrum[i])

                except ValueError:
                    continue 

        if not fresh_spectral_data[1] or not semi_spectral_data[1]:
             raise ValueError(f"[CRITICAL ERROR] CSV loaded but missing Fresh or Semi-Fresh data.")

        # Calculations
        FRESH_CH2_MIN = min(fresh_ch2_vals)
        FRESH_MQ137_MAX = max(fresh_mq137)
        FRESH_MQ3_MAX = max(fresh_mq3)
        
        def avg(lst): return sum(lst) / len(lst) if lst else 0
        MEAN_SPECTRAL_FRESH = [avg(fresh_spectral_data[i]) for i in range(1, 19)]
        MEAN_SPECTRAL_SEMI = [avg(semi_spectral_data[i]) for i in range(1, 19)]
        
        MAX_LUMA = max(all_lumas)
        fresh_reds.sort()
        idx = int(len(fresh_reds) * 0.95)
        idx = min(idx, len(fresh_reds) - 1)
        MAX_REDNESS = fresh_reds[idx]

        print("✅ DYNAMIC CALIBRATION SUCCESSFUL.")

    except Exception as e:
        print(f"\n❌ FATAL CALIBRATION ERROR: {e}")
        raise e

load_calibration()


# ==============================================================================
# 🧠 CORE LOGIC
# ==============================================================================

def calculate_multidimensional_distance(vec1, vec2):
    if len(vec1) != len(vec2): return float('inf')
    return math.sqrt(sum(math.pow(a - b, 2) for a, b in zip(vec1, vec2)))

def calculate_group_scores(raw_readings):
    # 1. Data Extraction
    mq137 = raw_readings.get('MQ-137 (Ammonia)', 0)
    mq3 = raw_readings.get('MQ-3 (Alcohol)', 0)
    current_spectrum = [raw_readings.get(f'AS7265X_ch{i}', 0) for i in range(1, 19)]
    def get_ch_val(ch_num): return current_spectrum[ch_num - 1]

    # 2. Classification Logic
    pred_label = "Unsure"
    classification_score = 0 
    
    # A. Safety Limits
    if get_ch_val(2) < FRESH_CH2_MIN:
        classification_score = 25 # Spoiled
    elif mq137 > FRESH_MQ137_MAX or mq3 > FRESH_MQ3_MAX:
        classification_score = 35 # Spoiled
    else:
        # B. Spectral Matching
        dist_fresh = calculate_multidimensional_distance(current_spectrum, MEAN_SPECTRAL_FRESH)
        dist_semi = calculate_multidimensional_distance(current_spectrum, MEAN_SPECTRAL_SEMI)
        
        if dist_fresh < dist_semi:
            classification_score = 95 # Fresh
        else:
            classification_score = 65 # Semi-Fresh

    # 3. Biochem Approximation
    current_red = (get_ch_val(9) + get_ch_val(10) + get_ch_val(11)) / 3.0
    ref_red = MAX_REDNESS if MAX_REDNESS > 0 else 500
    myo_est = min(max(((current_red / ref_red) * 2.5), 0.1), 3.5) 
    
    current_luma = (get_ch_val(2) + get_ch_val(5) + get_ch_val(7)) / 3.0
    ref_luma = MAX_LUMA if MAX_LUMA > 0 else 2000
    fat_est = min(max(((current_luma / ref_luma) * 6.0), 0.5), 8.0) 
    
    ref_gas = FRESH_MQ137_MAX if FRESH_MQ137_MAX > 0 else 1.5
    whc_est = min(max((WHC_BASE - ((mq137 / (ref_gas * 1.5)) * 20.0)), 50.0), 95.0)

    # 4. UI Outputs
    enose_index = max(0, min(100, int(100 - (mq137 * 30))))
    whc_index = int(whc_est)
    fac_index = int((fat_est / 8.0) * 100)
    myoglobin_index = int((myo_est / 3.5) * 100)

    return enose_index, whc_index, fac_index, myoglobin_index, int(classification_score)


def calculate_overall_quality(final_score):
    """
    Translates the numeric score into a QUALITY GRADE.
    """
    category = "PENDING"
    color_tag = "normal"
    grade_text = "N/A"
    
    if final_score >= 80:
        category = "FRESH"
        color_tag = "high" # Green
        grade_text = "Grade A"
    elif final_score >= 50:
        category = "SEMI-FRESH"
        color_tag = "normal" # Yellow/Orange
        grade_text = "Grade B"
    else:
        category = "SPOILT"
        color_tag = "low" # Red
        grade_text = "Grade C"
        
    return category, color_tag, grade_text