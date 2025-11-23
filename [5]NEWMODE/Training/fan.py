#!/usr/bin/env python3

"""
Controls a ventilation fan using LGPIO.
Reads 4 MQ sensors from ADS1115 ADC.
Fan runs until all sensors return to baseline threshold.
"""

import lgpio
import time
import board
import busio

from adafruit_ads1x15.ads1115 import ADS1115
from adafruit_ads1x15.analog_in import AnalogIn

# --- Configuration ---
FAN_PIN = 27
PWM_FREQ = 100

BASELINE_MQ137 = 1.2197
BASELINE_MQ135 = 0.16
BASELINE_MQ4   = 0.3489 
BASELINE_MQ3   = 0.6052

TOLERANCE = 0.02
POLL_INTERVAL = 2
# --- End Configuration ---


def setup_gpio():
    try:
        h = lgpio.gpiochip_open(0)
        lgpio.gpio_claim_output(h, FAN_PIN)
        lgpio.tx_pwm(h, FAN_PIN, PWM_FREQ, 0)

        print(f"lgpio handle opened. GPIO {FAN_PIN} initialized for PWM output.")
        return h

    except Exception as e:
        print(f"\nError initializing lgpio: {e}")
        return None


def setup_ads1115():
    """Initializes ADS1115 and returns channels."""
    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        ads = ADS1115(i2c)
        ads.gain = 1

        # Use channel *numbers* (compatible with all versions)
        mq137_channel = AnalogIn(ads, 0)  # A0
        mq135_channel = AnalogIn(ads, 1)  # A1
        mq3_channel   = AnalogIn(ads, 2)  # A2
        mq4_channel   = AnalogIn(ads, 3)  # A3

        print("ADS1115 ADC initialized.")
        print("Sensor mapping: A0=MQ137, A1=MQ135, A2=MQ3, A3=MQ4")

        return {
            'mq137': mq137_channel,
            'mq135': mq135_channel,
            'mq4': mq4_channel,
            'mq3': mq3_channel
        }

    except Exception as e:
        print(f"ADS1115 Setup Error: {e}")
        return None


def main_loop(sensors, thresholds):
    try:
        v_mq137 = sensors['mq137'].voltage
        v_mq135 = sensors['mq135'].voltage
        v_mq4   = sensors['mq4'].voltage
        v_mq3   = sensors['mq3'].voltage

        print("\n--- Sensor Readings ---")
        print(f"MQ-137: {v_mq137:6.4f} V  (<= {thresholds['mq137']:.4f})")
        print(f"MQ-135: {v_mq135:6.4f} V  (<= {thresholds['mq135']:.4f})")
        print(f"MQ-4:   {v_mq4:6.4f} V  (<= {thresholds['mq4']:.4f})")
        print(f"MQ-3:   {v_mq3:6.4f} V  (<= {thresholds['mq3']:.4f})")
        print("-----------------------")

        if (v_mq137 <= thresholds['mq137'] and
            v_mq135 <= thresholds['mq135'] and
            v_mq4   <= thresholds['mq4'] and
            v_mq3   <= thresholds['mq3']):

            print("\nSUCCESS: All sensors returned to baseline.")
            return True

        print("STATUS: Above-baseline. Ventilation running...")
        return False

    except Exception as e:
        print(f"Sensor read error: {e}")
        return False


def cleanup_gpio(h):
    print("Cleaning up GPIO...")
    if h:
        try:
            lgpio.tx_pwm(h, FAN_PIN, PWM_FREQ, 0)
            lgpio.gpio_free(h, FAN_PIN)
            lgpio.gpiochip_close(h)
            print("GPIO cleanup done. Fan OFF.")
        except Exception as e:
            print(f"Cleanup error: {e}")


if __name__ == "__main__":
    gpio_handle = None

    try:
        gpio_handle = setup_gpio()
        if gpio_handle is None:
            raise RuntimeError("Failed to init lgpio.")

        sensors = setup_ads1115()
        if sensors is None:
            raise RuntimeError("Failed to init ADS1115.")

        thresholds = {
            'mq137': BASELINE_MQ137 * (1 + TOLERANCE),
            'mq135': BASELINE_MQ135 * (1 + TOLERANCE),
            'mq4':   BASELINE_MQ4   * (1 + TOLERANCE),
            'mq3':   BASELINE_MQ3   * (1 + TOLERANCE)
        }

        print(f"\nTurning ON fan (GPIO {FAN_PIN})...")
        lgpio.tx_pwm(gpio_handle, FAN_PIN, PWM_FREQ, 100)

        print("Ventilation active. Monitoring sensors...")

        while True:
            if main_loop(sensors, thresholds):
                break
            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        print("\nUser interrupted.")

    except Exception as e:
        print(f"\nFatal error: {e}")

    finally:
        cleanup_gpio(gpio_handle)
        print("Script terminated.")
