import { api } from "../api.js";
import { escapeHtml, icon, toast, openModal, closeModal, triageBadge } from "../ui.js";

const SUGGESTED = [
  { cat: "Account & Login", q: "How do I reset my password?" },
  { cat: "Billing", q: "What payment methods are accepted?" },
  { cat: "Shipping", q: "Where is my package?" },
  { cat: "Refunds", q: "How long does a refund take?" },
];

export async function renderChat(root) {
  let messages = [];
  let lastAnalysis = null; // most recent assistant result, drives the analysis panel
  let sending = false;

  root.innerHTML = `
    <div class="chat-shell">
      <div class="chat-main">
        <div class="chat-scroll" id="chat-scroll"></div>
        <div class="chat-composer">
          <div class="composer-box">
            <textarea id="composer-input" rows="1" placeholder="Ask a customer support question…"></textarea>
            <button class="send-btn" id="send-btn" title="Send">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 2 11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>
            </button>
          </div>
          <div class="composer-note">SupportAI answers are grounded in your knowledge base. Sensitive issues are escalated for human review.</div>
        </div>
      </div>
      <div class="analysis-panel" id="analysis-panel"></div>
    </div>
  `;

  const scrollEl = root.querySelector("#chat-scroll");
  const input = root.querySelector("#composer-input");
  const sendBtn = root.querySelector("#send-btn");
  const panel = root.querySelector("#analysis-panel");

  input.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 130) + "px";
  });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }
  });
  sendBtn.addEventListener("click", handleSend);

  paintAnalysisEmpty();
  await loadHistory();

  async function loadHistory() {
    try {
      const data = await api.conversations(50);
      messages = data.messages || [];
    } catch (e) { /* fine, start empty */ }
    paintMessages();
  }

  function paintAnalysisEmpty() {
    panel.innerHTML = `
      <div class="analysis-label" style="margin-bottom:14px">AI Analysis</div>
      <div class="analysis-empty">
        ${icon.chart}
        <div style="margin-top:10px">Submit a question to see retrieval confidence, classification, and sources here.</div>
      </div>
    `;
  }

  function paintMessages() {
    if (!messages.length) {
      scrollEl.innerHTML = `
        <div class="chat-empty">
          <h2>What can I help with?</h2>
          <p>Ask about billing, accounts, shipping, refunds, or technical issues — answered straight from the knowledge base.</p>
          <div class="suggested-grid" id="suggested-grid"></div>
        </div>
      `;
      const grid = scrollEl.querySelector("#suggested-grid");
      SUGGESTED.forEach(s => {
        const card = document.createElement("div");
        card.className = "suggested-card";
        card.innerHTML = `<div class="cat">${escapeHtml(s.cat)}</div><div class="q">${escapeHtml(s.q)}</div>`;
        card.addEventListener("click", () => { input.value = s.q; handleSend(); });
        grid.appendChild(card);
      });
      return;
    }

    scrollEl.innerHTML = "";
    messages.forEach((m, idx) => {
      if (m.role === "user") {
        scrollEl.insertAdjacentHTML("beforeend", `
          <div class="msg-row user"><div class="msg-bubble">${escapeHtml(m.content)}</div></div>
        `);
      } else {
        scrollEl.appendChild(renderAssistantMessage(m, idx));
      }
    });
    scrollEl.scrollTop = scrollEl.scrollHeight;
  }

  function renderAssistantMessage(m, idx) {
    const wrap = document.createElement("div");
    wrap.className = "msg-row assistant";
    const chunkCount = (m.retrieved_chunks || []).length;
    wrap.innerHTML = `
      <div class="msg-avatar">AI</div>
      <div class="msg-bubble">
        <div class="assistant-card">
          <div class="assistant-header">
            ${triageBadge(m.triage_level)}
            ${m.confidence_score !== undefined && m.confidence_score !== null ? `<span class="badge badge-neutral">Confidence ${Math.round((m.confidence_score||0)*100)}%</span>` : ""}
            ${m.from_cache ? `<span class="cache-tag">● cache hit</span>` : ""}
          </div>
          <div class="assistant-text">${escapeHtml(m.content)}</div>
          <div class="assistant-footer">
            <div class="why-toggle" data-idx="${idx}">Why this answer? ${icon.chevron}</div>
            <div class="footer-actions">
              <div class="icon-btn" data-action="copy" title="Copy">${icon.copy}</div>
              <div class="icon-btn" data-action="up" title="Helpful">${icon.thumbsUp}</div>
              <div class="icon-btn" data-action="down" title="Not helpful">${icon.thumbsDown}</div>
            </div>
          </div>
          <div class="why-panel">
            <div class="why-body" id="why-${idx}">
              ${renderWhyBody(m)}
            </div>
          </div>
        </div>
      </div>
    `;

    wrap.querySelector(".why-toggle").addEventListener("click", () => {
      wrap.querySelector(`#why-${idx}`).classList.toggle("open");
    });
    wrap.querySelector('[data-action="copy"]').addEventListener("click", () => {
      navigator.clipboard.writeText(m.content);
      toast("Answer copied to clipboard.");
    });
    wrap.querySelector('[data-action="up"]').addEventListener("click", (e) => submitFeedback(m, "positive", e.currentTarget));
    wrap.querySelector('[data-action="down"]').addEventListener("click", (e) => submitFeedback(m, "negative", e.currentTarget));

    return wrap;
  }

  function renderWhyBody(m) {
    const sources = m.sources || [];
    const chunks = m.retrieved_chunks || [];
    const conf = Math.round((m.confidence_score || 0) * 100);
    return `
      <div class="analysis-label">Answer grounded in</div>
      <div class="source-chip-list">
        ${sources.length ? sources.map(s => `<span class="source-chip"><span class="tick">✓</span>${escapeHtml(s)}</span>`).join("") : `<span class="source-chip">No knowledge-base match</span>`}
      </div>
      <div class="analysis-label">Retrieval confidence</div>
      <div class="conf-bar-track"><div class="conf-bar-fill" style="width:${conf}%"></div></div>
      <div style="font-size:12px;color:var(--text-muted);margin-bottom:4px">${conf}%</div>
      <div style="font-size:12px;color:var(--text-secondary);margin:8px 0">${chunks.length} relevant chunk${chunks.length === 1 ? "" : "s"} retrieved · ${triageBadge(m.triage_level)}</div>
      ${chunks.length ? `
        <div class="why-toggle" data-context-toggle="1">View retrieved context ${icon.chevron}</div>
        <div class="chunk-list hidden" data-context-body="1">
          ${chunks.map(c => `
            <div class="chunk-item">
              <div class="chunk-src">${escapeHtml(c.source)}</div>
              <div class="chunk-text">${escapeHtml(c.text)}</div>
            </div>`).join("")}
        </div>` : ""}
      ${m.triage_level === "L2" ? `
        <div style="margin-top:14px">
          <div class="analysis-label">Human review recommended</div>
          <div style="font-size:12.5px;color:var(--text-secondary);margin-bottom:10px">${escapeHtml(m.triage_reason || "")}</div>
          <button class="btn btn-secondary btn-sm" data-open-ticket="1">Create Support Ticket</button>
        </div>` : ""}
    `;
  }

  // Delegate clicks inside dynamically-inserted "why" bodies (context toggle + ticket modal)
  scrollEl.addEventListener("click", (e) => {
    const ctxToggle = e.target.closest("[data-context-toggle]");
    if (ctxToggle) {
      ctxToggle.parentElement.querySelector("[data-context-body]").classList.toggle("hidden");
      return;
    }
    const ticketBtn = e.target.closest("[data-open-ticket]");
    if (ticketBtn) {
      const card = ticketBtn.closest(".assistant-card");
      const idx = Number(card.querySelector(".why-toggle[data-idx]").dataset.idx);
      openTicketModal(messages[idx]);
    }
  });

  async function submitFeedback(m, rating, btnEl) {
    try {
      // find preceding user query for context
      const idx = messages.indexOf(m);
      const userMsg = [...messages.slice(0, idx)].reverse().find(x => x.role === "user");
      await api.feedback(userMsg ? userMsg.content : m.content, m.content, rating);
      btnEl.classList.toggle(rating === "positive" ? "active-up" : "active-down", true);
      toast("Thanks for the feedback.");
    } catch (e) {
      toast(e.message, "error");
    }
  }

  async function handleSend() {
    const text = input.value.trim();
    if (!text || sending) return;
    sending = true;
    input.value = ""; input.style.height = "auto";
    sendBtn.disabled = true;

    messages.push({ role: "user", content: text, timestamp: new Date().toISOString() });
    paintMessages();
    showRetrievalStatus();

    try {
      const result = await api.ask(text, true);
      const assistantMsg = {
        role: "assistant",
        content: result.answer,
        sources: result.sources,
        triage_level: result.triage_level,
        triage_reason: result.triage_reason,
        confidence_score: result.confidence_score,
        from_cache: result.from_cache,
        retrieved_chunks: result.retrieved_chunks,
        timestamp: new Date().toISOString(),
      };
      messages.push(assistantMsg);
      lastAnalysis = assistantMsg;
      paintMessages();
      paintAnalysis(assistantMsg);
    } catch (e) {
      toast(e.message, "error");
      removeRetrievalStatus();
    } finally {
      sending = false;
      sendBtn.disabled = false;
    }
  }

  function showRetrievalStatus() {
    const el = document.createElement("div");
    el.className = "retrieval-status";
    el.id = "retrieval-status";
    el.innerHTML = `<span class="spinner"></span><span id="retrieval-status-text">Retrieving relevant context…</span>`;
    scrollEl.appendChild(el);
    scrollEl.scrollTop = scrollEl.scrollHeight;
    const steps = ["Retrieving relevant context…", "Classifying request…", "Generating grounded response…"];
    let i = 0;
    const timer = setInterval(() => {
      i = (i + 1) % steps.length;
      const t = document.getElementById("retrieval-status-text");
      if (t) t.textContent = steps[i]; else clearInterval(timer);
    }, 900);
    el.dataset.timer = timer;
  }
  function removeRetrievalStatus() {
    const el = document.getElementById("retrieval-status");
    if (el) { clearInterval(Number(el.dataset.timer)); el.remove(); }
  }

  function paintAnalysis(m) {
    removeRetrievalStatus();
    const conf = Math.round((m.confidence_score || 0) * 100);
    const chunkCount = (m.retrieved_chunks || []).length;
    const isL2 = m.triage_level === "L2";

    const riskSignals = isL2 ? deriveRiskSignals(m.triage_reason) : [];

    panel.innerHTML = `
      <div class="analysis-label">AI Analysis</div>
      <div class="analysis-section">
        <div class="analysis-row"><span class="k">Classification</span><span class="v">${triageBadge(m.triage_level)}</span></div>
        <div class="analysis-row"><span class="k">Retrieval confidence</span><span class="v">${conf}%</span></div>
        <div class="analysis-row"><span class="k">Retrieved chunks</span><span class="v">${chunkCount}</span></div>
        <div class="analysis-row"><span class="k">Cache</span><span class="v">${m.from_cache ? "● HIT" : "● MISS"}</span></div>
      </div>
      <div class="analysis-section">
        <div class="analysis-label">Sources</div>
        ${(m.sources || []).length ? (m.sources || []).map(s => `<div style="font-size:12px;color:var(--text-secondary);padding:3px 0;font-family:var(--font-mono)">${escapeHtml(s)}</div>`).join("") : `<div style="font-size:12px;color:var(--text-muted)">No knowledge-base match</div>`}
      </div>
      ${isL2 ? `
        <div class="analysis-section">
          <div class="analysis-label">Risk signals</div>
          ${riskSignals.length ? riskSignals.map(r => `<div class="risk-signal"><span class="dot"></span>${escapeHtml(r)}</div>`).join("") : `<div class="risk-signal"><span class="dot"></span>Low knowledge-base coverage</div>`}
        </div>
        <div class="analysis-section">
          <div class="analysis-label">Recommendation</div>
          <div class="recommendation-box l2">Human review required</div>
          <button class="btn btn-secondary btn-block" style="margin-top:12px" id="panel-ticket-btn">Create Support Ticket</button>
        </div>
      ` : `
        <div class="analysis-section">
          <div class="analysis-label">Recommendation</div>
          <div class="recommendation-box l1">AI resolution</div>
        </div>
      `}
    `;
    const ticketBtn = panel.querySelector("#panel-ticket-btn");
    if (ticketBtn) ticketBtn.addEventListener("click", () => openTicketModal(m));
  }

  function deriveRiskSignals(reason) {
    const r = (reason || "").toLowerCase();
    const signals = [];
    if (r.includes("fraud") || r.includes("hack") || r.includes("breach") || r.includes("security")) signals.push("Security concern");
    if (r.includes("confidence") || r.includes("coverage")) signals.push("Low KB coverage");
    if (r.includes("escalat") || r.includes("keyword")) signals.push("Escalation keyword");
    if (r.includes("complex") || r.includes("word")) signals.push("High complexity");
    return signals;
  }

  function openTicketModal(m) {
    const idx = messages.indexOf(m);
    const userMsg = [...messages.slice(0, idx)].reverse().find(x => x.role === "user");
    const query = userMsg ? userMsg.content : "";

    const overlay = openModal(`
      <div class="modal">
        <div class="modal-header"><h3>Create Support Ticket</h3><div class="icon-btn" id="modal-close">✕</div></div>
        <div class="modal-body">
          <div class="modal-info-box"><strong>AI-generated summary</strong><br/>${escapeHtml(m.content.slice(0, 220))}${m.content.length > 220 ? "…" : ""}</div>
          <div class="field-row">
            <div class="field"><label>Priority</label>
              <select class="select" id="tk-priority">
                <option value="low">Low</option><option value="normal">Normal</option>
                <option value="high">High</option><option value="critical">Critical</option>
              </select>
            </div>
            <div class="field"><label>Category</label>
              <select class="select" id="tk-category">
                <option value="general">General</option><option value="billing">Billing</option>
                <option value="account">Account</option><option value="shipping">Shipping</option>
                <option value="technical">Technical</option><option value="security">Security</option>
              </select>
            </div>
          </div>
          <div class="field"><label>Suggested response</label>
            <textarea class="input" id="tk-response" rows="3">Human investigation required.</textarea>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" id="modal-cancel">Cancel</button>
          <button class="btn btn-primary" id="modal-create">Create Ticket</button>
        </div>
      </div>
    `);

    api.ticketSuggest(query, m.triage_reason || "").then(s => {
      overlay.querySelector("#tk-priority").value = s.priority;
      overlay.querySelector("#tk-category").value = s.category;
    }).catch(() => {});

    overlay.querySelector("#modal-close").addEventListener("click", closeModal);
    overlay.querySelector("#modal-cancel").addEventListener("click", closeModal);
    overlay.querySelector("#modal-create").addEventListener("click", async () => {
      const btn = overlay.querySelector("#modal-create");
      btn.disabled = true; btn.textContent = "Creating…";
      try {
        const ticket = await api.createTicket({
          query,
          ai_summary: m.content.slice(0, 500),
          suggested_response: overlay.querySelector("#tk-response").value,
          category: overlay.querySelector("#tk-category").value,
          priority: overlay.querySelector("#tk-priority").value,
          triage_reason: m.triage_reason || "",
          confidence_score: m.confidence_score || 0,
          sources: m.sources || [],
        });
        closeModal();
        toast(`Ticket #${ticket.ticket_number} created`);
      } catch (e) {
        toast(e.message, "error");
        btn.disabled = false; btn.textContent = "Create Ticket";
      }
    });
  }
}
