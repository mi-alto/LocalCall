"""Audio-first session diarization, with independent browser-name attribution.

ECAPA embeddings + bounded average-linkage clustering. Text is never inspected.
This does not separate simultaneous voices; ambiguous windows remain unnamed.
"""
from collections import defaultdict
import math


DERIVED = {'speaker_check','speaker_proposal','context_inferred','voice_recovered',
           'voice_similarity','voice_model','acoustic_coverage','speaker_clusters',
           'name_support','diarization_method','original_attribution',
           'context_method','context_bounds','boundary_refinement'}


def protected(row):
    return row.get('source') in ('manual','microphone') or row.get('track')=='mic'


def speech_windows(words):
    """ASR/VAD timestamps delimit speech; windows ignore existing speaker labels."""
    runs=[]
    for row in sorted(words,key=lambda r:r['start']):
        a,b=row['start'],row['end']
        if not (math.isfinite(a) and math.isfinite(b) and b>a):
            continue
        if runs and a-runs[-1][1]<=.6:
            runs[-1][1]=max(b,runs[-1][1])
        else:
            runs.append([a,b])
    result=[]
    for a,b in runs:
        if b-a<1.5:
            continue
        t=a
        while t+3<=b:
            result.append((round(t,4),round(t+3,4)))
            t+=1.5
        last=(round(max(a,b-3),4),round(b,4))
        if not result or result[-1]!=last:
            result.append(last)
    return result


def exclusive_name(events,a,b):
    """Require >=85% one-name coverage, with no rival/multiple indicators."""
    from bisect import bisect_right
    times=[e['t'] for e in events]
    votes=defaultdict(float)
    for i in range(max(0,bisect_right(times,a)-1),len(events)):
        e=events[i]
        if e['t']>=b:break
        end=min(e['t']+1.25,events[i+1]['t'] if i+1<len(events) else b)
        overlap=max(0,min(b,end)-max(a,e['t']))
        if not overlap:continue
        names=set(e['speakers'])
        if len(names)>1:return None
        if names:votes[next(iter(names))]+=overlap
    if len(votes)!=1:return None
    name,duration=next(iter(votes.items()))
    return name if duration>=.85*(b-a) else None


def cluster_vectors(vectors, threshold=.65):
    """Bound quadratic memory with <=1,600 deterministic training windows.

    Remaining windows are classified against frozen centroids, never incrementally
    used as training evidence. Multiple acoustic clusters may map to one person.
    """
    import numpy as np
    from scipy.cluster.hierarchy import linkage,fcluster
    n=len(vectors)
    if n<2:return {},[]
    x=np.asarray(vectors,dtype=np.float32)
    indices=np.unique(np.linspace(0,n-1,min(n,1600)).astype(int))
    labels=fcluster(linkage(x[indices],method='average',metric='cosine'),t=threshold,criterion='distance')
    centroids={}
    for label in sorted(set(labels)):
        members=x[indices[labels==label]]
        if len(members)<3:continue
        c=members.mean(axis=0);norm=np.linalg.norm(c)
        if norm:centroids[int(label)]=c/norm
    assigned=[]
    for v in x:
        ranked=sorted(((int(k),float(v@c)) for k,c in centroids.items()),key=lambda t:t[1],reverse=True)
        if not ranked or ranked[0][1]<.55 or (len(ranked)>1 and ranked[0][1]-ranked[1][1]<.1):
            assigned.append((None,ranked[0][1] if ranked else 0))
        else:assigned.append(ranked[0])
    return centroids,assigned


def name_clusters(windows,assigned,events):
    votes=defaultdict(lambda:defaultdict(list))
    for (a,b),(cluster,score) in zip(windows,assigned):
        if cluster is None or score<.65:continue
        name=exclusive_name(events,a,b)
        if name:
            samples=votes[cluster][name]
            # Nonadjacent observations prevent one stale UI indicator dominating.
            if not samples or a-samples[-1]>=8:samples.append(a)
    mapping={};evidence={}
    for cluster,names in votes.items():
        ranked=sorted(((len(ts),name,ts) for name,ts in names.items()),reverse=True)
        count,name,times=ranked[0];total=sum(len(ts) for ts in names.values())
        runner=ranked[1][0] if len(ranked)>1 else 0
        if count>=3 and times[-1]-times[0]>=20 and count/total>=.8 and count-runner>=2:
            mapping[cluster]=name
            evidence[cluster]={'name':name,'support':count,'share':count/total,'sample_times':times}
    return mapping,evidence


