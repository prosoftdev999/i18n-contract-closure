import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent.parent))
from solution.browser import reconstruct
from solution.analyze import Analyzer

def main():
    local=Path(__file__).parent.parent/'environment/data'
    data=Path('/app/data') if (Path('/app/data')/'audit_context.json').exists() else local
    out=Path('/app/output') if data!=local else Path(__file__).parent.parent/'_local_output'
    out.mkdir(parents=True,exist_ok=True)
    release,responses,_=reconstruct(data)
    result=Analyzer(data,release,responses).build()
    (out/'i18n_contract.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
if __name__=='__main__': main()
