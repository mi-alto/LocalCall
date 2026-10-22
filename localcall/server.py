"""Loopback-only local recorder. No outbound network calls at runtime."""
import argparse
from functools import lru_cache
import fcntl
import math
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from .diarize import fuse, export, constrain_to_speech
from .speaker import recover, group_turns, possible_echo

ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / 'models/ggml-large-v3-turbo-q5_0.bin'
VAD = ROOT / 'models/ggml-silero-v6.2.0.bin'
LOCK = threading.RLock()
POOL = ThreadPoolExecutor(max_workers=1)

class Problem(Exception):
    def __init__(self, code, message):
        self.code, self.message = code, message

def save(path, obj):
    """Atomically commit metadata; callers serialize writes for a given session."""
    tmp = path.with_suffix('.tmp')
    with tmp.open('w') as f:
        json.dump(obj, f, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)

def read(path):
    return json.loads(path.read_text())

def events_from(path):
    if not path.exists():
        return []
    result = []
    with path.open(errors='replace') as f:
        for line in f:
            try:
                event = json.loads(line)
                if isinstance(event.get('t'), (int, float)) and math.isfinite(event['t']) and isinstance(event.get('speakers'), list):
                    result.append(event)
            except (ValueError, AttributeError):
                continue
    return result

@lru_cache(maxsize=256)
def stored_names(path, stamp, size, kind):
    file = Path(path)
    try:
        rows = events_from(file) if kind == 'events' else read(file)
        names = set()
        for row in rows:
            values = row.get('participants', []) + row.get('speakers', []) if kind == 'events' else [row.get('speaker', '')]
            names.update(n.strip() for n in values if isinstance(n, str) and n.strip() and not n.startswith('Non identificato'))
        return tuple(sorted(names))
    except (OSError, ValueError, TypeError, AttributeError):
        return ()

def valid_contacts(values, participants):
    result = {}
    if not isinstance(values, list):
        return []
    for value in values[:100]:
        if not isinstance(value, dict):
            continue
        name, email = value.get('name'), value.get('email')
        if not isinstance(name, str) or name not in participants or not isinstance(email, str):
            continue
        email = email.strip()
        if len(email) <= 254 and re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,}", email):
            result[(name, email.casefold())] = {'name': name, 'email': email}
    return list(result.values())

def participant_names(folder, meta):
    names = set(meta.get('participants', []))
    for filename, kind in [('events.jsonl', 'events'), ('transcript.json', 'transcript')]:
        if kind == 'events' and 'participants' in meta:
            continue
        path = folder/filename
        try:
            stat = path.stat()
            names.update(stored_names(str(path), stat.st_mtime_ns, stat.st_size, kind))
        except OSError:
            pass
    if 'mic' in meta.get('tracks', {}):
        names.add(meta.get('self_name') or 'Io')
    return sorted(names, key=str.casefold)

def public_meta(meta):
    return {**meta, 'tracks': {name:{k:v for k,v in info.items() if k not in ('hashes','last_hash')}
                              for name,info in meta.get('tracks',{}).items()}}

