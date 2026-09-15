"""DATAREIN 研修分析レポート生成器（datarein-report-kit）。

case.json から 個人5ページ×N名＋全体4ページ のPDF一式を生成する。
実行: uv run --with reportlab --with pypdf python3 scripts/build_report.py <case.json> [--out DIR]
生成: 結合PDF / 個別PDF / ZIP / 編集用md / 納品用フォルダ（人名別＋全体）
検証: 点数整合・禁止語・ページ数のアサート内蔵（描画目視と validate.py は別途）。
出自: 2026-09-14 ナインアース案件 build_report_v17.py の一般化。
"""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import json, html, re, sys, hashlib, argparse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, white
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table,
                                TableStyle, Flowable, PageBreak, KeepTogether)
from reportlab.lib.styles import ParagraphStyle
from pypdf import PdfReader, PdfWriter

# ---------------- 既定値（case.json の同名キーで上書き可） ----------------
DEFAULT_DIMENSIONS=[
 {"name":"理解度・活用レベル","short":"理解・活用","maximum":4,"baseline":2,"weight":"40%",
  "base_action":"2点：身近な用途で基本的な指示・利用ができる。","upper_action":"3点：目的に合わせ指示を調整・応用。4点：理解を伴い成果を再現。",
  "anchor":"0〜1点：理解・指示・用途の具体化に支援が必要。2点：個人の基礎利用。2.5点：基礎から目的に応じた応用へ進む中間区分。3点：目的に合わせて指示を調整・応用。4点：仕組みを理解し、実務成果を再現。"},
 {"name":"意欲・主体性","short":"意欲・主体性","maximum":2,"baseline":1,"weight":"20%",
  "base_action":"1点：働きかけを受けて取り組む段階。","upper_action":"1.5点：改善に積極的。2点：自ら課題を見つけ継続改善。",
  "anchor":"0点：取組への継続支援を要する。0.5点：追おうとする姿勢はあるが、働きかけを待つ段階。1点：働きかけを受けて取り組む段階。1.5点：改善に積極的。2点：自ら課題を見つけ継続改善。"},
 {"name":"組織活用への準備度","short":"組織活用の準備度","maximum":4,"baseline":2,"weight":"40%",
  "base_action":"2点：支援付きの限定業務への参加を見込む。","upper_action":"2.5点：運用へ視野が広がる。3点：小規模運用。4点：定着・展開。",
  "anchor":"0〜1点：用途・手順が整った後の利用を優先。1.5点：形にする役割は担えるが利用者・運用視点に課題。2点：支援付きの限定業務への参加を見込む。2.5点：運用へ視野が広がるが設計・実行には支援が必要。3点：小規模な試行・共有・運用を担う。4点：組織の定着・展開を自走。"}]
DEFAULT_LEVELS=[{"score":0,"label":"利用の前提づくり","description":"目的の共有と初歩操作から継続支援が必要。"},
 {"score":1,"label":"基礎理解を支援","description":"理解や操作の一つ一つに支援が必要。"},
 {"score":2,"label":"用途を絞って伴走","description":"身近な用途を具体化し、実演と支援で取り組む。"},
 {"score":3,"label":"支援下で限定利用","description":"手順と対象を限定して、伴走下で利用する。"},
 {"score":4,"label":"基礎活用を定着中","description":"使える場面はあるが、理解・応用に支援が必要。"},
 {"score":5,"label":"個人の基礎活用","description":"個人で基礎活用できる。応用・組織運用は支援前提。"},
 {"score":6,"label":"個人で応用・改善","description":"目的に合わせた工夫ができ、推進役への準備段階。"},
 {"score":7,"label":"小規模な推進を担当","description":"限定業務・チームで試行・共有・運用を担える。"},
 {"score":8,"label":"チームで改善を主導","description":"運用と役割を整え、効果を確認して改善する。"},
 {"score":9,"label":"継続成果を横展開","description":"複数業務へ展開し、他者育成と成果の再現を進める。"},
 {"score":10,"label":"組織で自走・定着","description":"課題設定・応用・運用・効果検証・育成を自走し、成果を再現。"}]
DEFAULT_FOCUS=[
 {"name":"指示の具体性・適切さ","detail":"目的・条件を言葉にし、出力に応じてAIへの指示を調整できるか。"},
 {"name":"業務・場面への接続","detail":"どの業務で何のために使うかを考え、目的に合う使い方を選べるか。"},
 {"name":"利用者目線・導入後の運用","detail":"実際の使われ方、利用手順、確認担当、保守・改善まで考えられるか。"}]
DEFAULT_TEXTS={
 "weight_reason":"指示・業務応用40%、改善への姿勢20%、利用者目線・管理運用・他者展開40%。選抜目的に照らし、個人の活用と組織で使い続ける力を同じ重さで評価する。意欲は重要だが、姿勢だけで実用性や運用力を置き換えない。",
 "rule":"内訳点の合計＝総合点。基準差＝内訳点－比較基準点であり、再加算しない。比較基準は持ち点や到達認定ではない。研修で見られた課題と、今回の所見だけでは判断できない領域を区別する。",
 "judgment_rule":"{issuer}の見解を軸に研修中の講師所見を反映。観察された強み・課題と、その所見からの解釈を区別する。所見にない実績は補わない。役回り案は研修所見に基づく育成・配置の参考提案とする。",
 "baseline":"5点は、個人として基礎的にAIを活用できるが、応用や組織運用には支援が必要な水準。個人で使っている、形にできるという事実だけで、必ず5点を超えるわけではない。総合点は異なる強み・課題の組合せを含むため、5点という合計だけで各項目の基準到達を認定しない。",
 "ceiling":"10点は、課題設定から応用、管理運用、効果検証、他者育成まで自走し、組織で継続的な成果を再現できる水準。",
 "level_note":"点数帯は役回り検討の目安。0.5点差は{issuer}の判断上の区分であり、客観的な測定差ではない。将来への期待は現時点の実績と分けて記す。",
 "disclosure":"総合判断を先に定め、その根拠を3項目に構造化して整理した。独立した項目試験の実測値や標準化・検証済みの適性検査ではない。",
 "timing":"{days}日間の研修修了時点の所見に基づく{issuer}の評価。研修外の能力全般を判定するものではない。0.5点差は測定差ではない。",
 "method":"本資料は、{days}日間の研修における講師の日別・場面別の観察所見をもとに、{issuer}がまとめた評価と適性の整理である。受講者ごとの総合評価を先に定めたうえで、その根拠を{dims}の3項目に構造化して整理した。受講者は所属部署が異なる場合があるため、本資料の役回りは同一チームの編成計画ではなく、チームに配置する場合にどの役回りが適するかを示す参考である。",
 "subtitle":"{days}日間の研修で見られた強み・課題の分析と、チームに配置する場合の適性・役回りの整理",
 "scope_note":"本評価は{days}日間の研修修了時点の所見に基づく。研修外の業務遂行能力や継続運用の実績、恒常的な意欲までを判定するものではなく、個人の人格や能力の全体を評価するものでもない。0.5点差は{issuer}の判断上の区分で、客観的な測定差ではない。役回りの提案は研修所見からの育成・配置の参考提案であり、最終判断は{client}様に委ねる。",
 "work_image_note":"本節は、研修所見から見込める活用範囲についての{issuer}の見立てであり、実務での実績を確認したものではない。実際の適用業務は、{client}様の業務内容に合わせて選定いただきたい。",
 "map_note":"本マップは研修所見に基づく{issuer}の定性的な配置であり、座標は測定値ではない。横軸は行動の起点が「形にする側」か「使う側」のどちらに寄るか、縦軸は現時点でどこまで支援なしに進められるかを示す。",
 "title":"AI研修 {days}日間の総合評価レポート"}
