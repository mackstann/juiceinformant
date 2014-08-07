import collections, datetime, itertools, sys, time

from Adafruit_I2C import Adafruit_I2C

from util import timestamp_to_base64

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

    def __init__(self):
        self.i2c = Adafruit_I2C(TSL2561.ADDR_FLOAT)
        self.winsize = 12
        self.window = collections.deque([], self.winsize)

        self.poweron()
        self.i2c.write8(TSL2561.COMMAND_BIT|TSL2561.REGISTER_TIMING, TSL2561.GAIN_1X|TSL2561.INTEGRATIONTIME_13MS)
        self.poweroff()

    def poweron(self):
        self.i2c.write8(TSL2561.COMMAND_BIT|TSL2561.REGISTER_CONTROL, TSL2561.CONTROL_POWERON)

    def poweroff(self):
        self.i2c.write8(TSL2561.COMMAND_BIT|TSL2561.REGISTER_CONTROL, TSL2561.CONTROL_POWEROFF)

    def check_state(self):
        # this should check the photo sensor and return True if it senses that the
        # LED is on, otherwise return False.

        self.poweron()
        time.sleep(0.0137)
        ir = self.i2c.reverseByteOrder(
                self.i2c.readU16(
                    TSL2561.COMMAND_BIT|TSL2561.WORD_BIT|TSL2561.REGISTER_CHAN1_LOW))
        self.poweroff()

        self.window.append((ir, time.time()))
        spiking = find_spike(ir, self.window)

        return time.time(), ir, spiking


# we are looking for a spike that looks something like this:
#
# . . . . . . . . . . . .
# . . . . o o o o . . . .
# . . . . . . . . . . . .
# . . . . . . . . . . . .
# . . . . . . . . . . . .
# . . . . . . . . . . . .
# . . . o . . . . . . . .
# . . . . . . . . . . . .
# . . . . . . . . . . . .
# . . . . . . . . . . . .
# . . . . . . . . o . . .
# . . . . . . . . . . . .
# . . . . . . . . . . . .
# o o o . . . . . . o o o
#
# x axis is time (~14ms ticks) and y axis is IR sensor value.


def spike_range(ir):
    """
    at night, when ir is normally about 0, lo=12
    during daytime, when ir is normally about 60, lo=12.75
    during direct sunlight, when ir is normally about 160, lo=14
    """
    return 10.5, 22


def mode(vals):
    return collections.Counter(vals).most_common(1)[0][0]


def find_spike(ir, window):
    lowest = min(window)[0]
    normalized_window = [ (x-lowest, t) for x, t in window ]
    # lowest value is now 0; all other values have been decreased by the same
    # amount needed to do that.

    spike_lo, spike_hi = spike_range(ir)

    #print normalized_window
    # find values within the spike range
    possible_spike_vals = ''.join([ 'y' if spike_lo <= x <= spike_hi else 'n' for x, t in normalized_window ])
    #print ir
    #print spike_lo, spike_hi
    #print possible_spike_vals

    if 'yyy' not in possible_spike_vals:
        #print 'reason 1'
        # spike should be at least 3 elements long.
        return False

    if 'yyyyyyy' in possible_spike_vals:
        #print 'reason 2'
        # spike can't be more than 6 elements long.
        return False

    spike_start = possible_spike_vals.index('yyy')
    if spike_start < 3:
        #print 'reason 3'
        # we need to have at least 3 non-spike elements before the spike.
        return False

    spike_end = possible_spike_vals.find('n', spike_start)
    if spike_end == -1:
        #print 'reason 4'
        # if we haven't seen the end of the spike then we can't make sense
        # of it yet.
        return False

    if spike_end - spike_start not in (3, 4, 5, 6):
        #print 'reason 5'
        # spike must be 3-6 elements long
        return False

    if spike_end > len(window)-3:
        #print 'reason 6'
        # we need to have at least 3 non-spike elements after the spike.
        return False

    vals = sorted([ x for x, t in list(window)[spike_start:spike_end] ])
    md = mode(vals)
    #print "mode is", md
    if vals.count(md) < 2:
        #print 'reason 7'
        # there must be at least 2 identical values in the spike
        return False

    times = [ t for x, t in list(window)[spike_start:spike_end] ]
    if max(times) - min(times) >= 0.1:
        #print 'reason 8'
        # spike must be less than 0.1s long.
        return False

    return True


def run():
    tsl = TSL2561()
    was_spiking = False

    with open("blink-log", "a") as f:
        while True:
            ts, ir, state = tsl.check_state()
            if state == True and was_spiking == False: # mark the beginning of the blink
                print 'blink'
                f.write(timestamp_to_base64(ts) + "\n") # deciseconds
                f.flush()
            was_spiking = state


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        pass
