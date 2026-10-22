"""Bounded, frozen-reference audit. Suggestions never overwrite speaker labels."""
import math
from functools import lru_cache

MAX_REFERENCE_TURNS = 6
COARSE_STEP = 9.0
WINDOW = 3.0
MIN_SECONDS = 1.5
MIN_WINNER = .55
MAX_ASSIGNED = .35
MIN_MARGIN = .20


def reference_plan(anchors):
    """One interior sample per turn, spread through the session; no self-training."""
    by_name = {}
    for turn, row in enumerate(anchors):
        if row.get('source') not in ('dom','manual') or row.get('timing_adjusted'):
            continue
        if row['source']=='manual' and not row.get('user_confirmed'):
            continue
        if row['source']=='dom' and row.get('confidence',0)<.85:
            continue
        a,b=row['start']+1.25,row['end']-1.25
        if b-a<3:
            continue
        center=(a+b)/2
        by_name.setdefault(row['speaker'],[]).append(dict(
            start=center-1.5,end=center+1.5,turn=turn,
            turn_start=row['start'],turn_end=row['end'],
            provenance='human' if row['source']=='manual' else 'dom'))
    result={}
    for name,spans in by_name.items():
        spans.sort(key=lambda s:s['start'])
        count=min(MAX_REFERENCE_TURNS,len(spans))
        ids=sorted({round(i*(len(spans)-1)/max(1,count-1)) for i in range(count)})
        result[name]=[spans[i] for i in ids]
    return result


def audit_runs(words):
    """Continuous remote speech, including transitions; never cross silence/mic/manual."""
    runs=[]
    for i,r in enumerate(words):
        if r.get('source') not in ('dom','missing','transition','overlap') or r.get('track','remote')!='remote':
            continue
        if runs and runs[-1][-1]==i-1 and r['start']-words[i-1]['end']<.3:
            runs[-1].append(i)
        else:
            runs.append([i])
    return runs


def audit_words(words, anchors, embedding, coherent_reference):
    """Return review-only suggestions and counts, using frozen, held-out references."""
    words=clean_audit(words)
    plan=reference_plan(anchors);bank={};stats={'reference_embeddings':0,'query_embeddings':0,'coarse_windows':0,'fine_windows':0}
    for name,spans in plan.items():
        for span in spans:
            v=embedding(span['start'],span['end']);stats['reference_embeddings']+=1
            if v is not None:
                bank.setdefault(name,[]).append(dict(span,vector=list(v)))
    @lru_cache(maxsize=128)
    def centroid(name,turns):
        return coherent_reference([(r['vector'],r['turn']) for r in bank[name] if r['turn'] in turns])
    @lru_cache(maxsize=512)
    def scores(a,b):
        # Exclude the entire reference turn containing the query, not just its sample.
        centers={}
        for name,refs in bank.items():
            eligible=[r for r in refs if r['turn_end']<=a or r['turn_start']>=b]
            c=centroid(name,tuple(r['turn'] for r in eligible))
            if c is not None:
                centers[name]=c
        if len(centers)<2:
            return None
        v=embedding(a,b);stats['query_embeddings']+=1
        if v is None:
            return None
        return {name:float(sum(x*y for x,y in zip(v,c))) for name,c in centers.items()}
    def decision(values,assigned):
        if values is None or assigned not in values:
            return None
        ranked=sorted(values,key=values.get,reverse=True)
        winner=ranked[0]
        if (winner==assigned or values[winner]<MIN_WINNER or values[assigned]>MAX_ASSIGNED
                or values[winner]-values[ranked[1]]<MIN_MARGIN):
            return None
        return winner
    proposals={};checks={}
    for ids in audit_runs(words):
        start=words[ids[0]]['start'];stop=max(words[i]['end'] for i in ids)
        if stop-start<WINDOW:
            continue
        probes={round(start,3),round(stop-WINDOW,3)}
        t=start
        while t+WINDOW<=stop:
            probes.add(round(t,3));t+=COARSE_STEP
        # Sample both sides of observed label changes and ambiguous regions.
        for prev,i in zip(ids,ids[1:]):
            if words[prev]['speaker']!=words[i]['speaker'] or words[prev]['source']!=words[i]['source']:
                for t in (words[i]['start']-WINDOW,words[i]['start']-WINDOW/2,words[i]['start']):
                    probes.add(round(max(start,min(t,stop-WINDOW)),3))
        suspects=[]
        for a in sorted(probes):
            b=min(a+WINDOW,stop);values=scores(a,b);stats['coarse_windows']+=1
            if values:
                for i in ids:
                    r=words[i]
                    if r['source']=='dom' and a<=r['start'] and r['end']<=b and r['speaker'] in values:
                        checks.setdefault(i,[]).append(values[r['speaker']])
            # Low similarity alone never triggers a relabel suggestion.
            if any(decision(values,words[i]['speaker']) for i in ids
                   if words[i]['source']=='dom' and words[i]['start']<b and words[i]['end']>a):
                suspects.append((max(start,a-1.5),min(stop,b+1.5)))
        fine=set()
        for a,b in suspects:
            if b-a>=WINDOW:
                fine.add((round(b-WINDOW,3),round(b,3)))
            while a+WINDOW<=b+.00001:
                fine.add((round(a,3),round(a+WINDOW,3)));a+=1.5
        for a,b in sorted(fine):
            stats['fine_windows']+=1
            mid=(a+b)/2
            full,left,right=scores(a,b),scores(a,mid),scores(mid,b)
            for i in ids:
                row=words[i]
                if row['source']!='dom' or row['start']<a or row['end']>b:
                    continue
                name=decision(full,row['speaker'])
                if not name or decision(left,row['speaker'])!=name or decision(right,row['speaker'])!=name:
                    proposals[i]={'conflict':True}
                    continue
                proposal=dict(speaker=name,assigned_speaker=row['speaker'],
                    similarity=round(min(v[name] for v in (full,left,right)),3),
                    assigned_similarity=round(max(v[row['speaker']] for v in (full,left,right)),3),
                    window_start=a,window_end=b,method='ecapa-audit-v1',status='needs_review')
                if proposals.get(i,{}).get('conflict'):
                    continue
                if i in proposals and proposals[i]['speaker']!=name:
                    proposals[i]={'conflict':True}
                else:
                    proposals[i]=proposal
    result=[dict(r) for r in words]
    for i,p in proposals.items():
        if not p.get('conflict'):
            result[i]['speaker_proposal']=p
    for i,values in checks.items():
        if len(values)>=2 and max(values)<=MAX_ASSIGNED and 'speaker_proposal' not in result[i]:
            result[i]['speaker_check']={'status':'uncertain','method':'ecapa-audit-v1','assigned_similarity':round(max(values),3)}
    stats['dom_words_checked']=len(checks)
    stats['dom_words_total']=sum(r['source']=='dom' for r in words)
    stats['flagged_words']=sum('speaker_check' in r for r in result)
    stats['proposed_words']=sum('speaker_proposal' in r for r in result)
    return result,stats


