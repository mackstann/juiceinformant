from redis import StrictRedis
from flask import Flask, request, jsonify

from util import get_local_datetime_from_timestamp, format

import os, datetime, hashlib, itertools

app = Flask(__name__)
redis = StrictRedis()

with open(os.path.dirname(os.path.abspath(__file__)) + '/secret') as f:
    secret = f.read().strip()

@app.route("/", methods=["GET"])
def index():
    return file('index.html').read()

@app.route("/logdata/latest-entry", methods=["GET"])
def latest_entry():
    keys = sorted([ x for x in redis.keys('blinks-*') if not x.startswith('blinks-x100') ])
    if not keys:
        return '0', 200
    latest_ts = redis.zrevrangebyscore(keys[0], '+inf', '-inf', withscores=True, start=0, num=1)[0][1]
    return format(latest_ts), 200


@app.route("/logdata", methods=["POST"])
def logdata():
    hash, rest = request.data.split('\n', 1)
    timestamps = rest.split('\n')

    if hashlib.sha256(secret + timestamps[0]).hexdigest() != hash:
        return 'Forbidden', 403

    pipe = redis.pipeline()
    wh = 0
    latest = float(redis.get('latest') or 0)
    for ts in timestamps:
        pacific_dt = get_local_datetime_from_timestamp(float(ts))

        day = pacific_dt.strftime("%Y-%m-%d")

        redis.zadd('blinks-' + day, ts, ts + " 1")

        m = 100
        rounded = int(float(ts)) - int(float(ts)) % m
        key = 'blinks-x{0}-'.format(m) + day
        wh_count = 1
        existing = redis.zrangebyscore(key, rounded, rounded, withscores=True)
        if existing:
            wh_count = int(existing[0][0].split()[1]) + 1
            redis.zrem(key, existing[0][0])
        redis.zadd(key, rounded, str(rounded) + ' ' + str(wh_count))

        if ts > latest:
            latest = ts

        wh += 1

    redis.incrby('wh-' + day, wh)
    redis.set('latest', latest)
    pipe.execute()

    # TODO:
    # * delete blinks older than 10m
    # * delete blinks-x100 older than 7d

    return '', 204

@app.route("/logdata/cubism/start=<float:start>/stop=<float:stop>/step=<float:step>", methods=["GET"])
def cubism(start, stop, step):
    # get blinks from days other than today
    start_day = get_local_datetime_from_timestamp(start/1000.0).date()
    stop_day = get_local_datetime_from_timestamp(stop/1000.0).date()

    keys = []
    prefix = 'blinks-x100-' if step > 10000 else 'blinks-'

    while start_day <= stop_day:
        keys.append(prefix + start_day.strftime("%Y-%m-%d"))
        start_day += datetime.timedelta(days=1)

    records = list(itertools.chain(*(
        redis.zrangebyscore(key,
            start/1000.0 - ((stop-start)*0.05)/1000.0,
            stop/1000.0, withscores=True)
        for key in keys
    )))
    # return them unsorted
    return jsonify({'d': records})

@app.route("/logdata/calendar", methods=["GET"])
def calendar():
    cal_keys = redis.keys('wh-*')
    cal_keys.sort()
    vals = redis.mget(cal_keys)
    response = "Date,Wh\n"
    for i, key in enumerate(cal_keys):
        response += key[3:] + "," + vals[i] + "\n"
    return response

if __name__ == "__main__":
    app.debug = True
    app.run(host='0.0.0.0', port=5000)

