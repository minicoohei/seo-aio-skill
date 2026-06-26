---
name: seo-aio-skill
description: seo-aio MCP（mcp.aibrainpartners.jp）で取得した SEO/AIO/LLMO データ（research.json）を、決定的な数表に整え、考察・施策をエージェントが書くための最小スキル。取得=MCP、分析=本スキル の二層構成。定期モニタリング（毎朝の差分通知）レシピ付き。
---

# seo-aio-skill — 検索/AI露出データの分析（最小・OSS）

**二層構成**: データ取得は **seo-aio MCP**（`run_research` / `get_run_data` / `check_status`）、
**分析・レポート化は本スキル＋あなたの AI エージェント**。
本スキルは「決定的に作れる数表」をスクリプトで生成し、考察・優先順位・施策は**エージェントが書く**。

## 0. MCP に接続（1回だけ）
```bash
# キー無しで接続して signup を呼ぶ → 返ってきた ?key= 付き1行で登録し直す
claude mcp add -t http seo-aio https://mcp.aibrainpartners.jp/mcp
# 「seo-aio の signup を呼んで」→ カード登録(¥0)で 260cr 付与 → 接続コマンドを貼り直す
```

## 1. データを取得（MCP）
エージェントにこう頼む:
```
seo-aio で example.com を診断したい。create_spec → update_spec で競合を採用 → run_research(with_llmo=true)
を実行して、research.json をダウンロードして ./research.json に保存して。
```
> `research.json` には keywords / serp / footprint / site_matrix / llm_probe（SoV）などが
> エンジン出力のまま透過格納されている。

## 2. 分析の骨格を生成（本スキル・決定的）
```bash
python3 scripts/analyze.py research.json -o analysis.md
```
出力 `analysis.md`:
- **1. 自然検索フットプリント**（自社 vs 競合：ランク語数・推定流入 eTV）
- **2. キーワード機会**（検索ボリューム降順・競合・CPC）
- **3. 生成AI SoV**（ChatGPT/Gemini/Claude 実査の言及率）
- **4. 考察（← エージェントが書く）** プレースホルダ

## 3. 考察を書かせる（エージェント）
`analysis.md` を渡してこう頼む:
```
この analysis.md の数表を根拠に、§4 を埋めて。
「現状を一言で」「3つの重要発見（事実→構造的欠陥→改善余地）」「90日の最優先アクション」。
数字は表から引用し、勝手な推測値は入れないこと。
```

## 4. 定期モニタリングを自動化（スケジュール処理）
継続観測は **`check_status`（同日再実行は無料）** と **`get_history`（推移）** で行う。
頻度の管理は**あなたのエージェントのスケジュール機能**に委ねる（サーバ側設定は不要）。

**Claude Code の Schedule に登録する依頼文（例・毎朝9時）:**
```
seo-aio の check_status を run_id=<RID> で実行し、get_history(run_id) を取得して
./history.json に保存。その後 `python3 scripts/watch.py history.json` を実行し、
SoV が前回より下落していたら原因仮説を添えて Slack に要約を投げて。変化が無ければ通知不要。
```

**差分判定の処理（`scripts/watch.py`）** — get_history の時系列から最新の変化を判定:
```bash
python3 scripts/watch.py history.json        # 下落時のみ exit code 1 + アラート文を出力
```
- 直近2点の `sov_pct` を比較し、低下していれば `ALERT` 行を出力して exit 1（＝通知トリガ）。
- 横ばい/改善なら `OK` を出力して exit 0（＝通知不要）。
- しきい値は `--drop`（既定 0.5 ポイント）で調整可能。

## 5. GSC（Search Console）/ Google Ads と紐づける
取得側（seo-aio MCP）の **検索ボリューム・SERP順位** に、あなたの実データ
（GSC の表示/クリック/CTR/順位、Google Ads の費用/CV）を**キーワードで結合**して使う。

### 5-1. GSC と突き合わせ（決定的）
GSC データを用意（どちらでも）:
- **A. CSV**: Search Console → 検索パフォーマンス → 「クエリ」をエクスポート
- **B. MCP**: あなたのエージェントに接続した GSC 用 MCP の出力を CSV/JSON で保存

結合:
```bash
python3 scripts/merge_gsc.py research.json gsc-queries.csv -o gsc_merge.md
```
出力 `gsc_merge.md`:
- **§1 順位は◯位以内なのに CTR が中央値未満** → title/description 改善候補
- **§2 検索需要はあるのに GSC 未出現** → 新規/強化すべきページ候補

> エージェントへの依頼例: 「gsc_merge.md の §1 は title/meta のリライト案、§2 は新規ページ案を、
> 検索意図ごとに優先度つきで出して」

### 5-2. Google Ads と紐づけ
- **出稿候補の選定**: `analyze.py` の §2（検索ボリューム×CPC×自社未ランク）がそのまま
  Keyword Planner 的なショートリスト。「CPC が安く検索数があり競合が上位＝広告と自然検索の両取り」を狙う。
- **実績との突き合わせ**: Ads の実績（キーワード別 クリック/費用/CV）を CSV にして同じ join で
  「費用はかかっているが research 上は競合も弱い＝自然検索に寄せられる語」「CV しているのに
  自然検索で未ランク＝SEO 強化の優先語」を抽出（`merge_gsc.py` を雛形に列を差し替え、
  もしくはエージェントに `research.json` と Ads CSV を渡して突き合わせを依頼）。

> いずれも **GSC / Ads 側の接続はあなたの環境の MCP / エクスポート**。本サービスは検索データ側を担当し、
> 突き合わせ（紐づけ）は本スキル＋エージェントで行う、という二層構成のまま。

## 注意
- 本スキルは**取得側（DataForSEO/LLM 実査）には触れない**。原価のかかる取得は MCP 側で課金される。
- `research.json` のフィールド名はエンジン出力をそのまま使う。スクリプトは欠損に強く、無いセクションはスキップする。
- 分析ロジックは自由に fork・改変可（MIT）。これは「分析側」の出発点サンプル。
