import json, copy
from pathlib import Path
from .importmap import ImportRuntime

def _jsonl(path):
    return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]

def _mounted_entry_chunks(stats, routes, route):
    ep=routes[route]['entrypoint']
    return set(stats['entrypoints'][ep]['initial'])

def _parents(chunks):
    out={}
    for parent,spec in chunks.items():
        for child in spec.get('children',[]): out.setdefault(child,[]).append(parent)
    return out

def disposition(chunks, accepts, mounted, changed):
    parents=_parents(chunks); q=list(changed); seen=set()
    while q:
        child=q.pop(0)
        if child in seen: continue
        seen.add(child)
        if child in mounted: return 'reload'
        for parent in parents.get(child,[]):
            if child not in set(accepts.get(parent,[])): q.append(parent)
    return 'accept'

def replay(data, base_stats):
    data=Path(data)
    patches=json.loads((data/'hmr_patches.json').read_text())
    snaps=json.loads((data/'hmr_snapshots.json').read_text())
    accepts=json.loads((data/'hmr_accept.json').read_text())['accepts']
    events=sorted(_jsonl(data/'hmr_session.jsonl'),key=lambda x:x['seq'])
    imports=ImportRuntime(data)
    routes=None
    # caller supplies route metadata by setting base_stats['_routes'] temporarily
    routes=base_stats.pop('_routes')
    chunks=copy.deepcopy(base_stats['chunks'])
    maps={k:'base' for k in chunks}
    overlay={}
    current=None; checkpoints={}
    def apply_overlay(ops):
        for op in ops:
            k=(op['locale'],op['namespace'],op['key'])
            overlay[k]=None if op['op']=='remove' else op['pattern']
    for e in events:
        if e['event']=='navigate': current=e['route']
        elif e['event']=='offer':
            p=patches[e['patch']]
            mounted=_mounted_entry_chunks(base_stats,routes,current)
            d=disposition(chunks,accepts,mounted,p['changed'])
            if d=='reload':
                s=snaps[p['reload_snapshot']]
                chunks=copy.deepcopy(s['chunks']); maps=dict(s['map_variants']); overlay={}
                apply_overlay(s.get('catalog_overlay',[]))
                imports.reload(p['reload_snapshot'])
            else:
                for ch,spec in p.get('chunks',{}).items(): chunks[ch]=copy.deepcopy(spec)
                maps.update(p.get('map_variants',{}))
                apply_overlay(p.get('catalog_ops',[]))
                imports.apply_patch(e['patch'])
        elif e['event']=='checkpoint':
            if e['route']!=current: raise ValueError('checkpoint route is not current navigation')
            ir=imports.checkpoint(current)
            checkpoints[current]={'chunks':copy.deepcopy(chunks),'map_variants':dict(maps),'catalog_overlay':dict(overlay),'import_modules':ir['modules'],'import_catalog_overlay':ir['catalog_overlay']}
    if set(checkpoints)!=set(routes): raise ValueError('missing route checkpoint')
    return checkpoints
