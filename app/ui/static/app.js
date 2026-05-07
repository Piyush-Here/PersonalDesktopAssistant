/* ── State ──────────────────────────────────────────────────── */
let pendingSession = null;   // { sessionId, turnEl }

/* ── DOM refs ───────────────────────────────────────────────── */
const chatHistory = document.getElementById("chat-history");
const textarea    = document.getElementById("text");
const sendBtn     = document.getElementById("send-btn");
const sendLabel   = document.getElementById("send-label");
const sendSpinner = document.getElementById("send-spinner");
const modeSelect  = document.getElementById("mode");
const llmBadge    = document.getElementById("llm-badge");

/* ── Boot ───────────────────────────────────────────────────── */
window.addEventListener("DOMContentLoaded", () => {
  loadLLMStatus();
  renderWelcome();

  sendBtn.addEventListener("click", handleSend);
  textarea.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  });

  // Example sidebar buttons
  document.querySelectorAll(".example-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      textarea.value = btn.dataset.text;
      textarea.focus();
    });
  });
});

/* ── LLM status badge ───────────────────────────────────────── */
async function loadLLMStatus() {
  try {
    const res  = await fetch("/api/llm/status");
    const data = await res.json();
    if (data.llm_active) {
      llmBadge.className = "badge badge-llm";
      llmBadge.textContent = `LLM · ${data.model || "ollama"}`;
    } else {
      llmBadge.className = "badge badge-det";
      llmBadge.textContent = "Deterministic";
    }
  } catch {
    llmBadge.className = "badge badge-loading";
    llmBadge.textContent = "offline";
  }
}

/* ── Welcome placeholder ────────────────────────────────────── */
function renderWelcome() {
  chatHistory.innerHTML = `
    <div class="welcome">
      <div class="welcome-icon">⬡</div>
      <h2>Personal Desktop Assistant</h2>
      <p>Give me an instruction in plain English. I'll plan what to do,
         show you the risk score, and only act after your confirmation.</p>
    </div>`;
}

/* ── Send handler ───────────────────────────────────────────── */
async function handleSend() {
  const text = textarea.value.trim();
  if (!text) return;
  if (sendBtn.disabled) return;

  // Clear welcome
  if (chatHistory.querySelector(".welcome")) chatHistory.innerHTML = "";

  const mode = modeSelect.value;
  textarea.value = "";

  setBusy(true);

  // Append user bubble
  const turnEl = document.createElement("div");
  turnEl.className = "chat-turn";
  turnEl.innerHTML = `<div class="bubble-user">${escHtml(text)}</div>`;
  chatHistory.appendChild(turnEl);
  scrollBottom();

  // Thinking placeholder
  const thinkEl = document.createElement("div");
  thinkEl.className = "bubble-assistant";
  thinkEl.innerHTML = `<span style="color:var(--muted);font-size:0.85rem">Thinking…</span>`;
  turnEl.appendChild(thinkEl);
  scrollBottom();

  try {
    const res  = await fetch("/api/request", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, mode }),
    });
    const data = await res.json();

    // Replace placeholder
    turnEl.removeChild(thinkEl);
    renderReply(data, turnEl);
  } catch (err) {
    thinkEl.innerHTML = `<span style="color:var(--danger);font-size:0.85rem">Request failed: ${escHtml(String(err))}</span>`;
  } finally {
    setBusy(false);
    scrollBottom();
  }
}