def process(folder):
    with LOCK:
        meta = read(folder/'session.json')
        meta.update(status='transcribing', error=None)
        save(folder/'session.json', meta)
    try:
        if not MODEL.exists() or not VAD.exists():
            raise RuntimeError('Modello assente. Esegui scripts/setup.py.')
        rows = []
        remote_for_echo = []
        events = events_from(folder/'events.jsonl')
        warnings = list(meta.get('client_warnings',[]))
        completed = 0
        for track, info in meta['tracks'].items():
            audio = folder/f'{track}.webm'
            if not audio.exists() or not audio.stat().st_size:
                continue
            wav = folder/f'{track}.wav'
            output = folder/f'{track}-whisper'
            try:
                with (folder/f'{track}-engine.log').open('w') as log:
                    subprocess.run(['ffmpeg', '-nostdin', '-y', '-i', str(audio), '-af', 'aresample=async=1:first_pts=0', '-ar', '16000', '-ac', '1', '-c:a', 'pcm_s16le', str(wav)], stdout=log, stderr=log, check=True, timeout=3600)
                    cmd = ['whisper-cli', '-m', str(MODEL), '-f', str(wav), '-l', meta['language'], '-ojf', '-of', str(output), '-ml', '1', '-sow', '-t', '4', '-sns', '--vad', '-vm', str(VAD), '-vsd', '500', '-vp', '200']
                    if os.environ.get('LOCALCALL_CPU') == '1':
                        cmd.append('-ng')
                    subprocess.run(cmd, stdout=log, stderr=log, check=True, timeout=43200)
                result = read(output.with_suffix('.json'))
                intervals = [(round(float(a)*1000),round(float(b)*1000)) for a,b in re.findall(r'VAD segment \d+: start = ([0-9.]+), end = ([0-9.]+)', (folder/f'{track}-engine.log').read_text(errors='replace'))]
                if result['transcription'] and not intervals:
                    warnings.append('Confini VAD non disponibili: verifica i tempi della traccia '+track)
                segments=constrain_to_speech(result['transcription'],intervals)
                anchors = fuse(segments, events, info['offset'], meta['self_name'] if track == 'mic' else None)
                track_rows = anchors
                if track == 'remote':
                    words = fuse(segments, events, info['offset'], merge=False)
                    remote_for_echo.extend(words)
                    clean_anchors = fuse([s for s in segments if not s.get('timing_adjusted')], events, info['offset'])
                    track_rows, warning = recover(ROOT, wav, words, clean_anchors, events, info['offset'],
                        [(a/1000+info['offset'],b/1000+info['offset']) for a,b in intervals] if intervals else None)
                    if warning:
                        track_rows = anchors
                        warnings.append(warning)
                for row in track_rows:
                    row['track'] = track
                rows.extend(track_rows)
                wav.unlink(missing_ok=True)
                completed += 1
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                warnings.append(f'Traccia {track} non elaborata: {exc}')
        if not completed:
            raise RuntimeError('; '.join(warnings) or 'Nessuna traccia audio disponibile')
        # Do not claim a second local speaker when the microphone contains remote echo.
        for row in rows:
            if row['source'] != 'microphone':
                continue
            if possible_echo(row, remote_for_echo):
                row.update(speaker='Non identificato (possibile eco)', source='possible_echo', confidence=0)
        rows.sort(key=lambda r: (r['start'], r['end']))
        rows = group_turns(rows)
        save(folder/'transcript.json', rows)
        for kind in ('txt', 'srt'):
            (folder/f'transcript.{kind}').write_text(export(rows, kind))
        with LOCK:
            meta = read(folder/'session.json')
            meta.update(status='done', segments=len(rows), warnings=warnings)
            save(folder/'session.json', meta)
    except Exception as exc:
        with LOCK:
            meta = read(folder/'session.json')
            meta.update(status='error', error=str(exc))
            save(folder/'session.json', meta)

