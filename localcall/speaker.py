"""Conservative local speaker recovery and readable turn grouping.

ECAPA scores are similarities, not calibrated probabilities. This is targeted
speaker verification, not an overlap detector or unrestricted diarization.
"""
from pathlib import Path
import json
import subprocess
import sys

MIN_SCORE = .45
MIN_MARGIN = .15


def choose(scores, candidates):
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    if len(ranked) < 2:
        return None
    name, score = ranked[0]
    if name not in candidates or score < MIN_SCORE or score-ranked[1][1] < MIN_MARGIN:
        return None
    return name


def possible_echo(row, remote_words):
    """Flag substantial coincident text as possible echo, never short acknowledgements."""
    import re
    from collections import Counter
    local = re.findall(r"\w+", row['text'].casefold())
    remote = re.findall(r"\w+", ' '.join(r['text'] for r in remote_words
                         if min(row['end']+.25,r['end']) > max(row['start']-.25,r['start'])).casefold())
    if min(len(local),len(remote)) < 3:
        return False
    matched=sum((Counter(local)&Counter(remote)).values())
    return matched/len(local)>=.9 and matched/len(remote)>=.9


def group_turns(rows):
    """Keep original attribution evidence while presenting contiguous known turns."""
    result = []
    for original in rows:
        row = dict(original)
        row['voice_recovered'] = bool(row.get('voice_recovered') or row['source']=='voice')
        row['context_inferred'] = bool(row.get('context_inferred') or row['source']=='context')
        known = row['source'] in ('dom', 'voice', 'microphone', 'context', 'manual', 'channel')
        same_unknown = bool(result and row['source'] in ('missing','transition','overlap','acoustic_unknown')
                            and result[-1]['source'] in (*AMBIGUOUS,'acoustic_unknown'))
        if (result and ((known and result[-1]['source'] in ('dom', 'voice', 'microphone', 'context', 'manual', 'channel')) or same_unknown)
                and result[-1]['speaker'] == row['speaker']
                and result[-1].get('track') == row.get('track')
                and result[-1].get('speaker_proposal',{}).get('speaker') == row.get('speaker_proposal',{}).get('speaker')
                and result[-1].get('speaker_check',{}).get('status') == row.get('speaker_check',{}).get('status')
                and -.2 <= row['start']-result[-1]['end'] < (1.2 if known else .8)
                and row['end']-result[-1]['start'] <= (60 if known else 20)):
            prev = result[-1]
            if 'parts' not in prev:
                prev['parts'] = [dict(prev)]
            prev['parts'].append(row)
            prev['text'] = prev['text'].rstrip()+' '+row['text'].lstrip()
            prev['end'] = max(prev['end'], row['end'])
            prev['confidence'] = min(prev.get('confidence', 0), row.get('confidence', 0))
            prev['channel_inferred'] = any(part.get('channel_inferred') for part in prev['parts'])
            prev['context_inferred'] = any(part.get('context_inferred') for part in prev['parts'])
            prev['voice_recovered'] = any(part['source']=='voice' for part in prev['parts'])
            totals={}
            for part in prev['parts']:
                totals[part['source']]=totals.get(part['source'],0)+part['end']-part['start']
            prev['source']=max(totals,key=totals.get)
            prev['source_durations']=totals
            prev['has_multiple_dom_indicators']=any(part['source']=='overlap' or part.get('original_attribution',{}).get('source')=='overlap' for part in prev['parts'])
        else:
            result.append(row)
    return result


def recover(root, wav, words, anchors, events, offset, speech_intervals=None, separate_microphone=False,self_name=None,confirmed_two_person=False,audio_source=None):
    from .speaker_audit import clean_audit
    words=clean_audit(words)
    python = root/'.speaker-env/bin/python'
    required = ('.ready','embedding_model.ckpt','hyperparams.yaml','mean_var_norm_emb.ckpt','classifier.ckpt','label_encoder.txt')
    if not python.exists() or not all((root/'models/speaker-ecapa'/name).exists() for name in required):
        return words, 'Riconoscimento voci non installato: esegui scripts/setup_speaker.py.'
    from .session_diarization import speech_windows
    if not speech_windows(words) and not any(row['source'] in ('missing','transition','overlap') for row in words):
        return words, None
    from .channel_attribution import two_person_context
    channel=two_person_context(events,separate_microphone,self_name,confirmed_two_person) if audio_source=='remote' else None
    payload = dict(single_remote=channel[0] if channel else None,mode='session',wav=str(wav), words=words, anchors=[],speech_intervals=speech_intervals,
                   events=[{'t': e['t'], 'speakers': e['speakers']} for e in events], offset=offset)
    try:
        command = [str(python), '-I', str(root/'localcall/speaker.py')]
        if sys.platform == 'darwin':
            command = ['/usr/bin/sandbox-exec', '-p', '(version 1)(allow default)(deny network*)']+command
        run = subprocess.run(command,
                             input=json.dumps(payload), text=True, capture_output=True, timeout=3600)
        wav.with_suffix('.speaker.log').write_text(getattr(run, 'stderr', '') or '')
        if run.returncode:
            return words, 'Confronto vocale non riuscito; mantenute le attribuzioni della pagina.'
        result = json.loads(run.stdout)
        if not isinstance(result, list) or len(result) != len(words):
            raise ValueError('Invalid result length')
        from .session_diarization import validate_result
        names={name for event in events for name in event['speakers']}
        for before, after in zip(words, result):
            validate_result(before,after,names)
        return result, None
    except (OSError, ValueError, TypeError, KeyError, AttributeError, subprocess.SubprocessError):
        return words, 'Confronto vocale non disponibile; mantenute le attribuzioni della pagina.'


