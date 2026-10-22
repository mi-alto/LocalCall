import unittest
from localcall.speaker import coherent_reference,group_turns
from localcall.speaker_audit import audit_words,reference_plan,validate_proposal


def row(start,end,name='A',source='dom'):
    return dict(start=start,end=end,speaker=name,source=source,text='test',confidence=1)


class AuditTests(unittest.TestCase):
    def anchors(self):
        return [row(0,8),row(10,18),row(20,28),row(30,38,'B'),row(40,48,'B'),row(50,58,'B')]
    def embed(self,a,b):
        return [1.,0.] if a<30 else [0.,1.]
    def test_proposes_without_overwriting_and_preserves_evidence(self):
        words=[row(60,61),row(61,62),row(62,63)]
        result,stats=audit_words(words,self.anchors(),self.embed,coherent_reference)
        self.assertEqual(stats['proposed_words'],3)
        for original,changed in zip(words,result):
            self.assertEqual(changed['speaker'],'A')
            self.assertEqual(changed['speaker_proposal']['speaker'],'B')
            validate_proposal(original,changed['speaker_proposal'],{'A','B'})
            self.assertEqual({k:v for k,v in changed.items() if k!='speaker_proposal'},original)
    def test_low_similarity_without_winner_is_not_correction(self):
        words=[row(60,63)]
        def embed(a,b):return [.1,.1] if a>=60 else self.embed(a,b)
        result,_=audit_words(words,self.anchors(),embed,coherent_reference)
        self.assertNotIn('speaker_proposal',result[0])
    def test_conflicting_halves_abstain(self):
        def embed(a,b):
            if a>=60 and a<61.5 and b-a<2:return [1.,0.]
            return self.embed(a,b)
        result,_=audit_words([row(60,61),row(61,62),row(62,63)],self.anchors(),embed,coherent_reference)
        self.assertTrue(all('speaker_proposal' not in r for r in result))
    def test_cannot_use_reference_turn_to_verify_itself(self):
        anchors=[row(60,70),row(0,8),row(30,38,'B'),row(40,48,'B')]
        def embed(a,b):return [1.,0.] if 30<=a<50 else [0.,1.]
        result,_=audit_words([row(62,65,'B')],anchors,embed,coherent_reference)
        self.assertNotIn('speaker_proposal',result[0])
        anchors[0]=row(10,18)
        result,_=audit_words([row(62,65,'B')],anchors,embed,coherent_reference)
        self.assertEqual(result[0]['speaker_proposal']['speaker'],'A')
    def test_sparse_stable_audio_does_not_trigger_fine_scan(self):
        words=[row(i,i+1,'B') for i in range(60,150)]
        result,stats=audit_words(words,self.anchors(),self.embed,coherent_reference)
        self.assertEqual(stats['fine_windows'],0)
        self.assertLessEqual(stats['coarse_windows'],12)
        self.assertEqual(result,words)
    def test_reference_budget_and_no_self_training(self):
        anchors=[row(i*10,i*10+8) for i in range(30)]
        anchors.extend([row(500,508,'Fake','voice'),row(510,518,'Fake','manual')])
        refs=reference_plan(anchors)
        self.assertEqual(len(refs['A']),6)
        self.assertNotIn('Fake',refs)
        anchors.append(dict(row(520,528,'Human','manual'),user_confirmed=True))
        self.assertEqual(reference_plan(anchors)['Human'][0]['provenance'],'human')
    def test_manual_and_mic_labels_are_untouched(self):
        words=[row(60,65,source='manual'),row(65,70,source='microphone')]
        result,_=audit_words(words,self.anchors(),self.embed,coherent_reference)
        self.assertEqual(result,words)
    def test_grouping_does_not_spread_a_proposal(self):
        a,b=row(60,61),row(61,62)
        b['speaker_proposal']={'speaker':'B'}
        self.assertEqual(len(group_turns([a,b])),2)
    def test_rejects_forged_proposal(self):
        proposal={'speaker':'B','assigned_speaker':'A','method':'ecapa-audit-v1','status':'needs_review','similarity':.8,'assigned_similarity':.1,'window_start':60,'window_end':63}
        validate_proposal(row(60,61),proposal,{'A','B'})
        for key,value in [('similarity',float('nan')),('window_start',62),('speaker','Unknown'),('status','accepted')]:
            with self.assertRaises(ValueError):validate_proposal(row(60,61),dict(proposal,**{key:value}),{'A','B'})

    def test_tail_of_run_is_reviewed(self):
        words=[row(60,61),row(61,62),row(62,63),row(63,64)]
        result,_=audit_words(words,self.anchors(),self.embed,coherent_reference)
        self.assertEqual(result[-1]['speaker_proposal']['speaker'],'B')

    def test_label_changes_increase_sampling(self):
        words=[row(i,i+1,'A' if i%10<5 else 'B') for i in range(60,150)]
        _,stats=audit_words(words,self.anchors(),self.embed,coherent_reference)
        self.assertGreater(stats['coarse_windows'],12)
        self.assertGreater(stats['fine_windows'],0)

    def test_mic_track_splits_audit_runs(self):
        from localcall.speaker_audit import audit_runs
        words=[row(60,62),dict(row(62,64),track='mic'),row(64,66)]
        self.assertEqual(audit_runs(words),[[0],[2]])

    def test_uncertain_flag_does_not_invent_a_name(self):
        def embed(a,b):return [.1,.1] if a>=60 else self.embed(a,b)
        words=[row(i,i+1) for i in range(60,64)]
        result,stats=audit_words(words,self.anchors(),embed,coherent_reference)
        self.assertGreater(stats['flagged_words'],0)
        self.assertTrue(all(r['speaker']=='A' and 'speaker_proposal' not in r for r in result))

    def test_session_parent_rejects_legacy_audit_proposals(self):
        import json,tempfile
        from pathlib import Path
        from unittest.mock import patch
        from types import SimpleNamespace
        from localcall.speaker import recover
        anchors=self.anchors()
        for r in anchors:
            if r['speaker']=='B':r.update(source='manual',user_confirmed=True)
        words=[row(60,63)]
        proposed={'speaker':'B','assigned_speaker':'A','method':'ecapa-audit-v1','status':'needs_review','similarity':.8,'assigned_similarity':.1,'window_start':60,'window_end':63}
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for f in ['.speaker-env/bin/python']+['models/speaker-ecapa/'+n for n in ('.ready','embedding_model.ckpt','hyperparams.yaml','mean_var_norm_emb.ckpt','classifier.ckpt','label_encoder.txt')]:
                p=root/f;p.parent.mkdir(parents=True,exist_ok=True);p.touch()
            for name in ['B','Fake']:
                output=[dict(words[0],speaker_proposal=dict(proposed,speaker=name))]
                with patch('localcall.speaker.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=json.dumps(output))):
                    result,warning=recover(root,root/'audio.wav',words,anchors,[],0)
                self.assertIsNotNone(warning)
                self.assertEqual(result,words)

    def test_half_window_with_fractional_offset(self):
        from localcall.speaker import audio_bounds
        for offset in [.1, .1234, 12.789]:
            self.assertIsNotNone(audio_bounds(218.69,220.19,offset,300))

    def test_rerun_removes_stale_annotations(self):
        words=[dict(row(60,63,'B'),speaker_proposal={'speaker':'A'},speaker_check={'status':'uncertain'})]
        result,_=audit_words(words,self.anchors(),self.embed,coherent_reference)
        self.assertEqual(result,[row(60,63,'B')])

    def test_check_validation_and_merge(self):
        from localcall.speaker_audit import validate_check,merge_audit
        valid={'method':'ecapa-audit-v1','status':'uncertain','assigned_similarity':.1}
        validate_check(row(0,1),valid)
        for key,value in [('assigned_similarity',True),('assigned_similarity',.5),('method','fake')]:
            with self.assertRaises(ValueError):validate_check(row(0,1),dict(valid,**{key:value}))
        with self.assertRaises(ValueError):validate_check(row(0,1,source='microphone'),valid)
        audited=[dict(row(0,1),speaker_check=valid)]
        self.assertEqual(merge_audit(audited,[row(0,1)]),audited)
        with self.assertRaises(ValueError):merge_audit(audited,[row(1,2)])

    def test_single_turn_name_cannot_validate(self):
        from localcall.speaker_audit import reference_names
        self.assertNotIn('Only',reference_names([row(0,8,'Only')]))

    def test_disagreeing_fine_window_vetoes_shared_word(self):
        def embed(a,b):
            if a>=60 and a>=62.5:return [1.,0.]
            return self.embed(a,b)
        words=[row(60,61),row(61,62),row(62,63),row(63,64)]
        result,_=audit_words(words,self.anchors(),embed,coherent_reference)
        self.assertNotIn('speaker_proposal',result[2])
