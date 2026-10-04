// Supabase Edge Function：AIGC 检测（腾讯朱雀官方 API）
// 部署：supabase functions deploy aigc-detect
// 环境变量（Dashboard 里设 Secret）：
//   ZHUQUE_KEY = EdgeOne 控制台创建的 API Key
//   ALLOW_ORIGIN = https://lwl555.github.io（可选，默认 *）

const ZHUQUE_URL = "https://ai-gateway.edgeone.link/v1/providers/zhuque-text/classify";
const KEY = Deno.env.get("ZHUQUE_KEY") || "";
const ORIGIN = Deno.env.get("ALLOW_ORIGIN") || "*";

const cors = {
  "Access-Control-Allow-Origin": ORIGIN,
  "Access-Control-Allow-Headers": "content-type,authorization",
  "Access-Control-Allow-Methods": "POST,OPTIONS",
  "Content-Type": "application/json",
};

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response(null, { headers: cors });

  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "仅支持 POST" }),
      { status: 405, headers: cors });
  }

  if (!KEY) {
    return new Response(JSON.stringify({
      error: "服务端未配置 ZHUQUE_KEY",
      hint: "在 Supabase Dashboard → Edge Functions → Secrets 里添加 ZHUQUE_KEY",
    }), { status: 500, headers: cors });
  }

  try {
    const { text, is_merge } = await req.json();
    const body = String(text || "").trim();
    if (body.replace(/\s/g, "").length < 50) {
      return new Response(JSON.stringify({ error: "文本太短（至少 50 字）" }),
        { status: 400, headers: cors });
    }

    const r = await fetch(ZHUQUE_URL, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ text: body, is_merge: is_merge !== false }),
    });

    if (!r.ok) {
      const t = await r.text();
      return new Response(JSON.stringify({
        error: `朱雀接口 ${r.status}`, detail: t.slice(0, 300),
      }), { status: 502, headers: cors });
    }

    const j = await r.json();

    // 归一化成前端好用的结构
    const seg = (j.segment_labels || []).map((s: any) => ({
      text: s.text,
      label: s.label,                       // 0 人工 / 1 AI / 2 疑似AI
      conf: s.conf,
      risk: s.label === 1 ? "ai" : s.label === 2 ? "suspect" : "human",
    }));

    return new Response(JSON.stringify({
      ok: true,
      score: j.softmax_confidence ?? 0,      // 整体 AI 置信度
      ratio: j.labels_ratio || {},           // {0:人工占比, 1:AI占比, 2:疑似占比}
      segments: seg,
      usage: j.makers_models_usage || j.usage || null,
      engine: "zhuque-text (EdgeOne)",
    }), { status: 200, headers: cors });

  } catch (e: any) {
    return new Response(JSON.stringify({ error: String(e?.message || e) }),
      { status: 500, headers: cors });
  }
});
