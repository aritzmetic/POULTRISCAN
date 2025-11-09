# Sensors/enose.py

import sys

# Global flag for status tracking
ENOSE_INITIALIZED = False
ADS_PINS = [0, 1, 2, 3] 

class UninitializedENoseError(Exception):
    """Custom exception raised when eNose object is accessed but failed to initialize."""
    pass

class SensorUnavailable:
    """Placeholder class that raises an error if accessed for voltage (removes random)."""
    def __init__(self, *args):
        pass
    @property
    def voltage(self):
        raise UninitializedENoseError("eNose (ADS1115/MQ sensors) access attempted, but initialization failed. Check wiring and I2C.")

# Define the sensor names and their corresponding ADC channel index (A0=0, A1=1, A2=2, A3=3)
# --- MODIFIED: Order: 137, 135, 3, 4 ---
mq_sensor_names = {
    0: "MQ-137 (Ammonia)",     # Connected to A0
    1: "MQ-135 (Air Quality)", # Connected to A1
    2: "MQ-3 (Alcohol)",       # --- MODIFIED: Connected to A2
    3: "MQ-4 (Methane)",       # Connected to A3
}

# Initialize all entries with the error-raising object
mq_sensors = {name: SensorUnavailable() for name in mq_sensor_names.values()}


try:
    # --- HARDWARE-DEPENDENT IMPORTS ---
    import board
    import busio
    from adafruit_ads1x15.ads1115 import ADS1115
    from adafruit_ads1x15.analog_in import AnalogIn
    # ---------------------------------
    
    # Attempt to initialize hardware
    i2c = busio.I2C(board.SCL, board.SDA)
    ads = ADS1115(i2c)
    
    # Map the AnalogIn channels to the sensor dictionary using the defined names/pins
    mq_sensors[mq_sensor_names[0]] = AnalogIn(ads, ADS_PINS[0]) # MQ-137 on A0
    mq_sensors[mq_sensor_names[1]] = AnalogIn(ads, ADS_PINS[1]) # MQ-135 on A1
    mq_sensors[mq_sensor_names[2]] = AnalogIn(ads, ADS_PINS[2]) # --- MODIFIED: MQ-3 on A2
    mq_sensors[mq_sensor_names[3]] = AnalogIn(ads, ADS_PINS[3]) # MQ-4 on A3
    
    ENOSE_INITIALIZED = True
    print("eNose hardware initialized successfully.")

except (ImportError, NotImplementedError, ValueError) as e:
    # Catching the errors if hardware setup fails.
    print("-" * 50)
    print(f"eNose initialization FAILED: {type(e).__name__}: {e}.")
    print("Ensure I2C is enabled and required CircuitPython libraries are installed.")
    print("eNose readings will now raise an exception.")
    print("-" * 50)
    
def read_enose():
    """Reads raw gas sensor data (voltage) from the actual sensor."""
    readings = {}
    
    # --- MODIFIED: Use the defined order (137, 135, 3, 4) to iterate over the dictionary keys ---
    ordered_names = [
        mq_sensor_names[0], 
        mq_sensor_names[1], 
        mq_sensor_names[2], 
        mq_sensor_names[3]
    ]

    for name in ordered_names:
        sensor = mq_sensors[name]
        try:
            # Reads the actual voltage from the AnalogIn object
            # Use 3 decimal places for voltage precision
            raw_voltage = sensor.voltage
            readings[name] = round(raw_voltage, 3) 
            
        except UninitializedENoseError as e:
            # Re-raise the custom error for the calling application to handle
            raise e
        except Exception as e:
            # Handle other potential hardware reading errors (e.g., I2C lockup)
            print(f"Error reading sensor {name}: {e}")
            raise UninitializedENoseError(f"Hardware reading error on {name}.") from e
            
    return readings