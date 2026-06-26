# seo-aio-skill

**検索 × 生成AI（AIO/LLMO）データの「分析」を、あなたの AI エージェントで回すための最小スキル。**

SEO 順位・CPC・検索ボリューム・AI Overview 引用・ChatGPT/Gemini/Claude での言及シェア（SoV）といった
データの **取得は MCP**、**分析はこのスキル＋あなたのエージェント**、という二層構成のうちの「分析側」サンプルです。

```
┌─────────────────────────┐        ┌──────────────────────────────┐
│ ① 取得（seo-aio MCP）   │  MCP   │ ② 分析（このスキル + あなたの │
│  run_research /         │ ─────▶ │    Claude Code / Codex 等）   │
│  check_status /         │        │  analyze.py → 数表            │
│  get_history            │        │  watch.py   → 定期差分通知    │
└─────────────────────────┘        │  考察はエージェントが執筆     │
                                    └──────────────────────────────┘
```

- 取得モジュール（本サービス）: https://mcp.aibrainpartners.jp/setup
- 使い方の実例集: https://mcp.aibrainpartners.jp/use-cases

## これは何

- `analyze.py` … MCP が返す `research.json` を読み、**決定的に作れる数表**（フットプリント比較・キーワード機会・SoV）を Markdown で出力。**依存ゼロ**（標準ライブラリのみ）。
- `watch.py` … 定期モニタリングの**差分判定の "処理"**。`get_history` の時系列から SoV 下落を検知し、下落時のみ通知トリガ（exit 1）を返す。
- 考察・優先順位・施策の文章は、**あなたのエージェントに書かせる**（プロンプト例つき）。

数表は機械的に、考察は AI に。これが「分析をエージェントに委ねる」の最小形です。

## クイックスタート

### 1. MCP に接続（取得側）
```bash
claude mcp add -t http seo-aio https://mcp.aibrainpartners.jp/mcp
# 「seo-aio の signup を呼んで」→ カード登録(¥0)で 260cr → 返ってきた ?key= 付き1行で登録し直す
```

### 2. データ取得 → 分析の骨格
エージェントに依頼してデータを取り、`./research.json` に保存したら:
```bash
python3 scripts/analyze.py research.json -o analysis.md
```

### 3. 考察を書かせる
`analysis.md` をエージェントに渡し、「§4 を表の数字を根拠に埋めて」と頼むだけ。
出力例 → [`examples/analysis.sample.md`](examples/analysis.sample.md)

## 定期モニタリング（スケジュール処理）

継続観測は `check_status`（同日再実行は無料）＋ `get_history`（推移）で行い、
**頻度の管理はあなたのエージェントのスケジュール機能**に任せます（サーバ側設定は不要）。

Claude Code の **Schedule** に登録する依頼文（毎朝の例）:
```
seo-aio の check_status を run_id=<RID> で実行し、get_history(run_id) を ./history.json に保存。
python3 scripts/watch.py history.json を実行し、SoV が下落していたら原因仮説を添えて Slack に要約を投げて。
変化が無ければ通知不要。
```

`watch.py` の挙動:
```bash
python3 scripts/watch.py history.json            # 下落時のみ exit 1 + ALERT 行
python3 scripts/watch.py history.json --drop 1.0 # 下落しきい値(ポイント)を変更
```

## research.json について

`research.json` は seo-aio エンジン出力をフィールド名そのままで透過格納した単一ファイル。
主なセクション: `meta` / `competitors` / `keywords` / `serp` / `footprint` / `site_matrix` / `llm_probe`（SoV）/ `costs`。
`analyze.py` は欠損に強く、無いセクションは黙ってスキップします。

## ライセンス

MIT。自由に fork・改変して、あなたの分析ロジックの出発点にどうぞ。

---
取得モジュール（seo-aio MCP）の提供: **AI BRAIN PARTNERS** — https://mcp.aibrainpartners.jp
