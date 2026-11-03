"""Independent reference for the native stopping-time contract; no strategy score."""
from itertools import groupby


def first_observation(w):
    if (any(w[k] < 0 for k in ('Nominal','LatencyMs','SearchMs','MaximumAgeMs'))
        or not w['Route'] or any(not s or not s.strip() for s in w['Route'])
        or len(set(w['Route'])) != len(w['Route'])):
        raise ValueError('OBSERVATION_WINDOW_CONTRACT')
    start=w['Nominal']+w['LatencyMs'];end=start+w['SearchMs']
    if not w['Complete']:
        return dict(Status='INCOMPLETE_SOURCE',At=None,Quotes=[])
    if any(e['At']<0 or not e['Symbol'].strip() or e['Side'] not in (0,1) for e in w['Events']):
        raise ValueError('OBSERVATION_EVENT_CONTRACT')
    state={}
    for at,events in groupby(sorted((e for e in w['Events'] if e['At']<=end),key=lambda e:e['At']),lambda e:e['At']):
        batch={}
        for e in events:
            key=e['Symbol'],e['Side']
            if key in batch and batch[key]['Price']!=e['Price']:
                raise ValueError('AMBIGUOUS_SAME_TIME_SIDE')
            batch[key]=e
        state.update(batch)
        if at<start:continue
        if all((s,0) in state and (s,1) in state and
               all(at-state[s,k]['At']<=w['MaximumAgeMs'] for k in (0,1)) and
               0<state[s,0]['Price']<=state[s,1]['Price'] for s in w['Route']):
            return dict(Status='OBSERVED',At=at,Quotes=[dict(Symbol=s,
                Bid=state[s,0]['Price'],Ask=state[s,1]['Price'],BidAt=state[s,0]['At'],AskAt=state[s,1]['At'])
                for s in sorted(w['Route'])])
    return dict(Status='NO_CAUSAL_OBSERVATION',At=None,Quotes=[])
