#!/usr/bin/env python3
"""Optional ECAPA install. Downloads code/weights only, never call data."""
from pathlib import Path
import shutil
import subprocess
import sys
import platform
import json

ROOT = Path(__file__).resolve().parent.parent
REVISION = '0f99f2d0ebe89ac095bcc5903c4dd8f72b367286'

def main():
    if sys.platform == 'darwin' and platform.machine() != 'arm64':
        sys.exit('This speaker environment requires an Apple Silicon Mac.')
    if not shutil.which('uv'):
        sys.exit('Install uv first: brew install uv')
    env = ROOT/'.speaker-env'
    if not (env/'bin/python').exists():
        subprocess.run(['uv','venv','--python','3.12',str(env)],check=True)
    python = env/'bin/python'
    subprocess.run(['uv','pip','sync','--python',str(python),'--require-hashes',str(ROOT/'scripts/speaker-requirements.lock')],check=True)
    subprocess.run([str(python),'-c',
        'from huggingface_hub import snapshot_download; '
        'snapshot_download("speechbrain/spkrec-ecapa-voxceleb", '
        f'revision={REVISION!r}, local_dir={str(ROOT/"models/speaker-ecapa")!r}, '
        'allow_patterns=["*.ckpt","*.yaml","*.txt","README.md"],token=False)'],check=True)
    (ROOT/'models/speaker-ecapa/.ready').write_text(json.dumps({'revision': REVISION}))
    print('ECAPA installed. Runtime processing is local, offline and sequential after Whisper.')

if __name__ == '__main__':
    main()