BANNED=['次回','未反映','未確認','�','Codex','ポジション','足枷','粗悪','置いてきぼり','足を引っ張','＊',
        '第1段階','第2段階','第3段階','第4段階','90日計画','受動的','ぐんぐん','かなり便利','いかがでしたでしょうか',
        'じゃ。','じゃが、','ゆえ、','おらん','ぬし','わし','言うて','非常に','極めて','多角的に','に他ならない']

def load_case(path):
    case=json.loads(Path(path).read_text())
    issuer=case.get('issuer','DATAREIN'); client=case['client']; days=case.get('days',5)
    dims=case.get('dimensions',DEFAULT_DIMENSIONS)
    fmt=dict(issuer=issuer,client=client,days=days,
             dims='・'.join(f"{d['short']}（{d['maximum']}点）" for d in dims))
    D=dict(case)
    D['issuer'],D['client'],D['days']=issuer,client,days
    D['dimensions']=dims
    D['levels']=case.get('levels',DEFAULT_LEVELS)
    D['focus']=case.get('focus',DEFAULT_FOCUS)
    for k,v in DEFAULT_TEXTS.items():
        D[k]=case.get(k,v).format(**fmt)
    n=len(D['people']); assert 2<=n<=10,f'受講者数は2〜10名を想定（現在{n}名）'
    total=sum(p['score'] for p in D['people']); raw=total/n
    D['_N'],D['_TOTAL'],D['_AVG']=n,total,round(raw,1)
    D['stats_note']=case.get('stats_note',
        f"対象は指定{n}名。平均は{total:g}÷{n}＝{raw:g}点を小数第1位で{round(raw,1):g}点と表示。合計は単純集計であり、組織の能力点ではない。")
    D['edition']=case.get('edition','分析レポート')
    return D

def find_fonts(case):
    cand=case.get('fonts',{})
    pairs=[(cand.get('regular'),cand.get('bold'))] if cand else []
    home=Path.home()
    pairs+= [(home/'Library/Fonts/NotoSansJP-Regular.ttf',home/'Library/Fonts/NotoSansJP-Bold.ttf'),
             (Path('/Library/Fonts/NotoSansJP-Regular.ttf'),Path('/Library/Fonts/NotoSansJP-Bold.ttf'))]
    for r,b in pairs:
        if r and b and Path(r).is_file() and Path(b).is_file(): return str(r),str(b)
    raise SystemExit('NotoSansJP-Regular.ttf / NotoSansJP-Bold.ttf が見つからない。'
                     'Google Fonts から Noto Sans JP を取得し ~/Library/Fonts へ置くか、case.json の fonts で指定する。')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('case'); ap.add_argument('--out',default=None)
    args=ap.parse_args()
    case_path=Path(args.case).resolve()
    D=load_case(case_path)
    OUT=Path(args.out).resolve() if args.out else case_path.parent/'output'
    OUT.mkdir(parents=True,exist_ok=True); (OUT/'個別PDF').mkdir(exist_ok=True)
    build(D,OUT,case_path)

# ---------------- 点数検証 ----------------
def prepare_people(D):
    P=[]
    for new in D['people']:
        p=dict(new)
        assert abs(sum(p['scores'])-p['score'])<1e-9,(p['name'],'内訳合計≠総合点')
        p['deltas']=[s-d['baseline'] for s,d in zip(p['scores'],D['dimensions'])]
        assert all(0<=s<=d['maximum'] and abs(s*2-round(s*2))<1e-9 for s,d in zip(p['scores'],D['dimensions'])),(p['name'],'0.5刻み/範囲外')
        for k in ['pos','strengths','issues','timeline','axis_detail','traits','leadership','risks','placement','work_image','manager_guidance','checklist']:
            assert p.get(k),(p['name'],f'{k} が未記入')
        assert all(p['pos'].get(x) for x in ['role','fit','timing','scope'])
        P.append(p)
    return P


# ---------------- 描画（v17の設計トークンを踏襲） ----------------
W,H=A4; M=39; CW=W-2*M
INK=HexColor('#172F43'); TEAL=HexColor('#176A71'); MUTED=HexColor('#5C6D7A')
LINE=HexColor('#D8E1E6'); PALE=HexColor('#F0F5F6'); AMBER=HexColor('#9A6841'); HEAD=HexColor('#F4F7F8')
AXIS_COLORS=[TEAL,HexColor('#64959B'),HexColor('#6D7F9A')]

def st(size=9.6,leading=15,bold=False,color=INK,align=0,space=0):
    return ParagraphStyle('s',fontName='JPB' if bold else 'JP',fontSize=size,leading=leading,
                          wordWrap='CJK',textColor=color,alignment=align,spaceAfter=space)

