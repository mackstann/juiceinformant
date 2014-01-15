import time

from util import timestamp_to_base64

from TSL2561 import TSL2561


tsl = TSL2561()

def check_state():
    # this should check the photo sensor and return True if it senses that the
    # LED is on, otherwise return False.
    maxval = 2**16
    return tsl.readIR() > maxval / 2.0


def run():
    f = open("blink-log", "a")
    last_state = False
    while True:
        ts, state = check_state()
        if state == True and last_state == False: # mark the beginning of the blink
            f.write(timestamp_to_base64(ts) + "\n")
            f.flush()

        last_state = state
        time.sleep(0.01)


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        pass
