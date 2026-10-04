# 测试: agnes-image 免费图片模型能否调通（用 Supabase 代理的 key 直连）
# 走 api.agnes-ai.cn 正确域名
import urllib.request, ssl, json

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# 图片模型走 /v1/images/generations
# 这里用占位——需要真实 AGNES_API_KEY。优先复用平台已配置的代理。
# 代理 base: https://wcnssyiqitugqfmcbdhe.functions.supabase.co/agnes-proxy
# 但平台现有代理只转 chat/completions。图片需要单独确认。

print('=== 检查平台现有代理是否支持图片端点 ===')
BASE = 'https://wcnssyiqitugqfmcbdhe.functions.supabase.co/agnes-proxy'
ANON = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndjbnNzeWlxaXR1Z3FmbWNiZGhlIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODM0MDEyNzUsImV4cCI6MjA5ODk3NzI3NX0.9EfbEr7BQhZtbOwHJ3IrkOy16kcaxlmzuJuV0A2Z8Eg'

# 试图片端点
for path in ['/v1/images/generations', '/v1/chat/completions']:
    try:
        body = json.dumps({
            'model': 'agnes-image-2.5-flash',
            'prompt': 'a minimal blue abstract background',
            'n': 1, 'size': '1K'
        }).encode()
        req = urllib.request.Request(
            BASE + path, data=body,
            headers={
                'Authorization': 'Bearer ' + ANON,
                'Content-Type': 'application/json'
            }
        )
        resp = urllib.request.urlopen(req, timeout=60, context=ctx)
        print(f'  {path:28} HTTP {resp.status} OK')
        r = json.loads(resp.read().decode())
        print('    返回 keys:', list(r.keys()))
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', 'ignore')[:120]
        print(f'  {path:28} HTTP {e.code} - {body}')
    except Exception as e:
        print(f'  {path:28} FAIL {type(e).__name__}: {str(e)[:60]}')