def build(D,OUT,case_path):
    reg,bold=find_fonts(D)
    pdfmetrics.registerFont(TTFont('JP',reg)); pdfmetrics.registerFont(TTFont('JPB',bold))
    pdfmetrics.registerFontFamily('JP',normal='JP',bold='JPB')
    P=prepare_people(D); N=D['_N']
    S_BODY=st(); S_SMALL=st(8.4,12.6,color=MUTED); S_NOTE=st(7.8,11.4,color=MUTED)
    S_H1=st(12,16,True,INK,space=4); S_H2=st(10,14,True,TEAL)
    S_LABEL=st(8,11,True,MUTED); S_CELL=st(9,13.6); S_CELLB=st(9,13.6,True)
    def esc(s): return html.escape(s).replace('\n','<br/>')
    def fdelta(x): return ('＋' if x>0 else '－' if x<0 else '')+f'{abs(x):.1f}'
    def para(s,style=S_BODY): return Paragraph(esc(s),style)
    def h1(s): return Paragraph(esc(s),S_H1)
    def h2(s): return Paragraph(esc(s),S_H2)
    def grid(rows,widths,head=False,pad=6,bg=None,inner=True):
        t=Table(rows,colWidths=widths,hAlign='LEFT')
        cmds=[('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),pad),('RIGHTPADDING',(0,0),(-1,-1),pad),
              ('TOPPADDING',(0,0),(-1,-1),pad),('BOTTOMPADDING',(0,0),(-1,-1),pad)]
        if inner: cmds+=[('LINEBELOW',(0,0),(-1,-2),0.5,LINE)]
        if head: cmds+=[('BACKGROUND',(0,0),(-1,0),INK),('TEXTCOLOR',(0,0),(-1,0),white)]
        if bg: cmds+=[('BACKGROUND',(0,0),(-1,-1),bg)]
        t.setStyle(TableStyle(cmds));return t
    def anchor_seg(dim,s):
        for seg in dim['anchor'].split('。'):
            seg=seg.strip()
            if '：' not in seg: continue
            label,desc=seg.split('：',1)
            m=re.fullmatch(r'(\d+(?:\.\d+)?)(?:〜(\d+(?:\.\d+)?))?点',label)
            if not m: continue
            lo=float(m.group(1)); hi=float(m.group(2) or m.group(1))
            if lo<=s<=hi: return label,desc
        return f'{s:g}点',''
    def labeled(rows,lw=92,style=S_CELL):
        return grid([[Paragraph(esc(k),S_LABEL),Paragraph(esc(v),style)] for k,v in rows],[lw,CW-lw],pad=5)
    def bullets(items,style=S_BODY):
        return [Paragraph('・ '+esc(v),style) for v in items]

    class Gauge(Flowable):
        def __init__(self,score,width): super().__init__(); self.score=score; self.w=width
        def wrap(self,aw,ah): return self.w,34
        def draw(self):
            c=self.canv; w=self.w
            c.setFont('JP',7.3); c.setFillColor(MUTED); c.drawString(0,26,'総合点と基準水準'); c.drawRightString(w,26,'破線：基準の5.0点')
            c.setFillColor(HexColor('#DDE6E9')); c.rect(0,12,w,8,fill=1,stroke=0)
            c.setFillColor(TEAL if self.score>=5 else AMBER); c.rect(0,12,w*self.score/10,8,fill=1,stroke=0)
            c.setStrokeColor(INK); c.setLineWidth(.8); c.setDash([2,2]); c.line(w*.5,8,w*.5,24); c.setDash([])
            c.setFont('JP',7); c.setFillColor(MUTED)
            for v in [0,5,10]: c.drawCentredString(w*v/10,1,str(v))

    class AxisBars(Flowable):
        def __init__(self,p,width): super().__init__(); self.p=p; self.w=width
        def wrap(self,aw,ah): return self.w,3*22+14
        def draw(self):
            c=self.canv; lx=96; gw=self.w-lx-70
            for i,(d,col) in enumerate(zip(D['dimensions'],AXIS_COLORS)):
                y=self.wrap(0,0)[1]-16-i*22; s=self.p['scores'][i]; bw=gw*s/d['maximum']
                c.setFont('JPB',8.3); c.setFillColor(INK); c.drawString(0,y,d['name'])
                c.setFillColor(HexColor('#DDE6E9')); c.rect(lx,y-2,gw,10,fill=1,stroke=0)
                c.setFillColor(col); c.rect(lx,y-2,bw,10,fill=1,stroke=0)
                bx=lx+gw*d['baseline']/d['maximum']; c.setStrokeColor(INK); c.setLineWidth(.8); c.setDash([2,2]); c.line(bx,y-5,bx,y+11); c.setDash([])
                dl=self.p['deltas'][i]
                c.setFont('JPB',8.6); c.setFillColor(INK); c.drawString(lx+gw+8,y,f"{s:.1f} / {d['maximum']}点")
                c.setFont('JP',7.2); c.setFillColor(TEAL if dl>0 else AMBER if dl<0 else MUTED); c.drawString(lx+gw+8,y-9,'基準差 '+fdelta(dl))
            c.setFont('JP',7); c.setFillColor(MUTED); c.drawString(lx,0,'破線＝各項目の比較基準点')

    class TotalStrip(Flowable):
        def __init__(self,me,width): super().__init__(); self.me=me; self.w=width
        def wrap(self,aw,ah): return self.w,74
        def draw(self):
            c=self.canv; w=self.w; y=42
            c.setFillColor(HexColor('#DDE6E9')); c.rect(0,y,w,8,fill=1,stroke=0)
            c.setStrokeColor(INK); c.setLineWidth(.8); c.setDash([2,2]); c.line(w*.5,y-6,w*.5,y+16); c.setDash([])
            c.setFont('JP',6.8); c.setFillColor(MUTED); c.drawCentredString(w*.5,y+19,'基準5.0')
            ax=w*(D['_TOTAL']/D['_N'])/10; c.setStrokeColor(MUTED); c.setLineWidth(.7); c.line(ax,y-2,ax,y+12)
            c.drawCentredString(ax,y-11,f"平均{D['_AVG']:g}")
            others=[q for q in P if q['name']!=self.me['name']]
            for j,q in enumerate(others):
                x=w*q['score']/10
                c.setFillColor(MUTED); c.circle(x,y+4,2.6,fill=1,stroke=0)
                yy=20-(j%3)*9
                c.setFont('JP',6.8); c.setFillColor(MUTED); c.drawCentredString(x,yy,f"{q['name']}さん {q['score']:.1f}")
            x=w*self.me['score']/10
            c.setFillColor(TEAL if self.me['score']>=5 else AMBER); c.circle(x,y+4,4.2,fill=1,stroke=0)
            c.setFont('JPB',8); c.setFillColor(INK); c.drawCentredString(x,y+21,f"{self.me['name']}さん {self.me['score']:.1f}")
            c.setFont('JP',6.8); c.setFillColor(MUTED)
            for v in [0,10]: c.drawCentredString(w*v/10,y-11,str(v))

    class GroupBars(Flowable):
        def wrap(self,aw,ah): self.w=aw; return aw,44+len(P)*23+20
        def draw(self):
            c=self.canv; gx=60; gw=self.w-111; top=self.wrap(self.w,0)[1]-10
            for i,(d,col) in enumerate(zip(D['dimensions'],AXIS_COLORS)):
                x=i*116; c.setFillColor(col); c.rect(x,top+2,7,7,fill=1,stroke=0); c.setFont('JP',8.1); c.setFillColor(MUTED); c.drawString(x+12,top+1,d['short'])
            c.setFont('JPB',8.1); c.setFillColor(TEAL); c.drawRightString(self.w,top+1,f"平均{D['_AVG']:g} / 合計{D['_TOTAL']:g}点")
            y0=top-16; depth=len(P)*23+18
            for tick in range(0,11,2):
                xx=gx+gw*tick/10; c.setStrokeColor(LINE); c.setLineWidth(.5); c.line(xx,y0-depth,xx,y0+2); c.setFont('JP',7.2); c.setFillColor(MUTED); c.drawCentredString(xx,y0-depth-10,str(tick))
            c.setStrokeColor(INK); c.setLineWidth(.8); c.setDash([2,2]); c.line(gx+gw*.5,y0-depth,gx+gw*.5,y0+3); c.setDash([])
            for i,p in enumerate(P):
                yy=y0-13-i*23; c.setFont('JPB',9); c.setFillColor(INK); c.drawString(0,yy,p['name']+'さん'); xx=gx
                for k,(s,col) in enumerate(zip(p['scores'],AXIS_COLORS)):
                    bw=gw*s/10; c.setFillColor(col); c.rect(xx,yy-2,bw,13,fill=1,stroke=0)
                    if bw>18:
                        c.setFont('JPB',7.5); c.setFillColor(white); c.drawCentredString(xx+bw/2,yy+1,f'{s:g}')
                    xx+=bw
                c.setFont('JPB',10); c.setFillColor(INK); c.drawString(xx+6,yy,f"{p['score']:.1f}")

    HAS_MAP=bool(D.get('aptitude_map'))
    class AptitudeMap(Flowable):
        def __init__(self,width,focus=None,h=188): super().__init__(); self.w=width; self.focus=focus; self.h=h
        def wrap(self,aw,ah): return self.w,self.h
        def draw(self):
            c=self.canv; am=D['aptitude_map']
            L,R,B,T=118,self.w-118,20,self.h-14
            c.setFillColor(HexColor('#F7FAFB')); c.rect(L,B,R-L,T-B,fill=1,stroke=0)
            c.setStrokeColor(LINE); c.setLineWidth(.8); c.rect(L,B,R-L,T-B,fill=0,stroke=1)
            mx,my=(L+R)/2,(B+T)/2
            c.setStrokeColor(MUTED); c.setLineWidth(.7); c.setDash([2,2]); c.line(mx,B,mx,T); c.line(L,my,R,my); c.setDash([])
            c.setFont('JP',7.6); c.setFillColor(MUTED)
            c.drawString(L+6,T-11,am['quadrants'][0]); c.drawRightString(R-6,T-11,am['quadrants'][1])
            c.drawString(L+6,B+5,am['quadrants'][2]); c.drawRightString(R-6,B+5,am['quadrants'][3])
            c.setFont('JPB',8.2); c.setFillColor(INK)
            c.drawRightString(L-8,my-3,am['x_left']); c.drawString(R+8,my-3,am['x_right'])
            c.drawCentredString(mx,T+5,am['y_top']); c.drawCentredString(mx,B-14,am['y_bottom'])
            for p in am['points']:
                x=L+(R-L)*p['x']/10; y=B+(T-B)*p['y']/10
                dim=self.focus is not None and p['name']!=self.focus
                col=MUTED if dim else (TEAL if p['score']>=5 else AMBER)
                c.setFillColor(col); c.circle(x,y,3.2 if dim else 4.6,fill=1,stroke=0)
                if not dim: c.setFillColor(white); c.circle(x,y,1.6,fill=1,stroke=0)
                side=1 if p['x']<5 else -1
                tx=x+side*9
                def _txt(s,ty,fn,fs,tcol):
                    tw=c.stringWidth(s,fn,fs)
                    bx=tx if side>0 else tx-tw
                    c.setFillColor(HexColor('#F7FAFB')); c.rect(bx-2,ty-1.5,tw+4,fs+2,fill=1,stroke=0)
                    c.setFont(fn,fs); c.setFillColor(tcol)
                    (c.drawString if side>0 else c.drawRightString)(tx,ty,s)
                _txt(f"{p['name']}さん {p['score']:.1f}",y+2,'JPB' if not dim else 'JP',8.6 if not dim else 7.6,INK if not dim else MUTED)
                if not dim: _txt(p['label'],y-8,'JP',7.4,MUTED)

    class NumberedCanvas(canvas.Canvas):
        def __init__(self,*a,**k): super().__init__(*a,**k); self._saved=[]
        def showPage(self): self._saved.append(dict(self.__dict__)); self._startPage()
        def save(self):
            n=len(self._saved)
            for s in self._saved:
                self.__dict__.update(s)
                self.setFont('JP',8); self.setFillColor(MUTED); self.drawRightString(W-M,H-61-8*.83,f'{self._pageNumber:02d} / {n:02d}')
                canvas.Canvas.showPage(self)
            canvas.Canvas.save(self)

    def make_doc(path,kind,title):
        def on_page(c,doc):
            c.saveState()
            c.setFont('JPB',16); c.setFillColor(INK); c.drawString(M,H-22-16*.83,D['issuer'])
            c.setFont('JP',8.3); c.setFillColor(MUTED); c.drawString(M+110,H-27-8.3*.83,D['title'])
            c.drawRightString(W-M,H-28-7.8*.83,f"{D['client']} 様 / 関係者限り")
            c.setStrokeColor(LINE); c.setLineWidth(.6); c.line(M,H-47,W-M,H-47)
            c.setFont('JPB',8.3); c.setFillColor(TEAL); c.drawString(M,H-61-8.3*.83,kind)
            c.line(M,H-791,W-M,H-791)
            c.setFont('JP',7.05); c.setFillColor(MUTED); c.drawString(M,H-798-7.05*.83,D['disclosure']); c.drawString(M,H-810-7.05*.83,D['timing'])
            c.restoreState()
        doc=BaseDocTemplate(str(path),pagesize=A4,leftMargin=M,rightMargin=M,topMargin=72,bottomMargin=60,
                            title=title,author=D['issuer'],subject=D['subtitle'],creator=D['issuer']+' Training Analysis')
        doc.addPageTemplates([PageTemplate(id='p',frames=[Frame(M,60,CW,H-72-60,leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)],onPage=on_page)])
        return doc

    def hero(p):
        col=TEAL if p['score']>=5 else AMBER
        left=[Paragraph(D['issuer']+'総合評価',st(8.2,11,True,MUTED)),
              Paragraph(f"<font size=40 color='{col.hexval()}'><b>{p['score']:.1f}</b></font> <font size=8.7 color='{MUTED.hexval()}'>/ 10点</font>",st(40,46)),
              Paragraph(esc(p['role']),st(8.4,12,True,col))]
        right=[para(p['summary'],st(9.2,14)),Spacer(1,8),Gauge(p['score'],CW-191)]
        t=Table([[left,right]],colWidths=[165,CW-165])
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),PALE),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),13),
                               ('RIGHTPADDING',(0,0),(-1,-1),13),('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10)]))
        return t

    def position_box(p):
        pos=p['pos']
        rows=[[Paragraph('チームに配置する場合に向く役回り（適性）',st(8.2,11,True,white)),''],
              [Paragraph('役回り',S_LABEL),Paragraph(esc(pos['role']),st(10.5,15,True,INK))],
              [Paragraph('向いている理由',S_LABEL),Paragraph(esc(pos['fit']),S_CELL)],
              [Paragraph('参加の条件',S_LABEL),Paragraph(esc(pos['timing']),S_CELL)],
              [Paragraph('担当範囲',S_LABEL),Paragraph(esc(pos['scope']),S_CELL)],
              [Paragraph('結論',S_LABEL),Paragraph(esc(p['conclusion']),S_CELL)]]
        t=Table(rows,colWidths=[86,CW-86],hAlign='LEFT')
        t.setStyle(TableStyle([('SPAN',(0,0),(1,0)),('BACKGROUND',(0,0),(-1,0),TEAL),('BOX',(0,0),(-1,-1),0.8,TEAL),
                               ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),
                               ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),('LINEBELOW',(0,1),(-1,-2),0.4,LINE)]))
        return t

    def two_col(title_l,items_l,title_r,items_r):
        def cell(title,items,col):
            out=[Paragraph(esc(title),st(9.4,13,True,col))]
            for it in items:
                out.append(Paragraph(f"<b>{esc(it['title'])}</b>",st(9,13,color=INK)))
                out.append(Paragraph(esc(it['body']),st(8.6,13,color=INK,space=4)))
            return out
        t=Table([[cell(title_l,items_l,TEAL),cell(title_r,items_r,AMBER)]],colWidths=[CW/2,CW/2])
        t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),
                               ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),4),('LINEAFTER',(0,0),(0,0),0.6,LINE),
                               ('LINEABOVE',(0,0),(-1,0),0.6,LINE),('LINEBELOW',(0,0),(-1,-1),0.6,LINE)]))
        return t

    def score_table(p):
        rows=[[Paragraph(esc(x),st(7.7,10,True,white)) for x in ['評価観点と基準点','内訳 / 配点','基準差',f"講師所見と{D['issuer']}の判断"]]]
        for i,d in enumerate(D['dimensions']):
            ch=p['deltas'][i]
            col=TEAL if ch>0 else AMBER if ch<0 else MUTED
            tag='上回る' if ch>0 else '下回る' if ch<0 else '差なし'
            rows.append([[Paragraph(esc(d['name']),S_CELLB),Spacer(1,4),Paragraph(f"基準 {d['baseline']:.1f} / {d['maximum']}点",S_NOTE)],
                         Paragraph(f"<font size=13><b>{p['scores'][i]:.1f}</b></font><br/><font size=8 color='{MUTED.hexval()}'>/ {d['maximum']}点</font>",st(13,18,align=1)),
                         Paragraph(f"<font size=12 color='{col.hexval()}'><b>{fdelta(ch)}</b></font><br/><font size=7.5 color='{col.hexval()}'>{tag}</font>",st(12,17,align=1)),
                         Paragraph(esc(p['reasons'][i]),S_CELL)])
        t=Table(rows,colWidths=[110,55,51,CW-216],hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),INK),('BACKGROUND',(0,1),(0,-1),HEAD),('VALIGN',(0,0),(-1,-1),'TOP'),
                               ('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),7),
                               ('BOTTOMPADDING',(0,0),(-1,-1),7),('LINEBELOW',(0,1),(-1,-1),0.6,LINE)]))
        return t

    def equation(p):
        parts=[(d['short'],p['scores'][i]) for i,d in enumerate(D['dimensions'])]+[('総合点',p['score'])]
        cells=[]
        for i,(label,v) in enumerate(parts):
            col=TEAL if i==len(parts)-1 else INK
            cells.append(Paragraph(f"<font size=7.5 color='{MUTED.hexval()}'>{('= ' if i==len(parts)-1 else '+ ' if i else '')}{label}</font><br/><font size=17 color='{col.hexval()}'><b>{v:.1f}</b></font>",st(17,22)))
        t=Table([cells],colWidths=[CW/len(parts)]*len(parts))
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),PALE),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),('LEFTPADDING',(0,0),(-1,-1),12)]))
        return t

    def levels_grid(score):
        lo=int(score); hi=lo+1 if score!=lo else lo
        rows=[]; style_cmds=[]
        for idx,l in enumerate(D['levels']):
            mark='◀ 本人' if l['score'] in (lo,hi) else ''
            rows.append([Paragraph(f"<b>{l['score']}点</b>",st(8.2,11.6,color=TEAL if l['score'] in (lo,hi) else INK)),
                         Paragraph(esc(l['label']),st(8.2,11.6,bold=l['score'] in (lo,hi))),
                         Paragraph(esc(l['description']),st(7.9,11.6,color=MUTED)),
                         Paragraph(mark,st(7.6,11.6,True,TEAL))])
            if l['score'] in (lo,hi): style_cmds.append(('BACKGROUND',(0,idx),(-1,idx),PALE))
        t=Table(rows,colWidths=[40,120,CW-220,60],hAlign='LEFT')
        t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),
                               ('TOPPADDING',(0,0),(-1,-1),2.5),('BOTTOMPADDING',(0,0),(-1,-1),2.5),
                               ('LINEBELOW',(0,0),(-1,-2),0.4,LINE)]+style_cmds))
        return t

    def method_flow():
        F=[h1('評価の目的と方法'),para(D['method'],st(9.2,14.2)),Spacer(1,8),
           h2('評価で重視した3つの着眼点'),
           grid([[Paragraph(f"<b>{esc(x['name'])}</b>",S_CELL),Paragraph(esc(x['detail']),S_CELL)] for x in D['focus']],[150,CW-150],pad=5),Spacer(1,8),
           h2('評価軸と配点'),
           grid([[Paragraph(esc(x),st(7.7,10,True,white)) for x in ['評価軸','配点 / 基準点','比重','基準点と上位の行動']]]+
                [[Paragraph(f"<b>{esc(d['name'])}</b>",S_CELL),Paragraph(f"{d['maximum']}点 / {d['baseline']}点",S_CELL),
                  Paragraph(d['weight'],S_CELL),Paragraph(esc(d['base_action']+' '+d['upper_action']),st(8.5,12.8))] for d in D['dimensions']],
                [108,72,40,CW-220],head=True,pad=5),
           para(D['weight_reason'],S_SMALL),Spacer(1,8),
           h2('判断のルール'),para(D['rule'],st(8.8,13.4)),Spacer(1,3),para(D['judgment_rule'],st(8.8,13.4)),Spacer(1,3),para(D['baseline'],st(8.8,13.4))]
        return F

    def individual(p,i):
        kind=f"{D['issuer']} 研修修了時の個人評価｜{p['name']}さん"
        path=OUTDIR_PDF/f"{i+1:02d}_{D['issuer']}_{p['name']}さん_個人分析.pdf"
        doc=make_doc(path,kind,f"{D['issuer']} {p['name']}さん 個人分析")
        F=[Paragraph(esc(p['name']+'さん'),st(24,30,True)),Paragraph(esc(p['headline']),st(10.1,14,True)),Spacer(1,8),hero(p),Spacer(1,10),
           position_box(p),Spacer(1,10),
           two_col('研修で見られた強み',p['strengths'],'研修で見られた課題',p['issues']),Spacer(1,8),
           h2('項目別の内訳と基準差'),Spacer(1,2),AxisBars(p,CW),Spacer(1,8),h2('評価の位置づけ'),para(p['rationale'],S_SMALL),PageBreak()]
        F+=[h1('スコアプロファイル'),score_table(p),Spacer(1,3),
            para('基準差は内訳点と比較基準の差。別枠の裁量点や、基準到達の認定ではない。',S_NOTE),
            Spacer(1,4),equation(p),Spacer(1,8),
            h2(f"受講{D['_N']}名の中での位置"),TotalStrip(p,CW),para(D['stats_note'],S_NOTE),Spacer(1,6),
            h2('総合点の尺度と本人の位置'),levels_grid(p['score']),para(D['level_note'],S_NOTE),PageBreak()]
        F+=[h1(f"研修{D['days']}日間の経過所見"),
            grid([[Paragraph(f"<b>{esc(r['period'])}</b>",st(8.6,12.6,True)),Paragraph(esc(r['obs']),st(8.8,13.2))] for r in p['timeline']],[96,CW-96],pad=5),Spacer(1,10),
            h1('観点別の所見・解釈・配置への含意')]
        for k,(d,ax) in enumerate(zip(D['dimensions'],p['axis_detail'])):
            lab,desc=anchor_seg(d,p['scores'][k])
            rows=[('研修で見られた行動',ax['observed']),(f"{D['issuer']}の解釈",ax['interpretation']),('配置への含意',ax['implication']),
                  ('尺度上の位置',f"{p['scores'][k]:.1f}点（{lab}：{desc}）")]
            F.append(KeepTogether([h2(d['name']),Spacer(1,2),labeled(rows,style=st(8.7,13.0)),Spacer(1,5)]))
        F+=[PageBreak()]
        F+=[h1('人材像：研修で見られた行動特性'),
            labeled([('仕事の進め方',p['traits']['work']),('AIとの向き合い方',p['traits']['ai']),('周囲との関わり',p['traits']['people'])]),Spacer(1,10),
            h1('任せる範囲と必要な支援'),
            labeled([('任せてよいこと','\n'.join('・'+x for x in p['placement']['allow'])),
                     ('まだ任せないこと','\n'.join('・'+x for x in p['placement']['not_yet'])),
                     ('必要な支援・伴走','\n'.join('・'+x for x in p['placement']['support']))]),Spacer(1,10),
            h1('リーダー適性の見立て'),
            grid([[Paragraph(f"<b>{esc(p['leadership']['verdict'])}</b>",st(9.6,14,color=TEAL)),Paragraph(esc(p['leadership']['body']),S_CELL)]],[150,CW-150],pad=7,bg=PALE,inner=False),Spacer(1,10),
            h1('配置上のリスクと対策'),
            grid([[Paragraph('想定されるリスク',st(7.7,10,True,white)),Paragraph('対策',st(7.7,10,True,white))]]+
                 [[Paragraph(esc(r['risk']),S_CELL),Paragraph(esc(r['measure']),S_CELL)] for r in p['risks']],[CW*.45,CW*.55],head=True),
            PageBreak()]
        F+=[h1('実務でのAI活用イメージ')]+bullets(p['work_image'])+[para(D['work_image_note'],S_NOTE),Spacer(1,10),
            h1('上司・推進責任者向けの関わり方')]+bullets(p['manager_guidance'])+[Spacer(1,10),
            h1('次に確認する観点')]+[Paragraph('□ '+esc(v),S_BODY) for v in p['checklist']]+[Spacer(1,10),
            h1('成長が確認できた場合の次の役回り'),para(p['next_position']),Spacer(1,6),
            para('将来への期待：'+p['future'],S_SMALL)]
        if HAS_MAP:
            F+=[Spacer(1,10),h2(f"受講{D['_N']}名の中での適性上の位置"),AptitudeMap(CW,focus=p['name'],h=150),
                para(f"座標は研修所見からの定性配置であり、測定値ではない。読み方の詳細は全体版「{D['_N']}名の適性マップ」を参照。",S_NOTE)]
        F+=[Spacer(1,8),h2('評価の範囲と注記'),para(D['scope_note'],S_NOTE),para(p['deduction_summary'],S_NOTE)]
        doc.build(F,canvasmaker=NumberedCanvas)
        return path

    def overall():
        g=D['group_plan']
        path=OUTDIR_PDF/f"{D['_N']+1:02d}_{D['issuer']}_全体分析と適性整理.pdf"
        doc=make_doc(path,f"{D['issuer']} 研修修了時の全体評価とチーム配置の適性整理",f"{D['issuer']} 全体分析と適性整理")
        F=[Paragraph(f"{D['days']}日間の総合評価と判断の枠組み",st(21.5,27,True)),Spacer(1,6),para(D['overall_summary'],st(9.2,14.2)),Spacer(1,10)]
        F+=method_flow()+[PageBreak()]
        F+=[h1('評価軸ごとの尺度（アンカー）')]
        for d in D['dimensions']:
            F.append(KeepTogether([h2(f"{d['name']}（配点{d['maximum']}点 / 比較基準{d['baseline']}点）"),
                                   para(d['anchor'],st(8.8,13.6)),Spacer(1,6)]))
        F+=[Spacer(1,4),h1('総合点の位置づけ')]
        F.append(grid([[Paragraph(f"<b>{l['score']}点｜{esc(l['label'])}</b>",st(8.8,12.6,color=TEAL)),Paragraph(esc(l['description']),st(8.6,12.6))] for l in D['levels']],[161,CW-161],pad=3,inner=False))
        F+=[para('形にできること・使えることだけで5点超とはしない。0.5点差は判断上の区分で、測定差ではない。',S_NOTE),
            Spacer(1,4),para(D['ceiling'],S_SMALL),Spacer(1,8),
            h1(f"{D['_N']}名の総合点と項目別内訳"),GroupBars(),
            para(f"破線＝基準5点。指定{D['_N']}名の単純集計。",S_NOTE),PageBreak()]
        F+=[Paragraph(esc(g['title']),st(21.5,27,True)),Spacer(1,5),para(g['lead'],st(9.1,13.4)),Spacer(1,8),h1(f"{D['_N']}名の評価サマリー")]
        rows=[[Paragraph(esc(x),st(7.7,10,True,white)) for x in ['対象者','総合点','評価の要点']]]
        for p in P:
            rows.append([Paragraph(esc(p['name']+'さん'),st(8.6,12.6,True)),Paragraph(f"{p['score']:.1f}",st(8.6,12.6)),
                         Paragraph(esc(p['headline']),st(8.6,12.6))])
        F+=[grid(rows,[62,40,CW-102],head=True,pad=4),Spacer(1,8),h1(f"{D['_N']}名の役回り")]
        rows=[[Paragraph(esc(x),st(7.7,10,True,white)) for x in ['対象者','総合点','向いている役回り','参加の条件','担当範囲']]]
        for p in P:
            rows.append([Paragraph(esc(p['name']+'さん'),st(8.6,12.6,True)),Paragraph(f"{p['score']:.1f}",st(8.6,12.6)),Paragraph(esc(p['pos']['role']),st(8.6,12.6,True)),
                         Paragraph(esc(p['pos']['timing']),st(8.6,12.6)),Paragraph(esc(p['pos']['scope']),st(8.6,12.6))])
        F+=[grid(rows,[62,40,190,100,CW-392],head=True,pad=4)]
        F+=[Spacer(1,5),h1('配置判断のポイント')]
        for dp in g['decision_points']:
            F+=[Paragraph(f"<b>{esc(dp['title'])}</b>",st(9.2,13.0,color=INK)),para(dp['body'],st(8.8,13.0,space=4))]
        if HAS_MAP:
            am=D['aptitude_map']
            def _quad(p): return (0 if p['x']<5 else 1) if p['y']>=5 else (2 if p['x']<5 else 3)
            qb=[Paragraph('・ '+esc(f"{am['quadrants'][_quad(p)]}＝{p['name']}さん（{p['label']}）。総合{p['score']:.1f}点。"),st(9.4,15)) for p in sorted(am['points'],key=_quad)]
            F+=[PageBreak(),Paragraph(f"{D['_N']}名の適性マップ",st(21.5,27,True)),Spacer(1,8),AptitudeMap(CW,h=270),Spacer(1,2),para(D['map_note'],S_NOTE),Spacer(1,10),h1('象限の読み方')]+qb
            F+=[Spacer(1,12),h2('評価の範囲と注記'),para(D['scope_note'],S_NOTE),para(D['stats_note'],S_NOTE)]
        else:
            F+=[Spacer(1,10),h2('評価の範囲と注記'),para(D['scope_note'],S_NOTE),para(D['stats_note'],S_NOTE)]
        doc.build(F,canvasmaker=NumberedCanvas)
        return path

    OUTDIR_PDF=OUT/'個別PDF'
    paths=[individual(p,i) for i,p in enumerate(P)]+[overall()]
    pages={pth.name:len(PdfReader(pth).pages) for pth in paths}
    for pth in paths[:-1]: assert 4<=pages[pth.name]<=6,(pth.name,pages[pth.name])
    assert 3<=pages[paths[-1].name]<=6,(paths[-1].name,pages[paths[-1].name])
    total=sum(pages.values())
    PDF=OUT/f"{D['issuer']}_{D['client']}_AI研修{D['edition']}_全{total}枚.pdf"
    wr=PdfWriter()
    for pth in [paths[-1]]+paths[:-1]:  # 経営者向けに全体版を先頭へ
        for pg in PdfReader(pth).pages: wr.add_page(pg)
    wr.add_metadata({'/Title':f"{D['issuer']} {D['client']} AI研修{D['edition']}",'/Author':D['issuer'],'/Subject':D['subtitle']})
    with PDF.open('wb') as f: wr.write(f)
    reader=PdfReader(PDF); assert len(reader.pages)==total
    texts=[pg.extract_text() for pg in reader.pages]
    banned=BANNED+list(D.get('banned_extra',[]))
    hits=[w for t in texts for w in banned if w in t]
    assert not hits,('禁止語検出',sorted(set(hits)))
    zpath=OUT/f"{D['issuer']}_{D['edition']}_個別{D['_N']+1}冊.zip"
    with ZipFile(zpath,'w',ZIP_DEFLATED) as z:
        for pth in paths: z.write(pth,pth.name)
    with ZipFile(zpath) as z: assert z.testzip() is None
    write_md(D,P,OUT)
    deliver=OUT/'納品用'
    for p,pth in zip(P,paths[:-1]):
        d=deliver/f"{p['name']}さん"; d.mkdir(parents=True,exist_ok=True)
        dst=d/f"{D['issuer']}_{p['name']}さん_個人分析レポート.pdf"; dst.write_bytes(pth.read_bytes())
        assert hashlib.sha256(dst.read_bytes()).hexdigest()==hashlib.sha256(pth.read_bytes()).hexdigest()
    d=deliver/'全体'; d.mkdir(parents=True,exist_ok=True)
    (d/f"{D['issuer']}_全体分析と適性整理レポート.pdf").write_bytes(paths[-1].read_bytes())
    (d/f"{D['issuer']}_全冊子結合_全{total}枚.pdf").write_bytes(PDF.read_bytes())
    print(json.dumps({'pdf':str(PDF),'pages':pages,'total':total,'deliver':str(deliver)},ensure_ascii=False))

