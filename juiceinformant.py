from redis import StrictRedis
from flask import Flask, request, Response, send_from_directory, jsonify

from util import get_local_datetime_from_timestamp, format

import os, datetime, hashlib, itertools, urllib2, sys, time


charts = [
    {'title': '10m', 'seconds': 60*10, 'resolution': 1000},
    {'title': '24h', 'seconds': 60*60*24, 'resolution': 1000},
    {'title': '7d', 'seconds': 60*60*24*7, 'resolution': 1000},
]

app = Flask(__name__, static_url_path='')
redis = None

class Cache(object):
    def __init__(self):
        self.data = {}
        self.update_times = {}

    def get(self, key, update_time, data_func):
        if update_time > self.update_times.get(key, 0):
            self.data[key] = data_func()
            self.update_times[key] = update_time
        return self.data[key]

cache = Cache()

base_dir = os.path.dirname(os.path.abspath(__file__))

with open(os.path.dirname(os.path.abspath(__file__)) + '/secret') as f:
    secret = f.read().strip()

@app.route("/", methods=["GET"])
def index():
    return file('index.html').read()

@app.route("/hdd", methods=["GET"])
def hdd():
    return jsonify(cache.get('hdd', float(redis.get('hdd-timestamp')), lambda: redis.hgetall('hdd')))

@app.route("/cdd", methods=["GET"])
def cdd():
    return jsonify(cache.get('cdd', float(redis.get('cdd-timestamp')), lambda: redis.hgetall('cdd')))

@app.route('/static/<path:filename>')
def static_file(filename):
    return send_from_directory(base_dir + '/static', filename)

@app.route("/logdata/latest-entry", methods=["GET"])
def latest_entry():
    keys = sorted([ x for x in redis.keys('blinks-*') if not x.startswith('blinks-x') ])[-1:]
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

    pipe = redis.pipeline(transaction=False)
    wh = 0
    latest = float(latest_entry()[0])

    print 'query existing Wh counts...'
    ranges = {}
    for ts in timestamps:
        pacific_dt = get_local_datetime_from_timestamp(float(ts))
        day = pacific_dt.strftime("%Y-%m-%d")
        for modulo in [ c['modulo'] for c in charts ]:
            if modulo not in (0, 1):
                binned_timestamp = int(float(ts)) - int(float(ts)) % modulo
                key = 'blinks-x{0}-'.format(modulo) + day
                ranges.setdefault(key, []).append(binned_timestamp)

    for key in ranges:
        ranges[key] = sorted(set(ranges[key])) # eliminate duplicates, keep it as a sorted list
        for binned_timestamp in ranges[key]:
            pipe.zrangebyscore(key, binned_timestamp, binned_timestamp)

    results = iter(pipe.execute())
    cache = {}
    for key in ranges:
        for binned_timestamp in ranges[key]:
            result = results.next()
            if result:
                #print result
                cache[(key, binned_timestamp)] = int(result[0].split()[1])
            else:
                cache[(key, binned_timestamp)] = 0

    print 'save data...'
    pipe = redis.pipeline()
    delete_prev_value = {}
    for ts in timestamps:
        pacific_dt = get_local_datetime_from_timestamp(float(ts))
        day = pacific_dt.strftime("%Y-%m-%d")
        for modulo in [ c['modulo'] for c in charts ]:
            if modulo in (0, 1):
                pipe.zadd('blinks-' + day, ts, ts + " 1")
            else:
                binned_timestamp = int(float(ts)) - int(float(ts)) % modulo
                key = 'blinks-x{0}-'.format(modulo) + day
                #print key, binned_timestamp, 'increment cache from {} to {}'.format(cache[(key, binned_timestamp)], cache[(key, binned_timestamp)]+1)
                if cache[(key, binned_timestamp)] != 0 and (key, binned_timestamp) not in delete_prev_value:
                    # first time we've come across this one, save its old value so we can delete it from redis.
                    delete_prev_value[(key, binned_timestamp)] = cache[(key, binned_timestamp)]
                cache[(key, binned_timestamp)] += 1
        wh += 1

    for (key, binned_timestamp) in cache:
        if (key, binned_timestamp) in delete_prev_value:
            #print 'zrem', key, str(binned_timestamp) + ' ' + str(delete_prev_value[(key, binned_timestamp)])
            pipe.zrem(key, str(binned_timestamp) + ' ' + str(delete_prev_value[(key, binned_timestamp)]))
            del delete_prev_value[(key, binned_timestamp)]
        #print 'zadd', key, binned_timestamp, str(binned_timestamp) + ' ' + str(cache[(key, binned_timestamp)])
        pipe.zadd(key, binned_timestamp, str(binned_timestamp) + ' ' + str(cache[(key, binned_timestamp)]))

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

    if chart['modulo'] not in (1, 0):
        prefix += 'x' + str(chart['modulo']) + '-'
    print 'prefix:', prefix

    while start_day <= stop_day:
        keys.append(prefix + start_day.strftime("%Y-%m-%d"))
        start_day += datetime.timedelta(days=1)

    print 'keys:', keys
    #import time
    #t = time.time()
    pipe = redis.pipeline(transaction=False)
    for key in keys:
        pipe.zrangebyscore(key,
            start/1000.0 - ((stop-start)*0.05)/1000.0,# this might need to be sloppier on short time spans. and take modulo into account instead of stop-start.
            stop/1000.0)
    #t2 = time.time()
    #print t2-t
    records = itertools.chain(*pipe.execute())
    #print len(keys), keys
    #print 'len records:', len(records)
    #t3 = time.time()
    #print t3-t2
    # return them unsorted
    data = 'Blah\n' + '\n'.join(records) + '\n'
    #t4 = time.time()
    #print t4-t3

    response = Response()
    response.data = data
    return response

