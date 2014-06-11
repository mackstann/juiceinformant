#!/usr/bin/env python

import datetime, sys

from hwmon import TSL2561


def run():
    tsl = TSL2561()
    was_spiking = False

    while 1:
        ts, ir, spiking = tsl.check_state()
        blink = spiking and not was_spiking
        was_spiking = spiking

        print '{},{},{}'.format(datetime.datetime.now().isoformat(), ir, 'BLINK' if blink else '')
        sys.stdout.flush()


if __name__ == '__main__':
    try:
        run()
    except KeyboardInterrupt:
        pass
