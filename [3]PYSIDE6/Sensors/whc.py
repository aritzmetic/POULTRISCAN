# Sensors/whc.py

# Placeholder for AS7265X sensor since it's not connected
SPECTROMETER_PLACEHOLDER = "No Sensor Yet"

def read_whc():
    """Reads Water Holding Capacity Index. Currently bypassed."""
    # Returns the placeholder string as the raw reading
    return {
        "WHC Index": SPECTROMETER_PLACEHOLDER
    }

read_whc.SPECTROMETER_PLACEHOLDER = SPECTROMETER_PLACEHOLDER