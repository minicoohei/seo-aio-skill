#!/usr/bin/env python3
"""seo-aio-skill — 定期モニタリングの差分判定（依存ゼロ）。

get_history(run_id) の時系列（points: 日付昇順の SoV など）を読み、
直近2点を比較して「下落していれば通知トリガ」を返す。スケジュール実行の "処理" 本体。

使い方:
  python3 scripts/watch.py history.json            # 下落時のみ exit 1 + ALERT
  python3 scripts/watch.py history.json --drop 1.0 # 下落しきい値(ポイント)を変更

出力/終了コード:
  ALERT … 直近で sov_pct が drop 以上低下 → exit 1（通知すべき）
  OK    … 横ばい/改善、または比較不能 → exit 0（通知不要）
"""
from __future__ import annotations

import argparse
import json
import sys


def _points(data) -> list:
    """get_history の戻り（{points:[...]} か points 配列そのもの）を日付昇順の list に正規化。"""
    pts = data.get("points") if isinstance(data, dict) else data
    if not isinstance(pts, list):
        return []
    pts = [p for p in pts if isinstance(p, dict)]
    pts.sort(key=lambda p: str(p.get("date") or ""))
    return pts


def _sov(p: dict):
    for k in ("sov_pct", "sov", "share_of_voice_pct", "llm_sov"):
        v = p.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="get_history の時系列から下落を検知")
    ap.add_argument("history", help="get_history が返した JSON のパス")
    ap.add_argument("--drop", type=float, default=0.5, help="通知する下落しきい値（ポイント・既定0.5）")
    args = ap.parse_args()

    try:
        data = json.load(open(args.history, encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"OK  (history を読めません: {e})")
        return 0

    pts = _points(data)
    if len(pts) < 2:
        print("OK  (比較できる履歴が2点未満)")
        return 0

    prev, last = pts[-2], pts[-1]
    s_prev, s_last = _sov(prev), _sov(last)
    if s_prev is None or s_last is None:
        print("OK  (sov_pct が取れない点がある)")
        return 0

    delta = s_last - s_prev
    d_prev, d_last = prev.get("date", "?"), last.get("date", "?")
    if delta <= -abs(args.drop):
        print(f"ALERT  SoV が {s_prev:.1f}% → {s_last:.1f}%（{delta:+.1f}pt）に下落  [{d_prev} → {d_last}]")
        summary = last.get("summary")
        if summary:
            print(f"  直近サマリ: {summary}")
        return 1
    print(f"OK  SoV {s_prev:.1f}% → {s_last:.1f}%（{delta:+.1f}pt）  [{d_prev} → {d_last}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
