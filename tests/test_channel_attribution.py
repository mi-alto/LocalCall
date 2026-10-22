import unittest
from localcall.channel_attribution import attribute_single_remote,two_person_context

class ChannelAttributionTests(unittest.TestCase):
    def apply(self,rows,events,separate=True,**kwargs):
        return attribute_single_remote(rows,events,separate,**dict(dict(audio_source='remote',mic_intervals=[]),**kwargs))
    def test_requires_remote_source_local_identity_and_mic_silence(self):
        rows,events=self.data()
        for kwargs in ({'audio_source':'mixed'},{'mic_intervals':None},{'mic_intervals':[(20.6,21)]}):
            self.assertEqual(self.apply(rows,events,**kwargs),rows)
        events=[{k:v for k,v in e.items() if k!='self_name'} for e in events]
        self.assertEqual(self.apply(rows,events),rows)
        self.assertEqual(self.apply(rows,events,confirmed_two_person=True)[-1]['source'],'channel')
        self.assertEqual(self.apply(rows,events,self_name='Remote'),rows)
        rows[-1]['track']='mic'
        self.assertEqual(self.apply(rows,events,confirmed_two_person=True),rows)
    def data(self):
        events=[dict(t=i/2,speakers=['Remote'],self_name='Self',participants=['Self','Remote']) for i in range(61)]
        rows=[dict(start=i,end=i+1,speaker='Remote',source='voice',confidence=0) for i in range(12)]
        rows.append(dict(start=20,end=20.5,speaker='Non identificato',source='acoustic_unknown',text='unchanged',confidence=0,original_attribution={'speaker':'Remote','source':'dom','confidence':1}))
        return rows,events
    def test_fills_only_unknown_and_marks_channel_not_voice(self):
        rows,events=self.data();new=self.apply(rows,events,True)
        self.assertEqual(new[:-1],rows[:-1]);self.assertEqual(new[-1]['source'],'channel')
        self.assertTrue(new[-1]['channel_inferred']);self.assertEqual(new[-1]['text'],'unchanged')
        self.assertEqual(new[-1]['original_attribution'],rows[-1]['original_attribution'])
        self.assertEqual(rows[-1]['speaker'],'Non identificato')
    def test_requires_two_people_separate_tracks_and_single_acoustic_identity(self):
        rows,events=self.data()
        self.assertEqual(self.apply(rows,events,False),rows)
        for mode in ('third','other_active','acoustic_conflict','no_roster','too_short'):
            rows,events=self.data()
            if mode=='third':events[-1]['participants'].append('Third')
            if mode=='other_active':events[-1]['speakers']=['Third']
            if mode=='acoustic_conflict':rows[0]['speaker']='Third'
            if mode=='no_roster':events=[dict(t=e['t'],speakers=e['speakers']) for e in events]
            if mode=='too_short':events=events[:10]
            with self.subTest(mode=mode):self.assertEqual(self.apply(rows,events,True),rows)
    def test_stale_or_silent_browser_and_missing_roster_do_not_fill(self):
        for mode in ('stale','silent','roster'):
            rows,events=self.data()
            if mode=='stale':events=[e for e in events if e['t']<18 or e['t']>22]
            if mode=='silent':
                for e in events:
                    if 18<=e['t']<=22:e['speakers']=[]
            if mode=='roster':
                for e in events:
                    if 18<=e['t']<=22:e['participants']=[]
            with self.subTest(mode=mode):self.assertEqual(self.apply(rows,events,True),rows)
    def test_mic_and_manual_rows_are_not_changed(self):
        for source in ('manual','microphone'):
            rows,events=self.data();rows[-1]['source']=source
            self.assertEqual(self.apply(rows,events,True),rows)
    def test_grouping_and_exports_keep_provenance(self):
        from localcall.speaker import group_turns
        from localcall.diarize import export
        rows,events=self.data();new=self.apply(rows,events,True)
        row=new[-1];after=dict(row,start=20.5,end=21,source='voice',channel_inferred=False,text='next')
        merged=group_turns([row,after]);self.assertEqual(len(merged),1);self.assertTrue(merged[0]['channel_inferred'])
        for kind in ('txt','srt'):self.assertIn('canale remoto',export(merged,kind))

    def test_configured_alias_does_not_override_browser_identity(self):
        rows,events=self.data()
        self.assertEqual(self.apply(rows,events,self_name='Short alias')[-1]['source'],'channel')
        events=[{k:v for k,v in e.items() if k!='self_name'} for e in events]
        self.assertEqual(self.apply(rows,events,self_name='Short alias'),rows)
        self.assertEqual(self.apply(rows,events,self_name='Short alias',confirmed_two_person=True)[-1]['source'],'channel')
    def test_any_event_loss_disables_channel_inference(self):
        from localcall.channel_attribution import observations_complete
        self.assertTrue(observations_complete({}))
        for meta in ({'event_gaps':1},{'dropped_events':1},{'client_warnings':['Alcuni nomi non sono stati salvati. L’audio continua.']}):
            self.assertFalse(observations_complete(meta))
