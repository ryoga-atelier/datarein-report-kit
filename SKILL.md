---
name: datarein-report-kit
description: DATAREIN研修後の受講者分析レポート（個人5ページ×N名＋全体4ページのPDF）を、講師への一人ずつのQ&Aヒアリングから作成する。受講者リストを受け取り「◯◯さんはどうでしたか」と順に聞き、観察所見を引き出して採点案を提案し、承認後にデザイン・図表・納品フォルダまで一括生成する。研修講師が「受講者の分析レポートを作りたい」「研修の評価レポート」「受講者フィードバックをPDFに」と言った時に使う。スライド制作は datarein-slide-kit、研修設計は fishbone-training を使い、本スキルは使わない。
---

# DATAREIN 研修分析レポート作成キット

研修講師へのヒアリングだけを情報源に、経営者が配置判断に使える受講者分析レポートを作る。詳細に語れない講師からも、質問台本で行動所見を引き出すことが本スキルの中心である。出自は2026-09-14ナインアース案件（個人5P×4名＋全体4P、業界水準の章立て・検証つき）。

## 成果物

- 個人分析レポート（1人5ページ）×N名、全体分析と適性整理（4ページ）、結合PDF（全体版が先頭）
- 個別PDFのZIP、編集用Markdown、納品用フォルダ（人名別＋全体、SHA照合済み）
- 章立て・図表・色・階層は references/design-spec.md（正本は scripts/build_report.py）

## 前提

- 実行環境に `uv` と NotoSansJP フォント（~/Library/Fonts）。無ければ build_report.py が導入手順を表示する。
- 案件の作業フォルダ（例: `~/workspace/documents/YYYY-MM-DD-<案件>/`）で作業し、成果物はそこへ保存する。スキルフォルダへ案件データを置かない。

## 工程

### フェーズA 前提確認
references/question-bank.md のA1〜A5を聞く。受講者リストを受け取ったら:
```
python3 <SKILL_DIR>/scripts/new_case.py <案件dir> --client <会社名> --days <日数> --names <氏名,氏名,...>
```
case.json（空欄雛形）と hearing_state.json（進行管理）ができる。

### フェーズB 一人ずつヒアリング（中核）
question-bank.md のB1〜B9を、リスト順に1問ずつ。語りが薄ければプローブで掘る。規範:
- 講師の発言＝観察。解釈はこちらが下書きし、講師に確認してから書く。
- 所見に無い事実（日付・発言・成果物名）を補作しない。
- 否定的な人物評は writing-style.md の変換表で行動記述に直す。
- 回答が来るたびに hearing_state.json へ保存。中断時は current の人から再開する。

### フェーズC 採点（提案→承認）
尺度アンカーを提示し、各軸の候補点＋行動根拠を提案→講師が承認・修正。内訳合計＝総合点をその場で確認。承認済み点数と根拠を case.json の scores / reasons へ。

### フェーズD 下書き承認
1人分の要約カード（総合点・役回り・強み3・課題3・実務イメージ）を提示→承認→次の人。全員後に全体編（役割の骨格・配置判断・適性マップ座標）を提案→承認。本文は writing-style.md に従い、schema.md の字数目安で書いて case.json を完成させる。

### フェーズE 生成
```
uv run --with reportlab --with pypdf python3 <SKILL_DIR>/scripts/build_report.py <案件dir>/case.json
```
出力は `<案件dir>/output/`。点数整合・禁止語・ページ数は生成時にアサートされる。

### フェーズF 検証と報告
```
uv run --with pypdf --with pymupdf python3 <SKILL_DIR>/scripts/validate.py <案件dir>/case.json
```
machine_ok（機械検査）と、`output/_png/` の全ページ目視（欠け・重なり・違和感）を**分けて**確認・報告する。出力の存在＝完成ではない。修正は case.json を直して再生成し、手でPDFを直さない。納品は `output/納品用/` を渡す。

## 品質の決まり

- 点数は講師の承認なしに確定しない。順位づけ・誇張・補作をしない（writing-style.md）。
- 低評価者にも育成の土台を必ず書く。人格評価にしない。
- 完了報告は「保存した／機械検査を通した／目視した／納品した」を区別して述べる。

## 参照

- references/question-bank.md — ヒアリング台本とプローブ
- references/writing-style.md — 文体規範・禁止語・言い換え表
- references/design-spec.md — 色・階層・図表・ページ構成
- references/schema.md — case.json の全フィールドと字数目安
- sample/case-sample.json — 架空2名の記入例（sample/output に生成例）
- 関連: datarein-slide-kit（スライド制作）、fishbone-training（研修設計）。文体の一般規範は ng-palette / japanese-tech-writing / bookmark-avoid-ai-writing。
