"""生成済みレポート一式の機械検査（machine_ok の判定）。描画の目視は別途行う。
実行: uv run --with pypdf --with pymupdf python3 scripts/validate.py <case.json> [--out DIR]
検査: 点数整合 / ページ数 / 禁止語・口調語 / ページ使用率 / 納品コピーのSHA一致 / PNG描画出力
"""
from pathlib import Path
import json, sys, re, hashlib, argparse
import fitz
from pypdf import PdfReader

BANNED=['次回','未反映','未確認','�','Codex','ポジション','足枷','粗悪','置いてきぼり','足を引っ張','＊',
        '第1段階','第2段階','第3段階','第4段階','90日計画','受動的','ぐんぐん','かなり便利','いかがでしたでしょうか',
        'じゃ。','じゃが、','ゆえ、','おらん','ぬし','わし','言うて','非常に','極めて','多角的に','に他ならない']
FOOTER_FIXED=['総合判断を先に定め','日間の研修修了時点の所見に基づく']

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('case'); ap.add_argument('--out',default=None)
    a=ap.parse_args()
    case_path=Path(a.case).resolve(); case=json.loads(case_path.read_text())
    OUT=Path(a.out).resolve() if a.out else case_path.parent/'output'
    issuer=case.get('issuer','DATAREIN'); people=case['people']; n=len(people)
    problems=[]; report={}
    # 1. 点数整合
    for p in people:
        if abs(sum(p['scores'])-p['score'])>1e-9: problems.append(f"点数不整合: {p['name']}")
        if any(abs(s*2-round(s*2))>1e-9 for s in p['scores']): problems.append(f"0.5刻み違反: {p['name']}")
    report['scores']='ok' if not any('点数' in x or '刻み' in x for x in problems) else 'NG'
    # 2. PDFの存在とページ数
    pdfs=sorted((OUT/'個別PDF').glob('*.pdf'))
    if len(pdfs)!=n+1: problems.append(f"個別PDFが{len(pdfs)}件（期待{n+1}件）")
    pages={}
    for i,f in enumerate(pdfs):
        c=len(PdfReader(f).pages); pages[f.name]=c
        lo,hi=(4,6) if i<n else (3,6)
        if not lo<=c<=hi: problems.append(f"ページ数逸脱: {f.name}={c}")
    report['pages']=pages
    # 3. 禁止語（結合PDF全文とmd）
    comb=list(OUT.glob('*_全*枚.pdf'))
    text=''.join(pg.extract_text() for f in comb for pg in PdfReader(f).pages)
    mds=list(OUT.glob('*編集用原稿.md'))
    if mds: text+=mds[0].read_text()
    hits=sorted({w for w in BANNED+list(case.get('banned_extra',[])) if w in text})
    if hits: problems.append(f"禁止語検出: {hits}")
    report['banned']='ok' if not hits else hits
    # 4. 使用率とPNG描画
    png=OUT/'_png'; png.mkdir(exist_ok=True)
    fills={}
    for f in pdfs:
        d=fitz.open(f)
        for i,pg in enumerate(d):
            pg.get_pixmap(dpi=80).save(str(png/f"{f.stem[:2]}-p{i+1}.png"))
            blocks=[b for b in pg.get_text('blocks') if b[4].strip()]
            body=[b[3] for b in blocks if b[3]<780]
            fill=round((max(body)-60)/(782-60)*100) if body else 0
            fills[f"{f.stem[:2]}-P{i+1}"]=fill
            if fill<50 or fill>98: problems.append(f"使用率逸脱: {f.name} P{i+1}={fill}%")
            if not any(k in pg.get_text() for k in FOOTER_FIXED): problems.append(f"フッター注記欠落: {f.name} P{i+1}")
    report['fill_percent']=fills
    # 5. 納品コピーのSHA一致
    deliver=OUT/'納品用'
    if deliver.is_dir():
        for p,f in zip(people,pdfs[:n]):
            dst=deliver/f"{p['name']}さん"/f"{issuer}_{p['name']}さん_個人分析レポート.pdf"
            if not dst.is_file(): problems.append(f"納品ファイル欠落: {dst.name}"); continue
            if hashlib.sha256(dst.read_bytes()).hexdigest()!=hashlib.sha256(f.read_bytes()).hexdigest():
                problems.append(f"納品SHA不一致: {dst.name}")
    else:
        problems.append('納品用フォルダなし')
    report['machine_ok']=not problems
    report['problems']=problems
    report['png_dir']=str(png)
    print(json.dumps(report,ensure_ascii=False,indent=1))
    sys.exit(0 if not problems else 1)

if __name__=='__main__':
    main()
