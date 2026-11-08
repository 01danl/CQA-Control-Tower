/* Local benchmark dashboard. Renders only real recorded data from /api/data. */
"use strict";

const CRITERIA = ["contact", "discovery", "identification", "consultation", "empathy", "dialogue", "closure", "critical"];
const SHORT = { contact: "C01", discovery: "C02", identification: "C03", consultation: "C04", empathy: "C05", dialogue: "C06", closure: "C07", critical: "C08" };

let DATA = null;
let CURRENT = null;

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const fmtUsd = (v) => v == null ? "—" : "$" + Number(v).toFixed(6);
const modelShort = (m) => m.split("/").pop();
const langOf = (cid) => (cid.match(/^p\d-([a-z]{2})-\d+$/) || [])[1]?.toUpperCase() ?? "?";

async function boot() {
  const list = await (await fetch("/api/experiments")).json();
  const sel = $("experiment");
  sel.innerHTML = list.experiments.map((e) =>
    `<option value="${esc(e.experiment_id)}">${esc(e.experiment_id)} (${e.completed}/${e.total})</option>`).join("");
  sel.onchange = () => load(sel.value);
  for (const btn of document.querySelectorAll(".tabs button"))
    btn.onclick = () => {
      document.querySelectorAll(".tabs button, .tab").forEach((n) => n.classList.remove("active"));
      btn.classList.add("active");
      $(btn.dataset.tab).classList.add("active");
    };
  if (list.experiments.length) await load(list.experiments[0].experiment_id);
  else $("meta").textContent = "No experiments collected yet — run app.experiments collect first.";
}

async function load(experimentId) {
  DATA = await (await fetch(`/api/data/${encodeURIComponent(experimentId)}`)).json();
  CURRENT = DATA;
  render();
}

function experimentRows() {
  // One row per (model, conversation) with transcript metadata attached.
  return DATA.experiments.map((r) => {
    const transcript = DATA.transcripts[r.conversation_id] || [];
    return {
      ...r,
      language: langOf(r.conversation_id),
      channel: transcript[0]?.speaker ? channelOf(r.conversation_id) : channelOf(r.conversation_id),
      turns: transcript.length,
    };
  });
}

function channelOf(cid) {
  // Channel is derived from transcript shape (voice calls are stored in DEV metadata
  // via baseline usage rows); fall back to p4-* prefix used for calls.
  return /^p4-/.test(cid) ? "voice call" : "agent chat";
}

function render() {
  const models = DATA.models;
  $("meta").textContent =
    `${DATA.experiment_id} · pipeline ${DATA.pipeline_hash?.slice(0, 8)} · prompt ${DATA.prompt_hash?.slice(0, 8)}`
    + ` · reasoning: ${Object.entries(DATA.reasoning_config).map(([m, r]) => `${modelShort(m)}=${r ?? "default"}`).join(", ")}`
    + ` · max_output: ${Object.values(DATA.max_output_tokens)[0]}`;

  // Filters
  const fill = (id, values) => {
    const el = $(id);
    el.innerHTML = `<option value="">${el.options[0].text}</option>` + [...new Set(values)].map((v) => `<option>${esc(v)}</option>`).join("");
  };
  fill("f-model", models.map(modelShort));
  fill("f-lang", experimentRows().map((r) => r.language));
  fill("f-channel", experimentRows().map((r) => r.channel));
  for (const id of ["f-model", "f-lang", "f-channel", "f-status"]) $(id).onchange = renderTables;

  renderCards();
  renderTables();
  renderSideBySide();
}

function visibleRows() {
  const fm = modelMatch($("f-model").value), fl = $("f-lang").value, fc = $("f-channel").value, fs = $("f-status").value;
  return experimentRows().filter((r) =>
    (!fm || modelShort(r.model) === fm) && (!fl || r.language === fl) && (!fc || r.channel === fc) && (!fs || r.status === fs));
}

function modelMatch(shortName) {
  const full = DATA.models.find((m) => modelShort(m) === shortName);
  return full || null;
}

