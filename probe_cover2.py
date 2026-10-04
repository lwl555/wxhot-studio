# 探测: 微信封面真实可行的获取路径
import urllib.request, ssl, re, gzip, json, urllib.parse

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def get(u, ref=None):
    h = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0',
        'Accept-Language': 'zh-CN,zh;q=0.9',
    }
    if ref:
        h['Referer'] = ref
    resp = urllib.request.urlopen(urllib.request.Request(u, headers=h), timeout=20, context=ctx)
    raw = resp.read()
    if resp.headers.get('Content-Encoding') == 'gzip':
        raw = gzip.decompress(raw)
    return raw.decode('utf-8', 'ignore')

d = json.load(open('data/articles.json', encoding='utf-8'))
arts = d['articles'] if isinstance(d, dict) else d

# 1. 已有 reprint 的5 条, 能否从转载页拿 og:image (同文真封面)
print('=== 路径A: 从已验证的转载页抓 og:image（标题一致=真图）===')
rep = [x for x in arts if x.get('reprint')]
for x in rep:
    try:
        p = get(x['reprint'])
        og = re.search(r'og:image"?\s*content="([^"]+)"', p)
        print(f'  {x["title"][:24]:26} -> {"有 " + og.group(1)[:55] if og else "无 og:image"}')
    except Exception as e:
        print(f'  {x["title"][:24]:26} -> FAIL {type(e).__name__}')

# 2. 搜狗微信搜索 — 看能否按标题搜到并拿到缩略图
print()
print('=== 路径B: 搜狗微信搜索缩略图 ===')
q = urllib.parse.quote(arts[[a["platform"] for a in arts].index("微信")]["title"])
try:
    p = get(f'https://weixin.sogou.com/weixin?type=2&query={q}')
    print('  搜狗返回 len=', len(p), '| 反爬=', ('antispider' in p or '验证码' in p))
    # 搜狗结果里的缩略图
    imgs = re.findall(r'<img[^>]+src="(https?://[^"]{20,200})"', p)
    print('  img 标签数=', len(imgs), '| 样例=', imgs[0][:70] if imgs else '无')
except Exception as e:
    print('  搜狗 FAIL', type(e).__name__, str(e)[:60])
