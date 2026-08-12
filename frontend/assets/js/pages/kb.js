import { api } from "../api.js";
import { escapeHtml, timeAgo, toast, icon } from "../ui.js";

export async function renderKB(root, user) {
  root.innerHTML = `<div class="page-pad"><div class="spin-loader">Loading knowledge base…</div></div>`;

  const [documents, health] = await Promise.all([
    api.kbDocuments().catch(() => ({ documents: [] })),
    api.kbHealth().catch(() => null),
  ]);

  paint(documents.documents || [], health);

  function paint(docs, health) {
    const totalChunks = docs.reduce((s, d) => s + d.chunks, 0);
    root.innerHTML = `
      <div class="page-pad">
        <div class="section-title">Knowledge Base</div>
        <div class="section-sub">Documents indexed into the vector store, and the pipeline that keeps them fresh.</div>

        <div class="kpi-row">
          <div class="kpi"><div class="kpi-label">Documents</div><div class="kpi-value">${docs.length}</div></div>
          <div class="kpi"><div class="kpi-label">Chunks</div><div class="kpi-value">${totalChunks}</div></div>
          <div class="kpi"><div class="kpi-label">Updated</div><div class="kpi-value" style="font-size:16px">${health && health.last_indexed ? timeAgo(health.last_indexed) : "—"}</div></div>
        </div>

        <div class="grid-2" style="align-items:start">
          <div class="card card-pad">
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px">
              <div>
                <div class="card-title">Documents</div>
                <div class="card-subtitle">TXT and PDF files in the support knowledge base</div>
              </div>
              <div style="display:flex;gap:8px">
                <label class="btn btn-secondary btn-sm" style="cursor:pointer">${icon.upload} Upload<input type="file" id="upload-input" accept=".txt,.pdf" class="hidden" /></label>
                <button class="btn btn-primary btn-sm" id="ingest-btn">Ingest Knowledge Base</button>
              </div>
            </div>
            ${docs.length ? renderDocTable(docs) : renderEmptyDocs()}
          </div>

          <div class="card card-pad">
            <div class="card-title">Knowledge Base Health</div>
            <div class="card-subtitle">Live status from the vector store</div>
            ${renderHealth(health)}
          </div>
        </div>
      </div>
    `;

    const uploadInput = root.querySelector("#upload-input");
    uploadInput.addEventListener("change", async () => {
      const file = uploadInput.files[0];
      if (!file) return;
      try {
        await api.kbUpload(file);
        toast(`'${file.name}' uploaded. Run ingestion to add it to the knowledge base.`);
        refresh();
      } catch (e) {
        toast(e.message, "error");
      }
    });

    root.querySelector("#ingest-btn").addEventListener("click", async (e) => {
      if (user.role !== "admin") { toast("Admin role required to run ingestion.", "error"); return; }
      const btn = e.currentTarget;
      btn.disabled = true; btn.textContent = "Ingesting…";
      try {
        await api.kbIngest();
        toast("Ingestion started — this can take a minute for larger knowledge bases.");
        pollIngestStatus(btn);
      } catch (err) {
        toast(err.message, "error");
        btn.disabled = false; btn.textContent = "Ingest Knowledge Base";
      }
    });
  }

  async function pollIngestStatus(btn) {
    const check = async () => {
      try {
        const s = await api.kbIngestStatus();
        if (s.running) {
          setTimeout(check, 2000);
        } else {
          btn.disabled = false; btn.textContent = "Ingest Knowledge Base";
          if (s.last_error) toast(`Ingestion failed: ${s.last_error}`, "error");
          else if (s.last_result) toast(`Ingestion complete — ${s.last_result.chunks_stored} chunks stored.`);
          refresh();
        }
      } catch (e) {
        btn.disabled = false; btn.textContent = "Ingest Knowledge Base";
      }
    };
    setTimeout(check, 2000);
  }

  async function refresh() {
    const [d, h] = await Promise.all([api.kbDocuments().catch(() => ({ documents: [] })), api.kbHealth().catch(() => null)]);
    paint(d.documents || [], h);
  }

  function renderDocTable(docs) {
    return `
      <div class="table-wrap">
        <table class="data-table">
          <thead><tr><th>Document</th><th>Chunks</th><th>Updated</th></tr></thead>
          <tbody>
            ${docs.map(d => `
              <tr>
                <td class="mono">${escapeHtml(d.filename)}</td>
                <td>${d.chunks}${d.chunks === 0 ? ' <span style="color:var(--warning);font-size:11px">not indexed</span>' : ""}</td>
                <td class="mono">${timeAgo(d.updated_at)}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    `;
  }

  function renderEmptyDocs() {
    return `
      <div class="empty-state">
        ${icon.book}
        <h3>No documents yet.</h3>
        <p>Upload a TXT or PDF file to add it to the support knowledge base.</p>
      </div>
    `;
  }

  function renderHealth(health) {
    if (!health) {
      return `<div class="error-state"><h3>We couldn't complete the AI analysis</h3><p>The knowledge-base service may be temporarily unavailable.</p></div>`;
    }
    const quality = health.chunks_indexed > 0 ? "GOOD" : "NOT READY";
    const coverage = health.chunks_on_disk > 0
      ? Math.min(100, Math.round((health.chunks_indexed / health.chunks_on_disk) * 100))
      : 0;
    return `
      <div class="analysis-row"><span class="k">Documents</span><span class="v">${health.documents}</span></div>
      <div class="analysis-row"><span class="k">Chunks on disk</span><span class="v">${health.chunks_on_disk}</span></div>
      <div class="analysis-row"><span class="k">Chunks indexed</span><span class="v">${health.chunks_indexed}</span></div>
      <div class="analysis-row"><span class="k">Embedding model</span><span class="v mono" style="font-weight:400">${escapeHtml(health.embedding_model)}</span></div>
      <div class="analysis-row"><span class="k">Vector database</span><span class="v">${escapeHtml(health.vector_database)}</span></div>
      <div class="analysis-row"><span class="k">Last indexed</span><span class="v">${health.last_indexed ? timeAgo(health.last_indexed) : "—"}</span></div>
      <div class="analysis-row"><span class="k">Retrieval quality</span><span class="v" style="color:${quality === "GOOD" ? "var(--accent)" : "var(--warning)"}">${quality}</span></div>
      <div class="analysis-row"><span class="k">Indexed coverage</span><span class="v">${coverage}%</span></div>
      ${health.documents_not_yet_indexed && health.documents_not_yet_indexed.length ? `
        <div style="margin-top:12px;font-size:12px;color:var(--warning)">⚠ ${health.documents_not_yet_indexed.length} document(s) haven't been indexed yet</div>
      ` : ""}
    `;
  }
}
