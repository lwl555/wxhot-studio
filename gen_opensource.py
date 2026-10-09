#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地补充脚本：当沙箱无法访问 tophub（tophub 经常超时），但能访问
api.github.com / hellogithub.com 时，用本脚本：
  1) 读入已有的 data/articles.json（含 tophub 全量数据）
  2) 清掉旧的 GitHub / HelloGitHub 条目
  3) 实时抓取 GitHub 官方 API（3 个时间窗）+ HelloGitHub 月刊
  4) 合并写回，附 fetchLog 诊断
CI 跑完整 fetch_hot.py 时本脚本不参与；本脚本仅用于本地补数。
"""
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_hot as fh

OUT = fh.OUT_FILE
FRESH = {"github", "hellogithub"}

# 1) 读入已有数据
old = json.load(open(OUT, encoding="utf-8"))
old_articles = old.get("articles", [])
kept = [a for a in old_articles if a.get("source") not in FRESH]
print(f"保留既有条目（tophub 等）：{len(kept)}")

# 2) 抓取开源源
new_items = []
new_items += fh.fetch_github_trending(1, "GitHub 本日新热")
new_items += fh.fetch_github_trending(7, "GitHub 本周新热")
new_items += fh.fetch_github_trending(30, "GitHub 本月新热")
new_items += fh.fetch_hellogithub()

# 3) 合并去重（按 url）
seen = set(a["url"] for a in kept)
merged = list(kept)
dup = 0
for it in new_items:
    if it["url"] in seen:
        dup += 1
        continue
    seen.add(it["url"])
    merged.append(it)
print(f"新增开源条目：{len(new_items) - dup}（跨窗口去重 {dup}）")

# 4) 为开源条目按榜单分配 rank（便于前端排序展示）
rank_counter = defaultdict(int)
for it in merged:
    if it.get("source") in FRESH:
        rank_counter[it["board"]] += 1
        it["rank"] = rank_counter[it["board"]]

# 5) 写回
payload = {
    "updatedAt": fh.now_bj(),
    "source": "tophub.today + GitHub API + HelloGitHub",
    "total": len(merged),
    "withRealRead": sum(1 for i in merged if i["hasRealRead"]),
    "fetchLog": fh.FETCH_LOG,
    "articles": merged,
}
os.makedirs(fh.OUT_DIR, exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)

print("\n=== fetchLog ===")
for e in fh.FETCH_LOG:
    print(f"  {e['source']:24} fetched={e['fetched']} items={e['items']} {('('+e['note']+')') if e.get('note') else ''}")
print(f"\n完成：共 {len(merged)} 条，写入 {OUT}")
