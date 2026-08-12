import { api } from "../api.js";
import { escapeHtml, pct } from "../ui.js";

export async function renderAnalytics(root) {
  root.innerHTML = `<div class="page-pad"><div class="spin-loader">Loading analytics…</div></div>`;

  const [overview, trend, categories, escalation, cache] = await Promise.all([
    api.analyticsOverview().catch(() => null),
    api.analyticsTrend(14).catch(() => ({ trend: [] })),
    api.analyticsCategories().catch(() => ({ categories: [] })),
    api.analyticsEscalation().catch(() => ({ reasons: [] })),
    api.analyticsCache().catch(() => ({ hits: 0, misses: 0, hit_rate: 0 })),
  ]);

  if (!overview) {
    root.innerHTML = `<div class="page-pad"><div class="error-state"><h3>We couldn't load analytics</h3><p>The API may be temporarily unavailable.</p></div></div>`;
    return;
  }

  root.innerHTML = `
    <div class="page-pad">
      <div class="section-title">Analytics</div>
      <div class="section-sub">Support operations performance, computed from real logged conversations.</div>

      <div class="kpi-row">
        <div class="kpi"><div class="kpi-label">Total Queries</div><div class="kpi-value">${overview.total_queries}</div></div>
        <div class="kpi"><div class="kpi-label">AI Resolved</div><div class="kpi-value accent">${overview.ai_resolved}</div></div>
        <div class="kpi"><div class="kpi-label">Automation Rate</div><div class="kpi-value">${pct(overview.automation_rate)}</div></div>
        <div class="kpi"><div class="kpi-label">Avg Confidence</div><div class="kpi-value">${pct(overview.avg_confidence)}</div></div>
        <div class="kpi"><div class="kpi-label">Satisfaction</div><div class="kpi-value">${overview.satisfaction_rate === null ? "No feedback yet" : pct(overview.satisfaction_rate)}</div></div>
        <div class="kpi"><div class="kpi-label">Cache Hit Rate</div><div class="kpi-value">${pct(overview.cache_hit_rate)}</div></div>
      </div>

      <div class="grid-2" style="margin-bottom:16px">
        <div class="card card-pad">
          <div class="card-title">Resolution trend</div>
          <div class="card-subtitle">AI-resolved vs. escalated queries, last 14 days</div>
          ${renderTrend(trend.trend)}
        </div>
        <div class="card card-pad">
          <div class="card-title">Query categories</div>
          <div class="card-subtitle">Keyword-based classification of incoming questions</div>
          ${renderHBars(categories.categories.map(c => ({ label: c.category, value: c.count })))}
        </div>
      </div>

      <div class="grid-2">
        <div class="card card-pad">
          <div class="card-title">Escalation reasons</div>
          <div class="card-subtitle">Why queries were routed to L2 human review</div>
          ${renderHBars(escalation.reasons.map(r => ({ label: r.reason, value: r.count })))}
        </div>
        <div class="card card-pad">
          <div class="card-title">Cache performance</div>
          <div class="card-subtitle">Response cache hit rate across all queries</div>
          ${renderCache(cache)}
        </div>
      </div>

      <div class="card card-pad" style="margin-top:16px">
        <div class="card-title">Feedback</div>
        <div class="card-subtitle">👍 / 👎 ratings collected on generated answers</div>
        <div style="display:flex;gap:32px;align-items:center">
          <div><div class="kpi-value accent" style="font-size:22px">${overview.positive_feedback}</div><div style="font-size:11.5px;color:var(--text-muted)">Positive</div></div>
          <div><div class="kpi-value danger" style="font-size:22px">${overview.negative_feedback}</div><div style="font-size:11.5px;color:var(--text-muted)">Negative</div></div>
        </div>
      </div>
    </div>
  `;
}

function renderTrend(trend) {
  if (!trend.length) return `<div style="color:var(--text-muted);font-size:12.5px;padding:30px 0;text-align:center">No conversation history yet in the selected window.</div>`;
  const max = Math.max(1, ...trend.map(d => d.ai_resolved + d.escalated));
  return `
    <div class="bars">
      ${trend.map(d => {
        const aiH = Math.round((d.ai_resolved / max) * 130);
        const escH = Math.round((d.escalated / max) * 130);
        return `
          <div class="bar-col">
            <div class="bar-stack" style="height:${aiH + escH}px">
              <div class="bar-seg esc" style="height:${escH}px"></div>
              <div class="bar-seg ai" style="height:${aiH}px"></div>
            </div>
            <div class="label">${escapeHtml(d.date.slice(5))}</div>
          </div>`;
      }).join("")}
    </div>
    <div class="legend">
      <span><span class="sw" style="background:var(--accent)"></span>AI resolved</span>
      <span><span class="sw" style="background:var(--warning)"></span>Escalated</span>
    </div>
  `;
}

function renderHBars(items) {
  const clean = items.filter(i => i.value > 0);
  if (!clean.length) return `<div style="color:var(--text-muted);font-size:12.5px;padding:20px 0;text-align:center">No data yet.</div>`;
  const max = Math.max(...clean.map(i => i.value));
  return clean.map(i => `
    <div class="hbar-row">
      <div class="hbar-label" style="text-transform:capitalize">${escapeHtml(i.label)}</div>
      <div class="hbar-track"><div class="hbar-fill" style="width:${Math.round((i.value / max) * 100)}%"></div></div>
      <div class="hbar-value">${i.value}</div>
    </div>
  `).join("");
}

function renderCache(cache) {
  const total = cache.hits + cache.misses;
  if (!total) return `<div style="color:var(--text-muted);font-size:12.5px;padding:20px 0;text-align:center">No queries logged yet.</div>`;
  return `
    <div class="hbar-row"><div class="hbar-label">Hits</div><div class="hbar-track"><div class="hbar-fill" style="width:${(cache.hits/total)*100}%"></div></div><div class="hbar-value">${cache.hits}</div></div>
    <div class="hbar-row"><div class="hbar-label">Misses</div><div class="hbar-track"><div class="hbar-fill" style="width:${(cache.misses/total)*100}%;background:var(--text-muted)"></div></div><div class="hbar-value">${cache.misses}</div></div>
    <div style="font-size:12.5px;color:var(--text-secondary);margin-top:6px">Hit rate: <strong>${pct(cache.hit_rate)}</strong></div>
  `;
}
