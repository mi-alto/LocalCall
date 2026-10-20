"""Bounded native-messaging bridge. Never accepts commands or paths from the browser."""
import fcntl
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
HOST = 'org.localcall.launcher'

def read_message(stream):
    header = stream.read(4)
    if len(header) != 4:
        raise ValueError('Missing message header')
    size = struct.unpack('@I', header)[0]
    if not 0 < size <= 4096:
        raise ValueError('Invalid message size')
    body = stream.read(size)
    if len(body) != size:
        raise ValueError('Truncated message')
    return json.loads(body)

def write_message(stream, value):
    body = json.dumps(value).encode('utf-8')
    stream.write(struct.pack('@I', len(body)) + body)
    stream.flush()

def ready(root, port=8765):
    try:
        token = (root/'data/token').read_text().strip()
        req = urllib.request.Request(f'http://127.0.0.1:{port}/api/status', headers={'Authorization': 'Bearer '+token})
        # Never route the local token through an environment proxy.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req, timeout=1) as response:
            status = json.load(response)
        if status.get('version') != '0.3.0':
            raise RuntimeError('Chiudi la precedente versione di LocalCall, poi riprova.')
        return token
    except (OSError, ValueError):
        return None

def start_backend(root=ROOT, port=8765):
    data = root/'data'
    data.mkdir(mode=0o700, exist_ok=True)
    os.chmod(data, 0o700)
    with (data/'.launcher.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        token = ready(root, port)
        if token:
            return {'ok': True, 'token': token}
        env = dict(os.environ)
        env['PATH'] = '/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin'
        with (data/'backend.log').open('ab') as log:
            child = subprocess.Popen([sys.executable, '-m', 'localcall.server', '--port', str(port)], cwd=root,
                                     env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                     start_new_session=True, close_fds=True)
        for _ in range(100):
            token = ready(root, port)
            if token:
                return {'ok': True, 'token': token}
            if child.poll() is not None:
                break
            time.sleep(0.1)
        raise RuntimeError('Avvio non riuscito. Controlla data/backend.log oppure avvia LocalCall dal Finder.')

def main():
    os.umask(0o077)
    try:
        config = json.loads((ROOT/'data/native-origins.json').read_text())
        if len(sys.argv) != 2 or sys.argv[1] not in config:
            raise ValueError('Origin not authorized')
        if read_message(sys.stdin.buffer) != {'action': 'start'}:
            raise ValueError('Unsupported action')
        result = start_backend()
    except Exception as error:
        result = {'error': str(error)}
    write_message(sys.stdout.buffer, result)

if __name__ == '__main__':
    main()
