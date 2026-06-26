#!/usr/bin/env python3
"""seo-aio-skill — research.json × Google Search Console（クエリCSV）を突き合わせ（依存ゼロ）。

取得側（seo-aio MCP）の検索ボリューム/SERP と、あなたの実データ（GSC の表示/クリック/CTR/順位）を
キーワードで結合し、改善余地を機械的に出す。考察はエージェントが書く。

GSC データの用意（どちらでも）:
  A) Search Console → 検索パフォーマンス → 「クエリ」をエクスポート（CSV）
  B) あなたのエージェントに接続した GSC 用 MCP の出力を CSV / JSON で保存
CSV 見出しは日英どちらも可（Top queries/上位のクエリ, Clicks/クリック数, Impressions/表示回数,
CTR, Position/掲載順位）。

使い方:
  python3 scripts/merge_gsc.py research.json gsc-queries.csv -o gsc_merge.md
  python3 scripts/merge_gsc.py research.json gsc-queries.csv --top 10   # 「順位◯位以内」の閾値
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys


def _norm(s: str) -> str:
    return (s or "").lower().replace(" ", "").replace("　", "")


def _num(x):
    try:
        return float(str(x).replace("%", "").replace(",", "").strip())
    except (TypeError, ValueError):
        return None


# GSC CSV 見出しの日英ゆれ → 正準キー
_HEAD = {
    "query": ("top queries", "queries", "query", "上位のクエリ", "検索キーワード", "クエリ"),
    "clicks": ("clicks", "クリック数"),
    "impr": ("impressions", "表示回数"),
    "ctr": ("ctr",),
    "pos": ("position", "掲載順位", "平均掲載順位"),
}


def _colmap(header: list) -> dict:
    low = [_norm(h) for h in header]
    m = {}
    for key, names in _HEAD.items():
        for i, h in enumerate(low):
            if any(_norm(n) == h for n in names):
                m[key] = i
                break
    return m


def load_gsc(path: str) -> list:
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    if not rows:
        return []
    cm = _colmap(rows[0])
    if "query" not in cm:
        # 先頭行がヘッダでない可能性 → 1列目をクエリとみなす最小フォールバック
        cm = {"query": 0, "clicks": 1, "impr": 2, "ctr": 3, "pos": 4}
        data = rows
    else:
        data = rows[1:]
    out = []
    for r in data:
        if not r or len(r) <= cm["query"]:
            continue
        q = r[cm["query"]].strip()
        if not q:
            continue
        def g(k):
            i = cm.get(k)
            return _num(r[i]) if i is not None and i < len(r) else None
        out.append({"query": q, "clicks": g("clicks"), "impr": g("impr"),
                    "ctr": g("ctr"), "pos": g("pos")})
    return out


def research_volumes(research: dict) -> dict:
    kw = research.get("keywords")
    kw = kw if isinstance(kw, dict) else {}
    rows = []
    for n in ("keywords", "rows", "items"):
        if isinstance(kw.get(n), list):
            rows = kw[n]
            break
    vol = {}
    for r in rows:
        if isinstance(r, dict):
            name = r.get("keyword") or r.get("kw")
            if name:
                vol[_norm(name)] = _num(r.get("search_volume") or r.get("volume")) or 0
    return vol


def _md_table(headers, rows):
    if not rows:
        return "_(該当なし)_"
    return "\n".join(["| " + " | ".join(headers) + " |",
                      "| " + " | ".join("---" for _ in headers) + " |",
                      *["| " + " | ".join(str(c) for c in r) + " |" for r in rows]])


def build(research: dict, gsc: list, top: int) -> str:
    vol = research_volumes(research)
    # 結合
    for g in gsc:
        g["volume"] = vol.get(_norm(g["query"]))
    ranked = [g for g in gsc if g["pos"] is not None and g["pos"] <= top and g["ctr"] is not None]
    median_ctr = statistics.median([g["ctr"] for g in ranked]) if ranked else None

    md = ["# GSC 突き合わせ — research.json × Search Console", ""]
    if median_ctr is not None:
        md += [f"- 上位{top}位以内クエリ {len(ranked)} 件の CTR 中央値: **{median_ctr:.1f}%**",
               "- ※ 数表は決定的。改善仮説・優先順位は**あなたのエージェントが追記**。", ""]

    # 1) 順位は良いのに CTR が低い（title/description 改善候補）
    cands = sorted([g for g in ranked if median_ctr is not None and g["ctr"] < median_ctr],
                   key=lambda g: -(g["impr"] or 0))
    md += [f"## 1. 順位は{top}位以内なのに CTR が中央値未満（title/description 改善候補）", "",
           _md_table(["クエリ", "掲載順位", "表示", "クリック", "CTR", "月間検索"],
                     [[g["query"], f'{g["pos"]:.1f}', int(g["impr"] or 0), int(g["clicks"] or 0),
                       f'{g["ctr"]:.1f}%', (int(g["volume"]) if g["volume"] else "-")] for g in cands[:20]]),
           ""]

    # 2) research に在るが GSC に出ていない高ボリューム語（露出ゼロ＝獲得余地）
    seen = {_norm(g["query"]) for g in gsc}
    missing = sorted([(k, v) for k, v in vol.items() if k not in seen and v > 0], key=lambda x: -x[1])
    md += ["## 2. 検索需要はあるのに GSC に未出現（＝まだ取れていない語）", "",
           _md_table(["キーワード(正規化)", "月間検索"], [[k, int(v)] for k, v in missing[:20]]),
           "",
           "> 依頼例: 「§1 は title/meta のリライト案、§2 は新規/強化すべきページ案を、"
           "検索意図ごとに優先度つきで出して」", ""]
    return "\n".join(md)


def main() -> int:
    ap = argparse.ArgumentParser(description="research.json × GSC クエリCSV の突き合わせ")
    ap.add_argument("research")
    ap.add_argument("gsc_csv")
    ap.add_argument("--top", type=int, default=10, help="「順位◯位以内」の閾値（既定10）")
    ap.add_argument("-o", "--out")
    args = ap.parse_args()
    try:
        research = json.load(open(args.research, encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: research.json を読めません: {e}", file=sys.stderr); return 1
    try:
        gsc = load_gsc(args.gsc_csv)
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: GSC CSV を読めません: {e}", file=sys.stderr); return 1
    if not gsc:
        print("ERROR: GSC CSV に行がありません", file=sys.stderr); return 1
    md = build(research, gsc, args.top)
    if args.out:
        open(args.out, "w", encoding="utf-8").write(md); print(f"wrote {args.out}")
    else:
        print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
