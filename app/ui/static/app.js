/* ── State ──────────────────────────────────────────────────── */
let pendingSession = null;

/* ── DOM refs ───────────────────────────────────────────────── */
const chatHistory  = document.getElementById("chat-history");
const textarea     = document.getElementById("text");
const sendBtn      = document.getElementById("send-btn");
const sendLabel    = document.getElementById("send-label");
const sendSpinner  = document.getElementById("send-spinner");
const modeSelect   = document.getElementById("mode");
const llmBadge     = document.getElementById("llm-badge");
const capsList     = document.getElementById("caps-list");

/* ── Boot ───────────────────────────────────────────────────── */
window.addEventListener("DOMContentLoaded", () => {
  loadLLMStatus();
  loadCapabilities();
  renderWelcome();

  sendBtn.addEventListener("click", handleSend);
  textarea.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }
  });

  document.querySelectorAll(".example-btn").forEach((btn) => {
    btn.addEventListener("click", () => { textarea.value = btn.dataset.text; textarea.focus(); });
  });
});

/* ── LLM badge ──────────────────────────────────────────────── */
async function loadLLMStatus() {
  try {
    const res = await fetch("/api/llm/status");
    if (!res.ok) throw new Error();
    const data = await res.json();
    llmBadge.className = data.llm_active ? "badge badge-llm" : "badge badge-det";
    llmBadge.textContent = data.llm_active ? `LLM · ${data.model || "ollama"}` : "Deterministic";
  } catch {
    llmBadge.className = "badge badge-loading";
    llmBadge.textContent = "offline";
  }
}

/* ── Capabilities ───────────────────────────────────────────── */
async function loadCapabilities() {
  try {
    const res  = await fetch("/api/capabilities");
    if (!res.ok) throw new Error();
    const caps = await res.json();
    const items = [
      { key: "screenshot",      label: "Screenshot" },
      { key: "desktop_actions", label: "Desktop actions" },
      { key: "ui_automation",   label: "UI automation" },
      { key: "ocr",             label: "OCR" },
    ];
    capsList.innerHTML = items.map(({ key, label }) => {
      const on = caps[key] === true;
      return `<span class="cap-item ${on ? "cap-yes" : "cap-no"}">${label}: ${on ? "on" : "off"}</span>`;
    }).join("") + (caps.pdf_engine
      ? `<span class="cap-item cap-yes">PDF: ${caps.pdf_engine}</span>`
      : `<span class="cap-item cap-no">PDF: none</span>`);
  } catch {
    capsList.innerHTML = `<span class="cap-item cap-loading">unavailable</span>`;
  }
}

/* ── Welcome ────────────────────────────────────────────────── */
function renderWelcome() {
  chatHistory.innerHTML = `
    <div class="welcome">
      <img src="/static/icon.svg" alt="" style="width:48px;height:48px;opacity:0.6">
      <h2>Personal Desktop Assistant</h2>
      <p>Give me an instruction in plain English — single step or a full chain like<br>
      <em>"Open Notepad, type Hello World, then save it"</em>.<br>
      I'll plan every step, score the risk, and only act after your approval.</p>
    </div>`;
}

/* ── Send handler ───────────────────────────────────────────── */
async function handleSend() {
  const text = textarea.value.trim();
  if (!text || sendBtn.disabled) return;

  if (chatHistory.querySelector(".welcome")) chatHistory.innerHTML = "";

  textarea.value = "";
  setBusy(true);

  const turnEl = document.createElement("div");
  turnEl.className = "chat-turn";
  turnEl.innerHTML = `<div class="bubble-user">${escHtml(text)}</div>`;
  chatHistory.appendChild(turnEl);
  scrollBottom();

  const thinkEl = document.createElement("div");
  thinkEl.className = "bubble-assistant";
  thinkEl.innerHTML = `<span style="color:var(--muted);font-size:0.85rem">Thinking…</span>`;
  turnEl.appendChild(thinkEl);
  scrollBottom();

  try {
    const res = await fetch("/api/request", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, mode: modeSelect.value }),
    });
    if (!res.ok) throw new Error(await res.text() || `HTTP ${res.status}`);
    const data = await res.json();
    turnEl.removeChild(thinkEl);
    renderReply(data, turnEl);
  } catch (err) {
    thinkEl.innerHTML = `<span style="color:var(--danger);font-size:0.85rem">✗ ${escHtml(String(err))}</span>`;
  } finally {
    setBusy(false);
    scrollBottom();
  }
}

