# Sensors/aht20.py

import sys

# Global flag for status tracking
AHT20_INITIALIZED = False

class UninitializedAHT20Error(Exception):
    """Custom exception raised when AHT20 object is accessed but failed to initialize."""
    pass

class SensorUnavailable:
    """Placeholder class that raises an error if accessed."""
    @property
    def temperature(self):
        raise UninitializedAHT20Error("AHT20 sensor access attempted, but initialization failed. Check wiring and I2C.")
    @property
    def relative_humidity(self):
        raise UninitializedAHT20Error("AHT20 sensor access attempted, but initialization failed. Check wiring and I2C.")

aht20 = SensorUnavailable() # Default to error-raising object

try:
    # --- HARDWARE-DEPENDENT IMPORTS ---
    import board
    import busio
    import adafruit_ahtx0 
    # ---------------------------------
    
    # Attempt to initialize hardware
    i2c = busio.I2C(board.SCL, board.SDA)
    aht20 = adafruit_ahtx0.AHTx0(i2c)
    AHT20_INITIALIZED = True
    print("AHT20 hardware initialized successfully.")

except (ImportError, NotImplementedError, ValueError) as e:
    # ImportError handles missing libraries (e.g., adafruit-blinka).
    # NotImplementedError handles the failure on unsupported platforms.
    # ValueError handles I2C bus not found errors.
    print("-" * 50)
    print(f"AHT20 initialization FAILED: {type(e).__name__}: {e}.")
    print("Ensure I2C is enabled and required CircuitPython libraries are installed.")
    print("AHT20 readings will now raise an exception.")
    print("-" * 50)
    # The default 'aht20 = SensorUnavailable()' remains, causing a failure on read.

def read_aht20():
    """Reads raw Temperature and Humidity from the actual sensor."""
    try:
        return {
            "Temperature": round(aht20.temperature, 1),
            "Humidity": round(aht20.relative_humidity, 1),
        }
    except UninitializedAHT20Error as e:
        # Re-raise the error to the calling function (e.g., sensor_fusion)
        raise e