def write_md(D,P,OUT):
    md=[f"# {D['issuer']} AI研修 受講者{D['edition']}",'',f"{D['client']} 様",'',D['subtitle'],'',D['method'],'',D['scope_note'],'',
        '## 評価の枠組み','','着眼点:']+[f"- **{x['name']}** {x['detail']}" for x in D['focus']]+['',D['weight_reason'],'',D['rule'],'',D['judgment_rule'],'',
        '| 評価項目 | 配点 | 基準点 | 比重 | 尺度（アンカー） |','|---|---:|---:|---:|---|']
    for d in D['dimensions']: md.append(f"| {d['name']} | {d['maximum']} | {d['baseline']} | {d['weight']} | {d['anchor']} |")
    md+=['','| 点数 | 到達水準 | 行動の目安 |','|---:|---|---|']+[f"| {l['score']} | {l['label']} | {l['description']} |" for l in D['levels']]
    for p in P:
        md+=['','---','',f"## {p['name']}さん 個人分析",'',f"**総合点 {p['score']:.1f} / 10点｜{p['role']}**",'',p['headline'],'',p['summary'],'',
             '### チームに配置する場合に向く役回り','',f"- 役回り: {p['pos']['role']}",f"- 向いている理由: {p['pos']['fit']}",f"- 参加の条件: {p['pos']['timing']}",f"- 担当範囲: {p['pos']['scope']}",'',p['conclusion'],'',
             f"### 研修{D['days']}日間の経過所見",'']+[f"- **{r['period']}** {r['obs']}" for r in p['timeline']]
        md+=['','### 研修で見られた強み','']+[f"- **{s['title']}** {s['body']}" for s in p['strengths']]+['','### 研修で見られた課題','']+[f"- **{s['title']}** {s['body']}" for s in p['issues']]
        md+=['','### スコアプロファイル','',f"| 評価項目 | 配点 | 基準点 | 内訳点 | 基準差 | 講師所見と{D['issuer']}の判断 |",'|---|---:|---:|---:|---:|---|']
        for i,d in enumerate(D['dimensions']):
            dl=p['scores'][i]-d['baseline']
            md.append(f"| {d['name']} | {d['maximum']} | {d['baseline']:.1f} | {p['scores'][i]:.1f} | {('＋' if dl>0 else '－' if dl<0 else '')+format(abs(dl),'.1f')} | {p['reasons'][i]} |")
        md+=['',' ＋ '.join(f"{d['short']}{p['scores'][i]:.1f}" for i,d in enumerate(D['dimensions']))+f" ＝ 総合{p['score']:.1f}点",'',
             '### 観点別の所見・解釈・配置への含意','']
        for d,ax in zip(D['dimensions'],p['axis_detail']):
            md+=[f"#### {d['name']}",'',f"- 研修で見られた行動: {ax['observed']}",f"- {D['issuer']}の解釈: {ax['interpretation']}",f"- 配置への含意: {ax['implication']}",'']
        md+=[p['rationale'],'','### 人材像','',f"- 仕事の進め方: {p['traits']['work']}",f"- AIとの向き合い方: {p['traits']['ai']}",f"- 周囲との関わり: {p['traits']['people']}",'',
             '### 任せる範囲と必要な支援','','任せてよいこと:']+[f'- {x}' for x in p['placement']['allow']]+['','まだ任せないこと:']+[f'- {x}' for x in p['placement']['not_yet']]+['','必要な支援・伴走:']+[f'- {x}' for x in p['placement']['support']]
        md+=['','### リーダー適性の見立て','',f"**{p['leadership']['verdict']}** {p['leadership']['body']}",'','### 配置上のリスクと対策','','| リスク | 対策 |','|---|---|']+[f"| {r['risk']} | {r['measure']} |" for r in p['risks']]
        md+=['','### 実務でのAI活用イメージ','']+[f'- {x}' for x in p['work_image']]+['',D['work_image_note']]
        md+=['','### 上司・推進責任者向けの関わり方','']+[f'- {x}' for x in p['manager_guidance']]+['','### 次に確認する観点','']+[f'- [ ] {x}' for x in p['checklist']]
        md+=['','### 成長が確認できた場合の次の役回り','',p['next_position'],'','将来への期待：'+p['future'],'',p['deduction_summary']]
    g=D['group_plan']
    md+=['','---','','## 全体分析','',D['overall_summary'],'',f"## {g['title']}",'',g['lead'],'','### 配置判断のポイント','']+[f"- **{d['title']}** {d['body']}" for d in g['decision_points']]
    if D.get('aptitude_map'):
        am=D['aptitude_map']
        md+=['',f"### {D['_N']}名の適性マップ",'',D['map_note'],'']+[f"- {p['name']}さん（{p['score']:.1f}点）: {'作る側' if p['x']<5 else '使う側'}の目線 × {'自走' if p['y']>=5 else '伴走前提'} — {p['label']}" for p in am['points']]
    md+=['',D['stats_note'],'',D['scope_note']]
    (OUT/f"{D['issuer']}_{D['edition']}_編集用原稿.md").write_text('\n'.join(md),encoding='utf-8')

if __name__=='__main__':
    main()