AMBIGUOUS = ('missing', 'transition', 'overlap')


def candidate_names(events, start, end):
    """Observations expire at the next observation, including an empty one."""
    names = set()
    for i, event in enumerate(events):
        stop = min(event['t']+1.25, events[i+1]['t'] if i+1<len(events) else end)
        if event['t'] < end and stop > start:
            names.update(event['speakers'])
    return names


def reference_spans(anchors):
    refs = {}
    for turn, row in enumerate(anchors):
        if row['source'] != 'dom' or row.get('confidence', 0) < .85 or row.get('timing_adjusted'):
            continue
        # Stay away from the uncertain edges of DOM turns.
        start, stop = row['start']+1.25, row['end']-1.25
        while start+1.5 <= stop:
            end = min(start+4, stop)
            refs.setdefault(row['speaker'], []).append((start, end, turn))
            start = end
    return refs


def query_chunks(words):
    """Non-overlapping windows contained in ambiguous runs; never borrow a known turn."""
    runs=[]
    for i,row in enumerate(words):
        if row['source'] not in AMBIGUOUS:
            continue
        if runs and runs[-1][-1] == i-1 and row['start']-words[i-1]['end'] < .3:
            runs[-1].append(i)
        else:
            runs.append([i])
    chunks=[]
    for indices in runs:
        start=words[indices[0]]['start'];stop=max(words[i]['end'] for i in indices)
        while stop-start >= 1.5:
            end=min(start+3,stop)
            if 0 < stop-end < 1.5:
                end=stop
            included=[i for i in indices if words[i]['start'] >= start and words[i]['end'] <= end]
            if included:
                chunks.append((start,end,included))
            start=end
    return chunks


def coherent_reference(vectors):
    """Require support from distinct DOM turns, independent of the query voice."""
    import math
    from itertools import combinations
    groups=[]
    dot=lambda a,b:sum(x*y for x,y in zip(a,b))
    for size in range(2,len(vectors)+1):
        for indices in combinations(range(len(vectors)),size):
            if len({vectors[i][1] for i in indices}) < 2:
                continue
            similarities=[dot(vectors[i][0],vectors[j][0]) for i,j in combinations(indices,2)]
            if min(similarities)>=.5:
                groups.append((size,sum(similarities)/len(similarities),indices))
    if not groups:
        return None
    groups.sort(reverse=True);best=groups[0]
    if any(g[0]==best[0] and not set(g[2])&set(best[2]) and
           max(dot(vectors[i][0],vectors[j][0]) for i in g[2] for j in best[2])<.35 for g in groups[1:]):
        return None
    v=[sum(vectors[i][0][j] for i in best[2]) for j in range(len(vectors[0][0]))]
    norm=math.sqrt(dot(v,v))
    return [x/norm for x in v] if norm else None


