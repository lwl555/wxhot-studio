/* ════════════════════════════════════════════════════
   浏览器端 AIGC 检测（zhv3 模型，纯本地推理）
   - 模型在用户浏览器里跑，稿子不经过任何服务器
   - transformers.js v2.17.2：所有模型文件通过 env.remoteHost +
     env.remotePathTemplate 拼接 URL（无 per-file 覆盖、无 files 选项），
     所以把 remoteHost 指向我们自己的服务器即可彻底绕开 HuggingFace。
   ════════════════════════════════════════════════════ */

// 全部自托管在 GitHub Pages 上（jsDelivr 在大陆经常不可达，曾导致检测加载失败）
const AIGC = {
  // 【踩坑记录】wasm 文件的真实目录是 vendor/tfjs/，不是 vendor/tfjs/dist/。
  // 之前写成 libBase + "/dist/" 导致 ort-wasm.wasm 404 → ONNX 引擎初始化失败
  // → 检测完全跑不起来（表现就是"点了没反应/检测失败"）。
  esmUrl: "https://lwl555.github.io/wxhot-studio/vendor/tfjs/transformers.min.js",
  libBase: "https://lwl555.github.io/wxhot-studio/vendor/tfjs/",
  // 模型根目录（HF 目录结构：<root>/custom/resolve/main/...）
  modelBase: "https://lwl555.github.io/wxhot-studio/aigc-model/",

  // 备选引擎源：自托管挂了/被墙时回退到公共 CDN（transformers.js 是公开 npm 包）
  esmFallback: [
    "https://cdn.jsdelivr.net/npm/@xenova/transformers@2.17.2",
    "https://unpkg.com/@xenova/transformers@2.17.2",
  ],
  loaded: false,
  loading: false,
  pipeline: null,
  srcName: "",           // 当前实际生效的引擎源，便于排查
};

/* 探测模型文件是否可达 + 预估下载耗时。
   模型 103MB，走 GitHub Pages 常年在 300KB/s~1MB/s，首次要几分钟；
   不先说清楚，用户会以为卡死而中途关掉，那这次下载就白费了。 */
async function probeAIGCModel(onTip) {
  const url = AIGC.modelBase + "custom/resolve/main/onnx/model_quantized.onnx";
  try {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 8000);
    const t0 = performance.now();
    const r = await fetch(url, {
      method: "GET",
      headers: { Range: "bytes=0-1048576" },   // 先拉 1MB 测速
      signal: ctrl.signal,
    });
    clearTimeout(timer);
    if (!r.ok && r.status !== 206) return { ok: false, why: `模型文件返回 HTTP ${r.status}` };
    const buf = await r.arrayBuffer();
    const sec = (performance.now() - t0) / 1000;
    const bytesPerSec = buf.byteLength / sec;
    const totalMB = 103;
    const estSec = Math.round((totalMB * 1024 * 1024) / bytesPerSec);
    const est = estSec > 90 ? `约 ${Math.ceil(estSec / 60)} 分钟` : `约 ${estSec} 秒`;
    onTip && onTip(est, Math.round(bytesPerSec / 1024));
    return { ok: true, est, kbps: Math.round(bytesPerSec / 1024) };
  } catch (e) {
    return { ok: false, why: "模型文件连不上（网络被墙或 GitHub Pages 不可达）" };
  }
}

/* 加载引擎 + 模型（首次约 100MB，之后走浏览器缓存） */
async function loadAIGC(onProgress) {
  if (AIGC.loaded) return true;
  if (AIGC.loading) return false;
  AIGC.loading = true;

  try {
  const errorList = [];
  // 逐个尝试引擎源：自托管优先，失败自动回退公共 CDN
  const esmSources = [AIGC.esmUrl, ...AIGC.esmFallback];
  for (const esmUrl of esmSources) {
    try {
      // transformers.js v2 是 ESM，普通 <script> 里用 new Function + import() 动态加载
      const mod = await (new Function("u", "return import(u)"))(esmUrl);
      const { pipeline, env } = mod;

      env.allowLocalModels = false;
      env.useBrowserCache = true;      // 已下载的模型走缓存，二次打开秒开
      // 关键：把所有模型文件请求重定向到我们自己的服务器，绕开 HuggingFace（本机不可达）
      env.remoteHost = AIGC.modelBase;
      env.remotePathTemplate = "{model}/resolve/{revision}/";
      // 【修正】wasm 就在 vendor/tfjs/ 根目录，不要再拼 dist/（拼了会 404 → 检测起不来）
      env.backends.onnx.wasm.wasmPaths = AIGC.libBase;

      AIGC.pipeline = await pipeline("text-classification", "custom", {
        quantized: true,
        progress_callback: (p) => {
          if (p.status === "progress" && p.total) {
            onProgress && onProgress(Math.round((p.loaded / p.total) * 100), p.file || "");
          } else if (p.status === "ready") {
            onProgress && onProgress(100, "就绪");
          }
        },
      });
      AIGC.srcName = esmUrl.includes("github.io") ? "自托管(GitHub Pages)" : "公共CDN";
      AIGC.loaded = true;
      return true;
    } catch (e) {
      console.error("AIGC 加载失败（源：" + esmUrl + "）", e);
      errorList.push(`${esmUrl.includes("github.io") ? "自托管" : "CDN"}：${e.message || e}`);
      // 换下一个源继续试
    }
  }
  const err = new Error("所有引擎源都加载失败。\n" + errorList.join("\n"));
  onProgress && onProgress(-1, err.message);
  throw err;
  } finally {
    AIGC.loading = false;   // 失败也必须复位，否则下次永远卡在"加载中"
  }
}

