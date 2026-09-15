# datarein-report-kit

DATAREIN研修後の受講者分析レポート（個人5ページ×N名＋全体4ページのPDF）を、講師への一人ずつのQ&Aヒアリングから作成するスキル。受講者リストを受け取り「◯◯さんはどうでしたか」と順に聞き、観察所見を引き出して採点案を提案し、講師の承認後にデザイン・図表・納品フォルダまで一括生成する。

- 入口・工程: [SKILL.md](SKILL.md)
- ヒアリング台本: [references/question-bank.md](references/question-bank.md)
- 文体規範・禁止語: [references/writing-style.md](references/writing-style.md)
- デザイン仕様: [references/design-spec.md](references/design-spec.md)
- 入力スキーマ: [references/schema.md](references/schema.md)
- 記入例と生成例: [sample/](sample/)（架空受講者2名。実在の受講者データは含まない）

## 必要環境

- Python 3.12+ と [uv](https://docs.astral.sh/uv/)（reportlab / pypdf / pymupdf を都度解決）
- Noto Sans JP（Regular / Bold）を `~/Library/Fonts` へ

## 最短の動作確認

```
uv run --with reportlab --with pypdf python3 scripts/build_report.py sample/case-sample.json --out /tmp/drk-out
uv run --with pypdf --with pymupdf python3 scripts/validate.py sample/case-sample.json --out /tmp/drk-out
```

個人5ページ×2名＋全体4ページ＝14枚が生成され、validate が machine_ok を返せば正常。

## 運用の正本

このリポジトリは配布用。運用の正本は作成者環境の `~/.agents/skills/datarein-report-kit/`（dotagents リポジトリ）にあり、変更は正本側から同期する。

出自: 2026-09-14 ナインアース研修分析レポート案件の一般化。
