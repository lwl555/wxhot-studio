#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
热榜数据采集器
数据源：
  1) 今日热榜 tophub.today —— 微信/微博/知乎/抖音等 30+ 平台（免费、免 key、含真实阅读量）
  2) GitHub 官方搜索 API —— 开源热门（最近创建 + star 排序，免 token）
  3) HelloGitHub 月刊 RSS + 详情页 —— 精选开源项目（含中文简介）

输出：data/articles.json（含 fetchLog 诊断字段）
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

# 节点清单：(节点ID, 平台标签, 榜单名, 默认分类)
# 默认分类：仅当标题没命中关键词分类时兜底（空串 → 走 BOARD_FALLBACK / 综合）
NODES = [
    ("WnBe01o371", "微信", "微信24h热文榜", ""),
    ("W1VdJPZoLQ", "微信", "微信今日视频榜", ""),
    ("KMZd7VOvrO", "知乎", "知乎日报Today", ""),
    ("mproPpoq6O", "知乎", "知乎热榜", ""),
    ("KqndgxeLl9", "微博", "微博热搜榜", ""),
    ("x9ozB4KoXb", "今日头条", "今日头条头条热榜", ""),
    ("Jb0vmloB1G", "百度", "百度实时热点", ""),
    ("Om4ejxvxEN", "百度贴吧", "百度贴吧热议榜", ""),
    ("DpQvNABoNE", "抖音", "抖音总榜", ""),
    ("74KvxwokxM", "哔哩哔哩", "哔哩哔哩全站日榜", ""),
    ("Q1Vd5Ko85R", "36氪", "36氪24小时热榜", "科技数码"),
    ("5VaobgvAj1", "虎嗅网", "虎嗅网热文", "科技数码"),
    ("wWmoO5Rd4E", "澎湃", "澎湃热榜", "社会热点"),
    ("DOvnNz1vEB", "机器之心", "机器之心", "科技数码"),
    ("MZd7azPorO", "量子位", "量子位", "科技数码"),
    ("Y2KeDGQdNP", "少数派", "少数派热门文章", "科技数码"),
    ("4KvxEX0dkx", "微信读书", "微信读书总榜", "书单"),
    ("mDOvnyBoEB", "豆瓣", "豆瓣电影新片榜", "娱乐影视"),
    ("3adqqzadng", "抖音", "抖音热点榜", ""),
    ("WYKd69jvaP", "梨视频", "梨视频总榜", "娱乐影视"),
    ("MZd7VN3vrO", "百度视频", "百度视频榜", "娱乐影视"),

    # ── 第二批：补垂直领域厚度（财经 / 体育 / 科技 / 娱乐 / 汽车 / 短视频 / 社区）──
    ("G2me3ndwjq", "华尔街见闻", "华尔街见闻日排行", "财经理财"),
    ("0MdKam4ow1", "第一财经", "第一财经热榜", "财经理财"),
    ("wWmoOqYd4E", "新浪体育", "新浪体育点击榜", "体育赛事"),
    ("G47o8weMmN", "虎扑", "虎扑社区热帖", "体育赛事"),
    ("rYqoXz8dOD", "掘金", "掘金技术热榜", "科技数码"),
    ("20MdK2vw1q", "果壳", "果壳科学人", "科技数码"),
    ("YqoXQGXvOD", "汽车之家", "汽车之家热榜", "科技数码"),
    ("9JndkpJe3V", "猫眼", "猫眼国内票房榜", "娱乐影视"),
    ("12owgX0oNV", "腾讯新闻", "腾讯新闻热榜", "社会热点"),
    ("NRrvWq3e5z", "煎蛋", "煎蛋热门", "科技数码"),
    ("MZd7PrPerO", "快手", "快手实时热榜", "社会热点"),

    # ── 第三批：扩满微信/公众号内容（tophub 各垂直维度 24h 热文榜）──
    ("WmoOxxDv4E", "微信", "微信·军事24h热文榜", "社会热点"),
    ("5PdMaaadmg", "微信", "微信·科技24h热文榜", "科技数码"),
    ("proPGGOeq6", "微信", "微信·文化24h热文榜", "社会热点"),
    ("nBe0xxje37", "微信", "微信·生活24h热文榜", "生活美食"),
    ("DOvn33ydEB", "微信", "微信·职场24h热文榜", "职场成长"),
    ("Ywv4BJRePa", "微信", "微信·财经24h热文榜", "财经理财"),
    ("MZd7BVYvrO", "微信", "微信·教育24h热文榜", "教育考试"),
    ("x9ozmmYeXb", "微信", "微信·历史24h热文榜", "社会热点"),
    ("Q0orrr0o8B", "微信", "微信·健康24h热文榜", "健康养生"),
    ("anoppbRolZ", "微信读书", "微信读书飙升榜", "书单"),
]