/* 检测单段（≤512 tokens） */
async function detectSegment(text) {
  if (!AIGC.loaded) throw new Error("模型还没加载完");
  const out = await AIGC.pipeline(text, { top_k: 2 });
  // 输出形如 [{label, score}, ...]，label 来自 config.id2label
  let ai = 0, hu = 0;
  for (const r of out) {
    if (/AI/i.test(r.label) && !/human/i.test(r.label)) ai = r.score;
    else if (/human/i.test(r.label)) hu = r.score;
    else ai = Math.max(ai, r.score); // 兜底：LABEL_1 之类，取较高者
  }
  return { ai: Math.round(ai * 100), human: Math.round(hu * 100) };
}

/* 长文分段检测：按句子聚合到 ~300 字一段，逐段查再汇总 */
async function detectLongText(fullText, onSeg) {
  const clean = String(fullText || "")
    .replace(/\[配图:[^\]]+\]/g, "")        // 去掉配图标记
    .replace(/\s+/g, " ")
    .trim();
  if (clean.length < 50) throw new Error("文本太短（至少 50 字）");

  // 分句后按 ~300 字打包
  const sentences = clean.split(/(?<=[。！？!?；;])/);
  const segs = [];
  let buf = "";
  for (const s of sentences) {
    if ((buf + s).length > 300 && buf) { segs.push(buf.trim()); buf = s; }
    else buf += s;
  }
  if (buf.trim()) segs.push(buf.trim());

  const results = [];
  for (let i = 0; i < segs.length; i++) {
    const t = segs[i];
    if (t.length < 20) { results.push({ text: t, ai: 0, skip: true }); continue; }
    const r = await detectSegment(t);
    results.push({ text: t, ai: r.ai });
    onSeg && onSeg(i + 1, segs.length, r.ai);
  }

  // 汇总（有效段平均）
  const valid = results.filter(x => !x.skip);
  const overall = valid.length
    ? Math.round(valid.reduce((s, x) => s + x.ai, 0) / valid.length)
    : 0;
  return { overall, segments: results, totalSegs: segs.length };
}

/* 渲染检测结果到页面 */
function renderAIGCResult(data) {
  const lv = data.overall >= 70
    ? { t: "AI 味很重", c: "var(--red)" }
    : data.overall >= 40
      ? { t: "AI 味偏中等", c: "#b45309" }
      : { t: "人味充足", c: "var(--green)" };

  const segs = data.segments.filter(x => !x.skip);
  const hot = segs.filter(x => x.ai >= 60).length;

  $("#detOut").innerHTML = `
    <div class="det-sum">
      <div class="det-sc" style="color:${lv.c}">${data.overall}<small>%</small></div>
      <div class="det-meta">
        <div class="det-lv" style="color:${lv.c}">${lv.t}</div>
        <div class="det-eng">浏览器本地检测 · zhv3 中文模型 · 稿子不外传</div>
      </div>
    </div>
    <div class="det-legend">
      <span>共 ${data.totalSegs} 段，其中 <b style="color:var(--red)">${hot} 段</b>AI 味重（≥60%）</span>
    </div>
    <div class="det-segs">
      ${segs.map((s, i) => `
        <div class="det-seg ${s.ai >= 70 ? "ai" : s.ai >= 40 ? "suspect" : ""}">
          <div class="det-seg-h">
            <span class="det-badge">${s.ai >= 70 ? "AI 重" : s.ai >= 40 ? "疑似" : "人味"}</span>
            <span class="det-cf">${s.ai}%</span>
          </div>
          <div class="det-tx">${esc(s.text.slice(0, 130))}${s.text.length > 130 ? "…" : ""}</div>
        </div>`).join("")}
    </div>
    <div class="note info" style="margin-top:14px">
      <b>怎么用这结果</b>：标红/标黄的段落建议改写。检测仅供参考，不是权威机构结论；
      模型每次最多读约 350 字，所以长文是分段查的。
    </div>`;
}