def assign_words(words,windows,assigned,mapping,evidence):
    result=[]
    for row in words:
        if protected(row):
            result.append(dict(row));continue
        a,b=row['start'],row['end'];votes=defaultdict(float);scores=defaultdict(list);clusters=defaultdict(set)
        total=0;covered=[]
        for (start,end),(cluster,score) in zip(windows,assigned):
            if start>=b:break
            overlap=max(0,min(b,end)-max(a,start))
            if not overlap:continue
            total+=overlap
            covered.append((max(a,start),min(b,end)))
            if cluster in mapping:
                name=mapping[cluster];votes[name]+=overlap;scores[name].append(score);clusters[name].add(cluster)
        fixed=dict(row)
        fixed['original_attribution']=row.get('original_attribution') or {k:row.get(k,0 if k=='confidence' else None) for k in ('speaker','source','confidence')}
        # A named DOM row is also audited: no bypass for a possibly stale UI name.
        fixed.update(speaker='Non identificato',source='acoustic_unknown',confidence=0,
                     diarization_method='ecapa-session-v1')
        for key in DERIVED - {'diarization_method','original_attribution'}:
            fixed.pop(key,None)
        duration=0;edge=a
        for start,end in covered:
            duration+=max(0,end-max(edge,start));edge=max(edge,end)
        ranked=sorted(votes.items(),key=lambda t:t[1],reverse=True)
        if duration>=.75*(b-a) and ranked and total and ranked[0][1]/total>=.75:
            name,weight=ranked[0]
            runner=ranked[1][1] if len(ranked)>1 else 0
            if (weight-runner)/total>=.5:
                fixed.update(speaker=name,source='voice',voice_similarity=round(min(scores[name]),4),
                    voice_model='speechbrain/ecapa-voxceleb',voice_recovered=True,
                    acoustic_coverage=round(weight/total,4),speaker_clusters=sorted({c for state in clusters[name] for c in evidence[state].get('cluster_ids',[state])}),
                    name_support=min(evidence[c]['support'] for c in clusters[name]))
        result.append(fixed)
    return result


def diarize(words,events,embedding,cache_path=None,speech_intervals=None,audio_range=None):
    windows=[];vectors=[]
    regions=[r for r in words if not protected(r)] if speech_intervals is None else [dict(start=a,end=b) for a,b in speech_intervals]
    for a,b in speech_windows(regions):
        if audio_range is not None:
            a,b=max(a,audio_range[0]),min(b,audio_range[1])
        if b-a<1.5:continue
        vector=embedding(a,b)
        if vector is not None:
            windows.append((a,b));vectors.append(vector)
    if cache_path:
        import numpy as np
        np.savez_compressed(cache_path,windows=windows,vectors=vectors)
    centroids,assigned=cluster_vectors(vectors)
    events=sorted(events,key=lambda e:e['t'])
    mapping,evidence=name_clusters(windows,assigned,events)
    decoded,names,support=decode_voices(windows,vectors,centroids,mapping,evidence)
    rows=assign_words(words,windows,decoded,names,support)
    rows,refinement_queries=refine_boundaries(words,rows,centroids,mapping,evidence,embedding,audio_range)
    return rows,{'windows':len(windows),'clusters':len(centroids),'named_clusters':len(mapping),
                 'named_words':sum(r['source']=='voice' for r in rows),'total_words':len(rows),'refinement_queries':refinement_queries,
                 'warning': 'No reliable browser-name matches' if windows and not mapping else None}


