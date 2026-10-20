"""Real offline inference integration, opt-in: LOCALCALL_INFERENCE_TEST=1."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from localcall.server import process, save, MODEL, VAD

@unittest.skipUnless(os.environ.get('LOCALCALL_INFERENCE_TEST')=='1','Opt-in real model test')
class InferenceTests(unittest.TestCase):
    def run_track(self, audio, language):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            subprocess.run(['ffmpeg','-nostdin','-y','-i',str(audio),'-c:a','libopus',str(folder/'mic.webm')],check=True,capture_output=True)
            save(folder/'session.json',dict(status='queued',language=language,self_name='Test',tracks={'mic':{'offset':0}}))
            process(folder)
            meta=json.loads((folder/'session.json').read_text())
            self.assertEqual(meta['status'],'done',meta.get('error'))
            return json.loads((folder/'transcript.json').read_text())
    def test_italian(self):
        rows=self.run_track(Path('.test-output/italiano.wav'),'it')
        self.assertIn('progetto',' '.join(r['text'] for r in rows).lower())
    def test_english(self):
        rows=self.run_track(Path('.test-output/english.wav'),'en')
        self.assertIn('project',' '.join(r['text'] for r in rows).lower())
    def test_silence_no_hallucinations(self):
        import wave
        with tempfile.TemporaryDirectory() as tmp:
            wav=Path(tmp)/'silence.wav'
            with wave.open(str(wav),'wb') as f:
                f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(b'\x00\x00'*16000*5)
            self.assertEqual(self.run_track(wav,'it'),[])

    def test_vad_preserves_original_timeline_after_long_silences(self):
        import wave
        with wave.open('.test-output/italiano.wav','rb') as source:
            params=source.getparams();samples=source.readframes(source.getnframes())
        silence=b'\x00\x00'*16000*10
        with tempfile.TemporaryDirectory() as tmp:
            wav=Path(tmp)/'pauses.wav'
            with wave.open(str(wav),'wb') as f:
                f.setparams(params);f.writeframes(silence+samples+silence+samples)
            rows=self.run_track(wav,'it')
            self.assertGreaterEqual(rows[0]['start'],9)
            self.assertTrue(any(r['start']>=26 and 'Buongiorno' in r['text'] for r in rows),rows)