/* ── Render assistant reply ─────────────────────────────────── */
function renderReply(data, turnEl) {
  const risk    = data.plan.risk_assessment;
  const waiting = data.plan.requires_confirmation && !data.execution_result;
  const isChain = data.plan.is_chain;

  if (waiting) pendingSession = { sessionId: data.session_id, turnEl };

  const bubble = document.createElement("div");
  bubble.className = "bubble-assistant";
  bubble.dataset.sessionId = data.session_id;

  // Summary
  bubble.innerHTML += `<div class="reply-summary">${escHtml(data.summary)}</div>`;

  // Risk bar
  const rl = risk.level;
  bubble.innerHTML += `
    <div class="risk-bar">
      <span class="risk-score risk-${rl}">Risk ${risk.score}/100 · ${rl.toUpperCase()}</span>
    </div>
    <ul class="risk-reasons">
      ${(risk.reasons || []).map(r => `<li>${escHtml(r)}</li>`).join("")}
    </ul>`;

  // Plan steps — chain vs single
  if (data.plan.steps && data.plan.steps.length) {
    const stepsDiv = document.createElement("div");
    stepsDiv.id = `steps-${data.session_id}`;

    if (isChain) {
      stepsDiv.innerHTML = `<div class="chain-header">Chain · ${data.plan.steps.length} steps</div>`;
      const chainEl = document.createElement("div");
      chainEl.className = "chain-steps";
      data.plan.steps.forEach((step, idx) => {
        const row = document.createElement("div");
        row.className = "chain-step-row";
        if (idx > 0) {
          const conn = document.createElement("div");
          conn.className = "chain-connector";
          conn.id = `conn-${data.session_id}-${idx}`;
          row.appendChild(conn);
        }
        row.appendChild(buildStepCard(step, data.session_id, true));
        chainEl.appendChild(row);
      });
      stepsDiv.appendChild(chainEl);
    } else {
      stepsDiv.innerHTML = `<div class="step-header">Planned steps</div>`;
      data.plan.steps.forEach(step => stepsDiv.appendChild(buildStepCard(step, data.session_id, false)));
    }

    bubble.appendChild(stepsDiv);
  }

  // Observations (collapsible)
  if (data.observations && data.observations.length) {
    const obsId = `obs-${data.session_id}`;
    bubble.innerHTML += `
      <div>
        <button class="observations-toggle" onclick="toggleObs('${obsId}')">
          Show observations (${data.observations.length})
        </button>
        <ul class="observations-body hidden" id="${obsId}">
          ${data.observations.map(o => `<li>${escHtml(o)}</li>`).join("")}
        </ul>
      </div>`;
  }

  // Confirmation gate
  if (waiting) {
    const confirmId = `confirm-${data.session_id}`;
    const chainMsg = isChain
      ? `<p style="font-size:0.8rem;color:var(--muted)">This is a ${data.plan.steps.length}-step chain. All steps will execute in sequence after you approve.</p>`
      : `<p style="font-size:0.8rem;color:var(--muted)">Review the plan above. Approve to execute or cancel to abort.</p>`;
    bubble.innerHTML += `
      <div class="confirm-block" id="${confirmId}">
        <div class="confirm-label">⚠ Confirmation required${isChain ? " — chain of " + data.plan.steps.length + " steps" : ""}</div>
        ${chainMsg}
        <div class="confirm-actions">
          <button class="btn btn-approve"
            onclick="confirmExecution('${data.session_id}', true, '${confirmId}', this.closest('.bubble-assistant'))">
            ✓ Confirm &amp; Execute${isChain ? " Chain" : ""}
          </button>
          <button class="btn btn-reject"
            onclick="confirmExecution('${data.session_id}', false, '${confirmId}', this.closest('.bubble-assistant'))">
            ✕ Cancel
          </button>
        </div>
      </div>`;
  }

  // Already-available result (read-only auto-exec)
  if (data.execution_result) {
    appendExecResult(bubble, data.execution_result, data.plan.steps);
  }

  turnEl.appendChild(bubble);
}