def decode_voices(windows,vectors,centroids,mapping,evidence,switch_cost=.12):
    """Viterbi over acoustic name scores, with an explicit unknown state.

    Names only index previously matched acoustic clusters. No transcript text or
    current browser indicator affects decoding. Silence resets temporal continuity.
    """
    import numpy as np
    names=sorted(set(mapping.values()))
    if not names:return [(None,0)]*len(windows),{},{}
    x=np.asarray(vectors,dtype=np.float32)
    columns=[]
    for name in names:
        refs=np.asarray([centroids[c] for c,n in mapping.items() if n==name])
        columns.append((x@refs.T).max(axis=1))
    scores=np.stack(columns,axis=1)
    unknown=np.full(len(x),.45)
    unnamed=[c for k,c in centroids.items() if k not in mapping]
    if unnamed:
        unknown=np.maximum(unknown,(x@np.asarray(unnamed).T).max(axis=1)-.05)
    emissions=np.column_stack([scores,unknown])
    states=len(names)+1
    decoded=[];begin=0
    while begin<len(windows):
        end=begin+1
        while end<len(windows) and windows[end][0]-windows[end-1][1]<=.6:end+=1
        back=np.zeros((end-begin,states),dtype=np.int32)
        cost=-emissions[begin]
        for i in range(begin+1,end):
            transitions=cost[:,None]+switch_cost*(1-np.eye(states))
            back[i-begin]=transitions.argmin(axis=0)
            cost=transitions.min(axis=0)-emissions[i]
        state=int(cost.argmin());path=[state]
        for i in range(end-begin-1,0,-1):state=int(back[i,state]);path.append(state)
        decoded.extend(reversed(path));begin=end
    assigned=[]
    for i,state in enumerate(decoded):
        if state==len(names):assigned.append((None,0));continue
        score=float(scores[i,state])
        competitors=np.delete(scores[i],state)
        # Smoothing cannot override a clear local voice change.
        if score<.45 or score<unknown[i] or (len(competitors) and score<float(competitors.max())-.08):
            assigned.append((None,score))
        else:assigned.append((state,score))
    mapped={i:name for i,name in enumerate(names)}
    support={i:{'support':min(evidence[c]['support'] for c,n in mapping.items() if n==name),'cluster_ids':[c for c,n in mapping.items() if n==name]} for i,name in mapped.items()}
    return assigned,mapped,support


def validate_result(before,after,names):
    """Validate worker output without loading the acoustic dependencies in the server."""
    if not isinstance(after,dict):raise ValueError('Invalid diarization row')
    if protected(before):
        if before!=after:raise ValueError('Changed protected track or manual correction')
        return
    for key,value in before.items():
        if key not in DERIVED | {'speaker','source','confidence'} and after.get(key)!=value:
            raise ValueError('Diarization changed transcript or timing')
    if after.get('diarization_method')!='ecapa-session-v1' or after.get('confidence')!=0:
        raise ValueError('Invalid diarization provenance')
    original=before.get('original_attribution') or {k:before.get(k,0 if k=='confidence' else None) for k in ('speaker','source','confidence')}
    if after.get('original_attribution')!=original:raise ValueError('Lost original evidence')
    if after.get('source')=='acoustic_unknown':
        if after.get('speaker')!='Non identificato':raise ValueError('Invented unknown name')
        return
    if after.get('source')!='voice' or after.get('speaker') not in names:raise ValueError('Invalid voice name')
    for field,minimum in [('voice_similarity',.45),('acoustic_coverage',.75)]:
        value=after.get(field)
        if not isinstance(value,(float,int)) or not math.isfinite(value) or not minimum<=value<=1:
            raise ValueError('Invalid acoustic score')
    if not isinstance(after.get('name_support'),int) or after['name_support']<3:raise ValueError('Insufficient name support')
    if not isinstance(after.get('speaker_clusters'),list) or not after['speaker_clusters'] or any(type(c)!=int or c<0 for c in after['speaker_clusters']):raise ValueError('Invalid voice identity')


