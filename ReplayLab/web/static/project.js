/* ReplayLab 二期 · 项目管理: golden录入 + 框点位画布。
   复用 app.js 顶层定义的 $(id) 与 api(url,opt)(全局词法环境共享)。 */

let PROJ_ITEMS = [], PROJ_VIDEOS = [], CUR_CFG = null, CUR_KEY = null;
// 框点位状态
let CTX = null, CIMG = null, CMETA = null;
let dragging = false, dStart = null, dRect = null;
const CVW = 960;  // canvas 显示宽(与抽帧 w 参数一致)

/* ---------- 项目列表 / 载入 ---------- */
async function loadProjItems() {
  PROJ_ITEMS = await api("/api/items");
  const sel = $("projSelect"); sel.innerHTML = "";
  PROJ_ITEMS.forEach(it => {
    const o = document.createElement("option");
    o.value = it.key; o.textContent = `${it.name} (${it.key})`;
    sel.appendChild(o);
  });
}

async function loadProject(key) {
  const r = await api("/api/item/" + key);
  if (r.error) { $("projHint").textContent = r.error; return; }
  CUR_KEY = key; CUR_CFG = r.config;
  $("projHint").textContent = "";
  fillEditor(CUR_CFG);
  $("projEditor").style.display = "block";
}

function fillEditor(cfg) {
  $("pName").value = cfg.name || "";
  $("pItemId").value = cfg.itemId ?? 0;
  $("pScoreField").value = cfg.score_field || "";
  $("pTimer").value = (cfg.timer === null || cfg.timer === undefined) ? "" : cfg.timer;
  $("pNeedStart").checked = !!cfg.need_start_sport;
  $("pVisitor").checked = !!cfg.visitor_auto_session;
  $("pTesters").value = (cfg.join && cfg.join.testers) || 8;
  const g = cfg.golden || {};
  $("pGType").value = g.type || "final";
  renderGolden(g);
  renderGrid8Info(cfg.grid8);
  // 重置框点位状态
  dRect = null; $("pApplyGrid8").disabled = true;
  $("pCropInfo").textContent = "未框选(选视频抽帧后拖框)";
}

/* ---------- golden 录入 ---------- */
function renderGolden(g) {
  const t = $("pGType").value;
  $("gFinal").style.display = t === "final" ? "flex" : "none";
  $("gPiece").style.display = t === "piecewise" ? "block" : "none";
  $("pGHint").textContent = t === "final"
    ? "计时计数类(跳绳/仰卧起坐等): 填8路各自的最终成绩"
    : "持续上涨类(开合跳等): 填分段点(秒,计数) + 循环帧数";
  if (t === "final") {
    const scores = g.scores || [];
    const box = $("pScores"); box.innerHTML = "";
    for (let i = 0; i < 8; i++) {
      const inp = document.createElement("input");
      inp.type = "number"; inp.value = scores[i] ?? 0; inp.title = "路" + i + " (areaIndex=" + i + ")";
      box.appendChild(inp);
    }
    $("pTotal").value = g.total ?? 0;
  } else {
    $("pLoop").value = g.loop_frames ?? 0;
    $("pPerLoop").value = g.total_per_loop ?? 0;
    $("pFps").value = g.fps ?? 30;
    const box = $("pPoints"); box.innerHTML = "";
    (g.points || []).forEach(p => addPointRow(p[0], p[1]));
  }
}

function addPointRow(t, c) {
  const row = document.createElement("div"); row.className = "point-row";
  const lt = document.createElement("label"); lt.textContent = "秒";
  const it = document.createElement("input"); it.className = "pt"; it.type = "number"; it.step = "0.5"; it.value = t ?? 0;
  const lc = document.createElement("label"); lc.textContent = "计数";
  const ic = document.createElement("input"); ic.className = "pc"; ic.type = "number"; ic.value = c ?? 0;
  const del = document.createElement("button"); del.className = "del"; del.textContent = "删";
  del.onclick = () => row.remove();
  row.append(lt, it, lc, ic, del);
  $("pPoints").appendChild(row);
}

