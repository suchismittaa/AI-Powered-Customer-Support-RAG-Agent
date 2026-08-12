import { api } from "../api.js";
import { escapeHtml, fmtDate, priorityBadge, openModal, closeModal, toast, icon } from "../ui.js";

export async function renderTickets(root) {
  root.innerHTML = `<div class="page-pad"><div class="spin-loader">Loading tickets…</div></div>`;

  let filters = { status: "", priority: "", category: "", search: "" };

  async function load() {
    const [kpis, listData] = await Promise.all([
      api.ticketsKpis().catch(() => ({ open: 0, l2: 0, critical: 0, resolved: 0 })),
      api.ticketsList(filters).catch(() => ({ tickets: [] })),
    ]);
    paint(kpis, listData.tickets || []);
  }

  function paint(kpis, list) {
    root.innerHTML = `
      <div class="page-pad">
        <div class="section-title">Support Tickets</div>
        <div class="section-sub">Escalations created from L2 triage and manual reviews.</div>

        <div class="kpi-row">
          <div class="kpi"><div class="kpi-label">Open</div><div class="kpi-value">${kpis.open}</div></div>
          <div class="kpi"><div class="kpi-label">Total</div><div class="kpi-value">${kpis.l2}</div></div>
          <div class="kpi"><div class="kpi-label">Critical</div><div class="kpi-value danger">${kpis.critical}</div></div>
          <div class="kpi"><div class="kpi-label">Resolved</div><div class="kpi-value accent">${kpis.resolved}</div></div>
        </div>

        <div class="toolbar">
          <input class="input" id="tk-search" placeholder="Search tickets…" value="${escapeHtml(filters.search)}" />
          <select class="select" id="tk-status-filter">
            <option value="">All statuses</option>
            <option value="open">Open</option>
            <option value="in_progress">In progress</option>
            <option value="ai_resolved">AI resolved</option>
            <option value="resolved">Resolved</option>
            <option value="closed">Closed</option>
          </select>
          <select class="select" id="tk-priority-filter">
            <option value="">All priorities</option>
            <option value="critical">Critical</option><option value="high">High</option>
            <option value="normal">Normal</option><option value="low">Low</option>
          </select>
          <select class="select" id="tk-category-filter">
            <option value="">All categories</option>
            <option value="billing">Billing</option><option value="account">Account</option>
            <option value="shipping">Shipping</option><option value="technical">Technical</option>
            <option value="security">Security</option><option value="general">General</option>
          </select>
        </div>

        <div class="card">
          ${list.length ? renderTable(list) : renderEmpty()}
        </div>
      </div>
    `;

    root.querySelector("#tk-status-filter").value = filters.status;
    root.querySelector("#tk-priority-filter").value = filters.priority;
    root.querySelector("#tk-category-filter").value = filters.category;

    let searchTimer;
    root.querySelector("#tk-search").addEventListener("input", (e) => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => { filters.search = e.target.value; load(); }, 350);
    });
    root.querySelector("#tk-status-filter").addEventListener("change", (e) => { filters.status = e.target.value; load(); });
    root.querySelector("#tk-priority-filter").addEventListener("change", (e) => { filters.priority = e.target.value; load(); });
    root.querySelector("#tk-category-filter").addEventListener("change", (e) => { filters.category = e.target.value; load(); });

    root.querySelectorAll("tbody tr[data-id]").forEach(tr => {
      tr.addEventListener("click", () => openTicketDetail(Number(tr.dataset.id)));
    });
  }

  function renderTable(list) {
    return `
      <div class="table-wrap">
        <table class="data-table">
          <thead><tr>
            <th>Ticket</th><th>Issue</th><th>Category</th><th>Priority</th><th>Status</th><th>Created</th>
          </tr></thead>
          <tbody>
            ${list.map(t => `
              <tr data-id="${t.id}">
                <td class="mono">#${escapeHtml(t.ticket_number)}</td>
                <td>${escapeHtml(t.query.slice(0, 60))}${t.query.length > 60 ? "…" : ""}</td>
                <td style="text-transform:capitalize">${escapeHtml(t.category)}</td>
                <td>${priorityBadge(t.priority)}</td>
                <td>${statusBadge(t.status)}</td>
                <td class="mono">${fmtDate(t.created_at)}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    `;
  }

  function renderEmpty() {
    return `
      <div class="empty-state">
        ${icon.ticket}
        <h3>No support tickets yet.</h3>
        <p>Tickets created from L2 escalations will appear here.</p>
      </div>
    `;
  }

  async function openTicketDetail(id) {
    const t = await api.getTicket(id);
    const overlay = openModal(`
      <div class="modal">
        <div class="modal-header">
          <h3>Ticket #${escapeHtml(t.ticket_number)}</h3>
          <div class="icon-btn" id="modal-close">✕</div>
        </div>
        <div class="modal-body">
          <div style="display:flex;gap:8px;margin-bottom:16px">${priorityBadge(t.priority)}<span class="badge badge-neutral" style="text-transform:capitalize">${escapeHtml(t.category)}</span>${statusBadge(t.status)}</div>
          <div class="field"><label>Customer query</label><div class="modal-info-box">${escapeHtml(t.query)}</div></div>
          ${t.ai_summary ? `<div class="field"><label>AI-generated summary</label><div class="modal-info-box">${escapeHtml(t.ai_summary)}</div></div>` : ""}
          ${t.suggested_response ? `<div class="field"><label>Suggested response</label><div class="modal-info-box">${escapeHtml(t.suggested_response)}</div></div>` : ""}
          ${t.triage_reason ? `<div class="field"><label>Escalation reason</label><div class="modal-info-box">${escapeHtml(t.triage_reason)}</div></div>` : ""}
          <div class="field"><label>Update status</label>
            <select class="select" id="tk-status-update">
              <option value="open">Open</option><option value="in_progress">In progress</option>
              <option value="ai_resolved">AI resolved</option><option value="resolved">Resolved</option>
              <option value="closed">Closed</option>
            </select>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" id="modal-cancel">Close</button>
          <button class="btn btn-primary" id="modal-save">Save Status</button>
        </div>
      </div>
    `);
    overlay.querySelector("#tk-status-update").value = t.status;
    overlay.querySelector("#modal-close").addEventListener("click", closeModal);
    overlay.querySelector("#modal-cancel").addEventListener("click", closeModal);
    overlay.querySelector("#modal-save").addEventListener("click", async () => {
      const status = overlay.querySelector("#tk-status-update").value;
      try {
        await api.updateTicketStatus(t.id, status);
        toast("Ticket updated.");
        closeModal();
        load();
      } catch (e) { toast(e.message, "error"); }
    });
  }

  function statusBadge(status) {
    const map = {
      open: ["badge-l2", "Open"],
      in_progress: ["badge-neutral", "In progress"],
      ai_resolved: ["badge-l1", "AI Resolved"],
      resolved: ["badge-l1", "Resolved"],
      closed: ["badge-neutral", "Closed"],
    };
    const [cls, label] = map[status] || ["badge-neutral", status];
    return `<span class="badge ${cls}">${label}</span>`;
  }

  load();
}
