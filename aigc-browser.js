/* ════════════════════════════════════════════════════
   浏览器端 AIGC 检测（zhv3 模型，纯本地推理）
   - 模型在用户浏览器里跑，稿子不经过任何服务器
   - 需要先加载 transformers.js + ONNX 模型
   ════════════════════════════════════════════════════ */
const AIGC = {
  libUrl: "https://cdn.jsdelivr.net/npm/@xenova/transformers@2.17.2",
  // 模型文件放我们自己的服务器（国内拉取快；HuggingFace 在部分网络下不可达）
  modelBase: "https://lwl555.github.io/wxhot-studio/aigc-model/",
  files: {
    "onnx/model_quantized.onnx": "model_quantized.onnx",
    "tokenizer.json": "tokenizer.json",
    "config.json": "config.json",
  },
  loaded: false,
  loading: false,
  pipeline: null,
  progress: 0,
};

/* 加载引擎 + 模型（首次约 98MB，之后走浏览器缓存） */
async function loadAIGC(onProgress) {
  if (AIGC.loaded) return true;
  if (AIGC.loading) return false;
  AIGC.loading = true;

  try {
    // 注入 transformers.js
    if (!window.transformers) {
      await new Promise((res, rej) => {
        const s = document.createElement("script");
        s.src = AIGC.libUrl + "/dist/transformers.min.js";
        s.onload = res;
        s.onerror = () => rej(new Error("检测引擎加载失败（jsDelivr 不可达）"));
        document.head.appendChild(s);
      });
    }
    const { pipeline, env } = window.transformers;
    env.allowLocalModels = false;
    env.useBrowserCache = true;

    const files = {};
    for (const [k, v] of Object.entries(AIGC.files)) files[k] = AIGC.modelBase + v;

    AIGC.pipeline = await pipeline("text-classification", "custom", {
      quantized: true,
      files,
      progress_callback: (p) => {
        if (p.status === "progress" && p.total) {
          AIGC.progress = Math.round((p.loaded / p.total) * 100);
          onProgress && onProgress(AIGC.progress, p.file || "");
        } else if (p.status === "ready") {
          onProgress && onProgress(100, "就绪");
        }
      },
    });
    AIGC.loaded = true;
    return true;
  } catch (e) {
    console.error("AIGC 加载失败", e);
    onProgress && onProgress(-1, e.message);
    throw e;
  } finally {
    AIGC.loading = false;
  }
}

/* 检测单段（≤512 tokens） */
async function detectSegment(text) {
  if (!AIGC.loaded) throw new Error("模型还没加载完");
  const out = await AIGC.pipeline(text, { top_k: 2 });
  // 输出形如 [{label, score}, ...]，label 含 Human_Written / AI_Generated
  let ai = 0, hu = 0;
  for (const r of out) {
    if (/ai/i.test(r.label) && !/human/i.test(r.label)) ai = r.score;
    else hu = r.score;
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

  // 汇总（按有效段加权平均）
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
