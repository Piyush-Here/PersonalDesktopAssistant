let currentSessionId = null;
let waitingForConfirmation = false;

const form = document.getElementById("assistant-form");
const responsePanel = document.getElementById("response-panel");
const summary = document.getElementById("summary");
const observations = document.getElementById("observations");
const steps = document.getElementById("steps");
const confirmActions = document.getElementById("confirm-actions");
const execution = document.getElementById("execution");

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = {
    mode: document.getElementById("mode").value,
    text: document.getElementById("text").value.trim(),
  };

  if (!payload.text) {
    return;
  }

  const response = await fetch("/api/request", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  renderReply(data);
});

document.getElementById("approve").addEventListener("click", () => confirmExecution(true));
document.getElementById("reject").addEventListener("click", () => confirmExecution(false));

async function confirmExecution(approved) {
  if (!currentSessionId || !waitingForConfirmation) {
    return;
  }

  const response = await fetch("/api/confirm", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: currentSessionId, approved }),
  });
  const data = await response.json();
  renderReply(data);
}

function renderReply(data) {
  currentSessionId = data.session_id;
  waitingForConfirmation = data.plan.requires_confirmation && !data.execution_result;
  responsePanel.classList.remove("hidden");

  summary.innerHTML = `<div class="card"><strong>Summary</strong><p>${escapeHtml(data.summary)}</p></div>`;

  const observationItems = data.observations.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  observations.innerHTML = `<div class="card"><strong>Observations</strong><ul>${observationItems}</ul></div>`;

  const stepCards = data.plan.steps.map((step) => `
    <div class="card">
      <strong>${escapeHtml(step.description)}</strong>
      <p class="meta">Tool: ${escapeHtml(step.tool)} | Risk: ${escapeHtml(step.risk_level)} | Status: ${escapeHtml(step.status)}</p>
      <p>${escapeHtml(step.preview || "")}</p>
    </div>
  `).join("");
  steps.innerHTML = `<div><strong>Plan</strong></div>${stepCards}`;

  confirmActions.classList.toggle("hidden", !waitingForConfirmation);

  if (data.execution_result) {
    const detailItems = (data.execution_result.details || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
    execution.innerHTML = `
      <div class="card">
        <strong>Execution</strong>
        <p>${escapeHtml(data.execution_result.message)}</p>
        <ul>${detailItems}</ul>
      </div>
    `;
  } else {
    execution.innerHTML = "";
  }
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
