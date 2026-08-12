import { api, isAuthed, getUser, clearSession } from "./api.js";
import { icon, escapeHtml, openModal, closeModal } from "./ui.js";
import { renderLogin } from "./pages/login.js";
import { renderChat } from "./pages/chat.js";
import { renderTickets } from "./pages/tickets.js";
import { renderAnalytics } from "./pages/analytics.js";
import { renderEvaluation } from "./pages/evaluation.js";
import { renderKB } from "./pages/kb.js";
import { renderSettings } from "./pages/settings.js";

const NAV_ITEMS = [
  { key: "chat", label: "Chat", icon: icon.chat },
  { key: "tickets", label: "Tickets", icon: icon.ticket },
  { key: "analytics", label: "Analytics", icon: icon.chart },
  { key: "evaluation", label: "Evaluation", icon: icon.check },
  { key: "kb", label: "Knowledge Base", icon: icon.book },
];
const PAGE_META = {
  chat: { title: "Customer Support", sub: "Ask a question — grounded in your knowledge base" },
  tickets: { title: "Support Tickets", sub: "Escalations and human-review queue" },
  analytics: { title: "Analytics", sub: "Support operations performance" },
  evaluation: { title: "RAG Evaluation", sub: "Quality control for the retrieval pipeline" },
  kb: { title: "Knowledge Base", sub: "Document ingestion and index health" },
  settings: { title: "Settings", sub: "Workspace, account, and system status" },
};

const app = document.getElementById("app");

function currentRoute() {
  const h = window.location.hash.replace("#/", "") || "chat";
  return NAV_ITEMS.some(n => n.key === h) || h === "settings" ? h : "chat";
}

function boot() {
  if (!isAuthed()) {
    renderLogin(app, () => { window.location.hash = "#/chat"; boot(); });
    return;
  }
  renderShell();
}

function renderShell() {
  const user = getUser();
  app.innerHTML = `
    <div class="app-shell">
      <aside class="sidebar" id="sidebar">
        <div class="sidebar-brand">
          <div class="mark">S</div>
          <div class="name">SUPPORTAI</div>
        </div>
        <div class="nav-label">Workspace</div>
        <ul class="nav-list" id="nav-list"></ul>
        <div class="nav-label">Administration</div>
        <ul class="nav-list">
          <li class="nav-item" data-key="settings">${icon.settings}<span>Settings</span></li>
        </ul>
        <div class="sidebar-footer">
          <div class="workspace-pill"><span>${escapeHtml(user.org_id)}</span><span class="dot ok"></span></div>
          <div class="user-row">
            <div class="avatar">${escapeHtml((user.name || "?").slice(0, 1).toUpperCase())}</div>
            <div class="user-meta">
              <div class="u-name">${escapeHtml(user.name)}</div>
              <div class="u-role">${escapeHtml(user.role)}</div>
            </div>
            <div class="icon-btn" id="logout-icon" title="Sign out">${icon.logout}</div>
          </div>
        </div>
      </aside>
      <div class="main">
        <div class="topbar">
          <div>
            <div class="topbar-title" id="topbar-title">Customer Support</div>
            <div class="topbar-sub" id="topbar-sub">Ask a question — grounded in your knowledge base</div>
          </div>
          <div class="status-pill" id="status-pill"><span class="dot" id="status-dot"></span><span id="status-text">Checking status…</span></div>
        </div>
        <div class="page" id="page-outlet"></div>
      </div>
    </div>
  `;

  const navList = document.getElementById("nav-list");
  NAV_ITEMS.forEach(item => {
    const li = document.createElement("li");
    li.className = "nav-item";
    li.dataset.key = item.key;
    li.innerHTML = `${item.icon}<span>${item.label}</span>`;
    navList.appendChild(li);
  });

  document.querySelectorAll(".nav-item").forEach(el => {
    el.addEventListener("click", () => { window.location.hash = `#/${el.dataset.key}`; });
  });
  document.getElementById("logout-icon").addEventListener("click", () => {
    clearSession();
    boot();
  });
  document.getElementById("status-pill").addEventListener("click", showStatusPopover);

  refreshStatusPill();
  renderRoute();
  window.addEventListener("hashchange", renderRoute);
}

async function refreshStatusPill() {
  const dot = document.getElementById("status-dot");
  const text = document.getElementById("status-text");
  if (!dot || !text) return;
  try {
    const s = await api.systemStatus();
    const ok = s.overall === "operational";
    dot.className = `dot ${ok ? "ok" : "warn"}`;
    text.textContent = ok ? "AI ENGINE OPERATIONAL" : "DEGRADED — CHECK STATUS";
  } catch (e) {
    dot.className = "dot bad";
    text.textContent = "STATUS UNAVAILABLE";
  }
}

async function showStatusPopover() {
  const overlay = openModal(`
    <div class="modal" style="width:380px">
      <div class="modal-header"><h3>System Status</h3><div class="icon-btn" id="modal-close">✕</div></div>
      <div class="modal-body" id="status-modal-body"><div class="spin-loader">Checking components…</div></div>
    </div>
  `);
  overlay.querySelector("#modal-close").addEventListener("click", closeModal);
  try {
    const s = await api.systemStatus();
    const labels = {
      vector_database: "Vector Database", embedding_model: "Embedding Model",
      groq_llm: "Groq LLM", knowledge_base: "Knowledge Base",
      response_cache: "Response Cache", api: "API",
    };
    const ok = new Set(["online", "loaded", "ready", "connected", "active"]);
    document.getElementById("status-modal-body").innerHTML = Object.entries(s.components).map(([k, v]) => `
      <div class="analysis-row">
        <span class="k">${labels[k] || k}</span>
        <span class="v" style="display:flex;align-items:center;gap:6px"><span class="dot ${ok.has(v) ? "ok" : "warn"}"></span>${escapeHtml(v.replace(/_/g, " "))}</span>
      </div>
    `).join("");
  } catch (e) {
    document.getElementById("status-modal-body").innerHTML = `<div class="error-state"><h3>Status unavailable</h3><p>Couldn't reach the API.</p></div>`;
  }
}

function renderRoute() {
  const route = currentRoute();
  document.querySelectorAll(".nav-item").forEach(el => el.classList.toggle("active", el.dataset.key === route));
  const meta = PAGE_META[route];
  document.getElementById("topbar-title").textContent = meta.title;
  document.getElementById("topbar-sub").textContent = meta.sub;

  const outlet = document.getElementById("page-outlet");
  outlet.innerHTML = "";
  const user = getUser();

  switch (route) {
    case "chat": renderChat(outlet); break;
    case "tickets": renderTickets(outlet); break;
    case "analytics": renderAnalytics(outlet); break;
    case "evaluation": renderEvaluation(outlet, user); break;
    case "kb": renderKB(outlet, user); break;
    case "settings": renderSettings(outlet, user, () => { boot(); }); break;
    default: renderChat(outlet);
  }
}

boot();
