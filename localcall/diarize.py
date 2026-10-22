"""Conservative temporal fusion. DOM observations expire rather than guess."""
from bisect import bisect_right

UNKNOWN = 'Non identificato'

def attribute(start, end, events, ttl=1.25, times=None, transitions=None):
    scores = {}
    ambiguous = 0.0
    duration = max(end - start, .02)
    if times is None:
        times = [e['t'] for e in events]
    if transitions:
        j = bisect_right(transitions, start-.25)
        if j < len(transitions) and transitions[j] < end+.25:
            return UNKNOWN, 'transition', 0
    i = max(0, bisect_right(times, start) - 1)
    for j in range(i, len(events)):
        event = events[j]
        if event['t'] >= end:
            break
        stop = min(event['t'] + ttl, events[j+1]['t'] if j+1 < len(events) else end)
        overlap = max(0, min(stop, end) - max(start, event['t']))
        names = set(event['speakers'])
        if len(names) == 1:
            name = next(iter(names))
            scores[name] = scores.get(name, 0) + overlap
        elif len(names) > 1:
            ambiguous += overlap
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    if ambiguous / duration > .2:
        return UNKNOWN, 'overlap', 0
    if not ranked or ranked[0][1] / duration < .6:
        return UNKNOWN, 'missing', 0
    if len(ranked) > 1 and ranked[1][1] / duration > .25:
        return UNKNOWN, 'transition', 0
    return ranked[0][0], 'dom', round(min(1, ranked[0][1]/duration), 2)

def constrain_to_speech(segments, intervals):
    """Whisper 1.8.3 can stretch a boundary word across a removed VAD gap.
    Clip it to the speech island with greatest overlap, preserving original time.
    Intervals come from the same Silero run, never from re-compressed audio.
    """
    if not intervals:
        return segments
    result=[]
    ends=[b for a,b in intervals]
    for segment in segments:
        start,end=segment['offsets']['from'],segment['offsets']['to']
        candidates=[]
        i=bisect_right(ends,start)
        while i<len(intervals) and intervals[i][0]<end:
            a,b=intervals[i]
            left,right=max(start,a),min(end,b)
            if right>left:candidates.append((right-left,left,right))
            i+=1
        if not candidates:
            continue
        # A boundary word can inherit the previous island's tail across a long
        # removed silence. Its end belongs to the resumed speech, not that tail.
        crosses_pause=any(candidates[j][1]-candidates[j-1][2]>1000 for j in range(1,len(candidates)))
        _,left,right=candidates[-1] if crosses_pause else max(candidates)
        adjusted=left-start>250 or end-right>250
        result.append({**segment,'offsets':{'from':left,'to':right},'timing_adjusted':adjusted})
    return result

def fuse(segments, events, offset=0, self_name=None, merge=True):
    result = []
    events = sorted(events, key=lambda e: e['t'])
    times = [e['t'] for e in events]
    transitions = [events[i]['t'] for i in range(1,len(events))
                   if events[i-1]['speakers'] and events[i]['speakers']
                   and set(events[i-1]['speakers']) != set(events[i]['speakers'])]
    for seg in segments:
        text = seg['text']
        if not text.strip() or text.strip().startswith('[_'):
            continue
        start, end = seg['offsets']['from']/1000 + offset, seg['offsets']['to']/1000 + offset
        if end <= start:
            end = start + .02
        name, source, confidence = (self_name, 'microphone', .9) if self_name else attribute(start, end, events, times=times, transitions=transitions)
        if seg.get('timing_adjusted'):
            confidence=min(confidence,.75)
        row = dict(start=round(start, 3), end=round(end, 3), speaker=name, text=text,
                   source=source, confidence=confidence, timing_adjusted=seg.get('timing_adjusted',False))
        if merge and result and result[-1]['speaker'] == name and result[-1]['source'] == source and start-result[-1]['end'] < .8 and end-result[-1]['start'] < 20:
            result[-1]['text'] += text
            result[-1]['end'] = row['end']
            result[-1]['timing_adjusted'] |= row['timing_adjusted']
            result[-1]['confidence'] = min(result[-1]['confidence'], confidence)
        else:
            result.append(row)
    for row in result:
        row['text'] = row['text'].strip()
    return result

def timestamp(seconds, comma=False):
    ms = round(max(0, seconds)*1000)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f'{h:02}:{m:02}:{s:02}{"," if comma else "."}{ms:03}'

def export(rows, kind):
    def display_name(row):
        return row['speaker'] + (' (canale remoto)' if row.get('channel_inferred') else '') + (' (continuità stimata)' if row.get('context_inferred') else '')
    if kind == 'txt':
        return '\n\n'.join(f'[{timestamp(r["start"])}] {display_name(r)}: {r["text"]}' for r in rows)
    # Display paragraphs may last a minute; SRT keeps the detailed short cues.
    def leaves(items):
        for item in items:
            if item.get('parts'):
                yield from leaves(item['parts'])
            else:
                yield dict(item)
    cues=[]
    for row in leaves(rows):
        if (cues and cues[-1]['speaker']==row['speaker']
                and cues[-1].get('track')==row.get('track')
                and 0 <= row['start']-cues[-1]['end'] < .8
                and row['end']-cues[-1]['start'] <= 20):
            cues[-1]['text'] += ' '+row['text']
            cues[-1]['end'] = row['end']
            cues[-1]['channel_inferred'] = bool(cues[-1].get('channel_inferred') or row.get('channel_inferred'))
            cues[-1]['context_inferred'] = bool(cues[-1].get('context_inferred') or row.get('context_inferred'))
        else:
            cues.append(row)
    rows=cues
    return '\n\n'.join(f'{i+1}\n{timestamp(r["start"], True)} --> {timestamp(r["end"], True)}\n{display_name(r)}: {r["text"]}' for i, r in enumerate(rows)) + '\n'