class App(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, address, data):
        self.data = Path(data)
        self.data.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.data, 0o700)
        self._data_lock = (self.data/'.lock').open('a')
        self._locks = {}
        self._locks_guard = threading.Lock()
        try:
            fcntl.flock(self._data_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self._data_lock.close()
            raise RuntimeError('LocalCall usa già questa cartella dati. Apri la finestra esistente.')
        try:
            # Bind before recovery: a failed launch must never touch live sessions.
            super().__init__(address, Handler)
            tokenfile = self.data/'token'
            if not tokenfile.exists():
                tokenfile.write_text(secrets.token_urlsafe(32))
            os.chmod(tokenfile, 0o600)
            self.token = tokenfile.read_text().strip()
            for path in self.data.glob('*/session.json'):
                try:
                    meta = read(path)
                    if meta['status'] in ('recording', 'queued', 'transcribing'):
                        for track, info in meta.get('tracks', {}).items():
                            audio = path.parent/f'{track}.webm'
                            if audio.exists() and 'size' in info and audio.stat().st_size > info['size']:
                                with audio.open('r+b') as f:
                                    f.truncate(info['size'])
                        meta.update(status='interrupted', error='Sessione interrotta. Puoi recuperare i dati salvati.')
                        save(path, meta)
                except (ValueError, KeyError, TypeError):
                    # Keep corrupt evidence on disk, without blocking healthy sessions.
                    continue
        except Exception:
            self.server_close()
            raise
    def session_lock(self, key):
        with self._locks_guard:
            return self._locks.setdefault(key, threading.RLock())
    def server_close(self):
        if hasattr(self, 'socket'):
            super().server_close()
        if not self._data_lock.closed:
            self._data_lock.close()

class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(20)
        self.response = None
        self.cached_body = None
    def log_message(self, *args):
        pass
    def origin_ok(self):
        origin = self.headers.get('Origin', '')
        return not origin or origin == f'http://127.0.0.1:{self.server.server_port}' or bool(re.fullmatch(r'chrome-extension://[a-p]{32}', origin))
    def respond(self, code, obj, mime='application/json'):
        self.response = (code, obj, mime)
    def send_result(self):
        code, obj, mime = self.response
        if isinstance(obj, Path):
            with obj.open('rb') as f:
                self.send_response(code)
                self.send_header('Content-Type', mime)
                self.send_header('Content-Length', str(os.fstat(f.fileno()).st_size))
                self.send_header('Cache-Control','no-store')
                self.end_headers()
                shutil.copyfileobj(f, self.wfile, length=65536)
            return
        body = json.dumps(obj, ensure_ascii=False).encode() if mime == 'application/json' else obj
        self.send_response(code)
        if self.origin_ok() and self.headers.get('Origin'):
            self.send_header('Access-Control-Allow-Origin', self.headers['Origin'])
            self.send_header('Vary', 'Origin')
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; connect-src 'self'; media-src 'self' blob:; style-src 'self'; script-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)
    def do_OPTIONS(self):
        if not self.origin_ok():
            self.respond(403, {'error':'Origin denied'})
            return self.send_result()
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', self.headers.get('Origin', ''))
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type, X-Sequence, X-Request-Id')
        self.send_header('Access-Control-Allow-Private-Network', 'true')
        self.end_headers()
    def body(self, limit=4*1024*1024):
        if self.cached_body is not None:
            return self.cached_body
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            raise Problem(400, 'Invalid length')
        if not 0 < length <= limit:
            raise Problem(413, 'Invalid body size')
        blob = self.rfile.read(length)
        if len(blob) != length:
            raise Problem(400, 'Corpo richiesta incompleto')
        return blob
    def json_body(self):
        try:
            return json.loads(self.body())
        except (ValueError, UnicodeError):
            raise Problem(400, 'Invalid JSON')
    def do_GET(self): self.handle_request('GET')
    def do_POST(self): self.handle_request('POST')
    def do_DELETE(self): self.handle_request('DELETE')
    def handle_request(self, method):
        try:
            self.route(method)
        except Problem as exc:
            self.respond(exc.code, {'error':exc.message})
        except (KeyError, TypeError, ValueError):
            self.respond(400, {'error':'Dati non validi'})
        except Exception:
            self.respond(500, {'error':'Errore locale; dati conservati'})
        if self.response:
            try:
                self.send_result()
            except (BrokenPipeError, ConnectionResetError, TimeoutError):
                pass
    def route(self, method):
        if self.headers.get('Host') != f'127.0.0.1:{self.server.server_port}' or not self.origin_ok():
            raise Problem(403, 'Host/origin denied')
        path = urlsplit(self.path).path
        if method == 'GET' and path in ('/', '/app.js', '/style.css'):
            name = {'/':'index.html', '/app.js':'app.js', '/style.css':'style.css'}[path]
            mime = {'/':'text/html; charset=utf-8', '/app.js':'text/javascript', '/style.css':'text/css'}[path]
            return self.respond(200, (ROOT/'localcall/static'/name).read_bytes(), mime)
        auth = self.headers.get('Authorization', '')
        if not hmac.compare_digest(auth, 'Bearer '+self.server.token):
            raise Problem(401, 'Codice di abbinamento non valido')
        # Read network input before taking any session lock; response is sent after release.
        if method == 'POST':
            self.cached_body = self.body()
        key = path.split('/')[3] if path.startswith('/api/sessions/') else 'catalog'
        with self.server.session_lock(key):
            if path == '/api/status' and method == 'GET':
                return self.respond(200, dict(model=MODEL.exists() and VAD.exists(), engine=bool(shutil.which('whisper-cli')), ffmpeg=bool(shutil.which('ffmpeg')), local=True, version='0.3.0'))
            if path == '/api/sessions' and method == 'GET':
                sessions = []
                for p in self.server.data.glob('*/session.json'):
                    try:
                        meta = read(p)
                        if isinstance(meta,dict) and 'created' in meta and 'status' in meta:
                            sessions.append({**public_meta(meta), 'participants': participant_names(p.parent, meta)})
                    except (ValueError, KeyError, TypeError):
                        continue
                return self.respond(200, sorted(sessions, key=lambda s:s['created'], reverse=True))
            if path == '/api/sessions' and method == 'POST':
                body = self.json_body()
                language = body.get('language', 'auto')
                if language not in ('it', 'en', 'auto'):
                    raise Problem(400, 'Lingua non supportata')
                request_id = self.headers.get('X-Request-Id','')
                if request_id and not re.fullmatch(r'[0-9a-f]{32}',request_id):
                    raise Problem(400, 'Identificativo richiesta non valido')
                sid = request_id or uuid.uuid4().hex
                existing = self.server.data/sid/'session.json'
                if existing.exists():
                    return self.respond(200, public_meta(read(existing)))
                folder = self.server.data/sid
                folder.mkdir(mode=0o700)
                meta = dict(id=sid, title=str(body.get('title', 'Riunione'))[:200], self_name=str(body.get('self_name', 'Io'))[:100] or 'Io', language=language, created=time.time(), updated=time.time(), status='recording', tracks={}, event_count=0)
                save(folder/'session.json', meta)
                return self.respond(201, meta)
            match = re.fullmatch(r'/api/sessions/([0-9a-f]{32})(?:/(.*))?', path)
            if not match:
                raise Problem(404, 'Not found')
            sid, action = match.groups()
            folder = self.server.data/sid
            if not (folder/'session.json').exists():
                raise Problem(404, 'Sessione assente')
            meta = read(folder/'session.json')
            if method == 'GET' and not action:
                meta['transcript'] = read(folder/'transcript.json') if (folder/'transcript.json').exists() else []
                meta['transcript'] = [{k:v for k,v in row.items() if k not in ('parts','original_attribution')} for row in meta['transcript']]
                meta['latest_event'] = meta.get('latest_event')
                meta['participants'] = participant_names(folder, meta)
                return self.respond(200, public_meta(meta))
            if method == 'DELETE' and not action:
                if meta['status'] in ('recording', 'queued', 'transcribing'):
                    raise Problem(409, 'Sessione attiva')
                shutil.rmtree(folder)
                return self.respond(200, {'ok':True})
            if method == 'GET' and action in ('export.txt', 'export.srt', 'export.json', 'audio.remote', 'audio.mic'):
                filename = ('transcript.'+action.split('.')[1]) if action.startswith('export') else action.split('.')[1]+'.webm'
                file = folder/filename
                if not file.exists():
                    raise Problem(404, 'File non disponibile')
                return self.respond(200, file, 'application/octet-stream')
            if method != 'POST':
                raise Problem(404, 'Not found')
            if action in ('finish', 'retry'):
                if action == 'retry' and meta['status'] == 'recording' and time.time()-meta.get('updated',meta['created']) < 30:
                    raise Problem(409, 'Registrazione ancora attiva: usa il pulsante Termina.')
                if meta['status'] in ('queued', 'transcribing', 'done'):
                    return self.respond(200, meta)
                if not any((folder/f'{t}.webm').exists() for t in meta['tracks']):
                    raise Problem(409, 'Nessun audio salvato')
                finish_body = self.json_body()
                meta['client_warnings'] = [str(w)[:300] for w in finish_body.get('warnings',[])][:20]
                meta['status'] = 'queued'
                save(folder/'session.json', meta)
                POOL.submit(process, folder)
                return self.respond(202, meta)
            if action == 'abort':
                if meta['status'] != 'recording':
                    raise Problem(409, 'Sessione non in registrazione')
                meta.update(status='interrupted', error='Registrazione interrotta; dati ricevuti conservati.')
                save(folder/'session.json', meta)
                return self.respond(200, meta)
            if meta['status'] != 'recording':
                raise Problem(409, 'Registrazione chiusa')
            if action == 'tracks':
                body = self.json_body()
                if not isinstance(body, dict) or not body or set(body)-{'remote', 'mic'}:
                    raise Problem(400, 'Tracce non valide')
                if meta['tracks']:
                    if body == {k:v['offset'] for k,v in meta['tracks'].items()}:
                        return self.respond(200, {'ok':True, 'duplicate':True})
                    raise Problem(409, 'Tracce già inizializzate')
                for name, offset in body.items():
                    if not isinstance(offset, (int, float)) or not 0 <= offset <= 60:
                        raise Problem(400, 'Offset non valido')
                    meta['tracks'][name] = dict(offset=offset, next_seq=0, size=0, last_hash=None)
            elif action == 'events':
                events = self.json_body()
                if not isinstance(events, list) or len(events)>100:
                    raise Problem(400, 'Eventi non validi')
                valid=[]
                for e in events:
                    if not isinstance(e,dict) or not isinstance(e.get('t'), (int,float)) or not math.isfinite(e['t']) or not 0 <= e['t'] <= 86400 or not isinstance(e.get('speakers'),list):
                        continue
                    participants = e.get('participants',[])
                    if not isinstance(participants,list): participants=[]
                    names = list(dict.fromkeys(str(n)[:100] for n in e['speakers']))
                    # Too many simultaneous speakers is ambiguous: never pick the first 30.
                    clean_participants=[str(n)[:100] for n in participants][:100]
                    valid.append(dict(t=e['t'], speakers=names if len(names)<=30 else [], participants=clean_participants, contacts=valid_contacts(e.get('contacts', []), clean_participants)))
                with (folder/'events.jsonl').open('a') as f:
                    for e in valid:
                        f.write(json.dumps(e, ensure_ascii=False)+'\n')
                meta['event_count'] += len(valid)
                meta['dropped_events'] = meta.get('dropped_events',0) + len(events)-len(valid)
                if valid:
                    meta['latest_event'] = valid[-1]
                    contacts={(c['name'],c['email'].casefold()):c for c in meta.get('contacts', [])}
                    for e in valid:
                        for c in e['contacts']:
                            contacts[(c['name'],c['email'].casefold())]=c
                    meta['contacts']=list(contacts.values())[:1000]
                    meta['participants'] = sorted(set(participant_names(folder, meta)).union(*(set(e['participants']+e['speakers']) for e in valid)))
            elif action in ('audio/remote', 'audio/mic'):
                name = action.split('/')[1]
                if name not in meta['tracks']:
                    raise Problem(409, 'Traccia non inizializzata')
                seq = int(self.headers.get('X-Sequence', '-1'))
                blob = self.body()
                digest = hashlib.sha256(blob).hexdigest()
                track = meta['tracks'][name]
                if seq == track['next_seq']-1 and track.get('last_hash',track.get('hashes',{}).get(str(seq))) == digest:
                    return self.respond(200, {'ok':True, 'duplicate':True})
                if seq != track['next_seq']:
                    raise Problem(409, 'Sequenza audio non valida')
                audio = folder/f'{name}.webm'
                committed = track.get('size', audio.stat().st_size if audio.exists() else 0)
                # Roll back uncommitted tails after I/O failure or process crash.
                with audio.open('r+b' if audio.exists() else 'w+b') as f:
                    if os.fstat(f.fileno()).st_size < committed:
                        raise Problem(409, 'Audio troncato: interrompi e recupera la sessione')
                    f.truncate(committed)
                    f.seek(committed)
                    f.write(blob)
                    f.flush()
                    os.fsync(f.fileno())
                track.pop('hashes',None)
                track.update(last_hash=digest, next_seq=seq+1, size=committed+len(blob))
            else:
                raise Problem(404, 'Not found')
            meta['updated'] = time.time()
            save(folder/'session.json', meta)
            self.respond(200, {'ok':True})

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--data', type=Path, default=ROOT/'data')
    args = parser.parse_args()
    os.umask(0o077)
    server = App(('127.0.0.1', args.port), args.data)
    print(f'LocalCall: http://127.0.0.1:{server.server_port}/#{server.token}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