def refine_boundaries(words,rows,centroids,mapping,evidence,embedding,audio_range=None,max_queries=768):
    """Refine short unnamed gaps between different acoustic speakers.

    Compare both sides of each possible change point at three time scales. Keep
    a collar around all near-optimal cuts unknown; never simply extend a name.
    Frozen input rows prevent recovered words becoming new reference anchors.
    """
    import numpy as np
    names=sorted(set(mapping.values()));result=[dict(r) for r in rows];i=0;queries=0
    named_refs={n:np.asarray([c for k,c in centroids.items() if mapping.get(k)==n]) for n in names}
    unnamed=np.asarray([c for k,c in centroids.items() if k not in mapping])
    def scores(a,b):
        nonlocal queries
        if queries>=max_queries:return None
        if audio_range and (a<audio_range[0] or b>audio_range[1]):return None
        v=embedding(round(a,4),round(b,4));queries+=1
        if v is None:return None
        return {n:float((named_refs[n]@v).max()) for n in names},float((unnamed@v).max()) if len(unnamed) else 0
    while i<len(rows):
        if rows[i]['source']!='acoustic_unknown':i+=1;continue
        first=i
        while i<len(rows) and rows[i]['source']=='acoustic_unknown':i+=1
        if first==0 or i==len(rows):continue
        left,right=rows[first-1],rows[i];a,b=rows[first]['start'],rows[i-1]['end']
        if (left['source']!='voice' or right['source']!='voice' or left['speaker']==right['speaker']
                or left['speaker'] not in names or right['speaker'] not in names
                or b-a>8 or b-a<.5 or a-left['end']>.3 or right['start']-b>.3
                or any(y['start']-x['end']>.6 for x,y in zip(rows[first:i],rows[first+1:i]))):continue
        ln,rn=left['speaker'],right['speaker']
        # Do not borrow context across a third or another observed acoustic turn.
        if any(r['source']=='voice' and r['speaker']!=ln and r['end']>a-6 and r['start']<a for r in rows[:first]):continue
        if any(r['source']=='voice' and r['speaker']!=rn and r['start']<b+6 and r['end']>b for r in rows[i:]):continue
        candidates=[]
        for tick in range(math.ceil(a*4),math.floor(b*4)+1):
            t=tick/4;ls=[];rs=[];margins=[];unknown_margins=[]
            for length in (3,4.5,6):
                l=scores(t-length,t);r=scores(t,t+length)
                if l is None or r is None:break
                ls.append(l[0][ln]);rs.append(r[0][rn])
                margins.extend([l[0][ln]-max(v for n,v in l[0].items() if n!=ln),r[0][rn]-max(v for n,v in r[0].items() if n!=rn)])
                unknown_margins.extend([l[0][ln]-l[1],r[0][rn]-r[1]])
            if len(ls)==3:candidates.append((sum(ls+rs)/6,t,ls,rs,margins,unknown_margins))
        if not candidates:continue
        best=max(candidates,key=lambda c:c[0]);_,cut,ls,rs,margins,unknown_margins=best
        if (min(sum(ls)/3,sum(rs)/3)<.55 or min(ls+rs)<.4
                or sum(margins)/6<.15 or sum(unknown_margins)/6<-.05):continue
        plausible=[c[1] for c in candidates if c[0]>=best[0]-.05]
        low,high=min(plausible)-.5,max(plausible)+.5
        for j in range(first,i):
            row=rows[j];duration=row['end']-row['start']
            if duration<=0:continue
            before=max(0,min(row['end'],low)-row['start'])/duration
            after=max(0,row['end']-max(row['start'],high))/duration
            if max(before,after)<.75:continue
            name,score,coverage=(ln,sum(ls)/3,before) if before>after else (rn,sum(rs)/3,after)
            clusters=[k for k,n in mapping.items() if n==name]
            result[j].update(speaker=name,source='voice',voice_similarity=round(score,4),
                voice_model='speechbrain/ecapa-voxceleb',voice_recovered=True,
                acoustic_coverage=round(min(1,coverage),4),speaker_clusters=clusters,
                name_support=min(evidence[c]['support'] for c in clusters),
                boundary_refinement={'method':'multiscale-change-point-v1','cut':cut,'uncertain_interval':[low,high]})
    return result,queries
