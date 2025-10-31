# Sensors/as7265x.py

import sys
import atexit
import csv
import time

# ====================================================================
## 🔌 Sensor Fusion Imports
# ====================================================================

try:
    # Import reading functions and custom errors from other sensor modules
    from Sensors.aht20 import read_aht20, UninitializedAHT20Error
    from Sensors.enose import read_enose, UninitializedENoseError
except ImportError as e:
    print(f"FATAL: Failed to import required sensor modules (AHT20, eNose): {e}")
    sys.exit(1)

# ====================================================================
## ⚠️ Error Handling and Placeholder Setup
# ====================================================================

# Global flag and placeholder values
AS7265X_INITIALIZED = False
SPECTROMETER_PLACEHOLDER = "No Sensor Yet"

class UninitializedAS7265XError(Exception):
    """Custom exception raised when AS7265x object is accessed but failed to initialize."""
    pass

class SensorUnavailable:
    """
    Placeholder class for the spectrometer that raises an error
    if any methods are accessed before successful initialization.
    This now mocks the Qwiic library's methods.
    """
    def __init__(self, *args):
        pass

    def _raise_error(self):
        raise UninitializedAS7265XError("AS7265x sensor access attempted, but initialization failed. Check wiring and I2C.")

    # --- Create methods for all Qwiic functions to raise the error ---
    def begin(self): self._raise_error()
    def is_connected(self): return False
    def take_measurements(self): self._raise_error()
    
    # --- MOCK THE CORRECT LED METHODS ---
    def enable_bulb(self, led_type): self._raise_error()
    def disable_bulb(self, led_type): self._raise_error()
    
    # 18 Channel methods
    def get_calibrated_a(self): self._raise_error()
    def get_calibrated_b(self): self._raise_error()
    def get_calibrated_c(self): self._raise_error()
    def get_calibrated_d(self): self._raise_error()
    def get_calibrated_e(self): self._raise_error()
    def get_calibrated_f(self): self._raise_error()
    def get_calibrated_g(self): self._raise_error()
    def get_calibrated_h(self): self._raise_error()
    def get_calibrated_r(self): self._raise_error()
    def get_calibrated_i(self): self._raise_error()
    def get_calibrated_s(self): self._raise_error()
    def get_calibrated_j(self): self._raise_error()
    def get_calibrated_t(self): self._raise_error()
    def get_calibrated_u(self): self._raise_error()
    def get_calibrated_v(self): self._raise_error()
    def get_calibrated_w(self): self._raise_error()
    def get_calibrated_k(self): self._raise_error()
    def get_calibrated_l(self): self._raise_error()

# Default the spectrometer object to the error-raising class
spectrometer = SensorUnavailable()

# Define placeholder zeros for all 18 raw channels
AS7265X_PLACEHOLDER_ZEROS = {f"AS7265X_ch{i+1}": 0 for i in range(18)}

# ====================================================================
## 💡 Cleanup Function (for atexit)
# ====================================================================

def _cleanup_as7265x():
    """Internal cleanup function registered with atexit to shut down the LED."""
    global AS7265X_INITIALIZED, spectrometer
    if AS7265X_INITIALIZED:
        try:
            print("ATEIXT: Shutting down AS7265x White LED...")
            spectrometer.disable_bulb(0) # 0 = White LED
            print("ATEIXT: AS7265x White LED is OFF.")
        except Exception as e:
            print(f"ATEIXT: Error during AS7265x cleanup: {e}")

# ====================================================================
## ⚙️ Hardware Initialization
# ====================================================================

try:
    # --- HARDWARE-DEPENDENT IMPORTS ---
    import qwiic_as7265x
    # ---------------------------------

    # Attempt to initialize hardware
    spectrometer = qwiic_as7265x.QwiicAS7265x()

    if not spectrometer.is_connected():
        raise RuntimeError("AS7265x device not connected. Check I2C connection.")

    if not spectrometer.begin():
        raise RuntimeError("Unable to initialize AS7265x sensor.")

    spectrometer.enable_bulb(0) # 0 = White LED
    AS7265X_INITIALIZED = True

    # Register the cleanup function
    atexit.register(_cleanup_as7265x)

    print("AS7265x spectrometer hardware (Qwiic) initialized successfully.")

