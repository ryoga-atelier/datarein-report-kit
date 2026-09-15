"""ヒアリング開始時の雛形生成。
実行: python3 scripts/new_case.py <出力dir> --client 会社名 --days 5 --names 佐藤,高橋,...
生成: case.json（テンプレの空欄つき）と hearing_state.json（進行管理）
"""
from pathlib import Path
import json, argparse
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('outdir'); ap.add_argument('--client',required=True)
    ap.add_argument('--days',type=int,default=5); ap.add_argument('--names',required=True)
    a=ap.parse_args()
    out=Path(a.outdir); out.mkdir(parents=True,exist_ok=True)
    names=[n.strip() for n in a.names.split(',') if n.strip()]
    tpl=json.loads((Path(__file__).parent.parent/'templates/case-template.json').read_text())
    person=tpl['people'][0]
    case=dict(tpl); case['client']=a.client; case['days']=a.days
    case['people']=[json.loads(json.dumps(person)) | {'name':n} for n in names]
    case['aptitude_map']['points']=[{'name':n,'score':0,'x':5,'y':5,'label':''} for n in names]
    (out/'case.json').write_text(json.dumps(case,ensure_ascii=False,indent=1),encoding='utf-8')
    (out/'hearing_state.json').write_text(json.dumps(
        {'client':a.client,'order':names,'current':0,'phase':'B','answers':{n:{} for n in names},'approved':[]},
        ensure_ascii=False,indent=1),encoding='utf-8')
    print(json.dumps({'case':str(out/'case.json'),'state':str(out/'hearing_state.json'),'people':names},ensure_ascii=False))
if __name__=='__main__': main()