function renderCards() {
  const cards = [];
  for (const model of DATA.models) {
    const rows = DATA.experiments.filter((r) => r.model === model);
    const ok = rows.filter((r) => r.status === "completed");
    const cost = ok.reduce((s, r) => s + Number(r.usage?.provider_cost_usd ?? 0), 0);
    const lat = ok.map((r) => r.duration_ms).filter(Boolean);
    const tokens = ok.reduce((s, r) => s + Number(r.usage?.output_tokens ?? 0), 0);
    const reasoning = ok.reduce((s, r) => s + Number(r.usage?.reasoning_tokens ?? 0), 0);
    const avgScore = ok.filter((r) => r.score != null);
    cards.push(`
      <div class="card">
        <h3>${esc(modelShort(model))}</h3>
        <div class="k">${esc(model)}</div>
        <div>completed <b>${ok.length}</b> / ${rows.length}</div>
        <div>avg score <b>${avgScore.length ? (avgScore.reduce((s, r) => s + r.score, 0) / avgScore.length).toFixed(2) : "—"}</b></div>
        <div>total cost <b>${fmtUsd(cost)}</b></div>
        <div>cost / success <b>${ok.length ? fmtUsd(cost / ok.length) : "—"}</b></div>
        <div>latency avg <b>${lat.length ? Math.round(lat.reduce((a, b) => a + b, 0) / lat.length) : "—"} ms</b></div>
        <div>output tokens <b>${tokens}</b> · reasoning <b>${reasoning}</b></div>
      </div>`);
  }
  const verified = DATA.official_baseline.filter((b) => b.status === "verified").length;
  cards.push(`<div class="card baseline"><h3>${esc(modelShort(DATA.production_model))} (official baseline)</h3>
    <div class="k">${esc(DATA.production_model)}</div>
    <div>provenance-verified results <b>${verified}</b> / ${DATA.official_baseline.length}</div>
    <div class="note">Read-only comparison anchor; never modified by experiments.</div></div>`);
  $("cards").innerHTML = cards.join("");
}

function renderTables() {
  // Latency/duration distribution per model (buckets).
  const head = `<tr><th>model</th><th>n</th><th>min ms</th><th>p50 ms</th><th>p90 ms</th><th>max ms</th><th>failed</th></tr>`;
  const rows = DATA.models.map((model) => {
    const ok = DATA.experiments.filter((r) => r.model === model && r.status === "completed" && r.duration_ms);
    const lat = ok.map((r) => r.duration_ms).sort((a, b) => a - b);
    const pick = (p) => lat.length ? lat[Math.min(lat.length - 1, Math.floor(p * lat.length))] : null;
    const failed = DATA.experiments.filter((r) => r.model === model && r.status === "failed").length;
    return `<tr><td>${esc(modelShort(model))}</td><td>${lat.length}</td>
      <td>${lat[0] ?? "—"}</td><td>${pick(0.5) ?? "—"}</td><td>${pick(0.9) ?? "—"}</td>
      <td>${lat[lat.length - 1] ?? "—"}</td><td>${failed}</td></tr>`;
  }).join("");
  $("latency").innerHTML = head + rows;

  // Case table with filters.
  const caseHead = `<tr><th>model</th><th>conversation</th><th>lang</th><th>channel</th><th>turns</th>
    <th>status</th><th>score</th><th>cost</th><th>duration ms</th><th>reasoning tok</th><th></th></tr>`;
  const caseRows = visibleRows().map((r) => `
    <tr class="status-${esc(r.status)}">
      <td>${esc(modelShort(r.model))}</td><td>${esc(r.conversation_id)}</td>
      <td>${esc(r.language)}</td><td>${esc(r.channel)}</td><td>${r.turns}</td>
      <td>${esc(r.status)}</td><td>${r.score ?? "—"}</td><td>${fmtUsd(r.usage?.provider_cost_usd)}</td>
      <td>${r.duration_ms ?? "—"}</td><td>${r.usage?.reasoning_tokens ?? "—"}</td>
      <td>${r.status === "completed" ? `<button onclick="openDetail('${esc(r.model)}','${esc(r.conversation_id)}')">open</button>` : ""}</td>
    </tr>`).join("");
  $("case-table").innerHTML = caseHead + (caseRows || `<tr><td colspan="11">no rows match the filters</td></tr>`);
}

function renderSideBySide() {
  const ids = [...new Set(DATA.experiments.map((r) => r.conversation_id))];
  const sel = $("sb-conversation");
  sel.innerHTML = ids.map((id) => `<option value="${esc(id)}">${esc(id)}</option>`).join("");
  sel.onchange = renderSb;
  renderSb();
}

