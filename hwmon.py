import time

from Adafruit_I2C import Adafruit_I2C

from util import timestamp_to_base64

def check_state(i2c):
    # this should check the photo sensor and return True if it senses that the
    # LED is on, otherwise return False.
    return time.time(), i2c.reverseByteOrder(i2c.readU16(0x8E)) > 30

def run():
    INTEGRATIONTIME_13MS      = 0x00 # 13.7ms
    INTEGRATIONTIME_101MS     = 0x01 # 101ms
    INTEGRATIONTIME_402MS     = 0x02 # 402ms
    GAIN_1X                   = 0x00 # No gain
    GAIN_16X                  = 0x10 # 16x gain
    i2c = Adafruit_I2C(0x39)
    i2c.write8(0x80, 0x03)     # enable the device
    i2c.write8(0x81, GAIN_16X|INTEGRATIONTIME_13MS)

    f = open("blink-log", "a")
    last_state = False
    while True:
        ts, state = check_state(i2c)
        if state == True and last_state == False: # mark the beginning of the blink
            f.write(timestamp_to_base64(ts) + "\n") # deciseconds
            f.flush()

        time.sleep(0.01)
        last_state = state

if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        pass
