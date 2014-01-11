import time, os, random

from util import timestamp_to_base64

def check_state():
    # this should check the photo sensor and return True if it senses that the
    # LED is on, otherwise return False.
    return time.time(), random.random() > 0.5

def run():
    f = open("blink-log", "a")
    last_state = False
    while True:
        ts, state = check_state()
        #if state == True and last_state == False: # mark the beginning of the blink
        f.write(timestamp_to_base64(ts) + "\n") # deciseconds
        f.flush()

        #time.sleep(0.01)
        last_state = state

        # this is just random shit to sleep a period of time that is based on the
        # current minute, the current memory usage, and some more random noise.
        # once actual hardware monitoring is implemented in check_state, this will
        # be thrown away.
        kb = os.popen("free -k | tail -n2 | head -n1 | awk '{print $3}'").read().strip()
        h = float(os.popen("date +%M").read().strip())/25.0
        h += random.random()/80
        v = ((10000000 - int(kb))/10000000.0)*(h+0.5)
        print v
        time.sleep(v)

if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        pass
