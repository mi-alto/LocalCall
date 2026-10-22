import unittest
from localcall.session_diarization import speech_windows,exclusive_name,name_clusters,assign_words

class SessionDiarizationTests(unittest.TestCase):
    def test_windows_ignore_names_and_text_and_skip_silence(self):
        words=[dict(start=0,end=7,text='anything',speaker='Wrong'),dict(start=12,end=13)]
        self.assertEqual(speech_windows(words),[(0,3),(1.5,4.5),(3,6),(4,7)])
        words[0].update(text='different',speaker='Different')
        self.assertEqual(speech_windows(words),[(0,3),(1.5,4.5),(3,6),(4,7)])
    def test_browser_name_needs_unambiguous_fresh_coverage(self):
        events=[dict(t=t,speakers=['A']) for t in (0,1,2)]
        self.assertEqual(exclusive_name(events,0,3),'A')
        self.assertIsNone(exclusive_name(events,4,7))
        events[1]['speakers']=['A','B']
        self.assertIsNone(exclusive_name(events,0,3))
    def test_names_require_repeated_separated_evidence(self):
        windows=[(t,t+3) for t in (0,10,30)]
        assigned=[(1,.9)]*3
        events=[dict(t=t+j,speakers=['A']) for t in (0,10,30) for j in range(3)]
        mapping,evidence=name_clusters(windows,assigned,events)
        self.assertEqual(mapping,{1:'A'});self.assertEqual(evidence[1]['support'],3)
        self.assertEqual(name_clusters(windows[:2],assigned[:2],events)[0],{})
        self.assertEqual(name_clusters(windows,[(1,.6)]*3,events)[0],{})
    def test_relabels_wrong_dom_only_from_audio_cluster(self):
        row=dict(start=1,end=2,speaker='Wrong',source='dom',confidence=1,text='unchanged')
        rows=assign_words([row],[(0,3)],[(1,.9)],{1:'Correct'},{1:{'support':4}})
        self.assertEqual(rows[0]['speaker'],'Correct')
        self.assertEqual(rows[0]['original_attribution']['speaker'],'Wrong')
        for key in ('start','end','text'):self.assertEqual(row[key],rows[0][key])
    def test_conflicting_or_unmapped_audio_abstains(self):
        row=dict(start=1,end=2,speaker='A',source='dom',confidence=1,text='anything')
        rows=assign_words([row],[(0,3),(0,3)],[(1,.9),(2,.9)],{1:'A',2:'B'},{1:{'support':4},2:{'support':4}})
        self.assertEqual(rows[0]['source'],'acoustic_unknown')
        self.assertEqual(assign_words([row],[(0,3)],[(1,.9)],{}, {})[0]['source'],'acoustic_unknown')

    def test_tiny_window_edge_cannot_label_a_long_word(self):
        row=dict(start=2.9,end=4,speaker='A',source='dom',confidence=1,text='test')
        self.assertEqual(assign_words([row],[(0,3)],[(1,.9)],{1:'A'},{1:{'support':4}})[0]['source'],'acoustic_unknown')

    def test_worker_validation_checks_names_provenance_and_timing(self):
        from localcall.session_diarization import validate_result
        row=dict(start=1,end=2,speaker='Wrong',source='dom',confidence=1,text='unchanged')
        after=assign_words([row],[(0,3)],[(1,.9)],{1:'Correct'},{1:{'support':4}})[0]
        validate_result(row,after,{'Correct'})
        for change in ({'speaker':'Invented'},{'text':'rewritten'},{'end':3},{'name_support':1},{'voice_similarity':float('nan')},{'acoustic_coverage':.3}):
            with self.subTest(change=change),self.assertRaises(ValueError):validate_result(row,dict(after,**change),{'Correct'})

    def test_acoustic_clustering_and_decoder_respect_real_voice_changes(self):
        try:import numpy as np
        except ImportError:self.skipTest('Run with .speaker-env for acoustic array tests')
        from localcall.session_diarization import cluster_vectors,decode_voices
        vectors=np.array([[1.,0.,0.]]*4+[[0.,1.,0.]]*4)
        centroids,assigned=cluster_vectors(vectors)
        self.assertEqual(len(centroids),2)
        a,b=assigned[0][0],assigned[-1][0]
        self.assertNotEqual(a,b)
        windows=[(i*1.5,i*1.5+3) for i in range(8)]
        decoded,names,_=decode_voices(windows,vectors,centroids,{a:'A',b:'B'},{a:{'support':4},b:{'support':4}})
        self.assertEqual([names[c] for c,_ in decoded],['A']*4+['B']*4)
        unknown=np.array([[0.,0.,1.]])
        decoded,_,_=decode_voices([(0,3)],unknown,centroids,{a:'A',b:'B'},{a:{'support':4},b:{'support':4}})
        self.assertIsNone(decoded[0][0])

    def test_manual_and_microphone_are_protected(self):
        from localcall.session_diarization import validate_result
        for source in ('manual','microphone'):
            row=dict(start=0,end=3,speaker='Self',source=source,confidence=1,text='original')
            result=assign_words([row],[(0,3)],[(1,.9)],{1:'Other'},{1:{'support':4}})[0]
            self.assertEqual(result,row);validate_result(row,result,{'Other'})

    def test_rerun_preserves_original_and_clears_old_voice_scores(self):
        from localcall.session_diarization import validate_result
        before=dict(start=0,end=3,speaker='A',source='voice',confidence=0,text='same',voice_similarity=.9,
                    original_attribution={'speaker':'B','source':'dom','confidence':1})
        after=assign_words([before],[],[],{}, {})[0]
        self.assertNotIn('voice_similarity',after)
        self.assertEqual(after['original_attribution'],before['original_attribution'])
        validate_result(before,after,{'A','B'})

    def test_unnamed_voice_competes_against_known_names(self):
        try:import numpy as np
        except ImportError:self.skipTest('Requires acoustic environment')
        from localcall.session_diarization import decode_voices
        centroids={1:np.array([1.,0.]),2:np.array([.5,3**.5/2])}
        assigned,_,_=decode_voices([(0,3)],np.array([centroids[2]]),centroids,{1:'A'},{1:{'support':4}})
        self.assertIsNone(assigned[0][0])

    def test_audio_bounds_are_applied_before_embeddings(self):
        try:import numpy
        except ImportError:self.skipTest('Requires acoustic environment')
        from localcall.session_diarization import diarize
        calls=[]
        def embed(a,b):calls.append((a,b));return None
        words=[dict(start=0,end=6,speaker='A',source='dom',confidence=1,text='original')]
        result,_=diarize(words,[],embed,audio_range=(2,4))
        self.assertTrue(all(2<=a<b<=4 for a,b in calls))
        self.assertEqual(result[0]['source'],'acoustic_unknown')

    def test_refinement_budget_and_existing_labels_are_preserved(self):
        try:import numpy as np
        except ImportError:self.skipTest('Requires acoustic environment')
        from localcall.session_diarization import refine_boundaries
        rows=[dict(start=10,end=11,speaker='A',source='voice'),
              dict(start=11,end=12,speaker='Non identificato',source='acoustic_unknown'),
              dict(start=12,end=13,speaker='B',source='voice')]
        calls=[]
        def embed(a,b):calls.append((a,b));return np.array([.7,.7])
        result,n=refine_boundaries(rows,rows,{1:np.array([1.,0.]),2:np.array([0.,1.])},{1:'A',2:'B'},{1:{'support':4},2:{'support':4}},embed,(0,30),max_queries=6)
        self.assertLessEqual(n,6);self.assertEqual(len(calls),n)
        self.assertEqual(result[0],rows[0]);self.assertEqual(result[-1],rows[-1])
        self.assertEqual(result[1]['speaker'],'Non identificato')

    def test_refinement_never_uses_text_or_manual_labels_as_anchors(self):
        try:import numpy as np
        except ImportError:self.skipTest('Requires acoustic environment')
        from localcall.session_diarization import refine_boundaries
        rows=[dict(start=10,end=11,speaker='A',source='manual'),
              dict(start=11,end=12,speaker='Non identificato',source='acoustic_unknown',text='a continuous sentence'),
              dict(start=12,end=13,speaker='B',source='voice')]
        def embed(a,b):raise AssertionError('Manual anchor must not start inference')
        result,n=refine_boundaries(rows,rows,{1:np.array([1.,0.]),2:np.array([0.,1.])},{1:'A',2:'B'},{},embed)
        self.assertEqual(result,rows);self.assertEqual(n,0)

    def test_multiscale_refinement_labels_both_edges_but_not_uncertain_cut(self):
        try:import numpy as np
        except ImportError:self.skipTest('Requires acoustic environment')
        from localcall.session_diarization import refine_boundaries
        rows=[dict(start=13,end=14,speaker='A',source='voice')]
        for a,b in [(14,14.4),(14.4,14.8),(14.8,15.2),(15.2,15.6),(15.6,16)]:
            rows.append(dict(start=a,end=b,speaker='Non identificato',source='acoustic_unknown',text='unaltered'))
        rows.append(dict(start=16,end=17,speaker='B',source='voice'))
        def embed(a,b):
            if b<=15:return np.array([1.,0.])
            if a>=15:return np.array([0.,1.])
            return np.array([2**-.5,2**-.5])
        out,n=refine_boundaries(rows,rows,{1:np.array([1.,0.]),2:np.array([0.,1.])},{1:'A',2:'B'},{1:{'support':4},2:{'support':4}},embed,(0,30))
        self.assertEqual(out[1]['speaker'],'A');self.assertEqual(out[-2]['speaker'],'B')
        self.assertEqual(out[3]['speaker'],'Non identificato')
        self.assertEqual([r.get('text') for r in out],[r.get('text') for r in rows])
