# case.json スキーマ（schema）

生成器 build_report.py の入力。templates/case-template.json が空欄雛形、sample/case-sample.json が記入例。

## トップレベル

| キー | 必須 | 内容 |
|---|---|---|
| client | ○ | 会社名（「様」は生成器が付ける） |
| days | ○ | 研修日数（既定5） |
| issuer |  | 発行者（既定 DATAREIN） |
| edition |  | 資料名の一部（既定「分析レポート」） |
| overall_summary | ○ | 全体版冒頭の要約。2〜3文 |
| people | ○ | 受講者配列（2〜10名） |
| group_plan | ○ | title / lead（3〜4文） / decision_points[]（title+body） |
| aptitude_map |  | 無ければマップ関連ページ・節を自動省略 |
| fonts |  | {regular, bold} NotoSansJPのパス指定 |
| banned_extra |  | 案件固有の禁止語を追加 |
| dimensions / levels / focus / method / scope_note 等 |  | 既定文の上書き（通常は触らない） |

## people[] の1人分（すべて必須。字数はA4版面に収まる目安）

| キー | 目安 | 内容 |
|---|---|---|
| name | — | 氏名（「さん」は生成器が付ける） |
| score / scores[3] | — | 総合点と内訳。合計一致・0.5刻み・各軸の配点内 |
| headline | 20〜30字 | 氏名下のサブタイトル。「◯◯と◯◯を評価」型。低評価者は「〜支援へ」型も可 |
| summary | 90〜120字 | 1ページ目ヒーローの要約。点数と育成方向まで |
| role | 12〜20字 | 点数の下の一言（例: 試行主導の候補として検討） |
| pos.role / fit / timing / scope | 20〜45字×4 | 向いている役回り・理由・参加の条件・担当範囲 |
| conclusion | 90〜130字 | 役回り枠の結論。断定調 |
| strengths[3] / issues[3] | title 8〜16字, body 40〜70字 | 行動根拠つきで3件ずつ |
| timeline[3〜4] | period 4〜10字, obs 40〜80字 | Day別・場面別の経過所見。事前情報は「事前情報」と明記 |
| reasons[3] | 60〜90字 | 内訳表の判断文。「講師所見：…。ISSUER判断：…x.x点、±y.y点。」型 |
| axis_detail[3] | 各40〜90字×3行 | observed / interpretation / implication。observedは講師の言葉由来 |
| rationale | 70〜110字 | 1ページ目末尾「評価の位置づけ」 |
| traits.work / ai / people | 40〜70字×3 | 人材像3行 |
| leadership.verdict / body | 15〜30字 / 90〜140字 | リーダー適性の言い切りと根拠 |
| risks[2〜3] | risk 25〜45字, measure 30〜55字 | 配置上のリスクと対策 |
| placement.allow / not_yet / support | 各2〜3項目 | 任せてよい・まだ任せない・必要な支援 |
| work_image[3〜4] | 35〜65字 | 実務でのAI活用イメージ（見立て） |
| manager_guidance[2〜4] | 25〜45字 | 上司向けの関わり方 |
| checklist[3〜5] | 20〜40字 | 次に確認する観点（〜たか。で終える） |
| next_position | 45〜70字 | 成長時の次の役回り |
| future | 35〜60字 | 将来への期待（実績と分ける） |
| deduction_summary | 60〜90字 | 末尾注記の内訳合計と根拠一言 |

## aptitude_map

x_left/x_right/y_top/y_bottom（軸ラベル）、quadrants[4]（左上・右上・左下・右下の順）、points[]＝{name, score, x, y, label}。x,yは0〜10の定性配置。labelは役回りの一言（6〜10字）。

## 整合の決まり

- scores の各値は dimensions のアンカー区分と矛盾しない説明を reasons に書く（生成器が尺度上の位置を自動表示する）。
- pos.timing と group_plan・individual本文の参加条件を一致させる。
- aptitude_map の位置と leadership / pos の記述を矛盾させない。