except (ImportError, RuntimeError) as e:
    # Initialization failed (missing libs, I2C bus error, etc.)
    print("-" * 50)
    print(f"AS7265x initialization FAILED: {type(e).__name__}: {e}.")
    print("Ensure I2C is enabled and the 'sparkfun-qwiic-as7265x' library is installed.")
    print("AS7265x readings will now be placeholders.")
    print("-" * 50)
    # Re-assign spectrometer to the error-raising class
    spectrometer = SensorUnavailable()

# ====================================================================
## 📊 Spectrometer Reading Function (for Main App)
# ====================================================================

def read_spectrometer():
    """
    Reads the AS7265x spectrometer and returns the raw 18-channel data,
    named AS7265X_ch1 through AS7265X_ch18.
    
    This function is for the main application import.
    """
    try:
        # Trigger a new measurement
        spectrometer.take_measurements()

        # Create a list of the 18 sensor values in the correct order
        sensor_values = [
            # AS72651 (UV-Violet)
            spectrometer.get_calibrated_a(), # ch1
            spectrometer.get_calibrated_b(), # ch2
            spectrometer.get_calibrated_c(), # ch3
            spectrometer.get_calibrated_d(), # ch4
            spectrometer.get_calibrated_e(), # ch5
            spectrometer.get_calibrated_f(), # ch6
            
            # AS72652 (Visible)
            spectrometer.get_calibrated_g(), # ch7
            spectrometer.get_calibrated_h(), # ch8
            spectrometer.get_calibrated_r(), # ch9 (610nm)
            spectrometer.get_calibrated_i(), # ch10 (645nm)
            spectrometer.get_calibrated_s(), # ch11 (680nm)
            spectrometer.get_calibrated_j(), # ch12 (705nm)
            
            # AS72653 (Near-IR)
            spectrometer.get_calibrated_t(), # ch13 (730nm)
            spectrometer.get_calibrated_u(), # ch14 (760nm)
            spectrometer.get_calibrated_v(), # ch15 (810nm)
            spectrometer.get_calibrated_w(), # ch16 (860nm)
            spectrometer.get_calibrated_k(), # ch17 (900nm)
            spectrometer.get_calibrated_l()  # ch18 (940nm)
        ]

        # Create a list of the new channel names
        channel_names = [f"AS7265X_ch{i+1}" for i in range(18)]

        # Combine them into a dictionary
        spectral_data = dict(zip(channel_names, sensor_values))

        # --- KEY CHANGE ---
        # The dashboard and data model expect the 18-channel raw data.
        # Do NOT return placeholder keys for "WHC Index", etc.
        return spectral_data

    except (UninitializedAS7265XError, Exception) as e:
        # Handle failure by printing a warning and returning placeholders/zeros
        if not 'printed_as7265x_error' in globals():
            print(f"Warning: AS7265x sensor failed. {e}. Using placeholders.")
            globals()['printed_as7265x_error'] = True

        # Return zeros for all 18 channels so data model doesn't crash
        return AS7265X_PLACEHOLDER_ZEROS

# ====================================================================
## ✨ Sensor Fusion Function (Public API)
# ====================================================================

def read_all_sensors():
    """
    Consolidates all sensor readings (AHT20, eNose, AS7265x) into a single dictionary.
    """
    
    try:
        temp_hum_data = read_aht20()
        mq_data = read_enose()
    except (UninitializedAHT20Error, UninitializedENoseError) as e:
        # Halt execution if critical temperature/eNose data is unavailable
        print(f"Hardware Error in Fusion: {e}")
        raise
        
    # Spectrometer reading (handles its own errors gracefully)
    spec_data = read_spectrometer()

    # Combine all readings into a single dictionary
    raw_readings = {
        **temp_hum_data,
        **mq_data,
        **spec_data
    }
    
    return raw_readings

