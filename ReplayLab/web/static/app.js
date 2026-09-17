/* ReplayLab Web 前端逻辑 */
const $ = id => document.getElementById(id);
let ITEMS = [], VIDEOS = [], curTask = null, pollTimer = null, logLen = 0;

function fmtSize(b) {
  if (b >= 1e9) return (b / 1e9).toFixed(2) + " GB";
  if (b >= 1e6) return (b / 1e6).toFixed(1) + " MB";
  return (b / 1e3).toFixed(0) + " KB";
}
function fmtTime(ts) {
  const d = new Date(ts * 1000), p = n => String(n).padStart(2, "0");
  return `${d.getMonth() + 1}-${d.getDate()} ${p(d.getHours())}:${p(d.getMinutes())}`;
}
async function api(url, opt) { const r = await fetch(url, opt); return r.json(); }

/* ---- 项目 ---- */
async function loadItems() {
  ITEMS = await api("/api/items");
  const sel = $("itemSelect"); sel.innerHTML = "";
  ITEMS.forEach(it => {
    const o = document.createElement("option");
    o.value = it.key; o.textContent = `${it.name} (id=${it.itemId})`;
    sel.appendChild(o);
  });
  sel.onchange = showItemMeta; showItemMeta();
}
function showItemMeta() {
  const it = ITEMS.find(x => x.key === $("itemSelect").value); if (!it) return;
  $("itemMeta").textContent = `${it.score_field}${it.timer ? " · timer" + it.timer : ""}${it.need_start_sport ? " · 需startSport" : " · visitor"}`;
  $("grid8").disabled = !it.has_grid8;
  if (!it.has_grid8) $("grid8").checked = false;
}

/* ---- 视频库 ---- */
async function loadVideos() {
  VIDEOS = await api("/api/videos");
  const tb = $("videoList"); tb.innerHTML = "";
  VIDEOS.forEach(v => {
    const tr = document.createElement("tr");
    const td0 = document.createElement("td");
    const radio = document.createElement("input");
    radio.type = "radio"; radio.name = "video"; radio.value = v.rel;
    td0.appendChild(radio);
    const td1 = document.createElement("td"); td1.textContent = v.name;
    const td2 = document.createElement("td"); td2.textContent = fmtSize(v.size);
    const td3 = document.createElement("td"); td3.textContent = fmtTime(v.mtime);
    tr.append(td0, td1, td2, td3);
    tr.onclick = () => {
      radio.checked = true;
      document.querySelectorAll("#videoList tr").forEach(x => x.classList.remove("sel"));
      tr.classList.add("sel");
    };
    tb.appendChild(tr);
  });
}

$("uploadBtn").onclick = async () => {
  const f = $("uploadFile").files[0];
  if (!f) { $("uploadHint").textContent = "请先选择文件"; return; }
  const fd = new FormData(); fd.append("file", f);
  $("uploadHint").textContent = "上传中(大文件请稍候)...";
  const r = await api("/api/upload", { method: "POST", body: fd });
  $("uploadHint").textContent = r.ok ? `已上传 ${r.name} (${fmtSize(r.size)})` : (r.error || "失败");
  if (r.ok) loadVideos();
};

/* ---- 发起测试 ---- */
$("runBtn").onclick = async () => {
  const rel = document.querySelector('input[name="video"]:checked');
  if (!rel) { $("runHint").textContent = "请先在②选择视频"; return; }
  const body = {
    item: $("itemSelect").value, video: rel.value, duration: +$("duration").value,
    grid8: $("grid8").checked, skip_deploy: $("skipDeploy").checked
  };
  const r = await api("/api/run", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body)
  });
  if (!r.ok) { $("runHint").textContent = r.error || "发起失败"; return; }
  $("runHint").textContent = "已发起 task " + r.task_id.slice(0, 8);
  startPoll(r.task_id);
  loadTasks();
};

function startPoll(tid) {
  curTask = tid; logLen = 0; $("taskLog").textContent = "";
  if (pollTimer) clearInterval(pollTimer);
  poll(); pollTimer = setInterval(poll, 2000);
  $("runBtn").disabled = true;
}
async function poll() {
  if (!curTask) return;
  const t = await api("/api/task/" + curTask + "?since=" + logLen);
  if (t.error) return;
  logLen = t.total;
  if (t.log.length) { $("taskLog").textContent += t.log.join("\n") + "\n"; $("taskLog").scrollTop = 1e9; }
  setStatus(t.status);
  if (t.status !== "running") {
    clearInterval(pollTimer); pollTimer = null;
    $("runBtn").disabled = false; loadReports(); loadTasks();
  }
}
function setStatus(s) {
  const el = $("taskStatus");
  el.textContent = s === "running" ? "运行中" : s === "done" ? "已完成" : "失败";
  el.className = "tag " + (s === "running" ? "run" : s === "done" ? "ok" : "err");
}

