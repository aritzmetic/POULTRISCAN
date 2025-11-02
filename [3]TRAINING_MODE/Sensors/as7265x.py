# Sensors/as7265x.py

import sys
import atexit
import csv
import time

# ====================================================================
## 🔌 Sensor Fusion Imports
# ====================================================================

try:
    import qwiic_as7265x
    from Sensors.aht20 import read_aht20, UninitializedAHT20Error
    from Sensors.enose import read_enose, UninitializedENoseError
except ImportError:
    class UninitializedAHT20Error(Exception): pass
    class UninitializedENoseError(Exception): pass
    def read_aht20():
        print("Warning: AHT20 not found (standalone mode?).")
        return {"Temperature": -99, "Humidity": -99}
    def read_enose():
        print("Warning: eNose not found (standalone mode?).")
        return {
            "MQ-137 (Ammonia)": -99, "MQ-135 (Air Quality)": -99,
            "MQ-7 (CO)": -99, "MQ-4 (Methane)": -99
        }
    if 'qwiic_as7265x' not in locals():
        print("FATAL: qwiic_as7265x library not found. Public functions will fail.")
        class DummyQwiic:
            def QwiicAS7265x(self):
                return None
        qwiic_as7265x = DummyQwiic()


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
    """
    def __init__(self, *args):
        pass
    def _raise_error(self):
        raise UninitializedAS7265XError("AS7265x sensor access attempted, but initialization failed. Check wiring and I2C.")
    def begin(self): self._raise_error()
    def is_connected(self): return False
    def take_measurements(self): self._raise_error()
    def enable_bulb(self, led_type): self._raise_error()
    def disable_bulb(self, led_type): self._raise_error()
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


spectrometer = SensorUnavailable()
AS7265X_PLACEHOLDER_ZEROS = {f"AS7265X_ch{i+1}": 0 for i in range(18)}

# ====================================================================
## 💡 Cleanup Function (MODIFIED)
# ====================================================================

def _cleanup_as7265x():
    """Turns off ALL LEDs on application exit."""
    global AS7265X_INITIALIZED, spectrometer
    if AS7265X_INITIALIZED:
        try:
            print("ATEIXT: Shutting down AS7265x LEDs (White, UV, IR)...")
            spectrometer.disable_bulb(0) # White
            spectrometer.disable_bulb(1) # UV
            spectrometer.disable_bulb(2) # IR
            print("ATEIXT: AS7265x LEDs are OFF.")
        except Exception as e:
            print(f"ATEIXT: Error during AS7265x cleanup: {e}")

# ====================================================================
## ⚙️ Hardware Initialization (MODIFIED)
# ====================================================================

try:
    spectrometer = qwiic_as7265x.QwiicAS7265x()

    if not spectrometer.is_connected():
        raise RuntimeError("AS7265x device not connected. Check I2C connection.")
    if not spectrometer.begin():
        raise RuntimeError("Unable to initialize AS7265x sensor.")

    spectrometer.disable_bulb(0) # 0 = White LED
    spectrometer.disable_bulb(1) # 1 = UV LED
    spectrometer.disable_bulb(2) # 2 = IR LED
    
    AS7265X_INITIALIZED = True
    atexit.register(_cleanup_as7265x)
    print("AS7265x spectrometer hardware (Qwiic) initialized successfully (ALL LEDs OFF).")

except (ImportError, RuntimeError, AttributeError) as e: 
    print("-" * 50)
    print(f"AS7265x initialization FAILED: {type(e).__name__}: {e}.")
    print("Ensure I2C is enabled and the 'sparkfun-qwiic-as7265x' library is installed.")
    print("AS7265x readings will now be placeholders.")
    print("-" * 50)
    spectrometer = SensorUnavailable()

# ====================================================================
## 💡 NEW: Public LED Control Functions (MODIFIED)
# ====================================================================

def as_led_on():
    """Turns the AS7265x built-in White LED ON."""
    try:
        spectrometer.enable_bulb(0)
    except Exception as e:
        print(f"Warning: Could not enable AS7265x LED: {e}")

def as_led_off():
    """Turns the AS7265x built-in White LED OFF."""
    try:
        spectrometer.disable_bulb(0)
    except Exception as e:
        print(f"Warning: Could not disable AS7265x LED: {e}")

def as_uv_led_on():
    """Turns the AS7265x built-in UV LED ON."""
    try:
        spectrometer.enable_bulb(1)
    except Exception as e:
        print(f"Warning: Could not enable AS7265x UV LED: {e}")

def as_uv_led_off():
    """Turns the AS7265x built-in UV LED OFF."""
    try:
        spectrometer.disable_bulb(1)
    except Exception as e:
        print(f"Warning: Could not disable AS7265x UV LED: {e}")

def as_ir_led_on():
    """Turns the AS7265x built-in IR LED ON."""
    try:
        spectrometer.enable_bulb(2)
    except Exception as e:
        print(f"Warning: Could not enable AS7265x IR LED: {e}")

def as_ir_led_off():
    """Turns the AS7265x built-in IR LED OFF."""
    try:
        spectrometer.disable_bulb(2)
    except Exception as e:
        print(f"Warning: Could not disable AS7265x IR LED: {e}")

# ====================================================================
## 📊 Spectrometer Reading Function (Unchanged)
# ====================================================================

def read_spectrometer():
    """
    Reads the AS7265x spectrometer and returns the raw 18-channel data.
    The calling function (e.g., TrainingTab) must turn the LED on/off.
    """
    try:
        # Trigger a new measurement
        spectrometer.take_measurements()

        sensor_values = [
            spectrometer.get_calibrated_a(), # ch1
            spectrometer.get_calibrated_b(), # ch2
            spectrometer.get_calibrated_c(), # ch3
            spectrometer.get_calibrated_d(), # ch4
            spectrometer.get_calibrated_e(), # ch5
            spectrometer.get_calibrated_f(), # ch6
            spectrometer.get_calibrated_g(), # ch7
            spectrometer.get_calibrated_h(), # ch8
            spectrometer.get_calibrated_r(), # ch9
            spectrometer.get_calibrated_i(), # ch10
            spectrometer.get_calibrated_s(), # ch11
            spectrometer.get_calibrated_j(), # ch12
            spectrometer.get_calibrated_t(), # ch13
            spectrometer.get_calibrated_u(), # ch14
            spectrometer.get_calibrated_v(), # ch15
            spectrometer.get_calibrated_w(), # ch16
            spectrometer.get_calibrated_k(), # ch17
            spectrometer.get_calibrated_l()  # ch18
        ]
        channel_names = [f"AS7265X_ch{i+1}" for i in range(18)]
        spectral_data = dict(zip(channel_names, sensor_values))
        return spectral_data

    except (UninitializedAS7265XError, Exception) as e:
        if not 'printed_as7265x_error' in globals():
            print(f"Warning: AS7265x sensor failed. {e}. Using placeholders.")
            globals()['printed_as7265x_error'] = True
        return AS7265X_PLACEHOLDER_ZEROS

# ====================================================================
## ✨ Sensor Fusion Function (MODIFIED with 2.0s delay)
# ====================================================================

def read_all_sensors():
    """
    Consolidates all sensor readings (AHT20, eNose, AS7265x) into a single 
    54-channel dictionary for the main Dashboard.
    Uses a 2-second delay for LED stabilization.
    """
    try:
        temp_hum_data = read_aht20()
        mq_data = read_enose()
    except (UninitializedAHT20Error, UninitializedENoseError) as e:
        print(f"Hardware Error in Fusion: {e}")
        raise
        
    # --- MODIFIED: Increased stabilization time to 2.0s ---
    
    # 1. Read White
    as_led_on()
    time.sleep(2.0) # <-- 2-second delay
    spec_data_white = read_spectrometer() # Returns {'AS7265X_ch1': ...}
    as_led_off()
    time.sleep(0.3) # <-- Added short pause for sensor to settle
    
    # 2. Read UV
    as_uv_led_on()
    time.sleep(2.0) # <-- 2-second delay
    spec_data_uv_raw = read_spectrometer() # Returns {'AS7265X_ch1': ...}
    as_uv_led_off()
    time.sleep(0.3) # <-- Added short pause for sensor to settle
    # Rename keys to AS_UV_ch...
    spec_data_uv = {f"AS_UV_ch{i+1}": spec_data_uv_raw.get(f"AS7265X_ch{i+1}", 0) for i in range(18)}

    # 3. Read IR
    as_ir_led_on()
    time.sleep(2.0) # <-- 2-second delay
    spec_data_ir_raw = read_spectrometer() # Returns {'AS7265X_ch1': ...}
    as_ir_led_off()
    # Rename keys to AS_IR_ch...
    spec_data_ir = {f"AS_IR_ch{i+1}": spec_data_ir_raw.get(f"AS7265X_ch{i+1}", 0) for i in range(18)}

    raw_readings = {
        **temp_hum_data,
        **mq_data,
        **spec_data_white,
        **spec_data_uv,
        **spec_data_ir
    }
    
    return raw_readings
    # --- END MODIFICATION ---


# ====================================================================
## 🏃‍♂️ ML Data Collection Script (MODIFIED)
# ====================================================================

CSV_FILE = "as7265x_data.csv"
def runExample(label=None, sample_delay=1.0):
    print("\nQwiic Spectral Triad Example - ML Data Collection\n")
    myAS7265x = qwiic_as7265x.QwiicAS7265x()
    if not myAS7265x.is_connected():
        print("Device not connected. Check connection.", file=sys.stderr)
        return
    if not myAS7265x.begin():
        print("Unable to initialize AS7265x. Check connection.", file=sys.stderr)
        return
    
    myAS7265x.enable_bulb(0) # 0 = White LED

    headers = [
        "A_410nm", "B_435nm", "C_460nm", "D_485nm", "E_510nm", "F_535nm",
        "G_560nm", "H_585nm", "R_610nm", "I_645nm", "S_680nm", "J_705nm",
        "T_730nm", "U_760nm", "V_810nm", "W_860nm", "K_900nm", "L_940nm"
    ]
    if label is not None:
        headers.append("label")
    with open(CSV_FILE, mode='a', newline='') as file:
        writer = csv.writer(file)
        if file.tell() == 0:
            writer.writerow(headers)
        print(f"Collecting data for label: '{label}' into {CSV_FILE}...")
        print("Press Ctrl+C to stop.")
        while True:
            myAS7265x.take_measurements()
            data_row = [
                myAS7265x.get_calibrated_a(),
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
            time.sleep(sample_delay)

if __name__ == '__main__':
    try:
        data_label = "healthy"
        print(f"Starting data collection. Label: '{data_label}'")
        runExample(label=data_label, sample_delay=1.0)
    except (KeyboardInterrupt, SystemExit):
        print("\nData collection stopped.")
        try:
            sensor = qwiic_as7265x.QwiicAS7265x()
            if sensor.is_connected():
                sensor.begin()
                sensor.disable_bulb(0) # White
                sensor.disable_bulb(1) # UV
                sensor.disable_bulb(2) # IR
                print("ML script exit: AS7265x LEDs are OFF.")
        except Exception as e:
            print(f"ML script exit: Error turning off LED: {e}")
        sys.exit(0)