/* ── Render full assistant reply ────────────────────────────── */
function renderReply(data, turnEl) {
  const risk    = data.plan.risk_assessment;
  const waiting = data.plan.requires_confirmation && !data.execution_result;

  if (waiting) {
    pendingSession = { sessionId: data.session_id, turnEl };
  }

  const assistantBubble = document.createElement("div");
  assistantBubble.className = "bubble-assistant";

  // Summary
  assistantBubble.innerHTML += `<div class="reply-summary">${escHtml(data.summary)}</div>`;

  // Risk bar
  const rl = risk.level;
  assistantBubble.innerHTML += `
    <div class="risk-bar">
      <span class="risk-score risk-${rl}">Risk ${risk.score}/100 · ${rl.toUpperCase()}</span>
    </div>
    <ul class="risk-reasons">
      ${(risk.reasons || []).map(r => `<li>${escHtml(r)}</li>`).join("")}
    </ul>`;

  // Plan steps
  if (data.plan.steps && data.plan.steps.length) {
    const stepsHtml = data.plan.steps.map(step => `
      <div class="step-card">
        <div class="step-title">
          ${escHtml(step.description)}
          <span class="status-pill status-${step.status}">${step.status}</span>
        </div>
        <div class="step-meta">tool: ${escHtml(step.tool)} &nbsp;|&nbsp; risk: ${step.risk_score}/100</div>
        ${step.preview ? `<div class="step-preview">${escHtml(step.preview)}</div>` : ""}
      </div>`).join("");

    assistantBubble.innerHTML += `
      <div class="plan-steps">
        <div class="step-header">Planned steps (${data.plan.steps.length})</div>
        ${stepsHtml}
      </div>`;
  }

  // Observations (collapsible)
  if (data.observations && data.observations.length) {
    const obsId = `obs-${data.session_id}`;
    const obsHtml = data.observations
      .map(o => `<li>${escHtml(o)}</li>`).join("");
    assistantBubble.innerHTML += `
      <div>
        <button class="observations-toggle" onclick="toggleObs('${obsId}')">
          Show observations (${data.observations.length})
        </button>
        <ul class="observations-body hidden" id="${obsId}">${obsHtml}</ul>
      </div>`;
  }

  // Confirmation gate
  if (waiting) {
    const confirmId = `confirm-${data.session_id}`;
    assistantBubble.innerHTML += `
      <div class="confirm-block" id="${confirmId}">
        <div class="confirm-label">⚠ Confirmation required before execution</div>
        <p style="font-size:0.8rem;color:var(--muted)">Review the plan above. Approve to execute, or cancel to abort.</p>
        <div class="confirm-actions">
          <button class="btn btn-approve"
            onclick="confirmExecution('${data.session_id}', true, '${confirmId}', this.closest('.bubble-assistant'))">
            Confirm &amp; Execute
          </button>
          <button class="btn btn-reject"
            onclick="confirmExecution('${data.session_id}', false, '${confirmId}', this.closest('.bubble-assistant'))">
            Cancel
          </button>
        </div>
      </div>`;
  }

  // Execution result (if already available — e.g. read-only auto-exec)
  if (data.execution_result) {
    appendExecResult(assistantBubble, data.execution_result);
  }

  turnEl.appendChild(assistantBubble);
}

/* ── Confirm / reject execution ────────────────────────────── */
async function confirmExecution(sessionId, approved, confirmId, bubbleEl) {
  const confirmBlock = document.getElementById(confirmId);
  if (confirmBlock) {
    confirmBlock.innerHTML = `<span style="color:var(--muted);font-size:0.82rem">${approved ? "Executing…" : "Canceling…"}</span>`;
  }

  try {
    const res  = await fetch("/api/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, approved }),
    });
    const data = await res.json();

    if (confirmBlock) confirmBlock.remove();
    if (data.execution_result && bubbleEl) {
      appendExecResult(bubbleEl, data.execution_result);
    }

    // Update step statuses inline
    if (data.plan && data.plan.steps && bubbleEl) {
      data.plan.steps.forEach((step, i) => {
        const pills = bubbleEl.querySelectorAll(".status-pill");
        if (pills[i]) {
          pills[i].className = `status-pill status-${step.status}`;
          pills[i].textContent = step.status;
        }
      });
    }
  } catch (err) {
    if (confirmBlock) {
      confirmBlock.innerHTML = `<span style="color:var(--danger);font-size:0.82rem">Confirmation failed: ${escHtml(String(err))}</span>`;
    }
  }

  scrollBottom();
}

/* ── Append execution result to a bubble ──────────────────── */
function appendExecResult(bubbleEl, result) {
  const cls   = result.success ? "exec-success" : "exec-failure";
  const icon  = result.success ? "✓" : "✗";
  const items = (result.details || []).map(d => `<li>${escHtml(d)}</li>`).join("");
  const div   = document.createElement("div");
  div.className = `exec-result ${cls}`;
  div.innerHTML = `
    <strong>${icon} ${escHtml(result.message)}</strong>
    ${items ? `<ul>${items}</ul>` : ""}`;
  bubbleEl.appendChild(div);
}

/* ── Helpers ────────────────────────────────────────────────── */
function toggleObs(id) {
  const el = document.getElementById(id);
  const btn = el.previousElementSibling;
  if (el.classList.toggle("hidden")) {
    btn.textContent = btn.textContent.replace("Hide", "Show");
  } else {
    btn.textContent = btn.textContent.replace("Show", "Hide");
  }
}

function setBusy(busy) {
  sendBtn.disabled = busy;
  sendLabel.classList.toggle("hidden", busy);
  sendSpinner.classList.toggle("hidden", !busy);
  textarea.disabled = busy;
}

function scrollBottom() {
  requestAnimationFrame(() => {
    chatHistory.scrollTop = chatHistory.scrollHeight;
  });
}

function escHtml(val) {
  return String(val)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