/* ---------- 框点位画布 ---------- */
async function loadProjVideos() {
  PROJ_VIDEOS = await api("/api/videos");
  const sel = $("pVideo"); sel.innerHTML = "";
  PROJ_VIDEOS.forEach(v => {
    const o = document.createElement("option"); o.value = v.rel; o.textContent = v.name;
    sel.appendChild(o);
  });
}

async function loadFrame() {
  const rel = $("pVideo").value; if (!rel) return;
  $("pCropInfo").textContent = "抽帧中...";
  const meta = await api("/api/videometa?video=" + encodeURIComponent(rel));
  if (meta.error) { $("pCropInfo").textContent = meta.error; return; }
  CMETA = meta;
  const t = +$("pFrameT").value || 0;
  const img = new Image();
  img.onload = () => {
    CIMG = img;
    const cv = $("pCanvas");
    cv.width = CVW; cv.height = Math.round(CVW * img.height / img.width);
    CTX = cv.getContext("2d");
    dRect = null; $("pApplyGrid8").disabled = true; drawCanvas();
    $("pCropInfo").textContent = `原图 ${meta.width}x${meta.height} · 在图上拖框出单人有效区域`;
  };
  img.onerror = () => { $("pCropInfo").textContent = "抽帧失败(视频格式?)"; };
  img.src = "/api/frame?video=" + encodeURIComponent(rel) + "&t=" + t + "&w=" + CVW + "&_=" + Date.now();
}

function drawCanvas() {
  if (!CTX || !CIMG) return;
  const cv = $("pCanvas");
  CTX.drawImage(CIMG, 0, 0, cv.width, cv.height);
  if (dRect) {
    CTX.strokeStyle = "#2f6fed"; CTX.lineWidth = 2;
    CTX.strokeRect(dRect.x, dRect.y, dRect.w, dRect.h);
    CTX.fillStyle = "rgba(47,111,237,.15)";
    CTX.fillRect(dRect.x, dRect.y, dRect.w, dRect.h);
  }
}

function cvPos(e) {
  const cv = $("pCanvas"), r = cv.getBoundingClientRect();
  const sx = cv.width / r.width, sy = cv.height / r.height;  // CSS缩放补偿
  return { x: (e.clientX - r.left) * sx, y: (e.clientY - r.top) * sy };
}
function normRect(a, b) {
  return { x: Math.min(a.x, b.x), y: Math.min(a.y, b.y), w: Math.abs(a.x - b.x), h: Math.abs(a.y - b.y) };
}

function showCrop() {
  if (!dRect || !CMETA) return;
  const cv = $("pCanvas"), k = CMETA.width / cv.width;      // canvas -> 原图
  const x = Math.round(dRect.x * k), y = Math.round(dRect.y * k);
  const w = Math.round(dRect.w * k), h = Math.round(dRect.h * k);
  dRect.orig = { x, y, w, h };
  $("pCropInfo").textContent = `crop 原图: 宽${w} 高${h} @ (${x},${y})`;
}

$("pCanvas").addEventListener("mousedown", e => { if (!CIMG) return; dragging = true; dStart = cvPos(e); dRect = null; });
window.addEventListener("mousemove", e => {
  if (!dragging) return;
  dRect = normRect(dStart, cvPos(e)); drawCanvas(); showCrop();
});
window.addEventListener("mouseup", () => {
  if (!dragging) return; dragging = false;
  if (dRect && dRect.w > 8 && dRect.h > 8) $("pApplyGrid8").disabled = false;
});

