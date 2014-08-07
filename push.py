import sys, time, requests, select, hashlib, os

from util import base64_to_timestamp, format, secret

def send_batch(server_host, secret, batch):
    body = hashlib.sha256(secret + format(batch[0])).hexdigest() + "\n" + '\n'.join(map(format, batch))
    while True:
        try:
            r = requests.post('http://{0}/logdata'.format(server_host), data=body, timeout=60)
        except requests.exceptions.RequestException, e:
            print >>sys.stderr, e
            time.sleep(1)
            continue
        else:
            if r.status_code >= 200 and r.status_code <= 204:
                print "Sent batch[{0}]: {1}...{2}".format(len(batch), batch[0], batch[-1])
                return
            print "HTTP {0}".format(r.status_code)
            continue

def get_remote_position(server_host):
    while True:
        try:
            r = requests.get('http://{0}/logdata/latest-entry'.format(server_host), timeout=5)
        except requests.exceptions.RequestException, e:
            print >>sys.stderr, e
            time.sleep(1)
            continue
        else:
            if r.status_code >= 200 and r.status_code <= 204:
                return float(r.text)
            print "HTTP {0}".format(r.status_code)
            continue

def run(server_host):
    batch = []
    remote_pos = get_remote_position(server_host)
    size = os.path.getsize('blink-log')
    f = file('blink-log', 'r')

    # catch up
    closest_match = None
    pos = 0
    # do a binary search to get close to the current position in the log. just
    # do it for 20 iterations and we'll be close enough.
    for i in range(20):
        chunk = f.read(30)
        pos += chunk.index('\n')
        f.seek(pos)
        parts = chunk.split()
        if len(parts) < 2:
            continue
        ts = base64_to_timestamp(parts[1])
        if ts < remote_pos:
            pos += (size - pos) / 2 # move forward
        elif ts > remote_pos:
            pos /= 2 # move backward
        else:
            break
        f.seek(pos)

    # back up a bit just in case
    f.seek(max(0, pos - 100))

    buf = ''

    # get to the next line beginning
    while True:
        buf += f.read(1)
        if '\n' in buf:
            buf = ''
            break

    while True:
        buf += f.read(1)
        if not buf:
            select.select([f], [], [])
            continue

        if not buf.endswith('\n'):
            continue

        t = base64_to_timestamp(buf.rstrip())
        buf = ''

        if t <= float(remote_pos):
            print '.',
            sys.stdout.flush()
            continue # the server already knows about this blink.

        # submit old timestamps in batches of 1000, but recent ones
        # immediately (batches of 1).
        batch_limit = 1000 if time.time() - t > 60 else 1

        batch.append(t)
        if len(batch) >= batch_limit:
            print 'sending...'
            send_batch(server_host, secret, batch)
            print 'done.'
            remote_pos = batch[-1]
            batch = []

if __name__ == '__main__':
    try:
        run(sys.argv[1])
    except KeyboardInterrupt:
        pass
