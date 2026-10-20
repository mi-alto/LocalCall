#!/usr/bin/env python3
"""Download only public model weights; verify the upstream LFS SHA256."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parent.parent
NAME='ggml-large-v3-turbo-q5_0.bin'
SHA='394221709cd5ad1f40c46e6031ca61bce88931e6e088c188294c6d5a55ffa7e2'
URL='https://huggingface.co/ggerganov/whisper.cpp/resolve/5359861c739e955e79d9a303bcbc70fb988958b1/'+NAME

def digest(path):
    with path.open('rb') as f:
        hasher=hashlib.sha256()
        for block in iter(lambda:f.read(1024*1024), b''):
            hasher.update(block)
        return hasher.hexdigest()

def install(name, url, sha):
    target=ROOT/'models'/name
    target.parent.mkdir(exist_ok=True)
    if target.exists() and digest(target)==sha:
        return
    part=target.with_suffix('.bin.part')
    if not part.exists() or digest(part)!=sha:
        subprocess.run(['curl','--fail','--location','--retry','3','--output',str(part),url],check=True)
    if digest(part)!=sha:
        sys.exit('Verifica SHA256 fallita: '+name)
    part.replace(target)

def main():
    missing=[x for x in ('whisper-cli','ffmpeg') if not shutil.which(x)]
    if missing:
        sys.exit('Installa prima i motori locali: brew install whisper-cpp ffmpeg')
    install(NAME,URL,SHA)
    install('ggml-silero-v6.2.0.bin',
            'https://huggingface.co/ggml-org/whisper-vad/resolve/9ffd54a1e1ee413ddf265af9913beaf518d1639b/ggml-silero-v6.2.0.bin',
            '2aa269b785eeb53a82983a20501ddf7c1d9c48e33ab63a41391ac6c9f7fb6987')
    print('Whisper e Silero installati e verificati. La trascrizione funziona senza rete.')

if __name__=='__main__':main()