# ====================================================================
## 🏃‍♂️ ML Data Collection Script (for direct execution)
# ====================================================================
#
#  This section is from your new code.
#  Run this file directly (python as7265x.py) to collect data.
#
# ====================================================================

# File to store ML-ready data
CSV_FILE = "as7265x_data.csv"

def runExample(label=None, sample_delay=1.0):
    print("\nQwiic Spectral Triad Example - ML Data Collection\n")

    # Use a new, local instance of the sensor for this script
    myAS7265x = qwiic_as7265x.QwiicAS7265x()

    if not myAS7265x.is_connected():
        print("Device not connected. Check connection.", file=sys.stderr)
        return
    
    if not myAS7265x.begin():
        print("Unable to initialize AS7265x. Check connection.", file=sys.stderr)
        return
    
    myAS7265x.enable_bulb(0) # 0 = White LED

    # Column headers for CSV
    headers = [
        "A_410nm", "B_435nm", "C_460nm", "D_485nm", "E_510nm", "F_535nm",
        "G_560nm", "H_585nm", "R_610nm", "I_645nm", "S_680nm", "J_705nm",
        # --- FIX: Added missing quotation mark ---
        "T_730nm", "U_760nm", "V_810nm", "W_860nm", "K_900nm", "L_940nm"
    ]
    if label is not None:
        headers.append("label")

    # Open CSV file in append mode
    with open(CSV_FILE, mode='a', newline='') as file:
        writer = csv.writer(file)
        # Write header only if file is empty
        if file.tell() == 0:
            writer.writerow(headers)

        print(f"Collecting data for label: '{label}' into {CSV_FILE}...")
        print("Press Ctrl+C to stop.")
        
        while True:
            myAS7265x.take_measurements()
            data_row = [
                myAS7265x.get_calibrated_a(),
                # --- FIX: Corrected variable name typo ---
                myAS7265x.get_calibrated_b(),
                myAS7265x.get_calibrated_c(),
                myAS7265x.get_calibrated_d(),
                myAS7265x.get_calibrated_e(),
                myAS7265x.get_calibrated_f(),
                myAS7265x.get_calibrated_g(),
                myAS7265x.get_calibrated_h(),
                myAS7265x.get_calibrated_r(),
                myAS7265x.get_calibrated_i(),
                myAS7265x.get_calibrated_s(),
                myAS7265x.get_calibrated_j(),
                myAS7265x.get_calibrated_t(),
                myAS7265x.get_calibrated_u(),
                myAS7265x.get_calibrated_v(),
                myAS7265x.get_calibrated_w(),
                myAS7265x.get_calibrated_k(),
                myAS7265x.get_calibrated_l()
            ]
            if label is not None:
                data_row.append(label)

            writer.writerow(data_row)
            print(f"Wrote row: {data_row}")
            time.sleep(sample_delay) # Delay between samples

if __name__ == '__main__':
    try:
        # Optional: add a label for supervised ML (e.g., "healthy" or "diseased")
        # You might want to get this from sys.argv for more flexibility
        data_label = "healthy"
        print(f"Starting data collection. Label: '{data_label}'")
        runExample(label=data_label, sample_delay=1.0)
        
    except (KeyboardInterrupt, SystemExit):
        print("\nData collection stopped.")
        # Turn off LED on exit
        try:
            sensor = qwiic_as7265x.QwiicAS7265x()
            if sensor.is_connected():
                sensor.begin()
                sensor.disable_bulb(0) # 0 = White LED
                print("ML script exit: AS7265x White LED is OFF.")
        except Exception as e:
            print(f"ML script exit: Error turning off LED: {e}")
        sys.exit(0)