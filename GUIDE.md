# 复用指引：搭「真实热榜 + AI 仿写」类平台

> 来源：2026-10-04 实做「热文创作台」总结。这套打法可以直接复用到任何"热榜聚合 + AI 创作"类项目。

---

## 一、数据源：真实阅读量怎么拿到（最关键）

**结论先说：微信官方接口 2025 年底已关闭，搜狗微信失效，市面上宣称"免费真实阅读量"的方案基本都不成立。**

### 实测结论表

| 源 | 状态 | 说明 |
|---|---|---|
| **tophub.today** | ✅ 可用 | **推荐**。免费、免 key、含真实阅读量、每日更新 |
| 红狐 redfox.hk | ⚠️ 需 key | 22 分类 10w+ 数据，字段最全，但不带 key 返回 500 |
| 天聚 wxhotarticle | ❌ 已下线 | 接口返回 `{"code":110,"msg":"当前API已下线"}` |
| 聚合数据 juhe | ⚠️ 需付费 | 接口通，有免费额度，只有热搜词无阅读量 |
| 搜狗微信搜索 | ⚠️ 半废 | 能返回文章列表，但**无阅读量**，且有 antispider 风险 |
| 微榜 wempapp.com | ❌ DNS 解析失败 | 域名已挂 |

### tophub 可用节点 ID（实测抓通）

```
微信24h热文榜    WnBe01o371    30 篇   ✅ 带真实阅读量
微博热搜榜      KqndgxeLl9    50 条   热度值
今日头条头条榜  x9ozB4KoXb    50 条   热度值
知乎日报Today   KMZd7VOvrO     4 条   热度值
虎嗅网热文      5VaobgvAj1    15 条   热度值
36氪24小时热榜  Q1Vd5Ko85R     8 条   热度值
```

板块入口：`/c/wxmp`（公众号）、`/c/tech`、`/c/news`、`/c/ai`

### ⚠️ tophub 有两种 HTML 结构，必须都支持

这是踩过的坑——图片型节点和文本型节点结构不同，只写一种会漏掉一半数据：

```python
# 文本型（微博/头条）→ <td><a>
r'<td><a href="(https?://[^"]+)"[^>]*>(.*?)</a>'

# 图片型（知乎/36氪/虎嗅）→ <td class="al"><div><a>...</a></div>
r'<div><a href="(https?://[^"]+)"[^>]*>(.*?)</a></div>'
```

正确写法（兼容两者）：
```python
a = re.search(r'<div><a href="(https?://[^"]+)"[^>]*>(.*?)</a></div>', row, re.S) \
    or re.search(r'<td><a href="(https?://[^"]+)"[^>]*>(.*?)</a>', row, re.S)
```

配套字段：
- 阅读量：`<td class="ws">10.0万</td>` → 需把"万"换算成整数
- 封面图：`<img src="...">`
- 摘要：`<div class="item-desc">...</div>`

防坑：`tophub.today` 首页返回 1.1MB 但用 curl 写文件会被沙箱挡，直接用 Python `urlopen` 读。

---

## 二、UI 规范（用户审美偏好，务必遵守）

用户明确说过：**讨厌花哨**。玻璃拟态、紫粉渐变、发光动画都被评过"不好看"。

**简约商务风标准：**
```
底色    #ffffff / #f9fafb
主色    #1d4ed8（商务蓝）
边框    #e5e7eb
文字    #111827 / #4b5563 / #9ca3af
圆角    8px（小）/ 12px（卡片）
阴影    几乎不用，用边框代替层次
```
禁止：渐变、发光、玻璃拟态、紫粉配色、大圆角、emoji 装饰。

---

## 三、AI 仿写：去 AI 味的正确做法

**关键认知：不是"事后洗稿"，而是"事前约束 AI 别写什么"。**

我在 prompt 里显式禁止这些，效果实测非常好（生成的稿子 AI 腔调词命中数为 0）：

```
禁止开头用"随着""众所周知""近年来"这类套话
禁止每段结尾都升华或总结
禁止用"值得注意的是""不难发现""综上"这类连接词
要求段落长短交错，不要整齐划一
允许口语、短句、语气词
```

风格维度设计（这几档实测效果好）：
`贴近原文` / `反角度对立` / `深度挖掘` / `故事化叙事` / `干货清单体`

"故事化叙事"效果最好——会自然写出具体人物名、生活细节、留白结尾。

### Agnes 代理调用要点

```
URL:  https://<ref>.functions.supabase.co/agnes-proxy/v1/chat/completions
模型: agnes-2.0-flash
```
- ⚠️ 路径必须带 `/v1/chat/completions` 后缀，POST 到根路径返回 405
- ⚠️ 免费档约 1 分钟 20 次，连测会 429，**测试时别连打**
- 单次约 12s / 2000 字，非流式
- 直连官方用 `api.agnes-ai.cn`（不是 `apihub.agnes-ai.com`，后者 401）

---

## 四、AIGC 检测

