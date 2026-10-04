#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文生图服务（最小可用封装）

用途：给前端 api/image 提供文生图能力。
支持 Agnes 官方图片模型（api.agnes-ai.cn），用户已有 key 直接用。

关键点（2026-09 实测）：
  正确域名是 https://api.agnes-ai.cn/v1  ← 不是 apihub.agnes-ai.com（后者 401）
  免费档有速率限制，连发会 429，冷却约 1 分钟

部署：python image_server.py   （本地或轻量 VPS）
"""

import json
import os
import time
import base64
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("PORT", "8787"))
AGNES_KEY = os.environ.get("AGNES_API_KEY", "")
AGNES_BASE = "https://api.agnes-ai.cn/v1"

# 候选图片模型（按可用性排序）
MODELS = ["agnes-image-1", "image-1", "agnes-2.5-pro-image"]

_lock = __import__("threading").Lock()
_last_call = 0.0
MIN_GAP = 8.0        # 两次调用最小间隔（秒），避开免费档 429


def gen_image(prompt: str, ratio: str = "16:9") -> str:
    """返回图片 data URL"""
    global _last_call
    with _lock:
        wait = MIN_GAP - (time.time() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.time()

    w, h = {"16:9": (1024, 576), "2.35:1": (1170, 498), "1:1": (1024, 1024),
            "4:3": (1024, 768)}.get(ratio, (1024, 576))

    payload = {
        "model": MODELS[0],
        "prompt": prompt,
        "size": f"{w}x{h}",
        "n": 1,
    }
    req = urllib.request.Request(
        f"{AGNES_BASE}/images/generations",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {AGNES_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            j = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")[:300]
        if e.code == 429:
            raise RuntimeError("图片模型速率限制中（免费档约 1 分钟冷却），请稍后重试")
        raise RuntimeError(f"图片接口 {e.code}: {detail}")

    d = (j.get("data") or [{}])[0]
    if d.get("b64_json"):
        return "data:image/png;base64," + d["b64_json"]
    if d.get("url"):
        return d["url"]
    raise RuntimeError(f"返回结构异常: {json.dumps(j)[:200]}")


class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "content-type")
        self.send_header("Access-Control-Allow-Methods", "POST,OPTIONS")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def log_message(self, fmt, *args):
        print(f"[http] {fmt % args}")

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            prompt = (body.get("prompt") or "").strip()
            ratio = body.get("ratio") or "16:9"

            if not prompt:
                return self._reply(400, {"error": "prompt 为空"})
            if not AGNES_KEY:
                return self._reply(503, {
                    "error": "未配置 AGNES_API_KEY",
                    "hint": "设置环境变量 AGNES_API_KEY 后重启服务",
                })

            url = gen_image(prompt, ratio)
            self._reply(200, {"images": [{"url": url}]})

        except Exception as e:
            print(f"[error] {e}")
            self._reply(500, {"error": str(e)})

    def _reply(self, code, payload):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    print("=" * 50)
    print("文生图服务启动 http://127.0.0.1:%d/api/image" % PORT)
    if AGNES_KEY:
        print("[ok] 已配置 AGNES_API_KEY（%s...）" % AGNES_KEY[:8])
    else:
        print("[warn] 未配置 AGNES_API_KEY，接口会返回 503")
    print("[info] 模型候选：", ", ".join(MODELS))
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
