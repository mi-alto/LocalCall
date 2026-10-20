#!/usr/bin/env python3
"""Synthetic test audio using built-in macOS speech; never captures a microphone."""
from pathlib import Path
import subprocess
out=Path(__file__).resolve().parent.parent/'.test-output'
out.mkdir(exist_ok=True)
for name,voice,text in [
    ('italiano','Alice','Buongiorno a tutti. Oggi discutiamo il progetto e le prossime attività. Michele prepara il documento, mentre Anna verifica i risultati.'),
    ('english','Samantha','Good morning everyone. Today we will review the project and agree on the next steps. Anna will check the results and Michael will prepare the report.')]:
    subprocess.run(['say','-v',voice,'-o',str(out/f'{name}.aiff'),text],check=True)
    subprocess.run(['ffmpeg','-nostdin','-y','-i',str(out/f'{name}.aiff'),'-ar','16000','-ac','1',str(out/f'{name}.wav')],check=True,capture_output=True)
print('Campioni sintetici creati in .test-output.')