/* ---- 任务历史 ---- */
async function loadTasks() {
  const ts = await api("/api/tasks");
  const c = $("taskList"); c.innerHTML = "";
  ts.slice(0, 8).forEach(t => {
    const d = document.createElement("span");
    d.className = "taskchip " + t.status;
    d.textContent = `${t.item} ${t.id.slice(0, 6)} ${t.status}`;
    d.title = t.video;
    d.onclick = () => {
      curTask = t.id; logLen = 0; $("taskLog").textContent = "";
      if (pollTimer) clearInterval(pollTimer);
      if (t.status === "running") pollTimer = setInterval(poll, 2000);
      poll();
    };
    c.appendChild(d);
  });
}

/* ---- 报告(md渲染 + 双报告对比) ---- */
function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
function inlineMd(h) {
  return h.replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>").replace(/`([^`]+)`/g, "<code>$1</code>");
}
function renderMd(md) {
  // 先escape原文再转标签, 输出安全HTML
  const out = []; let inCode = false;
  for (const ln of md.split("\n")) {
    if (/^```/.test(ln)) { out.push(inCode ? "</pre>" : "<pre>"); inCode = !inCode; continue; }
    if (inCode) { out.push(esc(ln)); continue; }
    let body, tag = "div";
    if (/^### /.test(ln)) { tag = "h4"; body = ln.slice(4); }
    else if (/^## /.test(ln)) { tag = "h3"; body = ln.slice(3); }
    else if (/^# /.test(ln)) { tag = "h2"; body = ln.slice(2); }
    else if (/^- /.test(ln)) { tag = "li"; body = ln.slice(2); }
    else if (ln.trim() === "") { continue; }
    else body = ln;
    out.push("<" + tag + ">" + inlineMd(esc(body)) + "</" + tag + ">");
  }
  if (inCode) out.push("</pre>");
  return out.join("");
}

async function loadReports() {
  const rs = await api("/api/reports");
  const c = $("reportList"); c.innerHTML = "";
  rs.forEach(r => {
    const d = document.createElement("div"); d.className = "repitem";
    const chk = document.createElement("input");
    chk.type = "checkbox"; chk.className = "cmpchk"; chk.value = r.name;
    chk.onclick = e => e.stopPropagation();
    const txt = document.createElement("span");
    const t1 = document.createElement("div"); t1.textContent = r.base;
    const t2 = document.createElement("div"); t2.className = "t";
    t2.textContent = `${fmtTime(r.mtime)} · ${fmtSize(r.size)}${r.has_jsonl ? " · 含数据" : ""}`;
    txt.append(t1, t2);
    d.append(chk, txt);
    d.onclick = () => viewReport(r.name);
    c.appendChild(d);
  });
}
async function viewReport(name) {
  const r = await api("/api/report/" + name);
  const rv = $("reportView");
  rv.classList.remove("cmpwrap");
  rv.innerHTML = r.content ? renderMd(r.content) : esc(r.error || "");
}
$("cmpBtn").onclick = async () => {
  const checked = Array.from(document.querySelectorAll(".cmpchk:checked")).map(x => x.value);
  if (checked.length !== 2) { alert("请勾选恰好 2 个报告再对比"); return; }
  const rv = $("reportView");
  rv.classList.add("cmpwrap"); rv.innerHTML = "";
  for (const name of checked) {
    const r = await api("/api/report/" + name);
    const col = document.createElement("div"); col.className = "cmpcol";
    col.innerHTML = renderMd(r.content || "");
    rv.appendChild(col);
  }
};

$("refreshVideos").onclick = loadVideos;
$("refreshReports").onclick = loadReports;

/* ---- 设备管理(多设备切换) ---- */
let DEVS = [];
async function loadDevices() {
  const r = await api("/api/devices");
  DEVS = r.devices || [];
  const sel = $("deviceSelect"); sel.innerHTML = "";
  DEVS.forEach(d => {
    const o = document.createElement("option");
    o.value = d.key; o.textContent = `${d.model}·${d.name} ${d.ip}`;
    if (d.active) o.selected = true;
    sel.appendChild(o);
  });
  const cur = DEVS.find(d => d.active);
  $("deviceInfo").textContent = cur ? `${cur.model}@${cur.ip}` : "无设备";
  loadFw();
}
async function loadFw() {
  const el = $("fwInfo"); if (!el) return;
  el.textContent = "固件 …";
  const r = await api("/api/device/firmware");
  el.textContent = r.ok ? ("固件 " + (r.version || "?")) : "固件 离线";
  el.classList.toggle("off", !r.ok);
}
$("deviceSelect").onchange = async () => {
  const r = await api("/api/device/select", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ key: $("deviceSelect").value }) });
  if (r.ok) { loadDevices(); } else { alert(r.error || "切换失败"); loadDevices(); }
};

let devEditKey = "";
$("devMgrBtn").onclick = () => { renderDevList(); devForm(null); loadFwPkgs(); $("devModal").style.display = "flex"; };
$("devClose").onclick = () => { $("devModal").style.display = "none"; };
$("devModal").onclick = e => { if (e.target === $("devModal")) $("devModal").style.display = "none"; };
function renderDevList() {
  const c = $("devList"); c.innerHTML = "";
  DEVS.forEach(d => {
    const item = document.createElement("div"); item.className = "devitem" + (d.active ? " on" : "");
    const info = document.createElement("span"); info.style.flex = "1";
    info.textContent = `${d.active ? "✓ 当前 · " : ""}${d.model} · ${d.name} · ${d.ip}`;
    const ed = document.createElement("button"); ed.className = "mini"; ed.textContent = "编辑";
    ed.onclick = () => devForm(d.key);
    const del = document.createElement("button"); del.className = "mini del"; del.textContent = "删除";
    del.onclick = () => delDevice(d.key);
    item.append(info, ed, del); c.appendChild(item);
  });
}
function devForm(key) {
  devEditKey = key || "";
  const d = DEVS.find(x => x.key === key);
  $("devFormTitle").textContent = key ? `编辑设备 ${key}` : "新增设备";
  $("dName").value = d ? d.name : ""; $("dModel").value = d ? d.model : "X5";
  $("dIp").value = d ? d.ip : ""; $("dUser").value = d ? d.ssh_user : "root";
  $("dPass").value = ""; $("dToken").value = "";
  $("dHint").textContent = key ? "密码/token 留空 = 保持不变" : "新设备请填 SSH 密码";
}
$("dNew").onclick = () => devForm(null);
$("dSave").onclick = async () => {
  const body = { key: devEditKey, name: $("dName").value.trim(), model: $("dModel").value, ip: $("dIp").value.trim(), ssh_user: $("dUser").value.trim() };
  if ($("dPass").value) body.ssh_pass = $("dPass").value;
  if ($("dToken").value) body.token = $("dToken").value;
  const r = await api("/api/device/save", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  $("dHint").textContent = r.ok ? `已保存 ${r.key}` : (r.error || "保存失败");
  if (r.ok) { await loadDevices(); renderDevList(); }
};
async function delDevice(key) {
  if (!confirm(`删除设备 ${key} ?`)) return;
  const r = await api("/api/device/delete", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ key }) });
  if (!r.ok) { alert(r.error || "删除失败"); return; }
  await loadDevices(); renderDevList();
}

async function loadFwPkgs() {
  const sel = $("fwSelect"); if (!sel) return;
  const cur = DEVS.find(d => d.active);
  $("fwDevInfo").textContent = cur ? `${cur.name} (${cur.model}@${cur.ip}) · 当前固件见顶栏` : "无激活设备";
  const r = await api("/api/firmware/list");
  sel.innerHTML = "";
  const model = cur ? (cur.model || "").toLowerCase() : "?";
  const pkgs = (r.ok && cur) ? (r.fw[model] || []) : [];
  if (!pkgs.length) { sel.innerHTML = `<option value="">(firmware/${model}/ 下暂无固件包)</option>`; return; }
  pkgs.forEach(p => { const o = document.createElement("option"); o.value = p.name; o.textContent = `${p.name} (${(p.size / 1048576).toFixed(1)}MB)`; sel.appendChild(o); });
}
$("flashBtn").onclick = async () => {
  const cur = DEVS.find(d => d.active); const f = $("fwSelect").value;
  if (!cur) { alert("无激活设备"); return; }
  if (!f) { alert("请先选择固件包(需先放入 firmware/" + (cur.model || "").toLowerCase() + "/ 目录)"); return; }
  if (!confirm(`确认刷机?\n\n设备: ${cur.name} (${cur.model}@${cur.ip})\n固件: ${f}\n\n⚠ 刷机有风险, 过程中请勿断电/断网, 设备将自动重启!`)) return;
  $("flashBtn").disabled = true; $("flashBtn").textContent = "刷机中(下载+更新, 请勿关页)...";
  try {
    const r = await api("/api/firmware/flash", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ key: cur.key, file: f }) });
    if (r.ok) { alert("✅ 刷机指令已下发, 设备更新中会自动重启, 稍后请刷新查看顶栏固件版本"); setTimeout(loadFw, 8000); }
    else alert("❌ 刷机失败: " + (r.error || JSON.stringify(r)));
  } finally { $("flashBtn").disabled = false; $("flashBtn").textContent = "🔥 开始刷机"; }
};

loadItems(); loadVideos(); loadReports(); loadTasks(); loadDevices();
