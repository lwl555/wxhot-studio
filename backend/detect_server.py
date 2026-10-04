#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
朱雀 AIGC 检测服务（最小可用封装）

用途：给静态前端一个 HTTP 端点，底层调用腾讯朱雀检测能力。
部署：本地 python detect_server.py，或放到轻量 VPS 上。

前置：需要能调用朱雀检测。两种方式任选：
  方式A：装了开源 CLI  → pip install "git+https://github.com/Sophomoresty/zhuque.git"
                        然后本脚本调用命令行
  方式B：有朱雀网页版  → 在下方 FILL_IN 填入网页版接口地址与凭据

限流提示：单 IP 约 36 次/小时、785 次/天。本脚本已内置串行队列与冷却。
"""

import json
import os
import re
import time
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("PORT", "8000"))

# ── 限流器：照搬朱雀实测限制，宁可慢也别被风控 ──
COOLDOWN_SECONDS = 30 * 60      # 触发风控后冷却 30 分钟
MAX_PER_HOUR = 32               # 留 4 次余量
_lock = threading.Lock()
_calls = []                     # 时间戳队列
_cooling_until = 0.0


def rate_gate():
    """返回 0 表示可继续，返回 >0 表示需要等待的秒数"""
    global _cooling_until
    with _lock:
        now = time.time()
        if now < _cooling_until:
            return int(_cooling_until - now)
        # 清理一小时前
        while _calls and _calls[0] < now - 3600:
            _calls.pop(0)
        if len(_calls) >= MAX_PER_HOUR:
            return int(3600 - (now - _calls[0]) + 5)
        _calls.append(now)
        return 0


def trip_breaker():
    """检测到风控时触发"""
    global _cooling_until
    _cooling_until = time.time() + COOLDOWN_SECONDS
    print(f"[rate-limit] 触发风控，冷却 {COOLDOWN_SECONDS // 60} 分钟")


# ── 朱雀 CLI 调用 ──
def detect_via_cli(text: str) -> dict:
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False,
                                     encoding="utf-8") as f:
        f.write(text)
        path = f.name
    try:
        proc = subprocess.run(
            ["zhuque", "check", "--file", path],
            capture_output=True, text=True, timeout=120,
        )
        if proc.returncode != 0:
            err = proc.stderr or proc.stdout
            if "evil_level" in err or "rate" in err.lower():
                trip_breaker()
            raise RuntimeError(f"zhuque CLI 失败: {err[:300]}")
        return json.loads(proc.stdout)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


# ── 分段（朱雀本来就会分段，这里做兜底） ──
def local_segment(text: str, per_seg: int = 180) -> list:
    paras = [p.strip() for p in text.split("\n") if p.strip()]
    segs, buf, n = [], [], 0
    for p in paras:
        buf.append(p)
        n += len(p)
        if n >= per_seg:
            segs.append("\n".join(buf))
            buf, n = [], 0
    if buf:
        segs.append("\n".join(buf))
    return segs or [text[:400]]


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
        if self.path.rstrip("/") != "/check":
            self.send_response(404)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error":"not found"}')
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            text = (body.get("text") or "").strip()

            if len(text.replace("\s", "")) < 200:
                self._reply(400, {"error": "文本不足 200 字"})
                return

            wait = rate_gate()
            if wait > 0:
                self._reply(429, {
                    "error": "触发限流",
                    "retryAfterSec": wait,
                    "hint": f"朱雀限流较严，约需等待 {wait // 60} 分钟后再试",
                })
                return

            result = detect_via_cli(text)

            # 补充分段文本，便于前端高亮
            labels = result.get("segment_labels") or []
            for lb in labels:
                if not lb.get("text"):
                    segs = local_segment(text)
                    idx = labels.index(lb)
                    lb["text"] = segs[idx][:120] if idx < len(segs) else ""

            self._reply(200, result)

        except Exception as e:
            print(f"[error] {type(e).__name__}: {e}")
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
    # 检查 zhuque 是否可用
    try:
        subprocess.run(["zhuque", "--version"], capture_output=True, timeout=10)
        print("[ok] 检测到 zhuque CLI")
    except Exception:
        print("[warn] 未找到 zhuque CLI。安装：")
        print("       pip install \"git+https://github.com/Sophomoresty/zhuque.git\"")
        print("       并确保已装 Node.js 与 jsdom（npm install -g jsdom）")

    print(f"[ok] 检测服务启动： http://127.0.0.1:{PORT}/check")
    print(f"[info] 限流：每小时 {MAX_PER_HOUR} 次，冷却 {COOLDOWN_SECONDS // 60} 分钟")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
