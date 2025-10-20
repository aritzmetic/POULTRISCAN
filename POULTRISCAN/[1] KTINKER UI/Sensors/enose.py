# Sensors/enose.py

import random

# Global flag for status tracking
ENOSE_INITIALIZED = False
ADS_PINS = [0, 1, 2, 3] 

class MockSensor:
    """Mock class for AnalogIn to simulate MQ sensor readings."""
    def __init__(self, *args):
        pass
    @property
    def voltage(self):
        # Return realistic mock voltage values for MQ sensors
        return random.uniform(0.1, 0.6) 

mq_sensors = {
    "MQ-137 (Ammonia)": MockSensor(), 
    "MQ-136 (H2S)": MockSensor(), 
    "MQ-4 (Methane)": MockSensor(), 
    "MQ-7 (CO)": MockSensor(),
}

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
    
    mq_sensors["MQ-137 (Ammonia)"] = AnalogIn(ads, ADS_PINS[0])
    mq_sensors["MQ-136 (H2S)"] = AnalogIn(ads, ADS_PINS[1])
    mq_sensors["MQ-4 (Methane)"] = AnalogIn(ads, ADS_PINS[2])
    mq_sensors["MQ-7 (CO)"] = AnalogIn(ads, ADS_PINS[3])
    
    ENOSE_INITIALIZED = True
    print("eNose hardware initialized.")

except (ImportError, NotImplementedError, ValueError) as e:
    # Catching the same set of errors for graceful mock fallback
    print(f"eNose initialization FAILED: {type(e).__name__}: {e}. Using mock data.")
    
def read_enose():
    """Reads raw gas sensor data."""
    readings = {}
    for name, sensor in mq_sensors.items():
        # Voltage * 10 is used as a proxy for the uncalibrated concentration index.
        readings[name] = round(sensor.voltage * 10.0, 2)
    return readings