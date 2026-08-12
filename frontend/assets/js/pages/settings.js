import { api, clearSession } from "../api.js";
import { escapeHtml, toast } from "../ui.js";

const COMPONENT_LABELS = {
  vector_database: "Vector Database",
  embedding_model: "Embedding Model",
  groq_llm: "Groq LLM",
  knowledge_base: "Knowledge Base",
  response_cache: "Response Cache",
  api: "API",
};
const OK_STATES = new Set(["online", "loaded", "ready", "connected", "active"]);

export async function renderSettings(root, user, onLogout) {
  root.innerHTML = `<div class="page-pad"><div class="spin-loader">Loading system status…</div></div>`;

  let status = null;
  try { status = await api.systemStatus(); } catch (e) { /* handled below */ }

  root.innerHTML = `
    <div class="page-pad">
      <div class="section-title">Settings</div>
      <div class="section-sub">Workspace, account, and system status.</div>

      <div class="grid-2" style="align-items:start">
        <div class="card card-pad">
          <div class="card-title">Account</div>
          <div class="analysis-row"><span class="k">Name</span><span class="v">${escapeHtml(user.name)}</span></div>
          <div class="analysis-row"><span class="k">Email</span><span class="v">${escapeHtml(user.email)}</span></div>
          <div class="analysis-row"><span class="k">Role</span><span class="v" style="text-transform:capitalize">${escapeHtml(user.role)}</span></div>
          <div class="analysis-row"><span class="k">Organization</span><span class="v">${escapeHtml(user.org_id)}</span></div>
          <button class="btn btn-danger btn-block" id="logout-btn" style="margin-top:16px">Sign Out</button>
        </div>

        <div class="card card-pad">
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:2px">
            <div class="card-title">System Status</div>
            <span class="badge ${status && status.overall === "operational" ? "badge-l1" : "badge-l2"}">${status ? status.overall.toUpperCase() : "UNKNOWN"}</span>
          </div>
          <div class="card-subtitle">Live health of each backend component</div>
          ${status ? Object.entries(status.components).map(([k, v]) => `
            <div class="analysis-row">
              <span class="k">${COMPONENT_LABELS[k] || k}</span>
              <span class="v" style="display:flex;align-items:center;gap:6px">
                <span class="dot ${OK_STATES.has(v) ? "ok" : "warn"}"></span>${escapeHtml(v.replace(/_/g, " "))}
              </span>
            </div>
          `).join("") : `<div class="error-state"><h3>Status unavailable</h3><p>Couldn't reach the system status endpoint.</p></div>`}
        </div>
      </div>
    </div>
  `;

  root.querySelector("#logout-btn").addEventListener("click", () => {
    clearSession();
    toast("Signed out.");
    onLogout();
  });
}
