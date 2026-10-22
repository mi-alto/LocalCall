"""Conservative, local-only contrast between separate microphone/remote profiles."""
import math


def recover(rows, windows, vectors, mic_intervals, remote_intervals, events,
            mic_embedding, name, diarization, max_references=256):
    import numpy as np
    def overlaps(intervals,a,b):
        return any(min(b,y)>max(a,x) for x,y in intervals)
    def bounded(values):
        if len(values)<=max_references:return values
        return [values[i] for i in np.linspace(0,len(values)-1,max_references).astype(int)]
    centroids,assigned=diarization.cluster_vectors(vectors)
    mapping,_=diarization.name_clusters(windows,assigned,events)
    if not mapping or set(mapping.values())!={name}:return rows
    remote_examples=bounded([((a,b),v) for (a,b),v,(c,s) in zip(windows,vectors,assigned)
        if c in mapping and s>=.75 and not overlaps(mic_intervals,a,b)])
    remote_refs=[v for span,v in remote_examples]
    remote_times=[span for span,v in remote_examples]
    local_windows=bounded([(a,b) for a,b in diarization.speech_windows(
        [dict(start=a,end=b) for a,b in mic_intervals])
        if not overlaps(remote_intervals,a-.25,b+.25)])
    local_refs=[v for a,b in local_windows if (v:=mic_embedding(a,b)) is not None]
    if len(remote_refs)<5 or len(local_refs)<5:return rows
    x=np.asarray(vectors)
    def scores(refs):
        return np.median(np.sort(x@np.asarray(refs).T,axis=1)[:,-5:],axis=1)
    # A query must not vote for itself through overlapping reference audio.
    matrix=x@np.asarray(remote_refs).T
    remote=[]
    for (a,b),similarities in zip(windows,matrix):
        independent=[s for (start,end),s in zip(remote_times,similarities) if min(b,end)<=max(a,start)]
        remote.append(float(np.median(np.sort(independent)[-5:])) if len(independent)>=5 else -1.)
    local=scores(local_refs)
    # Echo can change channel timbre: also compare simultaneous microphone audio.
    echo=set();queries=0
    unknown=[(r['start'],r['end']) for r in rows if r.get('source')=='acoustic_unknown']
    for i,((a,b),v,score,rival) in enumerate(zip(windows,vectors,remote,local)):
        if score<.4 or score-rival<.15 or not overlaps(unknown,a,b) or not overlaps(mic_intervals,a,b):continue
        if queries>=256:echo.add(i);continue
        queries+=1;near=mic_embedding(a,b)
        if near is not None and float(v@near)>=.8:echo.add(i)
    # The local profile is a competitor, never a license to label remote echo as self.
    decoded=[(0 if a>=.4 and a-b>=.15 and i not in echo else None,float(a)) for i,(a,b) in enumerate(zip(remote,local))]
    proposed=diarization.assign_words(rows,windows,decoded,{0:name},{0:{'support':len(remote_refs)}})
    result=[]
    for before,after in zip(rows,proposed):
        row=dict(before);result.append(row)
        if before.get('source')!='acoustic_unknown' or before.get('track')=='mic':continue
        if after.get('source')!='voice':continue
        if after.get('voice_similarity',0)<.4 or after.get('acoustic_coverage',0)<.75:continue
        row.update(speaker=name,source='voice',voice_recovered=True,confidence=0,
                   voice_similarity=after['voice_similarity'],voice_model='speechbrain/ecapa-voxceleb',
                   acoustic_coverage=after['acoustic_coverage'],
                   profile_recovery={'method':'paired-profiles-v1','remote_references':len(remote_refs),
                                     'local_references':len(local_refs),'threshold':.4,'margin':.15})
    return result


def validate(before,after,name):
    if before==after:return
    if before.get('source')!='acoustic_unknown' or before.get('track')=='mic':
        raise ValueError('Protected attribution changed')
    allowed={'speaker','source','voice_recovered','confidence','voice_similarity','voice_model',
             'acoustic_coverage','profile_recovery'}
    if {k:v for k,v in before.items() if k not in allowed}!={k:v for k,v in after.items() if k not in allowed}:
        raise ValueError('Changed transcript or provenance')
    if after.get('speaker')!=name or after.get('source')!='voice':raise ValueError('Unexpected speaker')
    for key,minimum in [('voice_similarity',.4),('acoustic_coverage',.75)]:
        value=after.get(key)
        if not isinstance(value,(int,float)) or not math.isfinite(value) or not minimum<=value<=1.001:
            raise ValueError('Invalid acoustic evidence')
    if after.get('confidence')!=0 or after.get('voice_recovered') is not True or after.get('voice_model')!='speechbrain/ecapa-voxceleb':raise ValueError('Invalid profile provenance')
    evidence=after.get('profile_recovery',{})
    if evidence.get('threshold')!=.4 or evidence.get('margin')!=.15:raise ValueError('Invalid profile thresholds')
    if evidence.get('method')!='paired-profiles-v1' or any(not 5<=evidence.get(k,0)<=256 for k in ('remote_references','local_references')):
        raise ValueError('Invalid reference evidence')
