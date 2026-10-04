# Supabase Edge Function：AIGC 检测代理
# 部署： supabase functions deploy aigc-detect
# 作用：把前端请求转发到自建的朱雀检测服务（隐藏内网地址与限流池）

// 部署后请把这个文件放到： supabase/functions/aigc-detect/index.ts
// 并在 Supabase Dashboard 设置：
//   ZHUQUE_URL  = 你的朱雀检测服务地址（本地或 VPS）
//   ZHUQUE_KEY  = 你的朱雀服务鉴权 key（如果没设鉴权可留空）

const ALLOWED = ["http://localhost:8000", "http://127.0.0.1:8000"];

Deno.serve(async (req: Request) => {
  const cors = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "content-type,authorization",
    "Access-Control-Allow-Methods": "POST,OPTIONS",
  };

  if (req.method === "OPTIONS") return new Response(null, { headers: cors });
  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "method not allowed" }), {
      status: 405, headers: { ...cors, "Content-Type": "application/json" },
    });
  }

  try {
    const { text } = await req.json();
    if (!text || text.replace(/\s/g, "").length < 200) {
      return new Response(JSON.stringify({ error: "文本不足 200 字" }), {
        status: 400, headers: { ...cors, "Content-Type": "application/json" },
      });
    }

    const target = Deno.env.get("ZHUQUE_URL") || "http://localhost:8000";
    const key = Deno.env.get("ZHUQUE_KEY") || "";
    if (target.startsWith("http://") && !ALLOWED.includes(target) &&
        !Deno.env.get("ZHUQUE_URL")) {
      return new Response(JSON.stringify({
        error: "未配置 ZHUQUE_URL",
        hint: "请先部署朱雀检测服务，或在 Supabase 设置 ZHUQUE_URL 环境变量",
      }), { status: 503, headers: { ...cors, "Content-Type": "application/json" } });
    }

    const r = await fetch(`${target}/check`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(key ? { "X-API-KEY": key } : {}),
      },
      body: JSON.stringify({ text }),
    });

    const j = await r.json();
    return new Response(JSON.stringify(j), {
      status: 200, headers: { ...cors, "Content-Type": "application/json" },
    });
  } catch (e) {
    return new Response(JSON.stringify({ error: String(e) }), {
      status: 500, headers: { ...cors, "Content-Type": "application/json" },
    });
  }
});
