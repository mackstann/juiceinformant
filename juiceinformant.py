from redis import StrictRedis
from flask import Flask, request, jsonify, send_from_directory

from util import get_local_datetime_from_timestamp, format

import os, datetime, hashlib, itertools


# this configurability is not quite done yet
charts = [
    {'title': '10m', 'seconds': 60*10, 'resolution': 1000},
    {'title': '24h', 'seconds': 60*60*24, 'resolution': 300},
    {'title': '7d', 'seconds': 60*60*24*7, 'resolution': 500},
]

app = Flask(__name__, static_url_path='')
redis = StrictRedis()

base_dir = os.path.dirname(os.path.abspath(__file__))

with open(os.path.dirname(os.path.abspath(__file__)) + '/secret') as f:
    secret = f.read().strip()

@app.route("/", methods=["GET"])
def index():
    return file('index.html').read()

@app.route('/static/<path:filename>')
def static_file(filename):
    return send_from_directory(base_dir + '/static', filename)

@app.route("/logdata/latest-entry", methods=["GET"])
def latest_entry():
    keys = sorted([ x for x in redis.keys('blinks-*') if not x.startswith('blinks-x') ])[-1:] # HERE not really though
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
    latest = float(latest_entry()[0])

    print 'query existing Wh counts...'
    for ts in timestamps:
        pacific_dt = get_local_datetime_from_timestamp(float(ts))
        day = pacific_dt.strftime("%Y-%m-%d")
        for modulo in [ c['modulo'] for c in charts ]:
            if modulo not in (0, 1):
                binned_timestamp = int(float(ts)) - int(float(ts)) % modulo
                key = 'blinks-x{0}-'.format(modulo) + day
                pipe.zrangebyscore(key, binned_timestamp, binned_timestamp, withscores=True)

    print 'execute...'
    existing = pipe.execute()
    print 'done.'

    print 'save data...'
    pipe = redis.pipeline()
    i = 0
    for ts in timestamps:
        pacific_dt = get_local_datetime_from_timestamp(float(ts))
        day = pacific_dt.strftime("%Y-%m-%d")
        for modulo in [ c['modulo'] for c in charts ]:
            if modulo in (0, 1):
                pipe.zadd('blinks-' + day, ts, ts + " 1")
            else:
                binned_timestamp = int(float(ts)) - int(float(ts)) % modulo
                key = 'blinks-x{0}-'.format(modulo) + day
                wh_count = 1
                if existing[i]:
                    wh_count = int(existing[i][0][0].split()[1]) + 1
                    pipe.zrem(key, existing[i][0][0])
                pipe.zadd(key, binned_timestamp, str(binned_timestamp) + ' ' + str(wh_count))
                i += 1

        wh += 1

    pipe.incrby('wh-' + day, wh)
    print 'execute...'
    pipe.execute()
    print 'done.'

    # TODO:
    # * delete blinks older than 10m
    # * delete blinks-x100 older than 7d

    return '', 204

for chart in charts:
    # modulo of 0 or 1 means every blink is recorded discretely.
    #
    # modulo of 2 or more means blinks are aggregated into every N second bins.
    # this is useful on longer time spans as it greatly reduces the number of
    # records to churn through. it cuts down the level of detail to what is
    # necessary (given the resolution requested), and no more.
    chart['modulo'] = int(chart['seconds']/float(chart['resolution']))

@app.route("/logdata/cubism/start=<float:start>/stop=<float:stop>/title=<title>", methods=["GET"])
def cubism(start, stop, title):
    # get blinks from days other than today
    start_day = get_local_datetime_from_timestamp(start/1000.0).date()
    stop_day = get_local_datetime_from_timestamp(stop/1000.0).date()

    keys = []
    prefix = 'blinks-'
    # HERE
    chart = [ c for c in charts if c['title'] == title][0]

    if chart['modulo'] != 0:
        prefix += 'x' + str(chart['modulo']) + '-'
    print prefix

    while start_day <= stop_day:
        keys.append(prefix + start_day.strftime("%Y-%m-%d"))
        start_day += datetime.timedelta(days=1)

    records = list(itertools.chain(*(
        redis.zrangebyscore(key,
            start/1000.0 - ((stop-start)*0.05)/1000.0,# this might need to be sloppier on short time spans. and take modulo into account instead of stop-start.
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
    app.run(host='0.0.0.0', port=5000, threaded=True)

