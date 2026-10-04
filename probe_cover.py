# 探测各平台真实封面的可获取性
import urllib.request, ssl, re, gzip, json

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

print('=== 探测A: 不反爬的平台能否拿到 og:image 真实封面 ===')
for plat in ['36氪', '虎嗅网', '今日头条', '微博', '知乎']:
    item = [x for x in arts if x['platform'] == plat and x.get('hasRealRead') is not None]
    if not item:
        continue
    u = item[0]['url']
    try:
        p = get(u)
        og = re.search(r'og:image"?\s*content="([^"]+)"', p)
        og2 = re.search(r'"image"\s*:\s*"(https?://[^"]{20,200})"', p)
        img = re.findall(r'<img[^>]+src="(https?://[^"]{20,200})"', p)
        got = og.group(1) if og else (og2.group(1) if og2 else (img[0] if img else None))
        print(f'  {plat:6} len={len(p):7} 封面={"有 " + got[:60] if got else "无"}')
    except Exception as e:
        print(f'  {plat:6} FAIL {type(e).__name__}')

print()
print('=== 探测B: 微信文章静态页里是否藏 mmbiz 封面图 ===')
wx = [x for x in arts if x['platform'] == '微信'][:4]
for x in wx:
    try:
        p = get(x['url'])
        fields = [k for k in ['cdn_url', 'msg_cdn_url', 'thumb_url', 'mmbiz', 'cover'] if k in p]
        m = re.search(r'(https?://mmbiz\.qpic\.cn/[^"\'<>\s]{20,200})', p)
        print(f'  len={len(p):6} 字段={fields or "无"}')
        print(f'    mmbiz封面={"有 " + m.group(1)[:65] if m else "无"}')
    except Exception as e:
        print(f'  FAIL {e}')
