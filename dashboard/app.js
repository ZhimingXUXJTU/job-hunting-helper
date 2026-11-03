/* 求职工作台前端（原生 JS，无依赖）。只读 /api/snapshot 渲染，不发任何外部请求。 */
"use strict";

const $ = (id) => document.getElementById(id);

const VERDICT_LABEL = {
  advance: "重点推进",
  review: "人工复核",
  watch: "观察",
  pass: "放弃",
  eliminated: "红线淘汰",
};

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function tag(verdict) {
  return `<span class="tag tag-${esc(verdict)}">${esc(VERDICT_LABEL[verdict] || verdict)}</span>`;
}

function renderCandidate(c) {
  if (!c.ready) {
    $("candidate").innerHTML = `<p class="empty">${esc(c.hint)}</p>`;
    return;
  }
  const np = c.needs_proof > 0
    ? `<span class="tag tag-needs">needs_proof × ${c.needs_proof}</span>`
    : `<span class="tag tag-ok">证据齐全</span>`;
  $("candidate").innerHTML = `
    <dl class="kv">
      <dt>定位</dt><dd>${esc(c.title || "未填")}</dd>
      <dt>年限</dt><dd>${esc(c.years ?? "未填")}</dd>
      <dt>目标城市</dt><dd>${esc((c.cities || []).join("、") || "不限")}</dd>
      <dt>技能</dt><dd>expert ${c.skills_count.expert} · practiced ${c.skills_count.practiced} · learned ${c.skills_count.learned}</dd>
      <dt>项目</dt><dd>${c.projects_total} 个，其中 ${np}</dd>
    </dl>`;
}

function table(headers, rowsHtml) {
  if (!rowsHtml) return `<p class="empty">（空）</p>`;
  return `<table><thead><tr>${headers.map((h) => `<th>${h}</th>`).join("")}</tr></thead>
    <tbody>${rowsHtml}</tbody></table>`;
}

function renderInbox(items) {
  const rows = items.map((j) => `
    <tr><td>${esc(j.company)}</td><td>${esc(j.position)}</td>
    <td>${esc(j.collected_at || "-")}</td><td class="muted">${esc(j.file)}</td></tr>`).join("");
  $("inbox").innerHTML = table(["公司", "岗位", "收录日", "文件"], rows);
}

function renderEvals(items) {
  const rows = items.map((e) => `
    <tr><td>${esc(e.evaluated_at || "-")}</td><td>${esc(e.company)}</td>
    <td>${esc(e.position)}</td>
    <td><span class="score">${esc(e.total ?? "-")}</span></td>
    <td>${tag(e.verdict)}${e.data_incomplete ? ' <span class="tag tag-review">数据不全</span>' : ""}</td></tr>`).join("");
  $("evals").innerHTML = table(["评估日", "公司", "岗位", "总分", "结论"], rows);
}

function renderTracker(rows) {
  const body = rows.map((r) => {
    const st = r.status || "";
    const stTag = st === "eliminated" ? tag("eliminated")
      : st === "scored" ? '<span class="tag tag-watch">已评分</span>'
      : `<span class="tag tag-review">${esc(st || "-")}</span>`;
    return `
      <tr><td>${esc(r.collected_date || "-")}</td><td>${esc(r.company)}</td>
      <td>${esc(r.position)}</td><td>${esc(r.city || "-")}</td>
      <td><span class="score">${esc(r.score || "-")}</span></td>
      <td>${stTag}</td><td>${esc(r.resume_version || "-")}</td>
      <td>${esc(r.next_action || "")}</td></tr>`;
  }).join("");
  $("tracker").innerHTML = table(
    ["日期", "公司", "岗位", "城市", "分", "状态", "简历版", "下一步"], body);
}

function renderRules(rules) {
  if (!rules) {
    $("rules").innerHTML = `<p class="empty">config/scoring.yml 不存在</p>`;
    return;
  }
  const rl = rules.redlines || {};
  const sn = rules.salary_notes || {};
  const th = rules.thresholds || {};
  const salary = [];
  if (sn.basis === "total_package") salary.push("按综合年包（月薪×薪数）进评分，不作红线");
  else if (sn.basis) salary.push(`口径：${sn.basis}`);
  if (sn.missing === "manual_review") salary.push("JD 未写薪资标人工复核");
  $("rules").innerHTML = `
    <dl class="kv">
      <dt>用工形式红线</dt><dd>${esc((rl.employment_type_blocked || []).join("、") || "无")}</dd>
      <dt>城市限制</dt><dd>${esc((rl.cities_allowed || []).join("、") || "不限")}</dd>
      <dt>文本红线词</dt><dd>${esc((rl.keyword_blocked || []).join("、") || "无")}</dd>
      <dt>薪资</dt><dd>${esc(salary.join("；") || "见 config/scoring.yml 的 salary_notes")}</dd>
      <dt>阈值</dt><dd>≥${esc(th.advance)} 重点推进 · ≥${esc(th.review)} 人工复核 · 其余观察/放弃</dd>
    </dl>`;
}

async function load() {
  try {
    const res = await fetch("/api/snapshot");
    const snap = await res.json();
    $("generated-at").textContent = `快照生成于 ${snap.generated_at}`;
    renderCandidate(snap.candidate);
    renderInbox(snap.inbox || []);
    renderEvals(snap.evals || []);
    renderTracker(snap.tracker || []);
    renderRules(snap.rules);
    const outs = snap.outputs || [];
    $("outputs-summary").textContent = outs.length
      ? `产物目录 ${outs.length} 个岗位（outputs/private/）：` + outs.map((o) => o.job_id).join("、")
      : "还没有产物：跑一次 tools/run_workflow.py 生成。";
  } catch (err) {
    $("generated-at").textContent = "快照加载失败：" + err;
  }
}

$("refresh").addEventListener("click", load);
load();
