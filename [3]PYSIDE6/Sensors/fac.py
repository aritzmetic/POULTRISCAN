# Sensors/fac.py

# Placeholder for AS7265X sensor since it's not connected
SPECTROMETER_PLACEHOLDER = "No Sensor Yet" 

def read_fac():
    """Reads Fatty Acid Profile Index. Currently bypassed."""
    # Returns the placeholder string as the raw reading
    return {
        "Fatty Acid Profile": SPECTROMETER_PLACEHOLDER
    }

read_fac.SPECTROMETER_PLACEHOLDER = SPECTROMETER_PLACEHOLDER