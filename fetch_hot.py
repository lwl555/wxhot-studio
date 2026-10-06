#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
热榜数据采集器
数据源：今日热榜 tophub.today（免费、免 key、每日更新、含真实阅读量）

已验证可用的节点：
  /n/WnBe01o371  微信24h热文榜   → 带真实阅读量（10.0万 / 8.7万）
  /c/wxmp       公众号频道       → 多个公众号维度榜单

输出：data/articles.json
"""

import json
import os
import re
import ssl
import html
import urllib.request
import datetime
import hashlib

# GitHub Actions 的 runner 是 UTC 时区，直接用 now() 会比北京慢 8 小时。
# 显式用 UTC+8，保证前端看到的时间和本地一致。
BJ = datetime.timezone(datetime.timedelta(hours=8))
def now_bj():
    return datetime.datetime.now(BJ).strftime("%Y-%m-%d %H:%M:%S")

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
OUT_FILE = os.path.join(OUT_DIR, "articles.json")

# 节点清单：(节点ID, 平台标签, 榜单名, 分类)
NODES = [
    ("WnBe01o371", "微信", "微信24h热文榜", "公众号爆文"),
    ("W1VdJPZoLQ", "微信", "微信今日视频榜", "视频爆款"),
    ("KMZd7VOvrO", "知乎", "知乎日报Today", "知乎"),
    ("mproPpoq6O", "知乎", "知乎热榜", "知乎"),
    ("KqndgxeLl9", "微博", "微博热搜榜", "微博"),
    ("x9ozB4KoXb", "今日头条", "今日头条头条热榜", "头条"),
    ("Jb0vmloB1G", "百度", "百度实时热点", "社会热点"),
    ("Om4ejxvxEN", "百度贴吧", "百度贴吧热议榜", "社区热议"),
    ("DpQvNABoNE", "抖音", "抖音总榜", "短视频"),
    ("74KvxwokxM", "哔哩哔哩", "哔哩哔哩全站日榜", "视频爆款"),
    ("Q1Vd5Ko85R", "36氪", "36氪24小时热榜", "科技"),
    ("5VaobgvAj1", "虎嗅网", "虎嗅网热文", "科技"),
    ("wWmoO5Rd4E", "澎湃", "澎湃热榜", "时政社会"),
    ("DOvnNz1vEB", "机器之心", "机器之心", "AI科技"),
    ("MZd7azPorO", "量子位", "量子位", "AI科技"),
    ("Y2KeDGQdNP", "少数派", "少数派热门文章", "数码效率"),
    ("4KvxEX0dkx", "微信读书", "微信读书总榜", "书单"),
    ("mDOvnyBoEB", "豆瓣", "豆瓣电影新片榜", "影视娱乐"),
]

# 关键词分类（按标题命中）
CATEGORY_RULES = [
    ("科技数码", ["苹果", "华为", "小米", "特斯拉", "芯片", "AI", "人工智能", "手机", "电脑",
                 "模型", "算法", "机器人", "程序员", "互联网", "卫星", "火箭", "SpaceX"]),
    ("财经理财", ["股", "黄金", "房价", "楼市", "银行", "存款", "利率", "基金", "经济", "GDP",
                 "央行", "汇率", "投资", "负债", "赚钱", "工资", "补贴"]),
    ("社会热点", ["通报", "警方", "事故", "遇难", "官方", "回应", "调查", "处罚", "判决", "起诉",
                 "教育局", "医院", "食品", "安全"]),
    ("娱乐影视", ["电影", "电视剧", "明星", "演唱会", "综艺", "票房", "官宣", "剧组", "演员",
                 "导演", "开播", "杀青", "收视"]),
    ("体育赛事", ["亚运", "奥运", "世界杯", "比赛", "夺冠", "金牌", "球队", "球员", "足球",
                 "篮球", "冠军", "决赛", "S赛", "IG", "RNG"]),
    ("健康养生", ["医生", "医院", "疾病", "养生", "血压", "血糖", "体检", "寿命", "睡眠",
                 "饮食", "中医", "医生提醒"]),
    ("情感心理", ["情感", "婚姻", "离婚", "恋爱", "爱情", "家庭", "婆媳", "中年", "焦虑",
                 "内耗", "emo", "孤独"]),
    ("职场成长", ["职场", "工作", "打工", "老板", "同事", "辞职", "offer", "面试", "简历",
                 "副业", "赚钱", "35岁", "35+"]),
    ("教育考试", ["高考", "中考", "学生", "老师", "教师", "大学", "高校", "考试", "录取",
                 "教育", "孩子", "家长", "开学"]),
    ("生活美食", ["美食", "菜谱", "早餐", "做饭", "餐厅", "好吃", "小吃", "火锅", "奶茶",
                 "零食", "厨房", "面", "饭"]),
]


def fetch(url, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            return urllib.request.urlopen(req, timeout=25, context=CTX).read().decode("utf-8", "ignore")
        except Exception as e:
            if i == retries - 1:
                print(f"  [FAIL] {url} -> {type(e).__name__}: {e}")
                return ""
    return ""


def parse_read_count(s):
    """'10.0万' -> 100000, '8534' -> 8534"""
    s = (s or "").strip()
    if not s:
        return 0
    if s.endswith("万"):
        try:
            return int(float(s[:-1]) * 10000)
        except ValueError:
            return 0
    m = re.search(r"(\d+)", s)
    return int(m.group(1)) if m else 0


def guess_category(title):
    for cat, kws in CATEGORY_RULES:
        for k in kws:
            if k in title:
                return cat
    return "综合"


def clean_url(u):
    return u.split("#")[0]


def parse_node(node_id, platform, board_name, category, rank_base=0):
    """解析单个 tophub 节点"""
    page = fetch(f"https://tophub.today/n/{node_id}")
    if not page:
        return []

    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S)
    items = []

    for idx, row in enumerate(rows):
        # 标题链接：兼容 <td><a> 与 <td class="al"><div><a> 两种结构
        a = re.search(
            r'<div><a href="(https?://[^\"]+)"[^>]*>(.*?)</a></div>',
            row, re.S
        ) or re.search(
            r'<td><a href="(https?://[^\"]+)"[^>]*>(.*?)</a>',
            row, re.S
        )
        if not a:
            continue

        url = html.unescape(a.group(1)).strip()
        title = html.unescape(re.sub("<[^>]+>", "", a.group(2))).strip()
        if not title or len(title) < 2:
            continue

        # 阅读量 / 热度值
        reads = 0
        w = re.search(r'<td class="ws">([^<]+)</td>', row)
        if w:
            reads = parse_read_count(w.group(1))
        if reads == 0:
            w2 = re.search(r'<td[^>]*class="[^"]*hs[^"]*"[^>]*>([^<]+)</td>', row)
            if w2:
                reads = parse_read_count(w2.group(1))

        # tophub 用热量值，没有真实阅读量的节点标记 hasRealRead=false
        has_real_read = (reads > 0 and (w is not None)) and platform == "微信"

        # 封面图（图片型节点带）
        cover = ""
        img = re.search(r'<img src="(https?://[^\"]+)"', row)
        if img:
            cover = html.unescape(img.group(1))

        # 摘要（item-desc）
        desc = ""
        ds = re.search(r'<div class="item-desc">(.*?)</div>', row, re.S)
        if ds:
            desc = html.unescape(re.sub("<[^>]+>", "", ds.group(1))).strip()

        uid = hashlib.md5(url.encode("utf-8")).hexdigest()[:12]

        items.append({
            "id": uid,
            "title": title,
            "url": clean_url(url),
            "platform": platform,
            "board": board_name,
            "category": category if platform == "微信" else guess_category(title),
            "readCount": reads,
            "readCountText": (w.group(1).strip() if w else "—"),
            "hasRealRead": has_real_read,
            "rank": rank_base + idx + 1,
            "cover": cover,
            "desc": desc,
            "collectedAt": now_bj(),
        })

    print(f"  [{platform}/{board_name}] 抓到 {len(items)} 条")
    return items


def main():
    print("=" * 56)
    print("热榜数据采集 —— 数据源：tophub.today（真实阅读量）")
    print("=" * 56)

    all_items = []
    for node_id, platform, board, cat in NODES:
        print(f"\n→ 抓取 {platform} · {board}")
        all_items.extend(parse_node(node_id, platform, board, cat))

    # 去重（按 url）
    seen = set()
    uniq = []
    for it in all_items:
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        uniq.append(it)

    # 公众号爆文（真实阅读量）优先置顶
    uniq.sort(key=lambda x: (not x["hasRealRead"], -(x["readCount"] or 0)))

    os.makedirs(OUT_DIR, exist_ok=True)
    payload = {
        "updatedAt": now_bj(),
        "source": "tophub.today",
        "total": len(uniq),
        "withRealRead": sum(1 for i in uniq if i["hasRealRead"]),
        "articles": uniq,
    }
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 56)
    print(f"完成：共 {len(uniq)} 条，其中 {payload['withRealRead']} 条带真实阅读量")
    print(f"写入：{OUT_FILE}")
    print("=" * 56)
    top = [i for i in uniq if i["hasRealRead"]][:5]
    if top:
        print("\n真实阅读量 TOP5：")
        for t in top:
            print(f"  {t['readCountText']:>7}  {t['title'][:40]}")


if __name__ == "__main__":
    main()
