# 前端后端对接说明

前端会 POST 到两个同源路径。本地开发用反向代理，线上用 Supabase Edge Function。

## api/image  文生图
## api/detect AIGC 检测

推荐线上做法（Supabase Edge Function，无需绑卡）：
1. 把 backend/aigc-detect/index.ts 部署为 Edge Function
2. 前端 api/detect 改为指向 https://<ref>.functions.supabase.co/aigc-detect
