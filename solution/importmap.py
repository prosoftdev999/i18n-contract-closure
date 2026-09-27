import json, copy
from pathlib import Path
from urllib.parse import urljoin, urlparse


def _norm(target, base):
    return urljoin(base, target)


def _best(table, spec):
    if spec in table:
        return table[spec]
    candidates=[(k,v) for k,v in table.items() if k.endswith('/') and spec.startswith(k)]
    if not candidates:
        return None
    k,v=max(candidates,key=lambda kv:len(kv[0]))
    return str(v)+spec[len(k):]


def resolve_import(mapobj, spec, referrer, base):
    p=urlparse(spec)
    if spec.startswith(('./','../','/')) or p.scheme:
        return urljoin(referrer,spec)
    scopes=mapobj.get('scopes',{})
    for prefix in sorted((x for x in scopes if referrer.startswith(x)),key=len,reverse=True):
        t=_best(scopes[prefix],spec)
        if t is not None:
            return _norm(t,base)
    t=_best(mapobj.get('imports',{}),spec)
    if t is None:
        raise ValueError(f'unmapped bare specifier {spec} from {referrer}')
    return _norm(t,base)


def patch_map(cur,delta):
    out=copy.deepcopy(cur)
    out.setdefault('imports',{}).update(delta.get('imports',{}))
    for scope,entries in delta.get('scopes',{}).items():
        out.setdefault('scopes',{}).setdefault(scope,{}).update(entries)
    return out


class ImportRuntime:
    def __init__(self,data):
        data=Path(data); self.data=data
        b=json.loads((data/'importmap_base.json').read_text())
        self.base=b['base_url']; self.roots=b['route_roots']; self.initial=copy.deepcopy(b['map'])
        self.patches=json.loads((data/'importmap_patches.json').read_text())
        self.snaps=json.loads((data/'importmap_snapshots.json').read_text())
        self.graph=json.loads((data/'module_graph.json').read_text())
        self.map=copy.deepcopy(self.initial); self.cache={}; self.executed=set(); self.overlay={}
    def _catalog(self,ops):
        for op in ops:
            k=(op['locale'],op['namespace'],op['key'])
            self.overlay[k]=None if op['op']=='remove' else op['pattern']
    def apply_patch(self,patch_id):
        self.map=patch_map(self.map,self.patches.get(patch_id,{}))
    def reload(self,snapshot_id):
        s=self.snaps[snapshot_id]
        self.map=copy.deepcopy(s['map']); self.cache={}; self.executed=set(); self.overlay={}
        for url in s.get('preload',[]):
            self._visit(url,set())
    def _edge(self,referrer,spec):
        k=(referrer,spec)
        if k not in self.cache:
            self.cache[k]=resolve_import(self.map,spec,referrer,self.base)
        return self.cache[k]
    def _visit(self,url,active):
        if url in active:
            return
        if url not in self.graph:
            raise ValueError(f'module graph missing {url}')
        active.add(url)
        m=self.graph[url]
        if url not in self.executed:
            self.executed.add(url)
            self._catalog(m.get('catalog_ops',[]))
        for spec in m.get('deps',[]):
            self._visit(self._edge(url,spec),active)
    def checkpoint(self,route):
        active=set(); self._visit(self.roots[route],active)
        modules=sorted({self.graph[u]['source_module'] for u in active})
        return {'modules':modules,'catalog_overlay':dict(self.overlay)}
