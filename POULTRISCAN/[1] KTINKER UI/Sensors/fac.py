# Sensors/fac.py

import random

SPECTROMETER_PLACEHOLDER = "No Sensor Yet" # Matches the one in whc.py

def read_fac():
    """Reads or mocks Fatty Acid Profile Index."""
    # Fatty Acid Profile mock data (0.4 to 1.6, raw index)
    fac_profile = round(random.uniform(0.4, 1.6), 2)
    
    # Return the raw reading dictionary
    return {
        "Fatty Acid Profile": fac_profile
    }