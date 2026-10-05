-- 手机 ↔ PC 同步：建表
-- 用法：Supabase Dashboard → SQL Editor → 粘贴执行（免费档，免绑卡）
--
-- 这张表只存同步中转的数据（当前文章 / 仿写稿 / 助手记忆），
-- 每个 sync_id 一条，新的覆盖旧的。

create table if not exists sync_store (
  sync_id    text primary key,
  payload    jsonb       not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

-- 允许匿名访问（前端用 anon key 直连）
alter table sync_store enable row level security;

-- 策略：任何人都能读写自己知道 sync_id 的那一行
-- （sync_id 相当于一个共享密钥，知道码就能同步——这是刻意的设计，别用敏感内容当码）
drop policy if exists "sync_all" on sync_store;
create policy "sync_all" on sync_store
  for all
  using (true)
  with check (true);

-- 自动清理 7 天没动过的（省空间）
-- 可选：Supabase 免费档有 500MB，这点数据完全够
-- delete from sync_store where updated_at < now() - interval '7 days';

-- 验证：执行下面这行应该返回 0 行且不报错
-- select * from sync_store limit 1;
