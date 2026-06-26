#!/usr/bin/env python3
"""seo-aio-skill — research.json を読んで「分析の骨格」を Markdown で出力する（依存ゼロ）。

役割分担:
  取得 = seo-aio MCP（run_research → research.json）
  分析 = 本スキル（このスクリプトが決定的な数表を作り、考察はあなたの AI エージェントが書く）

使い方:
  python3 scripts/analyze.py research.json            # Markdown を標準出力へ
  python3 scripts/analyze.py research.json -o out.md   # ファイルへ

研究データのフィールド名は seo-aio エンジン出力をそのまま透過格納したもの。
本スクリプトは欠損に強く（.get で防御）、無いセクションは黙ってスキップする。
"""
from __future__ import annotations

import argparse
import json
import sys


def _section(research: dict, key: str) -> dict:
    """エンベロープ（as_of/source）込みのセクションを返す。中身はエンジン出力フィールドが直に入る。"""
    sec = research.get(key)
    return sec if isinstance(sec, dict) else {}


def _rows(sec: dict, *names) -> list:
    for n in names:
        v = sec.get(n)
        if isinstance(v, list):
            return v
    return []


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def kw_opportunities(research: dict, limit: int = 15) -> list:
    """検索ボリューム降順のキーワード（自社未ランク・低競合を機会として印）。"""
    kw = _section(research, "keywords")
    rows = _rows(kw, "keywords", "rows", "items")
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        name = r.get("keyword") or r.get("kw")
        if not name:
            continue
        vol = _num(r.get("search_volume") or r.get("volume") or (r.get("keyword_info") or {}).get("search_volume"))
        comp = r.get("competition")
        cpc = r.get("cpc") or (r.get("keyword_info") or {}).get("cpc")
        out.append({"keyword": name, "volume": vol, "competition": comp, "cpc": cpc})
    out.sort(key=lambda x: -x["volume"])
    return out[:limit]


def footprint_table(research: dict) -> list:
    fp = _section(research, "footprint")
    sites = _rows(fp, "sites", "domains")
    out = []
    for s in sites:
        if not isinstance(s, dict):
            continue
        out.append({
            "name": s.get("name") or s.get("host") or s.get("domain") or "?",
            "tag": s.get("tag") or "",
            "ranked": _num(s.get("total_count") or s.get("ranked") or s.get("ranked_count") or s.get("words")),
            "etv": _num(s.get("etv") or s.get("estimated_traffic") or s.get("traffic")),
        })
    out.sort(key=lambda x: -x["etv"])
    return out


def sov_table(research: dict) -> list:
    lp = _section(research, "llm_probe")
    rows = _rows(lp, "share_of_voice")
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        out.append({
            "company": r.get("company") or r.get("name") or "?",
            "mentions": _num(r.get("mentions")),
            "mention_rate": r.get("mention_rate"),
            "first": _num(r.get("first_mentions")),
        })
    out.sort(key=lambda x: -(_num(x["mention_rate"]) or x["mentions"]))
    return out


def _md_table(headers: list, rows: list) -> str:
    line = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    body = "\n".join("| " + " | ".join(str(c) for c in r) + " |" for r in rows)
    return "\n".join([line, sep, body]) if rows else "_(データなし)_"


def build_markdown(research: dict) -> str:
    meta = research.get("meta", {})
    target = (meta.get("target") or {}) if isinstance(meta.get("target"), dict) else {}
    target_name = target.get("name") or target.get("target_domain") or meta.get("run_id") or "対象サイト"
    as_of = (_section(research, "keywords").get("as_of") or meta.get("generated_at") or "")

    md = [f"# SEO / AIO / LLMO 分析の骨格 — {target_name}",
          "",
          f"- 対象: **{target_name}**　/ 取得時刻: {as_of}　/ データ源: 外部データ（検索 + 生成AI実査）",
          "- ※ この骨格は決定的に生成。**考察・優先順位・施策はあなたの AI エージェントが追記**してください。",
          ""]

    # 1. フットプリント
    fp = footprint_table(research)
    md += ["## 1. 自然検索フットプリント（競合比較）", "",
           _md_table(["サイト", "区分", "ランク語数", "推定流入(eTV)"],
                     [[r["name"], r["tag"], int(r["ranked"]), int(r["etv"])] for r in fp]),
           ""]

    # 2. キーワード機会
    kw = kw_opportunities(research)
    md += ["## 2. キーワード機会（検索ボリューム降順）", "",
           _md_table(["キーワード", "月間検索", "競合", "CPC"],
                     [[r["keyword"], int(r["volume"]), (r["competition"] if r["competition"] is not None else "-"),
                       (r["cpc"] if r["cpc"] is not None else "-")] for r in kw]),
           "",
           "> エージェントへの依頼例: 「検索数が大きく競合が低め、かつ自社が未ランクの語を"
           "『獲得すべき最優先KW』として、想定流入と一緒に並べて」", ""]

    # 3. 生成AI SoV
    sov = sov_table(research)
    md += ["## 3. 生成AIでの言及シェア（SoV：ChatGPT / Gemini / Claude 実査）", "",
           _md_table(["企業", "言及数", "言及率", "初出数"],
                     [[r["company"], int(r["mentions"]),
                       (f'{r["mention_rate"]}%' if r["mention_rate"] is not None else "-"), int(r["first"])]
                      for r in sov]),
           "",
           "> エージェントへの依頼例: 「自社が引用されていない質問と、そのとき引用されている"
           "情報源の傾向（メディア/比較サイト/公式）を整理して、対策すべき質問を挙げて」", ""]

    # 4. 考察テンプレ（エージェントが埋める）
    md += ["## 4. 考察（← ここをエージェントが書く）", "",
           "- **現状を一言で**: ",
           "- **3つの重要発見**: 1) … 2) … 3) …",
           "- **最優先アクション**: ",
           ""]
    return "\n".join(md)


def main() -> int:
    ap = argparse.ArgumentParser(description="research.json → 分析の骨格(Markdown)")
    ap.add_argument("research", help="run_research が返した research.json のパス")
    ap.add_argument("-o", "--out", help="出力先 .md（省略時は標準出力）")
    args = ap.parse_args()
    try:
        research = json.load(open(args.research, encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: research.json を読めません: {e}", file=sys.stderr)
        return 1
    md = build_markdown(research)
    if args.out:
        open(args.out, "w", encoding="utf-8").write(md)
        print(f"wrote {args.out}")
    else:
        print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
