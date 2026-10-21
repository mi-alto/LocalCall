import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from pathlib import Path
from unittest.mock import patch
from localcall.diarize import attribute, fuse, export
from localcall.server import App

class FusionTests(unittest.TestCase):
    def test_names_and_turn_change(self):
        e=[{'t':0,'speakers':['Anna']},{'t':1,'speakers':['Luca']}]
        self.assertEqual(attribute(.1,.8,e)[0],'Anna')
        self.assertEqual(attribute(1.1,1.8,e)[0],'Luca')
    def test_expired_signal_unknown(self):
        self.assertEqual(attribute(5,6,[{'t':0,'speakers':['Anna']}])[1],'missing')
    def test_overlap_unknown(self):
        self.assertEqual(attribute(0,1,[{'t':0,'speakers':['A','B']}])[1],'overlap')
    def test_empty_resets_speaker(self):
        self.assertEqual(attribute(1,2,[{'t':0,'speakers':['A']},{'t':1,'speakers':[]}])[1],'missing')
    def test_transition_not_guessed(self):
        self.assertEqual(attribute(0,1,[{'t':0,'speakers':['A']},{'t':.5,'speakers':['B']}])[1],'missing')
    def test_mic_offset_and_export(self):
        r=fuse([{'text':' Ciao','offsets':{'from':100,'to':500}}],[],offset=2,self_name='Michele')
        self.assertEqual(r[0]['start'],2.1)
        self.assertEqual(r[0]['speaker'],'Michele')
        self.assertIn('00:00:02,100 --> 00:00:02,500',export(r,'srt'))
    def test_silence_boundary_does_not_erase_observed_speaker(self):
        events=[{'t':0,'speakers':[]},{'t':1,'speakers':['A']},{'t':2,'speakers':[]}]
        rows=fuse([{'text':' Ciao','offsets':{'from':1050,'to':1500}}],events)
        self.assertEqual(rows[0]['speaker'],'A')
        rows=fuse([{'text':' Ciao','offsets':{'from':2100,'to':2500}}],events)
        self.assertEqual(rows[0]['speaker'],'Non identificato')
    def test_word_merge(self):
        r=fuse([{'text':' Ciao','offsets':{'from':0,'to':300}},{'text':' mondo','offsets':{'from':300,'to':800}}],[{'t':0,'speakers':['A']}])
        self.assertEqual(r[0]['text'],'Ciao mondo')

class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.app=App(('127.0.0.1',0),Path(cls.tmp.name))
        cls.thread=threading.Thread(target=cls.app.serve_forever,daemon=True);cls.thread.start()
        cls.url=f'http://127.0.0.1:{cls.app.server_port}'
    @classmethod
    def tearDownClass(cls):
        cls.app.shutdown();cls.app.server_close();cls.tmp.cleanup()
    def request(self,path,method='GET',body=None,auth=True,headers=None):
        headers=headers or {}
        if auth:headers['Authorization']='Bearer '+self.app.token
        if body is not None and not isinstance(body,bytes):body=json.dumps(body).encode()
        req=urllib.request.Request(self.url+path,data=body,headers=headers,method=method)
        try:
            with urllib.request.urlopen(req) as r:return r.status,r.read()
        except urllib.error.HTTPError as e:
            with e:return e.code,e.read()
    def create(self):
        code,b=self.request('/api/sessions','POST',{'title':'Test','language':'it'})
        self.assertEqual(code,201);return json.loads(b)['id']
    def test_requires_token(self):self.assertEqual(self.request('/api/sessions',auth=False)[0],401)
    def test_rejects_external_origin(self):self.assertEqual(self.request('/api/status',headers={'Origin':'https://evil.example'})[0],403)
    def test_rejects_rebinding_host(self):self.assertEqual(self.request('/api/status',headers={'Host':'evil.example'})[0],403)
    def test_extension_cors(self):
        self.assertEqual(self.request('/api/status',headers={'Origin':'chrome-extension://'+'a'*32})[0],200)
    def test_language_validation(self):self.assertEqual(self.request('/api/sessions','POST',{'language':'--evil'})[0],400)
    def test_upload_order_idempotency_and_recovery(self):
        sid=self.create();base='/api/sessions/'+sid
        self.assertEqual(self.request(base+'/tracks','POST',{'mic':0})[0],200)
        self.assertEqual(self.request(base+'/audio/mic','POST',b'chunk',headers={'X-Sequence':'1'})[0],409)
        for _ in range(2):self.assertEqual(self.request(base+'/audio/mic','POST',b'chunk',headers={'X-Sequence':'0'})[0],200)
        self.assertEqual((Path(self.tmp.name)/sid/'mic.webm').read_bytes(),b'chunk')
        self.assertEqual(self.request(base+'/audio/mic','POST',b'other',headers={'X-Sequence':'0'})[0],409)
        self.assertEqual(self.request(base+'/abort','POST',{})[0],200)
        self.assertEqual(self.request(base+'/audio/mic','POST',b'next',headers={'X-Sequence':'1'})[0],409)
        with patch('localcall.server.POOL.submit') as submit:
            self.assertEqual(self.request(base+'/retry','POST',{})[0],202)
            self.assertEqual(self.request(base+'/retry','POST',{})[0],200)
            submit.assert_called_once()
    def test_bad_events_and_delete(self):
        sid=self.create();base='/api/sessions/'+sid
        self.assertEqual(self.request(base+'/events','POST',[{'t':-1,'speakers':['A']}])[0],200)
        self.assertEqual(self.request(base,'DELETE')[0],409)
        self.request(base+'/abort','POST',{})
        self.assertEqual(self.request(base,'DELETE')[0],200)
        self.assertEqual(self.request(base)[0],404)
    def test_no_path_traversal(self):self.assertEqual(self.request('/api/sessions/../../token')[0],404)
    def test_cannot_recover_active_recording(self):
        self.assertEqual(self.request('/api/sessions/'+self.create()+'/retry','POST',{})[0],409)
    def test_empty_finish(self):self.assertEqual(self.request('/api/sessions/'+self.create()+'/finish','POST',{})[0],409)

if __name__=='__main__':unittest.main()
