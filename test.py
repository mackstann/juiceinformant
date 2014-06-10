#!/usr/bin/env python

import datetime, sys, time
from Adafruit_I2C import Adafruit_I2C

class TSL2561:
    ADDR_FLOAT = 0x39 # Default address (pin left floating)

    COMMAND_BIT = 0x80 # Must be 1
    WORD_BIT    = 0x20 # 1 = read/write word (rather than byte)

    CONTROL_POWERON  = 0x03
    CONTROL_POWEROFF = 0x00

    REGISTER_CONTROL          = 0x00
    REGISTER_TIMING           = 0x01
    REGISTER_CHAN0_LOW        = 0x0C
    REGISTER_CHAN1_LOW        = 0x0E

    INTEGRATIONTIME_13MS      = 0x00 # 13.7ms
    GAIN_1X                   = 0x00 # No gain

def poweron(i2c):
    i2c.write8(TSL2561.COMMAND_BIT|TSL2561.REGISTER_CONTROL, TSL2561.CONTROL_POWERON)

def poweroff(i2c):
    i2c.write8(TSL2561.COMMAND_BIT|TSL2561.REGISTER_CONTROL, TSL2561.CONTROL_POWEROFF)

i2c = Adafruit_I2C(TSL2561.ADDR_FLOAT)
poweron(i2c)
i2c.write8(TSL2561.COMMAND_BIT|TSL2561.REGISTER_TIMING, TSL2561.GAIN_1X|TSL2561.INTEGRATIONTIME_13MS)
poweroff(i2c)

while 1:
    poweron(i2c)
    time.sleep(0.014)
    broadband = i2c.reverseByteOrder(i2c.readU16(TSL2561.COMMAND_BIT|TSL2561.WORD_BIT|TSL2561.REGISTER_CHAN0_LOW))
    ir = i2c.reverseByteOrder(i2c.readU16(TSL2561.COMMAND_BIT|TSL2561.WORD_BIT|TSL2561.REGISTER_CHAN1_LOW))
    poweroff(i2c)

    background = max(0, broadband - ir)
    isolated_ir = ir - background*2
    blink = isolated_ir >= 10

    print '{},{},{},{},{},{}'.format(datetime.datetime.now().isoformat(), broadband, ir, background, isolated_ir, 10 if blink else 0)
    sys.stdout.flush()
