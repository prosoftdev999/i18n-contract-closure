import json,base64,re
ALPH="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
DEC={c:i for i,c in enumerate(ALPH)}

def _vlq(s,i):
    value=shift=0
    while True:
        d=DEC[s[i]]; i+=1; value|=(d&31)<<shift
        if not d&32: break
        shift+=5
    neg=value&1; value>>=1
    return (-value if neg else value),i

def _basic_lookup(m,line0,col0):
    # Source Map v3 keeps source/original-position VLQ state across generated
    # lines. Only the generated column resets at each semicolon.
    src=oline=ocol=0
    lines=m.get('mappings','').split(';')
    if line0<0 or line0>=len(lines): return None
    chosen=None
    for line_index in range(line0+1):
        gen=0
        line=lines[line_index]
        for raw in line.split(',') if line else []:
            vals=[]; i=0
            while i<len(raw): v,i=_vlq(raw,i); vals.append(v)
            gen+=vals[0]
            if len(vals)>=4:
                src+=vals[1]; oline+=vals[2]; ocol+=vals[3]
                if line_index==line0:
                    if gen<=col0: chosen=(src,oline,ocol)
                    else: break
        if line_index==line0:
            break
    if chosen is None: return None
    si,ol,oc=chosen
    sources=m.get('sources',[])
    if si<0 or si>=len(sources): return None
    content=None
    sc=m.get('sourcesContent')
    if isinstance(sc,list) and si<len(sc): content=sc[si]
    return sources[si],ol,oc,content

def lookup(m,line0,col0):
    if 'sections' in m:
        chosen=None
        for sec in m['sections']:
            ol=sec['offset']['line']; oc=sec['offset']['column']
            if line0>ol or (line0==ol and col0>=oc): chosen=sec
            else: break
        if chosen is None: return None
        ol=chosen['offset']['line']; oc=chosen['offset']['column']
        cl=line0-ol; cc=col0-(oc if cl==0 else 0)
        return lookup(chosen['map'],cl,cc)
    return _basic_lookup(m,line0,col0)

def inline_map(content):
    if not content: return None
    m=re.search(r'sourceMappingURL=data:application/json;base64,([A-Za-z0-9+/=]+)',content)
    if not m: return None
    return json.loads(base64.b64decode(m.group(1)).decode())

def map_callsite(map_bytes,line1,col0):
    m=json.loads(map_bytes.decode())
    cur=lookup(m,line1-1,col0)
    depth=0
    while cur and depth<6:
        src,ol,oc,content=cur
        child=inline_map(content)
        if child is None: return src
        cur=lookup(child,ol,oc); depth+=1
    return cur[0] if cur else None