# 关键词分类（按标题命中；规则自上而下，先具体后宽泛）
CATEGORY_RULES = [
    ("科技数码", ["苹果", "华为", "小米", "特斯拉", "芯片", "AI", "人工智能", "手机", "电脑",
                 "模型", "算法", "机器人", "程序员", "互联网", "卫星", "火箭", "SpaceX",
                 "OpenAI", "英伟达", "显卡", "自动驾驶", "新能源", "数码", "发布会的",
                 "系统", "微信", "抖音", "B站", "APP", "App", "软件", "代码"]),
    ("财经理财", ["股", "黄金", "房价", "楼市", "银行", "存款", "利率", "基金", "经济", "GDP",
                 "央行", "汇率", "投资", "负债", "工资", "补贴", "A股", "美股", "涨停",
                 "市值", "融资", "上市", "降息", "通胀", "理财", "首付", "贷款", "亿元"]),
    ("社会热点", ["通报", "警方", "事故", "遇难", "官方", "回应", "调查", "处罚", "判决", "起诉",
                 "食品", "安全", "突发", "火灾", "地震", "台风", "暴雨", "辟谣", "紧急",
                 "中国", "美国", "日本", "俄罗斯", "韩国", "热搜", "身亡", "离世", "争议"]),
    ("娱乐影视", ["电影", "电视剧", "明星", "演唱会", "综艺", "票房", "官宣", "剧组", "演员",
                 "导演", "开播", "杀青", "收视", "偶像", "粉丝", "影视", "首播", "上映",
                 "预告", "口碑", "剧", "真人秀", "追剧", "红毯", "颁奖"]),
    ("体育赛事", ["亚运", "奥运", "世界杯", "比赛", "夺冠", "金牌", "球队", "球员", "足球",
                 "篮球", "冠军", "决赛", "S赛", "国足", "NBA", "CBA", "联赛", "教练",
                 "进球", "季后赛", "转会", "电竞", "世锦赛", "积分榜", "淘汰"]),
    ("健康养生", ["医生", "医院", "疾病", "养生", "血压", "血糖", "体检", "寿命", "睡眠",
                 "饮食", "中医", "癌", "健康", "锻炼", "跑步", "减肥", "熬夜", "颈椎",
                 "免疫力", "流感", "感冒", "吃药", "上火", "体质", "猝死", "身体"]),
    ("情感心理", ["情感", "婚姻", "离婚", "恋爱", "爱情", "家庭", "婆媳", "中年", "焦虑",
                 "内耗", "emo", "孤独", "相亲", "单身", "分手", "心理", "性格",
                 "安全感", "自卑", "讨好", "结婚", "彩礼"]),
    ("职场成长", ["职场", "打工", "老板", "同事", "辞职", "offer", "面试", "简历",
                 "副业", "35岁", "35+", "裁员", "加班", "跳槽", "涨薪", "年终奖",
                 "自由职业", "成长", "自律", "认知", "思维", "月薪", "年入"]),
    ("教育考试", ["高考", "中考", "学生", "老师", "教师", "大学", "高校", "考试", "录取",
                 "教育", "孩子", "家长", "开学", "考研", "考公", "公务员", "志愿",
                 "分数线", "寒假", "暑假", "幼儿园", "小学", "中学", "家庭教育"]),
    ("生活美食", ["美食", "菜谱", "早餐", "做饭", "餐厅", "好吃", "小吃", "火锅", "奶茶",
                 "零食", "厨房", "面", "饭", "旅游", "旅行", "景点", "出游", "自驾",
                 "咖啡", "烘焙", "家常菜", "做法", "攻略", "避坑", "好物", "收纳", "生活"]),
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


# 榜单主题兜底：标题/摘要都没命中关键词时，按榜单性质归类
BOARD_FALLBACK = {
    "微博热搜榜": "社会热点", "百度实时热点": "社会热点", "今日头条头条热榜": "社会热点",
    "抖音热点榜": "社会热点", "抖音总榜": "社会热点", "百度贴吧热议榜": "社会热点",
    "知乎热榜": "社会热点", "豆瓣电影新片榜": "娱乐影视",
    "新浪体育点击榜": "体育赛事", "猫眼国内票房榜": "娱乐影视",
    "汽车之家热榜": "科技数码", "快手实时热榜": "社会热点",
    "腾讯新闻热榜": "社会热点", "华尔街见闻日排行": "财经理财",
    "第一财经热榜": "财经理财", "掘金技术热榜": "科技数码",
    "果壳科学人": "科技数码", "煎蛋热门": "科技数码",
}


def guess_category(title, board="", default_cat=None):
    for cat, kws in CATEGORY_RULES:
        for k in kws:
            if k in title:
                return cat
    if default_cat:
        return default_cat
    if board and board in BOARD_FALLBACK:
        return BOARD_FALLBACK[board]
    return "综合"


def clean_url(u):
    return u.split("#")[0]



def fix_cover(u):
    """封面统一 https：网页部署在 HTTPS 下，http 图片会被浏览器拦截（Mixed Content）"""
    if not u:
        return ""
    u = u.strip()
    if u.startswith("http://"):
        return "https://" + u[len("http://"):]
    return u

def parse_node(node_id, platform, board_name, default_cat=None, rank_base=0):
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
            "category": guess_category(title + " " + desc, board_name, default_cat),
            "readCount": reads,
            "readCountText": (w.group(1).strip() if w else "—"),
            "hasRealRead": has_real_read,
            "source": "tophub",
            "rank": rank_base + idx + 1,
            "cover": fix_cover(cover),
            "desc": desc,
            "collectedAt": now_bj(),
        })

    print(f"  [{platform}/{board_name}] 抓到 {len(items)} 条")
    return items


