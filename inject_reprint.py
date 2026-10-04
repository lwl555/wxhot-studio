import json

path = "data/articles.json"
d = json.load(open(path, encoding="utf-8"))
arts = d["articles"] if isinstance(d, dict) else d

# 已验证可打开的真实原文/转载链接（搜索引擎交叉验证，2026-10-04）
reprints = {
    "苹果最终确认": "https://www.toutiao.com/article/7687854344951300659/",
    "恭喜当年办了ETC": "https://m.toutiao.com/article/7616578213309628979",
    "名古屋亚运会": "https://www.toutiao.com/article/7687622068887667243",
    "41岁薇娅": "https://m.sohu.com/a/1080030213_122553943",
    "83年": "https://m.toutiao.com/article/7688716389598691887",
}

hit = 0
for a in arts:
    t = a.get("title", "")
    for k, url in reprints.items():
        if k in t:
            a["reprint"] = url
            hit += 1
            break

if isinstance(d, dict):
    d["articles"] = arts
json.dump(d, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"已注入 {hit} 篇转载链接，总计 {len(arts)} 篇")
