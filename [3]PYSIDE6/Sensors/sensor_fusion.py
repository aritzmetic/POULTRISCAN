# Sensors/sensor_fusion.py

import sys

# Import sensor reading functions
try:
    # Assuming the updated aht20.py and enose.py (with no random/mock) are in place
    from Sensors.aht20 import read_aht20
    from Sensors.enose import read_enose
    # Import the custom error types for robust handling
    from Sensors.aht20 import UninitializedAHT20Error 
    from Sensors.enose import UninitializedENoseError
except ImportError as e:
    print(f"FATAL: Failed to import required sensor modules for fusion: {e}")
    sys.exit(1) # Exit if core sensor modules cannot be imported


# Placeholder for spectrometer value (WHC and FAC)
SPECTROMETER_PLACEHOLDER = "No Sensor Yet"


def read_spectrometer():
    """
    Spectrometer data (WHC and Fatty Acid Profile) is currently bypassed.
    Returns the placeholder value as the raw reading.
    """
    # These values will be used as the raw readings in read_all_sensors
    return {
        "WHC Index": SPECTROMETER_PLACEHOLDER,
        "Fatty Acid Profile": SPECTROMETER_PLACEHOLDER,
    }

def read_all_sensors():
    """Consolidates all sensor readings."""
    
    # Read individual components. Errors will propagate from the sensor files if hardware fails.
    try:
        temp_hum_data = read_aht20()
        mq_data = read_enose()
    except (UninitializedAHT20Error, UninitializedENoseError) as e:
        # Re-raise the hardware initialization error
        print(f"Hardware Error in Fusion: {e}")
        raise
        
    spec_data = read_spectrometer() # Reads the placeholder string

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
    
    The function handles the 'No Sensor Yet' placeholder for WHC and FAC.
    """
    
    # --- 1. eNose Index (VOCs) ---
    # Ensure sensor names are correct: 137, 135, 7, 4
    try:
        gas_readings = [
            raw_readings["MQ-137 (Ammonia)"], 
            raw_readings["MQ-135 (Air Quality)"], 
            raw_readings["MQ-7 (CO)"], 
            raw_readings["MQ-4 (Methane)"]
        ]
        avg_gas = sum(gas_readings) / len(gas_readings)
        # Scale: Lower avg_gas (fresher) -> Higher score
        enose_index = max(0, min(100, round(100 - (avg_gas * 8), 0))) 
    except KeyError:
        print("Error: MQ sensor names in raw_readings do not match expected names.")
        enose_index = 0
    except Exception as e:
        print(f"Error calculating eNose Index: {e}")
        enose_index = 0


    # --- 2. WHC Index (Water Holding Capacity) ---
    whc_raw = raw_readings["WHC Index"]
    if whc_raw == SPECTROMETER_PLACEHOLDER:
        whc_index = 0
        print("WHC Index set to 0: Sensor unavailable.")
    else:
        # Scale: Higher whc_raw (better WHC) -> Higher score
        whc_index = max(0, min(100, round(whc_raw * 100, 0)))

    # --- 3. FAC Index (Fatty Acid Profile) ---
    fac_raw = raw_readings["Fatty Acid Profile"]
    if fac_raw == SPECTROMETER_PLACEHOLDER:
        fac_index = 0
        print("FAC Index set to 0: Sensor unavailable.")
    else:
        # Scale: Higher fac_raw (better profile) -> Higher score
        fac_index = max(0, min(100, round(fac_raw * 150, 0))) 

    # --- 4. Weighted Average for Final Score (PoultriScan Quality Score) ---
    WEIGHTS = {
        "ENOSE": 0.40,
        "WHC": 0.30,
        "FAC": 0.30
    }
    
    # Calculate final score using the calculated indices
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