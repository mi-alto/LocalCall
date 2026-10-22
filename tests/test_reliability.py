import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from localcall.server import App, save, read, events_from, process
from tests import test_core

class LifecycleTests(unittest.TestCase):
    def test_second_instance_does_not_change_live_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            app=App(('127.0.0.1',0),tmp)
            try:
                folder=Path(tmp)/('a'*32);folder.mkdir()
                save(folder/'session.json',{'status':'recording'})
                for port in (app.server_port,0):
                    with self.assertRaises(RuntimeError):App(('127.0.0.1',port),tmp)
                    self.assertEqual(read(folder/'session.json')['status'],'recording')
            finally:app.server_close()
    def test_recovery_ignores_corrupt_metadata_and_truncates_tail(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad=Path(tmp)/('a'*32);bad.mkdir();(bad/'session.json').write_text('{')
            good=Path(tmp)/('b'*32);good.mkdir()
            save(good/'session.json',{'status':'recording','tracks':{'remote':{'size':4}}})
            (good/'remote.webm').write_bytes(b'gooduncommitted')
            app=App(('127.0.0.1',0),tmp)
            try:
                self.assertEqual((good/'remote.webm').read_bytes(),b'good')
                self.assertEqual(read(good/'session.json')['status'],'interrupted')
                self.assertEqual((bad/'session.json').read_text(),'{')
            finally:app.server_close()
    def test_jsonl_tail_corruption_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'events.jsonl'
            p.write_text('{"t":1,"speakers":["Anna"]}\n{"t":')
            self.assertEqual(len(events_from(p)),1)

class ReliableAPITests(unittest.TestCase):
    setUpClass = classmethod(test_core.APITests.setUpClass.__func__)
    tearDownClass = classmethod(test_core.APITests.tearDownClass.__func__)
    request = test_core.APITests.request
    create = test_core.APITests.create
    def test_failed_metadata_commit_retry_does_not_duplicate_audio(self):
        sid=self.create();base='/api/sessions/'+sid
        self.request(base+'/tracks','POST',{'remote':0})
        with patch('localcall.server.save',side_effect=OSError('synthetic disk error')):
            self.assertEqual(self.request(base+'/audio/remote','POST',b'chunk',headers={'X-Sequence':'0'})[0],500)
        self.assertEqual(self.request(base+'/audio/remote','POST',b'chunk',headers={'X-Sequence':'0'})[0],200)
        self.assertEqual((Path(self.tmp.name)/sid/'remote.webm').read_bytes(),b'chunk')
    def test_corrupt_session_does_not_break_listing(self):
        path=Path(self.tmp.name)/('f'*32);path.mkdir(exist_ok=True);(path/'session.json').write_text('{')
        self.assertEqual(self.request('/api/sessions')[0],200)
    def test_bad_event_does_not_cancel_batch_or_audio(self):
        sid=self.create();base='/api/sessions/'+sid
        events=[{'t':-1,'speakers':['A']},{'t':1,'speakers':['A']},{'t':2,'speakers':[str(i) for i in range(31)]}]
        self.assertEqual(self.request(base+'/events','POST',events)[0],200)
        meta=json.loads(self.request(base)[1])
        self.assertEqual(meta['status'],'recording');self.assertEqual(meta['event_count'],2)
        self.assertEqual(meta['dropped_events'],1);self.assertEqual(meta['latest_event']['speakers'],[])
    def test_large_event_does_not_break_session_detail(self):
        sid=self.create();base='/api/sessions/'+sid
        event={'t':0,'speakers':['A'],'participants':['x'*100]*100}
        self.request(base+'/events','POST',[event])
        self.assertEqual(len(json.loads(self.request(base)[1])['latest_event']['participants']),100)
    def test_local_identity_must_be_a_non_speaking_roster_member(self):
        sid=self.create();base='/api/sessions/'+sid
        for value,expected in [('Self','Self'),('Other',None),('Remote',None)]:
            event=dict(t=1,speakers=['Remote'],participants=['Self','Remote'],self_name=value)
            self.assertEqual(self.request(base+'/events','POST',[event])[0],200)
            saved=events_from(Path(self.tmp.name)/sid/'events.jsonl')[-1]
            self.assertEqual(saved.get('self_name'),expected)

    def test_create_idempotency(self):
        headers={'X-Request-Id':'c'*32}
        one=self.request('/api/sessions','POST',{'language':'it'},headers=headers)
        two=self.request('/api/sessions','POST',{'language':'it'},headers=headers)
        self.assertEqual(json.loads(one[1])['id'],json.loads(two[1])['id'])
    def test_metadata_size_bounded(self):
        sid=self.create();base='/api/sessions/'+sid
        self.request(base+'/tracks','POST',{'remote':0})
        for n in range(150):
            self.assertEqual(self.request(base+'/audio/remote','POST',b'x',headers={'X-Sequence':str(n)})[0],200)
        raw=read(Path(self.tmp.name)/sid/'session.json')
        self.assertNotIn('hashes',raw['tracks']['remote'])
        self.assertLess(len(json.dumps(raw)),1000)

    def test_contact_validation_and_history_persistence(self):
        sid=self.create();base='/api/sessions/'+sid
        contacts=[{'name':'Anna','email':'anna@example.org'}, {'name':'Other','email':'other@example.org'}, {'name':'Anna','email':'bad@example.org<script>'}]
        event={'t':0,'speakers':[],'participants':['Anna'],'contacts':contacts}
        self.assertEqual(self.request(base+'/events','POST',[event])[0],200)
        expected=[{'name':'Anna','email':'anna@example.org'}]
        self.assertEqual(json.loads(self.request(base)[1])['contacts'],expected)
        self.request(base+'/events','POST',[{'t':1,'speakers':[],'participants':[]}])
        listing=json.loads(self.request('/api/sessions')[1])
        self.assertEqual(next(s for s in listing if s['id']==sid)['contacts'],expected)

class TimingTests(unittest.TestCase):
    def test_boundary_word_is_clipped_to_correct_speech_island(self):
        from localcall.diarize import constrain_to_speech
        word={'text':' Buongiorno','offsets':{'from':17750,'to':28280}}
        actual=constrain_to_speech([word],[(9990,17980),(27940,35900)])[0]
        self.assertEqual(actual['offsets'],{'from':27940,'to':28280})
        self.assertTrue(actual['timing_adjusted'])
    def test_turn_boundary_is_not_confidently_assigned(self):
        from localcall.diarize import fuse
        result=fuse([{'text':' Ciao','offsets':{'from':950,'to':1050}}],[{'t':0,'speakers':['A']},{'t':1,'speakers':['B']}])
        self.assertEqual(result[0]['speaker'],'Non identificato')

class ParticipantNamesTests(unittest.TestCase):
    def test_collects_old_events_and_transcript_without_unknown_labels(self):
        from localcall.server import participant_names
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            (folder/'events.jsonl').write_text(json.dumps({'t':0,'participants':['Anna'],'speakers':['Luca']})+'\n')
            save(folder/'transcript.json',[{'speaker':'Luca'},{'speaker':'Non identificato'}])
            self.assertEqual(participant_names(folder,{'tracks':{'mic':{}},'self_name':'Michele'}),['Anna','Luca','Michele'])
            (folder/'events.jsonl').write_text(json.dumps({'t':1,'participants':['Sara'],'speakers':[]})+'\n')
            self.assertIn('Sara',participant_names(folder,{}))
