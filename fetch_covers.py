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


def main():
    d = json.load(open('data/articles.json', encoding='utf-8'))
    arts = d['articles'] if isinstance(d, dict) else d

    # 微信等反爬平台跳过；先试不反爬的
    targets = [a for a in arts if a['platform'] in ('36氪', '今日头条', '虎嗅网', '知乎', '微博')]
    got = 0
    for i, a in enumerate(targets, 1):
        if a.get('cover'):
            continue
        try:
            page = get(a['url'])
            c = pick_cover(page)
            if c:
                a['cover'] = c
                a['coverReal'] = True
                got += 1
                print(f'[{i}/{len(targets)}] ✓ {a["platform"]:6} {a["title"][:24]:26} -> {c[:58]}')
            else:
                print(f'[{i}/{len(targets)}] · {a["platform"]:6} {a["title"][:24]:26} -> 无封面(留色块)')
        except Exception as e:
            print(f'[{i}/{len(targets)}] × {a["platform"]:6} {a["title"][:20]:24} FAIL {type(e).__name__}')
        time.sleep(0.3)  # 轻限速，别把对方站点打崩

    # 微信等反爬平台显式标记，前端不虚标
    for a in arts:
        if a['platform'] == '微信' and not a.get('cover'):
            a['coverNoneReason'] = '微信风控无法静态抓取原文封面'

    json.dump(d, open('data/articles.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    real = sum(1 for a in arts if a.get('cover') and a.get('coverReal'))
    print(f'\n完成：新增真封面 {got} 张，库内真封面总数 {real}/{len(arts)}')
    print('封面来源分布：')
    from collections import Counter
    for k, v in Counter((a['platform'], bool(a.get('cover'))) for a in arts).items():
        print(f'  {k[0]:6} {"有封面" if k[1] else "无封面"}: {v}')


if __name__ == '__main__':
    main()