/* ── Build a single step card ───────────────────────────────── */
function buildStepCard(step, sessionId, isChain) {
  const card = document.createElement("div");
  card.className = "step-card";
  card.id = `step-${step.id}`;

  const numClass = { completed: "num-done", failed: "num-failed", running: "num-running" }[step.status] || "";
  card.innerHTML = `
    <div class="step-title">
      ${isChain ? `<span class="step-num ${numClass}" id="stepnum-${step.id}">${step.sequence_index + 1}</span>` : ""}
      ${escHtml(step.description)}
      <span class="status-pill status-${step.status}" id="steppill-${step.id}">${step.status}</span>
    </div>
    <div class="step-meta">tool: ${escHtml(step.tool)} &nbsp;|&nbsp; risk: ${step.risk_score}/100</div>
    ${step.preview ? `<div class="step-preview">${escHtml(step.preview)}</div>` : ""}
    ${step.result_key ? `<div class="context-badge">→ outputs ${step.result_key}</div>` : ""}
    <div class="step-result-detail" id="stepdetail-${step.id}" style="display:none"></div>`;
  return card;
}

/* ── Confirm / reject ───────────────────────────────────────── */
async function confirmExecution(sessionId, approved, confirmId, bubbleEl) {
  const confirmBlock = document.getElementById(confirmId);
  if (confirmBlock) confirmBlock.innerHTML = `<span style="color:var(--muted);font-size:0.82rem">${approved ? "Executing chain…" : "Canceling…"}</span>`;

  const beforeObs = extractObservationText(bubbleEl);

  try {
    const res = await fetch("/api/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, approved }),
    });
    if (!res.ok) throw new Error(await res.text() || `HTTP ${res.status}`);
    const data = await res.json();

    if (confirmBlock) confirmBlock.remove();

    if (data.execution_result) {
      // Update each step card with its result
      if (data.plan && data.plan.steps) {
        updateStepCards(data.plan.steps, data.execution_result.step_results || []);
      }
      appendExecResult(bubbleEl, data.execution_result, data.plan ? data.plan.steps : []);

      // Before/after diff
      if (approved && data.observations && data.observations.length) {
        appendDiff(bubbleEl, beforeObs, data.observations);
      }
    }
  } catch (err) {
    if (confirmBlock) confirmBlock.innerHTML = `<span style="color:var(--danger);font-size:0.82rem">✗ Failed: ${escHtml(String(err))}</span>`;
  }

  scrollBottom();
}

/* ── Update step cards after chain executes ─────────────────── */
function updateStepCards(steps, stepResults) {
  steps.forEach((step, idx) => {
    const card   = document.getElementById(`step-${step.id}`);
    const pill   = document.getElementById(`steppill-${step.id}`);
    const num    = document.getElementById(`stepnum-${step.id}`);
    const detail = document.getElementById(`stepdetail-${step.id}`);
    const conn   = document.getElementById(`conn-${step.id}-${idx}`);  // connector above

    if (pill) {
      pill.className = `status-pill status-${step.status}`;
      pill.textContent = step.status;
    }
    if (card) {
      card.className = `step-card ${
        step.status === "completed" ? "step-done" :
        step.status === "failed"    ? "step-failed" :
        step.status === "blocked"   ? "step-blocked" : ""
      }`;
    }
    if (num) {
      num.className = `step-num ${
        step.status === "completed" ? "num-done" :
        step.status === "failed"    ? "num-failed" : ""
      }`;
    }

    // Show per-step result message
    const sr = stepResults[idx];
    if (detail && sr) {
      const ok = sr.status === "completed";
      detail.className = `step-result-detail ${ok ? "ok" : "err"}`;
      detail.textContent = sr.message;
      if (sr.details && sr.details.length) {
        detail.textContent += " — " + sr.details.slice(0, 2).join(" | ");
      }
      detail.style.display = "block";
    }

    // Update chain connector color
    if (conn) {
      conn.className = `chain-connector ${
        step.status === "completed" ? "completed" :
        step.status === "failed"    ? "failed" : ""
      }`;
    }
  });
}

