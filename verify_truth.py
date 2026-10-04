# 验证微信文章真实性 + 从原文抓封面/公众号名回填
import json, re, time, urllib.request, ssl, html

ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Mobile Safari/537.36'}

d = json.load(open('data/articles.json', encoding='utf-8'))
arts = d['articles'] if isinstance(d, dict) else d

ok, fail = 0, []
for a in arts:
    if a.get('platform') != '微信':
        continue
    url = a['url']
    if 'mp.weixin.qq.com' not in url:
        continue
    try:
        req = urllib.request.Request(url, headers=UA)
        page = urllib.request.urlopen(req, timeout=20, context=ctx).read().decode('utf-8', 'ignore')
    except Exception as e:
        fail.append((a['title'][:30], type(e).__name__))
        continue

    # 1) 页面是否正常文章页
    alive = ('js_content' in page) or ('rich_media_title' in page) or ('<title>' in page and 'params' in page)
    # 2) 标题是否对得上（页面里的 var msg_title 或 <title>）
    m_title = re.search(r'var msg_title\s*=\s*[\'"]([^\'"]+)[\'"]', page) or re.search(r'<title>([^<]+)</title>', page)
    page_title = html.unescape(m_title.group(1)).strip() if m_title else ''
    match = a['title'][:14] in page_title or page_title[:14] in a['title']

    # 3) 封面图
    m_cdn = re.search(r'var msg_cdn_url\s*=\s*[\'"]([^\'"]+)[\'"]', page) or re.search(r'"(https?://mmbiz\.qpic\.cn/[^"]+)"', page)
    cover = m_cdn.group(1).replace('\\', '') if m_cdn else ''

    # 4) 公众号名
    m_nick = re.search(r'var nickname\s*=\s*[\'"]([^\'"]+)[\'"]', page) or re.search(r'id="js_name"[^>]*>\s*([^<]+?)\s*<', page)
    nick = html.unescape(m_nick.group(1)).strip() if m_nick else ''

    # 5) 发布时间
    m_ct = re.search(r'var ct\s*=\s*["\']?(\d{10})', page) or re.search(r'"publish_time"\s*:\s*"([^"]+)"', page)
    pub = m_ct.group(1) if m_ct else ''

    if alive and match:
        ok += 1
        if cover: a['cover'] = cover
        if nick: a['account'] = nick
        if pub: a['publishTs'] = pub
    else:
        fail.append((a['title'][:30], f'alive={alive} match={match} pageTitle={page_title[:24]}'))

    time.sleep(0.4)  # 温和访问，别触发微信风控

print(f'验证通过: {ok} 条')
print(f'验证失败: {len(fail)} 条')
for t, r in fail[:8]:
    print('  -', t, '|', r)

json.dump(d, open('data/articles.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('已回填 cover/account/publishTs 到 articles.json')