@app.route("/logdata/calendar", methods=["GET"])
def calendar():
    cal_keys = redis.keys('wh-*')
    cal_keys.sort()
    vals = redis.mget(cal_keys)
    response = "Date,Wh\n"
    for i, key in enumerate(cal_keys):
        response += key[3:] + "," + vals[i] + "\n"
    return response

def update_degree_days(type):
    assert type in ('hdd', 'cdd')

    # use this file to find your climate division ID (last column):
    # ftp://ftp.cpc.ncep.noaa.gov/htdocs/degree_days/weighted/daily_data/regions/ClimateDivisions.txt
    division_id = '3502'

    import datetime
    year = datetime.date.today().year
    url_template = 'ftp://ftp.cpc.ncep.noaa.gov/htdocs/degree_days/weighted/daily_data/{}/ClimateDivisions.{}.txt'
    url_type = 'Heating' if type == 'hdd' else 'Cooling'
    try:
        url = url_template.format(year, url_type)
        print 'downloading', url
        f = urllib2.urlopen(url)
    except urllib2.URLError as e:
        if 'Failed to change directory' in str(e):
            # it's probably January 1 and this year's file isn't out yet.
            url = url_template.format(year-1, url_type)
            print 'downloading', url
            f = urllib2.urlopen(url)
        else:
            raise
    print 'processing...'
    lines = f.read().splitlines()
    dates = [ x[:4] + '-' + x[4:6] + '-' + x[6:] for x in lines[3].split('|')[1:] ]
    degree_days = [ l for l in lines if l.startswith(division_id + '|') ][0].split('|')[1:]
    degree_days_by_date = dict(zip(dates, degree_days))

    pipe = redis.pipeline(transaction=False)
    for date, dd in degree_days_by_date.items():
        pipe.hset(type, date, dd)
    pipe.set(type + '-timestamp', time.time())
    pipe.execute()
    print 'done...'

def update_all_degree_days():
    update_degree_days('hdd')
    update_degree_days('cdd')


def prune():
    seconds_ago = max([ c['seconds'] for c in charts ])
    cutoff = datetime.datetime.now() - datetime.timedelta(seconds=seconds_ago + 24*60*60)

    for key in redis.keys('blinks-*'):
        if key.startswith('blinks-x'):
            date_str = key.split('-', 2)[-1]
        else:
            date_str = key.split('-', 1)[-1]

        year, month, day = map(int, date_str.split('-'))
        date = datetime.datetime(year, month, day, 0, 0, 0)

        if date < cutoff:
            print 'delete', key
            redis.delete(key)
        else:
            print 'keep  ', key


if __name__ == "__main__":
    app.debug = True

    if '--alt' in sys.argv: # hack
        redis = StrictRedis(db=1)
    else:
        redis = StrictRedis()

    if '--update-dd' in sys.argv:
        update_all_degree_days()
        raise SystemExit

    if '--prune' in sys.argv:
        prune()
        raise SystemExit

    if '--alt' in sys.argv: # hack
        app.run(host='0.0.0.0', port=7000, threaded=True)
    else:
        app.run(host='0.0.0.0', port=5000, threaded=True)
else: # uwsgi
    redis = StrictRedis()
