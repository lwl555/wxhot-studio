# 热文创作台

真实热榜爆文 → AI 仿写 → 配图生成 → AIGC 检测，一条链路的公众号创作平台。

---

## 核心特点：阅读量是真的

微信官方接口 2025 年底已关闭，搜狗微信也失效了。市面上宣称"真实阅读量"的免费方案基本都不成立。

本平台的数据源是 **今日热榜（tophub.today）** 的公开节点，实测可用：

| 节点 | 内容 | 阅读量 |
|---|---|---|
| 微信24h热文榜 | 30 篇 | **真实阅读量，精确到个位**（如 `10.0万` `8534`） |
| 微博热搜榜 | 50 条 | 榜单热度值 |
| 今日头条头条热榜 | 50 条 | 榜单热度值 |
| 知乎日报Today | 4 条 | 榜单热度值 |
| 虎嗅网热文 | 15 条 | 榜单热度值 |
| 36氪24小时热榜 | 8 条 | 榜单热度值 |

全部**免费、免 API key、每日自动更新**。页面上带真实阅读量的卡片会标红显示，可一键筛选。

抓下来的每条数据都带 `mp.weixin.qq.com` 原文直链，点进去就是原文章。

---

## 功能

### 1. 热榜浏览
- 157 条图文热文，覆盖 6 个平台
- 按平台 / 分类双维度筛选
- 「只看真实阅读量」开关
- 顶部实时统计：收录数、带真实阅读量数、最高阅读、覆盖平台数

### 2. AI 仿写
点任意文章进入工作台，选风格后生成：

| 风格 | 说明 |
|---|---|
| 贴近原文 | 同题材换角度重写 |
| 反角度对立 | 站在相反立场，制造认知冲突 |
| 深度挖掘 | 补充原文没讲透的因果和背景 |
| 故事化叙事 | 用具体场景和人物切入 |
| 干货清单体 | 短句分点，去冗余 |

- 字数：800 / 1200 / 1800 / 2500
- 去 AI 味三档：强 / 中 / 轻
- 支持「换一版」重新生成
- 可存进「我的作品」（存本机 localStorage）

去 AI 味的做法是**约束 AI 别写什么**，而不是事后洗：
- 禁止"随着…的发展""众所周知""值得注意的是""不难发现"
- 禁止每段结尾都升华或总结
- 要求段落长短交错，不整齐划一
- 允许口语、短句、语气词

### 3. 配图生成
- 5 种风格：写实摄影 / 扁平插画 / 日系动漫 / 3D 渲染 / 水墨国风
- 3 种比例：16:9 正文插图 / 2.35:1 封面 / 1:1 方图
- 「自动写提示词」由 AI 根据文章标题生成英文提示词
- 未接后端时出占位图，明确标注哪个环节没通

### 4. AIGC 检测
- 接腾讯朱雀检测（开源 CLI），**分段**给 AI 生成概率，标红可疑段落
- 后端未接通时提供**前端启发式检测**兜底：统计 AI 腔调词密度 + 句长均匀度
- 诚实标注启发式结果不等同于朱雀，不糊弄

---

## 快速开始

```bash
# 1. 抓热榜数据
python fetch_hot.py

# 2. 本地预览
python -m http.server 8899
# 打开 http://127.0.0.1:8899
```

AI 仿写默认走已有的 Supabase Edge Function 代理（`agnes-proxy`），开箱即用。

---

## 后端服务（可选，两个功能需要）

静态站本身跑不了 Python，图生图和朱雀检测都要单独起服务。

### 图片生成

```bash
cd backend
set AGNES_API_KEY=你的key
python image_server.py      # http://127.0.0.1:8787
```

> 注意：Agnes 正确域名是 `api.agnes-ai.cn`（不是 `apihub.agnes-ai.com`，后者返回 401）。
> 免费档有速率限制，连发会 429，约 1 分钟冷却。脚本已内置 8 秒最小间隔。

### AIGC 检测

```bash
pip install "git+https://github.com/Sophomoresty/zhuque.git"
npm install -g jsdom          # zhuque 依赖
cd backend
python detect_server.py      # http://127.0.0.1:8000/check
```

> 朱雀限流很严：单 IP 约 36 次/小时、785 次/天。脚本已内置串行队列与自动冷却。
> 自用和小团队够用，要更高并发得上代理池。

### 前端对接

前端会请求同源的 `api/image` 和 `api/detect`。两种接法：

**A. 直接代理**（本地开发最简单）——建个反向代理把 `/api/*` 转到上面两个服务

**B. 走 Supabase**（部署上线用）——部署 `backend/aigc-detect/index.ts` 为 Edge Function，在 Dashboard 设 `ZHUQUE_URL` 和 `ZHUQUE_KEY` 环境变量：

```bash
supabase functions deploy aigc-detect
```

未接通时前端会明确告诉你"检测服务未接通"，并给出两个选项，而不是静默失败。

---

## 部署

前端是纯静态站，GitHub Pages 即可：

```bash
git init && git add -A
git commit -m "init"
git remote add origin git@github.com:<你的账号>/<仓库>.git
git push -u origin main
# 然后在仓库 Settings → Pages 选 main 分支
```

**建议加一个 GitHub Actions 每日自动更新数据**，否则 `data/articles.json` 会过期。
`.github/workflows/update-data.yml` 示例：

```yaml
name: update hot data
on:
  schedule: [{ cron: "17 9 * * *" }]
  workflow_dispatch:
jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: python fetch_hot.py
      - run: |
          git config user.name  github-actions
          git config user.email actions@github.com
          git add data/articles.json
          git commit -m "update $(date +%F)" || echo "no change"
          git push
```

---

## 文件结构

```
wxhot-studio/
├── index.html              # 平台本体（单文件，含全部前端逻辑）
├── fetch_hot.py            # 热榜采集器 → data/articles.json
├── data/
│   └── articles.json       # 采集产物（157 条）
└── backend/
    ├── image_server.py     # 文生图服务（:8787）
    ├── detect_server.py    # 朱雀检测封装（:8000）
    └── aigc-detect/
        └── index.ts        # Supabase Edge Function
```

---

## 开源参考

调研过程中发现几个值得知道的项目：

| 项目 | 用途 | 许可 |
|---|---|---|
| [iniwap/AIWriteX](https://github.com/iniwap/AIWriteX) | 2046★ 公众号全自动 AI 工具，去 AI 味引擎 | Apache-2.0 |
| [Sophomoresty/zhuque](https://github.com/Sophomoresty/zhuque) | 腾讯朱雀 AIGC 检测 CLI | MIT |
| [wechat-article-exporter](https://github.com/wechat-article/wechat-article-exporter) | 公众号文章批量导出（13k★） | MIT |
| [redfox-data/redfox-community](https://github.com/redfox-data/redfox-community) | 22 分类 10w+ 热文数据（需申请 key） | — |

`AIWriteX` 和本平台功能高度重叠，但它是 Python 全家桶、界面不是你要的风格。如果想要图形界面 + 完整发布链路，可以去用它。本平台专注"从热榜选题到成稿"这一段，界面完全按简约商务风做。
