import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from localcall.speaker import choose, group_turns, recover
from localcall.diarize import fuse

class SpeakerTests(unittest.TestCase):
    def test_requires_separation_and_allows_only_candidates(self):
        self.assertEqual(choose({'F': .61, 'L': .1}, {'F','L'}), 'F')
        for scores,candidates in [({'F':.61,'L':.55},{'F','L'}),({'F':.4,'L':.1},{'F','L'}),({'F':.8},{'F'}),({'F':.8,'L':.1},{'L'})]:
            self.assertIsNone(choose(scores,candidates))
    def row(self,start,end,name='F',source='dom',track='remote'):
        return dict(start=start,end=end,speaker=name,source=source,track=track,text='test',confidence=.9)
    def test_groups_known_sources_preserves_evidence(self):
        a,b=self.row(0,2),self.row(2.1,4,source='voice')
        rows=group_turns([a,b])
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['source'],'dom')
        self.assertTrue(rows[0]['voice_recovered'])
        self.assertEqual([{k:v for k,v in r.items() if k not in ('voice_recovered','context_inferred')} for r in rows[0]['parts']],[a,b])
        self.assertNotIn('parts',a)
    def test_never_bridges_unknown_other_speaker_or_tracks(self):
        for other in [self.row(2,3,source='overlap'),self.row(2,3,name='L'),self.row(2,3,track='mic'),self.row(4,5),self.row(1,3)]:
            self.assertEqual(len(group_turns([self.row(0,2),other])),2)
    def test_word_mode_preserves_timing(self):
        segments=[{'text':' Hi','offsets':{'from':0,'to':300}},{'text':' there','offsets':{'from':300,'to':800}}]
        self.assertEqual(len(fuse(segments,[{'t':0,'speakers':['F']}],merge=False)),2)
    def test_missing_installation_falls_back(self):
        with tempfile.TemporaryDirectory() as d:
            rows=[self.row(0,1)]
            result,warning=recover(Path(d),Path('a.wav'),rows,[],[],0)
            self.assertEqual(result,rows);self.assertTrue(warning)
    def test_worker_cannot_change_text(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for f in ['.speaker-env/bin/python']+['models/speaker-ecapa/'+name for name in ('.ready','embedding_model.ckpt','hyperparams.yaml','mean_var_norm_emb.ckpt','classifier.ckpt','label_encoder.txt')]:
                p=root/f;p.parent.mkdir(parents=True,exist_ok=True);p.touch()
            rows=[self.row(0,1,source='transition')]
            bad=[dict(rows[0],text='changed')]
            with patch('localcall.speaker.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=json.dumps(bad))):
                result,warning=recover(root,Path('a.wav'),rows,[],[],0)
            self.assertEqual(result,rows);self.assertTrue(warning)

    def test_malformed_worker_results_fall_back(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for f in ['.speaker-env/bin/python']+['models/speaker-ecapa/'+name for name in ('.ready','embedding_model.ckpt','hyperparams.yaml','mean_var_norm_emb.ckpt','classifier.ckpt','label_encoder.txt')]:
                p=root/f;p.parent.mkdir(parents=True,exist_ok=True);p.touch()
            rows=[self.row(0,1,source='transition'), self.row(1,2)]
            changed=[dict(rows[0]),dict(rows[1],speaker='L')]
            for output in ['null','["x", "y"]','[{"start":0}, {}]','{"a":1,"b":2}',json.dumps(changed),'not json']:
                with self.subTest(output=output), patch('localcall.speaker.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=output)):
                    result,warning=recover(root,Path('a.wav'),rows,[],[],0)
                self.assertEqual(result,rows)
                self.assertTrue(warning)

    def test_known_rows_do_not_start_worker(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for f in ['.speaker-env/bin/python']+['models/speaker-ecapa/'+name for name in ('.ready','embedding_model.ckpt','hyperparams.yaml','mean_var_norm_emb.ckpt','classifier.ckpt','label_encoder.txt')]:
                p=root/f;p.parent.mkdir(parents=True,exist_ok=True);p.touch()
            rows=[self.row(0,1)]
            with patch('localcall.speaker.subprocess.run') as run:
                result,warning=recover(root,Path('a.wav'),rows,[],[],0)
            run.assert_not_called()
            self.assertEqual(result,rows)
            self.assertIsNone(warning)

    def test_reference_edges_and_adjusted_samples_excluded(self):
        from localcall.speaker import reference_spans
        rows=[self.row(0,10),dict(self.row(20,30),timing_adjusted=True)]
        refs=reference_spans(rows)['F']
        self.assertTrue(all(a>=1.25 and b<=8.75 for a,b,_ in refs))

    def test_queries_never_borrow_known_speech(self):
        from localcall.speaker import query_chunks
        rows=[self.row(0,2),self.row(2,2.5,source='transition'),self.row(2.5,4)]
        self.assertEqual(query_chunks(rows),[])
        rows=[self.row(0,2),self.row(2,4,source='overlap'),self.row(4,6)]
        self.assertEqual(query_chunks(rows),[(2,4,[1])])

    def test_distinct_reference_turns_required(self):
        from localcall.speaker import coherent_reference
        self.assertIsNone(coherent_reference([([1,0],1),([1,0],1)]))
        self.assertEqual(coherent_reference([([1,0],1),([1,0],2)]),[1,0])
        self.assertIsNone(coherent_reference([([1,0],1),([0,1],2)]))

    def test_outside_candidate_can_veto_and_windows_stay_inside(self):
        from localcall.speaker import resolve_words
        anchors=[self.row(0,8),self.row(10,18),self.row(20,28,name='L'),self.row(30,38,name='L'),self.row(40,48,name='Other'),self.row(50,58,name='Other')]
        words=[self.row(60,63,name='Non identificato',source='overlap')]
        events=[{'t':60+i*.5,'speakers':['F','L']} for i in range(6)]
        calls=[]
        def embed(a,b):
            calls.append((a,b))
            if a>=60:return [0,0,1]
            if a<20:return [1,0,0]
            if a<40:return [0,1,0]
            return [0,0,1]
        self.assertEqual(resolve_words(words,anchors,events,embed),words)
        self.assertTrue(all(a>=60 and b<=63 for a,b in calls if a>=60))
        def same(a,b):
            return [1,0,0] if a<20 or a>=60 else ([0,1,0] if a<40 else [0,0,1])
        self.assertEqual(resolve_words(words,anchors,events,same)[0]['speaker'],'F')

    def test_empty_observation_expires_candidates(self):
        from localcall.speaker import candidate_names
        events=[{'t':0,'speakers':['F']},{'t':.5,'speakers':[]}]
        self.assertEqual(candidate_names(events,.6,1),set())

    def test_srt_does_not_export_long_display_paragraph(self):
        from localcall.diarize import export
        rows=group_turns([self.row(0,15),self.row(15,30),self.row(30,45)])
        self.assertEqual(len(rows),1)
        self.assertEqual(export(rows,'srt').count('-->'),3)

    def test_audio_offset_clamping(self):
        from localcall.speaker import audio_bounds
        self.assertEqual(audio_bounds(10,13,10,20),(0,3))
        self.assertEqual(audio_bounds(9,13,10,20),(0,3))
        self.assertIsNone(audio_bounds(29,33,10,20))
        self.assertIsNone(audio_bounds(0,4,10,20))

    def test_echo_uses_words_and_rejects_short_acknowledgements(self):
        from localcall.speaker import possible_echo
        mic=dict(self.row(0,3,source='microphone'),text='uno due tre')
        remote=[dict(self.row(i,i+.8),text=t) for i,t in enumerate(['uno','due','tre'])]
        self.assertTrue(possible_echo(mic,remote))
        self.assertFalse(possible_echo(dict(mic,text='si'),[dict(remote[0],text='si')]))
        self.assertFalse(possible_echo(dict(mic,text='sono tre cose'),remote))

class AudioOnlyGroupingTests(unittest.TestCase):
    def test_text_cannot_supply_missing_speaker(self):
        rows=[dict(start=0,end=1,text='di',speaker='F',source='dom',confidence=1),
              dict(start=1,end=2,text='concetto potete farmi',speaker='Non identificato',source='transition',confidence=0),
              dict(start=2,end=3,text='per favore',speaker='F',source='dom',confidence=1)]
        grouped=group_turns(rows)
        self.assertEqual(len(grouped),3)
        self.assertEqual(grouped[1]['speaker'],'Non identificato')
        self.assertFalse(any(r.get('context_inferred') for r in grouped))
