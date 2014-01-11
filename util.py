import pytz

import datetime, struct, math, os

# an arbitrary recent time that cuts down on the amount of redundant data we
# store in blink-log (which takes up precious RPi disk space)
offset = 1380610800

# precision of timestamps. going from centiseconds to milliseconds makes the
# chart noticeably less blocky, but anything beyond milliseconds makes no
# noticeable difference.
second_divisor = 1000.0

decimal_digits = int(math.log10(second_divisor))
format_string = '{0:0.' + str(decimal_digits) + 'f}'

with open(os.path.dirname(os.path.abspath(__file__)) + '/secret') as secret_file:
    secret = secret_file.read().strip()

def format(ts):
    return format_string.format(ts)

def timestamp_to_base64(ts):
    return struct.pack('!Q', int((ts - offset)*second_divisor)).lstrip(chr(0)).encode('base64').rstrip('=\n')

def base64_to_timestamp(s):
    bytes = (s + '=' * (len(s) % 4) + '\n').decode('base64')
    bytes = chr(0) * (8 - len(bytes)) + bytes
    return struct.unpack('!Q', bytes)[0]/second_divisor + offset

def get_local_datetime_from_timestamp(ts):
    utc_dt = datetime.datetime.utcfromtimestamp(ts).replace(tzinfo=pytz.utc)
    pacific_tz = pytz.timezone('America/Los_Angeles')
    pacific_dt = pacific_tz.normalize(utc_dt.astimezone(pacific_tz))
    return pacific_dt

