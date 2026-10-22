"""Explicit channel-based attribution for verified two-person browser calls.

This is evidence about the remote audio source, not a voice match. It never uses
transcript wording and is disabled if the session roster or speakers conflict.
"""
from bisect import bisect_right
import math
from .session_diarization import exclusive_name


def two_person_context(events,separate_microphone,self_name=None,confirmed_two_person=False):
    if not separate_microphone:return None
    roster=set();active=set();pairs=[];selves=set()
    for e in events:
        if not isinstance(e.get('t'),(int,float)) or not math.isfinite(e['t']):return None
        if e.get('self_name'):
            if not isinstance(e['self_name'],str):return None
            selves.add(e['self_name'])
        people=e.get('participants',[]);speakers=e.get('speakers',[])
        if not isinstance(people,list) or not isinstance(speakers,list):return None
        if any(not isinstance(n,str) or not n.strip() for n in people+speakers):return None
        roster.update(people);active.update(speakers)
        if len(set(people))==2:pairs.append(e['t'])
        if len(roster)>2 or len(active)>1:return None
    if len(roster)!=2 or len(active)!=1 or len(pairs)<20 or max(pairs)-min(pairs)<10:return None
    name=next(iter(active))
    if name not in roster:return None
    if not selves and self_name in roster:selves.add(self_name)
    if selves and (len(selves)!=1 or roster-{name}!=selves):return None
    if not selves and not confirmed_two_person:return None
    return name,roster


def sole_remote(rows,events,separate_microphone,self_name=None,confirmed_two_person=False):
    context=two_person_context(events,separate_microphone,self_name,confirmed_two_person)
    if context is None:return None
    name,roster=context
    voice=[r for r in rows if r.get('source')=='voice' and not r.get('short_refinement')]
    if not voice or {r['speaker'] for r in voice}!={name}:return None
    if sum(max(0,r['end']-r['start']) for r in voice)<10:return None
    return name,roster


def attribute_single_remote(rows,events,separate_microphone=False,padding=.5,*,self_name=None,confirmed_two_person=False,mic_intervals=None,audio_source=None):
    """Only fill unresolved words with fresh, matching roster AND active signal."""
    if audio_source!="remote" or mic_intervals is None:return [dict(r) for r in rows]
    context=sole_remote(rows,events,separate_microphone,self_name,confirmed_two_person)
    if context is None:return [dict(r) for r in rows]
    name,roster=context;events=sorted(events,key=lambda e:e['t']);times=[e['t'] for e in events]
    result=[]
    for original in rows:
        row=dict(original);result.append(row)
        if row.get('source')!='acoustic_unknown' or row.get('track')=='mic':continue
        if any(min(row['end'],end+.25)>max(row['start'],start-.25) for start,end in mic_intervals):continue
        a,b=max(0,row['start']-padding),row['end']+padding
        if b<=a or exclusive_name(events,a,b)!=name:continue
        duration=0
        for i in range(max(0,bisect_right(times,a)-1),len(events)):
            e=events[i]
            if e['t']>=b:break
            stop=min(e['t']+1.25,events[i+1]['t'] if i+1<len(events) else b)
            if set(e.get('participants',[]))==roster:duration+=max(0,min(b,stop)-max(a,e['t']))
        if duration/(b-a)<.85:continue
        row.update(speaker=name,source='channel',confidence=0,channel_inferred=True,attribution_method='two-person-fresh-dom-v1',
                   channel_evidence={'method':'two-person-fresh-dom-v1','roster_size':2,'start':a,'end':b,'roster_coverage':round(duration/(b-a),4)})
        row.pop('diarization_method',None)
    return result

def observations_complete(meta):
    """Lost browser batches veto inference from the absence of other people."""
    return not (meta.get('event_gaps') or meta.get('dropped_events') or
                any('nomi non sono stati salvati' in w for w in meta.get('client_warnings',[])))
