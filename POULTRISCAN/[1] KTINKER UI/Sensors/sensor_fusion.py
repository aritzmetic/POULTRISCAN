# Sensors/sensor_fusion.py

import random

# Import sensor reading functions
try:
    # Assuming successful import logic from previous steps
    from Sensors.aht20 import read_aht20
    from Sensors.enose import read_enose
except ImportError as e:
    print(f"Failed to import sensor modules for fusion: {e}")
    # Define placeholder functions to prevent crash
    def read_aht20(): return {"Temperature": random.uniform(25, 30), "Humidity": random.uniform(50, 70)}
    def read_enose(): return {"MQ-137 (Ammonia)": random.uniform(1, 6), "MQ-136 (H2S)": random.uniform(0.5, 3), "MQ-4 (Methane)": random.uniform(2, 9), "MQ-7 (CO)": random.uniform(1, 5)}


# Placeholder for spectrometer value
SPECTROMETER_PLACEHOLDER = "N/A - Spectrometer Mock"


def read_spectrometer():
    """Mocks the spectrometer data (WHC and Fatty Acid Profile)."""
    # These are mock values for the AS7265X sensor data
    return {
        "WHC Index": round(random.uniform(0.80, 0.95), 3),
        "Fatty Acid Profile": round(random.uniform(0.40, 0.65), 3),
    }

def read_all_sensors():
    """Consolidates all sensor readings."""
    
    # Read individual components
    temp_hum_data = read_aht20()
    mq_data = read_enose()
    spec_data = read_spectrometer()

    # Combine all readings into a single dictionary
    raw_readings = {
        **temp_hum_data,
        **mq_data,
        **spec_data
    }

    return raw_readings


def calculate_group_scores(raw_readings):
    """
    Calculates the single PoultriScan Quality Score (0-100) 
    based on a weighted average of three index values.
    """
    
    # --- 1. eNose Index (VOCs) ---
    gas_readings = [
        raw_readings["MQ-137 (Ammonia)"], 
        raw_readings["MQ-136 (H2S)"], 
        raw_readings["MQ-4 (Methane)"], 
        raw_readings["MQ-7 (CO)"]
    ]
    avg_gas = sum(gas_readings) / len(gas_readings)
    # Scale: Lower avg_gas (fresher) -> Higher score (e.g., 100 - (2 * 5) = 90)
    enose_index = max(0, min(100, round(100 - (avg_gas * 8), 0))) 

    # --- 2. WHC Index (Water Holding Capacity) ---
    whc_raw = raw_readings["WHC Index"]
    # Scale: Higher whc_raw (better WHC) -> Higher score (e.g., 0.90 * 100 = 90)
    whc_index = max(0, min(100, round(whc_raw * 100, 0)))

    # --- 3. FAC Index (Fatty Acid Profile) ---
    fac_raw = raw_readings["Fatty Acid Profile"]
    # Scale: Higher fac_raw (better profile) -> Higher score (e.g., 0.55 * 150 = 82.5)
    fac_index = max(0, min(100, round(fac_raw * 150, 0))) 

    # --- 4. Weighted Average for Final Score (PoultriScan Quality Score) ---
    # Example Weighting: eNose (40%), WHC (30%), FAC (30%)
    WEIGHTS = {
        "ENOSE": 0.40,
        "WHC": 0.30,
        "FAC": 0.30
    }
    
    final_score = (
        (enose_index * WEIGHTS["ENOSE"]) + 
        (whc_index * WEIGHTS["WHC"]) + 
        (fac_index * WEIGHTS["FAC"])
    )

    # Return the three indexes for display, and the final score
    return int(enose_index), int(whc_index), int(fac_index), int(round(final_score))


def calculate_overall_quality(final_score):
    """Maps the single final score to one of the five quality categories."""
    
    if final_score >= 90:
        category = "FRESH"
        color_tag = "high"
    elif final_score >= 80:
        category = "SLIGHTLY FRESH"
        color_tag = "high"
    elif final_score >= 60:
        category = "NORMAL"
        color_tag = "low"
    elif final_score >= 40:
        category = "SLIGHTLY SPOILED"
        color_tag = "low"
    else: # < 40
        category = "SPOILED"
        color_tag = "low"
        
    return category, color_tag, final_score