/* ---------- 8格配置生成 ---------- */
function grid8Layouts() {
  const L = [];
  for (let r = 0; r < 2; r++) for (let c = 0; c < 4; c++) L.push([24 + c * 960, 45 + r * 1080]);
  return L;
}
$("pApplyGrid8").onclick = () => {
  if (!dRect || !dRect.orig || !CUR_CFG) return;
  const { x, y, w, h } = dRect.orig;
  const ratio = Math.min(920 / w, 1000 / h);                // fit cell 960x1080 留边距
  const sw = Math.round(w * ratio), sh = Math.round(h * ratio);
  CUR_CFG.grid8 = {
    crop: `${w}:${h}:${x}:${y}`, scale: `${sw}:${sh}`,
    canvas: "3840x2160", cell: [960, 1080], origin: [24, 45], inset_px: 10,
    layouts: grid8Layouts()
  };
  renderGrid8Info(CUR_CFG.grid8);
  $("pGrid8Info").textContent += " · 已生成(保存后生效)";
};
function renderGrid8Info(g) {
  $("pGrid8Info").textContent = g ? `当前8格: crop=${g.crop} scale=${g.scale}` : "未配置(将用整帧)";
}

/* ---------- 保存 / 新建 ---------- */
$("pSave").onclick = async () => {
  if (!CUR_CFG) return;
  CUR_CFG.name = $("pName").value.trim() || CUR_CFG.name;
  CUR_CFG.itemId = +$("pItemId").value || 0;
  CUR_CFG.score_field = $("pScoreField").value.trim() || "score";
  CUR_CFG.timer = $("pTimer").value === "" ? null : +$("pTimer").value;
  CUR_CFG.need_start_sport = $("pNeedStart").checked;
  CUR_CFG.visitor_auto_session = $("pVisitor").checked;
  CUR_CFG.join = CUR_CFG.join || {};
  CUR_CFG.join.testers = +$("pTesters").value || 8;
  const t = $("pGType").value;
  const g = CUR_CFG.golden || {};
  g.type = t;
  if (t === "final") {
    g.scores = Array.from($("pScores").querySelectorAll("input")).map(i => +i.value || 0);
    g.total = +$("pTotal").value || g.scores.reduce((a, b) => a + b, 0);
    g.round_sec = CUR_CFG.timer;
  } else {
    g.points = Array.from($("pPoints").querySelectorAll(".point-row"))
      .map(r => [+r.querySelector(".pt").value || 0, +r.querySelector(".pc").value || 0]);
    g.loop_frames = +$("pLoop").value || 0;
    g.total_per_loop = +$("pPerLoop").value || 0;
    g.fps = +$("pFps").value || 30;
  }
  CUR_CFG.golden = g;
  $("pSaveHint").textContent = "保存中...";
  const r = await api("/api/item/save", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key: CUR_KEY, config: CUR_CFG })
  });
  $("pSaveHint").textContent = r.ok ? "已保存 ✓ (部署/测试即生效)" : (r.error || "保存失败");
  if (r.ok) { loadProjItems(); if (typeof loadItems === "function") loadItems(); }
};

$("projNew").onclick = async () => {
  const key = prompt("新项目 key(英文/数字/下划线, 如 gaotuitui):"); if (!key) return;
  const name = prompt("项目名称(中文):") || key;
  const itemId = +prompt("itemId(数字):") || 0;
  const score_field = prompt("计数字段(score / ropeScore / ...):") || "score";
  const timerS = prompt("timer 秒(计时项目填, 否则留空):");
  const need_start_sport = confirm("是否需要 startSport?(计时类通常需要)");
  const golden_type = confirm("golden 类型:\n确定 = final(计时计数)\n取消 = piecewise(时间曲线)") ? "final" : "piecewise";
  const r = await api("/api/item/create", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key, name, itemId, score_field, timer: timerS === "" ? null : +timerS, need_start_sport, golden_type })
  });
  if (r.ok) {
    await loadProjItems(); $("projSelect").value = key; loadProject(key);
    if (typeof loadItems === "function") loadItems();
  } else alert(r.error || "创建失败");
};

/* ---------- 事件 & 初始化 ---------- */
$("projSelect").onchange = () => loadProject($("projSelect").value);
$("pGType").onchange = () => renderGolden({ type: $("pGType").value });
$("pAddPoint").onclick = () => addPointRow(0, 0);
$("pLoadFrame").onclick = loadFrame;

(async () => {
  await loadProjItems();
  await loadProjVideos();
  if (PROJ_ITEMS.length) { $("projSelect").value = PROJ_ITEMS[0].key; loadProject(PROJ_ITEMS[0].key); }
})();
