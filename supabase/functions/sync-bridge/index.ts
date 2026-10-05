// Supabase Edge Function：手机 ↔ PC 同步中转
// 部署：supabase functions deploy sync-bridge
// 免费档，免绑卡。前端用 anon key 直连（无需新增凭证）。
//
// 设计（按用户要求：按需连接，不常连）
//   - 本函数是无状态的：只在收发数据时被调用，不维持长连接
//   - 每个设备有个 syncId（自己起个名字，如 "pc-家里的" / "手机"）
//   - pull: 取对方推上来的最新数据
//   - push: 把自己的数据推上去，供对方拉取
//
// 存储：用 Supabase 表 sync_store (sync_id text primary key, payload jsonb, updated_at timestamptz)

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "content-type,authorization,x-sync-id",
  "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
  "Content-Type": "application/json",
};

function db() {
  if (!SUPABASE_URL || !SERVICE_KEY) return null;
  return createClient(SUPABASE_URL, SERVICE_KEY);
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response(null, { headers: cors });

  const url = new URL(req.url);
  const syncId = req.headers.get("x-sync-id") || url.searchParams.get("id") || "";

  if (!syncId) {
    return new Response(JSON.stringify({ error: "缺少 syncId（用 x-sync-id 头或 ?id=）" }),
      { status: 400, headers: cors });
  }

  const c = db();
  if (!c) {
    return new Response(JSON.stringify({
      error: "服务端未配置 SUPABASE_SERVICE_ROLE_KEY",
      hint: "Edge Function 里 SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY 是自动注入的，通常无需手动设置",
    }), { status: 500, headers: cors });
  }

  try {
    if (req.method === "POST") {
      // push：把 payload 存起来（upsert）
      const body = await req.json();
      const { error } = await c.from("sync_store").upsert({
        sync_id: syncId,
        payload: body.payload || {},
        updated_at: new Date().toISOString(),
      }, { onConflict: "sync_id" });
      if (error) throw new Error(error.message);
      return new Response(JSON.stringify({ ok: true, at: new Date().toISOString() }),
        { status: 200, headers: cors });
    }

    // GET：pull
    const { data, error } = await c.from("sync_store")
      .select("payload,updated_at").eq("sync_id", syncId).maybeSingle();
    if (error) throw new Error(error.message);
    if (!data) return new Response(JSON.stringify({ ok: true, empty: true }),
      { status: 200, headers: cors });
    return new Response(JSON.stringify({
      ok: true, payload: data.payload, at: data.updated_at,
    }), { status: 200, headers: cors });

  } catch (e: any) {
    return new Response(JSON.stringify({ error: String(e?.message || e) }),
      { status: 500, headers: cors });
  }
});