function renderSb() {
  const cid = $("sb-conversation").value;
  if (!cid) return;
  const perModel = DATA.models.map((model) => ({
    model,
    row: DATA.experiments.find((r) => r.model === model && r.conversation_id === cid),
  }));
  const baseline = DATA.official_baseline.find((b) => b.conversation_id === cid);
  $("sb-header").innerHTML =
    `<div><b>${esc(cid)}</b> · turns: ${(DATA.transcripts[cid] || []).length}</div>`
    + perModel.map(({ model, row }) =>
      `<div>${esc(modelShort(model))}: <b>${row?.score ?? "—"}</b>${row?.gross_error ? " · GROSS VIOLATION" : ""}</div>`).join("")
    + (baseline?.status === "verified" ? `<div>baseline V4.1: <b>${baseline.score}</b></div>` : `<div>baseline V4.1: no verified result</div>`);
  const cell = (row, crit) => {
    const c = (row?.criteria || []).find((x) => x.criterion_id === crit);
    if (!c) return `<td>—</td>`;
    const turns = (c.evidence || []).map((e) => e.message_index + 1);
    return `<td><b>${esc(c.value)}</b>${c.na_reason ? " (N/A)" : ""}<br>
      <button class="link" onclick="openDetail('${esc(row.model)}','${esc(cid)}',${turns[0] ?? -1})">evidence ${esc(turns.join(",") || "—")}</button></td>`;
  };
  let html = `<table class="grid"><tr><th>criterion</th>${perModel.map(({ model }) => `<th>${esc(modelShort(model))}</th>`).join("")}${baseline?.status === "verified" ? `<th>V4.1 baseline</th>` : ""}</tr>`;
  for (const crit of CRITERIA) {
    html += `<tr><td>${SHORT[crit]}</td>${perModel.map(({ row }) => cell(row, crit)).join("")}
      ${baseline?.status === "verified" ? cell({ criteria: baseline.criteria, model: "baseline" }, crit) : ""}</tr>`;
  }
  $("sb-grid").innerHTML = html + "</table>";
}

window.openDetail = function (model, cid, focusTurn = -1) {
  const row = DATA.experiments.find((r) => r.model === model && r.conversation_id === cid);
  if (!row) return;
  $("d-title").textContent = `${modelShort(model)} · ${cid}`;
  $("d-summary").innerHTML =
    `<div>status <b>${esc(row.status)}</b> · score <b>${row.score ?? "—"}</b> · cost ${fmtUsd(row.usage?.provider_cost_usd)}
     · duration ${row.duration_ms ?? "—"} ms</div>
     <div>tokens in/out/reasoning: ${row.usage?.input_tokens ?? "—"} / ${row.usage?.output_tokens ?? "—"} / ${row.usage?.reasoning_tokens ?? "—"}</div>
     ${row.error ? `<div class="err">${esc(row.error.code)}: ${esc(row.error.message)}</div>` : ""}`;
  $("d-results").innerHTML = `<table class="grid"><tr><th>#</th><th>value</th><th>rationale</th><th>evidence turns</th></tr>`
    + (row.criteria || []).map((c) => `
      <tr><td>${esc(SHORT[c.criterion_id] || c.criterion_id)}</td><td><b>${esc(c.value)}</b></td>
      <td class="rationale">${esc(c.reason)}</td>
      <td>${(c.evidence || []).map((e) => `<button class="link" onclick="jump(${e.message_index + 1})">turn ${e.message_index + 1}</button>`).join(" ")}</td></tr>`).join("")
    + `</table>`;
  const transcript = DATA.transcripts[cid] || [];
  $("d-transcript").innerHTML = transcript.map((msg, i) => `
    <div class="turn speaker-${esc(msg.speaker)}" id="turn-${i + 1}">
      <span class="idx">${i + 1}</span><span class="speaker">${esc(msg.speaker)}</span>: ${esc(msg.text)}
    </div>`).join("");
  document.getElementById("detail").showModal();
  if (focusTurn > 0) jump(focusTurn);
};

window.jump = function (turn) {
  const el = document.getElementById(`turn-${turn}`);
  if (!el) return;
  for (const node of document.querySelectorAll(".turn")) node.classList.remove("focus");
  el.classList.add("focus");
  el.scrollIntoView({ block: "center" });
};

$("export-json").onclick = () => {
  const blob = new Blob([JSON.stringify(CURRENT, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${DATA.experiment_id}-report.json`;
  a.click();
};

$("export-csv").onclick = () => {
  const head = ["model", "conversation_id", "language", "status", "score", "cost_usd", "duration_ms", "input_tokens", "output_tokens", "reasoning_tokens", "error_code"];
  const lines = [head.join(",")];
  for (const r of experimentRows()) {
    const cells = [r.model, r.conversation_id, r.language, r.status, r.score ?? "", r.usage?.provider_cost_usd ?? "",
      r.duration_ms ?? "", r.usage?.input_tokens ?? "", r.usage?.output_tokens ?? "", r.usage?.reasoning_tokens ?? "", r.error?.code ?? ""];
    lines.push(cells.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(","));
  }
  const blob = new Blob([lines.join("\n")], { type: "text/csv" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${DATA.experiment_id}-report.csv`;
  a.click();
};

boot();