/* ── Append execution result ────────────────────────────────── */
function appendExecResult(bubbleEl, result, steps) {
  const cls  = result.success ? "exec-success" : "exec-failure";
  const icon = result.success ? "✓" : "✗";
  const div  = document.createElement("div");
  div.className = `exec-result ${cls}`;

  // Show chain context if present
  let ctxHtml = "";
  if (result.chain_context && Object.keys(result.chain_context).length) {
    const entries = Object.entries(result.chain_context)
      .map(([k, v]) => `<li>${escHtml(k)}: ${escHtml(String(v))}</li>`)
      .join("");
    ctxHtml = `<details style="margin-top:6px"><summary style="font-size:0.72rem;cursor:pointer;color:var(--muted)">Chain context</summary><ul style="margin-top:4px">${entries}</ul></details>`;
  }

  div.innerHTML = `
    <strong>${icon} ${escHtml(result.message)}</strong>
    ${ctxHtml}`;
  bubbleEl.appendChild(div);
}

/* ── Before/after diff ──────────────────────────────────────── */
function extractObservationText(bubbleEl) {
  if (!bubbleEl) return "";
  return Array.from(bubbleEl.querySelectorAll(".observations-body li"))
    .map(li => li.textContent).join("\n");
}

function appendDiff(bubbleEl, before, afterObs) {
  const after = afterObs.join("\n");
  if (!before && !after) return;
  const div = document.createElement("div");
  div.className = "diff-block";
  div.innerHTML = `
    <div class="diff-label">Before / After</div>
    <div class="diff-row">
      <div><div class="diff-pane-label">Before</div>
           <div class="diff-pane">${escHtml(before || "(no observation)")}</div></div>
      <div><div class="diff-pane-label">After</div>
           <div class="diff-pane">${escHtml(after || "(no observation)")}</div></div>
    </div>`;
  bubbleEl.appendChild(div);
}

/* ── Settings modal ─────────────────────────────────────────── */
function openSettings() {
  document.getElementById("settings-overlay").classList.remove("hidden");
}
function closeSettings(event) {
  if (event && event.target !== document.getElementById("settings-overlay")) return;
  document.getElementById("settings-overlay").classList.add("hidden");
}
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") document.getElementById("settings-overlay").classList.add("hidden");
});

/* ── Helpers ────────────────────────────────────────────────── */
function toggleObs(id) {
  const el  = document.getElementById(id);
  const btn = el.previousElementSibling;
  el.classList.toggle("hidden");
  btn.textContent = el.classList.contains("hidden")
    ? btn.textContent.replace("Hide", "Show")
    : btn.textContent.replace("Show", "Hide");
}

function setBusy(busy) {
  sendBtn.disabled = busy;
  sendLabel.classList.toggle("hidden", busy);
  sendSpinner.classList.toggle("hidden", !busy);
  textarea.disabled = busy;
}

function scrollBottom() {
  requestAnimationFrame(() => { chatHistory.scrollTop = chatHistory.scrollHeight; });
}

function escHtml(val) {
  return String(val)
    .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
    .replace(/"/g,"&quot;").replace(/'/g,"&#039;");
}
