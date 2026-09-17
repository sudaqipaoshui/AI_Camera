/* 平台视图: 历史批次 / 趋势 / 指标
 *
 * 数据来自后端 /api/runs、/api/run/<id>、/api/trend, 源头是本机测试库的
 * test_run / case_result / metric 三张表。库不可用时后端返回 ok=false,
 * 这里只显示一句提示, 不影响页面其它功能。
 *
 * 渲染一律用 textContent, 不用 innerHTML 拼字符串 —— 用例名/失败信息来自
 * 测试输出, 属于外部内容, 不能直接当 HTML 塞进 DOM。
 */
const PF = { runs: [], targets: [], target: "" };

function pfEl(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

function pfShortTime(s) {
  return s ? String(s).slice(5, 16).replace("T", " ") : "—";
}

function pfPct(r) {
  const total = r.total || 0;
  return total ? Math.round((r.passed || 0) / total * 1000) / 10 : 0;
}

/* ---- 批次列表 ---- */
async function pfRefresh() {
  const hint = $("pfHint"); hint.textContent = "读取中…";
  let d;
  try {
    d = await api("/api/runs?limit=100" + (PF.target ? "&target=" + encodeURIComponent(PF.target) : ""));
  } catch (e) {
    hint.textContent = "请求失败: " + e; return;
  }
  if (!d.ok) { hint.textContent = d.error || "结果库不可用"; $("pfStatus").textContent = ""; return; }

  PF.runs = d.runs || [];
  PF.targets = d.targets || [];
  const sel = $("pfTarget");
  if (sel.options.length <= 1 && PF.targets.length) {
    PF.targets.forEach(t => {
      const o = document.createElement("option"); o.value = t; o.textContent = t; sel.appendChild(o);
    });
  }
  hint.textContent = `共 ${PF.runs.length} 个批次`;

  const tb = $("pfRunList"); tb.textContent = "";
  if (!PF.runs.length) {
    const tr = pfEl("tr"); const td = pfEl("td", "", "还没有批次。跑一次 `python run.py api` 就有了。");
    td.colSpan = 9; td.style.color = "#888780"; tr.appendChild(td); tb.appendChild(tr);
  }
  PF.runs.forEach(r => {
    const tr = pfEl("tr");
    tr.appendChild(pfEl("td", "pf-mono", r.run_id));
    tr.appendChild(pfEl("td", "", r.target || "—"));
    tr.appendChild(pfEl("td", "", pfShortTime(r.started_at)));
    const rate = pfPct(r);
    const tdRate = pfEl("td", "pf-rate");
    const bar = pfEl("span", "pf-bar" + (rate < 95 ? " bad" : ""));
    bar.style.width = Math.max(3, rate) + "px";
    tdRate.append(pfEl("span", "", rate + "%"), bar);
    tr.appendChild(tdRate);
    tr.appendChild(pfEl("td", "pf-num", String(r.failed == null ? "—" : r.failed)));
    tr.appendChild(pfEl("td", "pf-num", (r.duration_sec || 0) + "s"));
    tr.appendChild(pfEl("td", "pf-mono", r.firmware || "—"));
    tr.appendChild(pfEl("td", "", r.tag || "—"));
    const cls = r.verdict === "PASS" ? "pf-pass" : (r.verdict === "FAIL" ? "pf-fail" : "pf-warn");
    tr.appendChild(pfEl("td", cls, r.verdict || "—"));
    tr.onclick = () => pfDetail(r.run_id);
    tb.appendChild(tr);
  });
  pfTrend();
}

/* ---- 批次详情 ---- */
async function pfDetail(runId) {
  const box = $("pfDetail");
  box.style.display = "block";
  box.textContent = "读取 " + runId + " …";
  const d = await api("/api/run/" + encodeURIComponent(runId) + "?limit=300");
  if (!d.ok) { box.textContent = d.error || "读取失败"; return; }
  box.textContent = "";

  const run = d.run || {};
  const head = pfEl("div", "pf-detail-head",
    `${runId} · ${run.verdict} · ${run.passed}/${run.total} 通过 · 失败 ${run.failed} · ` +
    `跳过 ${run.skipped} · ${run.duration_sec}s · 固件 ${run.firmware || "未记录"}`);
  box.appendChild(head);

  const meta = pfEl("div", "hint",
    `设备 ${run.device_key || "—"} (${run.device_ip || "—"}) · 提交 ${(run.git_commit || "").slice(0, 8) || "—"}` +
    `${run.git_dirty ? " +未提交改动" : ""} · 触发 ${run.trigger_by || "—"}`);
  box.appendChild(meta);

  if (d.metrics && d.metrics.length) {
    const wrap = pfEl("div", "pf-metrics");
    d.metrics.forEach(m => {
      wrap.appendChild(pfEl("span", "pf-chip",
        `${m.name}${m.subject ? "[" + m.subject + "]" : ""}: ${m.value}${m.unit || ""}`));
    });
    box.appendChild(wrap);
  }

  const failed = (d.cases || []).filter(c => c.status === "failed" || c.status === "error");
  const h = pfEl("h3", "", `失败用例 (${failed.length})`);
  box.appendChild(h);
  if (!failed.length) {
    box.appendChild(pfEl("div", "hint", "没有失败用例。"));
  } else {
    const list = pfEl("div", "pf-cases");
    failed.forEach(c => {
      const item = pfEl("div", "pf-case");
      item.appendChild(pfEl("div", "pf-case-name", c.nodeid));
      const first = String(c.message || "").split("\n").filter(x => x.trim()).slice(-1)[0] || "";
      item.appendChild(pfEl("div", "pf-case-msg", first.slice(0, 300)));
      list.appendChild(item);
    });
    box.appendChild(list);
  }

  const btn = pfEl("button", "mini", "查看原始日志尾部");
  btn.onclick = async () => {
    const l = await api("/api/platform/log?run_id=" + encodeURIComponent(runId) + "&tail=20000");
    if (!l.ok) { alert(l.error); return; }
    const pre = pfEl("pre", "log", l.text);
    box.appendChild(pre);
    btn.disabled = true;
  };
  box.appendChild(btn);
}

/* ---- 趋势 ---- */
function pfSpark(points, w, h) {
  // 用 SVG 画通过率走势。points: [{value, label}]
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  svg.setAttribute("width", String(w));
  svg.setAttribute("height", String(h));
  if (points.length < 2) return svg;
  const vals = points.map(p => p.value);
  const lo = Math.min(100, Math.min(...vals));
  const hi = 100;
  const span = Math.max(1, hi - lo);
  const step = w / (points.length - 1);
  const y = v => h - 4 - ((v - lo) / span) * (h - 10);
  const d = points.map((p, i) => `${i ? "L" : "M"}${(i * step).toFixed(1)} ${y(p.value).toFixed(1)}`).join(" ");
  const path = document.createElementNS(NS, "path");
  path.setAttribute("d", d);
  path.setAttribute("fill", "none");
  path.setAttribute("stroke", vals[vals.length - 1] < 95 ? "#A32D2D" : "#3B6D11");
  path.setAttribute("stroke-width", "1.5");
  svg.appendChild(path);
  points.forEach((p, i) => {
    const c = document.createElementNS(NS, "circle");
    c.setAttribute("cx", (i * step).toFixed(1));
    c.setAttribute("cy", y(p.value).toFixed(1));
    c.setAttribute("r", "2");
    c.setAttribute("fill", p.value < 95 ? "#A32D2D" : "#3B6D11");
    const t = document.createElementNS(NS, "title");
    t.textContent = `${p.label}: ${p.value}%`;
    c.appendChild(t);
    svg.appendChild(c);
  });
  return svg;
}

async function pfTrend() {
  const box = $("pfTrend"); box.textContent = "";
  const d = await api("/api/trend?limit=60");
  if (!d.ok) { box.appendChild(pfEl("div", "hint", d.error || "趋势不可用")); return; }
  const targets = Object.keys(d.targets || {});
  if (!targets.length) { box.appendChild(pfEl("div", "hint", "暂无趋势数据。")); return; }

  box.appendChild(pfEl("h3", "", "通过率趋势(最近 20 批)"));
  targets.forEach(t => {
    const rows = (d.targets[t] || []).slice(-20);
    if (rows.length < 2) return;
    const wrap = pfEl("div", "pf-trend-row");
    wrap.appendChild(pfEl("div", "pf-trend-label", t));
    wrap.appendChild(pfSpark(rows.map(r => ({ value: r.pass_rate, label: r.run_id })), 320, 48));
    const last = rows[rows.length - 1], prev = rows[rows.length - 2];
    const delta = (last.pass_rate - prev.pass_rate).toFixed(1);
    const txt = `${last.pass_rate}%`;
    const tail = pfEl("div", "pf-trend-tail", `${txt}  ${delta > 0 ? "↑" : delta < 0 ? "↓" : "—"}${Math.abs(delta)}`);
    tail.classList.add(delta < 0 ? "pf-fail" : "pf-pass");
    wrap.appendChild(tail);
    wrap.appendChild(pfEl("span", "hint", `固件 ${last.firmware || "?"} · ${pfShortTime(last.started_at)}`));
    box.appendChild(wrap);
  });

  const mkeys = Object.keys(d.metrics || {});
  if (mkeys.length) {
    box.appendChild(pfEl("h3", "", "指标趋势"));
    mkeys.forEach(k => {
      const vals = d.metrics[k] || [];
      if (!vals.length) return;
      const nums = vals.map(x => x.value);
      const row = pfEl("div", "pf-trend-row");
      row.appendChild(pfEl("div", "pf-trend-label", k));
      row.appendChild(pfEl("div", "", `最新 ${nums[nums.length - 1]} · 最小 ${Math.min(...nums)} · 最大 ${Math.max(...nums)} · 样本 ${nums.length}`));
      box.appendChild(row);
    });
  }
}

/* ---- 生成报告 ---- */
async function pfMakeReport() {
  const hint = $("pfHint"); hint.textContent = "生成中…";
  const d = await api("/api/platform/trend-report", { method: "POST" });
  if (!d.ok) { hint.textContent = d.error || "生成失败"; return; }
  hint.textContent = "已生成，正在打开…";
  window.open(d.url, "_blank");
}

async function pfStatus() {
  const d = await api("/api/platform/status");
  const el = $("pfStatus");
  if (!d.ok) {
    el.textContent = "结果库不可用 —— " + (d.error || "") + (d.hint ? " | " + d.hint : "");
    el.className = "hint pf-fail";
  } else {
    el.textContent = `结果库正常 · ${d.total_runs} 个批次`;
    el.className = "hint";
  }
}

function pfInit() {
  $("pfRefresh").onclick = () => { pfStatus(); pfRefresh(); };
  $("pfMakeReport").onclick = pfMakeReport;
  $("pfTarget").onchange = () => { PF.target = $("pfTarget").value; pfRefresh(); };
  pfStatus();
  pfRefresh();
}

document.addEventListener("DOMContentLoaded", pfInit);
