#!/usr/bin/env python3
"""Register the local bridge for explicitly selected extension IDs (macOS)."""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import sys

ROOT = Path(__file__).resolve().parents[1]
HOST = 'org.localcall.launcher'

def install(ids, root=ROOT, home=None):
    if not ids or any(not re.fullmatch(r'[a-p]{32}', value) for value in ids):
        raise ValueError('Provide the 32-letter ID from the browser extensions page.')
    home = Path.home() if home is None else Path(home)
    os.umask(0o077)
    data = root/'data'
    data.mkdir(mode=0o700, exist_ok=True)
    origins = [f'chrome-extension://{value}/' for value in sorted(set(ids))]
    (data/'native-origins.json').write_text(json.dumps(origins))
    launcher = data/'native-launcher'
    launcher.write_text('#!/bin/sh\ncd '+shlex.quote(str(root))+' || exit 1\nexec '+shlex.quote(sys.executable)+' -m localcall.native_host "$@"\n')
    launcher.chmod(0o700)
    manifest = {'name': HOST, 'description': 'Launch LocalCall locally', 'path': str(launcher), 'type': 'stdio', 'allowed_origins': origins}
    for browser in ['Google/Chrome', 'BraveSoftware/Brave-Browser']:
        folder = home/'Library/Application Support'/browser/'NativeMessagingHosts'
        folder.mkdir(parents=True, exist_ok=True)
        (folder/(HOST+'.json')).write_text(json.dumps(manifest, indent=2)+'\n')
    return origins

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extension-id', action='append', required=True)
    args = parser.parse_args()
    if sys.platform != 'darwin':
        parser.error('This installer currently supports macOS only.')
    install(args.extension_id)
    print('Collegamento installato per Chrome e Brave. Ricarica LocalCall nella pagina delle estensioni.')
