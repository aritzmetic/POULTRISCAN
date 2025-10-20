# Sensors/whc.py

import random

# Placeholder for AS7265X sensor if it's not connected or the library fails
SPECTROMETER_PLACEHOLDER = "No Sensor Yet"

def read_whc():
    """Reads or mocks Water Holding Capacity Index."""
    # WHC Index mock data (0.70 to 0.98, raw ratio)
    whc_index = round(random.uniform(0.70, 0.98), 2)
    
    # Return the raw reading dictionary
    return {
        "WHC Index": whc_index
    }

read_whc.SPECTROMETER_PLACEHOLDER = SPECTROMETER_PLACEHOLDER