# ───────────────────────── 开源平台 ─────────────────────────
def parse_star(s):
    """'12,345' / '5.2k' / '5.2w' / '1.7万' -> int"""
    s = (s or "").strip().lower().replace(",", "")
    if not s:
        return 0
    m = re.match(r"([\d.]+)\s*([k万w]?)", s)
    if not m:
        m2 = re.search(r"\d+", s)
        return int(m2.group()) if m2 else 0
    num = float(m.group(1))
    unit = m.group(2)
    if unit == "w":
        num *= 10000
    elif unit == "k":
        num *= 1000
    elif unit == "万":
        num *= 10000
    return int(num)


def fmt_star(n):
    if not n:
        return "0"
    if n >= 10000:
        v = n / 10000
    elif n >= 1000:
        v = n / 1000
    else:
        return str(n)
    s = ("%.1f" % v).rstrip("0").rstrip(".")
    return s + ("万" if n >= 10000 else "k")


def build_item(title, url, platform, board, category, desc, reads, reads_text, source):
    uid = hashlib.md5(url.encode("utf-8")).hexdigest()[:12]
    return {
        "id": uid,
        "title": title,
        "url": clean_url(url),
        "platform": platform,
        "board": board,
        "category": category,
        "readCount": reads,
        "readCountText": reads_text,
        "hasRealRead": False,
        "source": source,
        "rank": 0,
        "cover": "",
        "desc": (desc or "").strip(),
        "collectedAt": now_bj(),
    }


FETCH_LOG = []   # 记录各开源源抓取状态，随 articles.json 一起输出，便于远程排查

def fetch_github_trending(since_days, label):
    """GitHub 官方搜索 API：取「最近 N 天创建、按 star 排序」的仓库，作为开源热门代理。
    免 token（非认证限额 10 次/分钟，每小时跑几次足够）。"""
    since = (datetime.datetime.utcnow() - datetime.timedelta(days=since_days)).strftime("%Y-%m-%d")
    url = (f"https://api.github.com/search/repositories?q=created:>{since}"
           f"&sort=stars&order=desc&per_page=25")
    txt = fetch(url)
    ok = bool(txt)
    items, note = [], ""
    if txt:
        try:
            data = json.loads(txt)
            if "items" not in data:
                note = (data.get("message") or "no items")[:80]
            for it in (data.get("items") or []):
                repo = it.get("full_name", "")
                if not repo or repo.count("/") != 1:
                    continue
                desc = (it.get("description") or "").strip()
                lang = it.get("language") or ""
                stars = it.get("stargazers_count") or 0
                title = repo + ((" · " + lang) if lang else "")
                items.append(build_item(
                    title, it.get("html_url", "https://github.com/" + repo),
                    "GitHub", label, "科技数码", desc, stars,
                    ("★" + fmt_star(stars)) if stars else "—", "github"))
        except Exception as e:
            note = f"json err: {e}"
    FETCH_LOG.append({"source": "GitHub/" + label, "fetched": ok, "items": len(items), "note": note})
    print(f"  [GitHub/{label}] 抓到 {len(items)} 个仓库" + (f"（{note}）" if note else ""))
    return items