def resolve_words(words, anchors, events, embedding):
    """Pure orchestration: injectable embeddings make timing and abstention testable."""
    result=[dict(row) for row in words]
    refs=reference_spans(anchors)
    events=sorted(events,key=lambda e:e['t'])
    for start,end,indices in query_chunks(words):
        candidates=candidate_names(events,start,end)
        if not candidates:
            continue
        centroids={}
        # Other session speakers act as negative controls, even if DOM did not show them.
        for name,spans in refs.items():
            nearby=sorted((span for span in spans if span[1]<=start or span[0]>=end),
                          key=lambda span:min(abs(start-span[1]),abs(end-span[0])))
            selected=[];turns=set()
            for span in nearby:
                if span[2] not in turns:
                    selected.append(span);turns.add(span[2])
                if len(selected)==4:
                    break
            vectors=[]
            for a,b,turn in selected:
                v=embedding(a,b)
                if v is not None:
                    vectors.append((list(v),turn))
            centroid=coherent_reference(vectors)
            if centroid is not None:
                centroids[name]=centroid
        if not candidates.issubset(centroids) or len(centroids)<2:
            continue
        windows=[(start,end)]
        if end-start>=3:
            mid=(start+end)/2
            windows.extend([(start,mid),(mid,end)])
        choices=[]
        for a,b in windows:
            v=embedding(a,b)
            if v is None:
                break
            scores={name:float(sum(x*y for x,y in zip(v,c))) for name,c in centroids.items()}
            winner=choose(scores,candidates)
            if not winner:
                break
            choices.append((winner,scores[winner]))
        if len(choices)!=len(windows) or len({name for name,_ in choices})!=1:
            continue
        for i in indices:
            row=result[i]
            row['original_attribution']={k:row[k] for k in ('speaker','source','confidence')}
            row.update(speaker=choices[0][0],source='voice',confidence=0,
                       voice_similarity=round(min(score for _,score in choices),3),
                       voice_model='speechbrain/ecapa-voxceleb')
    return result


def audio_bounds(start, end, offset, duration):
    a,b=max(0,start-offset),min(duration,end-offset)
    return (a,b) if round(b*16000)-round(a*16000)>=24000 else None


def main():
    import os
    os.environ.update(HF_HUB_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1', DO_NOT_TRACK='1')
    import socket
    def deny(*args, **kwargs):
        raise RuntimeError('Network disabled during speaker inference')
    socket.socket.connect = deny
    socket.socket.connect_ex = deny
    socket.create_connection = deny
    task = json.load(sys.stdin)
    root = Path(__file__).resolve().parent.parent
    import importlib.util
    spec=importlib.util.spec_from_file_location('speaker_audit',root/'localcall/speaker_audit.py')
    audit_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit_module)
    refs = reference_spans(task['anchors'])
    if task.get('mode')!='session' and not audit_module.can_audit(task['words'],task['anchors']) and sum(len({span[2] for span in spans}) >= 2 for spans in refs.values()) < 2:
        return task['words']
    import threading
    import time
    parent = os.getppid()
    def watch_parent():
        while True:
            time.sleep(2)
            if os.getppid() != parent:
                os._exit(1)
    threading.Thread(target=watch_parent, daemon=True).start()
    import numpy as np
    import soundfile as sf
    import torch
    from functools import lru_cache
    from speechbrain.inference.speaker import EncoderClassifier
    torch.set_num_threads(2)
    root = Path(__file__).resolve().parent.parent
    model = root/'models/speaker-ecapa'
    encoder = EncoderClassifier.from_hparams(source=str(model), savedir=str(model),
                 run_opts={'device': 'cpu'}, overrides={'pretrained_path': str(model)})
    offset = task['offset']
    with sf.SoundFile(task['wav']) as audio:
        if audio.samplerate != 16000 or audio.channels != 1:
            raise ValueError('Expected mono 16 kHz audio')
        duration = len(audio)/16000
        @lru_cache(maxsize=512)
        def embedding(start, end):
            bounds=audio_bounds(start,end,offset,duration)
            if bounds is None:
                return None
            start,end=bounds
            first,last=round(start*16000),round(end*16000)
            audio.seek(first)
            y = audio.read(last-first, dtype='float32')
            if len(y) < 24000 or np.sqrt(np.mean(y*y)) < .001:
                return None
            with torch.inference_mode():
                v = encoder.encode_batch(torch.from_numpy(y).unsqueeze(0)).numpy().reshape(-1)
            norm = np.linalg.norm(v)
            return v/norm if norm > 0 else None
        if task.get('mode')=='session':
            spec=importlib.util.spec_from_file_location('session_diarization',root/'localcall/session_diarization.py')
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            result,stats=module.diarize(task['words'],task['events'],embedding,task.get('embedding_cache'),task.get('speech_intervals'),(offset,offset+duration),task.get('single_remote'))
            print('session_diarization_metrics '+json.dumps(stats),file=sys.stderr)
            return result
        # Audit original labels before recovery: never train on or audit our own guesses.
        audited,stats=audit_module.audit_words(task['words'],task['anchors'],embedding,coherent_reference)
        result=resolve_words(task['words'], task['anchors'], task['events'], embedding)
        result=audit_module.merge_audit(audited,result)
        stats['embedding_computations']=embedding.cache_info().misses
        print('speaker_audit_metrics '+json.dumps(stats),file=sys.stderr)
        return result


if __name__ == '__main__':
    from contextlib import redirect_stdout
    with redirect_stdout(sys.stderr):
        result = main()
    json.dump(result, sys.stdout, ensure_ascii=False)
