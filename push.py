import sys, time, requests, select, hashlib

from util import base64_to_timestamp, format, secret

def send_batch(server_host, secret, batch):
    body = hashlib.sha256(secret + format(batch[0])).hexdigest() + "\n" + '\n'.join(map(format, batch))
    while True:
        try:
            r = requests.post('http://{0}/logdata'.format(server_host), data=body, timeout=3)
        except requests.exceptions.RequestException, e:
            print >>sys.stderr, e
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
            r = requests.get('http://{0}/logdata/latest-entry'.format(server_host), timeout=3)
        except requests.exceptions.RequestException, e:
            print >>sys.stderr, e
            continue
        else:
            if r.status_code >= 200 and r.status_code <= 204:
                return float(r.text)
            print "HTTP {0}".format(r.status_code)
            continue

def run(server_host):
    batch = []
    pos = get_remote_position(server_host)
    while True:
        select.select([sys.stdin], [], [])

        t = base64_to_timestamp(sys.stdin.readline().rstrip())

        if t <= float(pos):
            continue # the server already knows about this blink.

        # submit old timestamps in batches of 1000, but recent ones
        # immediately (batches of 1).
        batch_limit = 1000 if time.time() - t > 60 else 1

        batch.append(t)
        if len(batch) >= batch_limit:
            send_batch(server_host, secret, batch)
            pos = batch[-1]
            batch = []

if __name__ == '__main__':
    try:
        run(sys.argv[1])
    except KeyboardInterrupt:
        pass
