#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""部署 Supabase Edge Functions"""
import sys, json, urllib.request, urllib.error, os

TOKEN = os.environ.get("SB_TOKEN", "")
REF = os.environ.get("SB_REF", "wcnssyiqitugqfmcbdhe")
BASE = f"https://api.supabase.com/v1/projects/{REF}/functions"

def api(method, url, data=None, ctype="application/json"):
    req = urllib.request.Request(url, data=data, method=method,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": ctype})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.status, r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "ignore")
    except Exception as e:
        return 0, str(e)

def deploy(name, path):
    code = open(path, encoding="utf-8").read()
    # Supabase 部署接口：POST /functions，body 带 name/entrypoint_path/body
    payload = json.dumps({
        "slug": name,
        "name": name,
        "entrypoint_path": "index.ts",
        "body": code,
    }, ensure_ascii=False).encode("utf-8")
    st, txt = api("POST", f"{BASE}?slug={name}", payload)
    print(f"[{name}] HTTP {st}")
    if st in (200, 201):
        try:
            j = json.loads(txt)
            print(f"  ✓ 部署成功  id={j.get('id','?')}  version={j.get('version','?')}")
            print(f"  状态: {j.get('status','?')}")
            return True
        except Exception:
            print("  响应:", txt[:200])
            return st < 300
    else:
        print("  错误:", txt[:400])
    return False

if __name__ == "__main__":
    fns = [
        ("sync-bridge", r"D:\WorkBuddy\wxhot-studio\supabase\functions\sync-bridge\index.ts"),
        ("fetch-hot",  r"D:\WorkBuddy\wxhot-studio\supabase\functions\fetch-hot\index.ts"),
        ("aigc-detect",r"D:\WorkBuddy\wxhot-studio\supabase\functions\aigc-detect\index.ts"),
    ]
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for name, p in fns:
        if only and only != name:
            continue
        if not os.path.exists(p):
            print(f"[{name}] 跳过（文件不存在: {p}）")
            continue
        deploy(name, p)
        print()
