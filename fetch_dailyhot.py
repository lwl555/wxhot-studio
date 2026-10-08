# 从开源热榜 API（DailyHotApi，GitHub ★4k+）补充板块
# 目的：补 tophub 没有的平台（简书 / IT之家 / 爱范儿 / 酷安 / V2EX / NGA / 吾爱破解 / 网易新闻 / 新浪新闻 / HelloGitHub / 豆瓣小组 / CSDN）
# 说明：公开实例偶尔不稳定，失败不影响主数据（Actions 里 continue-on-error）
import urllib.request, ssl, gzip, json, hashlib, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_hot import guess_category, fix_cover   # 复用分类规则与封面 https 化

API = "https://api-hot.imsyy.top/"
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0'
OUT = "data/articles.json"

# (路由, 平台名, 榜单名)
NODES = [
    ("jianshu", "简书", "简书热门推荐"),
    ("ithome", "IT之家", "IT之家热榜"),
    ("ifanr", "爱范儿", "爱范儿快讯"),
    ("coolapk", "酷安", "酷安热榜"),
    ("v2ex", "V2EX", "V2EX主题榜"),
    ("ngabbs", "NGA", "NGA热帖"),
    ("52pojie", "吾爱破解", "吾爱破解榜单"),
    ("netease-news", "网易新闻", "网易热点榜"),
    ("sina-news", "新浪新闻", "新浪热点榜"),
    ("hellogithub", "HelloGitHub", "开源项目 Trending"),
    ("douban-group", "豆瓣小组", "豆瓣讨论精选"),
    ("csdn", "CSDN", "CSDN排行榜"),
]


def pick(d, *keys):
    """宽容取字段：不同版本 API 字段名可能不同"""
    for k in keys:
        v = d.get(k)
        if v:
            return v
    return ""


def fetch_json(route):
    req = urllib.request.Request(API + route, headers={"User-Agent": UA, "Accept": "application/json"})
    r = urllib.request.urlopen(req, timeout=20, context=CTX)
    raw = r.read()
    if r.headers.get("Content-Encoding") == "gzip":
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8", "ignore"))


def main():
    try:
        d = json.load(open(OUT, encoding="utf-8"))
    except Exception as e:
        print("读取 articles.json 失败：", e)
        return

    arts = [x for x in d["articles"] if x.get("source") != "dailyhot"]   # 先清掉上一轮的
    added = 0

    for route, plat, board in NODES:
        try:
            j = fetch_json(route)
        except Exception as e:
            print(f"  × {plat:8} {route:14} FAIL {type(e).__name__}")
            continue
        rows = j.get("data") if isinstance(j, dict) else j
        if not isinstance(rows, list) or not rows:
            print(f"  · {plat:8} {route:14} 无数据")
            continue
        got = 0
        for idx, it in enumerate(rows):
            if not isinstance(it, dict):
                continue
            title = str(pick(it, "title", "name", "text")).strip()
            url = str(pick(it, "url", "link", "mobileUrl", "href", "target")).strip()
            if not title or not url:
                continue
            desc = str(pick(it, "desc", "description", "content", "summary")).strip()
            cover = str(pick(it, "cover", "pic", "picUrl", "image", "thumbnail")).strip()
            hot = str(pick(it, "hot", "hotValue", "heat", "view", "views")).strip()
            arts.append({
                "id": hashlib.md5(url.encode("utf-8")).hexdigest()[:12],
                "title": title[:200],
                "url": url.split("#")[0],
                "platform": plat,
                "board": board,
                "category": guess_category(title + " " + desc, board),
                "readCount": 0,
                "readCountText": hot or "—",
                "hasRealRead": False,
                "source": "dailyhot",
                "rank": idx + 1,
                "cover": fix_cover(cover),
                "desc": desc[:300],
            })
            got += 1
        added += got
        print(f"  ✓ {plat:8} {route:14} {got} 条")
        time.sleep(0.3)

    arts.sort(key=lambda x: (not x.get("hasRealRead"), -(x.get("readCount") or 0)))
    d["articles"] = arts
    d["total"] = len(arts)
    d["withRealRead"] = sum(1 for x in arts if x.get("hasRealRead"))
    json.dump(d, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n完成：开源 API 新增 {added} 条，库内总计 {len(arts)} 条")


if __name__ == "__main__":
    main()
