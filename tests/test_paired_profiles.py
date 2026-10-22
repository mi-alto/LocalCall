import unittest
from types import SimpleNamespace
from localcall.paired_profiles import recover,validate
from localcall import session_diarization as diarization

class PairedProfileTests(unittest.TestCase):
    def data(self):
        import numpy as np
        vectors=np.asarray([[1.,0.]]*8)
        windows=[(i*4,i*4+3) for i in range(8)]
        words=[dict(start=0,end=1,text='unchanged',speaker='Non identificato',source='acoustic_unknown',confidence=0,track='remote')]
        engine=SimpleNamespace(cluster_vectors=lambda v:({1:np.array([1.,0.])},[(1,.9)]*len(v)),
            name_clusters=lambda *args:({1:'Remote'},{}),speech_windows=diarization.speech_windows,assign_words=diarization.assign_words)
        return words,windows,vectors,[(100+i*4,103+i*4) for i in range(8)],engine
    def test_two_profiles_recover_unknown_without_changing_content(self):
        import numpy as np
        rows,w,v,m,engine=self.data()
        out=recover(rows,w,v,m,w,[],lambda a,b:np.array([0.,1.]),'Remote',engine)
        self.assertEqual(out[0]['speaker'],'Remote');validate(rows[0],out[0],'Remote')
        self.assertEqual(rows[0]['speaker'],'Non identificato')
    def test_local_competitor_missing_references_and_mic_rows_abstain(self):
        import numpy as np
        rows,w,v,m,engine=self.data()
        for local in (lambda a,b:np.array([1.,0.]),lambda a,b:None):
            self.assertEqual(recover(rows,w,v,m,w,[],local,'Remote',engine),rows)
        rows[0]['track']='mic'
        self.assertEqual(recover(rows,w,v,m,w,[],lambda a,b:np.array([0.,1.]),'Remote',engine),rows)
    def test_resolved_and_manual_labels_are_immutable(self):
        import numpy as np
        for source in ('voice','manual','channel','microphone'):
            rows,w,v,m,engine=self.data();rows[0].update(source=source,speaker='Other')
            self.assertEqual(recover(rows,w,v,m,w,[],lambda a,b:np.array([0.,1.]),'Remote',engine),rows)
    def test_validator_rejects_content_and_evidence_tampering(self):
        import numpy as np
        rows,w,v,m,engine=self.data();out=recover(rows,w,v,m,w,[],lambda a,b:np.array([0.,1.]),'Remote',engine)[0]
        for changes in ({'text':'changed'},{'speaker':'Wrong'},{'voice_similarity':float('nan')},{'voice_similarity':.39},{'profile_recovery':{}}):
            with self.assertRaises(ValueError):validate(rows[0],dict(out,**changes),'Remote')
    def test_reference_work_is_bounded(self):
        import numpy as np
        rows,w,v,m,engine=self.data();calls=[]
        def embed(a,b):calls.append((a,b));return np.array([0.,1.])
        recover(rows,w,v,[(100+i*4,103+i*4) for i in range(1000)],w,[],embed,'Remote',engine)
        self.assertLessEqual(len(calls),256)
    def test_lost_events_do_not_start_worker(self):
        from pathlib import Path
        from unittest.mock import patch
        from localcall.speaker import recover_profiles
        rows,_,_,_,_=self.data()
        events=[dict(t=i,speakers=['Remote'],participants=['Self','Remote'],self_name='Self') for i in range(30)]
        with patch('localcall.speaker.subprocess.run',side_effect=AssertionError('Must not start')):
            out,warning=recover_profiles(Path('/tmp'),Path('/tmp/no.wav'),Path('/tmp/no-mic.wav'),rows,events,0,0,[(0,5)],[(10,20)],{'event_gaps':1,'self_name':'Self','confirmed_participant_count':2})
        self.assertEqual(out,rows);self.assertIsNone(warning)
    def test_server_keeps_both_tracks_until_profile_step_then_cleans_up(self):
        import json,tempfile
        from pathlib import Path
        from unittest.mock import patch
        from localcall import server
        for order in (('remote','mic'),('mic','remote')):
            with tempfile.TemporaryDirectory() as tmp:
                folder=Path(tmp);model=folder/'model';model.write_text('test')
                meta=dict(status='queued',language='it',self_name='Self',tracks={k:{'offset':0,'size':4} for k in order})
                server.save(folder/'session.json',meta)
                for k in order:(folder/f'{k}.webm').write_bytes(b'test')
                def run(cmd,**kwargs):
                    if cmd[0]=='ffmpeg':Path(cmd[-1]).write_bytes(b'wave')
                    else:
                        output=Path(cmd[cmd.index('-of')+1]).with_suffix('.json')
                        output.write_text(json.dumps({'transcription':[{'text':'test','offsets':{'from':100,'to':500}}]}))
                        kwargs['stdout'].write('VAD segment 0: start = 0.0, end = 1.0\n');kwargs['stdout'].flush()
                def profiles(root,wav,mic,rows,*args):
                    self.assertTrue(wav.exists());self.assertTrue(mic.exists())
                    return rows,'Synthetic profile fallback'
                with patch.object(server,'MODEL',model),patch.object(server,'VAD',model),patch.object(server.subprocess,'run',side_effect=run),patch.object(server,'recover',side_effect=lambda root,wav,words,*args,**kw:(words,None)),patch.object(server,'recover_profiles',side_effect=profiles) as call:
                    server.process(folder)
                self.assertEqual(call.call_count,1)
                result=server.read(folder/'session.json');self.assertEqual(result['status'],'done',result)
                self.assertIn('Synthetic profile fallback',result['warnings'])
                self.assertFalse((folder/'mic.wav').exists());self.assertFalse((folder/'remote.wav').exists())

    def test_overlapping_references_cannot_recognize_themselves(self):
        import numpy as np
        rows,w,v,m,engine=self.data()
        overlapping=[(0,3)]*8
        out=recover(rows,overlapping,v,m,overlapping,[],lambda a,b:np.array([0.,1.]),'Remote',engine)
        self.assertEqual(out,rows)
    def test_simultaneous_echo_vetoes_remote_recovery(self):
        import numpy as np
        rows,w,v,m,engine=self.data()
        m=m+[(0,3)]
        def embedding(a,b):return np.array([1.,0.]) if a<10 else np.array([0.,1.])
        out=recover(rows,w,v,m,w,[],embedding,'Remote',engine)
        self.assertEqual(out,rows)
