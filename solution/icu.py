class ParseError(ValueError): pass

class Parser:
    def __init__(self,s): self.s=s; self.i=0
    def parse(self):
        nodes=self._seq(None)
        if self.i!=len(self.s): raise ParseError("trailing input")
        return {"type":"seq","items":nodes}
    def _seq(self, stop):
        out=[]; text=[]
        def flush():
            if text:
                out.append({"type":"text","value":"".join(text)}); text.clear()
        while self.i<len(self.s):
            c=self.s[self.i]
            if stop and c==stop: break
            if c=="'":
                # ICU apostrophe quoting: doubled apostrophe is literal; otherwise quote through next apostrophe.
                if self.i+1<len(self.s) and self.s[self.i+1]=="'": text.append("'"); self.i+=2; continue
                end=self.s.find("'",self.i+1)
                if end==-1: text.append("'"); self.i+=1; continue
                text.append(self.s[self.i+1:end]); self.i=end+1; continue
            if c=='{':
                flush(); out.append(self._arg()); continue
            text.append(c); self.i+=1
        flush(); return out
    def _ws(self):
        while self.i<len(self.s) and self.s[self.i].isspace(): self.i+=1
    def _token_until(self, chars):
        start=self.i
        while self.i<len(self.s) and self.s[self.i] not in chars: self.i+=1
        return self.s[start:self.i].strip()
    def _arg(self):
        assert self.s[self.i]=='{'; self.i+=1; self._ws()
        name=self._token_until(',}')
        if self.i>=len(self.s): raise ParseError("unterminated argument")
        if self.s[self.i]=='}': self.i+=1; return {'type':'arg','name':name,'format':'string'}
        self.i+=1; self._ws(); kind=self._token_until(',}')
        if self.i>=len(self.s): raise ParseError("unterminated format")
        if kind in ('number','date','time'):
            # Ignore optional style/skeleton after the kind.
            depth=0
            while self.i<len(self.s):
                c=self.s[self.i]
                if c=='}' and depth==0: self.i+=1; break
                self.i+=1
            return {'type':'arg','name':name,'format':'number' if kind=='number' else 'date'}
        if kind not in ('select','plural','selectordinal'): raise ParseError(f'unsupported ICU kind {kind}')
        if self.s[self.i]==',': self.i+=1
        branches={}
        while True:
            self._ws()
            if self.i>=len(self.s): raise ParseError("unterminated choice")
            if self.s[self.i]=='}': self.i+=1; break
            key=self._token_until('{').strip()
            if not key or self.i>=len(self.s) or self.s[self.i]!='{': raise ParseError("bad branch")
            self.i+=1
            body=self._seq('}')
            if self.i>=len(self.s) or self.s[self.i]!='}': raise ParseError("unterminated branch")
            self.i+=1; branches[key]={'type':'seq','items':body}
        return {'type':kind,'name':name,'branches':branches}

def parse(pattern): return Parser(pattern).parse()

def _merge(out,name,typ):
    old=out.get(name)
    if old is None or old==typ: out[name]=typ; return
    raise ValueError(f'incompatible ICU requirements for {name}: {old} vs {typ}')

def required_args(ast, arg_facts, plural_selector):
    out={}
    def walk(n):
        t=n['type']
        if t=='text': return
        if t=='seq':
            for x in n['items']: walk(x)
            return
        if t=='arg': _merge(out,n['name'],n['format']); return
        name=n['name']; selector_type='string' if t=='select' else 'number'
        _merge(out,name,selector_type)
        facts=arg_facts.get(name,{})
        vals=facts.get('values')
        keys=[]
        if vals is None:
            keys=list(n['branches'])
        else:
            for v in vals:
                if t=='select': key=str(v)
                else:
                    exact='='+str(v)
                    key= exact if exact in n['branches'] else plural_selector(t,v)
                if key not in n['branches']: key='other'
                if key in n['branches'] and key not in keys: keys.append(key)
        for k in keys: walk(n['branches'][k])
    walk(ast)
    return {k:out[k] for k in sorted(out)}