- 腾讯朱雀开源 CLI：`Sophomoresty/zhuque`（MIT），文本+图片，按段落给判定
- ⚠️ 限流极狠：单 IP 约 36 次/小时、785 次/天，冷却约 30 分钟
- **必须有降级方案**：静态站跑不了 Python，所以要写个前端启发式兜底
  - 统计 AI 腔调词密度 + 句长均匀度（方差 < 40 视为"过于整齐"）
  - ⚠️ 必须诚实标注"此为启发式结果，不等同于朱雀"，别糊弄用户

---

## 五、验证方法（这套很顺手）

**agent-browser 在 Windows 沙箱里起不来**（daemon 卡死、command not found）。改用 **playwright-core + 已下载的 Chrome**：

```js
// Chrome 路径注意：少一层 chrome-win64 目录
const CHROME = 'C:/Users/<user>/.agent-browser/browsers/chrome-<ver>/chrome.exe';
const browser = await chromium.launch({ executablePath: CHROME, args: ['--no-sandbox'] });
```
安装：`npm install playwright-core`，浏览器用 `agent-browser install` 装好后复用其下载的 Chrome。

验证脚本要覆盖：统计卡数值 → 卡片数量 → 筛选是否真生效 → 点开抽屉 → 四个标签页可见性 → 兜底逻辑 → 空状态。截图存 `shots/` 供人工复核。

**注意**：抽屉打开时遮罩 `#ov` 会拦截导航栏点击，脚本里要先点 `#dClose` 再切页——这是正常交互不是 bug。

---

## 六、部署

- 前端纯静态 → GitHub Pages
- 后端（文生图/检测）→ 本地或轻量 VPS，或 Supabase Edge Function 代理转发
- **务必加 GitHub Actions 每日自动跑采集**，否则数据文件会过期：
  ```yaml
  on:
    schedule: [{ cron: "17 9 * * *" }]
  ```

---

## 七、可复用的开源项目

| 项目 | 星 | 用途 | 许可 |
|---|---|---|---|
| `iniwap/AIWriteX` | 2046 | 公众号全自动 AI 工具，含去 AI 味引擎 | Apache-2.0 |
| `Sophomoresty/zhuque` | 78 | 腾讯朱雀 AIGC 检测 CLI | MIT |
| `wechat-article-exporter` | 13k | 公众号文章批量导出（含阅读量，需扫码登录） | MIT |
| `redfox-data/redfox-community` | 422 | 22 分类 10w+ 热文数据（需申请 key） | — |

调研时用这些关键词组合搜索最快：`GitHub 微信热榜 聚合 阅读量`、`开源 AIGC 检测 朱雀`、`公众号 AI 仿写 洗稿`。

---

## 八、常见 bug 清单

1. **筛选按钮没绑事件** → `renderFilters()` 里重新渲染 innerHTML 会覆盖 onclick。必须在 `renderFilters` 内部重新绑定，或用事件委托。
2. **图片型 vs 文本型 HTML 结构不兼容** → 见上文第一节。
3. **`curl -o file` 被沙箱挡** → 改用 Python `urlopen` 直接读。
4. **正则 `<td>` 后缺 `<a>`** → 写成 `<td><a` 仍匹配不到 `<td class="al">`。
5. **429 误判成 key 无效** → Agnes 429 是限流不是鉴权失败，别往 key 上查。

### ⭐ 5.1 移动端 flex 塌陷（高频坑，务必记住）

**症状**：≤820px 时卡片文字被压成一列竖排（"微\n信"），"AI 仿写"压在标签中间，标题框宽度 = 0。

**根因**：媒体查询里写了 `.aim{width:100%}` 想让它独占一行，但**父级 `.card` 没开 `flex-wrap:wrap`**，所以 `.aim` 并没换行，而是和 `.bd` 抢同一行空间。`.bd` 是 `flex:1` + `min-width:0`，被挤到 0 宽，文字就按字竖排。

**正确修法**（几处一起改）：
```css
@media(max-width:820px){
  .card{flex-wrap:wrap}                          /* ← 关键：父级必须能换行 */
  .bd{flex:1 1 calc(100% - 26px - 72px - 12px)}  /* ← 显式给宽度，不靠 flex:1 被动分配 */
  .aim{margin-left:0;width:100%;order:3}          /* order 明确排到末尾 */
  .tag,.rd-n,.aim{white-space:nowrap}             /* 标签禁止竖排 */
  .aim{flex-shrink:0}
}
```

**排查方法（强烈推荐复用）**：写多宽度测量脚本，`for w of [1400,1100,946,900,820,700,600,480,380]`，每档量 `.card/.bd/.tt/.mt` 的 `getBoundingClientRect()`，判定标准 `bd.w < 200` 即塌陷。**比肉眼看截图快十倍**，能一次定位塌陷的精确宽度区间。

脚本已存于 `.tools/diag-layout.js`，改样式后直接跑一遍回归。

**顺带注意**：写移动端媒体查询时别顺手 `nav{display:none}`——用户手机上就切不了页了。应换行保留（`flex:1;text-align:center`）。

### 5.2 固定宽度面板的窄屏兜底
`width:min(920px,94vw)` 虽不溢出，但内部双列表单会挤。补一条 `@media(max-width:560px)`：抽屉改 `width:100vw`、`.row` 单列、`.dres` 竖排、`.imgs` 两列、`.tabs` 换行。
