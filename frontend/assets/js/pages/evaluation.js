import { api } from "../api.js";
import { escapeHtml, pct, fmtDate, toast, icon } from "../ui.js";

export async function renderEvaluation(root, user) {
  root.innerHTML = `<div class="page-pad"><div class="spin-loader">Loading evaluation history…</div></div>`;

  if (user.role !== "admin") {
    root.innerHTML = `
      <div class="page-pad">
        <div class="section-title">RAG Evaluation</div>
        <div class="empty-state">
          ${icon.check}
          <h3>Admin access required</h3>
          <p>Evaluation runs and test-case results are visible to workspace admins.</p>
        </div>
      </div>`;
    return;
  }

  let history = [];
  try {
    const data = await api.evalHistory();
    history = data.runs || [];
  } catch (e) {
    root.innerHTML = `<div class="page-pad"><div class="error-state"><h3>We couldn't load evaluation history</h3><p>${escapeHtml(e.message)}</p><button class="btn btn-secondary" id="retry">Retry</button></div></div>`;
    root.querySelector("#retry")?.addEventListener("click", () => renderEvaluation(root, user));
    return;
  }

  paint(history[0] || null);

  function paint(latest) {
    root.innerHTML = `
      <div class="page-pad">
        <div style="display:flex;align-items:center;justify-content:space-between">
          <div>
            <div class="section-title">RAG Evaluation</div>
            <div class="section-sub">Faithfulness, relevance, and triage accuracy against the labeled test set.</div>
          </div>
          <button class="btn btn-primary" id="run-eval-btn">Run Evaluation</button>
        </div>

        ${latest ? renderSummary(latest) : renderEmptySummary()}

        ${latest ? `
          <div class="card card-pad" style="margin-top:16px">
            <div class="card-title">Test Cases</div>
            <div class="card-subtitle">Run ${escapeHtml(latest.run_id)} · ${fmtDate(latest.run_timestamp)}</div>
            <div id="testcase-list"><div class="spin-loader">Loading test cases…</div></div>
          </div>
        ` : ""}

        <div class="card card-pad" style="margin-top:16px">
          <div class="card-title">Run History</div>
          <div class="table-wrap">
            <table class="data-table">
              <thead><tr><th>Run</th><th>Date</th><th>Questions</th><th>Answer F1</th><th>Triage Accuracy</th></tr></thead>
              <tbody>
                ${history.map(r => `
                  <tr>
                    <td class="mono">${escapeHtml(r.run_id)}</td>
                    <td class="mono">${fmtDate(r.run_timestamp)}</td>
                    <td>${r.total_questions}</td>
                    <td>${pct(Math.round((r.avg_answer_f1 || 0) * 100))}</td>
                    <td>${pct(Math.round((r.triage_accuracy || 0) * 100))}</td>
                  </tr>
                `).join("") || `<tr><td colspan="5" style="color:var(--text-muted)">No runs yet.</td></tr>`}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    `;

    root.querySelector("#run-eval-btn").addEventListener("click", async (e) => {
      const btn = e.currentTarget;
      btn.disabled = true; btn.textContent = "Running…";
      try {
        await api.evalRun();
        toast("Evaluation run complete.");
        const data = await api.evalHistory();
        history = data.runs || [];
        paint(history[0] || null);
      } catch (err) {
        toast(err.message, "error");
        btn.disabled = false; btn.textContent = "Run Evaluation";
      }
    });

    if (latest) loadTestCases(latest.run_id);
  }

  function renderSummary(s) {
    const metric = (v) => pct(Math.round((v || 0) * 100));
    return `
      <div class="metric-ring-row">
        <div class="kpi"><div class="kpi-label">Answer F1</div><div class="kpi-value accent">${metric(s.avg_answer_f1)}</div></div>
        <div class="kpi"><div class="kpi-label">Answer Precision</div><div class="kpi-value">${metric(s.avg_answer_precision)}</div></div>
        <div class="kpi"><div class="kpi-label">Answer Recall</div><div class="kpi-value">${metric(s.avg_answer_recall)}</div></div>
        <div class="kpi"><div class="kpi-label">Triage Accuracy</div><div class="kpi-value">${metric(s.triage_accuracy)}</div></div>
        <div class="kpi"><div class="kpi-label">KB Coverage</div><div class="kpi-value">${metric(s.coverage_rate)}</div></div>
        <div class="kpi"><div class="kpi-label">Avg Latency</div><div class="kpi-value">${Math.round(s.avg_latency_ms || 0)}ms</div></div>
      </div>
      <div class="grid-2">
        <div class="card card-pad">
          <div class="card-title">L1 (AI resolution) precision / recall</div>
          <div class="hbar-row"><div class="hbar-label">Precision</div><div class="hbar-track"><div class="hbar-fill" style="width:${(s.l1_precision||0)*100}%"></div></div><div class="hbar-value">${metric(s.l1_precision)}</div></div>
          <div class="hbar-row"><div class="hbar-label">Recall</div><div class="hbar-track"><div class="hbar-fill" style="width:${(s.l1_recall||0)*100}%"></div></div><div class="hbar-value">${metric(s.l1_recall)}</div></div>
        </div>
        <div class="card card-pad">
          <div class="card-title">L2 (human review) precision / recall</div>
          <div class="hbar-row"><div class="hbar-label">Precision</div><div class="hbar-track"><div class="hbar-fill" style="width:${(s.l2_precision||0)*100}%;background:var(--warning)"></div></div><div class="hbar-value">${metric(s.l2_precision)}</div></div>
          <div class="hbar-row"><div class="hbar-label">Recall</div><div class="hbar-track"><div class="hbar-fill" style="width:${(s.l2_recall||0)*100}%;background:var(--warning)"></div></div><div class="hbar-value">${metric(s.l2_recall)}</div></div>
        </div>
      </div>
    `;
  }

  function renderEmptySummary() {
    return `
      <div class="empty-state">
        ${icon.check}
        <h3>No evaluation runs yet.</h3>
        <p>Run the evaluation suite against the labeled test set to see faithfulness, relevance, and triage accuracy.</p>
      </div>
    `;
  }

  async function loadTestCases(runId) {
    const container = root.querySelector("#testcase-list");
    if (!container) return;
    try {
      const data = await api.evalDetail(runId);
      const results = data.results || [];
      if (!results.length) { container.innerHTML = `<div style="color:var(--text-muted);font-size:12.5px">No per-question detail stored for this run.</div>`; return; }
      container.innerHTML = results.map((r, i) => {
        const outcome = r.triage_correct && r.answer_f1 >= 0.5 ? "pass" : (r.triage_correct || r.answer_f1 >= 0.3 ? "partial" : "fail");
        const icons = { pass: "✓ PASS", partial: "⚠ PARTIAL", fail: "✕ FAIL" };
        const classes = { pass: "result-pass", partial: "result-partial", fail: "result-fail" };
        return `
          <div class="testcase">
            <div class="testcase-head" data-i="${i}">
              <div class="testcase-q">${escapeHtml(r.question)}</div>
              <div class="${classes[outcome]}" style="font-size:12px;font-weight:600">${icons[outcome]}</div>
            </div>
            <div class="testcase-body" id="tc-${i}">
              <div class="row"><div class="lab">Expected</div>${escapeHtml(r.expected_answer)}</div>
              <div class="row"><div class="lab">Generated answer</div>${escapeHtml(r.predicted_answer)}</div>
              <div class="row"><div class="lab">Retrieved sources</div>${(r.sources_retrieved || []).join(", ") || "—"}</div>
              <div class="row"><div class="lab">Triage</div>${escapeHtml(r.predicted_triage)} (expected ${escapeHtml(r.expected_triage)}) · F1 ${Math.round((r.answer_f1||0)*100)}% · ${Math.round(r.latency_ms||0)}ms</div>
            </div>
          </div>
        `;
      }).join("");
      container.querySelectorAll(".testcase-head").forEach(h => {
        h.addEventListener("click", () => {
          document.getElementById(`tc-${h.dataset.i}`).classList.toggle("open");
        });
      });
    } catch (e) {
      container.innerHTML = `<div style="color:var(--text-muted);font-size:12.5px">Couldn't load test case detail.</div>`;
    }
  }
}
