// Supabase Edge Function：手机 ↔ PC 同步中转（原生 fetch，无外部依赖）
// 部署：supabase functions deploy sync-bridge（或管理 API PUT）
// 免费档免绑卡。前端用匿名调用（verify_jwt=false 已关闭）。
//
// 设计（按用户要求：按需连接，不常连）
//   - 无状态：只在收发数据时被调用，不维持长连接
//   - 每个设备有个 syncId（自己起个名字，如 "pc-家里的" / "手机"）
//   - pull: 取对方推上来的最新数据；push: 把自己的数据推上去
//
// 存储：Supabase 表 sync_store (sync_id text primary key, payload jsonb, updated_at timestamptz)
// 用 service_role key（Deno 环境自动注入）经 REST API 操作，绕过 RLS，安全隔离前端直连。

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "content-type,authorization,x-sync-id",
  "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
  "Content-Type": "application/json",
};

function authHeaders() {
  return {
    "apikey": SERVICE_KEY,
    "Authorization": `Bearer ${SERVICE_KEY}`,
    "Content-Type": "application/json",
  };
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response(null, { headers: cors });

  if (!SUPABASE_URL || !SERVICE_KEY) {
    return new Response(JSON.stringify({ error: "服务端未配置 SUPABASE_URL / SERVICE_ROLE_KEY" }),
      { status: 500, headers: cors });
  }

  const url = new URL(req.url);
  const syncId = req.headers.get("x-sync-id") || url.searchParams.get("id") || "";
  if (!syncId) {
    return new Response(JSON.stringify({ error: "缺少 syncId（用 x-sync-id 头或 ?id=）" }),
      { status: 400, headers: cors });
  }

  try {
    if (req.method === "POST") {
      // push：upsert
      const body = await req.json().catch(() => ({}));
      const r = await fetch(
        `${SUPABASE_URL}/rest/v1/sync_store?on_conflict=sync_id`,
        {
          method: "POST",
          headers: { ...authHeaders(), "Prefer": "resolution=merge-duplicates" },
          body: JSON.stringify({
            sync_id: syncId,
            payload: body.payload || {},
            updated_at: new Date().toISOString(),
          }),
        },
      );
      if (!r.ok) {
        const t = await r.text().catch(() => "");
        throw new Error("upsert " + r.status + " " + t.slice(0, 120));
      }
      return new Response(JSON.stringify({ ok: true, at: new Date().toISOString() }),
        { status: 200, headers: cors });
    }

    // GET：pull
    const r = await fetch(
      `${SUPABASE_URL}/rest/v1/sync_store?sync_id=eq.${encodeURIComponent(syncId)}&select=payload,updated_at`,
      { headers: authHeaders() },
    );
    if (!r.ok) {
      const t = await r.text().catch(() => "");
      throw new Error("select " + r.status + " " + t.slice(0, 120));
    }
    const rows = await r.json();
    if (!rows.length) {
      return new Response(JSON.stringify({ ok: true, empty: true }),
        { status: 200, headers: cors });
    }
    return new Response(JSON.stringify({
      ok: true, payload: rows[0].payload, at: rows[0].updated_at,
    }), { status: 200, headers: cors });

  } catch (e: any) {
    return new Response(JSON.stringify({ error: String(e?.message || e) }),
      { status: 500, headers: cors });
  }
});