def fetch_hellogithub():
    """HelloGitHub 月刊：从 RSS 拿到最新一期，再抓该期里的开源项目（含简介）。"""
    rss = fetch("https://hellogithub.com/rss")
    vol = ""
    m = re.search(r'https://hellogithub\.com/periodical/volume/(\d+)', rss or "")
    if m:
        vol = m.group(1)
    if not vol:
        FETCH_LOG.append({"source": "HelloGitHub/月刊", "fetched": bool(rss),
                          "items": 0, "note": "rss 未解析到 volume"})
        return []
    page = fetch(f"https://hellogithub.com/periodical/volume/{vol}")
    if not page:
        FETCH_LOG.append({"source": "HelloGitHub/月刊", "fetched": False,
                          "items": 0, "note": f"v{vol} 页面为空"})
        return []
    for j, lm in enumerate(links):
        repo = lm.group(1).rstrip("/")
        name = html.unescape(lm.group(2)).strip()
        if repo in seen or not name:
            continue
        seen.add(repo)
        start = lm.end()
        end = links[j + 1].start() if j + 1 < len(links) else len(page)
        chunk_raw = page[start:end]
        # 先抽 Star（清洗会删掉 Star 文本，所以先取）
        sm = re.search(r"Star\s*([\d.,]+[k万w]?)", chunk_raw)
        stars = parse_star(sm.group(1)) if sm else 0
        # 再清洗成简介
        chunk = re.sub(r"<[^>]+>", " ", chunk_raw)
        chunk = html.unescape(chunk)
        chunk = re.sub(r"Star\s*[\d.,]*[k万w]?", " ", chunk)
        chunk = re.sub(r"(Fork|详情|\[\s*详情\s*\])", " ", chunk)
        chunk = re.sub(r"[\d,]+\s*(天前|小时前|分钟前)", " ", chunk)
        chunk = re.sub(r"^\s*\d+\s*[\.、]?\s*", "", chunk)
        desc = re.sub(r"\s+", " ", chunk).strip()[:160]
        items.append(build_item(
            name, repo, "HelloGitHub", "HelloGitHub 月刊", "科技数码",
            desc, stars, ("★" + fmt_star(stars)) if stars else "—", "hellogithub"))
    FETCH_LOG.append({"source": "HelloGitHub/月刊", "fetched": True,
                      "items": len(items), "note": f"v{vol}"})
    print(f"  [HelloGitHub 月刊 v{vol}] 抓到 {len(items)} 个项目")
    return items


def main():
    print("=" * 56)
    print("热榜数据采集 —— 数据源：tophub.today + GitHub Trending + HelloGitHub")
    print("=" * 56)

    all_items = []
    for node_id, platform, board, cat in NODES:
        print(f"\n→ 抓取 {platform} · {board}")
        all_items.extend(parse_node(node_id, platform, board, cat))

    # 开源平台（免 token：GitHub 官方搜索 API + HelloGitHub 月刊）
    print("\n→ 抓取 开源平台 · GitHub（官方 API）")
    all_items.extend(fetch_github_trending(1, "GitHub 本日新热"))
    all_items.extend(fetch_github_trending(7, "GitHub 本周新热"))
    all_items.extend(fetch_github_trending(30, "GitHub 本月新热"))
    print("\n→ 抓取 开源平台 · HelloGitHub 月刊")
    all_items.extend(fetch_hellogithub())

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

    # 继承上一轮已采集到的封面/摘要：本轮是全新抓取，不继承的话补图成果会被覆盖丢失
    old = {}
    try:
        with open(OUT_FILE, encoding="utf-8") as f:
            old = json.load(f)
        oldmap = {x.get("url"): x for x in (old.get("articles") or [])}
    except Exception:
        oldmap = {}
    inherited = 0
    for it in uniq:
        o = oldmap.get(it["url"])
        if not o:
            continue
        if not it.get("cover") and o.get("cover"):
            it["cover"] = o["cover"]
            if o.get("coverReal"):
                it["coverReal"] = True
            inherited += 1
        if not it.get("desc") and o.get("desc"):
            it["desc"] = o["desc"]
    if inherited:
        print(f"\n继承上一轮封面 {inherited} 条（避免补图成果被覆盖）")

    # 保留上一轮来自「非本轮实时抓取」源的条目（如已废弃的 dailyhot），
    # 本轮实时抓取的 tophub/github/hellogithub 不继承旧值，避免开源榜堆积陈旧仓库
    FRESH_SOURCES = {"tophub", "github", "hellogithub"}
    seen_u = {x["url"] for x in uniq}
    kept = 0
    for x in (old.get("articles") or []):
        if x.get("source") and x.get("source") not in FRESH_SOURCES and x.get("url") not in seen_u:
            uniq.append(x)
            seen_u.add(x["url"])
            kept += 1
    if kept:
        print(f"保留其他数据源条目 {kept} 条")

    os.makedirs(OUT_DIR, exist_ok=True)
    payload = {
        "updatedAt": now_bj(),
        "source": "tophub.today + GitHub API + HelloGitHub",
        "total": len(uniq),
        "withRealRead": sum(1 for i in uniq if i["hasRealRead"]),
        "fetchLog": FETCH_LOG,
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
