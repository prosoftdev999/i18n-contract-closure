import json, os, stat
from pathlib import Path

ART=Path('/app/output/i18n_contract.json')
EXPECTED=json.loads((Path(__file__).parent/'expected.json').read_text())

def load_candidate():
    assert ART.exists(), 'artifact missing'
    st=ART.lstat()
    assert stat.S_ISREG(st.st_mode), 'artifact must be a regular file'
    assert not ART.is_symlink(), 'artifact must not be a symlink'
    assert st.st_size <= 12_000_000, 'artifact too large'
    try:
        obj=json.loads(ART.read_text())
    except Exception as exc:
        raise AssertionError(f'invalid JSON: {exc}')
    return obj

def canonical(obj):
    assert isinstance(obj,dict)
    assert set(obj)=={'release','route_locales','summary'}
    assert isinstance(obj['release'],str)
    assert isinstance(obj['summary'],dict)
    assert set(obj['summary'])=={'route_locale_count','clean_count','issue_count','callsite_evaluations'}
    rows=obj['route_locales']; assert isinstance(rows,list)
    seen=set(); out=[]
    for r in rows:
        assert isinstance(r,dict)
        assert set(r)=={'route','locale','modules','callsites','issues'}
        key=(r['route'],r['locale']); assert key not in seen; seen.add(key)
        mods=r['modules']; assert isinstance(mods,list) and all(isinstance(x,str) for x in mods)
        assert len(mods)==len(set(mods))
        calls=r['callsites']; assert isinstance(calls,list)
        cseen=set(); cc=[]
        for c in calls:
            assert isinstance(c,dict)
            assert set(c)=={'callsite_id','module','message','source_locale','required_args','issues'}
            cid=c['callsite_id']; assert isinstance(cid,str) and cid not in cseen; cseen.add(cid)
            assert isinstance(c['module'],str) and isinstance(c['message'],str)
            assert c['source_locale'] is None or isinstance(c['source_locale'],str)
            req=c['required_args']; assert isinstance(req,dict)
            assert all(isinstance(k,str) and v in {'string','number','date'} for k,v in req.items())
            issues=c['issues']; assert isinstance(issues,list) and all(isinstance(x,str) for x in issues)
            cc.append((cid,c['module'],c['message'],c['source_locale'],tuple(sorted(req.items())),tuple(sorted(set(issues)))))
        issues=r['issues']; assert isinstance(issues,list) and all(isinstance(x,str) for x in issues)
        out.append((key,tuple(sorted(mods)),tuple(sorted(cc)),tuple(sorted(set(issues)))))
    return (obj['release'], tuple(sorted(out)), tuple(sorted(obj['summary'].items())))

def test_artifact_schema_and_shape():
    obj=load_candidate()
    canonical(obj)

def test_complete_semantics_match_sealed_truth():
    obj=load_candidate()
    assert canonical(obj)==canonical(EXPECTED)

def test_summary_is_self_consistent():
    obj=load_candidate()
    rows=obj['route_locales']
    assert obj['summary']['route_locale_count']==len(rows)
    assert obj['summary']['clean_count']==sum(1 for r in rows if not r['issues'])
    assert obj['summary']['issue_count']==sum(len(set(r['issues'])) for r in rows)
    assert obj['summary']['callsite_evaluations']==sum(len(r['callsites']) for r in rows)

def test_route_locale_and_callsite_identity_is_complete():
    obj=load_candidate(); exp=EXPECTED
    assert {(r['route'],r['locale']) for r in obj['route_locales']}=={(r['route'],r['locale']) for r in exp['route_locales']}
    got={(r['route'],r['locale']):{c['callsite_id'] for c in r['callsites']} for r in obj['route_locales']}
    want={(r['route'],r['locale']):{c['callsite_id'] for c in r['callsites']} for r in exp['route_locales']}
    assert got==want
