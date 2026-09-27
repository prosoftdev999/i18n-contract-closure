import json,subprocess
from pathlib import Path
from .sourcemap import map_callsite
from .browser import read_body
from .icu import parse,required_args
from .hmr import replay as replay_hmr

def jloads(b): return json.loads(b.decode())
def jl(b): return [json.loads(x) for x in b.decode().splitlines() if x.strip()]

class Analyzer:
    def __init__(self,data,release,responses):
        self.data=Path(data); self.release=release; self.responses=responses
        self.stats=jloads(self.body('/diag/stats.json'))
        self.routes=jloads(self.body('/diag/routes.json'))
        self.cfg=jloads(self.body('/diag/locale_graph.json'))
        self.calls=jl(self.body('/diag/callsites.jsonl'))
        self.catalog_events={}
        needed=set(self.cfg.get('aliases',{}).values())|set(self.cfg.get('parents',{}))|set(self.cfg.get('parents',{}).values())|set(self.cfg.get('requested_locales',[]))
        needed.discard(None)
        for loc in sorted(needed):
            url=f'/diag/catalog/{loc}.jsonl'
            if url in responses: self.catalog_events[loc]=jl(self.body(url))
        base=dict(self.stats); base['_routes']=self.routes
        self.hmr=replay_hmr(self.data,base)
        self.ast={}; self.pc={}; self.registry_cache={}; self.map_cache={}
    def body(self,url): return read_body(self.data,self.responses[url])
    def map_body(self,asset,variant):
        k=(asset,variant)
        if k in self.map_cache: return self.map_cache[k]
        if variant=='base': b=self.body(f'/diag/maps/{asset}.map')
        else: b=(self.data/'hmr_maps'/variant/f'{asset}.map').read_bytes()
        self.map_cache[k]=b; return b
    def locale_chain(self,requested):
        loc=self.cfg.get('aliases',{}).get(requested,requested); out=[]; seen=set()
        while loc is not None:
            if loc in seen: raise ValueError('locale parent cycle')
            seen.add(loc); out.append(loc); loc=self.cfg['parents'].get(loc)
        return out
    def route_state(self,route):
        hs=self.hmr[route]; chunkspec=hs['chunks']
        start=list(self.stats['entrypoints'][self.routes[route]['entrypoint']]['initial']); stack=list(start); chunks=set(); mods=set()
        while stack:
            ch=stack.pop()
            if ch in chunks: continue
            chunks.add(ch); spec=chunkspec[ch]; mods.update(spec['modules']); stack.extend(spec.get('children',[]))
        mods.update(hs.get('import_modules',[]))
        return sorted(mods),frozenset(chunks),hs['map_variants'],hs['catalog_overlay'],hs.get('import_catalog_overlay',{})
    def registry(self,chunks,overlay,import_overlay):
        key=(chunks,tuple(sorted((k,v) for k,v in overlay.items())),tuple(sorted((k,v) for k,v in import_overlay.items())))
        if key in self.registry_cache: return self.registry_cache[key]
        reg={}
        for loc,events in self.catalog_events.items():
            state={}
            for e in sorted(events,key=lambda x:x['seq']):
                if e['bundle'] not in chunks: continue
                k=(e['namespace'],e['key']); state[k]=None if e['op']=='remove' else e['pattern']
            reg[loc]=state
        for (loc,ns,k),value in overlay.items(): reg.setdefault(loc,{})[(ns,k)]=value
        for (loc,ns,k),value in import_overlay.items(): reg.setdefault(loc,{})[(ns,k)]=value
        self.registry_cache[key]=reg; return reg
    def resolve(self,requested,message,reg):
        ns,key=message.split(':',1); barriers={(x['locale'],x['namespace']) for x in self.cfg.get('fallback_barriers',[])}
        for loc in self.locale_chain(requested):
            state=reg.get(loc,{})
            if (ns,key) in state:
                pat=state[(ns,key)]
                if pat is None: return None,None
                return pat,loc
            if (loc,ns) in barriers: return None,None
        return None,None
    def plural(self,locale,kind,value):
        k=(locale,kind,value)
        if k in self.pc: return self.pc[k]
        proc=subprocess.run(['node',str(Path(__file__).with_name('plural.mjs'))],input=json.dumps({'locale':locale,'type':kind,'values':[value]}),text=True,capture_output=True,check=True)
        self.pc[k]=json.loads(proc.stdout)[0]; return self.pc[k]
    def call(self,locale,c,module,reg):
        pat,src=self.resolve(locale,c['message'],reg); issues=[]
        if pat is None:
            issues=[f"missing-message:{c['callsite_id']}:{c['message']}"]
            return {'callsite_id':c['callsite_id'],'module':module,'message':c['message'],'source_locale':None,'required_args':{},'issues':issues}
        ast=self.ast.setdefault(pat,parse(pat)); req=required_args(ast,c['args'],lambda kind,v:self.plural(locale,kind,v))
        for arg,typ in req.items():
            actual=c['args'].get(arg,{}).get('type')
            if actual is None: issues.append(f"missing-arg:{c['callsite_id']}:{arg}")
            elif not (actual==typ or (typ=='number' and actual=='integer')): issues.append(f"incompatible-arg:{c['callsite_id']}:{arg}:expected={typ}:actual={actual}")
        return {'callsite_id':c['callsite_id'],'module':module,'message':c['message'],'source_locale':src,'required_args':req,'issues':sorted(issues)}
    def build(self):
        rows=[]; ic=clean=ev=0
        for route in sorted(self.routes):
            mods,chunks,maps,overlay,import_overlay=self.route_state(route); mset=set(mods); mapped=[]
            for c in self.calls:
                variant=maps.get(c['asset'],'base')
                module=map_callsite(self.map_body(c['asset'],variant),c['generated_line_1based'],c['generated_column_0based'])
                if module in mset: mapped.append((c,module))
            reg=self.registry(chunks,overlay,import_overlay)
            for loc in sorted(self.cfg['requested_locales']):
                cc=sorted((self.call(loc,c,module,reg) for c,module in mapped),key=lambda x:x['callsite_id']); issues=sorted({i for c in cc for i in c['issues']})
                rows.append({'route':route,'locale':loc,'modules':mods,'callsites':cc,'issues':issues}); ic+=len(issues); ev+=len(cc); clean+=not issues
        return {'release':self.release,'route_locales':rows,'summary':{'route_locale_count':len(rows),'clean_count':int(clean),'issue_count':ic,'callsite_evaluations':ev}}