def validate_proposal(row,proposal,known_names):
    if row['source']!='dom' or not isinstance(proposal,dict):
        raise ValueError('Invalid proposal source')
    if (proposal.get('status')!='needs_review' or proposal.get('method')!='ecapa-audit-v1'
            or proposal.get('speaker') not in known_names or proposal['speaker']==row['speaker']
            or proposal.get('assigned_speaker')!=row['speaker']):
        raise ValueError('Invalid proposed name')
    for key in ('similarity','assigned_similarity','window_start','window_end'):
        v=proposal.get(key)
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v):
            raise ValueError('Invalid proposal value')
    if (not MIN_WINNER<=proposal['similarity']<=1 or not -1<=proposal['assigned_similarity']<=MAX_ASSIGNED
            or proposal['window_start']>row['start'] or proposal['window_end']<row['end']
            or proposal['similarity']-proposal['assigned_similarity']<MIN_MARGIN-1e-6
            or abs(proposal['window_end']-proposal['window_start']-WINDOW)>.001):
        raise ValueError('Invalid proposal evidence')


def reference_names(anchors):
    return {name for name,spans in reference_plan(anchors).items() if len(spans)>=2}


def can_audit(words,anchors):
    return (sum(len(spans)>=2 for spans in reference_plan(anchors).values())>=2
            and any(words[ids[-1]]['end']-words[ids[0]]['start']>=WINDOW for ids in audit_runs(words)))


def clean_audit(words):
    return [{k:v for k,v in row.items() if k not in ('speaker_proposal','speaker_check')} for row in words]


def validate_check(row,check):
    if row['source']!='dom' or not isinstance(check,dict):
        raise ValueError('Invalid check source')
    score=check.get('assigned_similarity')
    if (check.get('status')!='uncertain' or check.get('method')!='ecapa-audit-v1'
            or isinstance(score,bool) or not isinstance(score,(int,float)) or not math.isfinite(score)
            or not -1<=score<=MAX_ASSIGNED):
        raise ValueError('Invalid check evidence')


def merge_audit(audited,resolved):
    if len(audited)!=len(resolved):
        raise ValueError('Mismatched word count')
    result=clean_audit(resolved)
    for before,after in zip(audited,result):
        if any(before[k]!=after[k] for k in ('start','end','text')):
            raise ValueError('Mismatched word timing/text')
        for key in ('speaker_proposal','speaker_check'):
            if key in before:
                after[key]=before[key]
    return result
