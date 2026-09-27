import json,re,heapq
from pathlib import Path

def jsonl(path):
    return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]

def worker_meta(data):
    return {x['worker_sha']:x for x in json.loads((Path(data)/'workers.json').read_text())}

def worker_policy(data, worker_sha):
    meta=worker_meta(data)[worker_sha]
    src=(Path(data)/meta['source']).read_text()
    m=re.search(r'NETWORK_FIRST_TIMEOUT_MS\s*=\s*(\d+)',src)
    if not m: raise ValueError('worker timeout missing')
    return meta['release'], int(m.group(1))

def classify(url):
    if url.startswith('/diag/maps/'): return 'cache-first'
    if url.startswith('/diag/catalog/') or url.endswith('/locale_graph.json') or url.endswith('/routes.json'): return 'network-first'
    return 'stale-while-revalidate'

def controllers(data):
    ctl={}
    for e in sorted(jsonl(Path(data)/'sw_events.jsonl'),key=lambda x:x['t_ms']):
        if e['event'] in ('client-open','controllerchange'):
            ctl[e['client_id']]=e['controller_sha']
    return ctl

def reconstruct(data):
    data=Path(data)
    ctx=json.loads((data/'audit_context.json').read_text())
    target=ctx['client_id']; end=ctx['capture_end_ms']
    initial=json.loads((data/'initial_cache.json').read_text())['entries']
    cache=dict(initial)
    ctl=controllers(data)
    if target not in ctl: raise ValueError('target client has no controller')
    release,_=worker_policy(data,ctl[target])
    reqs=sorted(jsonl(data/'request_trace.jsonl'),key=lambda x:(x['start_ms'],x['request_id']))
    pending=[]; serial=0; returned={}
    def apply_until(t):
        nonlocal pending
        while pending and pending[0][0] <= t:
            _,_,url,sha=heapq.heappop(pending)
            cache[url]=sha
    for q in reqs:
        if q['start_ms']>end: break
        apply_until(q['start_ms'])
        worker=ctl[q['client_id']]
        _,timeout=worker_policy(data,worker)
        kind=classify(q['url']); hit=cache.get(q['url'])
        done=q['start_ms']+q['network_latency_ms']
        network_ok=q['status']==200
        chosen=None
        if kind=='cache-first':
            if hit is not None:
                chosen=hit
            else:
                chosen=q['body_sha'] if network_ok else None
                if network_ok:
                    serial+=1; heapq.heappush(pending,(done,serial,q['url'],q['body_sha']))
        elif kind=='stale-while-revalidate':
            chosen=hit if hit is not None else (q['body_sha'] if network_ok else None)
            if network_ok:
                serial+=1; heapq.heappush(pending,(done,serial,q['url'],q['body_sha']))
        else: # network-first with timeout
            if network_ok and q['network_latency_ms'] <= timeout:
                chosen=q['body_sha']
                serial+=1; heapq.heappush(pending,(done,serial,q['url'],q['body_sha']))
            else:
                chosen=hit if hit is not None else (q['body_sha'] if network_ok else None)
                if network_ok:
                    serial+=1; heapq.heappush(pending,(done,serial,q['url'],q['body_sha']))
        if q['client_id']==target:
            if chosen is None: raise ValueError(f'no response for {q["url"]}')
            returned[q['url']]=chosen
    apply_until(end)
    return release, returned, cache

def read_body(data, sha):
    return (Path(data)/'archive'/sha).read_bytes()
