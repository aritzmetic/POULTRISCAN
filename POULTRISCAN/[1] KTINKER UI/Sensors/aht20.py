# Sensors/aht20.py

import random

# Global flag for status tracking
AHT20_INITIALIZED = False

class MockAHT20:
    """Mock class for AHT20 to simulate Temp/Humidity."""
    @property
    def temperature(self):
        return round(random.uniform(25.0, 30.0), 1) 
    @property
    def relative_humidity(self):
        return round(random.uniform(50.0, 70.0), 1)

aht20 = MockAHT20() # Default to mock object

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
    print("AHT20 hardware initialized.")

except (ImportError, NotImplementedError, ValueError) as e:
    # ImportError handles missing libraries (e.g., adafruit-blinka not installed/working).
    # NotImplementedError handles the failure on Windows/unsupported platforms.
    # ValueError handles I2C bus not found errors on Pi if wires are wrong.
    print(f"AHT20 initialization FAILED: {type(e).__name__}: {e}. Using mock data.")

def read_aht20():
    """Reads raw Temperature and Humidity."""
    return {
        "Temperature": round(aht20.temperature, 1),
        "Humidity": round(aht20.relative_humidity, 1),
    }