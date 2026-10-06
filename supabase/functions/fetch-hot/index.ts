// Supabase Edge Function：实时采集热榜
// 作用：让网页端「手动刷新」真正抓到最新数据（静态站无法跑 Python）
// 部署：supabase functions deploy fetch-hot
// 免费档免绑卡。tophub.today 公开、免 key。

const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";

// 返回北京时区时间字符串（不能直接用 toISOString，那是 UTC，会比本地少 8 小时）
function beijingNow(): string {
  const d = new Date(Date.now() + 8 * 3600 * 1000);
  return d.toISOString().slice(0, 19).replace("T", " ");
}

// (节点ID, 平台, 榜单名, 分类)
// 全部节点均已实测可抓到数据（2026-10-06）
const NODES: [string, string, string, string][] = [
  ["WnBe01o371", "微信", "微信24h热文榜", "公众号爆文"],
  ["W1VdJPZoLQ", "微信", "微信今日视频榜", "视频爆款"],
  ["KMZd7VOvrO", "知乎", "知乎日报Today", "知乎"],
  ["mproPpoq6O", "知乎", "知乎热榜", "知乎"],
  ["KqndgxeLl9", "微博", "微博热搜榜", "微博"],
  ["x9ozB4KoXb", "今日头条", "今日头条头条热榜", "头条"],
  ["Jb0vmloB1G", "百度", "百度实时热点", "社会热点"],
  ["Om4ejxvxEN", "百度贴吧", "百度贴吧热议榜", "社区热议"],
  ["DpQvNABoNE", "抖音", "抖音总榜", "短视频"],
  ["74KvxwokxM", "哔哩哔哩", "哔哩哔哩全站日榜", "视频爆款"],
  ["Q1Vd5Ko85R", "36氪", "36氪24小时热榜", "科技"],
  ["5VaobgvAj1", "虎嗅网", "虎嗅网热文", "科技"],
  ["wWmoO5Rd4E", "澎湃", "澎湃热榜", "时政社会"],
  ["DOvnNz1vEB", "机器之心", "机器之心", "AI科技"],
  ["MZd7azPorO", "量子位", "量子位", "AI科技"],
  ["Y2KeDGQdNP", "少数派", "少数派热门文章", "数码效率"],
  ["4KvxEX0dkx", "微信读书", "微信读书总榜", "书单"],
  ["mDOvnyBoEB", "豆瓣", "豆瓣电影新片榜", "影视娱乐"],
];

const CATEGORY_RULES: [string, string[]][] = [
  ["科技数码", ["苹果","华为","小米","特斯拉","芯片","AI","人工智能","手机","电脑","模型","算法","机器人","程序员","互联网","卫星","火箭","SpaceX"]],
  ["财经理财", ["股","黄金","房价","楼市","银行","存款","利率","基金","经济","GDP","央行","汇率","投资","负债","赚钱","工资","补贴"]],
  ["社会热点", ["通报","警方","事故","遇难","官方","回应","调查","处罚","判决","起诉","教育局","医院","食品","安全"]],
  ["娱乐影视", ["电影","电视剧","明星","演唱会","综艺","票房","官宣","剧组","演员","导演","开播","杀青","收视"]],
  ["体育赛事", ["亚运","奥运","世界杯","比赛","夺冠","金牌","球队","球员","足球","篮球","冠军","决赛"]],
  ["健康养生", ["医生","医院","疾病","养生","血压","血糖","体检","寿命","睡眠","饮食","中医"]],
  ["情感心理", ["情感","婚姻","离婚","恋爱","爱情","家庭","婆媳","中年","焦虑","内耗","emo","孤独"]],
  ["职场成长", ["职场","工作","打工","老板","同事","辞职","offer","面试","简历","副业","35岁"]],
];

function guessCat(title: string): string {
  for (const [cat, kws] of CATEGORY_RULES) {
    if (kws.some(k => title.includes(k))) return cat;
  }
  return "社会热点";
}

function stripTags(s: string): string {
  return s.replace(/<[^>]+>/g, "").replace(/&amp;/g, "&").replace(/&quot;/g, '"')
    .replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&nbsp;/g, " ").trim();
}

function toReads(s: string): number {
  s = s.trim();
  if (s.endsWith("万")) return Math.round(parseFloat(s.slice(0, -1)) * 10000);
  if (/^\d+$/.test(s)) return parseInt(s, 10);
  return 0;
}

async function fetchNode(id: string, platform: string, board: string, cat: string) {
  try {
    const r = await fetch(`https://tophub.today/n/${id}`, {
      headers: { "User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9" },
    });
    if (!r.ok) return [];
    const page = await r.text();
    const rows = page.match(/<tr[^>]*>[\s\S]*?<\/tr>/g) || [];
    const out: any[] = [];
    let i = 0;

    for (const row of rows) {
      // 图片型节点用 div 包 a，文本型直接 td 包 a
      const a =
        row.match(/<a[^>]+href="(https?:\/\/mp\.weixin\.qq\.com\/s[^"]+)"[^>]*>([\s\S]*?)<\/a>/) ||
        row.match(/<a[^>]+href="(https?:\/\/[^"]+)"[^>]*>([\s\S]*?)<\/a>/);
      if (!a) continue;
      const url = a[1];
      const title = stripTags(a[2]);
      if (!title || title.length < 2) continue;

      // 阅读量：ws 类（微信热文榜）
      const w = row.match(/<td class="ws">([^<]+)<\/td>/);
      const readText = w ? w[1].trim() : "";
      const reads = toReads(readText);
      const hasReal = /^\d+(\.\d+)?万?$/.test(readText) && readText !== "";

      // 封面
      const cm = row.match(/<img[^>]+src="(https?:\/\/[^"]+)"[^>]*>/);

      out.push({
        id: hashUrl(url),
        title,
        url: url.split("&amp;").join("&"),
        platform,
        board,
        category: platform === "微信" ? cat : guessCat(title),
        readCount: reads,
        readCountText: readText || "—",
        hasRealRead: hasReal,
        rank: i + 1,
        cover: cm ? cm[1] : "",
        collectedAt: beijingNow(),
      });
      i++;
    }
    return out;
  } catch {
    return [];
  }
}

function hashUrl(u: string): string {
  let h = 0;
  for (let i = 0; i < u.length; i++) h = (h * 31 + u.charCodeAt(i)) >>> 0;
  return h.toString(16).padStart(8, "0");
}

Deno.serve(async (req: Request) => {
  const cors = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "content-type,authorization",
    "Access-Control-Allow-Methods": "GET,OPTIONS",
    "Content-Type": "application/json",
  };
  if (req.method === "OPTIONS") return new Response(null, { headers: cors });

  try {
    // 抓所有节点（并发）
    const results = await Promise.all(NODES.map(n => fetchNode(...n)));
    const arts = results.flat();

    // 去重（按 id）
    const seen = new Set<string>();
    const uniq = arts.filter(a => {
      if (seen.has(a.id)) return false;
      seen.add(a.id);
      return true;
    });

    // 按时间：新→旧，同一节点内保持榜单排名
    uniq.sort((a, b) => (b.collectedAt || "").localeCompare(a.collectedAt || ""));

    return new Response(JSON.stringify({
      articles: uniq,
      updatedAt: beijingNow(),
      source: "tophub.today（实时）",
      count: uniq.length,
      realRead: uniq.filter(a => a.hasRealRead).length,
    }), { status: 200, headers: cors });
  } catch (e: any) {
    return new Response(JSON.stringify({ error: String(e?.message || e) }),
      { status: 500, headers: cors });
  }
});
