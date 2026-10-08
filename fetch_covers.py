# 采集真实封面（og:image）
# 只对不反爬的平台抓真封面；抓不到的留空，前端用首字色块
import urllib.request, ssl, re, gzip, json, sys, time

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0'


def get(u, ref=None):
    h = {'User-Agent': UA, 'Accept-Language': 'zh-CN,zh;q=0.9'}
    if ref:
        h['Referer'] = ref
    resp = urllib.request.urlopen(urllib.request.Request(u, headers=h), timeout=20, context=ctx)
    raw = resp.read()
    if resp.headers.get('Content-Encoding') == 'gzip':
        raw = gzip.decompress(raw)
    return raw.decode('utf-8', 'ignore')


def pick_cover(page):
    """按优先级提取封面：og:image > twitter:image > 正文首图"""
    for pat in [
        r'og:image"?\s*content="([^"]+)"',
        r'twitter:image"?\s*content="([^"]+)"',
        r'"image"\s*:\s*"(https?://[^"]{20,300})"',
    ]:
        m = re.search(pat, page)
        if m:
            u = m.group(1).replace('&amp;', '&')
            if u.startswith('http'):
                return u
    return None


def pick_desc(page):
    """按优先级提取摘要：og:description > meta description > twitter:description"""
    for pat in [
        r'og:description"?\s*content="([^"]+)"',
        r'<meta[^>]+name="description"[^>]+content="([^"]+)"',
        r'twitter:description"?\s*content="([^"]+)"',
    ]:
        m = re.search(pat, page, re.I)
        if m:
            s = re.sub(r'<[^>]+>', '', m.group(1)).replace('&amp;', '&').replace('&nbsp;', ' ').strip()
            if 10 <= len(s) <= 400:
                return s
    return None


def main():
    d = json.load(open('data/articles.json', encoding='utf-8'))
    arts = d['articles'] if isinstance(d, dict) else d

    # 微信、B站等反爬平台跳过；其余静态可抓的都试（渐进补齐，每次限量避免 Actions 超时）
    PLATS = ('36氪', '今日头条', '虎嗅网', '知乎', '微博', '澎湃', '少数派',
             '豆瓣', '机器之心', '量子位', '梨视频', '百度视频', '百度贴吧')
    MAX_PER_RUN = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    targets = [a for a in arts if a['platform'] in PLATS and (not a.get('cover') or not a.get('desc'))]
    targets = targets[:MAX_PER_RUN]
    got_c = got_d = 0
    for i, a in enumerate(targets, 1):
        needC, needD = not a.get('cover'), not a.get('desc')
        try:
            page = get(a['url'])
            c = pick_cover(page) if needC else None
            d2 = pick_desc(page) if needD else None
            if c:
                a['cover'] = c
                a['coverReal'] = True
                got_c += 1
            if d2:
                a['desc'] = d2[:300]
                got_d += 1
            flag = ('图' if c else '') + ('摘' if d2 else '')
            print(f'[{i}/{len(targets)}] {"✓" if flag else "·"} {a["platform"]:6} {a["title"][:22]:24} -> {flag or "无"}')
        except Exception as e:
            print(f'[{i}/{len(targets)}] × {a["platform"]:6} {a["title"][:18]:22} FAIL {type(e).__name__}')
        time.sleep(0.3)  # 轻限速，别把对方站点打崩

    # 微信等反爬平台显式标记，前端不虚标
    for a in arts:
        if a['platform'] == '微信' and not a.get('cover'):
            a['coverNoneReason'] = '微信风控无法静态抓取原文封面'

    json.dump(d, open('data/articles.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    real = sum(1 for a in arts if a.get('cover') and a.get('coverReal'))
    print(f'\n完成：本轮新增封面 {got_c} 张、摘要 {got_d} 条')
    print(f'  库内真封面 {real}/{len(arts)}，有摘要 {sum(1 for a in arts if a.get("desc"))}/{len(arts)}')
    print('封面来源分布：')
    from collections import Counter
    for k, v in Counter((a['platform'], bool(a.get('cover'))) for a in arts).items():
        print(f'  {k[0]:6} {"有封面" if k[1] else "无封面"}: {v}')


if __name__ == '__main__':
    main()
